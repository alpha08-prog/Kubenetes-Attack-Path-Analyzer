import { AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

interface ThreatScoreData {
  threat_score: number;
  risk_level: string;
  description: string;
  factors?: {
    attack_paths: boolean;
    shortest_path_hops?: number;
    privilege_escalation_cycles: number;
    critical_node_junctions: number;
    blast_radius_size: number;
  };
}

interface Props {
  threatScore?: ThreatScoreData;
  loading?: boolean;
}

export default function ThreatScoreCard({ threatScore, loading = false }: Props) {
  if (!threatScore) {
    return null;
  }

  const score = threatScore.threat_score;
  const riskLevel = threatScore.risk_level;

  // Determine color based on risk level
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'text-red-600 dark:text-red-400';
      case 'high':
        return 'text-orange-600 dark:text-orange-400';
      case 'medium':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'low':
        return 'text-blue-600 dark:text-blue-400';
      case 'minimal':
        return 'text-green-600 dark:text-green-400';
      default:
        return 'text-foreground';
    }
  };

  const getBgColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800';
      case 'high':
        return 'bg-orange-50 dark:bg-orange-950 border-orange-200 dark:border-orange-800';
      case 'medium':
        return 'bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800';
      case 'low':
        return 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800';
      case 'minimal':
        return 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800';
      default:
        return 'bg-secondary border-border';
    }
  };

  const getRiskBadgeColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'minimal':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      default:
        return 'bg-secondary text-foreground';
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getBgColor(riskLevel)} space-y-3`}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground uppercase">Threat Level</p>
          <div className="flex items-baseline gap-2">
            <span className={`text-3xl font-bold ${getRiskColor(riskLevel)}`}>
              {loading ? '—' : score.toFixed(1)}
            </span>
            <span className="text-xs text-muted-foreground">/10</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <AlertTriangle className={`w-5 h-5 ${getRiskColor(riskLevel)}`} />
          <span className={`text-xs font-semibold px-2 py-1 rounded ${getRiskBadgeColor(riskLevel)}`}>
            {riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)}
          </span>
        </div>
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">
        {threatScore.description}
      </p>

      {threatScore.factors && (
        <div className="space-y-1 border-t border-current/10 pt-3">
          <p className="text-xs font-medium text-muted-foreground">Risk Factors</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Attack Paths:</span>
              <span className={threatScore.factors.attack_paths ? 'text-destructive font-medium' : 'text-green-600 dark:text-green-400'}>
                {threatScore.factors.attack_paths ? '✓ Found' : '✗ None'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Escalation:</span>
              <span className={threatScore.factors.privilege_escalation_cycles > 0 ? 'text-destructive font-medium' : 'text-green-600 dark:text-green-400'}>
                {threatScore.factors.privilege_escalation_cycles} cycle{threatScore.factors.privilege_escalation_cycles !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Critical Nodes:</span>
              <span className="font-medium">{threatScore.factors.critical_node_junctions}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Blast Radius:</span>
              <span className="font-medium">{threatScore.factors.blast_radius_size} nodes</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
