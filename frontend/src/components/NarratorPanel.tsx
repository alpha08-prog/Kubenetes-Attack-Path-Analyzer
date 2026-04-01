import { useState } from 'react';
import { Loader2, ChevronUp, ChevronDown, Download, FileText } from 'lucide-react';
import FindingCard from './FindingCard';
import { SEVERITY_ORDER } from '@/styles/nodeColors';

interface Props {
  report: any;
  loading: boolean;
  onFetchReport: () => void;
}

export default function NarratorPanel({ report, loading, onFetchReport }: Props) {
  const [expanded, setExpanded] = useState(false);

  const findings = report?.findings || report || [];
  const sorted = [...(Array.isArray(findings) ? findings : [])].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity?.toLowerCase()) - SEVERITY_ORDER.indexOf(b.severity?.toLowerCase())
  );

  const exportReport = () => {
    const blob = new Blob([JSON.stringify(sorted, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'security-report.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="border-t border-border bg-card">
      <button
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded && !report && !loading) onFetchReport();
        }}
        className="w-full flex items-center justify-between px-6 py-3 hover:bg-secondary/50 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          <FileText className="w-4 h-4 text-primary" />
          Generate AI Security Report
        </span>
        {expanded ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronUp className="w-4 h-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-6 pb-6 max-h-[50vh] overflow-y-auto scrollbar-thin">
          {loading && (
            <div className="flex items-center justify-center py-12 gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground animate-pulse-glow">Analyzing attack graph with AI...</span>
            </div>
          )}

          {!loading && sorted.length > 0 && (
            <>
              <div className="flex justify-end mb-4">
                <button
                  onClick={exportReport}
                  className="flex items-center gap-2 text-xs bg-secondary text-foreground px-3 py-1.5 rounded hover:bg-surface-hover transition-colors"
                >
                  <Download className="w-3 h-3" />
                  Export Report
                </button>
              </div>
              <div className="space-y-4">
                {sorted.map((f: any, i: number) => (
                  <FindingCard key={i} finding={f} />
                ))}
              </div>
            </>
          )}

          {!loading && sorted.length === 0 && !report && (
            <p className="text-sm text-muted-foreground text-center py-8">Click to generate the report</p>
          )}
        </div>
      )}
    </div>
  );
}
