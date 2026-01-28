/**
 * Mind Map Viewer Component
 * Educational Note: Uses React Flow to render an interactive mind map.
 *
 * Features:
 * - Horizontal tree layout via dagre
 * - Collapsible nodes (start collapsed, click to expand)
 * - Custom node styling by type (root/category/leaf)
 * - Pan and zoom controls with toolbar
 * - Expand/collapse all functionality
 */

import { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { calculateMindMapLayout, NODE_COLORS } from './mindMapLayout';
import type { MindMapNode } from '@/lib/api/studio';
import { Button } from '@/components/ui/button';
import { Plus, Minus, MagnifyingGlassPlus, MagnifyingGlassMinus, ArrowsOutSimple, CaretRight } from '@phosphor-icons/react';

interface MindMapNodeData {
  label: string;
  description?: string;
  nodeType: 'root' | 'category' | 'leaf';
  hasChildren: boolean;
  isExpanded: boolean;
  childCount: number;
  onToggleExpand: (nodeId: string) => void;
  nodeId: string;
}

// Custom node component with expand/collapse
function MindMapNodeComponent({ data }: { data: MindMapNodeData }) {
  const nodeType = data.nodeType;
  const colors = NODE_COLORS[nodeType] || NODE_COLORS.leaf;
  const hasChildren = data.hasChildren;
  const isExpanded = data.isExpanded;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren && data.onToggleExpand) {
      data.onToggleExpand(data.nodeId);
    }
  };

  const nodeStyles: React.CSSProperties = {
    background: colors.background,
    border: `2px solid ${colors.border}`,
    borderRadius: nodeType === 'root' ? '12px' : nodeType === 'category' ? '10px' : '8px',
    padding: nodeType === 'root' ? '12px 20px' : nodeType === 'category' ? '8px 16px' : '6px 12px',
    color: 'white',
    fontWeight: nodeType === 'root' ? 600 : nodeType === 'category' ? 500 : 400,
    fontSize: nodeType === 'root' ? '14px' : nodeType === 'category' ? '13px' : '12px',
    cursor: hasChildren ? 'pointer' : 'default',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    transition: 'transform 0.2s, box-shadow 0.2s',
    maxWidth: nodeType === 'root' ? '200px' : nodeType === 'category' ? '180px' : '160px',
    textAlign: 'center',
    wordBreak: 'break-word',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  return (
    <div
      style={nodeStyles}
      className={hasChildren ? 'hover:scale-105 hover:shadow-lg' : ''}
      onClick={handleClick}
      title={data.description || data.label}
    >
      {/* Input handle (left side) - for non-root nodes */}
      {nodeType !== 'root' && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: colors.border,
            border: 'none',
            width: 8,
            height: 8,
          }}
        />
      )}

      {/* Node label */}
      <span className="flex-1">{data.label as string}</span>

      {/* Expand/collapse indicator */}
      {hasChildren && (
        <span
          className="flex items-center justify-center transition-transform duration-200"
          style={{
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
            opacity: 0.8,
          }}
        >
          <CaretRight size={14} weight="bold" />
        </span>
      )}

      {/* Child count badge when collapsed */}
      {hasChildren && !isExpanded && data.childCount > 0 && (
        <span
          className="absolute -right-2 -top-2 bg-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center shadow-sm"
          style={{ color: colors.border }}
        >
          {data.childCount}
        </span>
      )}

      {/* Output handle (right side) */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: colors.border,
          border: 'none',
          width: 8,
          height: 8,
        }}
      />
    </div>
  );
}

// Define custom node types - use 'any' to avoid React Flow type complexity
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nodeTypes: any = {
  mindMapNode: MindMapNodeComponent,
};

interface MindMapViewerProps {
  nodes: MindMapNode[];
  topicSummary?: string | null;
}

// Inner component that uses useReactFlow
function MindMapViewerInner({ nodes: mindMapNodes }: MindMapViewerProps) {
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  // Build parent-child relationships
  const { childrenMap, rootId } = useMemo(() => {
    const map = new Map<string, string[]>();
    let root: string | null = null;

    mindMapNodes.forEach((node) => {
      if (node.parent_id === null) {
        root = node.id;
      } else {
        const children = map.get(node.parent_id) || [];
        children.push(node.id);
        map.set(node.parent_id, children);
      }
    });

    return { childrenMap: map, rootId: root };
  }, [mindMapNodes]);

  // Get all descendants of a node
  const getDescendants = useCallback((nodeId: string): string[] => {
    const children = childrenMap.get(nodeId) || [];
    let descendants = [...children];
    children.forEach((childId) => {
      descendants = [...descendants, ...getDescendants(childId)];
    });
    return descendants;
  }, [childrenMap]);

  // Count direct children
  const getChildCount = useCallback((nodeId: string): number => {
    return (childrenMap.get(nodeId) || []).length;
  }, [childrenMap]);

  // Track expanded nodes - start with only root expanded
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() => {
    return new Set(rootId ? [rootId] : []);
  });

  // Toggle expand/collapse
  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        // Collapse: remove this node and all its descendants
        next.delete(nodeId);
        getDescendants(nodeId).forEach((id) => next.delete(id));
      } else {
        // Expand: add this node
        next.add(nodeId);
      }
      return next;
    });
  }, [getDescendants]);

  // Expand all nodes
  const expandAll = useCallback(() => {
    const allIds = new Set(mindMapNodes.map((n) => n.id));
    setExpandedNodes(allIds);
  }, [mindMapNodes]);

  // Collapse all (show only root)
  const collapseAll = useCallback(() => {
    setExpandedNodes(new Set(rootId ? [rootId] : []));
  }, [rootId]);

  // Determine which nodes are visible
  const visibleNodeIds = useMemo(() => {
    const visible = new Set<string>();

    // Root is always visible
    if (rootId) {
      visible.add(rootId);
    }

    // A node is visible if its parent is expanded
    mindMapNodes.forEach((node) => {
      if (node.parent_id === null) {
        visible.add(node.id); // Root
      } else if (expandedNodes.has(node.parent_id)) {
        visible.add(node.id);
      }
    });

    return visible;
  }, [mindMapNodes, expandedNodes, rootId]);

  // Filter nodes to only visible ones
  const visibleMindMapNodes = useMemo(() => {
    return mindMapNodes.filter((n) => visibleNodeIds.has(n.id));
  }, [mindMapNodes, visibleNodeIds]);

  // Calculate layout for visible nodes only
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => calculateMindMapLayout(visibleMindMapNodes),
    [visibleMindMapNodes]
  );

  // Add expand/collapse data to nodes
  const nodesWithHandlers = useMemo(() => {
    return layoutNodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        hasChildren: childrenMap.has(node.id),
        isExpanded: expandedNodes.has(node.id),
        childCount: getChildCount(node.id),
        onToggleExpand: toggleExpand,
        nodeId: node.id,
      },
    }));
  }, [layoutNodes, childrenMap, expandedNodes, getChildCount, toggleExpand]);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState(nodesWithHandlers);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Update nodes when layout changes
  useEffect(() => {
    setNodes(nodesWithHandlers);
    setEdges(layoutEdges);
  }, [nodesWithHandlers, layoutEdges, setNodes, setEdges]);

  // Fit view only on initial load (when rootId changes)
  // Don't reset zoom on expand/collapse - let user control zoom
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.2, duration: 300 });
    }, 50);
    return () => clearTimeout(timer);
  }, [rootId, fitView]); // Only depends on rootId, not visibleNodeIds.size

  // Selected node for details panel
  const [selectedNode, setSelectedNode] = useState<MindMapNode | null>(null);

  // Handle node click for details
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      const mindMapNode = mindMapNodes.find((n) => n.id === node.id);
      if (mindMapNode) {
        setSelectedNode(mindMapNode);
      }
    },
    [mindMapNodes]
  );

  if (mindMapNodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No mind map data available
      </div>
    );
  }

  const totalNodes = mindMapNodes.length;
  const visibleCount = visibleNodeIds.size;

  return (
    <div className="w-full h-full flex flex-col">
      {/* Toolbar */}
      <div className="px-4 py-2 bg-muted/30 border-b flex items-center justify-between gap-2 flex-shrink-0">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={expandAll}
            className="h-7 text-xs gap-1"
          >
            <Plus size={14} />
            Expand All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={collapseAll}
            className="h-7 text-xs gap-1"
          >
            <Minus size={14} />
            Collapse
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => zoomOut()}
            className="h-7 w-7 p-0"
            title="Zoom out"
          >
            <MagnifyingGlassMinus size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => zoomIn()}
            className="h-7 w-7 p-0"
            title="Zoom in"
          >
            <MagnifyingGlassPlus size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fitView({ padding: 0.2, duration: 300 })}
            className="h-7 w-7 p-0"
            title="Fit view"
          >
            <ArrowsOutSimple size={16} />
          </Button>
        </div>
      </div>

      {/* React Flow Container */}
      <div className="flex-1 relative min-h-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{
            padding: 0.2,
            minZoom: 0.3,
            maxZoom: 1.5,
          }}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          className="bg-background"
          panOnScroll
          zoomOnScroll
          panOnDrag
        >
          <Controls
            position="bottom-right"
            showInteractive={false}
            showZoom={false}
            showFitView={false}
            className="bg-background border rounded-lg shadow-sm"
          />
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#e5e7eb"
          />
        </ReactFlow>
      </div>

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="px-4 py-3 bg-muted/50 border-t flex-shrink-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-sm">{selectedNode.label}</h4>
              {selectedNode.description && (
                <p className="text-xs text-muted-foreground mt-1">
                  {selectedNode.description}
                </p>
              )}
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-muted-foreground hover:text-foreground text-lg leading-none flex-shrink-0"
            >
              x
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-muted/30 border-t text-xs text-muted-foreground flex items-center justify-between flex-shrink-0">
        <span>
          {visibleCount} of {totalNodes} nodes visible
        </span>
        <span className="text-[10px]">
          Click nodes to expand. Scroll to zoom. Drag to pan.
        </span>
      </div>
    </div>
  );
}

// Wrapper with ReactFlowProvider
export function MindMapViewer(props: MindMapViewerProps) {
  return (
    <ReactFlowProvider>
      <MindMapViewerInner {...props} />
    </ReactFlowProvider>
  );
}
