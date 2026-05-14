---
name: frontend-design
description: Distinctive, production-grade frontend interfaces with high design quality. Always loaded into the component agent's system prompt so generated components avoid generic AI-slop aesthetics.
source: claude-plugins-official/plugins/frontend-design (Anthropic)
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work — the key is intentionality, not intensity.

Then implement working code (HTML / CSS / JS) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial when no brand font is specified; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font. (If Brand Guidelines below mandate a specific font, that wins — brand always overrides creative freedom.)
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (when free to choose: Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: you are capable of extraordinary creative work. Don't hold back — show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Iconography (project-specific override)

NEVER use emoji as icons in component HTML. Use **real icons**:

- **Preferred**: inline SVG icons (zero network roundtrip, fully self-contained, themeable via `currentColor` / CSS variables, smallest visual footprint).
- **Acceptable**: Font Awesome 6 via the existing CDN `<link>` already permitted in the component prompt's HTML structure.
- **Forbidden**: emoji characters (`🚀`, `⚡`, `📦`, etc.) standing in for icons. Emoji render inconsistently across OSes, can't be themed, and look unprofessional.

When in doubt, ship inline SVG.

## Imagery (project-specific override)

Components must be fully self-contained — no external image fetches. For any raster imagery the component needs (illustrations, decorative graphics, pattern fills):

- **Preferred**: inline SVG (drawn directly in markup). Crisp at any size, themeable, no extra bytes for the network.
- **Acceptable**: tiny inline base64 `data:image/...;base64,...` URIs for small raster decorations under ~20 KB. The BRAND_LOGO placeholder is already injected as base64 post-generation; follow the same pattern for any other raster you absolutely need.
- **Forbidden**: `<img src="https://images.unsplash.com/…">`, `<img src="https://via.placeholder.com/…">`, or any external HTTP image URL. The component preview iframe runs in a sandbox and external image hosts can fail, slow down the preview, or pull from servers the user doesn't control.

If you'd otherwise reach for a hero photograph from a stock site, **draw it as inline SVG instead** — abstract shapes, gradient meshes, geometric patterns. Lean into the SKILL's "creative backgrounds and textures" guidance.
