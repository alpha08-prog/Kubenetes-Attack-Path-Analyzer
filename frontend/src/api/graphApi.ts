import client from './client';

export const getGraph = () => client.get('/api/graph');
export const getGraphSummary = () => client.get('/api/graph/summary');
export const reloadGraph = () => client.post('/api/graph/reload');

export const getAttackPath = (source: string, target: string) =>
  client.post('/api/attack/path', { source, target });
export const getAutoAttackPath = () => client.get('/api/attack/auto');

export const getBlastRadius = (nodeId: string, maxHops: number) =>
  client.post('/api/blast/radius', { node_id: nodeId, max_hops: maxHops });

export const getCycles = () => client.get('/api/cycles');
export const getCriticalNodes = (topN = 10) =>
  client.get('/api/critical/nodes', { params: { top_n: topN } });
export const getRemovalCandidates = (source: string, target: string) =>
  client.get('/api/critical/candidates', { params: { source, target } });

export const simulateRemoval = (nodeId: string, source: string, target: string) =>
  client.post('/api/simulate/remove', { node_id: nodeId, source, target });
export const getAutoSimulation = () => client.get('/api/simulate/auto');

export const getReport = (clusterName = 'nokia-telecom-cluster') =>
  client.get('/api/report', { params: { cluster_name: clusterName } });

export const getReportPdf = (clusterName = 'nokia-telecom-cluster') =>
  client.get('/api/report/pdf', {
    params: { cluster_name: clusterName },
    responseType: 'blob',
  });

export const getFullAnalysis = () => client.get('/api/analysis');

// History
export const getRunHistory = (limit = 20) =>
  client.get('/api/history', { params: { limit } });

// Diff
export const getDiffLatest = () => client.get('/api/diff/latest');
export const compareDiffRuns = (run_id_before: string, run_id_after: string) =>
  client.post('/api/diff/compare', { run_id_before, run_id_after });
export const getDiffVsCurrent = (runId: string) =>
  client.get(`/api/diff/vs-current/${runId}`);
