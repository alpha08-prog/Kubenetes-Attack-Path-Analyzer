/**
 * useMonitoring.ts — React hook for real-time graph monitoring via SSE.
 *
 * Connects to GET /api/monitor/events/stream (Server-Sent Events) and
 * dispatches a custom DOM event 'graphUpdate' whenever the backend detects
 * a security-relevant cluster change.
 *
 * Usage:
 *   const { isConnected, lastUpdate, monitoringError } = useMonitoring();
 *
 * The hook automatically:
 *   - Reconnects after 5 s if the stream drops
 *   - Skips reconnect if the tab is hidden (pauses silently)
 *   - Cleans up on unmount
 */

import { useEffect, useRef, useState } from 'react';
import client from '@/api/client';

export interface RiskDelta {
  before:          number;
  after:           number;
  delta:           number;
  delta_pct:       number;
  direction:       string;
  severity_before: string;
  severity_after:  string;
}

export interface PathDelta {
  before:    number;
  after:     number;
  delta:     number;
  direction: string;
  label:     string;
}

export interface GraphUpdateEvent {
  type:      string;   // 'GRAPH_UPDATE' | 'ANALYSIS_TRIGGERED' | ...
  run_id?:   string;
  timestamp: string;
  message?:  string;
  diff?: {
    meta:           Record<string, string>;
    risk_delta:     RiskDelta;
    path_delta:     PathDelta;
    cycle_delta:    PathDelta;
    node_changes:   Record<string, any>;
    severity_shift: Record<string, any>;
    top_new_risks:  any[];
    top_improved:   any[];
    recommendation: string;
  };
}

interface UseMonitoringResult {
  isConnected:     boolean;
  lastUpdate:      GraphUpdateEvent | null;
  liveEvents:      GraphUpdateEvent[];   // all events received in this session
  monitoringError: string | null;
}

const SSE_URL  = '/api/monitor/events/stream';
const RECONNECT_DELAY_MS = 5_000;

export function useMonitoring(): UseMonitoringResult {
  const [isConnected, setIsConnected]         = useState(false);
  const [lastUpdate,  setLastUpdate]          = useState<GraphUpdateEvent | null>(null);
  const [liveEvents,  setLiveEvents]          = useState<GraphUpdateEvent[]>([]);
  const [monitoringError, setMonitoringError] = useState<string | null>(null);

  const esRef       = useRef<EventSource | null>(null);
  const retryTimer  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmounted   = useRef(false);

  const connect = () => {
    if (unmounted.current) return;
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Build absolute URL so EventSource uses the API base
    const baseUrl = (client.defaults.baseURL || '').replace(/\/$/, '');
    const url = baseUrl ? `${baseUrl}${SSE_URL}` : SSE_URL;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (unmounted.current) return;
      setIsConnected(true);
      setMonitoringError(null);
    };

    es.onmessage = (event: MessageEvent) => {
      if (unmounted.current) return;
      try {
        // Ignore SSE comment lines (heartbeats start with ':')
        if (!event.data || event.data.startsWith(':')) return;

        const update: GraphUpdateEvent = JSON.parse(event.data);
        if (update.type === 'GRAPH_UPDATE') {
          setLastUpdate(update);
          // Accumulate in session log (keep newest 100)
          setLiveEvents(prev => [...prev, update].slice(-100));
          // Dispatch a DOM event so Dashboard (and any other consumer) can react
          window.dispatchEvent(
            new CustomEvent<GraphUpdateEvent>('graphUpdate', { detail: update })
          );
        } else {
          // All other event types (ANALYSIS_TRIGGERED, NEW_RESOURCES, etc.)
          // appear in Session Events.
          setLiveEvents(prev => [...prev, update].slice(-100));
        }
      } catch {
        // Malformed JSON — ignore quietly
      }
    };

    es.onerror = () => {
      if (unmounted.current) return;
      setIsConnected(false);
      es.close();
      esRef.current = null;
      setMonitoringError('Monitoring stream disconnected — reconnecting…');

      // Schedule reconnect
      retryTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };
  };

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { isConnected, lastUpdate, liveEvents, monitoringError };
}

/**
 * Thin wrapper around the monitor control REST endpoints.
 */
export const monitoringApi = {
  start:           () => client.post('/api/monitor/start'),
  stop:            () => client.post('/api/monitor/stop'),
  status:          () => client.get('/api/monitor/status'),
  events:          (limit = 20) => client.get('/api/monitor/events', { params: { limit } }),
  recordBaseline:  () => client.post('/api/monitor/record-baseline'),
  triggerAnalysis: () => client.post('/api/monitor/trigger-analysis'),
  // Script can take up to 2 min to deploy K8s resources — override global 45s timeout
  runScenario:     () => client.post('/api/monitor/run-scenario', null, { timeout: 140_000 }),
  cleanupScenario: () => client.post('/api/monitor/run-scenario', null, { params: { cleanup: true }, timeout: 60_000 }),
};
