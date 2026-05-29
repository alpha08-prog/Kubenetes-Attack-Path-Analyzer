import { useEffect, useState } from 'react';
import { isMockModeActive } from '@/api/mock/router';

export default function MockModeBanner() {
  const [active, setActive] = useState<boolean>(() => isMockModeActive());
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const onChange = () => setActive(isMockModeActive());
    window.addEventListener('mock-mode-changed', onChange);
    return () => window.removeEventListener('mock-mode-changed', onChange);
  }, []);

  if (!active || dismissed) return null;

  return (
    <div className="fixed top-0 inset-x-0 z-[100] flex justify-center pointer-events-none">
      <div className="pointer-events-auto mt-2 flex items-center gap-3 rounded-full border border-amber-500/40 bg-amber-500/10 backdrop-blur px-4 py-1.5 text-[11px] font-medium text-amber-300 shadow-lg shadow-amber-500/10">
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
        <span>
          Mock mode — backend unreachable. Showing synthetic Nokia-telecom scenario data.
        </span>
        <button
          onClick={() => setDismissed(true)}
          className="text-amber-300/70 hover:text-amber-200 transition-colors"
          aria-label="Dismiss mock mode banner"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
