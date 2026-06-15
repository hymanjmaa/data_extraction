<template>
  <div class="home">
    <el-container>
      <el-header>
        <div class="header-content">
          <h1>📊 文档数据提取系统</h1>
          <el-menu mode="horizontal" :default-active="activeMenu" router>
            <el-menu-item index="/">首页</el-menu-item>
            <el-menu-item index="/documents">文档上传</el-menu-item>
            <el-menu-item index="/templates">模板管理</el-menu-item>
            <el-menu-item index="/batch">批量处理</el-menu-item>
            <el-menu-item index="/chat">文档数据提取助手</el-menu-item>
            <el-menu-item index="/wechat">微信管理</el-menu-item>
          </el-menu>
        </div>
      </el-header>
      
      <el-main>
        <el-row :gutter="20">
          <el-col :span="24">
            <el-card class="welcome-card">
              <template #header>
                <h2>欢迎使用文档数据提取系统</h2>
              </template>
              <div class="welcome-content">
                <p>支持多种文档类型的数据提取，包括：</p>
                <el-row :gutter="20" class="feature-grid">
                  <el-col :span="6">
                    <el-card class="feature-card">
                      <el-icon size="40"><Document /></el-icon>
                      <h3>发票提取</h3>
                      <p>自动识别发票信息</p>
                    </el-card>
                  </el-col>
                  <el-col :span="6">
                    <el-card class="feature-card">
                      <el-icon size="40"><Coin /></el-icon>
                      <h3>付款水单</h3>
                      <p>银行回单处理</p>
                    </el-card>
                  </el-col>
                  <el-col :span="6">
                    <el-card class="feature-card">
                      <el-icon size="40"><FolderOpened /></el-icon>
                      <h3>租约管理</h3>
                      <p>租赁合同提取</p>
                    </el-card>
                  </el-col>
                  <el-col :span="6">
                    <el-card class="feature-card">
                      <el-icon size="40"><ChatDotRound /></el-icon>
                      <h3>即时通讯</h3>
                      <p>碎片信息结构化</p>
                    </el-card>
                  </el-col>
                </el-row>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <el-row :gutter="20" class="stats-row">
          <el-col :span="6">
            <el-card>
              <el-statistic title="总文档数" :value="stats.total_documents">
                <template #prefix>
                  <el-icon><Document /></el-icon>
                </template>
              </el-statistic>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card>
              <el-statistic title="模板数" :value="stats.total_templates">
                <template #prefix>
                  <el-icon><FolderOpened /></el-icon>
                </template>
              </el-statistic>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card>
              <el-statistic title="提取记录" :value="stats.total_extractions">
                <template #prefix>
                  <el-icon><DataAnalysis /></el-icon>
                </template>
              </el-statistic>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card>
              <el-statistic title="系统状态">
                <template #value>
                  <el-tag type="success">运行中</el-tag>
                </template>
              </el-statistic>
            </el-card>
          </el-col>
        </el-row>
        
        <el-row :gutter="20" class="quick-actions">
          <el-col :span="24">
            <el-card>
              <template #header>
                <h3>快速操作</h3>
              </template>
              <el-space wrap>
                <el-button type="primary" @click="$router.push('/documents')">
                  <el-icon><Upload /></el-icon>
                  上传文档
                </el-button>
                <el-button type="success" @click="$router.push('/templates')">
                  <el-icon><Plus /></el-icon>
                  创建模板
                </el-button>
                <el-button type="warning" @click="$router.push('/batch')">
                  <el-icon><Grid /></el-icon>
                  批量处理
                </el-button>
                <el-button type="info" @click="$router.push('/chat')">
                  <el-icon><ChatLineRound /></el-icon>
                  处理消息
                </el-button>
              </el-space>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeMenu = ref('/')
const stats = ref({
  total_documents: 0,
  total_templates: 0,
  total_extractions: 0
})

onMounted(async () => {
  try {
    const response = await axios.get('/stats')
    if (response.data.status === 'healthy') {
      const healthResponse = await axios.get('/stats')
      stats.value = {
        total_documents: healthResponse.data.total_documents || 0,
        total_templates: healthResponse.data.total_templates || 0,
        total_extractions: healthResponse.data.total_extractions || 0
      }
    }
  } catch (error) {
    console.error('获取统计信息失败:', error)
  }
})
</script>

<style scoped>
.home {
  min-height: 100vh;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
  color: #409EFF;
}

.welcome-card {
  margin-bottom: 20px;
}

.feature-grid {
  margin-top: 20px;
}

.feature-card {
  text-align: center;
  padding: 20px;
}

.feature-card h3 {
  margin: 15px 0 10px;
}

.feature-card p {
  color: #909399;
  font-size: 14px;
}

.stats-row {
  margin-bottom: 20px;
}

.quick-actions {
  margin-bottom: 20px;
}
</style>
