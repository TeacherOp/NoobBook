# Frontend Migration Plan: React → Vue 3

## Context

NoobBook's frontend is React 19 + Tailwind + shadcn/ui (Radix). The Attest Design System Storybook (https://design-system.attest.tech/) is built on Vue 3 + Vite. Migrating the frontend to Vue 3 enables direct use of Attest's component library and aligns the tech stack with the design system's native framework.

### Current Frontend Stats
- **185 component files** (.tsx)
- **54 shadcn/ui components** (Radix UI primitives)
- **131 feature components** (dashboard, chat, sources, studio, settings, auth)
- **2 routes** (`/` dashboard, `/projects/:projectId` workspace)
- **2 context providers** (Auth, Studio)
- **3 custom hooks** (useAuth, useVoiceRecording, useIsMobile)
- **31 API service files** (axios-based, framework-agnostic)
- **48 npm dependencies** (~20 React-specific, ~28 framework-agnostic)

---

## Phase 1: Project Scaffolding & Core Infrastructure

### Step 1.1: Initialize Vue 3 project alongside React
Create a new `frontend-vue/` directory (parallel to existing `frontend/`) to allow incremental migration without breaking the working app.

```
frontend-vue/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts
│   ├── composables/        # Vue equivalent of hooks
│   ├── components/
│   │   └── ui/             # shadcn-vue components
│   ├── lib/                # Copy from React (framework-agnostic)
│   │   ├── api/            # Reuse as-is
│   │   ├── auth/           # Reuse as-is
│   │   ├── logger.ts       # Reuse as-is
│   │   ├── utils.ts        # Reuse as-is (cn() works in Vue)
│   │   └── citations.ts    # Reuse as-is
│   ├── assets/
│   └── index.css           # Reuse with design system tokens
├── package.json
├── vite.config.ts
├── tailwind.config.js      # Reuse from React
├── tsconfig.json
└── components.json         # shadcn-vue config
```

**Key files to modify:**
- `vite.config.ts` — Replace `@vitejs/plugin-react` with `@vitejs/plugin-vue`
- `tsconfig.json` — Remove `jsx: react-jsx`, add Vue SFC support
- `package.json` — New dependencies listed in Step 1.2

### Step 1.2: Install Vue 3 dependencies

**Replace (React-specific → Vue equivalent):**

| React Dependency | Vue 3 Replacement |
|---|---|
| `react`, `react-dom` | `vue` |
| `@vitejs/plugin-react` | `@vitejs/plugin-vue` |
| `react-router-dom` | `vue-router@4` |
| `react-hook-form` + `@hookform/resolvers` | `vee-validate` + `@vee-validate/zod` |
| `@radix-ui/*` (12 packages) | `radix-vue` (single package) |
| `react-resizable-panels` | `vue-resizable-panels` or custom CSS Grid |
| `embla-carousel-react` | `embla-carousel-vue` |
| `react-markdown` | `vue-markdown-render` or `markdown-it` + `v-html` |
| `react-day-picker` | Built into shadcn-vue Calendar |
| `@xyflow/react` | `@vue-flow/core` |
| `@excalidraw/excalidraw` | Keep via iframe embed (React-only lib) |
| `@elevenlabs/react` | Direct WebSocket (already custom in useVoiceRecording) |
| `next-themes` | `@vueuse/core` useDark() |
| `sonner` | `vue-sonner` |
| `cmdk` | Built into shadcn-vue Command |
| `vaul` | `vaul-vue` |
| `input-otp` | `vue-input-otp` |
| `eslint-plugin-react-hooks` | `eslint-plugin-vue` |
| `eslint-plugin-react-refresh` | Remove (not needed) |

**Keep unchanged (framework-agnostic):**
- `axios`, `zod`, `date-fns`, `pino`, `mermaid`, `dagre`
- `recharts` → Replace with `vue-chartjs` + `chart.js` (recharts is React-only)
- `tailwindcss`, `tailwind-merge`, `clsx`, `class-variance-authority`, `tailwindcss-animate`
- `@phosphor-icons/react` → `@phosphor-icons/vue`
- `autoprefixer`, `postcss`

### Step 1.3: Set up Vue Router

**File**: `frontend-vue/src/router/index.ts`

Current React routes map directly:

```
React Route                          → Vue Route
Route path="/projects/:projectId"    → { path: '/projects/:projectId', component: ProjectWorkspace }
Route path="*"                       → { path: '/:pathMatch(.*)*', component: Dashboard }
```

Only 2 routes — simple flat routing, no nested routes.

### Step 1.4: Copy framework-agnostic code

These files can be copied directly from `frontend/src/lib/` with zero changes:
- `lib/api/client.ts` — Axios instance, interceptors, auth headers
- `lib/api/auth.ts`, `projects.ts`, `chats.ts`, `sources.ts`, `settings.ts`, `brand.ts`
- `lib/api/studio/` — All 18 studio API files
- `lib/auth/session.ts` — localStorage token management
- `lib/logger.ts` — Pino logger
- `lib/utils.ts` — `cn()` utility (clsx + tailwind-merge)
- `lib/citations.ts` — Citation parsing
- `lib/exportChatMarkdown.ts` — Chat markdown export

---

## Phase 2: Convert React Patterns → Vue 3 Composition API

### Step 2.1: Convert Context providers to composables

**AuthContext → `composables/useAuth.ts`**

| React Pattern | Vue 3 Equivalent |
|---|---|
| `createContext()` + `Provider` | `provide()` / `inject()` or Pinia store |
| `useState` | `ref()` |
| `useEffect(() => {}, [])` | `onMounted()` |
| `useCallback` | Plain function (no memoization needed in Vue) |

**Current file**: `frontend/src/hooks/useAuth.tsx`
**New file**: `frontend-vue/src/composables/useAuth.ts`

The auth composable wraps: `user`, `loading`, `login()`, `signup()`, `logout()`

**StudioContext → `composables/useStudio.ts`**

| React Pattern | Vue 3 Equivalent |
|---|---|
| `useMemo(() => new Set(...), [signals])` | `computed(() => new Set(...))` |
| `useState<Map>(() => new Map())` | `ref(new Map())` or `reactive(new Map())` |
| `useCallback` handlers | Plain functions (Vue's reactivity doesn't re-create) |

**Current file**: `frontend/src/components/studio/StudioContext.tsx`
**New file**: `frontend-vue/src/composables/useStudio.ts`

### Step 2.2: Convert custom hooks to composables

| React Hook | Vue Composable | Complexity |
|---|---|---|
| `useAuth()` | `useAuth()` | Low — provide/inject pattern |
| `useVoiceRecording()` | `useVoiceRecording()` | Medium — WebSocket + AudioWorklet |
| `useIsMobile()` | `useIsMobile()` or `@vueuse/core` `useMediaQuery` | Trivial — use VueUse |

**useVoiceRecording** is the most complex — it manages:
- WebSocket connection to ElevenLabs
- AudioWorklet for PCM encoding
- Partial/committed transcript state

The WebSocket and AudioWorklet code is vanilla JS — only the reactive state wrapper changes.

### Step 2.3: React state patterns → Vue reactivity

Global pattern conversion for all 131 feature components:

| React | Vue 3 | Notes |
|---|---|---|
| `useState(initial)` | `ref(initial)` | Use `.value` in script, auto-unwrap in template |
| `useState<T[]>([])` | `ref<T[]>([])` | Same |
| `useEffect(() => { fetch() }, [])` | `onMounted(async () => { await fetch() })` | Mount-only effects |
| `useEffect(() => {}, [dep])` | `watch(dep, () => {})` | Dependency-triggered effects |
| `useEffect(() => { return cleanup }, [])` | `onMounted()` + `onUnmounted()` | Lifecycle cleanup |
| `useMemo(() => compute, [deps])` | `computed(() => compute)` | Auto-tracked deps |
| `useCallback(fn, [deps])` | Plain function | Vue doesn't re-create on render |
| `useRef(null)` | `ref(null)` or `useTemplateRef()` | Template refs for DOM |
| `props.onChange(val)` | `emit('change', val)` | Events instead of callback props |
| `{condition && <Component />}` | `<Component v-if="condition" />` | Conditional rendering |
| `{items.map(i => <Item key={i.id} />)}` | `<Item v-for="i in items" :key="i.id" />` | List rendering |
| `className={cn(...)}` | `:class="cn(...)"` | Dynamic classes |

---

## Phase 3: UI Component Library (shadcn-vue)

### Step 3.1: Install shadcn-vue

shadcn-vue (https://www.shadcn-vue.com/) is the official Vue port of shadcn/ui. It uses **Radix Vue** under the hood — the Vue equivalent of Radix UI.

```bash
npx shadcn-vue@latest init
```

### Step 3.2: Add shadcn-vue equivalents of all 54 current UI components

All 54 current shadcn/ui components have direct shadcn-vue equivalents. Install each:

```bash
npx shadcn-vue@latest add button card dialog sheet input textarea select ...
```

**Key differences from React shadcn:**
- Components are `.vue` SFCs instead of `.tsx`
- `cva` variants work identically
- `cn()` utility is the same
- Tailwind classes are identical

### Step 3.3: Special component migrations

| Component | React Implementation | Vue Approach |
|---|---|---|
| **Resizable Panels** | `react-resizable-panels` with `ImperativePanelHandle` refs | `splitpanes` Vue package or CSS Grid with drag handles |
| **Markdown Rendering** | `react-markdown` + `remark-gfm` | `markdown-it` with `v-html` or `vue-markdown-render` |
| **Charts** | `recharts` (React-only) | `vue-chartjs` + `chart.js` |
| **Flow Diagrams** | `@xyflow/react` | `@vue-flow/core` (same maintainer, Vue port) |
| **Excalidraw** | `@excalidraw/excalidraw` (React-only) | Embed via iframe or find Vue alternative |
| **Mermaid** | Direct DOM rendering | Same approach — `mermaid.render()` is framework-agnostic |
| **Command Palette** | `cmdk` (React) | Built into shadcn-vue as `Command` component |
| **Carousel** | `embla-carousel-react` | `embla-carousel-vue` (same API) |

---

## Phase 4: Feature Component Migration (by area)

Migrate in this order — each area is self-contained and independently testable:

### Step 4.1: Auth page (1 component)
- **File**: `auth/AuthPage.tsx` → `auth/AuthPage.vue`
- Simple form with login/signup
- Tests: Login flow, signup flow, error handling

### Step 4.2: Dashboard (3 components)
- `dashboard/Dashboard.vue`
- `dashboard/CreateProjectDialog.vue`
- `dashboard/AppSettings.vue`
- Tests: Project list, create project, navigate to workspace

### Step 4.3: Project workspace shell (3 components)
- `project/ProjectWorkspace.vue` — 3-panel resizable layout
- `project/ProjectHeader.vue`
- `project/ProjectList.vue`
- Tests: Panel resize, collapse/expand, header controls

### Step 4.4: Sources panel (14 components)
- `sources/SourcesPanel.vue` (container)
- `sources/SourcesList.vue`, `SourceItem.vue`
- `sources/AddSourcesSheet.vue` (tabbed modal)
- `sources/UploadTab.vue`, `LinkTab.vue`, `PasteTab.vue`, `ResearchTab.vue`
- `sources/GoogleDriveTab.vue`, `DatabaseTab.vue`
- `sources/ProcessedContentSheet.vue`
- Tests: Upload file, add URL, Google Drive OAuth, source list

### Step 4.5: Chat panel (7 components)
- `chat/ChatPanel.vue` (container)
- `chat/ChatMessages.vue` — Markdown rendering, citations, code blocks
- `chat/ChatList.vue`, `ChatInput.vue`, `ChatHeader.vue`
- `chat/CitationBadge.vue`, `ChatEmptyState.vue`
- Tests: Send message, receive response, citations, voice input, markdown

### Step 4.6: Studio panel (40+ components)
- `studio/StudioContext.ts` → `composables/useStudio.ts` (done in Phase 2)
- `studio/sections/` — 15 generation section components
- `studio/audio/`, `video/`, `presentations/`, `prd/`, etc.
- `studio/shared/` — Shared studio components
- Tests: Generate audio, view presentation, progress indicators

### Step 4.7: Settings (12 components)
- `settings/SettingsSidebar.vue`
- `settings/sections/ApiKeysSection.vue`
- `settings/sections/ProfileSection.vue`, `SystemSection.vue`
- `settings/sections/DesignSection.vue`, `IntegrationsSection.vue`, `TeamSection.vue`
- `settings/team/CreateUserDialog.vue`, `DeleteUserDialog.vue`, `PasswordDisplay.vue`
- Tests: API key management, user profile, team management

### Step 4.8: Brand components
- Migrate last as they're the least critical path

---

## Phase 5: Design System Integration

### Step 5.1: Apply Attest design tokens
- Copy CSS variables from the Attest Storybook into `index.css`
- Install Nunito Sans font
- Update Tailwind config with Attest palette
- This is the same work described in the design system migration plan — but now directly using Vue

### Step 5.2: Adopt Attest Storybook components where applicable
Since both are now Vue 3, any Attest Storybook component can potentially be imported directly if the Attest design system is published as an npm package. Otherwise, use shadcn-vue styled with Attest tokens.

---

## Phase 6: Cleanup & Cutover

### Step 6.1: Testing
- Run `npm run build` — verify no build errors
- Start dev server, test all routes and features manually:
  - Auth: login, signup, logout
  - Dashboard: project CRUD, navigation
  - Workspace: 3-panel layout, resize, collapse
  - Sources: all source types (upload, URL, text, Google Drive, YouTube)
  - Chat: send messages, citations, voice input, markdown rendering
  - Studio: generate audio, presentations, PRDs
  - Settings: API keys, profile, team management
- Verify WebSocket voice input works
- Verify all API calls succeed with auth

### Step 6.2: Rename and replace
- Move `frontend/` → `frontend-react-backup/`
- Move `frontend-vue/` → `frontend/`
- Update `bin/dev`, `bin/setup` scripts if needed
- Update Docker config if applicable

### Step 6.3: Update documentation
- `DESIGN_SYSTEM.md` — Update component examples to Vue SFC syntax
- `CLAUDE.md` — Update frontend rules from React to Vue conventions
- Remove React-specific ESLint rules, add Vue ESLint rules

---

## Key Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Excalidraw has no Vue port** | Medium | Embed React Excalidraw via iframe, or use tldraw (has Vue support) |
| **react-resizable-panels has no direct Vue equivalent** | Medium | Use `splitpanes` Vue package or CSS Grid with custom drag handles |
| **Voice recording WebSocket is complex** | Low | WebSocket + AudioWorklet code is vanilla JS; only wrapper changes |
| **185 components is a lot of conversion** | High | Migrate area-by-area (Phase 4); each area independently testable |
| **recharts is React-only** | Medium | Use `vue-chartjs` + `chart.js`; different API but same visual output |
| **Parallel frontend during migration** | Low | Keep React frontend working until Vue is fully tested |

---

## Verification

1. `npm run build` — zero errors
2. `npm run lint` — zero Vue-specific lint errors
3. Manual testing of all features listed in Phase 6, Step 6.1
4. Compare visual output of Vue frontend against React frontend (screenshot comparison)
5. Verify all API integrations (auth, CRUD, file upload, WebSocket)
6. Performance check: Vue bundle size vs React bundle size
