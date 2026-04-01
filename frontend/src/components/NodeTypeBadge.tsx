import { NODE_COLORS, NODE_LABELS } from '@/styles/nodeColors';

interface Props {
  type: string;
}

export default function NodeTypeBadge({ type }: Props) {
  const color = NODE_COLORS[type] || '#8b8fa8';
  const label = NODE_LABELS[type] || type;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: color + '22', color, border: `1px solid ${color}44` }}
    >
      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
