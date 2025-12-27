<template>
  <n-layout style="height: 100vh">
    <n-layout-header bordered style="padding: 20px;">
      <n-page-header subtitle="管理脚本运行所需的环境变量 (如 COOKIE, TOKEN)" on-back="() => $router.push('/')">
        <template #title>Secrets 管理</template>
        <template #extra>
          <n-button type="primary" @click="showModal = true">添加 Secret</n-button>
        </template>
      </n-page-header>
    </n-layout-header>

    <n-layout-content style="padding: 24px;">
      <n-data-table :columns="columns" :data="secrets" :bordered="false" />
    </n-layout-content>
  </n-layout>

  <!-- 添加 Secret 弹窗 -->
  <n-modal v-model:show="showModal" preset="card" title="添加/更新 Secret" style="width: 500px">
    <n-form>
      <n-form-item label="Name (Key)">
        <n-input v-model:value="form.key" placeholder="例如: JD_COOKIE" />
      </n-form-item>
      <n-form-item label="Secret (Value)">
        <n-input type="textarea" v-model:value="form.value" placeholder="输入具体的值..." />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-button type="primary" block @click="saveSecret">保存</n-button>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { NLayout, NLayoutHeader, NLayoutContent, NPageHeader, NButton, NDataTable, NModal, NForm, NFormItem, NInput, useMessage, NTag } from 'naive-ui'
import axios from 'axios'
import { useRouter } from 'vue-router'

const router = useRouter()
const message = useMessage()
const secrets = ref([])
const showModal = ref(false)
const form = ref({ key: '', value: '' })

const columns = [
  { title: 'Name', key: 'key', render: (row) => h(NTag, { type: 'info', bordered: false }, { default: () => row.key }) },
  { title: 'Value', key: 'value', render: () => '******' }, // 永远不显示明文
  { title: 'Created', key: 'id' } // 简单展示ID作为占位
]

const fetchSecrets = async () => {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/secrets', { headers: { Authorization: `Bearer ${token}` } })
    secrets.value = res.data
  } catch (e) {
    message.error('加载失败')
  }
}

const saveSecret = async () => {
  if (!form.value.key || !form.value.value) return
  try {
    const token = localStorage.getItem('token')
    await axios.post('/api/secrets', form.value, { headers: { Authorization: `Bearer ${token}` } })
    message.success('Secret 保存成功')
    showModal.value = false
    form.value = { key: '', value: '' }
    fetchSecrets()
  } catch (e) {
    message.error('保存失败')
  }
}

onMounted(fetchSecrets)
</script>
