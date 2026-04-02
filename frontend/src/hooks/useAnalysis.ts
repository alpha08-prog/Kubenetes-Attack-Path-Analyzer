import { useState } from 'react';
import * as api from '@/api/graphApi';
import { toast } from '@/hooks/use-toast';

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeAxios = error as { response?: { data?: { detail?: string } }; message?: string };
    return maybeAxios.response?.data?.detail || maybeAxios.message || 'Unknown error';
  }
  return 'Unknown error';
}

function normalizeAttackPath(raw: any) {
  if (!raw) return raw;

  if (Array.isArray(raw.path) && raw.path.length > 0 && typeof raw.path[0] === 'string' && Array.isArray(raw.hops)) {
    if (raw.hops.length === 0) {
      return {
        ...raw,
        path: [],
        message: raw.message || 'Source and target resolved to the same node. Choose different nodes.',
      };
    }

    return {
      ...raw,
      path: raw.hops.map((hop: any) => ({
        from: hop.from,
        to: hop.to,
        from_label: hop.from_label,
        to_label: hop.to_label,
        relation: hop.relation,
        severity: hop.severity,
        risk_score: hop.edge_risk ?? 0,
      })),
    };
  }

  return raw;
}

function normalizeBlastRadius(raw: any) {
  if (!raw) return raw;

  const normalizedZones: Record<string, string[]> = {};
  const zones = raw.zones || {};
  Object.entries(zones).forEach(([hop, value]) => {
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0]?.id) {
      normalizedZones[hop] = value.map((n: any) => String(n.id));
    } else if (Array.isArray(value)) {
      normalizedZones[hop] = value.map((v: any) => String(v));
    } else {
      normalizedZones[hop] = [];
    }
  });

  return {
    ...raw,
    total_affected: raw.total_affected ?? raw.total_reachable ?? 0,
    zones: normalizedZones,
  };
}

export function useAnalysis() {
  const [attackPath, setAttackPath] = useState<any>(null);
  const [blastRadius, setBlastRadius] = useState<any>(null);
  const [cycles, setCycles] = useState<any>(null);
  const [criticalNodes, setCriticalNodes] = useState<any>(null);
  const [simulation, setSimulation] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const setL = (key: string, val: boolean) => setLoading(p => ({ ...p, [key]: val }));

  const findAttackPath = async (source: string, target: string) => {
    setL('attack', true);
    try {
      const res = await api.getAttackPath(source, target);
      setAttackPath(normalizeAttackPath(res.data));
    } catch (e: unknown) {
      toast({ title: 'Attack path error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('attack', false); }
  };

  const autoAttackPath = async () => {
    setL('attack', true);
    try {
      const res = await api.getAutoAttackPath();
      setAttackPath(normalizeAttackPath(res.data));
    } catch (e: unknown) {
      toast({ title: 'Auto-detect error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('attack', false); }
  };

  const analyzeBlast = async (nodeId: string, maxHops: number) => {
    setL('blast', true);
    try {
      const res = await api.getBlastRadius(nodeId, maxHops);
      setBlastRadius(normalizeBlastRadius(res.data));
    } catch (e: unknown) {
      toast({ title: 'Blast radius error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('blast', false); }
  };

  const fetchCycles = async () => {
    setL('cycles', true);
    try {
      const res = await api.getCycles();
      setCycles(res.data);
    } catch (e: unknown) {
      toast({ title: 'Cycles error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('cycles', false); }
  };

  const fetchCriticalNodes = async (topN = 10) => {
    setL('critical', true);
    try {
      const res = await api.getCriticalNodes(topN);
      setCriticalNodes(res.data);
    } catch (e: unknown) {
      toast({ title: 'Critical nodes error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('critical', false); }
  };

  const runSimulation = async (nodeId: string, source: string, target: string) => {
    setL('simulation', true);
    try {
      const res = await api.simulateRemoval(nodeId, source, target);
      setSimulation(res.data);
      return res.data;
    } catch (e: unknown) {
      toast({ title: 'Simulation error', description: getErrorMessage(e), variant: 'destructive' });
      return null;
    } finally { setL('simulation', false); }
  };

  const fetchReport = async () => {
    setL('report', true);
    try {
      const res = await api.getReport();
      setReport(res.data);
    } catch (e: unknown) {
      toast({ title: 'Report error', description: getErrorMessage(e), variant: 'destructive' });
    } finally { setL('report', false); }
  };

  return {
    attackPath, blastRadius, cycles, criticalNodes, simulation, report, loading,
    findAttackPath, autoAttackPath, analyzeBlast, fetchCycles, fetchCriticalNodes,
    runSimulation, fetchReport, setAttackPath, setBlastRadius, setCycles, setSimulation,
  };
}
