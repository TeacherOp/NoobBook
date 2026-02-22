import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Primary solid - Main CTA buttons (amber)
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        // Destructive - Delete/danger actions
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        // Outline - Subtle outline, standard shadcn style
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        // Soft - Cream background with visible border (most common secondary action)
        // Use this for: Choose Files, Memory, Brand Kit, Project Settings, etc.
        soft:
          "bg-[#e8e7e4] border border-stone-300 text-foreground hover:bg-[#dcdbd8] active:bg-[#d0cfcc]",
        // Brand - Primary border with light amber background (highlighted secondary)
        // Use this for: Important but not primary actions
        brand:
          "border-2 border-primary bg-primary/5 text-primary hover:bg-primary/10 active:bg-primary/15",
        // Secondary - Very subtle background
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        // Ghost - No background until hover
        ghost: "hover:bg-accent hover:text-accent-foreground",
        // Link - Text with underline on hover
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
