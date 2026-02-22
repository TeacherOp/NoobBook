import { CircleNotch } from "@phosphor-icons/react"

import { cn } from "src/lib/utils"

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <CircleNotch
      size={16}
      role="status"
      aria-label="Loading"
      className={cn("animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
