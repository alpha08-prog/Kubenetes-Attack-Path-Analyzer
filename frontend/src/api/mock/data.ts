// Self-contained mock graph + derived analytics, served when the backend is
// unreachable so the dashboard still renders a complete picture.
//
// Shape mirrors the Nokia telecom scenario the backend ships with — the
// frontend's existing normalizers and components consume it unchanged.

export interface MockNode {
  id: string;
  label: string;
  type: string;
  risk: number;
  namespace: string;
  is_source?: boolean;
  is_sink?: boolean;
  metadata?: Record<string, any>;
}

export interface MockEdge {
  source: string;
  target: string;
  relation: string;
  risk: number;
  weight: number;
}

export const MOCK_NODES: MockNode[] = [
  // pods
  { id: 'pod:default:web-server', label: 'web-server', type: 'pod', risk: 7.5, is_source: true, namespace: 'default',
    metadata: { image: ['nginx:1.19'], host_network: false, privileged: false, phase: 'Running', note: 'Public-facing pod — attacker entry point' } },
  { id: 'pod:default:api-server', label: 'api-server', type: 'pod', risk: 8.0, namespace: 'default',
    metadata: { image: ['node:18-alpine'], privileged: false, phase: 'Running', note: 'Internal API pod with overbroad SA' } },
  { id: 'pod:default:metrics-collector', label: 'metrics-collector', type: 'pod', risk: 6.0, namespace: 'default',
    metadata: { image: ['prom/prometheus:v2.40.0'], privileged: false, phase: 'Running' } },
  { id: 'pod:kube-system:coredns', label: 'coredns', type: 'pod', risk: 5.5, namespace: 'kube-system',
    metadata: { image: ['registry.k8s.io/coredns/coredns:v1.10.1'], phase: 'Running' } },
  { id: 'pod:kube-system:kube-proxy', label: 'kube-proxy', type: 'pod', risk: 8.0, namespace: 'kube-system',
    metadata: { image: ['registry.k8s.io/kube-proxy:v1.35.1'], host_network: true, privileged: true, phase: 'Running' } },

  // service accounts
  { id: 'service_account:default:backend-sa', label: 'backend-sa', type: 'service_account', risk: 8.5, namespace: 'default',
    metadata: { note: 'Overbroad SA — bound to admin-role' } },
  { id: 'service_account:default:metrics-sa', label: 'metrics-sa', type: 'service_account', risk: 4.5, namespace: 'default', metadata: {} },
  { id: 'service_account:kube-system:coredns-sa', label: 'coredns-sa', type: 'service_account', risk: 5.0, namespace: 'kube-system', metadata: {} },

  // roles
  { id: 'role:default:admin-role', label: 'admin-role', type: 'role', risk: 9.5, namespace: 'default',
    metadata: { has_wildcard: true, cluster_scoped: false, note: 'Wildcard role — can read all secrets' } },
  { id: 'role:default:secret-reader', label: 'secret-reader', type: 'role', risk: 7.5, namespace: 'default',
    metadata: { has_wildcard: false } },
  { id: 'role:default:metrics-role', label: 'metrics-role', type: 'role', risk: 3.5, namespace: 'default', metadata: {} },
  { id: 'role:cluster:cluster-admin', label: 'cluster-admin', type: 'role', risk: 10.0, namespace: 'cluster',
    metadata: { has_wildcard: true, cluster_scoped: true, note: 'Full cluster access — maximum risk' } },

  // secrets
  { id: 'secret:default:db-credentials', label: 'db-credentials', type: 'secret', risk: 9.0, namespace: 'default',
    metadata: { secret_type: 'Opaque', is_db_creds: true, note: 'Contains plaintext DB password — critical exposure' } },
  { id: 'secret:default:tls-cert', label: 'tls-cert', type: 'secret', risk: 5.5, namespace: 'default',
    metadata: { secret_type: 'kubernetes.io/tls', is_db_creds: false } },
  { id: 'secret:default:api-token', label: 'api-token', type: 'secret', risk: 8.0, namespace: 'default',
    metadata: { secret_type: 'kubernetes.io/service-account-token', is_db_creds: false, note: 'SA token — can be used to impersonate backend-sa' } },

  // databases
  { id: 'database:default:billing-db', label: 'billing-db', type: 'database', risk: 9.5, is_sink: true, namespace: 'default',
    metadata: { engine: 'PostgreSQL', note: 'Production billing database — primary target' } },
  { id: 'database:default:analytics-db', label: 'analytics-db', type: 'database', risk: 7.0, is_sink: true, namespace: 'default',
    metadata: { engine: 'ClickHouse', note: 'Telemetry analytics store' } },

  // users
  { id: 'user:cluster:dev-1', label: 'dev-1', type: 'user', risk: 6.5, is_source: true, namespace: 'cluster',
    metadata: { note: 'Developer with secret-reader binding — lateral move risk' } },
  { id: 'user:cluster:ci-bot', label: 'ci-bot', type: 'user', risk: 7.5, is_source: true, namespace: 'cluster',
    metadata: { note: 'CI/CD service user bound to cluster-admin — over-privileged' } },
];

export const MOCK_EDGES: MockEdge[] = [
  { source: 'pod:default:web-server',           target: 'service_account:default:backend-sa',  relation: 'uses',              risk: 7.5, weight: 2.5 },
  { source: 'pod:default:api-server',           target: 'service_account:default:backend-sa',  relation: 'uses',              risk: 8.0, weight: 2.0 },
  { source: 'pod:default:metrics-collector',    target: 'service_account:default:metrics-sa',  relation: 'uses',              risk: 4.5, weight: 5.5 },
  { source: 'pod:kube-system:coredns',          target: 'service_account:kube-system:coredns-sa', relation: 'uses',           risk: 5.0, weight: 5.0 },
  { source: 'service_account:default:backend-sa', target: 'role:default:admin-role',           relation: 'bound-to',          risk: 9.5, weight: 0.5 },
  { source: 'service_account:default:metrics-sa', target: 'role:default:metrics-role',         relation: 'bound-to',          risk: 3.5, weight: 6.5 },
  { source: 'role:default:admin-role',          target: 'secret:default:db-credentials',       relation: 'can-read',          risk: 9.0, weight: 1.0 },
  { source: 'role:default:admin-role',          target: 'secret:default:api-token',            relation: 'can-read',          risk: 8.0, weight: 2.0 },
  { source: 'role:default:admin-role',          target: 'secret:default:tls-cert',             relation: 'can-read',          risk: 5.5, weight: 4.5 },
  { source: 'role:default:secret-reader',       target: 'secret:default:db-credentials',       relation: 'can-read',          risk: 7.5, weight: 2.5 },
  { source: 'secret:default:db-credentials',    target: 'database:default:billing-db',         relation: 'unlocks',           risk: 9.5, weight: 0.5 },
  { source: 'secret:default:db-credentials',    target: 'database:default:analytics-db',       relation: 'unlocks',           risk: 7.0, weight: 3.0 },
  { source: 'user:cluster:dev-1',               target: 'role:default:secret-reader',          relation: 'bound-to',          risk: 7.5, weight: 2.5 },
  { source: 'user:cluster:ci-bot',              target: 'role:cluster:cluster-admin',          relation: 'bound-to',          risk: 10.0, weight: 0.0 },
  { source: 'role:default:admin-role',          target: 'service_account:default:backend-sa',  relation: 'can-impersonate',   risk: 9.0, weight: 1.0 },
  { source: 'secret:default:api-token',         target: 'service_account:default:backend-sa',  relation: 'authenticates-as',  risk: 8.0, weight: 2.0 },
  { source: 'role:cluster:cluster-admin',       target: 'secret:default:db-credentials',       relation: 'can-read',          risk: 10.0, weight: 0.0 },
  { source: 'role:cluster:cluster-admin',       target: 'database:default:billing-db',         relation: 'accesses',          risk: 10.0, weight: 0.0 },
  { source: 'role:default:metrics-role',        target: 'pod:default:web-server',              relation: 'can-read',          risk: 4.0, weight: 6.0 },
  { source: 'role:default:metrics-role',        target: 'pod:default:api-server',              relation: 'can-read',          risk: 4.0, weight: 6.0 },
];

const NODE_BY_ID = new Map(MOCK_NODES.map((n) => [n.id, n]));

const labelOf = (id: string) => NODE_BY_ID.get(id)?.label ?? id;

const severityOf = (risk: number): string => {
  if (risk >= 9.0) return 'CRITICAL';
  if (risk >= 7.0) return 'HIGH';
  if (risk >= 4.0) return 'MEDIUM';
  return 'LOW';
};

// ── Graph payload ────────────────────────────────────────────────────────────
export const mockGraphPayload = () => ({
  meta: {
    source: 'mock',
    generated: new Date().toISOString(),
    node_count: MOCK_NODES.length,
    edge_count: MOCK_EDGES.length,
  },
  nodes: MOCK_NODES.map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type,
    risk_score: n.risk,
    risk: n.risk,
    namespace: n.namespace,
    metadata: n.metadata ?? {},
    properties: {},
  })),
  edges: MOCK_EDGES.map((e, i) => ({
    id: `e${i}`,
    source: e.source,
    target: e.target,
    relation: e.relation,
    risk_score: e.risk,
    risk: e.risk,
    weight: e.weight,
  })),
});

// ── Attack path (web-server → backend-sa → admin-role → db-credentials → billing-db) ──
const ATTACK_PATH_NODES = [
  'pod:default:web-server',
  'service_account:default:backend-sa',
  'role:default:admin-role',
  'secret:default:db-credentials',
  'database:default:billing-db',
];

const buildAttackHops = (pathNodes: string[]) => {
  const hops: any[] = [];
  for (let i = 0; i < pathNodes.length - 1; i++) {
    const from = pathNodes[i];
    const to = pathNodes[i + 1];
    const edge = MOCK_EDGES.find((e) => e.source === from && e.target === to);
    const risk = edge?.risk ?? 5.0;
    hops.push({
      from,
      to,
      from_label: labelOf(from),
      to_label: labelOf(to),
      relation: edge?.relation ?? 'accesses',
      edge_risk: risk,
      severity: severityOf(risk),
      risk_score: risk,
    });
  }
  return hops;
};

const REMEDIATIONS = [
  {
    title: 'Remove wildcard verbs from admin-role',
    description: 'Replace "*" with explicit verbs/resources to prevent secret exfiltration.',
    change: 'Update Role.rules — drop verbs:["*"], resources:["*"]',
    target_resource: 'admin-role',
    target_resource_type: 'Role',
    difficulty: 'low',
    impact_count: 3,
    yaml_snippet:
`apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: admin-role
  namespace: default
rules:
- apiGroups: [""]
  resources: ["pods", "configmaps"]
  verbs: ["get", "list"]`,
  },
  {
    title: 'Move db-credentials to an external secret manager',
    description: 'Plaintext DB password in a default-namespace Secret is the highest-value target.',
    change: 'Migrate to AWS Secrets Manager / Vault and reference via CSI driver',
    target_resource: 'db-credentials',
    target_resource_type: 'Secret',
    difficulty: 'medium',
    impact_count: 2,
    yaml_snippet:
`apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: db-credentials
spec:
  provider: vault
  parameters:
    objects: |
      - objectName: "db-password"
        secretPath: "secret/data/db"`,
  },
  {
    title: 'Rebind ci-bot to a least-privilege role',
    description: 'ci-bot is bound to cluster-admin — way more than needed for CI tasks.',
    change: 'Replace cluster-admin binding with namespaced ci-deployer role',
    target_resource: 'ci-bot',
    target_resource_type: 'ClusterRoleBinding',
    difficulty: 'low',
    impact_count: 1,
    yaml_snippet:
`apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ci-bot-deployer
  namespace: default
subjects:
- kind: User
  name: ci-bot
roleRef:
  kind: Role
  name: ci-deployer
  apiGroup: rbac.authorization.k8s.io`,
  },
];

export const mockAttackPath = (source: string, target: string) => {
  const hops = source && target
    ? buildAttackHops([source, ...ATTACK_PATH_NODES.slice(1, -1), target])
    : buildAttackHops(ATTACK_PATH_NODES);
  const pathNodes = source && target
    ? [source, ...ATTACK_PATH_NODES.slice(1, -1), target]
    : ATTACK_PATH_NODES;
  const total_cost = hops.reduce((s, h) => s + (10 - h.edge_risk + 0.5), 0);

  return {
    found: true,
    source: pathNodes[0],
    target: pathNodes[pathNodes.length - 1],
    source_label: labelOf(pathNodes[0]),
    target_label: labelOf(pathNodes[pathNodes.length - 1]),
    path: pathNodes,
    hops,
    hop_count: hops.length,
    total_cost,
    severity: total_cost >= 19.6 ? 'CRITICAL' : total_cost >= 11 ? 'HIGH' : total_cost >= 5 ? 'MEDIUM' : 'LOW',
    remediations: REMEDIATIONS,
    message: 'Mock data — backend offline',
  };
};

// ── Blast radius ─────────────────────────────────────────────────────────────
export const mockBlastRadius = (nodeId: string, maxHops: number = 3) => {
  const visited = new Set<string>();
  const zones: Record<number, { id: string; label: string; type: string; risk: number; severity: string }[]> = {
    0: [],
  };
  const sourceNode = NODE_BY_ID.get(nodeId);
  if (!sourceNode) {
    return {
      source: nodeId,
      source_label: nodeId,
      total_reachable: 0,
      zones: { 0: [] },
      stats: { critical: 0, high: 0, total: 0 },
      highest_risk_node: null,
    };
  }
  zones[0].push({ id: nodeId, label: sourceNode.label, type: sourceNode.type, risk: sourceNode.risk, severity: severityOf(sourceNode.risk) });
  visited.add(nodeId);

  let frontier = [nodeId];
  for (let h = 1; h <= maxHops; h++) {
    const next: string[] = [];
    zones[h] = [];
    for (const cur of frontier) {
      for (const e of MOCK_EDGES) {
        if (e.source !== cur) continue;
        if (visited.has(e.target)) continue;
        const tgt = NODE_BY_ID.get(e.target);
        if (!tgt) continue;
        visited.add(e.target);
        zones[h].push({ id: tgt.id, label: tgt.label, type: tgt.type, risk: tgt.risk, severity: severityOf(tgt.risk) });
        next.push(e.target);
      }
    }
    frontier = next;
    if (!frontier.length) break;
  }

  const all = Object.values(zones).flat();
  const critical = all.filter((n) => n.risk >= 9.0).length;
  const high = all.filter((n) => n.risk >= 7.0 && n.risk < 9.0).length;
  const totalReachable = all.length - 1; // exclude source

  const highest = all.reduce<typeof all[0] | null>((best, n) => (best && best.risk >= n.risk ? best : n), null);

  return {
    source: nodeId,
    source_label: sourceNode.label,
    total_reachable: totalReachable,
    zones,
    stats: { critical, high, total: totalReachable },
    highest_risk_node: highest,
  };
};

// ── Cycles ───────────────────────────────────────────────────────────────────
const CYCLE_NODES = ['service_account:default:backend-sa', 'role:default:admin-role'];

export const mockCycles = () => ({
  cycle_count: 1,
  cycles: [
    {
      nodes: [...CYCLE_NODES, CYCLE_NODES[0]],
      length: 2,
      risk_score: 9.0,
      severity: 'CRITICAL',
      description: 'backend-sa ↔ admin-role privilege escalation loop',
    },
  ],
  cycle_node_ids: CYCLE_NODES,
});

// ── Critical nodes (centrality ranking) ──────────────────────────────────────
export const mockCriticalNodes = (topN: number = 10) => {
  const nodes = MOCK_NODES.map((n, i) => {
    // Coarse approximation: junctions (SAs/roles/secrets) score higher
    const junctionWeight = ['service_account', 'role', 'secret'].includes(n.type) ? 0.7 : 0.2;
    const centrality = Math.max(0, junctionWeight - i * 0.02);
    const combined = +(centrality * 0.6 + (Math.min(n.risk, 10) / 10) * 0.4).toFixed(4);
    return {
      id: n.id,
      label: n.label,
      type: n.type,
      namespace: n.namespace,
      centrality_score: +centrality.toFixed(4),
      risk: n.risk,
      combined_score: combined,
      recommendation: n.type === 'role'
        ? `Tighten ${n.label} — drop wildcard rules`
        : n.type === 'service_account'
        ? `Audit bindings for ${n.label}`
        : n.type === 'secret'
        ? `Rotate ${n.label} and move to a secrets manager`
        : `Harden ${n.label}`,
    };
  })
    .sort((a, b) => b.combined_score - a.combined_score)
    .map((n, i) => ({ ...n, rank: i + 1 }));

  return { total_nodes: MOCK_NODES.length, top_n: topN, nodes: nodes.slice(0, topN) };
};

// ── Threat score / full analysis ────────────────────────────────────────────
export const mockThreatScore = () => ({
  threat_score: 8.5,
  risk_level: 'high',
  description: 'High risk: Significant attack paths present; urgent remediation needed',
  factors: {
    attack_paths: true,
    shortest_path_hops: 4,
    privilege_escalation_cycles: 1,
    critical_node_junctions: 5,
    blast_radius_size: 9,
  },
  benchmarks: {
    example_safe_cluster: 1.2,
    example_typical_cluster: 5.0,
    example_vulnerable_cluster: 8.5,
  },
});

export const mockFullAnalysis = () => ({
  attack_path: mockAttackPath('pod:default:web-server', 'database:default:billing-db'),
  blast_radius: mockBlastRadius('pod:default:web-server', 3),
  cycles: mockCycles(),
  critical_nodes: mockCriticalNodes(5),
  threat_score: mockThreatScore(),
});

// ── Simulation ──────────────────────────────────────────────────────────────
export const mockSimulation = (nodeId: string, _source: string, _target: string) => ({
  node_id: nodeId,
  node_label: labelOf(nodeId),
  paths_before: 3,
  paths_after: 1,
  paths_broken: 2,
  cycles_before: 1,
  cycles_after: 0,
  cycles_broken: 1,
  impact: 'high',
  recommendation: `Removing ${labelOf(nodeId)} would eliminate the privilege-escalation cycle and break 2 of 3 critical attack paths.`,
  narrative: `Simulating removal of ${labelOf(nodeId)}: attack surface drops from 3 to 1 path. The backend-sa ↔ admin-role cycle is broken. Recommended hardening: replace this node with a tightly scoped equivalent.`,
});

// ── AI report ───────────────────────────────────────────────────────────────
export const mockReport = () => ({
  cluster_name: 'nokia-telecom-cluster',
  generated_at: new Date().toISOString(),
  summary:
    'The cluster has a critical 4-hop attack path from the public web-server pod to the billing-db database via an over-privileged backend service account. A privilege-escalation cycle (backend-sa ↔ admin-role) compounds the risk.',
  executive_summary:
    'Threat level HIGH. One critical attack path and one privilege-escalation cycle were identified. Estimated remediation effort: ~3 engineering days.',
  findings: [
    { severity: 'critical', title: 'Wildcard Role grants secrets access', description: 'admin-role uses verbs:["*"] resources:["*"] and is bound to backend-sa.' },
    { severity: 'high', title: 'Plaintext DB credentials in Secret', description: 'db-credentials Secret stores the production DB password unencrypted.' },
    { severity: 'high', title: 'ci-bot bound to cluster-admin', description: 'CI service identity has full cluster privileges — far more than needed.' },
    { severity: 'medium', title: 'Privilege-escalation cycle', description: 'backend-sa ↔ admin-role forms a self-reinforcing loop.' },
  ],
  recommendations: REMEDIATIONS,
  attack_path: mockAttackPath('pod:default:web-server', 'database:default:billing-db'),
  threat_score: mockThreatScore(),
});

// ── History / runs ──────────────────────────────────────────────────────────
const NOW = Date.now();
const isoOffset = (mins: number) => new Date(NOW - mins * 60_000).toISOString();

const RUNS = [
  { run_id: 'mock-run-0001', created_at: isoOffset(60),  overall_risk: 8.5, attack_paths: 3, cycles: 1, source: 'mock' },
  { run_id: 'mock-run-0002', created_at: isoOffset(45),  overall_risk: 8.2, attack_paths: 3, cycles: 1, source: 'mock' },
  { run_id: 'mock-run-0003', created_at: isoOffset(30),  overall_risk: 9.0, attack_paths: 4, cycles: 2, source: 'mock' },
  { run_id: 'mock-run-0004', created_at: isoOffset(15),  overall_risk: 8.7, attack_paths: 3, cycles: 1, source: 'mock' },
  { run_id: 'mock-run-0005', created_at: isoOffset(5),   overall_risk: 8.5, attack_paths: 3, cycles: 1, source: 'mock' },
];

export const mockHistory = (limit = 20) => ({ runs: RUNS.slice(0, limit), total: RUNS.length });

// ── Diff payload (what DiffPanel consumes) ──────────────────────────────────
export const mockDiff = () => ({
  meta: { time_before: isoOffset(30), time_after: isoOffset(5), note: 'Mock comparison — backend offline' },
  risk_delta: { before: 9.0, after: 8.5, delta: -0.5 },
  path_delta: { before: 4, after: 3, delta: -1 },
  cycle_delta: { before: 2, after: 1, delta: -1 },
  node_changes: { total_before: 18, total_after: 19, added: ['pod:default:metrics-collector'], removed: [], new_edges: [] },
  edge_changes: {
    total_before: 19,
    total_after: 20,
    new_edges: [{ source: 'pod:default:metrics-collector', target: 'service_account:default:metrics-sa', relation: 'uses' }],
    removed_edges: [],
  },
  severity_shift: {
    before: { critical: 4, high: 5, medium: 6, low: 3 },
    after: { critical: 3, high: 5, medium: 7, low: 4 },
    deltas: { critical: -1, high: 0, medium: 1, low: 1 },
  },
  finding_delta: {
    new_count: 1,
    resolved_count: 1,
    new_findings: [{ severity: 'medium', title: 'metrics-collector added without NetworkPolicy' }],
  },
  top_new_risks: [{ id: 'pod:default:metrics-collector', label: 'metrics-collector', type: 'pod', delta: 0.5, is_new: true }],
  top_improved: [{ id: 'role:default:admin-role', label: 'admin-role', type: 'role', delta: -1.0 }],
  recommendation: {
    alert_level: 'success',
    text: 'Risk has improved since the last run — one privilege-escalation cycle was broken. Maintain the current trajectory.',
  },
});

// ── Snapshots / timeline / alerts ───────────────────────────────────────────
const SNAPSHOTS = RUNS.map((r, i) => ({
  snapshot_id: `mock-snap-${String(i + 1).padStart(4, '0')}`,
  cluster_name: 'nokia-telecom-cluster',
  timestamp: r.created_at,
  trigger: { source: i === 0 ? 'baseline' : 'manual', description: i === 0 ? 'Initial baseline' : 'Periodic snapshot' },
  metadata: {
    node_count: 18 + i,
    edge_count: 20 + i,
    entry_points: ['pod:default:web-server', 'user:cluster:dev-1', 'user:cluster:ci-bot'],
    sensitive_targets: ['database:default:billing-db', 'database:default:analytics-db'],
    cycles_detected: r.cycles,
    aggregate_risk: r.overall_risk,
  },
}));

export const mockSnapshots = (limit = 20, offset = 0) => ({
  snapshots: SNAPSHOTS.slice(offset, offset + limit),
  total: SNAPSHOTS.length,
  limit,
  offset,
});

export const mockSnapshotFull = (id: string) => {
  const meta = SNAPSHOTS.find((s) => s.snapshot_id === id) ?? SNAPSHOTS[0];
  return { ...meta, nodes: mockGraphPayload().nodes, edges: mockGraphPayload().edges };
};

export const mockSnapshotTimeline = (days: number = 7) => ({
  days,
  timeline: SNAPSHOTS.map((s) => ({
    snapshot_id: s.snapshot_id,
    timestamp: s.timestamp,
    aggregate_risk: s.metadata.aggregate_risk,
    node_count: s.metadata.node_count,
    edge_count: s.metadata.edge_count,
    cycles_detected: s.metadata.cycles_detected,
  })),
});

export const mockSnapshotDiff = () => ({
  diff_id: 'mock-diff-0001',
  snapshot_id_before: SNAPSHOTS[0].snapshot_id,
  snapshot_id_after: SNAPSHOTS[SNAPSHOTS.length - 1].snapshot_id,
  timestamp_before: SNAPSHOTS[0].timestamp,
  timestamp_after: SNAPSHOTS[SNAPSHOTS.length - 1].timestamp,
  nodes_added: ['pod:default:metrics-collector'],
  nodes_removed: [],
  nodes_risk_increased: [{ id: 'pod:default:web-server', label: 'web-server', old_risk: 7.0, new_risk: 7.5, delta: 0.5 }],
  nodes_risk_decreased: [{ id: 'role:default:admin-role', label: 'admin-role', old_risk: 10.0, new_risk: 9.5, delta: -0.5 }],
  edges_added: [{ source: 'pod:default:metrics-collector', target: 'service_account:default:metrics-sa' }],
  edges_removed: [],
  new_attack_paths: [{ source: 'pod:default:metrics-collector', target: 'database:default:analytics-db' }],
  disappeared_paths: [],
  new_cycles: [],
  disappeared_cycles: [{ nodes: ['service_account:default:backend-sa', 'role:default:admin-role'] }],
  overall_risk_delta: -0.5,
  high_risk_nodes_delta: -1,
  nodes_added_count: 1,
  nodes_removed_count: 0,
  edges_added_count: 1,
  edges_removed_count: 0,
  new_attack_paths_count: 1,
  disappeared_paths_count: 0,
  new_cycles_count: 0,
  disappeared_cycles_count: 1,
  severity: 'info',
  alert_triggered: false,
  alert_reasons: [],
  computed_at: new Date().toISOString(),
});

export const mockAlerts = (limit = 20) => ({
  alerts: [
    {
      alert_id: 'mock-alert-0001',
      diff_id: 'mock-diff-0001',
      severity: 'high',
      title: 'New attack path detected',
      description: 'metrics-collector → metrics-sa → metrics-role → analytics-db',
      new_paths: [{ source: 'pod:default:metrics-collector', target: 'database:default:analytics-db' }],
      new_cycles: [],
      risk_delta: 0.5,
      triggered_at: isoOffset(20),
    },
    {
      alert_id: 'mock-alert-0002',
      diff_id: 'mock-diff-0002',
      severity: 'critical',
      title: 'Privilege escalation cycle introduced',
      description: 'backend-sa ↔ admin-role cycle now exists',
      new_paths: [],
      new_cycles: [{ nodes: ['service_account:default:backend-sa', 'role:default:admin-role'] }],
      risk_delta: 1.5,
      triggered_at: isoOffset(40),
    },
  ].slice(0, limit),
  total: 2,
});

// ── CVE feed ────────────────────────────────────────────────────────────────
const CVES = [
  { cve_id: 'CVE-2024-21626', title: 'runc — file descriptor escape', description: 'runc 1.1.11 and earlier allow container escapes via internal fd leak.', cvss_score: 8.6, severity: 'high', published: isoOffset(60 * 24 * 5), modified: isoOffset(60 * 24 * 2), component: 'runc', vector: 'CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H', references: ['https://nvd.nist.gov/vuln/detail/CVE-2024-21626'], source: 'mock' },
  { cve_id: 'CVE-2024-3094', title: 'xz-utils — backdoored upstream', description: 'Malicious code in xz-utils 5.6.0/5.6.1 affecting sshd via liblzma.', cvss_score: 10.0, severity: 'critical', published: isoOffset(60 * 24 * 12), modified: isoOffset(60 * 24 * 10), component: 'xz-utils', vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H', references: ['https://nvd.nist.gov/vuln/detail/CVE-2024-3094'], source: 'mock' },
  { cve_id: 'CVE-2023-44487', title: 'HTTP/2 Rapid Reset', description: 'HTTP/2 protocol DoS via rapid stream reset; affects nginx, Go, Node, etc.', cvss_score: 7.5, severity: 'high', published: isoOffset(60 * 24 * 60), component: 'http2', source: 'mock' },
  { cve_id: 'CVE-2024-6387', title: 'OpenSSH regreSSHion', description: 'Race condition in sshd allows pre-auth RCE on glibc Linux.', cvss_score: 8.1, severity: 'high', published: isoOffset(60 * 24 * 35), component: 'openssh', source: 'mock' },
  { cve_id: 'CVE-2025-0001', title: 'Mock Kubernetes API SSRF', description: 'Synthetic CVE for offline-mode demonstrations.', cvss_score: 6.5, severity: 'medium', published: isoOffset(60 * 24 * 1), component: 'kubernetes', source: 'mock' },
];

export const mockCveFeed = (q?: string) => {
  const filtered = q ? CVES.filter((c) => (c.cve_id + c.description + c.component).toLowerCase().includes(q.toLowerCase())) : CVES;
  return {
    source: 'mock',
    keyword: q ?? 'kubernetes',
    fetched_at: new Date().toISOString(),
    total: filtered.length,
    cves: filtered,
    warning: 'Backend offline — serving offline mock CVE feed',
  };
};

export const mockCveSummary = () => ({
  total: CVES.length,
  critical: CVES.filter((c) => c.severity === 'critical').length,
  high: CVES.filter((c) => c.severity === 'high').length,
  medium: CVES.filter((c) => c.severity === 'medium').length,
  latest_date: CVES[0].published,
  top_component: 'runc',
  fetched_at: new Date().toISOString(),
});

export const mockPodCves = (podId: string) => {
  const pod = NODE_BY_ID.get(podId);
  const images: string[] = (pod?.metadata?.image as string[]) ?? [];
  const imageData = images.map((img) => ({
    image: img,
    cvss_score: 7.5,
    severity: 'high',
    source: 'mock',
  }));
  return {
    pod_id: podId,
    pod_label: pod?.label ?? podId,
    images: imageData,
    aggregate_risk: imageData.length ? 7.5 : 0,
    aggregate_severity: imageData.length ? 'high' : 'none',
    timestamp: new Date().toISOString(),
  };
};

// ── Monitor / removal candidates / etc. ─────────────────────────────────────
export const mockMonitorStatus = () => ({
  running: false,
  baseline_recorded: true,
  events_seen: 0,
  last_event: null,
  message: 'Mock mode — real-time monitoring disabled',
});

export const mockRemovalCandidates = () => [
  { node_id: 'role:default:admin-role',          node_label: 'admin-role',  node_type: 'role',            paths_broken: 3, impact: 'high',   recommendation: 'Drop wildcard rules' },
  { node_id: 'service_account:default:backend-sa', node_label: 'backend-sa', node_type: 'service_account', paths_broken: 2, impact: 'high',   recommendation: 'Rebind to least-privilege role' },
  { node_id: 'secret:default:db-credentials',    node_label: 'db-credentials', node_type: 'secret',         paths_broken: 2, impact: 'high',   recommendation: 'Move to external secret manager' },
  { node_id: 'role:cluster:cluster-admin',       node_label: 'cluster-admin', node_type: 'role',            paths_broken: 1, impact: 'medium', recommendation: 'Restrict cluster-admin bindings' },
];
