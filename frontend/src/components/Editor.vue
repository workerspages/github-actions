<template>
  <div ref="editorContainer" class="editor-container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as monaco from 'monaco-editor'

const props = defineProps(['modelValue'])
const emit = defineEmits(['update:modelValue'])
const editorContainer = ref(null)
let editorInstance = null

onMounted(() => {
  editorInstance = monaco.editor.create(editorContainer.value, {
    value: props.modelValue,
    language: 'python',
    theme: 'vs-dark', // 深色主题
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    scrollBeyondLastLine: false,
  })

  // 监听内容变化传回父组件
  editorInstance.onDidChangeModelContent(() => {
    emit('update:modelValue', editorInstance.getValue())
  })
})

// 监听父组件传来的值变化（例如打开新脚本时）
watch(() => props.modelValue, (newValue) => {
  if (editorInstance && newValue !== editorInstance.getValue()) {
    editorInstance.setValue(newValue)
  }
})

onBeforeUnmount(() => {
  if (editorInstance) editorInstance.dispose()
})
</script>

<style scoped>
.editor-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
  border: 1px solid #333;
  border-radius: 4px;
}
</style>
