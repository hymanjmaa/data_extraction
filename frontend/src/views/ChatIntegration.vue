<template>
  <div class="chatbot">
    <el-page-header @back="$router.back()" content="文档数据提取助手" />

    <el-card class="chat-card">
      <template #header>
        <div class="chat-header">
          <el-space>
            <el-select v-model="meta.source" size="small" style="width: 120px">
              <el-option label="文档" value="document" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-input v-model="meta.sender" size="small" style="width: 180px" placeholder="发送者(可选)" />
          </el-space>
          <div class="chat-hint">输入“帮助”查看指令</div>
        </div>
      </template>

      <div ref="chatBodyRef" class="chat-body">
        <div v-if="chatMessages.length === 0" class="chat-empty">
          上传文档或输入指令，我会进行相应的数据提取操作。输入"帮助"查看可用指令。
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
          <el-button size="small" @click="showChatHistoryDialog">
            选择聊天历史
          </el-button>
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
            <el-button
              :disabled="!speechSupported || sending"
              :type="isRecording ? 'danger' : 'default'"
              @click="toggleVoice"
            >
              <el-icon><Microphone /></el-icon>
              {{ isRecording ? '停止' : '语音' }}
            </el-button>
            <el-button type="primary" @click="send" :loading="sending" :disabled="!inputText.trim() && pendingFiles.length === 0">
              发送
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="chatHistoryVisible" title="选择聊天历史" width="800px">
      <el-form :inline="true" class="chat-filter-form">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="chatTimeRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="群组/联系人">
          <el-select v-model="chatFilterName" clearable placeholder="选择">
            <el-option v-for="g in chatGroups" :key="g.chat_name" :label="g.chat_name" :value="g.chat_name" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchWeChatMessages">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table
        :data="wechatMessages"
        style="width: 100%"
        v-loading="chatHistoryLoading"
        @selection-change="handleChatSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="chat_name" label="群组/联系人" width="180" />
        <el-table-column prop="sender_name" label="发送者" width="120" />
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
      </el-table>

      <template #footer>
        <el-button @click="chatHistoryVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmChatHistory">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { Microphone } from '@element-plus/icons-vue'

const meta = ref({
  source: 'document',
  sender: '',
})

const chatBodyRef = ref(null)
const chatMessages = ref([])
const inputText = ref('')
const pendingFiles = ref([])
const sending = ref(false)
const sessionId = ref(localStorage.getItem('chat_session_id') || '')

const speechSupported = ref(false)
const isRecording = ref(false)
const recognitionRef = ref(null)
const voiceBaseText = ref('')

const chatHistoryVisible = ref(false)
const chatTimeRange = ref([])
const chatFilterName = ref('')
const wechatMessages = ref([])
const chatHistoryLoading = ref(false)
const chatGroups = ref([])
const selectedChatMessages = ref([])

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

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    speechSupported.value = false
    return
  }

  const rec = new SpeechRecognition()
  rec.lang = 'zh-CN'
  rec.continuous = false
  rec.interimResults = true

  rec.onresult = (event) => {
    let transcript = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0]?.transcript || ''
    }
    inputText.value = `${voiceBaseText.value}${transcript}`.trimStart()
  }

  rec.onerror = (event) => {
    isRecording.value = false
    ElMessage.error(`语音识别失败：${event?.error || 'unknown'}`)
  }

  rec.onend = () => {
    isRecording.value = false
  }

  recognitionRef.value = rec
  speechSupported.value = true
})

onBeforeUnmount(() => {
  try {
    recognitionRef.value?.stop?.()
  } catch {
  }
})

const toggleVoice = () => {
  if (!speechSupported.value || !recognitionRef.value) {
    ElMessage.warning('当前浏览器不支持语音输入')
    return
  }

  if (isRecording.value) {
    try {
      recognitionRef.value.stop()
    } catch {
    }
    return
  }

  voiceBaseText.value = inputText.value ? `${inputText.value.trimEnd()} ` : ''
  try {
    isRecording.value = true
    recognitionRef.value.start()
  } catch {
    isRecording.value = false
    ElMessage.error('语音识别启动失败')
  }
}

const send = async () => {
  if (isRecording.value && recognitionRef.value) {
    try {
      recognitionRef.value.stop()
    } catch {
    }
  }
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

const showChatHistoryDialog = async () => {
  chatHistoryVisible.value = true
  if (chatGroups.value.length === 0) {
    try {
      const res = await axios.get('/wechat/chat-groups')
      if (res.data.success) {
        chatGroups.value = res.data.groups
      }
    } catch {
    }
  }
}

const fetchWeChatMessages = async () => {
  chatHistoryLoading.value = true
  try {
    const params = {
      page: 1,
      per_page: 200,
    }
    if (chatTimeRange.value && chatTimeRange.value[0]) params.start_time = chatTimeRange.value[0]
    if (chatTimeRange.value && chatTimeRange.value[1]) params.end_time = chatTimeRange.value[1]
    if (chatFilterName.value) params.chat_name = chatFilterName.value

    const res = await axios.get('/wechat/messages', { params })
    if (res.data.success) {
      wechatMessages.value = res.data.messages.reverse()
    }
  } catch {
    ElMessage.error('获取聊天历史失败')
  } finally {
    chatHistoryLoading.value = false
  }
}

const handleChatSelectionChange = (selection) => {
  selectedChatMessages.value = selection
}

const confirmChatHistory = () => {
  if (selectedChatMessages.value.length === 0) {
    ElMessage.warning('请先选择聊天消息')
    return
  }

  const combinedContent = selectedChatMessages.value
    .map(m => `[${m.timestamp}] ${m.sender_name}@${m.chat_name}: ${m.content}`)
    .join('\n')

  chatHistoryVisible.value = false
  inputText.value = `从微信聊天历史提取数据：\n${combinedContent}`

  ElMessage.success(`已选择 ${selectedChatMessages.value.length} 条消息`)
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
  gap: 10px;
}
</style>
