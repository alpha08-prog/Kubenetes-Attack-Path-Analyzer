import { Loader2 } from 'lucide-react';

interface Props {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color?: string;
  loading?: boolean;
}

export default function StatCard({ title, value, icon, color = 'hsl(var(--primary))', loading }: Props) {
  return (
    <div
      className="relative flex flex-col justify-between rounded-xl bg-card border border-border px-2 sm:px-4 py-1.5 overflow-hidden h-full"
      style={{ borderLeftColor: color, borderLeftWidth: '3px' }}
    >
      {/* Subtle background tint */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{ background: `radial-gradient(ellipse at top left, ${color}, transparent 70%)` }}
      />

      {/* Icon + title row */}
      <div className="flex items-start justify-between gap-1 mb-1">
        <p className="text-[9px] md:text-[10px] font-medium text-muted-foreground tracking-wide uppercase flex-1 truncate">{title}</p>
        <div
          className="p-1 rounded-lg flex-shrink-0"
          style={{ backgroundColor: color + '1a' }}
        >
          <span style={{ color }}>{icon}</span>
        </div>
      </div>

      {/* Value */}
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
      ) : (
        <p className="text-sm md:text-lg lg:text-xl font-black tabular-nums text-foreground leading-tight truncate">{value}</p>
      )}
    </div>
  );
}
