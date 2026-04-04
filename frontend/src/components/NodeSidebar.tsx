import { useState } from 'react';
import { X, AlertTriangle, RefreshCw, Package, ShieldAlert } from 'lucide-react';
import NodeTypeBadge from './NodeTypeBadge';
import SeverityBadge from './SeverityBadge';
import { riskToColor } from '@/styles/riskGradient';
import type { GraphNode } from '@/hooks/useGraph';
import client from '@/api/client';

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

function scoreToSeverity(score: number): string {
  if (score >= 9) return 'critical';
  if (score >= 7) return 'high';
  if (score >= 4) return 'medium';
  if (score > 0) return 'low';
  return 'none';
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#E24B4A',
  high: '#EF9F27',
  medium: '#378ADD',
  low: '#1D9E75',
  none: '#888780',
};

interface ImageCvssData {
  image: string;
  cvss_score: number;
  severity: string;
  source: string;
}

interface PodCvssResult {
  pod_id: string;
  pod_label: string;
  images: ImageCvssData[];
  aggregate_risk: number;
  aggregate_severity: string;
  timestamp: string;
}

export default function NodeSidebar({ node, onClose }: Props) {
  const [cvssData, setCvssData] = useState<PodCvssResult | null>(null);
  const [cvssLoading, setCvssLoading] = useState(false);
  const [cvssError, setCvssError] = useState<string | null>(null);

  if (!node) return null;

  const isPod = node.type === 'pod';
  const hasCveScore = node.metadata?.cve_score > 0;
  const cvssScores: Record<string, number> = node.metadata?.cvss_scores ?? {};
  const containerImages: string[] = node.metadata?.container_images ?? [];

  const loadCvssDetails = async () => {
    setCvssLoading(true);
    setCvssError(null);
    try {
      const encodedId = encodeURIComponent(node.id);
      const res = await client.get(`/api/cves/images/${encodedId}`);
      setCvssData(res.data);
    } catch (e: any) {
      setCvssError(e.message || 'Failed to load CVSS data');
    } finally {
      setCvssLoading(false);
    }
  };

  const imagesToShow: ImageCvssData[] = cvssData?.images ?? containerImages.map(img => ({
    image: img,
    cvss_score: cvssScores[img] ?? 0,
    severity: scoreToSeverity(cvssScores[img] ?? 0),
    source: 'cached',
  }));

  return (
    <div className="absolute top-0 right-0 w-80 h-full bg-card border-l border-border p-4 overflow-y-auto scrollbar-thin z-20 transition-transform duration-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-foreground">Node Details</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-xs text-muted-foreground">Label</p>
          <p className="font-medium text-foreground">{node.label}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Type</p>
          <NodeTypeBadge type={node.type} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">ID</p>
          <p className="text-sm font-mono text-muted-foreground break-all">{node.id}</p>
        </div>
        {node.namespace && (
          <div>
            <p className="text-xs text-muted-foreground">Namespace</p>
            <p className="text-sm text-foreground">{node.namespace}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-muted-foreground">Risk Score</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${node.risk_score * 10}%`, backgroundColor: riskToColor(node.risk_score) }}
              />
            </div>
            <span className="text-sm font-bold" style={{ color: riskToColor(node.risk_score) }}>
              {node.risk_score}
            </span>
          </div>
        </div>
        {node.risk_score >= 8 && <SeverityBadge severity="critical" />}
        {node.risk_score >= 6 && node.risk_score < 8 && <SeverityBadge severity="high" />}

        {node.properties && Object.keys(node.properties).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Properties</p>
            <div className="space-y-1">
              {Object.entries(node.properties).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="text-foreground font-mono truncate ml-4" title={String(v)}>{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── B2: Container Security Section ──────────────────────────── */}
        {isPod && (
          <div className="mt-4 pt-4 border-t border-border/60">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-orange-400" />
                <p className="text-sm font-semibold text-foreground">Container Security</p>
              </div>
              <button
                onClick={loadCvssDetails}
                disabled={cvssLoading}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-secondary"
                title="Refresh CVSS from NVD"
              >
                <RefreshCw className={`w-3 h-3 ${cvssLoading ? 'animate-spin' : ''}`} />
                {cvssLoading ? 'Loading…' : 'Refresh'}
              </button>
            </div>

            {cvssError && (
              <p className="text-xs text-red-400 mb-2">{cvssError}</p>
            )}

            {(hasCveScore || imagesToShow.length > 0) ? (
              <div className="space-y-2">
                {imagesToShow.length > 0 && (
                  <div className="space-y-1.5">
                    {imagesToShow.map((img) => (
                      <div key={img.image} className="bg-secondary/30 rounded-lg p-2.5">
                        <div className="flex items-start gap-2">
                          <Package className="w-3 h-3 text-muted-foreground mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-mono text-foreground truncate" title={img.image}>
                              {img.image}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <span
                                className="text-xs font-bold"
                                style={{ color: SEVERITY_COLORS[img.severity] ?? '#888780' }}
                              >
                                CVSS {img.cvss_score > 0 ? img.cvss_score.toFixed(1) : 'N/A'}
                              </span>
                              {img.severity !== 'none' && (
                                <span
                                  className="text-[10px] uppercase px-1.5 py-0.5 rounded font-medium"
                                  style={{
                                    backgroundColor: `${SEVERITY_COLORS[img.severity]}22`,
                                    color: SEVERITY_COLORS[img.severity],
                                  }}
                                >
                                  {img.severity}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {hasCveScore && imagesToShow.length === 0 && (
                  <div className="bg-secondary/30 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                        <span className="text-xs text-muted-foreground">Max CVSS Score</span>
                      </div>
                      <span className="text-sm font-bold text-orange-400">
                        {node.metadata.cve_score}
                      </span>
                    </div>
                  </div>
                )}

                {(cvssData || hasCveScore) && (
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    Risk score adjusted with live CVE data from NIST NVD API.
                    {cvssData?.timestamp && (
                      <span className="block mt-0.5">
                        Last checked: {new Date(cvssData.timestamp).toLocaleString()}
                      </span>
                    )}
                  </p>
                )}
              </div>
            ) : (
              <div className="bg-secondary/20 rounded-lg p-3 text-center">
                <p className="text-xs text-muted-foreground">
                  No container images detected or no known vulnerabilities.
                </p>
                <button
                  onClick={loadCvssDetails}
                  className="mt-2 text-xs text-blue-400 hover:underline"
                >
                  Check NVD for this pod
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
