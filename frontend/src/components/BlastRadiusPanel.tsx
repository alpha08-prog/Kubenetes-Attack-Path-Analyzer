import { useState } from 'react';
import { Loader2, Play, Target } from 'lucide-react';
import SeverityBadge from './SeverityBadge';
import NodeTypeBadge from './NodeTypeBadge';
import type { GraphNode } from '@/hooks/useGraph';

interface Props {
  nodes: GraphNode[];
  blastRadius: any;
  loading: boolean;
  onAnalyze: (nodeId: string, maxHops: number) => void;
  onShowOnGraph: () => void;
}

export default function BlastRadiusPanel({ nodes, blastRadius, loading, onAnalyze, onShowOnGraph }: Props) {
  const [nodeId, setNodeId] = useState('');
  const [hops, setHops] = useState(3);

  return (
    <div className="space-y-4 p-4">
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Node</label>
        <select value={nodeId} onChange={e => setNodeId(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select node...</option>
          {nodes.map(n => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Max Hops: {hops}</label>
        <input
          type="range" min={1} max={5} value={hops}
          onChange={e => setHops(parseInt(e.target.value))}
          className="w-full accent-primary"
        />
      </div>

      <button
        onClick={() => nodeId && onAnalyze(nodeId, hops)}
        disabled={!nodeId || loading}
        className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
        Analyze
      </button>

      {/* Loading state */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-primary" />
          <span className="text-xs text-muted-foreground">Analyzing...</span>
        </div>
      )}

      {!loading && blastRadius && (
        <div className="space-y-3 mt-4">
          <p className="text-sm font-medium text-foreground">
            {blastRadius.total_affected || 0} nodes reachable within {blastRadius.max_hops || hops} hops
          </p>

          {blastRadius.stats && (
            <div className="flex gap-2">
              <SeverityBadge severity="critical" />
              <span className="text-xs text-foreground">{blastRadius.stats.critical || 0}</span>
              <SeverityBadge severity="high" />
              <span className="text-xs text-foreground">{blastRadius.stats.high || 0}</span>
            </div>
          )}

          {blastRadius.zones && Object.entries(blastRadius.zones).map(([hop, nodeIds]: [string, any]) => (
            <details key={hop} className="bg-secondary rounded-md">
              <summary className="px-3 py-2 text-sm font-medium text-foreground cursor-pointer">
                Zone {hop} ({(nodeIds as string[]).length} nodes)
              </summary>
              <div className="px-3 pb-2 space-y-1">
                {(nodeIds as string[]).map((id: string) => {
                  const n = nodes.find(x => x.id === id);
                  return (
                    <div key={id} className="flex items-center gap-2 text-sm">
                      <NodeTypeBadge type={n?.type || id.split(':')[0]} />
                      <span className="text-foreground">{n?.label || id}</span>
                    </div>
                  );
                })}
              </div>
            </details>
          ))}

          <button
            onClick={onShowOnGraph}
            className="w-full bg-severity-high/20 text-severity-high border border-severity-high/30 rounded-md px-3 py-2 text-sm font-medium hover:bg-severity-high/30 transition-colors"
          >
            Show on Graph
          </button>
        </div>
      )}

      {!loading && !blastRadius && (
        <div className="text-center py-8 text-muted-foreground">
          <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Select a node to analyze blast radius</p>
        </div>
      )}
    </div>
  );
}
