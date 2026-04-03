import { useState, useEffect } from 'react';
import { Loader2, ChevronUp, ChevronDown, Download, FileText, AlertCircle } from 'lucide-react';
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

  // Cycle through loading messages so judges know it's working
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
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">{LOADING_MESSAGES[loadingMsgIdx]}</span>
              <span className="text-xs text-muted-foreground/60">This takes 10–20 seconds (LLM analysis)</span>
            </div>
          )}

          {!loading && error && (
            <div className="flex items-start gap-3 p-4 bg-destructive/10 rounded border border-destructive/30 text-sm text-destructive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium">Report generation failed</p>
                <p className="text-xs mt-1 text-destructive/80">{error}</p>
                <button onClick={onFetchReport} className="text-xs underline mt-2">Try again</button>
              </div>
            </div>
          )}

          {!loading && !error && sorted.length > 0 && (
            <>
              <div className="flex justify-end mb-4">
                <button
                  onClick={exportReport}
                  disabled={downloading}
                  className="flex items-center gap-2 text-xs bg-secondary text-foreground px-3 py-1.5 rounded hover:bg-surface-hover transition-colors"
                >
                  {downloading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Download PDF
                </button>
              </div>
              <div className="space-y-4">
                {sorted.map((f: any, i: number) => (
                  <FindingCard key={i} finding={f} />
                ))}
              </div>
            </>
          )}

          {!loading && !error && sorted.length === 0 && !report && (
            <p className="text-sm text-muted-foreground text-center py-8">Click to generate the AI security report</p>
          )}
        </div>
      )}
    </div>
  );
}
