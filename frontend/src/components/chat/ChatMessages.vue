<script setup lang="ts">
/**
 * ChatMessages Component
 * Educational Note: Renders the conversation with markdown support and inline citations.
 *
 * Markdown + Citation strategy:
 * 1. Pre-process: convert [[cite:CHUNK_ID]] markers to a custom HTML tag
 *    <span data-cite="CHUNK_ID" data-num="N"></span>
 * 2. `marked` renders markdown to HTML
 * 3. v-html renders the HTML
 * 4. A post-render step using Vue's custom renderer is not feasible for inline
 *    citation badges in markdown — instead we split each AI message into segments
 *    by the citation markers and render CitationBadge components inline.
 *
 * Segment-based rendering:
 *   "text [[cite:abc_page_1_chunk_2]] more text"
 *   → [TextSegment("text "), CitationSegment(abc..., 1), TextSegment(" more text")]
 *   Each TextSegment is rendered as markdown HTML via marked.
 *   Each CitationSegment is rendered as <CitationBadge>.
 */
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { PhGhost, PhFileText, PhCopy, PhCheck, PhDownloadSimple } from '@phosphor-icons/vue'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { parseCitations } from '@/lib/citations'
import { sourcesAPI } from '@/lib/api/sources'
import CitationBadge from './CitationBadge.vue'
import type { Message } from '@/lib/api/chats'

// Configure marked once
marked.setOptions({ gfm: true, breaks: false })

const props = defineProps<{
  messages: Message[]
  sending: boolean
  projectId: string
}>()

// ── Markdown rendering ────────────────────────────────────────────────────────

function renderMarkdown(text: string): string {
  const html = marked.parse(text) as string
  if (typeof DOMPurify !== 'undefined') {
    return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
  }
  return html
}

// ── Citation + segment parsing ────────────────────────────────────────────────

interface TextSegment { type: 'text'; html: string }
interface CitationSegment {
  type: 'citation'
  citationNumber: number
  chunkId: string
  pageNumber: number
}
type Segment = TextSegment | CitationSegment

const CITE_RE = /\[\[cite:([a-zA-Z0-9_-]+_page_(\d+)_chunk_\d+)\]\]/g

function parseSegments(content: string): Segment[] {
  const { markerToNumber } = parseCitations(content)
  const segments: Segment[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  CITE_RE.lastIndex = 0
  while ((match = CITE_RE.exec(content)) !== null) {
    if (match.index > lastIndex) {
      // Render text between citations as markdown
      let textPart = content.slice(lastIndex, match.index)
      // Replace image markers with img tags
      textPart = textPart.replace(/\[\[image:([^\]]+)\]\]/g, (_m, fn) => {
        const url = sourcesAPI.getAIImageUrl(props.projectId, fn)
        return `![${fn}](${url})`
      })
      segments.push({ type: 'text', html: renderMarkdown(textPart) })
    }
    const fullMarker = match[0]
    const chunkId = match[1]
    const pageNumber = parseInt(match[2], 10)
    const citationNumber = markerToNumber.get(fullMarker) || 0
    segments.push({ type: 'citation', citationNumber, chunkId, pageNumber })
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < content.length) {
    let remaining = content.slice(lastIndex)
    remaining = remaining.replace(/\[\[image:([^\]]+)\]\]/g, (_m, fn) => {
      const url = sourcesAPI.getAIImageUrl(props.projectId, fn)
      return `![${fn}](${url})`
    })
    segments.push({ type: 'text', html: renderMarkdown(remaining) })
  }

  return segments
}

// ── Unique citations for sources footer ──────────────────────────────────────

function getUniqueCitations(content: string) {
  return parseCitations(content).uniqueCitations
}

// ── Copy / download actions ───────────────────────────────────────────────────

const copiedId = ref<string | null>(null)

async function copyMessage(msg: Message) {
  const clean = msg.content.replace(/\[\[cite:[^\]]+\]\]/g, '')
  try {
    await navigator.clipboard.writeText(clean)
  } catch {
    const el = document.createElement('textarea')
    el.value = clean
    el.style.cssText = 'position:fixed;opacity:0'
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  copiedId.value = msg.id
  setTimeout(() => { copiedId.value = null }, 2000)
}

function downloadMessage(msg: Message) {
  const clean = msg.content.replace(/\[\[cite:[^\]]+\]\]/g, '')
  const blob = new Blob([clean], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `response-${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Auto-scroll ───────────────────────────────────────────────────────────────

const containerRef = ref<HTMLDivElement | null>(null)
const endRef = ref<HTMLDivElement | null>(null)
let userScrolledAway = false
let prevCount = 0

function handleScroll() {
  const el = containerRef.value
  if (!el) return
  const dist = el.scrollHeight - el.scrollTop - el.clientHeight
  if (dist > 150) userScrolledAway = true
  else if (dist < 50) userScrolledAway = false
}

watch([() => props.messages.length, () => props.sending], async () => {
  await nextTick()
  const isInitial = prevCount === 0 && props.messages.length > 0
  prevCount = props.messages.length
  if (isInitial) {
    endRef.value?.scrollIntoView({ behavior: 'instant' as 'auto' | 'smooth' | 'instant' })
    userScrolledAway = false
  } else if (!userScrolledAway) {
    endRef.value?.scrollIntoView({ behavior: 'smooth' })
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="flex-1 min-h-0 min-w-0 w-full overflow-y-auto overflow-x-hidden bg-white"
    @scroll="handleScroll"
  >
    <div class="pt-6 pb-2 px-6 space-y-4 w-full">
      <div v-for="msg in props.messages" :key="msg.id">

        <!-- User message -->
        <div v-if="msg.role === 'user'" class="flex justify-end w-full">
          <div class="max-w-[80%] min-w-0">
            <div class="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2">
              <p class="text-sm whitespace-pre-wrap break-words">{{ msg.content }}</p>
            </div>
          </div>
        </div>

        <!-- AI message -->
        <div v-else class="flex justify-start w-full max-w-full overflow-hidden">
          <div class="max-w-[85%] min-w-0 flex gap-3 overflow-hidden">
            <div class="flex-shrink-0 mt-1">
              <PhGhost
                :size="28"
                weight="bold"
                class="text-primary hover:scale-110 hover:rotate-6 transition-transform duration-200 cursor-pointer"
              />
            </div>
            <div class="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3 min-w-0 overflow-hidden flex-1">
              <p class="text-xs font-medium text-muted-foreground mb-2">NoobBook</p>

              <!-- Segment-based rendering: markdown text + inline citation badges -->
              <div class="prose prose-sm max-w-none min-w-0 overflow-hidden text-sm leading-relaxed">
                <template v-for="(seg, i) in parseSegments(msg.content)" :key="i">
                  <!-- Markdown text segment -->
                  <!-- eslint-disable-next-line vue/no-v-html -->
                  <span v-if="seg.type === 'text'" class="[&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold [&_h3]:text-sm [&_h3]:font-bold [&_p]:mb-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2 [&_code]:bg-muted [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_pre]:bg-stone-900 [&_pre]:text-stone-100 [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_a]:text-primary [&_a]:underline [&_table]:border-collapse [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground" v-html="seg.html" />
                  <!-- Citation badge -->
                  <CitationBadge
                    v-else-if="seg.type === 'citation'"
                    :citation-number="seg.citationNumber"
                    :chunk-id="seg.chunkId"
                    :page-number="seg.pageNumber"
                    :project-id="props.projectId"
                  />
                </template>
              </div>

              <!-- Sources footer (when citations exist) -->
              <template v-if="getUniqueCitations(msg.content).length > 0">
                <Separator class="my-3" />
                <div class="space-y-1">
                  <div class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <PhFileText :size="12" />
                    <span>Sources</span>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="cit in getUniqueCitations(msg.content)"
                      :key="`footer-${cit.citationNumber}`"
                      class="text-xs text-muted-foreground"
                    >
                      <span class="font-medium">[{{ cit.citationNumber }}]</span>
                      Page {{ cit.pageNumber }}
                      <template v-if="cit.chunkIndex > 1">, Section {{ cit.chunkIndex }}</template>
                    </span>
                  </div>
                </div>
              </template>

              <!-- Copy + Download actions -->
              <TooltipProvider>
                <div class="flex items-center gap-1 mt-2">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                        @click="copyMessage(msg)"
                      >
                        <PhCheck v-if="copiedId === msg.id" :size="16" weight="bold" class="text-green-600" />
                        <PhCopy v-else :size="16" weight="bold" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p class="text-xs">{{ copiedId === msg.id ? 'Copied!' : 'Copy' }}</p>
                    </TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                        @click="downloadMessage(msg)"
                      >
                        <PhDownloadSimple :size="16" weight="bold" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom"><p class="text-xs">Download</p></TooltipContent>
                  </Tooltip>
                </div>
              </TooltipProvider>
            </div>
          </div>
        </div>

        <p v-if="msg.error" class="text-xs text-destructive text-center mt-1">
          This message had an error
        </p>
      </div>

      <!-- Loading indicator -->
      <div v-if="props.sending" class="flex justify-start">
        <div class="max-w-[85%] flex gap-3">
          <div class="flex-shrink-0 mt-1">
            <PhGhost :size="28" weight="bold" class="text-primary" />
          </div>
          <div class="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3">
            <p class="text-xs font-medium text-muted-foreground mb-2">NoobBook</p>
            <div class="flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:0ms]" />
              <span class="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:200ms]" />
              <span class="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:400ms]" />
            </div>
          </div>
        </div>
      </div>

      <div ref="endRef" />
    </div>
  </div>
</template>
