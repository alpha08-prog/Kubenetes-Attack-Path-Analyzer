import { useEffect } from 'react';
import { Loader2, Zap } from 'lucide-react';
import NodeTypeBadge from './NodeTypeBadge';

interface Props {
  criticalNodes: any;
  loading: boolean;
  onFetch: () => void;
  onSimulate: (nodeId: string) => void;
}

export default function CriticalNodeTable({ criticalNodes, loading, onFetch, onSimulate }: Props) {
  useEffect(() => { onFetch(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  const nodes = criticalNodes?.nodes || criticalNodes || [];

  if (!nodes || nodes.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-4">No critical nodes found</p>;
  }

  return (
    <div className="p-4">
      <h4 className="text-sm font-medium text-foreground mb-3">Critical Node Leaderboard</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground border-b border-border">
              <th className="text-left py-2 pr-2">#</th>
              <th className="text-left py-2 pr-2">Node</th>
              <th className="text-left py-2 pr-2">Type</th>
              <th className="text-right py-2 pr-2">Centrality</th>
              <th className="text-right py-2 pr-2">Risk</th>
              <th className="text-right py-2 pr-2">Combined</th>
              <th className="text-right py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((n: any, i: number) => (
              <tr key={n.id || i} className="border-b border-border/50 hover:bg-secondary/50 transition-colors">
                <td className="py-2 pr-2 text-muted-foreground">{i + 1}</td>
                <td className="py-2 pr-2 font-medium text-foreground">{n.label || n.id}</td>
                <td className="py-2 pr-2"><NodeTypeBadge type={n.type} /></td>
                <td className="py-2 pr-2 text-right text-muted-foreground">{(n.centrality_score ?? n.centrality ?? 0).toFixed(3)}</td>
                <td className="py-2 pr-2 text-right text-muted-foreground">{n.risk_score ?? 0}</td>
                <td className="py-2 pr-2 text-right font-medium text-foreground">{(n.combined_score ?? 0).toFixed(2)}</td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => onSimulate(n.id)}
                    className="text-xs bg-node-role/20 text-node-role px-2 py-1 rounded hover:bg-node-role/30 transition-colors"
                  >
                    <Zap className="w-3 h-3 inline mr-1" />
                    Simulate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
