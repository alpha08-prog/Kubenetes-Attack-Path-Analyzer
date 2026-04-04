import { useState, useCallback, useEffect } from 'react';
import { listAlerts, type TemporalAlert } from '@/api/snapshotApi';

export function useTemporalAlerts(pollIntervalMs?: number) {
  const [alerts, setAlerts] = useState<TemporalAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (limit = 20, severity?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAlerts(limit, severity);
      setAlerts(res.data.alerts);
      setTotal(res.data.total);
    } catch (e: any) {
      setError(e.message || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (!pollIntervalMs) return;
    const interval = setInterval(() => load(), pollIntervalMs);
    return () => clearInterval(interval);
  }, [load, pollIntervalMs]);

  return { alerts, total, loading, error, load };
}
