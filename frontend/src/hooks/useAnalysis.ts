import { useState } from 'react';
import * as api from '@/api/graphApi';
import { toast } from '@/hooks/use-toast';

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
      setAttackPath(res.data);
    } catch (e: any) {
      toast({ title: 'Attack path error', description: e.message, variant: 'destructive' });
    } finally { setL('attack', false); }
  };

  const autoAttackPath = async () => {
    setL('attack', true);
    try {
      const res = await api.getAutoAttackPath();
      setAttackPath(res.data);
    } catch (e: any) {
      toast({ title: 'Auto-detect error', description: e.message, variant: 'destructive' });
    } finally { setL('attack', false); }
  };

  const analyzeBlast = async (nodeId: string, maxHops: number) => {
    setL('blast', true);
    try {
      const res = await api.getBlastRadius(nodeId, maxHops);
      setBlastRadius(res.data);
    } catch (e: any) {
      toast({ title: 'Blast radius error', description: e.message, variant: 'destructive' });
    } finally { setL('blast', false); }
  };

  const fetchCycles = async () => {
    setL('cycles', true);
    try {
      const res = await api.getCycles();
      setCycles(res.data);
    } catch (e: any) {
      toast({ title: 'Cycles error', description: e.message, variant: 'destructive' });
    } finally { setL('cycles', false); }
  };

  const fetchCriticalNodes = async (topN = 10) => {
    setL('critical', true);
    try {
      const res = await api.getCriticalNodes(topN);
      setCriticalNodes(res.data);
    } catch (e: any) {
      toast({ title: 'Critical nodes error', description: e.message, variant: 'destructive' });
    } finally { setL('critical', false); }
  };

  const runSimulation = async (nodeId: string, source: string, target: string) => {
    setL('simulation', true);
    try {
      const res = await api.simulateRemoval(nodeId, source, target);
      setSimulation(res.data);
    } catch (e: any) {
      toast({ title: 'Simulation error', description: e.message, variant: 'destructive' });
    } finally { setL('simulation', false); }
  };

  const fetchReport = async () => {
    setL('report', true);
    try {
      const res = await api.getReport();
      setReport(res.data);
    } catch (e: any) {
      toast({ title: 'Report error', description: e.message, variant: 'destructive' });
    } finally { setL('report', false); }
  };

  return {
    attackPath, blastRadius, cycles, criticalNodes, simulation, report, loading,
    findAttackPath, autoAttackPath, analyzeBlast, fetchCycles, fetchCriticalNodes,
    runSimulation, fetchReport, setAttackPath, setBlastRadius, setCycles, setSimulation,
  };
}
