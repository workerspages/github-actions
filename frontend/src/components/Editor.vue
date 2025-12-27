<template>
  <div ref="editorContainer" class="editor-container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as monaco from 'monaco-editor'

const props = defineProps(['modelValue'])
const emit = defineEmits(['update:modelValue'])
const editorContainer = ref(null)
let editorInstance = null

const initEditor = () => {
  if (!editorContainer.value) return

  editorInstance = monaco.editor.create(editorContainer.value, {
    value: props.modelValue || '', // 防止 null 报错
    language: 'python',
    theme: 'vs-dark',
    automaticLayout: true,
    scrollBeyondLastLine: false,
    renderLineHighlight: 'all',
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
    },
    minimap: { enabled: false },
    fontSize: 14,
    fontFamily: "'Fira Code', 'Consolas', monospace",
    tabSize: 4,
    insertSpaces: true,
  })

  editorInstance.onDidChangeModelContent(() => {
    emit('update:modelValue', editorInstance.getValue())
  })
}

onMounted(() => {
  // 关键修复：延迟 100ms 初始化，等待 Modal 动画结束和 DOM 布局稳定
  setTimeout(() => {
    initEditor()
  }, 100)
})

watch(() => props.modelValue, (newValue) => {
  if (editorInstance && newValue !== editorInstance.getValue()) {
    editorInstance.setValue(newValue || '')
  }
})

onBeforeUnmount(() => {
  if (editorInstance) {
    editorInstance.dispose()
    editorInstance = null
  }
})
</script>

<style scoped>
.editor-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 4px;
}
</style>
