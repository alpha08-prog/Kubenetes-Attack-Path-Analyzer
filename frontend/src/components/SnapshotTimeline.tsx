import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import type { TimelinePoint } from '@/api/snapshotApi';

interface Props {
  timeline: TimelinePoint[];
  loading?: boolean;
}

function formatTs(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
      ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts.slice(0, 16);
  }
}

function riskColor(risk: number): string {
  if (risk >= 7) return '#E24B4A';
  if (risk >= 4) return '#EF9F27';
  return '#1D9E75';
}

export default function SnapshotTimeline({ timeline, loading }: Props) {
  if (loading) {
    return (
      <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
        Loading timeline…
      </div>
    );
  }

  if (timeline.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
        No snapshot data yet. Create your first snapshot to start tracking risk over time.
      </div>
    );
  }

  const data = timeline.map((p) => ({
    ...p,
    label: formatTs(p.timestamp),
    risk: parseFloat(p.aggregate_risk.toFixed(2)),
  }));

  const maxRisk = Math.max(...data.map((d) => d.risk), 1);

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: '#888' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, Math.max(maxRisk + 1, 10)]}
            tick={{ fontSize: 10, fill: '#888' }}
            tickLine={false}
            axisLine={false}
            width={28}
          />
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(val: number) => [val.toFixed(2), 'Aggregate Risk']}
            labelFormatter={(l) => `Snapshot: ${l}`}
          />
          {/* Danger threshold lines */}
          <ReferenceLine y={7} stroke="#E24B4A" strokeDasharray="4 2" strokeOpacity={0.5} />
          <ReferenceLine y={4} stroke="#EF9F27" strokeDasharray="4 2" strokeOpacity={0.4} />
          <Line
            type="monotone"
            dataKey="risk"
            stroke="#378ADD"
            strokeWidth={2}
            dot={(props: any) => {
              const { cx, cy, payload } = props;
              return (
                <circle
                  key={payload.snapshot_id}
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={riskColor(payload.risk)}
                  stroke="hsl(var(--card))"
                  strokeWidth={1.5}
                />
              );
            }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-1 text-[10px] text-muted-foreground px-2">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-red-400 inline-block rounded" />
          High ≥7
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-orange-400 inline-block rounded" />
          Medium ≥4
        </span>
      </div>
    </div>
  );
}
