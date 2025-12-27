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
                    确定要立即执行该脚本吗？这将忽略随机延时。
                  </n-popconfirm>
                  
                  <n-button size="small" secondary type="warning" @click="editScript(script)">编辑</n-button>
                  
                  <n-popconfirm @positive-click="deleteScript(script.id)">
                    <template #trigger>
                      <n-button size="small" secondary type="error">删除</n-button>
                    </template>
                    确定删除该任务？
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

  <!-- 编辑/新建 模态框 (全屏感) -->
  <n-modal v-model:show="showModal" preset="card" style="width: 90vw; height: 90vh; max-width: 1400px;" :title="isEdit ? '编辑脚本' : '新建脚本'">
    <n-layout has-sider style="height: 100%">
      <!-- 左侧：设置 -->
      <n-layout-sider width="300" content-style="padding-right: 20px;">
        <n-form label-placement="top">
          <n-form-item label="任务名称">
            <n-input v-model:value="form.name" placeholder="例如: 京东签到" />
          </n-form-item>
          <n-form-item label="Cron 表达式">
            <n-input v-model:value="form.cron" placeholder="0 8 * * *" />
            <n-text depth="3" style="font-size: 12px;">分 时 日 月 周</n-text>
          </n-form-item>
          <n-form-item :label="`随机延时: ${form.delay} 秒`">
            <n-slider v-model:value="form.delay" :max="1800" :step="10" />
            <n-text depth="3" style="font-size: 12px;">防止被识别为机器人，建议 > 60s</n-text>
          </n-form-item>
          <n-divider />
          <n-alert type="info" :show-icon="false" title="Tips">
            使用 <n-text code>os.environ['KEY']</n-text> 读取 Secrets。
          </n-alert>
        </n-form>
      </n-layout-sider>

      <!-- 右侧：代码编辑器 -->
      <n-layout-content>
        <!-- 引入之前的 Editor 组件 -->
        <Editor v-model="form.code" />
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
  NModal, NForm, NFormItem, NInput, NSlider, NText, NDivider, NAlert, NEmpty, useMessage 
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
import Editor from '../components/Editor.vue' // 引入组件

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
  code: 'import os\nimport time\n\nprint("Task started at " + time.ctime())\n# print(os.environ["MY_SECRET"])\nprint("Task finished!")'
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
  if (status === 'Failed' || status === 'Error') return 'error'
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
  form.value = { name: '', cron: '0 8 * * *', delay: 300, code: 'import os\n\nprint("Hello FluxTask")' }
  showModal.value = true
}

const editScript = (script) => {
  isEdit.value = true
  currentId.value = script.id
  form.value = { 
    name: script.name, 
    cron: script.cron_exp, 
    delay: script.random_delay, 
    code: script.code 
  }
  showModal.value = true
}

const saveData = async () => {
  if (!form.value.name) return message.warning('请输入名称')
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      cron: form.value.cron, // 后端需注意字段名匹配
      delay: form.value.delay,
      code: form.value.code
    }
    
    if (isEdit.value) {
      await axios.put(`/api/scripts/${currentId.value}`, payload, { headers: { Authorization: `Bearer ${getToken()}` } })
    } else {
      await axios.post('/api/scripts', payload, { headers: { Authorization: `Bearer ${getToken()}` } })
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
</style>
