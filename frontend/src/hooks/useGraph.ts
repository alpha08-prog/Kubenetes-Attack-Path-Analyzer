import { useState, useEffect, useCallback } from 'react';
import { getGraph, getGraphSummary, reloadGraph } from '@/api/graphApi';
import { toast } from '@/hooks/use-toast';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  risk_score: number;
  namespace?: string;
  properties?: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  risk_score: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphSummary {
  total_nodes: number;
  total_edges: number;
  critical_findings: number;
  cycles_detected: number;
}

export function useGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const [graphRes, summaryRes] = await Promise.all([getGraph(), getGraphSummary()]);
      setGraphData(graphRes.data);
      setSummary(summaryRes.data);
    } catch (e: any) {
      toast({ title: 'Error loading graph', description: e.message, variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      await reloadGraph();
      await fetchGraph();
      toast({ title: 'Graph reloaded' });
    } catch (e: any) {
      toast({ title: 'Error reloading graph', description: e.message, variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [fetchGraph]);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  return { graphData, summary, loading, reload, fetchGraph };
}
