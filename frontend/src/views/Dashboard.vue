<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider bordered width="220" content-style="padding: 24px;" style="background-color: #18181c;">
      <div class="logo">GitHub Actions</div>
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
            <n-card hoverable class="script-card" :class="{ 'paused-card': !script.is_active }">
              <template #header>
                <div class="card-header">
                  <span class="script-name">{{ script.name }}</span>
                  <n-tag v-if="!script.is_active" size="small" type="warning" bordered>已暂停</n-tag>
                  <n-tag v-else size="small" :type="getStatusType(script.last_status)">
                    {{ script.last_status || 'Wait' }}
                  </n-tag>
                </div>
              </template>
              
              <div class="card-body">
                <div class="info-row">
                  <n-icon><time-icon /></n-icon>
                  <span :style="{ textDecoration: !script.is_active ? 'line-through' : 'none' }">
                    {{ script.cron || script.cron_exp }}
                  </span>
                </div>
                <div class="info-row">
                  <n-icon><hourglass-icon /></n-icon>
                  <span>延迟: 0~{{ script.delay || script.random_delay }}s</span>
                </div>
                <div class="info-row" style="margin-top: 10px; font-size: 12px; color: #666;">
                  上次运行: {{ script.last_run || '无' }}
                </div>
              </div>

              <template #action>
                <n-space justify="end">
                  <n-button size="small" secondary @click="openLogDrawer(script.id)">
                    <template #icon><n-icon><document-text-icon /></n-icon></template>
                    日志
                  </n-button>
                  
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button size="small" circle secondary :type="script.is_active ? 'warning' : 'success'" @click="toggleScriptStatus(script)">
                        <template #icon>
                          <n-icon v-if="script.is_active"><pause-icon /></n-icon>
                          <n-icon v-else><play-icon /></n-icon>
                        </template>
                      </n-button>
                    </template>
                    {{ script.is_active ? '暂停任务' : '恢复任务' }}
                  </n-tooltip>

                  <n-popconfirm @positive-click="runScript(script.id)">
                    <template #trigger>
                      <n-button size="small" secondary type="success">运行</n-button>
                    </template>
                    确定要立即执行该脚本吗？
                  </n-popconfirm>
                  
                  <n-button size="small" secondary type="warning" @click="editScript(script.id)">编辑</n-button>
                  
                  <n-popconfirm @positive-click="deleteScript(script.id)">
                    <template #trigger>
                      <n-button size="small" secondary type="error">删除</n-button>
                    </template>
                    确定删除该任务及其虚拟环境？
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

  <n-modal 
    v-model:show="showModal" 
    preset="card" 
    :title="isEdit ? '编辑脚本' : '新建脚本'"
    style="width: 90vw; height: 90vh; max-width: 1400px;"
    :bordered="true"
    :segmented="{ content: 'soft', footer: 'soft' }"
    content-style="padding: 0; overflow: hidden;"
  >
    <n-layout has-sider style="height: 100%">
      <n-layout-sider 
        width="320" 
        bordered 
        content-style="padding: 24px;" 
        :native-scrollbar="false"
      >
        <n-form label-placement="top">
          <n-form-item label="任务名称">
            <n-input v-model:value="form.name" placeholder="例如: 京东签到" />
          </n-form-item>
          <n-form-item label="运行环境">
            <n-radio-group v-model:value="form.runtime" name="runtime_group">
              <n-space>
                <n-radio value="python">Python</n-radio>
                <n-radio value="node">Node.js</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>
          <n-form-item label="Cron 表达式">
            <n-input v-model:value="form.cron" placeholder="0 8 * * *" />
            <n-text depth="3" style="font-size: 12px;">格式: 分 时 日 月 周</n-text>
          </n-form-item>
          <n-form-item :label="`随机延时: ${form.delay} 秒`">
            <n-slider v-model:value="form.delay" :max="1800" :step="10" />
            <n-text depth="3" style="font-size: 12px;">防止被识别为机器人，建议 > 60s</n-text>
          </n-form-item>
          <n-divider />
          
          <n-alert type="info" :show-icon="false" title="提示">
            
            <div style="margin-bottom: 16px;">
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #e5e5e5;">🔐 Secrets 环境变量</p>
              <div style="background: #1e1e1e; padding: 10px; border-radius: 6px; font-family: 'Fira Code', Consolas, monospace; font-size: 11px; color: #d4d4d4;">
                <span style="color: #9cdcfe;">os</span>.<span style="color: #9cdcfe;">environ</span>[<span style="color: #ce9178;">'KEY'</span>]
              </div>
              <p style="margin: 6px 0 0 0; font-size: 11px; color: #aaa;">可在 "Secrets 管理" 标签页设置此任务独享的环境变量，优先级高于全局设置。</p>
            </div>
            
            <div style="margin-bottom: 16px;">
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #e5e5e5;">📦 依赖管理</p>
              <p style="margin: 0; font-size: 11px; color: #aaa;">请在右侧 <b>"依赖"</b> 标签页填写 <span style="background: #1e1e1e; color: #ce9178; padding: 2px 6px; border-radius: 4px; font-family: 'Fira Code', Consolas, monospace;">requirements.txt</span> (Python) 或包名 (Node.js)。</p>
            </div>
            
            <div style="margin-bottom: 16px;">
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #e5e5e5;">🐛 如果出错</p>
              <p style="margin: 0 0 6px 0; font-size: 11px; color: #aaa;">请尝试删除代码中的此行判断：</p>
              <div style="background: #1e1e1e; padding: 10px; border-radius: 6px; font-family: 'Fira Code', Consolas, monospace; font-size: 11px; color: #d4d4d4;">
                <span style="color: #c678dd;">if</span> <span style="color: #9cdcfe;">os</span>.<span style="color: #dcdcaa;">getenv</span>(<span style="color: #ce9178;">'GITHUB_ACTIONS'</span>):
              </div>
            </div>

            <div style="margin-bottom: 16px;">
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #e5e5e5;">🔄 运行模式 (Python / Node.js)</p>
              <p style="margin: 0 0 6px 0; font-size: 11px; color: #aaa;">可在上方选择运行环境。Node.js 和 Python 享有各自的依赖管理体验，前端会自动向 Node.js 注入 runtime 注释。</p>
            </div>

            <div>
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #e5e5e5;">🌐 Playwright 推荐参数</p>
              <p style="margin: 0 0 6px 0; font-size: 11px; color: #aaa;">Docker root 环境必须加参数：</p>
              <div style="background: #1e1e1e; padding: 12px; border-radius: 6px; font-family: 'Fira Code', Consolas, monospace; font-size: 11px; overflow-x: auto; line-height: 1.5; color: #d4d4d4;">
                <div style="color: #6a9955;">// --- 修改重点区域开始 ---</div>
                <div><span style="color: #c678dd;">const</span> <span style="color: #9cdcfe;">browser</span> = <span style="color: #c678dd;">await</span> <span style="color: #9cdcfe;">chromium</span>.<span style="color: #dcdcaa;">launch</span>({</div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #9cdcfe;">headless</span>: <span style="color: #56b6c2;">true</span>,</div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #9cdcfe;">channel</span>: <span style="color: #ce9178;">'chrome'</span>, <span style="color: #6a9955;">// 明确指定使用内置 Chrome</span></div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #9cdcfe;">args</span>: [</div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #ce9178;">'--no-sandbox'</span>,</div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #ce9178;">'--disable-setuid-sandbox'</span>,</div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #ce9178;">'--disable-dev-shm-usage'</span>, <span style="color: #6a9955;">// 防止内存崩溃</span></div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #ce9178;">'--disable-gpu'</span></div>
                <div>&nbsp;&nbsp;&nbsp;&nbsp;]</div>
                <div>});</div>
                <div style="color: #6a9955;">// --- 修改重点区域结束 ---</div>
              </div>
            </div>

          </n-alert>

        </n-form>
      </n-layout-sider>

      <n-layout-content content-style="height: 100%; display: flex; flex-direction: column;">
        <n-tabs type="line" animated style="height: 100%; display: flex; flex-direction: column;">
          <n-tab-pane name="code" :tab="form.runtime === 'node' ? 'Node.js 代码' : 'Python 代码'" style="height: 100%; padding: 0;">
             <Editor v-model="form.code" :language="form.runtime === 'node' ? 'javascript' : 'python'" style="height: 100%;" />
          </n-tab-pane>
          
          <n-tab-pane name="requirements" :tab="form.runtime === 'node' ? '依赖 (package.json)' : '依赖 (Requirements.txt)'" display-directive="show" style="height: 100%; padding: 0;">
            <div style="height: 100%; display: flex; flex-direction: column;">
              <div style="padding: 12px; background: #2d2d30; color: #aaa; font-size: 12px; border-bottom: 1px solid #333;">
                <n-icon style="vertical-align: middle; margin-right: 5px;"><key-icon /></n-icon>
                <span v-if="form.runtime === 'python'">请输入依赖包名称，每行一个。</span>
                <span v-else>请输入 package.json 内容或对象 (如 {"dependencies": {"axios": "^1.0"}})。</span>
              </div>
              <textarea 
                v-model="form.requirements" 
                class="simple-editor"
                :placeholder="form.runtime === 'node' ? '{\n  \'dependencies\': {\n    \'axios\': \'^1.0.0\'\n  }\n}' : '# 在此处输入 requirements.txt 内容...'"
                spellcheck="false"
              ></textarea>
            </div>
          </n-tab-pane>

          <n-tab-pane name="secrets" tab="Secrets 管理" display-directive="show" style="height: 100%; padding: 0;">
            <div style="padding: 24px; height: 100%; overflow-y: auto;">
              <n-space vertical size="large">
                 <div style="display: flex; justify-content: space-between; align-items: center;">
                    <n-text>任务独享的环境变量 (Task Secrets)</n-text>
                    <n-button size="small" type="primary" dashed @click="addLocalSecret">
                      <template #icon><n-icon><add-icon /></n-icon></template>
                      添加变量
                    </n-button>
                 </div>
                 
                 <n-empty v-if="localSecrets.length === 0" description="暂无任务私有变量" />
                 
                 <div v-for="(item, index) in localSecrets" :key="index" class="secret-row">
                    <n-input v-model:value="item.key" placeholder="Key (e.g. USERNAME)" style="flex: 1" />
                    <span style="color: #666">=</span>
                    <n-input v-model:value="item.value" placeholder="Value (支持 JSON 字符串)" style="flex: 1.5" type="textarea" :autosize="{minRows: 1, maxRows: 3}" />
                    <n-button circle size="small" type="error" secondary @click="removeLocalSecret(index)">
                       <template #icon><n-icon><trash-icon /></n-icon></template>
                    </n-button>
                 </div>
              </n-space>
            </div>
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

  <n-drawer v-model:show="showLogDrawer" width="800" placement="right">
    <n-drawer-content :title="currentLogScript?.name + ' - 执行日志'" closable body-style="padding: 0; background-color: #0d1117;">
      <template #header-extra>
        <n-button size="small" secondary @click="refreshLog"><template #icon><n-icon><refresh-icon/></n-icon></template>刷新</n-button>
      </template>
      
      <div v-if="logSteps.length > 0" class="log-container">
        <div v-for="(step, index) in logSteps" :key="index" class="log-step">
          <div class="log-step-header" @click="step.expanded = !step.expanded">
            <div class="step-left">
              <n-icon class="arrow-icon" :class="{ expanded: step.expanded }"><chevron-forward-icon /></n-icon>
              <n-icon v-if="step.status === 0" color="#238636" size="18"><checkmark-circle-icon /></n-icon>
              <n-icon v-else-if="step.status === 1" color="#f85149" size="18"><close-circle-icon /></n-icon>
              <n-icon v-else-if="step.status === 2" color="#dbab09" size="18"><ellipse-icon /></n-icon>
              <n-icon v-else color="#8b949e" size="18"><ellipse-icon /></n-icon>
              <span class="step-name">{{ step.name }}</span>
            </div>
            <span class="step-duration">{{ step.duration }}</span>
          </div>
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
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { 
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NAvatar, 
  NButton, NSpace, NIcon, NGrid, NGridItem, NCard, NTag, NPopconfirm, 
  NModal, NForm, NFormItem, NInput, NSlider, NText, NDivider, NAlert, NEmpty, useMessage,
  NTabs, NTabPane, NDrawer, NDrawerContent, NTooltip, NRadioGroup, NRadio
} from 'naive-ui'
import { 
  TimeOutline as TimeIcon, HourglassOutline as HourglassIcon, 
  Add as AddIcon, Refresh as RefreshIcon, List as ListIcon, Key as KeyIcon,
  DocumentText as DocumentTextIcon, ChevronForward as ChevronForwardIcon,
  CheckmarkCircle as CheckmarkCircleIcon, CloseCircle as CloseCircleIcon, Ellipse as EllipseIcon,
  Play as PlayIcon, Pause as PauseIcon, Trash as TrashIcon
} from '@vicons/ionicons5'
import axios from 'axios'
import Editor from '../components/Editor.vue'

const router = useRouter()
const message = useMessage()

// 状态
const activeMenu = ref('dashboard')
const scripts = ref([])          // 列表只存轻量字段（无 code / last_log）
const scriptDetailCache = ref({}) // 按需缓存完整数据（打开编辑/日志时填入）
const showModal = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const currentId = ref(null)
const showLogDrawer = ref(false)
const currentLogScript = ref(null)
const logSteps = ref([])

const form = ref({ name: '', cron: '0 8 * * *', delay: 300, code: '', requirements: '', is_active: true, runtime: 'python' })
const localSecrets = ref([])

const menuOptions = [
  { label: '任务列表', key: 'dashboard', icon: () => h(NIcon, null, { default: () => h(ListIcon) }) }
]

const handleMenuClick = (_key) => {}

const getStatusType = (status) => {
  if (status === 'Success') return 'success'
  if (status === 'Failed' || status === 'Error' || status === 'Dep Error') return 'error'
  if (status === 'Running') return 'warning'
  return 'default'
}

const getToken = () => localStorage.getItem('token')

// ⚠️修复: 统一 401 处理 —— 所有 API 调用均通过此 axios 实例，拦截器统一跳转 /login
const api = axios.create()
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

// ⚠️修复: 列表接口不再返回 code/last_log 大字段（后端已处理），前端轻量存储
const fetchScripts = async () => {
  try {
    const res = await api.get('/api/scripts')
    // 只保留列表卡片展示需要的字段，不存 code / last_log
    scripts.value = res.data.map(s => ({
      id: s.id,
      name: s.name,
      cron: s.cron || s.cron_exp,
      cron_exp: s.cron_exp,
      delay: s.delay !== undefined ? s.delay : s.random_delay,
      random_delay: s.random_delay,
      is_active: s.is_active,
      last_run: s.last_run,
      last_status: s.last_status,
      task_secrets: s.task_secrets,
    }))
    // 若日志抽屉已打开，同步刷新日志（使用完整详情接口）
    if (showLogDrawer.value && currentLogScript.value) {
      await refreshLog()
    }
  } catch (e) {
    // 401 由拦截器处理，此处只处理其他错误
    if (!e.response || e.response.status !== 401) {
      message.error('获取任务列表失败')
    }
  }
}

// ⚠️修复: 打开日志时按需请求完整数据（含 last_log），不依赖列表缓存
const openLogDrawer = async (scriptId) => {
  const light = scripts.value.find(s => s.id === scriptId)
  if (!light) return
  currentLogScript.value = light
  showLogDrawer.value = true
  logSteps.value = []
  await refreshLog()
}

const refreshLog = async () => {
  if (!currentLogScript.value) return
  try {
    const res = await api.get(`/api/scripts/${currentLogScript.value.id}`)
    const detail = res.data
    scriptDetailCache.value[detail.id] = detail
    // 更新卡片状态
    const idx = scripts.value.findIndex(s => s.id === detail.id)
    if (idx !== -1) {
      scripts.value[idx].last_status = detail.last_status
      scripts.value[idx].last_run = detail.last_run
    }
    try {
      const logs = JSON.parse(detail.last_log || '[]')
      logs.forEach((step, index) => {
        step.expanded = (step.status !== 0 && step.status !== 2) || (index === logs.length - 1)
      })
      logSteps.value = logs
    } catch (e) {
      logSteps.value = []
    }
  } catch (e) {
    if (!e.response || e.response.status !== 401) {
      message.error('获取日志失败')
    }
  }
}

const runScript = async (id) => {
  try {
    await api.post(`/api/scripts/${id}/run`, {})
    message.success('任务开始运行...')
    setTimeout(fetchScripts, 1000)
  } catch(e) {
    if (!e.response || e.response.status !== 401) message.error('运行失败')
  }
}

const toggleScriptStatus = async (script) => {
  try {
    // 切换时需要完整 payload；code/requirements 从缓存取，缓存没有时先拉取
    let detail = scriptDetailCache.value[script.id]
    if (!detail) {
      const res = await api.get(`/api/scripts/${script.id}`)
      detail = res.data
      scriptDetailCache.value[script.id] = detail
    }
    const payload = {
      name: script.name,
      cron: script.cron || script.cron_exp,
      delay: script.delay !== undefined ? script.delay : script.random_delay,
      code: detail.code,
      requirements: detail.requirements,
      task_secrets: script.task_secrets,
      is_active: !script.is_active
    }
    await api.put(`/api/scripts/${script.id}`, payload)
    message.success(script.is_active ? '任务已暂停' : '任务已恢复')
    fetchScripts()
  } catch (e) {
    if (!e.response || e.response.status !== 401) message.error('操作失败')
  }
}

const deleteScript = async (id) => {
  try {
    await api.delete(`/api/scripts/${id}`)
    delete scriptDetailCache.value[id]
    message.success('已删除')
    fetchScripts()
  } catch(e) {
    if (!e.response || e.response.status !== 401) message.error('删除失败')
  }
}

const addLocalSecret = () => { localSecrets.value.push({ key: '', value: '' }) }
const removeLocalSecret = (index) => { localSecrets.value.splice(index, 1) }

const openCreateModal = () => {
  isEdit.value = false
  form.value = { 
    name: '', 
    cron: '0 8 * * *', 
    delay: 300, 
    code: 'import os\nfrom loguru import logger\n\nlogger.info("Task Start...")\n',
    requirements: '',
    is_active: true,
    runtime: 'python'
  }
  localSecrets.value = []
  showModal.value = true
}

// ⚠️修复: 编辑时按需拉取完整数据（含 code），不再依赖列表缓存
const editScript = async (scriptId) => {
  let detail = scriptDetailCache.value[scriptId]
  if (!detail) {
    try {
      const res = await api.get(`/api/scripts/${scriptId}`)
      detail = res.data
      scriptDetailCache.value[scriptId] = detail
    } catch (e) {
      if (!e.response || e.response.status !== 401) message.error('加载脚本数据失败')
      return
    }
  }

  isEdit.value = true
  currentId.value = detail.id
  
  let codeStr = detail.code || ''
  let runtime = 'python'
  if (codeStr.trim().startsWith('// runtime: node')) {
    runtime = 'node'
    codeStr = codeStr.replace(/^\s*\/\/\s*runtime:\s*node\r?\n?/, '')
  }

  form.value = { 
    name: detail.name, 
    cron: detail.cron || detail.cron_exp, 
    delay: detail.delay !== undefined ? detail.delay : detail.random_delay, 
    code: codeStr,
    requirements: detail.requirements || '',
    is_active: detail.is_active,
    runtime
  }
  
  localSecrets.value = []
  try {
    const secretsObj = JSON.parse(detail.task_secrets || '{}')
    for (const [k, v] of Object.entries(secretsObj)) {
      localSecrets.value.push({ key: k, value: v })
    }
  } catch (e) {
    console.error('解析 Secrets 失败', e)
  }
  
  showModal.value = true
}

const saveData = async () => {
  if (!form.value.name) return message.warning('请输入名称')
  saving.value = true
  try {
    const secretsObj = {}
    localSecrets.value.forEach(item => { if(item.key) secretsObj[item.key] = item.value })

    let finalCode = form.value.code
    if (form.value.runtime === 'node') {
      if (!finalCode.trim().startsWith('// runtime: node')) finalCode = '// runtime: node\n' + finalCode
    } else {
      if (finalCode.trim().startsWith('// runtime: node')) finalCode = finalCode.replace(/^\s*\/\/\s*runtime:\s*node\r?\n?/, '')
    }

    const payload = {
      name: form.value.name,
      cron: form.value.cron,
      delay: form.value.delay,
      code: finalCode,
      requirements: form.value.requirements,
      is_active: form.value.is_active,
      task_secrets: JSON.stringify(secretsObj)
    }
    
    if (isEdit.value) {
      await api.put(`/api/scripts/${currentId.value}`, payload)
      // 更新后清除缓存，下次打开编辑器重新拉取最新数据
      delete scriptDetailCache.value[currentId.value]
    } else {
      await api.post('/api/scripts', payload)
    }
    
    message.success('保存成功')
    showModal.value = false
    fetchScripts()
  } catch (e) {
    if (!e.response || e.response.status !== 401) {
      message.error('保存失败: ' + (e.response?.data?.detail || e.message))
    }
  } finally {
    saving.value = false
  }
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
.paused-card { opacity: 0.7; border-style: dashed; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.script-name { font-weight: 600; font-size: 16px; }
.info-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; color: #aaa; }
.user-info { position: absolute; bottom: 24px; left: 24px; display: flex; align-items: center; }
:deep(.n-tabs) { height: 100%; display: flex; flex-direction: column; }
:deep(.n-tabs .n-tabs-pane-wrapper) { flex: 1; overflow: hidden; }
:deep(.n-tab-pane) { height: 100%; display: flex; flex-direction: column; }
.simple-editor { flex: 1; width: 100%; background: #1e1e1e; color: #d4d4d4; border: none; padding: 15px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 14px; line-height: 1.5; resize: none; outline: none; }
.secret-row { display: flex; align-items: center; gap: 10px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 6px; }
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
