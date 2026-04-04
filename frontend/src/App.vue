<script setup>
import { ref } from 'vue'
import axios from 'axios'

const message = ref('👇 点击按钮测试后端连接')
const loading = ref(false)

async function testBackend() {
  loading.value = true
  message.value = '🔄 请求中...'
  try {
    const res = await axios.post('http://127.0.0.1:8000/api/skill', {
      query: '测试指令'
    })
    message.value = res.data.result
  } catch (e) {
    message.value = '❌ 调用失败：' + e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="padding: 24px; text-align: center; font-family: sans-serif;">
    <h2>🧪 最简联调测试</h2>
    <p style="color: #666; margin: 20px 0;">{{ message }}</p>
    <button 
      @click="testBackend" 
      :disabled="loading"
      style="padding: 10px 28px; font-size: 15px; cursor: pointer; background: #42b983; color: white; border: none; border-radius: 6px;"
    >
      {{ loading ? '请求中...' : '调用后端 API' }}
    </button>
  </div>
</template>