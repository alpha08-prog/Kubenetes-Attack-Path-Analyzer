import { useEffect } from 'react';
import { Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import SeverityBadge from './SeverityBadge';

interface Props {
  cycles: any;
  loading: boolean;
  onFetch: () => void;
}

export default function CyclesPanel({ cycles, loading, onFetch }: Props) {
  useEffect(() => { onFetch(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  const cycleList = cycles?.cycles || cycles || [];

  if (!cycleList || cycleList.length === 0) {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-10 h-10 text-severity-low mx-auto mb-2" />
        <p className="text-sm font-medium text-severity-low">No privilege escalation loops detected</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-severity-high" />
        Privilege Escalation Cycles ({cycleList.length})
      </h4>
      {cycleList.map((cycle: any, i: number) => (
        <div key={i} className="bg-secondary rounded-lg p-3 space-y-2 border border-border">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={cycle.severity || 'high'} />
            <span className="text-xs text-muted-foreground">Length: {cycle.length || cycle.chain?.length || 0}</span>
            {cycle.max_risk != null && (
              <span className="text-xs text-muted-foreground ml-auto">Risk: {cycle.max_risk}</span>
            )}
          </div>
          <p className="text-sm font-mono text-foreground bg-background rounded px-2 py-1">
            {cycle.chain_string || (cycle.chain || cycle.nodes || []).join(' → ')}
          </p>
        </div>
      ))}
    </div>
  );
}
