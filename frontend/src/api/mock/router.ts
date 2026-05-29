// Maps an outgoing request to a canned mock response.
//
// Returns `null` if no mock matches, so the original network error can
// surface. The first time any mock is served we flip a global flag and
// dispatch a `mock-mode-changed` window event — the App-level banner
// listens for this and surfaces "running on mock data".

import type { InternalAxiosRequestConfig } from 'axios';
import {
  mockGraphPayload,
  mockAttackPath,
  mockBlastRadius,
  mockCycles,
  mockCriticalNodes,
  mockFullAnalysis,
  mockSimulation,
  mockReport,
  mockHistory,
  mockDiff,
  mockSnapshots,
  mockSnapshotFull,
  mockSnapshotTimeline,
  mockSnapshotDiff,
  mockAlerts,
  mockCveFeed,
  mockCveSummary,
  mockPodCves,
  mockMonitorStatus,
  mockRemovalCandidates,
  MOCK_NODES,
  MOCK_EDGES,
} from './data';

declare global {
  interface Window {
    __APA_MOCK_MODE__?: boolean;
  }
}

export function isMockModeActive(): boolean {
  return typeof window !== 'undefined' && !!window.__APA_MOCK_MODE__;
}

function activateMockMode() {
  if (typeof window === 'undefined') return;
  if (!window.__APA_MOCK_MODE__) {
    window.__APA_MOCK_MODE__ = true;
    window.dispatchEvent(new CustomEvent('mock-mode-changed', { detail: { active: true } }));
  }
}

function getPath(url: string): string {
  // axios may pass either an absolute URL or a path. Strip protocol+host.
  try {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return new URL(url).pathname;
    }
  } catch {
    // fall through
  }
  return url.split('?')[0];
}

function getQuery(url: string, config: InternalAxiosRequestConfig): URLSearchParams {
  const params = new URLSearchParams();
  // axios `params` config
  const cfgParams = (config.params ?? {}) as Record<string, any>;
  Object.entries(cfgParams).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  // inline query string
  const qsIndex = url.indexOf('?');
  if (qsIndex !== -1) {
    new URLSearchParams(url.slice(qsIndex + 1)).forEach((v, k) => {
      if (!params.has(k)) params.set(k, v);
    });
  }
  return params;
}

function getBody(config: InternalAxiosRequestConfig): any {
  if (!config.data) return {};
  if (typeof config.data === 'string') {
    try { return JSON.parse(config.data); } catch { return {}; }
  }
  return config.data;
}

interface MockResolution {
  status: number;
  data: any;
  headers?: Record<string, string>;
}

export function resolveMock(config: InternalAxiosRequestConfig): MockResolution | null {
  const method = (config.method || 'get').toLowerCase();
  const path = getPath(config.url || '');
  const params = getQuery(config.url || '', config);
  const body = getBody(config);

  const result = match(method, path, params, body);
  if (result) activateMockMode();
  return result;
}

function ok(data: any, headers?: Record<string, string>): MockResolution {
  return { status: 200, data, headers };
}

function match(method: string, path: string, params: URLSearchParams, body: any): MockResolution | null {
  // ── Graph ────────────────────────────────────────────────────────────────
  if (method === 'get' && path === '/api/graph') return ok(mockGraphPayload());
  if (method === 'get' && path === '/api/graph/summary') {
    const g = mockGraphPayload();
    return ok({
      total_nodes: g.nodes.length,
      total_edges: g.edges.length,
      critical_findings: g.nodes.filter((n: any) => n.risk_score >= 8).length,
      cycles_detected: 1,
    });
  }
  if (method === 'post' && path === '/api/graph/reload') return ok({ ok: true, source: 'mock', message: 'Mock graph reloaded' });

  // ── Attack ──────────────────────────────────────────────────────────────
  if (method === 'post' && path === '/api/attack/path') return ok(mockAttackPath(body.source, body.target));
  if (method === 'post' && path === '/api/attack/all-paths') {
    const ap = mockAttackPath(body.source, body.target);
    return ok({ source: ap.source, target: ap.target, paths: [ap], count: 1 });
  }
  if (method === 'get' && path === '/api/attack/auto') {
    const ap = mockAttackPath('pod:default:web-server', 'database:default:billing-db');
    return ok({ ...ap, auto_detected: true, blast_radius: mockBlastRadius('pod:default:web-server', 3) });
  }

  // ── Blast radius ────────────────────────────────────────────────────────
  if (method === 'post' && path === '/api/blast/radius') {
    return ok(mockBlastRadius(body.node_id, Number(body.max_hops ?? 3)));
  }

  // ── Cycles / critical / candidates ──────────────────────────────────────
  if (method === 'get' && path === '/api/cycles') return ok(mockCycles());
  if (method === 'get' && path === '/api/critical/nodes') {
    const top = Number(params.get('top_n') ?? 10);
    return ok(mockCriticalNodes(top));
  }
  if (method === 'get' && path === '/api/critical/candidates') return ok({ candidates: mockRemovalCandidates() });

  // ── Simulation ──────────────────────────────────────────────────────────
  if (method === 'post' && path === '/api/simulate/remove') return ok(mockSimulation(body.node_id, body.source, body.target));
  if (method === 'get' && path === '/api/simulate/auto') return ok(mockSimulation('role:default:admin-role', 'pod:default:web-server', 'database:default:billing-db'));

  // ── Report / analysis ───────────────────────────────────────────────────
  if (method === 'get' && path === '/api/report') return ok(mockReport());
  if (method === 'get' && path === '/api/report/pdf') {
    // produce a minimal blob so axios responseType:'blob' callers don't crash
    const text = 'Mock PDF — backend offline. Generated by Attack Path Analyzer offline mode.';
    const blob = new Blob([text], { type: 'application/pdf' });
    return ok(blob);
  }
  if (method === 'get' && path === '/api/analysis') return ok(mockFullAnalysis());

  // ── History / diff ──────────────────────────────────────────────────────
  if (method === 'get' && path === '/api/history') {
    const limit = Number(params.get('limit') ?? 20);
    return ok(mockHistory(limit));
  }
  if (method === 'get' && path === '/api/diff/latest') return ok(mockDiff());
  if (method === 'post' && path === '/api/diff/compare') return ok(mockDiff());
  if (method === 'get' && path.startsWith('/api/diff/vs-current/')) return ok(mockDiff());

  // ── Snapshots / timeline / alerts ───────────────────────────────────────
  if (method === 'get' && path === '/api/snapshots') {
    const limit = Number(params.get('limit') ?? 20);
    const offset = Number(params.get('offset') ?? 0);
    return ok(mockSnapshots(limit, offset));
  }
  if (method === 'post' && path === '/api/snapshots') {
    const snap = mockSnapshots(1, 0).snapshots[0];
    return ok({ ...snap, diff: mockSnapshotDiff() });
  }
  if (method === 'get' && path === '/api/snapshots/timeline') {
    const days = Number(params.get('days') ?? 7);
    return ok(mockSnapshotTimeline(days));
  }
  if (method === 'get' && path === '/api/snapshots/alerts') {
    const limit = Number(params.get('limit') ?? 20);
    return ok(mockAlerts(limit));
  }
  // /api/snapshots/:id  and  /api/snapshots/:id/diff/:id2
  const snapMatch = /^\/api\/snapshots\/([^/]+)(?:\/diff\/([^/]+))?$/.exec(path);
  if (method === 'get' && snapMatch) {
    if (snapMatch[2]) return ok(mockSnapshotDiff());
    return ok(mockSnapshotFull(snapMatch[1]));
  }

  // ── CVEs ────────────────────────────────────────────────────────────────
  if (method === 'get' && path === '/api/cves') return ok(mockCveFeed());
  if (method === 'get' && path === '/api/cves/search') return ok(mockCveFeed(params.get('q') ?? undefined));
  if (method === 'get' && path === '/api/cves/summary') return ok(mockCveSummary());
  const podCveMatch = /^\/api\/cves\/images\/(.+)$/.exec(path);
  if (method === 'get' && podCveMatch) return ok(mockPodCves(decodeURIComponent(podCveMatch[1])));

  // ── Monitor (REST endpoints; the SSE stream is handled separately in useMonitoring) ──
  if (path.startsWith('/api/monitor/')) {
    if (method === 'get' && path === '/api/monitor/status') return ok(mockMonitorStatus());
    if (method === 'get' && path === '/api/monitor/events') return ok({ events: [], total: 0 });
    if (method === 'post' && path === '/api/monitor/start') return ok({ started: true, message: 'Mock mode — monitor unavailable' });
    if (method === 'post' && path === '/api/monitor/stop') return ok({ stopped: true });
    if (method === 'post' && path === '/api/monitor/record-baseline') return ok({ recorded: true, message: 'Baseline recorded (mock)' });
    if (method === 'post' && path === '/api/monitor/trigger-analysis') return ok({ triggered: true });
    if (method === 'post' && path === '/api/monitor/run-scenario') return ok({ ok: true, message: 'Scenario runner unavailable in mock mode' });
    if (method === 'post' && path === '/api/monitor/demo-flow') {
      return ok({
        ok: true,
        snapshots_created: 3,
        snapshot_ids: mockSnapshots(3).snapshots.map((s) => s.snapshot_id),
        message: 'Mock demo flow — three synthetic snapshots created',
      });
    }
  }

  // Fallthrough — keep an escape hatch for endpoints we haven't mocked
  // so the frontend at least sees a structured 200 instead of a crash.
  if (method === 'get') {
    return ok({ mock: true, message: 'No mock handler for this path; returning empty payload', path });
  }

  return null;
}

// Test/debug helper — exposed so the optional banner can show counts
export function mockGraphSize() {
  return { nodes: MOCK_NODES.length, edges: MOCK_EDGES.length };
}
