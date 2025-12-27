<template>
  <div class="login-bg">
    <n-card class="login-card" :bordered="false" size="huge">
      <div class="header">
        <h1 class="title">GitHub Actions</h1>
        <p class="subtitle">私有化任务调度终端</p>
      </div>
      
      <n-form ref="formRef" :model="form" :rules="rules">
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="form.username" placeholder="Admin" />
        </n-form-item>
        <n-form-item path="password" label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            placeholder="Password"
            @keyup.enter="handleLogin"
          />
        </n-form-item>
      </n-form>
      
      <n-button type="primary" block size="large" @click="handleLogin" :loading="loading">
        进入系统
      </n-button>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'
import axios from 'axios'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const form = ref({ username: '', password: '' })

const rules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' }
}

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  
  // 发送 x-www-form-urlencoded 格式
  const params = new URLSearchParams()
  params.append('username', form.value.username)
  params.append('password', form.value.password)

  try {
    const res = await axios.post('/token', params)
    localStorage.setItem('token', res.data.access_token)
    message.success('身份验证成功')
    router.push('/')
  } catch (err) {
    message.error('登录失败：用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-bg {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at center, #2e3338 0%, #101014 100%);
}
.login-card {
  width: 400px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}
.title {
  text-align: center;
  font-size: 2.5rem;
  margin: 0;
  background: -webkit-linear-gradient(315deg, #42d392 25%, #647eff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.subtitle {
  text-align: center;
  color: #888;
  margin-bottom: 30px;
}
</style>
