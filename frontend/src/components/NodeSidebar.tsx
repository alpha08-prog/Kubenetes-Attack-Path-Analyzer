import { X } from 'lucide-react';
import NodeTypeBadge from './NodeTypeBadge';
import SeverityBadge from './SeverityBadge';
import { riskToColor } from '@/styles/riskGradient';
import type { GraphNode } from '@/hooks/useGraph';

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

export default function NodeSidebar({ node, onClose }: Props) {
  if (!node) return null;

  return (
    <div className="absolute top-0 right-0 w-80 h-full bg-card border-l border-border p-4 overflow-y-auto scrollbar-thin z-20 transition-transform duration-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-foreground">Node Details</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-xs text-muted-foreground">Label</p>
          <p className="font-medium text-foreground">{node.label}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Type</p>
          <NodeTypeBadge type={node.type} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">ID</p>
          <p className="text-sm font-mono text-muted-foreground break-all">{node.id}</p>
        </div>
        {node.namespace && (
          <div>
            <p className="text-xs text-muted-foreground">Namespace</p>
            <p className="text-sm text-foreground">{node.namespace}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-muted-foreground">Risk Score</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${node.risk_score * 10}%`, backgroundColor: riskToColor(node.risk_score) }}
              />
            </div>
            <span className="text-sm font-bold" style={{ color: riskToColor(node.risk_score) }}>
              {node.risk_score}
            </span>
          </div>
        </div>
        {node.risk_score >= 8 && <SeverityBadge severity="critical" />}
        {node.risk_score >= 6 && node.risk_score < 8 && <SeverityBadge severity="high" />}

        {node.properties && Object.keys(node.properties).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Properties</p>
            <div className="space-y-1">
              {Object.entries(node.properties).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="text-foreground font-mono">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
