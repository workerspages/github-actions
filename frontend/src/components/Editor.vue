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
    theme: 'vs-dark',
    
    // --- 核心修复配置 ---
    automaticLayout: true,          
    scrollBeyondLastLine: false,    
    renderLineHighlight: 'all',
    
    // 强制行号宽度，防止数字重叠
    lineNumbers: 'on',
    lineNumbersMinChars: 4,  // 预留4位数字的宽度
    glyphMargin: false,      // 关闭左侧图标栏，节省空间
    folding: true,           // 启用代码折叠
    
    // 字体设置 (关键修复)
    fontSize: 14,
    fontFamily: "'Menlo', 'Monaco', 'Courier New', monospace", // 使用等宽字体
    fontLigatures: false,    // 关闭连字，避免渲染异常
    
    // 滚动条优化
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      verticalScrollbarSize: 10,
      horizontalScrollbarSize: 10,
      alwaysConsumeMouseWheel: false, 
    },
    
    // 视觉优化
    minimap: { enabled: false },    
    tabSize: 4,
    insertSpaces: true,
    overviewRulerLanes: 0,          
    hideCursorInOverviewRuler: true,
    renderValidationDecorations: 'off' // 关闭波浪线验证，纯净显示
  })

  editorInstance.onDidChangeModelContent(() => {
    emit('update:modelValue', editorInstance.getValue())
  })
}

onMounted(() => {
  // 延迟初始化，等待 DOM 布局稳定
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
/* 强制 Monaco 内部样式重置，防止外部 CSS 干扰行号 */
:deep(.monaco-editor .margin-view-overlays .line-numbers) {
  text-align: right !important;
  padding-right: 5px !important;
}
</style>
