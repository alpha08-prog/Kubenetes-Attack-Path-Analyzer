export const NODE_COLORS: Record<string, string> = {
  pod: '#378ADD',
  service_account: '#1D9E75',
  role: '#7F77DD',
  secret: '#BA7517',
  database: '#E24B4A',
  user: '#D85A30',
};

export const NODE_SHAPES: Record<string, string> = {
  pod: 'rectangle',
  service_account: 'ellipse',
  role: 'diamond',
  secret: 'triangle',
  database: 'barrel',
  user: 'hexagon',
};

export const NODE_LABELS: Record<string, string> = {
  pod: 'Pod',
  service_account: 'Service Account',
  role: 'Role',
  secret: 'Secret',
  database: 'Database',
  user: 'User',
};

export const SEVERITY_COLORS: Record<string, string> = {
  critical: '#E24B4A',
  high: '#EF9F27',
  medium: '#378ADD',
  low: '#1D9E75',
};

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'];
