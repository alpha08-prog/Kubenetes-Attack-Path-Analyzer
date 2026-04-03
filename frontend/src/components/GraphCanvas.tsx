import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { NODE_COLORS, NODE_SHAPES } from '@/styles/nodeColors';
import { riskToColor, riskToSize, riskToWidth } from '@/styles/riskGradient';
import type { GraphData, GraphNode } from '@/hooks/useGraph';
import NodeSidebar from './NodeSidebar';

cytoscape.use(dagre);

interface Props {
  graphData: GraphData | null;
  attackPath?: any;
  blastRadius?: any;
  cycles?: any;
  overlayMode: 'default' | 'attack' | 'blast' | 'cycle';
  onNodeSelect?: (node: GraphNode) => void;
  onContextAction?: (action: string, nodeId: string) => void;
}

type FilterGroup = 'pods' | 'secrets' | 'databases' | 'serviceAccounts' | 'roles';
type TypeFilters = Record<FilterGroup, boolean>;

const DEFAULT_TYPE_FILTERS: TypeFilters = {
  pods: true,
  secrets: true,
  databases: true,
  serviceAccounts: false,
  roles: false,
};

const FILTER_LABELS: Array<{ key: FilterGroup; label: string }> = [
  { key: 'pods', label: 'Pods' },
  { key: 'secrets', label: 'Secrets' },
  { key: 'databases', label: 'Databases' },
  { key: 'serviceAccounts', label: 'Service Accounts' },
  { key: 'roles', label: 'Roles' },
];

const LEGEND_ITEMS = [
  { type: 'pod', label: 'Pod' },
  { type: 'service_account', label: 'Service Acct' },
  { type: 'role', label: 'Role' },
  { type: 'secret', label: 'Secret' },
  { type: 'database', label: 'Database' },
  { type: 'user', label: 'User' },
];

const ROLE_TYPES = new Set([
  'role',
  'clusterrole',
  'rolebinding',
  'clusterrolebinding',
  'cluster_role',
  'role_binding',
  'cluster_role_binding',
]);

const SERVICE_ACCOUNT_TYPES = new Set(['service_account', 'serviceaccount']);

function matchesTypeFilter(nodeType: string, filters: TypeFilters): boolean {
  const normalizedType = (nodeType || '').toLowerCase();

  if (normalizedType === 'pod') return filters.pods;
  if (normalizedType === 'secret') return filters.secrets;
  if (normalizedType === 'database') return filters.databases;
  if (SERVICE_ACCOUNT_TYPES.has(normalizedType)) return filters.serviceAccounts;
  if (ROLE_TYPES.has(normalizedType)) return filters.roles;

  // Keep non-core types (for example "user") visible unless narrowed by risk/focus.
  return true;
}

function buildFocusNodeIds(attackPath: any, blastRadius: any): Set<string> {
  const ids = new Set<string>();

  if (Array.isArray(attackPath?.path)) {
    attackPath.path.forEach((step: any) => {
      if (step?.from) ids.add(String(step.from));
      if (step?.to) ids.add(String(step.to));
    });
  }

  if (blastRadius?.zones && typeof blastRadius.zones === 'object') {
    Object.values(blastRadius.zones).forEach((zone: any) => {
      if (Array.isArray(zone)) {
        zone.forEach((id) => ids.add(String(id)));
      }
    });
  }

  return ids;
}

export default function GraphCanvas({
  graphData,
  attackPath,
  blastRadius,
  cycles,
  overlayMode,
  onNodeSelect,
  onContextAction,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);
  const [typeFilters, setTypeFilters] = useState<TypeFilters>(DEFAULT_TYPE_FILTERS);
  const [riskThreshold, setRiskThreshold] = useState(0);
  const [focusMode, setFocusMode] = useState(false);

  const hasAttackPath = Array.isArray(attackPath?.path) && attackPath.path.length > 0;
  const focusNodeIds = useMemo(() => buildFocusNodeIds(attackPath, blastRadius), [attackPath, blastRadius]);

  useEffect(() => {
    if (!hasAttackPath && focusMode) {
      setFocusMode(false);
    }
  }, [hasAttackPath, focusMode]);

  const filteredGraph = useMemo(() => {
    if (!graphData) return null;

    const filteredNodes = graphData.nodes.filter((node) => {
      if ((node.risk_score ?? 0) < riskThreshold) return false;
      if (!matchesTypeFilter(node.type, typeFilters)) return false;
      if (focusMode && !focusNodeIds.has(node.id)) return false;
      return true;
    });

    const visibleNodeIds = new Set(filteredNodes.map((node) => node.id));
    const filteredEdges = graphData.edges.filter(
      (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
    );

    return { nodes: filteredNodes, edges: filteredEdges };
  }, [graphData, typeFilters, riskThreshold, focusMode, focusNodeIds]);

  const nodeCount = filteredGraph?.nodes.length ?? 0;
  const layout = useMemo(
    () =>
      nodeCount > 50
        ? ({
            name: 'concentric',
            minNodeSpacing: 40,
            avoidOverlap: true,
            spacingFactor: 1.1,
            padding: 24,
            concentric: (node: any) => Number(node.data('risk_score') ?? 0),
            levelWidth: () => 2,
            animate: false,
          } as any)
        : ({
            name: 'dagre',
            rankDir: 'LR',
            nodeSep: 60,
            rankSep: 100,
            padding: 30,
            fit: true,
            spacingFactor: 1.1,
          } as any),
    [nodeCount],
  );

  const buildCy = useCallback(() => {
    if (!containerRef.current || !filteredGraph) return;

    if (cyRef.current) cyRef.current.destroy();

    const elements: cytoscape.ElementDefinition[] = [];
    filteredGraph.nodes.forEach((node) => {
      elements.push({
        data: { id: node.id, label: node.label, type: node.type, risk_score: node.risk_score, ...node },
      });
    });
    filteredGraph.edges.forEach((edge) => {
      elements.push({
        data: {
          id: edge.id || `${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          relation: edge.relation,
          risk_score: edge.risk_score,
        },
      });
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '10px',
            color: '#ffffff',
            'text-margin-y': 8,
            'text-outline-color': '#0f1117',
            'text-outline-width': 2,
            'border-width': 2,
            'border-color': (ele: any) => riskToColor(ele.data('risk_score') || 5),
            width: (ele: any) => riskToSize(ele.data('risk_score') || 5),
            height: (ele: any) => riskToSize(ele.data('risk_score') || 5),
            'background-color': (ele: any) => {
              const risk = ele.data('risk_score') || 5;
              const typeColor = NODE_COLORS[ele.data('type')];
              // Blend: high-risk nodes get risk color, low-risk keep type color
              return risk >= 7 ? riskToColor(risk) : (typeColor || '#8b8fa8');
            },
            shape: (ele: any) => NODE_SHAPES[ele.data('type')] || 'ellipse',
          } as any,
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#FFD700',
          },
        },
        {
          selector: 'edge',
          style: {
            width: (ele: any) => riskToWidth(ele.data('risk_score') || 3),
            'line-color': (ele: any) => riskToColor(ele.data('risk_score') || 3),
            'target-arrow-color': (ele: any) => riskToColor(ele.data('risk_score') || 3),
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(relation)',
            'font-size': '8px',
            color: '#8b8fa8',
            'text-rotation': 'autorotate',
            'text-outline-color': '#0f1117',
            'text-outline-width': 1,
          } as any,
        },
        {
          selector: '.dimmed',
          style: { opacity: 0.15 },
        },
        {
          selector: '.highlighted',
          style: { opacity: 1 },
        },
        {
          selector: '.attack-edge',
          style: { 'line-color': '#E24B4A', 'target-arrow-color': '#E24B4A', width: 4 } as any,
        },
        {
          selector: '.blast-0',
          style: { 'background-color': '#E24B4A', 'border-color': '#E24B4A' } as any,
        },
        {
          selector: '.blast-1',
          style: { 'background-color': '#EF9F27', 'border-color': '#EF9F27' } as any,
        },
        {
          selector: '.blast-2',
          style: { 'background-color': '#FFD700', 'border-color': '#FFD700' } as any,
        },
        {
          selector: '.blast-3',
          style: { 'background-color': '#8b8fa8', 'border-color': '#8b8fa8' } as any,
        },
        {
          selector: '.cycle-node',
          style: { 'background-color': '#7F77DD', 'border-color': '#7F77DD', 'border-width': 3 } as any,
        },
      ],
      layout,
      wheelSensitivity: 0.3,
    });

    cy.on('tap', 'node', (e) => {
      const data = e.target.data();
      setSelectedNode(data as GraphNode);
      onNodeSelect?.(data as GraphNode);
      setContextMenu(null);
    });

    cy.on('tap', (e) => {
      if (e.target === cy) {
        setSelectedNode(null);
        setContextMenu(null);
      }
    });

    cy.on('cxttap', 'node', (e) => {
      const pos = e.renderedPosition;
      setContextMenu({ x: pos.x, y: pos.y, nodeId: e.target.data('id') });
    });

    cyRef.current = cy;
  }, [filteredGraph, layout, onNodeSelect]);

  useEffect(() => {
    buildCy();
  }, [buildCy]);

  useEffect(() => {
    if (!selectedNode || !filteredGraph) return;
    if (!filteredGraph.nodes.some((node) => node.id === selectedNode.id)) {
      setSelectedNode(null);
      setContextMenu(null);
    }
  }, [filteredGraph, selectedNode]);

  // Overlay effects
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('dimmed highlighted attack-edge blast-0 blast-1 blast-2 blast-3 cycle-node');

    if (overlayMode === 'attack' && attackPath?.path) {
      cy.elements().addClass('dimmed');
      const pathNodes = new Set<string>();
      attackPath.path.forEach((step: any) => {
        pathNodes.add(step.from);
        pathNodes.add(step.to);
      });
      pathNodes.forEach((id) => cy.getElementById(id).removeClass('dimmed').addClass('highlighted'));
      attackPath.path.forEach((step: any) => {
        cy.edges()
          .filter((edge: any) => edge.data('source') === step.from && edge.data('target') === step.to)
          .removeClass('dimmed')
          .addClass('highlighted attack-edge');
      });
    }

    if (overlayMode === 'blast' && blastRadius?.zones) {
      cy.elements().addClass('dimmed');
      Object.entries(blastRadius.zones).forEach(([hop, nodes]: [string, any]) => {
        const cls = `blast-${Math.min(parseInt(hop, 10), 3)}`;
        (nodes as string[]).forEach((id: string) => {
          cy.getElementById(id).removeClass('dimmed').addClass(`highlighted ${cls}`);
        });
      });
    }

    if (overlayMode === 'cycle' && cycles?.cycles) {
      cy.elements().addClass('dimmed');
      cycles.cycles.forEach((cycle: any) => {
        (cycle.nodes || cycle.chain || []).forEach((id: string) => {
          cy.getElementById(id).removeClass('dimmed').addClass('highlighted cycle-node');
        });
      });
    }
  }, [overlayMode, attackPath, blastRadius, cycles]);

  const handleContextAction = (action: string) => {
    if (contextMenu) {
      onContextAction?.(action, contextMenu.nodeId);
      setContextMenu(null);
    }
  };

  const toggleTypeFilter = (group: FilterGroup) => {
    setTypeFilters((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  const totalNodes = graphData?.nodes.length ?? 0;
  const visibleNodes = filteredGraph?.nodes.length ?? 0;
  const visibleEdges = filteredGraph?.edges.length ?? 0;

  return (
    <div className="w-full h-full flex flex-col bg-background rounded-lg border border-border overflow-hidden">
      <div className="border-b border-border bg-card/90 px-3 py-2">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="text-muted-foreground font-medium">Show:</span>
          {FILTER_LABELS.map((filter) => (
            <label key={filter.key} className="inline-flex items-center gap-1.5 text-foreground cursor-pointer">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-primary"
                checked={typeFilters[filter.key]}
                onChange={() => toggleTypeFilter(filter.key)}
              />
              <span>{filter.label}</span>
            </label>
          ))}

          <button
            type="button"
            onClick={() => setFocusMode((prev) => !prev)}
            disabled={!hasAttackPath}
            className={`ml-auto rounded-md px-2.5 py-1 font-medium transition-colors ${
              focusMode
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
            title={hasAttackPath ? 'Show only path/blast context' : 'Run attack-path analysis first'}
          >
            Focus Mode {focusMode ? 'On' : 'Off'}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
          <span className="text-muted-foreground font-medium">Risk threshold:</span>
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={riskThreshold}
            onChange={(e) => setRiskThreshold(Number(e.target.value))}
            className="w-40"
          />
          <span className="rounded bg-secondary px-2 py-0.5 text-foreground">{riskThreshold}</span>
          <span className="text-muted-foreground">
            Showing <span className="text-foreground font-medium">{visibleNodes}</span> / {totalNodes} nodes,{' '}
            <span className="text-foreground font-medium">{visibleEdges}</span> edges
          </span>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="w-40 flex-shrink-0 border-r border-border bg-card/50 p-4 text-xs space-y-5 overflow-y-auto hidden sm:block">
          <div>
            <p className="text-xs font-semibold text-foreground mb-3">Risk Level</p>
            {[
              { color: '#E24B4A', label: 'Critical (≥8)' },
              { color: '#EF9F27', label: 'High (6-7.9)' },
              { color: '#378ADD', label: 'Medium (4-5.9)' },
              { color: '#1D9E75', label: 'Low (<4)' },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-2.5 mb-2">
                <span className="w-3 h-3 rounded-full flex-shrink-0 shadow-sm" style={{ backgroundColor: item.color }} />
                <span className="text-muted-foreground">{item.label}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-border pt-4">
            <p className="text-xs font-semibold text-foreground mb-3">Node Type</p>
            {LEGEND_ITEMS.map((item) => (
              <div key={item.type} className="flex items-center gap-2.5 mb-2">
                <span className="w-3 h-3 rounded-sm flex-shrink-0 shadow-sm" style={{ backgroundColor: NODE_COLORS[item.type] }} />
                <span className="text-muted-foreground">{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative flex-1 min-h-0">
          <div ref={containerRef} className="w-full h-full" />

          {contextMenu && (
            <div
              className="absolute z-30 bg-card border border-border rounded-lg shadow-lg py-1 min-w-[180px]"
              style={{ left: contextMenu.x, top: contextMenu.y }}
            >
              {[
                { action: 'set-source', label: 'Set as Attack Source' },
                { action: 'set-target', label: 'Set as Attack Target' },
                { action: 'blast-radius', label: 'Show Blast Radius' },
                { action: 'simulate-removal', label: 'Simulate Removal' },
              ].map((item) => (
                <button
                  key={item.action}
                  className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-secondary transition-colors"
                  onClick={() => handleContextAction(item.action)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

        <NodeSidebar node={selectedNode} onClose={() => setSelectedNode(null)} />
        </div>
      </div>
    </div>
  );
}
