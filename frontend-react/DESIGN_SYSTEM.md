# NoobBook Design System

A comprehensive design system reference for maintaining visual consistency across NoobBook projects.

## Quick Reference

| Aspect | Value |
|--------|-------|
| **Primary Color** | Amber-600 `#D97706` |
| **Text Color** | Stone-800 `#292524` |
| **Background** | Warm Cream (tinted stone-50) |
| **Card/Surface** | Pure White `#FFFFFF` |
| **Border Radius** | 8px base |
| **Spacing Unit** | 4px (Tailwind scale) |
| **Font Family** | System UI stack |
| **Icon Library** | Phosphor Icons |
| **Component Library** | shadcn/ui + Radix UI |
| **CSS Framework** | Tailwind CSS |

---

## 1. Color Palette

**Theme:** Stone + Amber (warm, readable, learning-focused)

### CSS Variables

```css
:root {
  /* Background & Surface */
  --background: 40 15% 95%;           /* Warm cream/beige */
  --card: 0 0% 100%;                  /* Pure white */
  --popover: 0 0% 100%;               /* White popovers */

  /* Text Colors */
  --foreground: 12 10% 15%;           /* Stone-800: warm dark text */
  --card-foreground: 12 10% 15%;      /* Stone-800 on cards */
  --muted-foreground: 25 6% 45%;      /* Stone-500: secondary text */

  /* Interactive Colors */
  --primary: 32 95% 44%;              /* Amber-600: main action color */
  --primary-foreground: 0 0% 100%;    /* White text on primary */
  --secondary: 60 5% 96%;             /* Stone-100: subtle background */
  --accent: 48 96% 89%;               /* Amber-100: hover states */
  --accent-foreground: 32 95% 38%;    /* Amber-700: text on accent */

  /* Semantic Colors */
  --destructive: 0 72% 51%;           /* Red-500: warnings/delete */
  --destructive-foreground: 0 0% 100%;

  /* Structural Colors */
  --border: 30 6% 90%;                /* Stone-200: subtle borders */
  --input: 30 6% 90%;                 /* Stone-200: input borders */
  --ring: 32 95% 44%;                 /* Amber-600: focus ring */
  --muted: 60 5% 96%;                 /* Stone-100 */

  /* Border Radius */
  --radius: 0.5rem;                   /* 8px base */
}
```

### Tailwind Color Classes

| Purpose | Class | Hex |
|---------|-------|-----|
| Primary Button | `bg-primary` | `#D97706` (amber-600) |
| Primary Text | `text-primary` | `#D97706` |
| Dark Text | `text-foreground` | Stone-800 |
| Muted Text | `text-muted-foreground` | Stone-500 |
| Background | `bg-background` | Warm cream |
| Card | `bg-card` | White |
| Hover State | `bg-accent` | Amber-100 |
| Border | `border-border` | Stone-200 |

---

## 2. Typography

### Font Stack

```css
font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
```

### Text Sizes

| Element | Size | Weight | Tailwind Class |
|---------|------|--------|----------------|
| H1 | 18px | Bold | `text-lg font-bold` |
| H2 | 16px | Bold | `text-base font-bold` |
| H3 | 14px | Bold | `text-sm font-bold` |
| Card Title | 20px | Semibold | `text-2xl font-semibold` |
| Button | 14px | Medium | `text-sm font-medium` |
| Label | 14px | Medium | `text-sm font-medium` |
| Body | 14px | Regular | `text-sm` |
| Code | 12px | Mono | `text-xs font-mono` |
| Small | 12px | Regular | `text-xs` |

---

## 3. Spacing

All spacing uses Tailwind's 4px increments.

### Common Patterns

```
Cards:
  - Header: p-6 (24px) with space-y-1.5 between children
  - Content: p-6 pt-0 (24px sides, 0 top)
  - Footer: p-6 pt-0

Buttons:
  - Default: px-4 py-2 (16px x 8px)
  - Small: px-3 (12px)
  - Large: px-8 (32px)

Inputs:
  - Padding: px-3 py-2 (12px x 8px)
  - Height: h-10 (40px)

Gaps:
  - Flex items: gap-2 to gap-4 (8px to 16px)
  - List items: space-y-1 or space-y-2 (4px or 8px)
  - Sections: space-y-4 (16px)

Page Container:
  - Padding: px-4 (16px)
  - Max width: 1400px at 2xl breakpoint
```

---

## 4. Border Radius

| Size | Value | Usage |
|------|-------|-------|
| `rounded-sm` | 4px | Tabs, small components |
| `rounded-md` | 8px | Inputs, buttons, selects |
| `rounded-lg` | 8px | Cards, alerts |
| `rounded-xl` | 12px | Panel containers |
| `rounded-2xl` | 16px | Chat bubbles |
| `rounded-full` | 9999px | Badges, avatars |

### Special Patterns

```
Chat Bubble (User):    rounded-2xl rounded-tr-sm
Chat Bubble (AI):      rounded-2xl rounded-tl-sm
Cards:                 rounded-lg
Buttons:               rounded-md
Badges:                rounded-full
Avatar:                rounded-full
```

---

## 5. Shadows & Borders

### Shadows

Minimal shadow usage - clean, flat design.

```
Cards: shadow-sm (subtle)
```

### Borders

```
Default:     border (1px solid border-input)
Color:       Stone-200 (--border)
Focus Ring:  ring-2 ring-ring ring-offset-2 (amber-600)
```

---

## 6. Components

### Button Variants

```tsx
Variants:
- default:     bg-primary text-primary-foreground hover:bg-primary/90
               → Primary CTA, solid amber background
- soft:        bg-[#e8e7e4] border-stone-300 hover:bg-[#dcdbd8]
               → Most common secondary action (cream bg, visible border)
               → Use for: Choose Files, Memory, Brand Kit, Project Settings, etc.
- brand:       border-2 border-primary bg-primary/5 text-primary hover:bg-primary/10
               → Highlighted secondary (amber border, light amber bg)
- destructive: bg-destructive text-destructive-foreground hover:bg-destructive/90
               → Delete/danger actions
- outline:     border border-input bg-background hover:bg-accent
               → Subtle outline (use sparingly)
- secondary:   bg-secondary text-secondary-foreground hover:bg-secondary/80
               → Very subtle background
- ghost:       hover:bg-accent hover:text-accent-foreground
               → No background until hover
- link:        text-primary underline-offset-4 hover:underline
               → Text with underline

When to use which:
- default:  Primary page action (Create, Save, Submit)
- soft:     Most buttons - visible, clickable, not overwhelming
- brand:    Important but not primary (Upgrade, Try Feature)
- outline:  Use sparingly - very subtle
- ghost:    Icon-only buttons, menu items
- link:     Inline text links

Sizes:
- default:     h-10 px-4 py-2
- sm:          h-9 rounded-md px-3
- lg:          h-11 rounded-md px-8
- icon:        h-10 w-10
```

### Badge Variants

```tsx
- default:     bg-primary text-primary-foreground
- secondary:   bg-secondary text-secondary-foreground
- destructive: bg-destructive text-destructive-foreground
- outline:     border-only, no background

All badges: rounded-full px-2.5 py-0.5 text-xs font-semibold
```

### Input Pattern

```tsx
h-10
border border-input
rounded-md
px-3 py-2
focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
placeholder:text-muted-foreground
disabled:cursor-not-allowed disabled:opacity-50
```

---

## 7. Icons

**Library:** Phosphor Icons (`@phosphor-icons/react`)

### Common Icons

| Category | Icons |
|----------|-------|
| Navigation | `CaretLeft`, `CaretRight`, `ArrowLeft`, `DotsThreeVertical` |
| Content | `FileText`, `BookOpen`, `Ghost`, `Sparkle`, `Brain` |
| Actions | `Plus`, `Trash`, `Gear`, `FolderOpen` |
| Loading | `CircleNotch` (with `animate-spin`) |
| Chat | `User`, `Robot` |
| Media | `Microphone`, `PaperPlaneTilt` |
| Social | `GithubLogo`, `YoutubeLogo` |
| Status | `Warning`, `CircleNotch` |

### Icon Sizes

- 12px, 16px, 18px, 20px, 24px, 32px
- Use `size={N}` prop

### Icon in Button Pattern

```tsx
<Button>
  <Plus size={16} />
  <span>Add Item</span>
</Button>

// Container: gap-2 for spacing
// Icons: [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0
```

---

## 8. Layout Patterns

### Responsive Breakpoints

| Breakpoint | Width |
|------------|-------|
| `sm` | 640px |
| `md` | 768px |
| `lg` | 1024px |
| `xl` | 1280px |
| `2xl` | 1400px |

### 3-Panel Layout

```
┌─────────────────────────────────────────┐
│          Header                         │  h-14
├─────────────────────────────────────────┤
│ ┌─────┬───────────────┬─────┐          │
│ │Left │    Center     │Right│          │  flex-1
│ │ 20% │     55%       │ 25% │          │  rounded-xl
│ └─────┴───────────────┴─────┘          │
├─────────────────────────────────────────┤
│  Footer                                 │  py-2
└─────────────────────────────────────────┘

Panels: bg-card (white)
Gaps: bg-background (cream) creates separation
Container: px-3 pb-2
```

### Chat Message Layout

```tsx
// User Message (right-aligned)
<div className="flex justify-end">
  <div className="max-w-[80%] min-w-0 flex gap-3">
    <div className="bg-primary rounded-2xl rounded-tr-sm px-4 py-2">
      {message}
    </div>
    <Avatar className="h-8 w-8 rounded-full bg-primary/10" />
  </div>
</div>

// AI Message (left-aligned)
<div className="flex justify-start">
  <div className="max-w-[85%] min-w-0 flex gap-3">
    <Avatar className="h-8 w-8 rounded-full bg-primary" />
    <div className="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3">
      {message}
    </div>
  </div>
</div>
```

---

## 9. Animations

### Keyframes

```javascript
'accordion-down': {
  from: { height: '0' },
  to: { height: 'var(--radix-accordion-content-height)' }
}

'accordion-up': {
  from: { height: 'var(--radix-accordion-content-height)' },
  to: { height: '0' }
}
```

### Animation Classes

| Animation | Usage |
|-----------|-------|
| `animate-spin` | Loading spinners (CircleNotch) |
| `animate-pulse` | Skeleton loaders |
| `accordion-down` | Expanding content (0.2s ease-out) |
| `accordion-up` | Collapsing content (0.2s ease-out) |

### Transitions

```
Buttons:      transition-colors
Links:        transition-colors
Scroll:       behavior: 'smooth' (JS)
Focus:        instant (no transition)
```

---

## 10. Markdown / Code Blocks

```tsx
// Inline code
className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono"

// Code block
className="my-2 overflow-x-auto max-w-full !bg-stone-900 !text-stone-100 p-3 rounded-lg"

// Blockquote
className="border-l-2 border-primary/50 pl-3 italic text-muted-foreground my-2"

// Link
className="text-primary underline hover:no-underline break-all"

// Table
className="min-w-full text-sm border-collapse border border-border rounded-lg"
```

---

## 11. Interactive States

### Button States

```
Default:   Solid background
Hover:     bg-primary/90 (reduced opacity)
Active:    Handled by Radix UI
Disabled:  opacity-50 pointer-events-none
Focus:     ring-2 ring-ring ring-offset-2
```

### Input States

```
Empty:       border-input (stone-200)
Focus:       ring-2 ring-ring ring-offset-2
Placeholder: text-muted-foreground
Disabled:    opacity-50 cursor-not-allowed
```

---

## 12. Empty States & Loading

### Skeleton

```tsx
className="rounded-md bg-muted animate-pulse"
```

### Loading Spinner

```tsx
<CircleNotch className="animate-spin text-muted-foreground" size={24} />
```

### Empty State Pattern

```tsx
<div className="flex flex-col items-center justify-center h-full gap-4">
  <Icon size={48} className="text-muted-foreground" />
  <p className="text-muted-foreground">No items yet</p>
  <Button>Add First Item</Button>
</div>
```

---

## 13. Accessibility

- Focus rings: 2px with offset on all interactive elements
- ARIA: Provided by Radix UI primitives
- Keyboard nav: Tab, Enter, Space, Arrow keys
- Color contrast: WCAG AA compliant
- Focus visible: `focus-visible:` utilities for keyboard-only focus

---

## Dependencies

```json
{
  "@phosphor-icons/react": "^2.x",
  "@radix-ui/react-*": "various",
  "class-variance-authority": "^0.7.x",
  "clsx": "^2.x",
  "tailwind-merge": "^2.x",
  "tailwindcss": "^3.4.x",
  "tailwindcss-animate": "^1.0.x"
}
```

---

## Utility Function

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

---

## Setup for New Project

1. Install Tailwind CSS and configure with the CSS variables above
2. Install dependencies: `@phosphor-icons/react`, `class-variance-authority`, `clsx`, `tailwind-merge`, `tailwindcss-animate`
3. Add shadcn/ui: `npx shadcn@latest init`
4. Copy the CSS variables to your `globals.css` or `index.css`
5. Use the `cn()` utility for conditional class merging
