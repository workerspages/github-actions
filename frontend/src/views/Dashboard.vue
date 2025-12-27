<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider bordered width="240" style="background: #18181c">
      <div class="logo">FluxTask</div>
      <n-menu :options="menuOptions" />
    </n-layout-sider>
    
    <n-layout>
      <n-layout-header bordered class="header">
        <h2>任务面板</h2>
        <n-button type="primary" @click="showAddModal = true">新建脚本</n-button>
      </n-layout-header>
      
      <n-layout-content content-style="padding: 24px;">
        <n-grid :x-gap="12" :y-gap="12" :cols="3">
          <n-grid-item v-for="script in scripts" :key="script.id">
            <n-card :title="script.name" hoverable>
              <template #header-extra>
                <n-tag :type="script.last_status === 'Success' ? 'success' : 'error'">
                  {{ script.last_status || '未运行' }}
                </n-tag>
              </template>
              <p>Cron: {{ script.cron_exp }}</p>
              <p>随机延时: 0~{{ script.random_delay }}s</p>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-layout-content>
    </n-layout>
  </n-layout>

  <!-- 新建/编辑 模态框 -->
  <n-modal v-model:show="showAddModal" preset="card" style="width: 800px; height: 600px" title="编辑脚本">
    <n-form>
      <n-form-item label="脚本名称"><n-input v-model:value="form.name" /></n-form-item>
      <n-form-item label="Cron表达式 (分 时 日 月 周)">
         <n-input v-model:value="form.cron" placeholder="0 9 * * *" />
      </n-form-item>
      <n-form-item label="随机延时 (秒) - 反爬虫关键">
         <n-slider v-model:value="form.delay" :max="600" :step="10" />
         <span style="margin-left:10px">{{ form.delay }}s</span>
      </n-form-item>
      <n-form-item label="Python代码">
         <n-input type="textarea" v-model:value="form.code" :rows="15" placeholder="import os..." />
         <!-- 这里实际建议集成 monaco-editor 组件 -->
      </n-form-item>
    </n-form>
    <template #footer>
      <n-button type="primary" @click="saveScript">保存并激活</n-button>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NButton, NCard, NGrid, NGridItem, NTag, NModal, NForm, NFormItem, NInput, NSlider } from 'naive-ui'
import axios from 'axios'

const scripts = ref([])
const showAddModal = ref(false)
const form = ref({ name: '', cron: '0 8 * * *', delay: 120, code: 'import os\nprint("Hello World")' })

// 获取脚本列表
const fetchScripts = async () => {
  const token = localStorage.getItem('token')
  const res = await axios.get('/api/scripts', { headers: { Authorization: `Bearer ${token}` } })
  scripts.value = res.data
}

const saveScript = async () => {
  const token = localStorage.getItem('token')
  await axios.post('/api/scripts', form.value, { headers: { Authorization: `Bearer ${token}` } })
  showAddModal.value = false
  fetchScripts()
}

onMounted(fetchScripts)
</script>

<style scoped>
.logo { padding: 20px; font-size: 24px; font-weight: bold; color: #63e2b7; text-align: center; }
.header { padding: 15px 24px; display: flex; justify-content: space-between; align-items: center; }
</style>
