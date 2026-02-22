import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Utility function for merging Tailwind CSS classes.
 * Educational Note: This function combines clsx (for conditional classes)
 * and tailwind-merge (to handle conflicts in Tailwind classes).
 * This is essential for shadcn/ui components to work properly.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}