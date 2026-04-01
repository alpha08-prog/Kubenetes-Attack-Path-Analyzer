import { useEffect, useRef, useCallback, useState } from 'react';
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

const LEGEND_ITEMS = [
  { type: 'pod', label: 'Pod', shape: '■' },
  { type: 'service_account', label: 'Service Acct', shape: '●' },
  { type: 'role', label: 'Role', shape: '◆' },
  { type: 'secret', label: 'Secret', shape: '▲' },
  { type: 'database', label: 'Database', shape: '⬬' },
  { type: 'user', label: 'User', shape: '⬡' },
];

export default function GraphCanvas({ graphData, attackPath, blastRadius, cycles, overlayMode, onNodeSelect, onContextAction }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);

  const buildCy = useCallback(() => {
    if (!containerRef.current || !graphData) return;

    if (cyRef.current) cyRef.current.destroy();

    const elements: cytoscape.ElementDefinition[] = [];
    graphData.nodes.forEach(n => {
      elements.push({
        data: { id: n.id, label: n.label, type: n.type, risk_score: n.risk_score, ...n },
      });
    });
    graphData.edges.forEach(e => {
      elements.push({
        data: { id: e.id || `${e.source}-${e.target}`, source: e.source, target: e.target, relation: e.relation, risk_score: e.risk_score },
      });
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '10px',
            'color': '#ffffff',
            'text-margin-y': 8,
            'text-outline-color': '#0f1117',
            'text-outline-width': 2,
            'border-width': 2,
            'border-color': '#ffffff44',
            'width': (ele: any) => riskToSize(ele.data('risk_score') || 5),
            'height': (ele: any) => riskToSize(ele.data('risk_score') || 5),
            'background-color': (ele: any) => NODE_COLORS[ele.data('type')] || '#8b8fa8',
            'shape': (ele: any) => NODE_SHAPES[ele.data('type')] || 'ellipse',
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
            'width': (ele: any) => riskToWidth(ele.data('risk_score') || 3),
            'line-color': (ele: any) => riskToColor(ele.data('risk_score') || 3),
            'target-arrow-color': (ele: any) => riskToColor(ele.data('risk_score') || 3),
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(relation)',
            'font-size': '8px',
            'color': '#8b8fa8',
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
          style: { 'line-color': '#E24B4A', 'target-arrow-color': '#E24B4A', 'width': 4 } as any,
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
      layout: { name: 'dagre', rankDir: 'TB', nodeSep: 60, rankSep: 80 } as any,
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
  }, [graphData, onNodeSelect]);

  useEffect(() => { buildCy(); }, [buildCy]);

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
      pathNodes.forEach(id => cy.getElementById(id).removeClass('dimmed').addClass('highlighted'));
      attackPath.path.forEach((step: any) => {
        cy.edges().filter((e: any) => e.data('source') === step.from && e.data('target') === step.to)
          .removeClass('dimmed').addClass('highlighted attack-edge');
      });
    }

    if (overlayMode === 'blast' && blastRadius?.zones) {
      cy.elements().addClass('dimmed');
      Object.entries(blastRadius.zones).forEach(([hop, nodes]: [string, any]) => {
        const cls = `blast-${Math.min(parseInt(hop), 3)}`;
        (nodes as string[]).forEach((id: string) => {
          cy.getElementById(id).removeClass('dimmed').addClass(`highlighted ${cls}`);
        });
      });
    }

    if (overlayMode === 'cycle' && cycles?.cycles) {
      cy.elements().addClass('dimmed');
      cycles.cycles.forEach((c: any) => {
        (c.nodes || c.chain || []).forEach((id: string) => {
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

  return (
    <div className="relative w-full h-full bg-background rounded-lg border border-border overflow-hidden">
      <div ref={containerRef} className="w-full h-full" />

      {/* Legend */}
      <div className="absolute bottom-3 left-3 bg-card/90 backdrop-blur border border-border rounded-lg p-3 text-xs space-y-1">
        {LEGEND_ITEMS.map(item => (
          <div key={item.type} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: NODE_COLORS[item.type] }} />
            <span className="text-muted-foreground">{item.shape} {item.label}</span>
          </div>
        ))}
      </div>

      {/* Context menu */}
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
          ].map(item => (
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

      {/* Node sidebar */}
      <NodeSidebar node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  );
}
