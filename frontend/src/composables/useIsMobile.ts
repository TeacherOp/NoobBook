/**
 * useIsMobile Composable
 *
 * Educational Note: Vue equivalent of the React useIsMobile hook.
 * Uses window.matchMedia with a reactive ref. The media query listener
 * fires on breakpoint changes without polling.
 */

import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_BREAKPOINT = 768

export function useIsMobile() {
  const isMobile = ref(false)
  let mql: MediaQueryList | null = null

  const onChange = () => {
    isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  }

  onMounted(() => {
    mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    mql.addEventListener('change', onChange)
    isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  })

  onUnmounted(() => {
    if (mql) {
      mql.removeEventListener('change', onChange)
    }
  })

  return isMobile
}
