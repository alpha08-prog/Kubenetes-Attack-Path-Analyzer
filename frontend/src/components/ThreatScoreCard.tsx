import { AlertTriangle, ShieldAlert, ShieldCheck } from 'lucide-react';

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

const RISK_CONFIG: Record<string, {
  scoreColor: string;
  badgeBg: string;
  badgeText: string;
  borderColor: string;
  barColor: string;
  glowClass: string;
  Icon: React.ElementType;
}> = {
  critical: {
    scoreColor: 'text-red-400',
    badgeBg: 'bg-red-500/15 border border-red-500/30',
    badgeText: 'text-red-400',
    borderColor: 'border-red-500/40',
    barColor: 'bg-red-500',
    glowClass: 'glow-critical',
    Icon: ShieldAlert,
  },
  high: {
    scoreColor: 'text-orange-400',
    badgeBg: 'bg-orange-500/15 border border-orange-500/30',
    badgeText: 'text-orange-400',
    borderColor: 'border-orange-500/40',
    barColor: 'bg-orange-400',
    glowClass: '',
    Icon: AlertTriangle,
  },
  medium: {
    scoreColor: 'text-yellow-400',
    badgeBg: 'bg-yellow-500/15 border border-yellow-500/30',
    badgeText: 'text-yellow-400',
    borderColor: 'border-yellow-500/30',
    barColor: 'bg-yellow-400',
    glowClass: '',
    Icon: AlertTriangle,
  },
  low: {
    scoreColor: 'text-blue-400',
    badgeBg: 'bg-blue-500/15 border border-blue-500/30',
    badgeText: 'text-blue-400',
    borderColor: 'border-blue-500/30',
    barColor: 'bg-blue-400',
    glowClass: 'glow-primary',
    Icon: ShieldCheck,
  },
  minimal: {
    scoreColor: 'text-emerald-400',
    badgeBg: 'bg-emerald-500/15 border border-emerald-500/30',
    badgeText: 'text-emerald-400',
    borderColor: 'border-emerald-500/30',
    barColor: 'bg-emerald-400',
    glowClass: '',
    Icon: ShieldCheck,
  },
};

const FALLBACK = {
  scoreColor: 'text-foreground',
  badgeBg: 'bg-secondary',
  badgeText: 'text-foreground',
  borderColor: 'border-border',
  barColor: 'bg-primary',
  glowClass: '',
  Icon: AlertTriangle,
};

export default function ThreatScoreCard({ threatScore, loading = false }: Props) {
  if (!threatScore) return null;

  const { threat_score: score, risk_level: riskLevel, description, factors } = threatScore;
  const cfg = RISK_CONFIG[riskLevel] ?? FALLBACK;
  const { Icon } = cfg;
  const pct = Math.min(100, (score / 10) * 100);
  const label = riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1);

  return (
    <div className={`rounded-xl border bg-card p-2.5 flex flex-col gap-2 ${cfg.borderColor} ${cfg.glowClass}`}>
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-semibold tracking-widest text-muted-foreground uppercase">
          Threat
        </span>
        <span className={`flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${cfg.badgeBg} ${cfg.badgeText}`}>
          <Icon className="w-2.5 h-2.5" />
          {label}
        </span>
      </div>

      {/* Score + bar row */}
      <div className="flex items-center gap-2">
        <span className={`text-2xl font-black tabular-nums leading-none flex-shrink-0 ${cfg.scoreColor}`}>
          {loading ? '—' : score.toFixed(1)}
        </span>
        <div className="h-1 rounded-full bg-secondary overflow-hidden flex-1">
          <div
            className={`h-full rounded-full animate-fill-bar ${cfg.barColor}`}
            style={{ width: loading ? '0%' : `${pct}%` }}
          />
        </div>
      </div>

      {/* Description — single line only */}
      <p className="text-[9px] text-muted-foreground leading-tight line-clamp-1">
        {description}
      </p>

      {/* Risk factors — hidden (use tooltip if needed in future) */}
    </div>
  );
}

function FactorRow({ label, value, danger }: { label: string; value: string; danger: boolean }) {
  return (
    <div className="flex items-center justify-between gap-1">
      <span className="text-[10px] text-muted-foreground truncate">{label}</span>
      <span className={`text-[10px] font-semibold tabular-nums ${danger ? 'text-destructive' : 'text-foreground'}`}>
        {value}
      </span>
    </div>
  );
}
