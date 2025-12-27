<template>
  <n-layout has-sider style="height: 100vh">
    <!-- 侧边栏 -->
    <n-layout-sider bordered width="220" content-style="padding: 24px;" style="background-color: #18181c;">
      <div class="logo">FluxTask</div>
      <n-menu :options="menuOptions" :value="activeMenu" @update:value="handleMenuClick" />
      <div class="user-info">
        <n-avatar round size="small" src="https://avatars.githubusercontent.com/u/1?v=4" />
        <span style="margin-left: 10px; color: #aaa;">Admin</span>
      </div>
    </n-layout-sider>

    <n-layout>
      <n-layout-header bordered class="header">
        <div class="header-title">任务列表</div>
        <n-space>
          <n-button strong secondary circle type="info" @click="fetchScripts">
            <template #icon><n-icon><refresh-icon /></n-icon></template>
          </n-button>
          <n-button type="primary" @click="openCreateModal">
            <template #icon><n-icon><add-icon /></n-icon></template>
            新建任务
          </n-button>
        </n-space>
      </n-layout-header>

      <n-layout-content class="content-bg" content-style="padding: 24px;">
        <n-grid :x-gap="24" :y-gap="24" cols="1 800:2 1200:3 1600:4">
          <n-grid-item v-for="script in scripts" :key="script.id">
            <n-card hoverable class="script-card">
              <template #header>
                <div class="card-header">
                  <span class="script-name">{{ script.name }}</span>
                  <n-tag size="small" :type="getStatusType(script.last_status)">
                    {{ script.last_status || 'Wait' }}
                  </n-tag>
                </div>
              </template>
              
              <div class="card-body">
                <div class="info-row"><n-icon><time-icon /></n-icon><span>{{ script.cron_exp }}</span></div>
                <div class="info-row"><n-icon><hourglass-icon /></n-icon><span>延迟: 0~{{ script.random_delay }}s</span></div>
                <div class="info-row" style="margin-top: 10px; font-size: 12px; color: #666;">
                  上次运行: {{ script.last_run || '无' }}
                </div>
              </div>

              <template #action>
                <n-space justify="end">
                  <!-- 查看日志按钮 -->
                  <n-button size="small" secondary @click="openLogDrawer(script)">
                    <template #icon><n-icon><document-text-icon /></n-icon></template>
                    日志
                  </n-button>
                  <n-popconfirm @positive-click="runScript(script.id)">
                    <template #trigger><n-button size="small" secondary type="success">运行</n-button></template>
                    确定立即执行？
                  </n-popconfirm>
                  <n-button size="small" secondary type="warning" @click="editScript(script)">编辑</n-button>
                  <n-popconfirm @positive-click="deleteScript(script.id)">
                    <template #trigger><n-button size="small" secondary type="error">删除</n-button></template>
                    确定删除？
                  </n-popconfirm>
                </n-space>
              </template>
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-empty v-if="scripts.length === 0" description="暂无任务，点击右上角新建" style="margin-top: 100px" />
      </n-layout-content>
    </n-layout>
  </n-layout>

  <!-- 编辑/新建 模态框 -->
  <n-modal 
    v-model:show="showModal" preset="card" :title="isEdit ? '编辑脚本' : '新建脚本'"
    style="width: 90vw; height: 90vh; max-width: 1400px;" :bordered="true"
    :segmented="{ content: 'soft', footer: 'soft' }" content-style="padding: 0; overflow: hidden;"
  >
    <n-layout has-sider style="height: 100%">
      <n-layout-sider width="320" bordered content-style="padding: 24px;" :native-scrollbar="false">
        <n-form label-placement="top">
          <n-form-item label="任务名称"><n-input v-model:value="form.name" /></n-form-item>
          <n-form-item label="Cron 表达式"><n-input v-model:value="form.cron" placeholder="0 8 * * *" /></n-form-item>
          <n-form-item :label="`随机延时: ${form.delay} 秒`"><n-slider v-model:value="form.delay" :max="1800" :step="10" /></n-form-item>
          <n-divider />
          <n-alert type="info" :show-icon="false" title="Tips">
            <p>Secrets: <n-text code>os.environ['KEY']</n-text></p>
            <p>依赖管理: 请在右侧 <b>"依赖"</b> 标签页填写 <n-text code>requirements.txt</n-text>。</p>
          </n-alert>
        </n-form>
      </n-layout-sider>
      <n-layout-content content-style="height: 100%; display: flex; flex-direction: column;">
        <n-tabs type="line" animated style="height: 100%; display: flex; flex-direction: column;">
          <n-tab-pane name="code" tab="Python 代码" style="height: 100%; padding: 0;"><Editor v-model="form.code" style="height: 100%;" /></n-tab-pane>
          <n-tab-pane name="requirements" tab="依赖 (Requirements.txt)" display-directive="show" style="height: 100%; padding: 0;">
            <textarea v-model="form.requirements" style="flex: 1; width: 100%; background: #1e1e1e; color: #d4d4d4; border: none; padding: 15px; font-family: monospace; resize: none; outline: none; height: 100%;" placeholder="requests==2.31.0"></textarea>
          </n-tab-pane>
        </n-tabs>
      </n-layout-content>
    </n-layout>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" @click="saveData" :loading="saving">保存并应用</n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 日志抽屉 (复刻 GitHub Actions UI) -->
  <n-drawer v-model:show="showLogDrawer" width="800" placement="right">
    <n-drawer-content :title="currentLogScript?.name + ' - 执行日志'" closable body-style="padding: 0; background-color: #0d1117;">
      <template #header-extra>
        <n-button size="small" secondary @click="fetchScripts"><template #icon><n-icon><refresh-icon/></n-icon></template>刷新</n-button>
      </template>
      
      <div v-if="logSteps.length > 0" class="log-container">
        <div v-for="(step, index) in logSteps" :key="index" class="log-step">
          <!-- 步骤标题栏 -->
          <div class="log-step-header" @click="step.expanded = !step.expanded">
            <div class="step-left">
              <n-icon class="arrow-icon" :class="{ expanded: step.expanded }"><chevron-forward-icon /></n-icon>
              <!-- 状态图标 -->
              <n-icon v-if="step.status === 0" color="#238636" size="18"><checkmark-circle-icon /></n-icon>
              <n-icon v-else-if="step.status === 1" color="#f85149" size="18"><close-circle-icon /></n-icon>
              <n-icon v-else color="#8b949e" size="18"><ellipse-icon /></n-icon>
              <span class="step-name">{{ step.name }}</span>
            </div>
            <span class="step-duration">{{ step.duration }}</span>
          </div>
          
          <!-- 步骤详细日志 -->
          <div v-if="step.expanded" class="log-step-body">
            <div v-for="(line, idx) in step.output.split('\n')" :key="idx" class="log-line">
              <span class="line-num">{{ idx + 1 }}</span>
              <span class="line-content">{{ line }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <n-empty v-else description="暂无日志" style="margin-top: 100px; color: #8b949e" />
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { ref, onMounted, h, computed } from 'vue'
import { useRouter } from 'vue-router'
import { 
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NAvatar, 
  NButton, NSpace, NIcon, NGrid, NGridItem, NCard, NTag, NPopconfirm, 
  NModal, NForm, NFormItem, NInput, NSlider, NText, NDivider, NAlert, NEmpty, useMessage,
  NTabs, NTabPane, NDrawer, NDrawerContent
} from 'naive-ui'
import { 
  TimeOutline as TimeIcon, HourglassOutline as HourglassIcon, 
  Add as AddIcon, Refresh as RefreshIcon, List as ListIcon, Key as KeyIcon,
  DocumentText as DocumentTextIcon, ChevronForward as ChevronForwardIcon,
  CheckmarkCircle as CheckmarkCircleIcon, CloseCircle as CloseCircleIcon, Ellipse as EllipseIcon
} from '@vicons/ionicons5'
import axios from 'axios'
import Editor from '../components/Editor.vue'

const router = useRouter()
const message = useMessage()

// 状态
const activeMenu = ref('dashboard')
const scripts = ref([])
const showModal = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const currentId = ref(null)
const showLogDrawer = ref(false)
const currentLogScript = ref(null)
const logSteps = ref([])

const form = ref({ name: '', cron: '0 8 * * *', delay: 300, code: '', requirements: '' })

const menuOptions = [
  { label: '任务列表', key: 'dashboard', icon: () => h(NIcon, null, { default: () => h(ListIcon) }) },
  { label: 'Secrets 管理', key: 'secrets', icon: () => h(NIcon, null, { default: () => h(KeyIcon) }) }
]

const handleMenuClick = (key) => { if (key === 'secrets') router.push('/secrets') }
const getStatusType = (s) => s === 'Success' ? 'success' : (s === 'Failed' || s === 'Error' ? 'error' : 'default')
const getToken = () => localStorage.getItem('token')

const fetchScripts = async () => {
  try {
    const res = await axios.get('/api/scripts', { headers: { Authorization: `Bearer ${getToken()}` } })
    scripts.value = res.data
    // 如果抽屉打开，更新日志
    if (showLogDrawer.value && currentLogScript.value) {
      const updated = scripts.value.find(s => s.id === currentLogScript.value.id)
      if (updated) openLogDrawer(updated)
    }
  } catch (e) { if (e.response?.status === 401) router.push('/login') }
}

const openLogDrawer = (script) => {
  currentLogScript.value = script
  showLogDrawer.value = true
  try {
    const logs = JSON.parse(script.last_log || '[]')
    // 默认展开失败的步骤，或者最后一个步骤
    logs.forEach((step, index) => {
      step.expanded = (step.status !== 0) || (index === logs.length - 1 && logs.length > 1)
    })
    logSteps.value = logs
  } catch (e) {
    logSteps.value = []
  }
}

const runScript = async (id) => {
  try {
    await axios.post(`/api/scripts/${id}/run`, {}, { headers: { Authorization: `Bearer ${getToken()}` } })
    message.success('任务开始运行...')
    // 简单轮询一下日志
    setTimeout(fetchScripts, 2000)
  } catch(e) { message.error('运行失败') }
}

const deleteScript = async (id) => {
  try {
    await axios.delete(`/api/scripts/${id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
    message.success('已删除')
    fetchScripts()
  } catch(e) { message.error('删除失败') }
}

const openCreateModal = () => {
  isEdit.value = false
  form.value = { name: '', cron: '0 8 * * *', delay: 300, code: 'import os\nfrom loguru import logger\n\nlogger.info("Task Start...")\n', requirements: '' }
  showModal.value = true
}

const editScript = (script) => {
  isEdit.value = true
  currentId.value = script.id
  form.value = { name: script.name, cron: script.cron_exp, delay: script.random_delay, code: script.code, requirements: script.requirements || '' }
  showModal.value = true
}

const saveData = async () => {
  if (!form.value.name) return message.warning('请输入名称')
  saving.value = true
  try {
    const payload = { name: form.value.name, cron: form.value.cron, delay: form.value.delay, code: form.value.code, requirements: form.value.requirements }
    const headers = { Authorization: `Bearer ${getToken()}` }
    if (isEdit.value) await axios.put(`/api/scripts/${currentId.value}`, payload, { headers })
    else await axios.post('/api/scripts', payload, { headers })
    message.success('保存成功')
    showModal.value = false
    fetchScripts()
  } catch (e) { message.error('保存失败: ' + (e.response?.data?.detail || e.message)) } finally { saving.value = false }
}

onMounted(fetchScripts)
</script>

<style scoped>
.logo { font-size: 24px; font-weight: 700; color: #63e2b7; margin-bottom: 30px; text-align: center; letter-spacing: 1px; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 0 32px; height: 64px; background: rgba(255,255,255,0.02); }
.header-title { font-size: 18px; font-weight: 500; }
.content-bg { background-color: #101014; }
.script-card { border-radius: 12px; transition: transform 0.2s; background: #18181c; border: 1px solid #2d2d30; }
.script-card:hover { transform: translateY(-4px); border-color: #63e2b7; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.script-name { font-weight: 600; font-size: 16px; }
.info-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; color: #aaa; }
.user-info { position: absolute; bottom: 24px; left: 24px; display: flex; align-items: center; }
:deep(.n-tabs) { height: 100%; display: flex; flex-direction: column; }
:deep(.n-tabs .n-tabs-pane-wrapper) { flex: 1; overflow: hidden; }
:deep(.n-tab-pane) { height: 100%; display: flex; flex-direction: column; }

/* --- GitHub Actions 风格日志样式 --- */
.log-container { display: flex; flex-direction: column; gap: 8px; padding: 16px; }
.log-step { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
.log-step-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; cursor: pointer; user-select: none; transition: background 0.2s; }
.log-step-header:hover { background-color: #21262d; }
.step-left { display: flex; align-items: center; gap: 10px; }
.arrow-icon { transition: transform 0.2s; color: #8b949e; }
.arrow-icon.expanded { transform: rotate(90deg); }
.step-name { font-weight: 600; font-size: 14px; color: #c9d1d9; }
.step-duration { font-size: 12px; color: #8b949e; }
.log-step-body { border-top: 1px solid #30363d; padding: 10px 0; background-color: #0d1117; font-family: 'Fira Code', monospace; font-size: 12px; max-height: 500px; overflow-y: auto; }
.log-line { display: flex; gap: 12px; padding: 2px 16px; color: #8b949e; }
.log-line:hover { background-color: #161b22; color: #c9d1d9; }
.line-num { min-width: 24px; text-align: right; user-select: none; opacity: 0.5; }
.line-content { white-space: pre-wrap; word-break: break-all; flex: 1; }
</style>
