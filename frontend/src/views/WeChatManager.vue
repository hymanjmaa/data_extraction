<template>
  <div class="wechat-manager">
    <el-page-header @back="$router.back()" content="微信管理" />

    <el-card class="status-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>登录状态</span>
          <el-button v-if="isLoggedIn" type="danger" @click="handleLogout">退出登录</el-button>
        </div>
      </template>

      <el-empty v-if="!isLoggedIn && !qrCode" description="点击登录获取二维码" />

      <div v-if="!isLoggedIn && qrCode" class="qr-section">
        <img :src="`data:image/png;base64,${qrCode}`" alt="QR Code" class="qr-code" />
        <p>请使用微信扫描二维码登录</p>
      </div>

      <div v-if="isLoggedIn" class="user-info">
        <el-tag type="success">已登录</el-tag>
        <span class="nickname">{{ nickname }}</span>
      </div>

      <el-button v-if="!isLoggedIn" type="primary" @click="handleLogin" :loading="loginLoading">
        获取登录二维码
      </el-button>
    </el-card>

    <el-card class="history-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>聊天历史</span>
        </div>
      </template>

      <el-form :inline="true" class="filter-form">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            @change="handleTimeChange"
          />
        </el-form-item>
        <el-form-item label="群组/联系人">
          <el-select v-model="filterChatName" clearable placeholder="选择群组或联系人">
            <el-option v-for="g in chatGroups" :key="g.chat_name" :label="g.chat_name" :value="g.chat_name" />
          </el-select>
        </el-form-item>
        <el-form-item label="发送者">
          <el-input v-model="filterSender" placeholder="发送者昵称" clearable @keyup.enter="fetchMessages" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchMessages">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="messages" style="width: 100%" v-loading="loading">
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="chat_name" label="群组/联系人" width="180" />
        <el-table-column prop="sender_name" label="发送者" width="120" />
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_group" type="warning" size="small">群聊</el-tag>
            <el-tag v-else type="info" size="small">私聊</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        style="margin-top: 20px; justify-content: center"
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="perPage"
        :total="total"
        @current-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const isLoggedIn = ref(false)
const nickname = ref('')
const qrCode = ref('')
const loginLoading = ref(false)

const messages = ref([])
const total = ref(0)
const page = ref(1)
const perPage = ref(50)
const loading = ref(false)

const timeRange = ref([])
const filterChatName = ref('')
const filterSender = ref('')
const chatGroups = ref([])

const fetchStatus = async () => {
  try {
    const res = await axios.get('/wechat/status')
    if (res.data.success) {
      isLoggedIn.value = res.data.logged_in
      nickname.value = res.data.nickname || ''
    }
  } catch {
  }
}

const handleLogin = async () => {
  loginLoading.value = true
  try {
    const res = await axios.post('/wechat/login')
    if (res.data.success) {
      qrCode.value = res.data.qr_code
      ElMessage.success('二维码已生成，请扫码登录')
    } else {
      ElMessage.error(res.data.error || '登录失败')
    }
  } catch (e) {
    ElMessage.error('登录请求失败: ' + (e.message || '未知错误'))
  } finally {
    loginLoading.value = false
  }
}

const handleLogout = async () => {
  try {
    const res = await axios.post('/wechat/logout')
    if (res.data.success) {
      ElMessage.success('已退出登录')
      isLoggedIn.value = false
      qrCode.value = ''
    }
  } catch {
    ElMessage.error('退出登录失败')
  }
}

const fetchMessages = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      per_page: perPage.value,
    }
    if (timeRange.value && timeRange.value[0]) params.start_time = timeRange.value[0]
    if (timeRange.value && timeRange.value[1]) params.end_time = timeRange.value[1]
    if (filterChatName.value) params.chat_name = filterChatName.value
    if (filterSender.value) params.sender_name = filterSender.value

    const res = await axios.get('/wechat/messages', { params })
    if (res.data.success) {
      messages.value = res.data.messages
      total.value = res.data.total
    }
  } catch {
    ElMessage.error('获取消息失败')
  } finally {
    loading.value = false
  }
}

const fetchChatGroups = async () => {
  try {
    const res = await axios.get('/wechat/chat-groups')
    if (res.data.success) {
      chatGroups.value = res.data.groups
    }
  } catch {
  }
}

const handleTimeChange = () => {
  page.value = 1
  fetchMessages()
}

const handlePageChange = (newPage) => {
  page.value = newPage
  fetchMessages()
}

onMounted(() => {
  fetchStatus()
  fetchMessages()
  fetchChatGroups()
})
</script>

<style scoped>
.wechat-manager {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.qr-section {
  text-align: center;
  margin: 20px 0;
}
.qr-code {
  width: 300px;
  height: 300px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
}
.nickname {
  font-size: 18px;
  font-weight: bold;
}
.filter-form {
  margin-bottom: 20px;
}
</style>
