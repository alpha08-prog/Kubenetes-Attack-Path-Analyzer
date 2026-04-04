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
  metadata?: Record<string, any>;
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

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeAxios = error as { response?: { data?: { detail?: string } }; message?: string };
    return maybeAxios.response?.data?.detail || maybeAxios.message || 'Unknown error';
  }
  return 'Unknown error';
}

function normalizeGraphData(raw: unknown): GraphData {
  const source = (raw || {}) as { nodes?: Array<any>; edges?: Array<any> };

  const nodes = (source.nodes || []).map((node) => {
    const data = node?.data ?? node ?? {};
    return {
      id: String(data.id ?? ''),
      label: String(data.label ?? data.id ?? ''),
      type: String(data.type ?? 'unknown'),
      risk_score: Number(data.risk_score ?? data.risk ?? 0),
      namespace: data.namespace,
      properties: data.properties ?? {},
      metadata: data.metadata ?? {},
    } as GraphNode;
  });

  const edges = (source.edges || []).map((edge, index) => {
    const data = edge?.data ?? edge ?? {};
    return {
      id: String(data.id ?? `e${index}`),
      source: String(data.source ?? ''),
      target: String(data.target ?? ''),
      relation: String(data.relation ?? 'accesses'),
      risk_score: Number(data.risk_score ?? data.risk ?? 0),
    } as GraphEdge;
  });

  return { nodes, edges };
}

function normalizeSummary(rawSummary: unknown, graphData: GraphData): GraphSummary {
  const data = (rawSummary || {}) as Record<string, any>;
  const criticalCount = graphData.nodes.filter((n) => (n.risk_score ?? 0) >= 8).length;

  return {
    total_nodes: Number(data.total_nodes ?? graphData.nodes.length ?? 0),
    total_edges: Number(data.total_edges ?? graphData.edges.length ?? 0),
    critical_findings: Number(data.critical_findings ?? criticalCount),
    cycles_detected: Number(data.cycles_detected ?? data.cycle_count ?? 0),
  };
}

export function useGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const [graphRes, summaryRes] = await Promise.all([getGraph(), getGraphSummary()]);
      const normalizedGraph = normalizeGraphData(graphRes.data);
      const normalizedSummary = normalizeSummary(summaryRes.data, normalizedGraph);
      setGraphData(normalizedGraph);
      setSummary(normalizedSummary);
    } catch (e: unknown) {
      toast({ title: 'Error loading graph', description: getErrorMessage(e), variant: 'destructive' });
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
    } catch (e: unknown) {
      toast({ title: 'Error reloading graph', description: getErrorMessage(e), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [fetchGraph]);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  return { graphData, summary, loading, reload, fetchGraph };
}
