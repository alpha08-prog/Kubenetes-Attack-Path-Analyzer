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
    <div className="flex items-center gap-3 rounded-lg bg-card border border-border px-4 py-3">
      <div className="p-2 rounded-md" style={{ backgroundColor: color + '22' }}>
        <span style={{ color }}>{icon}</span>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{title}</p>
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground mt-1" />
        ) : (
          <p className="text-lg font-bold text-foreground">{value}</p>
        )}
      </div>
    </div>
  );
}
