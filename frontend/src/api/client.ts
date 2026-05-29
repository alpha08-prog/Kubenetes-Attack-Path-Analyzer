import axios, { AxiosError, AxiosResponse } from 'axios';
import { resolveMock } from './mock/router';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 45000,
});

// Optional kill-switch via Vite env: set VITE_API_MOCK=off in .env to disable
// the mock fallback entirely (and surface real backend errors).
const MOCK_DISABLED =
  ((import.meta as any).env?.VITE_API_MOCK ?? '').toString().toLowerCase() === 'off';

function buildSyntheticResponse(error: AxiosError): AxiosResponse | null {
  if (MOCK_DISABLED) return null;
  if (!error.config) return null;
  const mock = resolveMock(error.config);
  if (!mock) return null;
  return {
    data: mock.data,
    status: mock.status,
    statusText: 'OK (mock)',
    headers: mock.headers ?? { 'x-mock-mode': 'true' },
    config: error.config,
    request: error.request,
  };
}

// Global response interceptor — surfaces meaningful error messages and falls
// back to canned mock data when the backend is unreachable so the UI keeps
// rendering a complete picture instead of bare error toasts.
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const isNetworkError = !error.response;
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');

    if (isNetworkError || isTimeout) {
      const synthetic = buildSyntheticResponse(error);
      if (synthetic) return Promise.resolve(synthetic);
    }

    if (isTimeout) {
      return Promise.reject(new Error('Request timed out. The algorithm may still be running — try again in a moment.'));
    }
    if (isNetworkError) {
      return Promise.reject(new Error('Cannot reach backend. Make sure the server is running on port 8000.'));
    }
    const respData = error.response?.data as { detail?: string; error?: string } | undefined;
    const detail = respData?.detail || respData?.error || error.message;
    return Promise.reject(new Error(detail || `Server error (${error.response?.status})`));
  }
);

export default client;
