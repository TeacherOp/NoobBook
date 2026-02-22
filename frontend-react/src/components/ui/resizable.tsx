import * as ResizablePrimitive from "react-resizable-panels"
import type { ImperativePanelHandle } from "react-resizable-panels"

import { cn } from "@/lib/utils"

const ResizablePanelGroup = ({
  className,
  ...props
}: React.ComponentProps<typeof ResizablePrimitive.PanelGroup>) => (
  <ResizablePrimitive.PanelGroup
    className={cn(
      "flex h-full w-full data-[panel-group-direction=vertical]:flex-col",
      className
    )}
    {...props}
  />
)

const ResizablePanel = ResizablePrimitive.Panel

/**
 * ResizableHandle Component
 * Educational Note: Wide gutter-style handle that creates visual separation between panels.
 * The handle itself IS the gap - matches background color to look like space between cards.
 * Cursor changes on hover to indicate draggable area.
 */
const ResizableHandle = ({
  withHandle,
  className,
  ...props
}: React.ComponentProps<typeof ResizablePrimitive.PanelResizeHandle> & {
  withHandle?: boolean
}) => (
  <ResizablePrimitive.PanelResizeHandle
    className={cn(
      // Wide gutter that acts as visual gap between panels (w-3 = 12px)
      "relative flex w-3 items-center justify-center",
      // Match background color to create "gap" illusion
      "bg-background hover:bg-muted/50 transition-colors cursor-col-resize",
      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
      // Vertical direction support (h-3 = 12px for vertical gaps)
      "data-[panel-group-direction=vertical]:h-3 data-[panel-group-direction=vertical]:w-full data-[panel-group-direction=vertical]:cursor-row-resize",
      className
    )}
    {...props}
  >
    {/* Optional visual indicator - only shows on hover */}
    {withHandle && (
      <div className="h-8 w-1 rounded-full bg-border/0 hover:bg-border/60 transition-colors" />
    )}
  </ResizablePrimitive.PanelResizeHandle>
)

export { ResizablePanelGroup, ResizablePanel, ResizableHandle }
export type { ImperativePanelHandle }
