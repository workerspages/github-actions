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

const initEditor = () => {
  if (!editorContainer.value) return

  editorInstance = monaco.editor.create(editorContainer.value, {
    value: props.modelValue || '', 
    language: 'python',
    theme: 'vs-dark', // 深色主题
    
    // --- 核心配置 ---
    automaticLayout: true,          // 自动适应父容器大小
    scrollBeyondLastLine: false,    // 禁止滚动超过最后一行
    renderLineHighlight: 'all',     // 高亮当前行
    
    // --- 滚动条优化 ---
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      alwaysConsumeMouseWheel: false, 
    },
    
    // --- 其他视觉优化 ---
    minimap: { enabled: false },    
    fontSize: 14,
    fontFamily: "'Fira Code', 'Consolas', monospace",
    tabSize: 4,
    insertSpaces: true,
    lineNumbersMinChars: 3,         
    overviewRulerLanes: 0,          
    hideCursorInOverviewRuler: true
  })

  // 监听内容变化传回父组件
  editorInstance.onDidChangeModelContent(() => {
    emit('update:modelValue', editorInstance.getValue())
  })
}

onMounted(() => {
  // 关键修复：延迟 100ms 初始化，等待 Modal 动画结束和 DOM 布局稳定
  // 否则在 Tabs 或 Modal 中编辑器高度可能计算为 0
  setTimeout(() => {
    initEditor()
  }, 100)
})

// 监听父组件传来的值变化
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
