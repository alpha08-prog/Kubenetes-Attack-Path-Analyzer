import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 45000,
});

// Global response interceptor — surfaces meaningful error messages
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return Promise.reject(new Error('Request timed out. The algorithm may still be running — try again in a moment.'));
    }
    if (!error.response) {
      return Promise.reject(new Error('Cannot reach backend. Make sure the server is running on port 8000.'));
    }
    const detail = error.response?.data?.detail || error.response?.data?.error || error.message;
    return Promise.reject(new Error(detail || `Server error (${error.response.status})`));
  }
);

export default client;
