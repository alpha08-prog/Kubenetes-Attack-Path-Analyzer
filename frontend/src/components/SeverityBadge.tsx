import { SEVERITY_COLORS } from '@/styles/nodeColors';

interface Props {
  severity: string;
}

export default function SeverityBadge({ severity }: Props) {
  const color = SEVERITY_COLORS[severity?.toLowerCase()] || '#8b8fa8';
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider"
      style={{ backgroundColor: color + '22', color, border: `1px solid ${color}44` }}
    >
      {severity}
    </span>
  );
}
