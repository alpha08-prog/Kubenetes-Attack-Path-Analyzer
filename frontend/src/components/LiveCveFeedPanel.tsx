import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw, Search } from 'lucide-react';
import { getCves, getCveSummary, searchCves, type CveItem, type CveSummaryResponse } from '@/api/cveApi';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const REFRESH_INTERVAL_MS = 30 * 60 * 1000;

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeAxios = error as { response?: { data?: { detail?: string } }; message?: string };
    return maybeAxios.response?.data?.detail || maybeAxios.message || 'Unknown error';
  }

  return 'Unknown error';
}

function formatPublishedDate(value: string): string {
  if (!value) return 'Unknown date';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function severityBadgeClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'border-red-500/30 bg-red-500/15 text-red-200';
    case 'high':
      return 'border-orange-500/30 bg-orange-500/15 text-orange-200';
    case 'medium':
      return 'border-blue-500/30 bg-blue-500/15 text-blue-200';
    default:
      return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-200';
  }
}

function SummaryTile({
  label,
  value,
  className,
}: {
  label: string;
  value: number | string;
  className: string;
}) {
  return (
    <div className={cn('rounded px-1.5 py-0.5 flex items-center gap-1.5 border', className)}>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm font-bold text-foreground">{value}</span>
    </div>
  );
}

function CveCard({ cve }: { cve: CveItem }) {
  return (
    <article className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <code className="text-xs font-semibold text-foreground">{cve.cve_id}</code>
        <Badge variant="outline" className={severityBadgeClass(cve.severity)}>
          {cve.severity}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="bg-secondary/80 text-foreground">
          CVSS {cve.cvss_score ?? 'N/A'}
        </Badge>
        <Badge variant="outline" className="border-border text-muted-foreground">
          {cve.component || 'unknown'}
        </Badge>
      </div>

      <p className="mt-3 text-sm leading-5 text-muted-foreground">{cve.description}</p>

      <div className="mt-3 text-xs text-muted-foreground">
        Published {formatPublishedDate(cve.published)}
      </div>
    </article>
  );
}

export default function LiveCveFeedPanel() {
  const [cves, setCves] = useState<CveItem[]>([]);
  const [summary, setSummary] = useState<CveSummaryResponse | null>(null);
  const [query, setQuery] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasSearch = useMemo(() => activeQuery.trim().length > 0, [activeQuery]);

  const loadSummary = useCallback(async () => {
    const response = await getCveSummary();
    setSummary(response.data);
  }, []);

  const loadFeed = useCallback(async (searchTerm = '') => {
    const trimmed = searchTerm.trim();
    const response = trimmed ? await searchCves(trimmed) : await getCves();
    setCves(response.data.cves || []);
    setActiveQuery(trimmed);
  }, []);

  const loadPanel = useCallback(async () => {
    setError(null);
    setLoading(true);

    try {
      await Promise.all([loadSummary(), loadFeed('')]);
    } catch (error: unknown) {
      setError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [loadFeed, loadSummary]);

  const refreshPanel = useCallback(async () => {
    setError(null);
    setRefreshing(true);

    try {
      await Promise.all([loadSummary(), loadFeed(activeQuery)]);
    } catch (error: unknown) {
      setError(getErrorMessage(error));
    } finally {
      setRefreshing(false);
    }
  }, [activeQuery, loadFeed, loadSummary]);

  const handleSearch = useCallback(async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSearching(true);

    try {
      await loadFeed(query);
    } catch (error: unknown) {
      setError(getErrorMessage(error));
    } finally {
      setSearching(false);
    }
  }, [loadFeed, query]);

  const handleClear = useCallback(async () => {
    setQuery('');
    setError(null);
    setSearching(true);

    try {
      await loadFeed('');
    } catch (error: unknown) {
      setError(getErrorMessage(error));
    } finally {
      setSearching(false);
    }
  }, [loadFeed]);

  useEffect(() => {
    loadPanel();
  }, [loadPanel]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      refreshPanel();
    }, REFRESH_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [refreshPanel]);

  return (
    <section className="flex h-full w-full min-h-0 flex-col border-0 bg-transparent">
      <div className="border-b border-border px-3 py-2.5">
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-2.5">
          <div className="flex items-center justify-between xl:justify-start flex-1 min-w-0">
            <div className="truncate">
              <h2 className="text-sm font-semibold text-foreground truncate">Live CVE Feed</h2>
              <p className="text-[11px] text-muted-foreground truncate">
                {hasSearch ? `Results for "${activeQuery}"` : 'Latest Kubernetes CVEs'}
              </p>
            </div>
            
            {/* Show refresh button next to titles on smaller screens, or hide logic */}
            <RefreshCw className={cn('h-3.5 w-3.5 text-muted-foreground xl:hidden ml-2 flex-shrink-0', refreshing && 'animate-spin cursor-pointer')} onClick={refreshPanel} />
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <SummaryTile
              label="Critical"
              value={summary?.critical ?? (loading ? '...' : 0)}
              className="border-red-500/20 bg-red-500/8 text-red-500"
            />
            <SummaryTile
              label="High"
              value={summary?.high ?? (loading ? '...' : 0)}
              className="border-orange-500/20 bg-orange-500/8 text-orange-500"
            />
            <RefreshCw className={cn('h-3.5 w-3.5 text-muted-foreground hidden xl:block cursor-pointer hover:text-foreground transition-colors', refreshing && 'animate-spin')} onClick={refreshPanel} />
          </div>
        </div>

        <form onSubmit={handleSearch} className="mt-3 flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search CVEs, components, or keywords"
              className="h-9 border-border bg-background pl-9 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={searching}
            className="rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
          </button>
          {hasSearch && (
            <button
              type="button"
              onClick={handleClear}
              disabled={searching}
              className="rounded-md border border-border px-3 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 scrollbar-thin">
        {loading ? (
          <div className="flex h-full min-h-40 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading CVE feed...
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive-foreground">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
              <div>
                <p className="font-medium text-foreground">Unable to load the CVE feed</p>
                <p className="mt-1 text-muted-foreground">{error}</p>
              </div>
            </div>
          </div>
        ) : cves.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            No CVEs matched this search.
          </div>
        ) : (
          cves.map((cve) => <CveCard key={cve.cve_id} cve={cve} />)
        )}
      </div>
    </section>
  );
}
