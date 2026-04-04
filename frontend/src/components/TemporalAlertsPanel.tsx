import { useEffect } from 'react';
import { Bell, AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';
import { useTemporalAlerts } from '@/hooks/useTemporalAlerts';

const SEVERITY_CONFIG: Record<string, { color: string; Icon: any; bg: string }> = {
  critical: { color: '#E24B4A', Icon: AlertCircle,   bg: 'bg-red-500/10' },
  high:     { color: '#EF9F27', Icon: AlertTriangle,  bg: 'bg-orange-500/10' },
  medium:   { color: '#378ADD', Icon: Info,            bg: 'bg-blue-500/10' },
  low:      { color: '#1D9E75', Icon: CheckCircle2,   bg: 'bg-green-500/10' },
};

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export default function TemporalAlertsPanel() {
  const { alerts, total, loading, error, load } = useTemporalAlerts();

  useEffect(() => { load(); }, [load]);

  if (loading && alerts.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        Loading alerts…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-32 text-red-400 text-sm">
        {error}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 h-32 text-muted-foreground">
        <Bell className="w-7 h-7 opacity-30" />
        <p className="text-sm">No temporal alerts yet.</p>
        <p className="text-xs opacity-60">Alerts appear when consecutive snapshots reveal new attack paths or risk increases.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-muted-foreground">{total} alert{total !== 1 ? 's' : ''} total</p>
        <button
          onClick={() => load()}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Refresh
        </button>
      </div>

      {alerts.map((alert) => {
        const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
        const { color, Icon, bg } = cfg;
        return (
          <div key={alert.alert_id} className={`rounded-lg p-3 ${bg} border border-transparent`}>
            <div className="flex items-start gap-2">
              <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-foreground truncate">{alert.title}</p>
                  <span
                    className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded flex-shrink-0"
                    style={{ backgroundColor: `${color}22`, color }}
                  >
                    {alert.severity}
                  </span>
                </div>
                {alert.description && (
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                    {alert.description}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
                  <span>{formatTs(alert.triggered_at)}</span>
                  {alert.risk_delta !== 0 && (
                    <span style={{ color: alert.risk_delta > 0 ? '#E24B4A' : '#1D9E75' }}>
                      Risk {alert.risk_delta > 0 ? '+' : ''}{alert.risk_delta.toFixed(1)}
                    </span>
                  )}
                  {alert.new_paths?.length > 0 && (
                    <span className="text-red-400">{alert.new_paths.length} new path(s)</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
