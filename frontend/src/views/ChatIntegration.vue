<template>
  <div class="chatbot">
    <el-page-header @back="$router.back()" content="即时通讯助手" />

    <el-card class="chat-card">
      <template #header>
        <div class="chat-header">
          <el-space>
            <el-select v-model="meta.source" size="small" style="width: 120px">
              <el-option label="微信" value="wechat" />
              <el-option label="邮件" value="email" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-input v-model="meta.sender" size="small" style="width: 180px" placeholder="发送者(可选)" />
          </el-space>
          <div class="chat-hint">输入“帮助”查看指令</div>
        </div>
      </template>

      <div ref="chatBodyRef" class="chat-body">
        <div v-if="chatMessages.length === 0" class="chat-empty">
          输入一段微信群/邮件内容，我会提取其中的租赁/交易/联系人/时间/金额等信息，并输出结构化结果。
        </div>

        <div v-for="m in chatMessages" :key="m.localId" class="chat-row" :class="m.role">
          <div class="bubble">
            <div class="bubble-meta">
              <span class="bubble-role">{{ m.role === 'user' ? '你' : 'Bot' }}</span>
              <span class="bubble-time">{{ formatTime(m.timestamp) }}</span>
            </div>
            <div class="bubble-text">
              {{ m.content }}
            </div>

            <div v-if="m.structuredData" class="bubble-structured">
              <el-collapse>
                <el-collapse-item title="结构化结果">
                  <pre class="json-block">{{ formatJson(m.structuredData) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <div class="chat-attachments">
          <el-upload
            v-model:file-list="pendingFiles"
            multiple
            :auto-upload="false"
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.zip"
          >
            <el-button size="small">选择附件</el-button>
          </el-upload>
        </div>
        <div class="chat-compose">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="输入消息，Enter发送，Shift+Enter换行"
            @keydown.enter.exact.prevent="send"
          />
          <div class="chat-actions">
            <el-button type="primary" @click="send" :loading="sending" :disabled="!inputText.trim() && pendingFiles.length === 0">
              发送
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const meta = ref({
  source: 'wechat',
  sender: '',
})

const chatBodyRef = ref(null)
const chatMessages = ref([])
const inputText = ref('')
const pendingFiles = ref([])
const sending = ref(false)
const sessionId = ref(localStorage.getItem('chat_session_id') || '')

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return
  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const appendMessage = async (msg) => {
  chatMessages.value.push(msg)
  await scrollToBottom()
}

const appendSystemMessage = async (content, structuredData = null) => {
  await appendMessage({
    localId: `s_${Date.now()}`,
    role: 'assistant',
    content,
    timestamp: Date.now(),
    structuredData
  })
}

onMounted(async () => {
  await appendSystemMessage('你好，我是文档数据提取助手。输入“帮助”查看可用指令。')
})

const send = async () => {
  const content = inputText.value.trim()
  const hasFiles = pendingFiles.value.length > 0
  if (!content && !hasFiles) return

  const now = Date.now()
  inputText.value = ''

  await appendMessage({
    localId: `u_${now}`,
    role: 'user',
    content,
    timestamp: now,
    structuredData: null
  })

  sending.value = true
  try {
    const fd = new FormData()
    fd.append('source', meta.value.source)
    if (meta.value.sender) fd.append('sender', meta.value.sender)
    fd.append('content', content || '')
    if (sessionId.value) fd.append('session_id', sessionId.value)
    for (const f of pendingFiles.value) {
      if (f.raw) fd.append('files', f.raw)
    }

    const response = await axios.post('/chat/agent/message', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (!response.data.success) {
      throw new Error(response.data.error || '处理失败')
    }

    if (response.data.session_id) {
      sessionId.value = response.data.session_id
      localStorage.setItem('chat_session_id', sessionId.value)
    }

    pendingFiles.value = []

    const botText = response.data.assistant_message || '已完成。'
    const structuredData = response.data.structured_data || null

    await appendMessage({
      localId: `b_${Date.now()}`,
      role: 'assistant',
      content: botText,
      timestamp: Date.now(),
      structuredData
    })
  } catch (e) {
    await appendMessage({
      localId: `b_${Date.now()}`,
      role: 'assistant',
      content: `处理失败：${e?.message || '未知错误'}`,
      timestamp: Date.now(),
      structuredData: null
    })
  } finally {
    sending.value = false
  }
}

const formatTime = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

const formatJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}
</script>

<style scoped>
.chatbot {
  padding: 20px;
}

.chat-card {
  margin-top: 20px;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-hint {
  color: #909399;
  font-size: 13px;
}

.chat-body {
  height: calc(100vh - 320px);
  min-height: 420px;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.chat-empty {
  color: #909399;
  text-align: center;
  padding: 40px 20px;
}

.chat-row {
  display: flex;
  margin-bottom: 12px;
}

.chat-row.user {
  justify-content: flex-end;
}

.chat-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 760px;
  width: fit-content;
  padding: 10px 12px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.chat-row.user .bubble {
  background: #ecf5ff;
}

.bubble-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
}

.bubble-structured {
  margin-top: 10px;
}

.json-block {
  margin: 0;
  padding: 10px;
  background: #0b1020;
  color: #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  overflow-x: auto;
}

.chat-input {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-attachments {
  display: flex;
  justify-content: flex-start;
}

.chat-compose {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
