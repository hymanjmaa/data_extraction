<template>
  <div class="batch-process">
    <el-page-header @back="$router.back()" content="批量文档处理">
      <template #extra>
        <el-button type="primary" @click="showUploadDialog">
          <el-icon><Upload /></el-icon>
          上传批量文件
        </el-button>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="batch-stats">
      <el-col :span="6">
        <el-card>
          <el-statistic title="总批次" :value="batchStats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="处理中" :value="batchStats.processing">
            <template #prefix>
              <el-icon color="blue"><Loading /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="已完成" :value="batchStats.completed">
            <template #prefix>
              <el-icon color="green"><CircleCheck /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="失败" :value="batchStats.failed">
            <template #prefix>
              <el-icon color="red"><CircleClose /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="batch-list">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <h3>批次列表</h3>
              <el-select v-model="filterStatus" placeholder="筛选状态" clearable @change="loadBatches">
                <el-option label="待处理" value="pending" />
                <el-option label="处理中" value="processing" />
                <el-option label="已完成" value="completed" />
                <el-option label="失败" value="failed" />
              </el-select>
            </div>
          </template>

          <el-table :data="batches" v-loading="loading" stripe>
            <el-table-column prop="id" label="批次ID" width="100" />
            <el-table-column prop="name" label="批次名称" width="200" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)">
                  {{ getStatusText(scope.row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="200">
              <template #default="scope">
                <el-progress
                  :percentage="getProgress(scope.row)"
                  :status="getProgressStatus(scope.row)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="successful_files" label="成功" width="100">
              <template #default="scope">
                <el-tag type="success">{{ scope.row.successful_files }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="failed_files" label="失败" width="100">
              <template #default="scope">
                <el-tag type="danger">{{ scope.row.failed_files }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="scope">
                <el-button
                  v-if="scope.row.status === 'pending'"
                  type="primary"
                  size="small"
                  @click="startProcessing(scope.row)"
                >
                  开始处理
                </el-button>
                <el-button
                  v-if="scope.row.status === 'completed'"
                  type="success"
                  size="small"
                  @click="viewResults(scope.row)"
                >
                  查看结果
                </el-button>
                <el-button
                  v-if="scope.row.status === 'completed'"
                  type="info"
                  size="small"
                  @click="exportResults(scope.row)"
                >
                  导出
                </el-button>
                <el-button type="danger" size="small" @click="deleteBatch(scope.row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadBatches"
            @current-change="loadBatches"
            style="margin-top: 20px"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="uploadDialogVisible" title="上传批量文件" width="700px">
      <el-form :model="uploadForm" label-width="120px">
        <el-form-item label="批次名称">
          <el-input v-model="uploadForm.name" placeholder="自动生成或手动输入" />
        </el-form-item>

        <el-form-item label="选择模板" required>
          <el-select v-model="uploadForm.template_id" placeholder="请选择提取模板">
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="template.name"
              :value="template.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="上传方式">
          <el-radio-group v-model="uploadType">
            <el-radio label="files">多文件上传</el-radio>
            <el-radio label="zip">ZIP压缩包</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="uploadType === 'files'" label="选择文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
          </el-upload>
        </el-form-item>

        <el-form-item v-if="uploadType === 'zip'" label="上传ZIP包">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleZipChange"
            :file-list="zipFileList"
            accept=".zip"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择ZIP文件
            </el-button>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="uploading">
          上传并创建批次
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resultsDialogVisible" title="处理结果" width="1000px">
      <el-descriptions :column="3" border v-if="currentBatch">
        <el-descriptions-item label="批次名称">
          {{ currentBatch.name }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentBatch.status)">
            {{ getStatusText(currentBatch.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总文件数">
          {{ currentBatch.total_files }}
        </el-descriptions-item>
        <el-descriptions-item label="成功">
          <el-tag type="success">{{ currentBatch.successful_files }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="失败">
          <el-tag type="danger">{{ currentBatch.failed_files }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="完成时间">
          {{ formatDate(currentBatch.completed_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <el-table :data="batchResults" v-loading="loadingResults" stripe>
        <el-table-column prop="document_id" label="文档ID" width="100" />
        <el-table-column label="文件名" width="200">
          <template #default="scope">
            {{ getDocumentName(scope.row.document_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="success" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.success ? 'success' : 'danger'">
              {{ scope.row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="150">
          <template #default="scope">
            <el-progress
              v-if="scope.row.success"
              :percentage="(scope.row.confidence * 100).toFixed(1)"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息">
          <template #default="scope">
            <span v-if="scope.row.error" style="color: #F56C6C">
              {{ scope.row.error }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="resultsDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportResults(currentBatch)">
          导出结果
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const uploading = ref(false)
const loadingResults = ref(false)

const batches = ref([])
const templates = ref([])
const uploadDialogVisible = ref(false)
const resultsDialogVisible = ref(false)
const currentBatch = ref(null)
const batchResults = ref([])

const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const uploadType = ref('files')
const uploadForm = ref({
  name: '',
  template_id: null
})

const uploadRef = ref()
const fileList = ref([])
const zipFileList = ref([])

const batchStats = computed(() => {
  const stats = {
    total: batches.value.length,
    processing: 0,
    completed: 0,
    failed: 0
  }
  
  batches.value.forEach(batch => {
    if (batch.status === 'processing') stats.processing++
    else if (batch.status === 'completed') stats.completed++
    else if (batch.status === 'failed') stats.failed++
  })
  
  return stats
})

onMounted(() => {
  loadBatches()
  loadTemplates()
})

const loadBatches = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize.value
    }
    
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    const response = await axios.get('/batch/list', { params })
    
    if (response.data.success) {
      batches.value = response.data.batches
      total.value = response.data.total
    }
  } catch (error) {
    ElMessage.error('加载批次列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadTemplates = async () => {
  try {
    const response = await axios.get('/templates/list', { params: { per_page: 100 } })
    
    if (response.data.success) {
      templates.value = response.data.templates
    }
  } catch (error) {
    console.error('加载模板列表失败', error)
  }
}

const showUploadDialog = () => {
  uploadForm.value = {
    name: '',
    template_id: null
  }
  fileList.value = []
  zipFileList.value = []
  uploadDialogVisible.value = true
}

const handleFileChange = (file, files) => {
  fileList.value = files
}

const handleZipChange = (file, files) => {
  zipFileList.value = files
}

const submitUpload = async () => {
  if (!uploadForm.value.template_id) {
    ElMessage.warning('请选择提取模板')
    return
  }
  
  uploading.value = true
  
  try {
    let response
    
    if (uploadType.value === 'files') {
      if (fileList.value.length === 0) {
        ElMessage.warning('请选择要上传的文件')
        uploading.value = false
        return
      }
      
      const formData = new FormData()
      
      fileList.value.forEach(file => {
        formData.append('files', file.raw)
      })
      
      formData.append('name', uploadForm.value.name || '')
      formData.append('template_id', uploadForm.value.template_id)
      
      response = await axios.post('/batch/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    } else {
      if (zipFileList.value.length === 0) {
        ElMessage.warning('请选择ZIP文件')
        uploading.value = false
        return
      }
      
      const formData = new FormData()
      formData.append('file', zipFileList.value[0].raw)
      formData.append('name', uploadForm.value.name || '')
      formData.append('template_id', uploadForm.value.template_id)
      
      response = await axios.post('/batch/upload-zip', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }
    
    if (response.data.success) {
      ElMessage.success('文件上传成功')
      uploadDialogVisible.value = false
      loadBatches()
    }
  } catch (error) {
    ElMessage.error('上传失败')
    console.error(error)
  } finally {
    uploading.value = false
  }
}

const startProcessing = async (batch) => {
  try {
    await ElMessageBox.confirm('确定要开始处理这个批次吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    
    const response = await axios.post(`/batch/${batch.id}/process`, {
      max_workers: 4
    })
    
    if (response.data.success) {
      ElMessage.success('批次处理已开始')
      loadBatches()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('启动处理失败')
      console.error(error)
    }
  }
}

const viewResults = async (batch) => {
  currentBatch.value = batch
  resultsDialogVisible.value = true
  loadingResults.value = true
  
  try {
    const response = await axios.get(`/batch/${batch.id}/results`)
    
    if (response.data.success) {
      batchResults.value = response.data.results.results || []
    }
  } catch (error) {
    ElMessage.error('加载结果失败')
    console.error(error)
  } finally {
    loadingResults.value = false
  }
}

const getDocumentName = (docId) => {
  return `文档 #${docId}`
}

const exportResults = async (batch) => {
  try {
    const response = await axios.get(`/batch/${batch.id}/export`, {
      params: { format: 'json' }
    })
    
    const blob = new Blob([JSON.stringify(response.data, null, 2)], {
      type: 'application/json'
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `batch_${batch.id}_results.json`
    link.click()
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
    console.error(error)
  }
}

const deleteBatch = async (batch) => {
  try {
    await ElMessageBox.confirm('确定要删除这个批次吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await axios.delete(`/batch/${batch.id}`)
    
    if (response.data.success) {
      ElMessage.success('删除成功')
      loadBatches()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const getStatusType = (status) => {
  const types = {
    pending: 'info',
    uploading: 'warning',
    processing: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    pending: '待处理',
    uploading: '上传中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}

const getProgress = (batch) => {
  if (batch.total_files === 0) return 0
  return Math.round((batch.processed_files / batch.total_files) * 100)
}

const getProgressStatus = (batch) => {
  if (batch.failed_files > 0 && batch.status === 'completed') return 'exception'
  if (batch.status === 'completed') return 'success'
  return undefined
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}
</script>

<style scoped>
.batch-process {
  padding: 20px;
}

.batch-stats {
  margin-top: 20px;
}

.batch-list {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
