<script setup>
import { NConfigProvider, NGlobalStyle, NMessageProvider, darkTheme } from 'naive-ui'
import { RouterView } from 'vue-router'
</script>

<template>
  <!-- 强制使用深色主题，大气 -->
  <n-config-provider :theme="darkTheme">
    <n-global-style />
    <n-message-provider>
      <div class="app-container">
        <router-view />
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
body { margin: 0; background-color: #101014; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
.app-container { min-height: 100vh; }
</style>
