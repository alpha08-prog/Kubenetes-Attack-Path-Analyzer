import { X } from 'lucide-react';
import SeverityBadge from './SeverityBadge';

interface Props {
  simulation: any;
  onClose: () => void;
}

export default function SimulationModal({ simulation, onClose }: Props) {
  if (!simulation) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background/80 flex items-center justify-center" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-foreground">Simulation Result</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-secondary rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">Paths Broken</p>
            <p className="text-xl font-bold text-destructive">{simulation.paths_broken ?? 0}</p>
          </div>
          <div className="bg-secondary rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">Cycles Broken</p>
            <p className="text-xl font-bold text-accent">{simulation.cycles_broken ?? 0}</p>
          </div>
        </div>

        {simulation.impact && (
          <div className="mb-3">
            <span className="text-xs text-muted-foreground mr-2">Impact:</span>
            <SeverityBadge severity={simulation.impact} />
          </div>
        )}

        {simulation.narrative && (
          <blockquote className="border-l-2 border-primary pl-3 text-sm text-muted-foreground italic mb-3">
            {simulation.narrative}
          </blockquote>
        )}

        <button
          onClick={onClose}
          className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm hover:bg-surface-hover transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  );
}
