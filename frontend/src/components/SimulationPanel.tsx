import { useState } from 'react';
import { Loader2, Play, Trash2, ArrowRight } from 'lucide-react';
import SeverityBadge from './SeverityBadge';
import type { GraphNode } from '@/hooks/useGraph';

interface Props {
  nodes: GraphNode[];
  criticalNodes: any;
  simulation: any;
  loading: boolean;
  onSimulate: (nodeId: string, source: string, target: string) => void;
}

const FALLBACK_SOURCES = ['pod:default:web-server', 'user:cluster:dev-1'];
const FALLBACK_TARGETS = ['database:default:billing-db', 'secret:default:db-credentials'];

export default function SimulationPanel({ nodes, criticalNodes, simulation, loading, onSimulate }: Props) {
  const [nodeId, setNodeId] = useState('');
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');

  const critList = criticalNodes?.nodes || criticalNodes || [];
  const removeOptions = critList.length > 0
    ? critList.map((n: any) => ({ id: n.id, label: n.label || n.id, type: n.type }))
    : nodes;

  const sources = nodes.filter(n => ['pod', 'user'].includes(n.type));
  const targets = nodes.filter(n => ['database', 'secret'].includes(n.type));
  const srcList = sources.length > 0 ? sources : FALLBACK_SOURCES.map(id => ({ id, label: id.split(':').pop()!, type: id.split(':')[0] } as GraphNode));
  const tgtList = targets.length > 0 ? targets : FALLBACK_TARGETS.map(id => ({ id, label: id.split(':').pop()!, type: id.split(':')[0] } as GraphNode));

  return (
    <div className="space-y-4 p-4">
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Node to Remove</label>
        <select value={nodeId} onChange={e => setNodeId(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select node...</option>
          {removeOptions.map((n: any) => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Source</label>
        <select value={source} onChange={e => setSource(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select source...</option>
          {srcList.map(n => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Target</label>
        <select value={target} onChange={e => setTarget(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select target...</option>
          {tgtList.map(n => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <button
        onClick={() => nodeId && source && target && onSimulate(nodeId, source, target)}
        disabled={!nodeId || !source || !target || loading}
        className="w-full flex items-center justify-center gap-2 bg-destructive text-destructive-foreground rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
        Run Simulation
      </button>

      {simulation && (
        <div className="space-y-3 mt-4">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-secondary rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground">Paths Broken</p>
              <p className="text-lg font-bold text-destructive">{simulation.paths_broken ?? 0}</p>
            </div>
            <div className="bg-secondary rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground">Cycles Broken</p>
              <p className="text-lg font-bold text-accent">{simulation.cycles_broken ?? 0}</p>
            </div>
            <div className="bg-secondary rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground">Cost Before</p>
              <p className="text-lg font-bold text-foreground">{(simulation.cost_before ?? 0).toFixed(1)}</p>
            </div>
            <div className="bg-secondary rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground">Cost After</p>
              <p className="text-lg font-bold text-foreground">{(simulation.cost_after ?? 0).toFixed(1)}</p>
            </div>
          </div>

          {simulation.impact && <SeverityBadge severity={simulation.impact} />}

          {simulation.narrative && (
            <blockquote className="border-l-2 border-primary pl-3 text-sm text-muted-foreground italic">
              {simulation.narrative}
            </blockquote>
          )}
        </div>
      )}

      {!simulation && !loading && (
        <div className="text-center py-8 text-muted-foreground">
          <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Configure and run a removal simulation</p>
        </div>
      )}
    </div>
  );
}
