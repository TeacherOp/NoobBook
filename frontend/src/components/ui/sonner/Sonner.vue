<script lang="ts" setup>
import type { ToasterProps } from "vue-sonner"
import { reactiveOmit } from "@vueuse/core"
import { PhCheckCircle, PhInfo, PhCircleNotch, PhXCircle, PhWarning, PhX } from "@phosphor-icons/vue"
import { Toaster as Sonner } from "vue-sonner"

const props = defineProps<ToasterProps>()
const delegatedProps = reactiveOmit(props, "toastOptions")
</script>

<template>
  <Sonner
    class="toaster group"
    :toast-options="{
      classes: {
        toast: 'group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg',
        description: 'group-[.toast]:text-muted-foreground',
        actionButton:
          'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
        cancelButton:
          'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
      },
    }"
    v-bind="delegatedProps"
  >
    <template #success-icon>
      <PhCheckCircle :size="16" />
    </template>
    <template #info-icon>
      <PhInfo :size="16" />
    </template>
    <template #warning-icon>
      <PhWarning :size="16" />
    </template>
    <template #error-icon>
      <PhXCircle :size="16" />
    </template>
    <template #loading-icon>
      <div>
        <PhCircleNotch :size="16" class="animate-spin" />
      </div>
    </template>
    <template #close-icon>
      <PhX :size="16" />
    </template>
  </Sonner>
</template>
