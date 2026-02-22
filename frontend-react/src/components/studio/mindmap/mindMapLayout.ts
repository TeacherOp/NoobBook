/**
 * Mind Map Layout Utility
 * Educational Note: Uses dagre for automatic horizontal tree layout.
 * Dagre is a JavaScript library for laying out directed graphs.
 *
 * The layout algorithm:
 * 1. Create a dagre graph with horizontal direction (LR = Left to Right)
 * 2. Add all nodes with their dimensions
 * 3. Add edges based on parent_id relationships
 * 4. Run layout calculation
 * 5. Extract calculated positions for React Flow
 */

import dagre from 'dagre';
import type { Node, Edge } from '@xyflow/react';
import type { MindMapNode } from '@/lib/api/studio';

// Node dimensions based on type
const NODE_DIMENSIONS = {
  root: { width: 180, height: 60 },
  category: { width: 160, height: 50 },
  leaf: { width: 140, height: 44 },
};

// Colors for node types (NotebookLM-inspired)
export const NODE_COLORS = {
  root: {
    background: 'linear-gradient(135deg, #3B82F6, #2563EB)',
    border: '#1D4ED8',
  },
  category: {
    background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)',
    border: '#6D28D9',
  },
  leaf: {
    background: 'linear-gradient(135deg, #14B8A6, #0D9488)',
    border: '#0F766E',
  },
};

/**
 * Convert Claude's mind map nodes to React Flow format with dagre layout
 */
export function calculateMindMapLayout(
  mindMapNodes: MindMapNode[]
): { nodes: Node[]; edges: Edge[] } {
  if (!mindMapNodes || mindMapNodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  // Create dagre graph
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Configure for horizontal layout (Left to Right)
  dagreGraph.setGraph({
    rankdir: 'LR',      // Left to Right
    nodesep: 40,        // Vertical spacing between nodes
    ranksep: 100,       // Horizontal spacing between ranks
    marginx: 20,
    marginy: 20,
  });

  // Add nodes to dagre
  mindMapNodes.forEach((node) => {
    const dimensions = NODE_DIMENSIONS[node.node_type] || NODE_DIMENSIONS.leaf;
    dagreGraph.setNode(node.id, {
      width: dimensions.width,
      height: dimensions.height,
    });
  });

  // Add edges based on parent_id relationships
  mindMapNodes.forEach((node) => {
    if (node.parent_id) {
      dagreGraph.setEdge(node.parent_id, node.id);
    }
  });

  // Run the layout
  dagre.layout(dagreGraph);

  // Convert to React Flow nodes
  const rfNodes: Node[] = mindMapNodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const dimensions = NODE_DIMENSIONS[node.node_type] || NODE_DIMENSIONS.leaf;

    return {
      id: node.id,
      type: 'mindMapNode', // Custom node type
      position: {
        // Dagre gives center position, React Flow uses top-left
        x: nodeWithPosition.x - dimensions.width / 2,
        y: nodeWithPosition.y - dimensions.height / 2,
      },
      data: {
        label: node.label,
        description: node.description,
        nodeType: node.node_type,
      },
    };
  });

  // Create edges
  const rfEdges: Edge[] = mindMapNodes
    .filter((node) => node.parent_id)
    .map((node) => ({
      id: `edge-${node.parent_id}-${node.id}`,
      source: node.parent_id!,
      target: node.id,
      type: 'smoothstep',
      style: {
        stroke: '#94A3B8',
        strokeWidth: 2,
      },
      animated: false,
    }));

  return { nodes: rfNodes, edges: rfEdges };
}

/**
 * Get the bounding box of all nodes for fit view calculation
 */
export function getNodesBounds(nodes: Node[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  if (nodes.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  nodes.forEach((node) => {
    const dimensions = NODE_DIMENSIONS[node.data.nodeType as keyof typeof NODE_DIMENSIONS] || NODE_DIMENSIONS.leaf;
    minX = Math.min(minX, node.position.x);
    minY = Math.min(minY, node.position.y);
    maxX = Math.max(maxX, node.position.x + dimensions.width);
    maxY = Math.max(maxY, node.position.y + dimensions.height);
  });

  return { minX, minY, maxX, maxY };
}
