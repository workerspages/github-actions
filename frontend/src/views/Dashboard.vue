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
      <!-- 顶部 Header -->
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

      <!-- 内容区域 -->
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
                <div class="info-row">
                  <n-icon><time-icon /></n-icon>
                  <span>{{ script.cron_exp }}</span>
                </div>
                <div class="info-row">
                  <n-icon><hourglass-icon /></n-icon>
                  <span>延迟: 0~{{ script.random_delay }}s</span>
                </div>
                <div class="info-row" style="margin-top: 10px; font-size: 12px; color: #666;">
                  上次运行: {{ script.last_run || '无' }}
                </div>
              </div>

              <template #action>
                <n-space justify="end">
                  <n-popconfirm @positive-click="runScript(script.id)">
                    <template #trigger>
                      <n-button size="small" secondary type="success">运行</n-button>
                    </template>
                    确定要立即执行该脚本吗？<br>如果定义了新依赖，首次运行会自动安装。
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

        <!-- 如果没数据 -->
        <n-empty v-if="scripts.length === 0" description="暂无任务，点击右上角新建" style="margin-top: 100px" />
      </n-layout-content>
    </n-layout>
  </n-layout>

  <!-- 编辑/新建 模态框 -->
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
      <!-- 左侧：设置 (允许独立滚动) -->
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
          <n-alert type="info" :show-icon="false" title="Tips">
            <p>Secrets: <n-text code>os.environ['KEY']</n-text></p>
            <p>依赖管理: 请在右侧 <b>"依赖"</b> 标签页填写 <n-text code>requirements.txt</n-text> 内容。</p>
          </n-alert>
        </n-form>
      </n-layout-sider>

      <!-- 右侧：Tabs (代码 | 依赖) -->
      <n-layout-content content-style="height: 100%; display: flex; flex-direction: column;">
        <n-tabs type="line" animated style="height: 100%; display: flex; flex-direction: column;">
          <!-- Tab 1: 代码 -->
          <n-tab-pane name="code" tab="Python 代码" style="height: 100%; padding: 0;">
             <Editor v-model="form.code" style="height: 100%;" />
          </n-tab-pane>
          
          <!-- Tab 2: 依赖 -->
          <n-tab-pane name="requirements" tab="依赖 (Requirements.txt)" display-directive="show" style="height: 100%; padding: 0;">
            <div style="height: 100%; display: flex; flex-direction: column;">
              <div style="padding: 12px; background: #2d2d30; color: #aaa; font-size: 12px; border-bottom: 1px solid #333;">
                <n-icon style="vertical-align: middle; margin-right: 5px;"><key-icon /></n-icon>
                请输入依赖包名称，每行一个。例如：
                <span style="color: #63e2b7; margin-left: 5px;">requests==2.31.0</span>
                <span style="color: #63e2b7; margin-left: 10px;">selenium</span>
              </div>
              <textarea 
                v-model="form.requirements" 
                style="
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
                "
                placeholder="# 在此处输入 requirements.txt 内容..."
                spellcheck="false"
              ></textarea>
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
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { 
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NAvatar, 
  NButton, NSpace, NIcon, NGrid, NGridItem, NCard, NTag, NPopconfirm, 
  NModal, NForm, NFormItem, NInput, NSlider, NText, NDivider, NAlert, NEmpty, useMessage,
  NTabs, NTabPane
} from 'naive-ui'
import { 
  TimeOutline as TimeIcon, 
  HourglassOutline as HourglassIcon, 
  Add as AddIcon, 
  Refresh as RefreshIcon,
  List as ListIcon,
  Key as KeyIcon
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

const form = ref({
  name: '',
  cron: '0 8 * * *',
  delay: 300,
  code: '',
  requirements: '' 
})

// 菜单配置
const menuOptions = [
  { label: '任务列表', key: 'dashboard', icon: () => h(NIcon, null, { default: () => h(ListIcon) }) },
  { label: 'Secrets 管理', key: 'secrets', icon: () => h(NIcon, null, { default: () => h(KeyIcon) }) }
]

const handleMenuClick = (key) => {
  if (key === 'secrets') router.push('/secrets')
}

// 辅助函数
const getStatusType = (status) => {
  if (status === 'Success') return 'success'
  if (status === 'Failed' || status === 'Error' || status === 'Dep Error') return 'error'
  return 'default'
}

// API 操作
const getToken = () => localStorage.getItem('token')

const fetchScripts = async () => {
  try {
    const res = await axios.get('/api/scripts', { headers: { Authorization: `Bearer ${getToken()}` } })
    scripts.value = res.data
  } catch (e) {
    if (e.response && e.response.status === 401) router.push('/login')
  }
}

const runScript = async (id) => {
  try {
    await axios.post(`/api/scripts/${id}/run`, {}, { headers: { Authorization: `Bearer ${getToken()}` } })
    message.success('指令已发送，后台运行中')
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
  form.value = { 
    name: '', 
    cron: '0 8 * * *', 
    delay: 300, 
    code: 'import os\nimport time\nfrom loguru import logger\n\nlogger.info("Task Start...")\n',
    requirements: ''
  }
  showModal.value = true
}

const editScript = (script) => {
  isEdit.value = true
  currentId.value = script.id
  form.value = { 
    name: script.name, 
    cron: script.cron_exp, 
    delay: script.random_delay, 
    code: script.code,
    requirements: script.requirements || ''
  }
  showModal.value = true
}

const saveData = async () => {
  if (!form.value.name) return message.warning('请输入名称')
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      cron: form.value.cron,
      delay: form.value.delay,
      code: form.value.code,
      requirements: form.value.requirements
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
.logo {
  font-size: 24px;
  font-weight: 700;
  color: #63e2b7;
  margin-bottom: 30px;
  text-align: center;
  letter-spacing: 1px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  height: 64px;
  background: rgba(255,255,255,0.02);
}
.header-title {
  font-size: 18px;
  font-weight: 500;
}
.content-bg {
  background-color: #101014;
}
.script-card {
  border-radius: 12px;
  transition: transform 0.2s;
  background: #18181c;
  border: 1px solid #2d2d30;
}
.script-card:hover {
  transform: translateY(-4px);
  border-color: #63e2b7;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.script-name {
  font-weight: 600;
  font-size: 16px;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  color: #aaa;
}
.user-info {
  position: absolute;
  bottom: 24px;
  left: 24px;
  display: flex;
  align-items: center;
}

/* --- 关键修复：强制 Tabs 撑满高度，防止内容塌陷 --- */
:deep(.n-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}
:deep(.n-tabs .n-tabs-pane-wrapper) {
  flex: 1; /* 让 Pane 包装器撑满剩余空间 */
  overflow: hidden;
}
:deep(.n-tab-pane) {
  height: 100%; /* 让具体 Pane 撑满包装器 */
  display: flex;
  flex-direction: column;
}
</style>
