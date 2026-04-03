import { AlertCircle } from 'lucide-react';

interface Props {
  error: string;
  onRetry: () => void;
}

export function ErrorState({ error, onRetry }: Props) {
  return (
    <div className="flex items-center gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
      <AlertCircle className="w-4 h-4 flex-shrink-0 text-destructive" />
      <div className="flex-1">
        <p className="text-sm font-medium text-destructive">{error}</p>
        <button
          onClick={onRetry}
          className="text-xs underline mt-2 hover:no-underline text-destructive hover:text-destructive/80"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
