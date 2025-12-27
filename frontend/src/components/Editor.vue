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
    
    // --- 核心修复配置 ---
    automaticLayout: true,          // 自动适应父容器大小
    scrollBeyondLastLine: false,    // 【关键】禁止滚动超过最后一行
    renderLineHighlight: 'all',     // 高亮当前行
    
    // --- 滚动条优化 ---
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      alwaysConsumeMouseWheel: false, // 防止阻断外部滚动
    },
    
    // --- 其他视觉优化 ---
    minimap: { enabled: false },    // 关闭右侧代码缩略图 (省空间)
    fontSize: 14,
    fontFamily: "'Fira Code', 'Consolas', monospace",
    tabSize: 4,
    insertSpaces: true,
    lineNumbersMinChars: 3,         // 行号宽度优化
    overviewRulerLanes: 0,          // 隐藏右侧概览标尺
    hideCursorInOverviewRuler: true
  })

  // 监听内容变化传回父组件
  editorInstance.onDidChangeModelContent(() => {
    emit('update:modelValue', editorInstance.getValue())
  })
})

// 监听父组件传来的值变化（例如打开新脚本时，或者切换脚本时）
watch(() => props.modelValue, (newValue) => {
  if (editorInstance && newValue !== editorInstance.getValue()) {
    // 使用 executeEdits 保留撤销栈，或者用 setValue 重置
    // 这里用 setValue 简单直接，适合切换文件场景
    editorInstance.setValue(newValue)
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
  /* 移除 min-height，完全依赖父容器 flex 布局 */
  overflow: hidden;
  border-radius: 4px;
}
</style>
