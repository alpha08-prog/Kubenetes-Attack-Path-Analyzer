import client from './client';

export interface SnapshotMeta {
  node_count: number;
  edge_count: number;
  entry_points: string[];
  sensitive_targets: string[];
  cycles_detected: number;
  aggregate_risk: number;
}

export interface SnapshotTrigger {
  source: string;
  description: string;
}

export interface GraphSnapshot {
  snapshot_id: string;
  cluster_name: string;
  timestamp: string;
  trigger: SnapshotTrigger;
  metadata: SnapshotMeta;
}

export interface GraphSnapshotFull extends GraphSnapshot {
  nodes: Record<string, any>[];
  edges: Record<string, any>[];
}

export interface SnapshotDiff {
  diff_id: string;
  snapshot_id_before: string;
  snapshot_id_after: string;
  timestamp_before: string;
  timestamp_after: string;
  nodes_added: string[];
  nodes_removed: string[];
  nodes_risk_increased: { id: string; label: string; old_risk: number; new_risk: number; delta: number }[];
  nodes_risk_decreased: { id: string; label: string; old_risk: number; new_risk: number; delta: number }[];
  edges_added: { source: string; target: string }[];
  edges_removed: { source: string; target: string }[];
  new_attack_paths: { source: string; target: string }[];
  disappeared_paths: { source: string; target: string }[];
  new_cycles: { nodes: string[] }[];
  disappeared_cycles: { nodes: string[] }[];
  overall_risk_delta: number;
  high_risk_nodes_delta: number;
  nodes_added_count: number;
  nodes_removed_count: number;
  edges_added_count: number;
  edges_removed_count: number;
  new_attack_paths_count: number;
  disappeared_paths_count: number;
  new_cycles_count: number;
  disappeared_cycles_count: number;
  severity: string;
  alert_triggered: boolean;
  alert_reasons: string[];
  computed_at: string;
}

export interface TimelinePoint {
  snapshot_id: string;
  timestamp: string;
  aggregate_risk: number;
  node_count: number;
  edge_count: number;
  cycles_detected: number;
}

export interface TemporalAlert {
  alert_id: string;
  diff_id: string;
  severity: string;
  title: string;
  description: string;
  new_paths: { source: string; target: string }[];
  new_cycles: { nodes: string[] }[];
  risk_delta: number;
  triggered_at: string;
  acknowledged_at?: string;
}

export const listSnapshots = (limit = 20, offset = 0) =>
  client.get<{ snapshots: GraphSnapshot[]; total: number; limit: number; offset: number }>(
    '/api/snapshots/',
    { params: { limit, offset } }
  );

export const getSnapshot = (snapshotId: string) =>
  client.get<GraphSnapshotFull>(`/api/snapshots/${snapshotId}`);

export const createSnapshot = (triggerSource = 'manual', description = 'Manual snapshot') =>
  client.post<GraphSnapshot & { diff?: Partial<SnapshotDiff> }>('/api/snapshots/', {
    trigger_source: triggerSource,
    description,
  });

export const diffSnapshots = (id1: string, id2: string) =>
  client.get<SnapshotDiff>(`/api/snapshots/${id1}/diff/${id2}`);

export const getSnapshotTimeline = (days = 7) =>
  client.get<{ timeline: TimelinePoint[]; days: number }>('/api/snapshots/timeline', {
    params: { days },
  });

export const listAlerts = (limit = 20, severity?: string) =>
  client.get<{ alerts: TemporalAlert[]; total: number }>('/api/snapshots/alerts', {
    params: { limit, ...(severity ? { severity } : {}) },
  });
