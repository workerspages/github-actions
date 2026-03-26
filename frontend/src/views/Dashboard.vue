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
                  <n-button size="small" secondary @click="openLogDrawer(script)">
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
                  
                  <n-button size="small" secondary type="warning" @click="editScript(script)">编辑</n-button>
                  
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
              <p style="margin: 0 0 6px 0; font-size: 11px; color: #aaa;">默认执行 <b>Python</b>。若要执行 <b>Node.js</b>，需在首行添加魔法注释：</p>
              <div style="background: #1e1e1e; padding: 10px; border-radius: 6px; font-family: 'Fira Code', Consolas, monospace; font-size: 11px; color: #d4d4d4;">
                <span style="color: #6a9955;">// runtime: node</span>
              </div>
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
          <n-tab-pane name="code" tab="Python 代码" style="height: 100%; padding: 0;">
             <Editor v-model="form.code" style="height: 100%;" />
          </n-tab-pane>
          
          <n-tab-pane name="requirements" tab="依赖 (Requirements.txt)" display-directive="show" style="height: 100%; padding: 0;">
            <div style="height: 100%; display: flex; flex-direction: column;">
              <div style="padding: 12px; background: #2d2d30; color: #aaa; font-size: 12px; border-bottom: 1px solid #333;">
                <n-icon style="vertical-align: middle; margin-right: 5px;"><key-icon /></n-icon>
                请输入依赖包名称，每行一个。
              </div>
              <textarea 
                v-model="form.requirements" 
                class="simple-editor"
                placeholder="# 在此处输入 requirements.txt 内容..."
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
        <n-button size="small" secondary @click="fetchScripts"><template #icon><n-icon><refresh-icon/></n-icon></template>刷新</n-button>
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
  NTabs, NTabPane, NDrawer, NDrawerContent, NTooltip
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
const scripts = ref([])
const showModal = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const currentId = ref(null)
const showLogDrawer = ref(false)
const currentLogScript = ref(null)
const logSteps = ref([])

// 表单数据，增加 task_secrets
const form = ref({ name: '', cron: '0 8 * * *', delay: 300, code: '', requirements: '', is_active: true })
// 本地编辑 Secrets 的临时数组
const localSecrets = ref([])

const menuOptions = [
  { label: '任务列表', key: 'dashboard', icon: () => h(NIcon, null, { default: () => h(ListIcon) }) }
]

const handleMenuClick = (key) => {
  // 仅保留任务列表，无额外逻辑
}

const getStatusType = (status) => {
  if (status === 'Success') return 'success'
  if (status === 'Failed' || status === 'Error' || status === 'Dep Error') return 'error'
  if (status === 'Running') return 'warning'
  return 'default'
}

const getToken = () => localStorage.getItem('token')

const fetchScripts = async () => {
  try {
    const res = await axios.get('/api/scripts', { headers: { Authorization: `Bearer ${getToken()}` } })
    scripts.value = res.data
    if (showLogDrawer.value && currentLogScript.value) {
      const updated = scripts.value.find(s => s.id === currentLogScript.value.id)
      if (updated) openLogDrawer(updated)
    }
  } catch (e) {
    if (e.response && e.response.status === 401) router.push('/login')
  }
}

const openLogDrawer = (script) => {
  currentLogScript.value = script
  showLogDrawer.value = true
  try {
    const logs = JSON.parse(script.last_log || '[]')
    logs.forEach((step, index) => {
      step.expanded = (step.status !== 0 && step.status !== 2) || (index === logs.length - 1)
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
    setTimeout(fetchScripts, 1000)
  } catch(e) {
    message.error('运行失败')
  }
}

// 切换暂停/恢复
const toggleScriptStatus = async (script) => {
  try {
    // 构造完整的更新对象，只修改 is_active
    const payload = {
      name: script.name,
      cron: script.cron || script.cron_exp,
      delay: script.delay || script.random_delay,
      code: script.code,
      requirements: script.requirements,
      task_secrets: script.task_secrets,
      is_active: !script.is_active // 切换状态
    }
    await axios.put(`/api/scripts/${script.id}`, payload, { headers: { Authorization: `Bearer ${getToken()}` } })
    message.success(script.is_active ? '任务已暂停' : '任务已恢复')
    fetchScripts()
  } catch (e) {
    message.error('操作失败')
  }
}

const deleteScript = async (id) => {
  try {
    await axios.delete(`/api/scripts/${id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
    message.success('已删除')
    fetchScripts()
  } catch(e) {
    message.error('删除失败')
  }
}

// 本地 Secrets 操作
const addLocalSecret = () => {
  localSecrets.value.push({ key: '', value: '' })
}
const removeLocalSecret = (index) => {
  localSecrets.value.splice(index, 1)
}

const openCreateModal = () => {
  isEdit.value = false
  form.value = { 
    name: '', 
    cron: '0 8 * * *', 
    delay: 300, 
    code: 'import os\nfrom loguru import logger\n\nlogger.info("Task Start...")\n',
    requirements: '',
    is_active: true
  }
  localSecrets.value = [] // 清空本地 Secrets
  showModal.value = true
}

const editScript = (script) => {
  isEdit.value = true
  currentId.value = script.id
  form.value = { 
    name: script.name, 
    cron: script.cron || script.cron_exp, 
    delay: script.delay !== undefined ? script.delay : script.random_delay, 
    code: script.code,
    requirements: script.requirements || '',
    is_active: script.is_active
  }
  
  // 解析 task_secrets JSON 字符串到本地数组
  localSecrets.value = []
  try {
    const secretsObj = JSON.parse(script.task_secrets || '{}')
    for (const [k, v] of Object.entries(secretsObj)) {
      localSecrets.value.push({ key: k, value: v })
    }
  } catch (e) {
    console.error("解析 Secrets 失败", e)
  }
  
  showModal.value = true
}

const saveData = async () => {
  if (!form.value.name) return message.warning('请输入名称')
  saving.value = true
  try {
    // 将本地 Secrets 数组转换为 JSON 字符串
    const secretsObj = {}
    localSecrets.value.forEach(item => {
      if(item.key) secretsObj[item.key] = item.value
    })

    const payload = {
      name: form.value.name,
      cron: form.value.cron,
      delay: form.value.delay,
      code: form.value.code,
      requirements: form.value.requirements,
      is_active: form.value.is_active,
      task_secrets: JSON.stringify(secretsObj) // 序列化
    }
    const headers = { Authorization: `Bearer ${getToken()}` }
    
    if (isEdit.value) {
      await axios.put(`/api/scripts/${currentId.value}`, payload, { headers })
    } else {
      await axios.post('/api/scripts', payload, { headers })
    }
    
    message.success('保存成功')
    showModal.value = false
    fetchScripts()
  } catch (e) {
    message.error('保存失败: ' + (e.response?.data?.detail || e.message))
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
/* 暂停状态的卡片样式 */
.paused-card { opacity: 0.7; border-style: dashed; }

.card-header { display: flex; justify-content: space-between; align-items: center; }
.script-name { font-weight: 600; font-size: 16px; }
.info-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; color: #aaa; }
.user-info { position: absolute; bottom: 24px; left: 24px; display: flex; align-items: center; }
:deep(.n-tabs) { height: 100%; display: flex; flex-direction: column; }
:deep(.n-tabs .n-tabs-pane-wrapper) { flex: 1; overflow: hidden; }
:deep(.n-tab-pane) { height: 100%; display: flex; flex-direction: column; }

.simple-editor {
  flex: 1; 
  width: 100%; 
  background: #1e1e1e; 
  color: #d4d4d4; 
  border: none; 
  padding: 15px; 
  font-family: 'Fira Code', 'Consolas', monospace; 
  font-size: 14px;
  line-height: 1.5;
  resize: none; 
  outline: none;
}

.secret-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
}

/* 日志样式 */
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
