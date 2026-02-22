/**
 * FlowDiagramViewer Component
 * Educational Note: Renders Mermaid diagrams with interactive pan/zoom features.
 * Uses the Mermaid.js library to parse and render diagram syntax.
 *
 * Features:
 * - Auto-fit to container on load
 * - Pan with mouse drag
 * - Zoom with scroll wheel or buttons
 * - Fit-to-view reset
 * - Copy syntax and download SVG
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';
import {
  ArrowsOut,
  ArrowsIn,
  Copy,
  Check,
  DownloadSimple,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  ArrowsOutCardinal,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { createLogger } from '@/lib/logger';

const log = createLogger('flow-diagram-viewer');

interface FlowDiagramViewerProps {
  mermaidSyntax: string;
  title?: string;
  description?: string;
  diagramType?: string;
}

// Initialize mermaid with theme configuration
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    // Match app theme colors
    primaryColor: '#3B82F6',
    primaryTextColor: '#1F2937',
    primaryBorderColor: '#2563EB',
    lineColor: '#6B7280',
    secondaryColor: '#8B5CF6',
    tertiaryColor: '#F3F4F6',
    // Flowchart specific
    nodeBorder: '#2563EB',
    clusterBkg: '#F3F4F6',
    clusterBorder: '#D1D5DB',
    // Font
    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
    fontSize: '14px',
  },
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
    padding: 15,
  },
  sequence: {
    diagramMarginX: 50,
    diagramMarginY: 10,
    actorMargin: 50,
    width: 150,
    height: 65,
    boxMargin: 10,
    boxTextMargin: 5,
    noteMargin: 10,
    messageMargin: 35,
  },
});

export const FlowDiagramViewer: React.FC<FlowDiagramViewerProps> = ({
  mermaidSyntax,
  title,
  description,
  diagramType,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);

  // Pan and zoom state
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 });

  // Render the mermaid diagram
  const renderDiagram = useCallback(async () => {
    if (!mermaidSyntax) return;

    try {
      // Generate unique ID for this render
      const id = `mermaid-${Date.now()}`;

      // Render the diagram
      const { svg } = await mermaid.render(id, mermaidSyntax);
      setSvgContent(svg);
      setError(null);

      // Parse SVG dimensions after render
      const parser = new DOMParser();
      const svgDoc = parser.parseFromString(svg, 'image/svg+xml');
      const svgElement = svgDoc.querySelector('svg');
      if (svgElement) {
        const width = parseFloat(svgElement.getAttribute('width') || '0');
        const height = parseFloat(svgElement.getAttribute('height') || '0');
        setSvgDimensions({ width, height });
      }
    } catch (err) {
      log.error({ err }, 'mermaid render failed');
      setError(err instanceof Error ? err.message : 'Failed to render diagram');
    }
  }, [mermaidSyntax]);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  // Auto-fit diagram to container when SVG is ready
  useEffect(() => {
    if (svgContent && containerRef.current && svgDimensions.width > 0) {
      fitToView();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [svgContent, svgDimensions]);

  // Fit diagram to container view
  const fitToView = useCallback(() => {
    if (!containerRef.current || svgDimensions.width === 0) return;

    const container = containerRef.current;
    const containerWidth = container.clientWidth - 40; // Padding
    const containerHeight = container.clientHeight - 40;

    const scaleX = containerWidth / svgDimensions.width;
    const scaleY = containerHeight / svgDimensions.height;
    const newScale = Math.min(scaleX, scaleY, 1.5); // Cap at 150% for readability

    setScale(Math.max(0.1, newScale));
    setPosition({ x: 0, y: 0 });
  }, [svgDimensions]);

  // Mouse wheel zoom - use native event listener to properly prevent default
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheelNative = (e: WheelEvent) => {
      // Prevent browser zoom (pinch) and page scroll
      e.preventDefault();
      e.stopPropagation();

      // For pinch-to-zoom (ctrlKey is true), use smaller delta for finer control
      const isPinch = e.ctrlKey;
      const delta = e.deltaY > 0 ? (isPinch ? 0.95 : 0.9) : (isPinch ? 1.05 : 1.1);

      setScale((prev) => Math.min(Math.max(prev * delta, 0.1), 10));
    };

    // Use passive: false to allow preventDefault
    container.addEventListener('wheel', handleWheelNative, { passive: false });

    return () => {
      container.removeEventListener('wheel', handleWheelNative);
    };
  }, []);

  // Pan handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  }, [position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Copy mermaid syntax to clipboard
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(mermaidSyntax);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      log.error({ err }, 'failed to copy');
    }
  };

  // Download as SVG
  // Educational Note: Mermaid with htmlLabels:true embeds HTML inside <foreignObject>.
  // HTML tags like <br>, <hr>, <img> are not self-closing in HTML5 but must be
  // self-closing in XML/SVG (e.g., <br/>, <hr/>, <img/>). We sanitize before download.
  const handleDownload = () => {
    if (!svgContent) return;

    // Sanitize HTML void elements to be XML-compatible (self-closing)
    // This fixes: "Opening and ending tag mismatch: br line 1 and p"
    // Uses negative lookahead (?![^>]*\/>) to skip already self-closing tags
    let sanitizedSvg = svgContent
      .replace(/<br(?![^>]*\/>)([^>]*)>/gi, '<br$1/>')
      .replace(/<hr(?![^>]*\/>)([^>]*)>/gi, '<hr$1/>')
      .replace(/<img(?![^>]*\/>)([^>]*)>/gi, '<img$1/>')
      .replace(/<input(?![^>]*\/>)([^>]*)>/gi, '<input$1/>')
      .replace(/<meta(?![^>]*\/>)([^>]*)>/gi, '<meta$1/>')
      .replace(/<link(?![^>]*\/>)([^>]*)>/gi, '<link$1/>');

    const blob = new Blob([sanitizedSvg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title?.replace(/\s+/g, '_') || 'diagram'}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Zoom controls
  const handleZoomIn = () => setScale((prev) => Math.min(prev * 1.25, 10));
  const handleZoomOut = () => setScale((prev) => Math.max(prev * 0.8, 0.1));

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <div className="text-red-500 mb-4">Failed to render diagram</div>
        <pre className="text-xs text-muted-foreground bg-muted p-4 rounded-md max-w-full overflow-auto">
          {error}
        </pre>
        <div className="mt-4">
          <p className="text-sm text-muted-foreground mb-2">Mermaid syntax:</p>
          <pre className="text-xs bg-muted p-4 rounded-md max-w-full overflow-auto text-left">
            {mermaidSyntax}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${isFullscreen ? 'fixed inset-0 z-50 bg-background' : ''}`}>
      {/* Header with controls */}
      <div className="flex items-center justify-between p-3 border-b bg-muted/30 flex-shrink-0">
        <div className="flex items-center gap-3">
          {title && (
            <h3 className="text-sm font-medium">{title}</h3>
          )}
          {diagramType && (
            <span className="text-xs px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded-full capitalize">
              {diagramType}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 mr-2 px-2 py-1 bg-muted rounded-md">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={handleZoomOut}
              title="Zoom out"
            >
              <MagnifyingGlassMinus size={16} />
            </Button>
            <button
              onClick={fitToView}
              className="text-xs min-w-[50px] hover:bg-background/50 px-2 py-1 rounded font-medium"
              title="Click to fit to view"
            >
              {Math.round(scale * 100)}%
            </button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={handleZoomIn}
              title="Zoom in"
            >
              <MagnifyingGlassPlus size={16} />
            </Button>
          </div>

          {/* Fit to view */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={fitToView}
            title="Fit to view"
          >
            <ArrowsOutCardinal size={16} />
          </Button>

          {/* Copy syntax */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={handleCopy}
            title="Copy Mermaid syntax"
          >
            {copied ? (
              <Check size={16} className="text-green-600" />
            ) : (
              <Copy size={16} />
            )}
          </Button>

          {/* Download SVG */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={handleDownload}
            title="Download as SVG"
          >
            <DownloadSimple size={16} />
          </Button>

          {/* Fullscreen toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <ArrowsIn size={16} /> : <ArrowsOut size={16} />}
          </Button>
        </div>
      </div>

      {/* Description */}
      {description && (
        <div className="px-3 py-2 text-sm text-muted-foreground bg-muted/20 border-b flex-shrink-0">
          {description}
        </div>
      )}

      {/* Diagram container with pan/zoom */}
      <div
        ref={containerRef}
        className="flex-1 overflow-hidden bg-white relative select-none"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        {svgContent ? (
          <div
            ref={svgContainerRef}
            className="absolute inset-0 flex items-center justify-center"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
              transformOrigin: 'center center',
              transition: isDragging ? 'none' : 'transform 0.1s ease-out',
            }}
          >
            <div
              dangerouslySetInnerHTML={{ __html: svgContent }}
              className="diagram-content"
            />
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
            Loading diagram...
          </div>
        )}

        {/* Pan/zoom hint */}
        <div className="absolute bottom-3 left-3 text-xs text-muted-foreground bg-white/80 px-2 py-1 rounded shadow-sm pointer-events-none">
          Scroll to zoom, drag to pan
        </div>
      </div>
    </div>
  );
};
