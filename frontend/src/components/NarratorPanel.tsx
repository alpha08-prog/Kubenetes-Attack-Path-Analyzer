import { useState, useEffect } from 'react';
import { Loader2, ChevronUp, ChevronDown, Download, Sparkles, AlertCircle } from 'lucide-react';
import FindingCard from './FindingCard';
import { SEVERITY_ORDER } from '@/styles/nodeColors';
import { getReportPdf } from '@/api/graphApi';

interface Props {
  report: any;
  loading: boolean;
  onFetchReport: () => void;
  error?: string;
}

const LOADING_MESSAGES = [
  'Analyzing attack graph with AI...',
  'Running kill chain analysis...',
  'Generating remediation narrative...',
  'Almost there...',
];

export default function NarratorPanel({ report, loading, onFetchReport, error }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);

  useEffect(() => {
    if (!loading) { setLoadingMsgIdx(0); return; }
    const timer = setInterval(() => {
      setLoadingMsgIdx(i => (i + 1) % LOADING_MESSAGES.length);
    }, 4000);
    return () => clearInterval(timer);
  }, [loading]);

  const findings = report?.findings || report || [];
  const sorted = [...(Array.isArray(findings) ? findings : [])].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity?.toLowerCase()) - SEVERITY_ORDER.indexOf(b.severity?.toLowerCase())
  );

  const exportReport = async () => {
    setDownloading(true);
    try {
      const response = await getReportPdf();
      const contentDisposition = response.headers['content-disposition'] as string | undefined;
      const fileNameMatch = contentDisposition?.match(/filename="?([^"]+)"?/i);
      const fileName = fileNameMatch?.[1] || 'security-report.pdf';
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const hasSummary = sorted.length > 0;
  const criticalCount = sorted.filter((f: any) => f.severity?.toLowerCase() === 'critical').length;

  return (
    <div className="flex-shrink-0 border-t border-border bg-card/90">
      {/* Trigger bar */}
      <button
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded && !report && !loading) onFetchReport();
        }}
        className="w-full flex items-center justify-between px-4 sm:px-6 py-2.5 hover:bg-secondary/40 transition-colors group"
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-semibold text-foreground">AI Security Narrative</span>
          </div>
          {hasSummary && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">{sorted.length} findings</span>
              {criticalCount > 0 && (
                <span className="text-[10px] font-semibold text-destructive bg-destructive/10 border border-destructive/20 px-1.5 py-0.5 rounded-full">
                  {criticalCount} critical
                </span>
              )}
            </div>
          )}
          {loading && (
            <span className="flex items-center gap-1 text-[10px] text-primary animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              Generating...
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!expanded && !hasSummary && (
            <span className="text-[10px] text-muted-foreground hidden sm:inline group-hover:text-primary transition-colors">
              Click to generate →
            </span>
          )}
          {expanded
            ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
            : <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
          }
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 sm:px-6 pb-6 max-h-[50vh] overflow-y-auto scrollbar-thin border-t border-border/60">
          {loading && (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <div className="relative">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <div className="absolute inset-0 rounded-full animate-pulse-glow" style={{ boxShadow: '0 0 20px hsl(210 80% 58% / 0.4)' }} />
              </div>
              <span className="text-sm text-muted-foreground animate-slide-in-up">{LOADING_MESSAGES[loadingMsgIdx]}</span>
              <span className="text-xs text-muted-foreground/50">LLM analysis · 10–20 seconds</span>
            </div>
          )}

          {!loading && error && (
            <div className="flex items-start gap-3 mt-4 p-4 bg-destructive/8 rounded-lg border border-destructive/25 text-sm text-destructive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium">Report generation failed</p>
                <p className="text-xs mt-1 text-destructive/70">{error}</p>
                <button onClick={onFetchReport} className="text-xs underline mt-2 hover:no-underline">
                  Try again
                </button>
              </div>
            </div>
          )}

          {!loading && !error && sorted.length > 0 && (
            <div className="mt-4 space-y-4">
              <div className="flex justify-end">
                <button
                  onClick={exportReport}
                  disabled={downloading}
                  className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-surface-hover text-foreground px-3 py-1.5 rounded-lg transition-colors"
                >
                  {downloading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Download PDF
                </button>
              </div>
              {sorted.map((f: any, i: number) => (
                <FindingCard key={i} finding={f} />
              ))}
            </div>
          )}

          {!loading && !error && sorted.length === 0 && !report && (
            <p className="text-sm text-muted-foreground text-center py-8">
              Click to generate the AI security narrative
            </p>
          )}
        </div>
      )}
    </div>
  );
}
