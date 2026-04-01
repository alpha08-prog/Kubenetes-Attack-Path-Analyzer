import SeverityBadge from './SeverityBadge';
import NodeTypeBadge from './NodeTypeBadge';
import { Wrench } from 'lucide-react';

interface Finding {
  severity: string;
  category: string;
  title: string;
  description: string;
  kill_chain?: string;
  affected_nodes?: string[];
  recommendation?: string;
  effort?: string;
}

export default function FindingCard({ finding }: { finding: Finding }) {
  const categoryColors: Record<string, string> = {
    attack_path: '#378ADD',
    blast_radius: '#EF9F27',
    privilege_escalation: '#7F77DD',
    critical_node: '#E24B4A',
  };

  return (
    <div className="rounded-lg bg-card border border-border p-4 space-y-3 animate-slide-in-right">
      <div className="flex items-center gap-2 flex-wrap">
        <SeverityBadge severity={finding.severity} />
        <span
          className="text-xs px-2 py-0.5 rounded font-medium"
          style={{
            backgroundColor: (categoryColors[finding.category] || '#8b8fa8') + '22',
            color: categoryColors[finding.category] || '#8b8fa8',
          }}
        >
          {finding.category?.replace(/_/g, ' ')}
        </span>
      </div>

      <h4 className="font-semibold text-foreground">{finding.title}</h4>
      <p className="text-sm text-muted-foreground">{finding.description}</p>

      {finding.kill_chain && (
        <pre className="text-xs p-3 rounded bg-background font-mono text-muted-foreground overflow-x-auto">
          {finding.kill_chain}
        </pre>
      )}

      {finding.affected_nodes && finding.affected_nodes.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {finding.affected_nodes.map((n, i) => {
            const type = n.split(':')[0];
            return <NodeTypeBadge key={i} type={type} />;
          })}
        </div>
      )}

      {finding.recommendation && (
        <div className="flex items-start gap-2 p-3 rounded bg-accent/10 border border-accent/20">
          <Wrench className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
          <p className="text-sm text-foreground">{finding.recommendation}</p>
        </div>
      )}

      {finding.effort && (
        <span className="text-xs text-muted-foreground">
          Effort: <span className="font-medium text-foreground">{finding.effort}</span>
        </span>
      )}
    </div>
  );
}
