import client from './client';

export interface CveItem {
  cve_id: string;
  title?: string;
  description: string;
  cvss_score: number | null;
  severity: string;
  published: string;
  modified?: string;
  component: string;
  vector?: string | null;
  references?: string[];
  source?: string;
}

export interface CveFeedResponse {
  source: string;
  keyword: string;
  fetched_at: string;
  total: number;
  cves: CveItem[];
  warning?: string;
}

export interface CveSummaryResponse {
  total: number;
  critical: number;
  high: number;
  medium: number;
  latest_date: string;
  top_component: string;
  fetched_at: string;
}

export const getCves = () => client.get<CveFeedResponse>('/api/cves/');

export const searchCves = (query: string) =>
  client.get<CveFeedResponse>('/api/cves/search', { params: { q: query } });

export const getCveSummary = () =>
  client.get<CveSummaryResponse>('/api/cves/summary');
