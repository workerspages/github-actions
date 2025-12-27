<template>
  <n-layout style="height: 100vh">
    <n-layout-header bordered style="padding: 20px;">
      <n-page-header subtitle="管理脚本运行所需的环境变量 (如 COOKIE, TOKEN)" @back="handleBack">
        <template #title>Secrets 管理</template>
        <template #extra>
          <n-button type="primary" @click="openCreate">添加 Secret</n-button>
        </template>
      </n-page-header>
    </n-layout-header>

    <n-layout-content style="padding: 24px;">
      <n-data-table :columns="columns" :data="secrets" :bordered="false" />
    </n-layout-content>
  </n-layout>

  <!-- 添加/修改 Secret 弹窗 -->
  <n-modal v-model:show="showModal" preset="card" :title="isEdit ? '更新 Secret' : '添加 Secret'" style="width: 500px">
    <n-form>
      <n-form-item label="Name (Key)">
        <n-input v-model:value="form.key" placeholder="例如: JD_COOKIE" :disabled="isEdit" />
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
import { useRouter } from 'vue-router'
import { NLayout, NLayoutHeader, NLayoutContent, NPageHeader, NButton, NDataTable, NModal, NForm, NFormItem, NInput, useMessage, NTag, NSpace, NPopconfirm } from 'naive-ui'
import axios from 'axios'

const router = useRouter()
const message = useMessage()
const secrets = ref([])
const showModal = ref(false)
const isEdit = ref(false)
const form = ref({ key: '', value: '' })

// 表格列定义
const columns = [
  { title: 'Name', key: 'key', render: (row) => h(NTag, { type: 'info', bordered: false }, { default: () => row.key }) },
  { title: 'Value', key: 'value', render: () => '******' }, 
  { title: 'ID', key: 'id', width: 80 },
  { 
    title: 'Actions', 
    key: 'actions',
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, {
            size: 'small',
            secondary: true,
            onClick: () => openEdit(row)
          }, { default: () => '修改' }),
          h(
            NPopconfirm,
            {
              onPositiveClick: () => deleteSecret(row.id)
            },
            {
              trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' }, { default: () => '删除' }),
              default: () => '确定删除这个 Secret 吗？'
            }
          )
        ]
      })
    }
  }
]

const handleBack = () => router.push('/')

const fetchSecrets = async () => {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/secrets', { headers: { Authorization: `Bearer ${token}` } })
    secrets.value = res.data
  } catch (e) {
    message.error('加载失败')
  }
}

const openCreate = () => {
  isEdit.value = false
  form.value = { key: '', value: '' }
  showModal.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  form.value = { key: row.key, value: '' } // value 为空，提示用户重新输入
  showModal.value = true
}

const deleteSecret = async (id) => {
  try {
    const token = localStorage.getItem('token')
    await axios.delete(`/api/secrets/${id}`, { headers: { Authorization: `Bearer ${token}` } })
    message.success('已删除')
    fetchSecrets()
  } catch(e) {
    message.error('删除失败')
  }
}

const saveSecret = async () => {
  if (!form.value.key || !form.value.value) return message.warning('请填写完整')
  try {
    const token = localStorage.getItem('token')
    // 后端 api/secrets 是 create_or_update，根据 key 判断
    await axios.post('/api/secrets', form.value, { headers: { Authorization: `Bearer ${token}` } })
    message.success('保存成功')
    showModal.value = false
    fetchSecrets()
  } catch (e) {
    message.error('保存失败')
  }
}

onMounted(fetchSecrets)
</script>
