import { useState, useCallback } from 'react';
import {
  listSnapshots, createSnapshot, diffSnapshots,
  getSnapshotTimeline,
  type GraphSnapshot, type SnapshotDiff, type TimelinePoint,
} from '@/api/snapshotApi';

export function useSnapshots() {
  const [snapshots, setSnapshots] = useState<GraphSnapshot[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (limit = 20, offset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listSnapshots(limit, offset);
      setSnapshots(res.data.snapshots);
      setTotal(res.data.total);
    } catch (e: any) {
      setError(e.message || 'Failed to load snapshots');
    } finally {
      setLoading(false);
    }
  }, []);

  const takeSnapshot = useCallback(async (description = 'Manual snapshot') => {
    setLoading(true);
    setError(null);
    try {
      const res = await createSnapshot('manual', description);
      await load();
      return res.data;
    } catch (e: any) {
      setError(e.message || 'Failed to create snapshot');
      return null;
    } finally {
      setLoading(false);
    }
  }, [load]);

  return { snapshots, total, loading, error, load, takeSnapshot };
}

export function useSnapshotDiff() {
  const [diff, setDiff] = useState<SnapshotDiff | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compare = useCallback(async (id1: string, id2: string) => {
    setLoading(true);
    setError(null);
    setDiff(null);
    try {
      const res = await diffSnapshots(id1, id2);
      setDiff(res.data);
      return res.data;
    } catch (e: any) {
      setError(e.message || 'Failed to compute diff');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { diff, loading, error, compare };
}

export function useSnapshotTimeline(days = 7) {
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (d = days) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSnapshotTimeline(d);
      setTimeline(res.data.timeline);
    } catch (e: any) {
      setError(e.message || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [days]);

  return { timeline, loading, error, load };
}
