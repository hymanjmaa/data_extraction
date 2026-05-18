<template>
  <div class="document-upload">
    <el-page-header @back="$router.back()" content="文档上传与提取">
      <template #extra>
        <el-button type="primary" @click="refreshList">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="upload-section">
      <el-col :span="24">
        <el-card>
          <template #header>
            <h3>上传文档</h3>
          </template>
          <el-upload
            ref="uploadRef"
            class="upload-demo"
            drag
            :action="`${baseURL}/documents/upload`"
            :auto-upload="false"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :file-list="fileList"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF、图片、Word、Excel 格式，单个文件不超过 16MB
              </div>
            </template>
          </el-upload>
          
          <el-form :model="extractForm" class="extract-form">
            <el-form-item label="选择提取模板">
              <el-select v-model="extractForm.template_id" placeholder="请选择模板" @change="loadTemplate">
                <el-option
                  v-for="template in templates"
                  :key="template.id"
                  :label="template.name"
                  :value="template.id"
                >
                  <span>{{ template.name }}</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">
                    {{ template.document_type }}
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="submitUpload" :loading="uploading">
                <el-icon v-if="!uploading"><Upload /></el-icon>
                上传并提取
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" v-if="selectedTemplate">
      <el-col :span="24">
        <el-card>
          <template #header>
            <h3>选中的模板：{{ selectedTemplate.name }}</h3>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文档类型">
              {{ selectedTemplate.document_type }}
            </el-descriptions-item>
            <el-descriptions-item label="字段数量">
              {{ selectedTemplate.fields?.length || 0 }}
            </el-descriptions-item>
          </el-descriptions>
          
          <el-divider>提取字段</el-divider>
          
          <el-table :data="selectedTemplate.fields" stripe>
            <el-table-column prop="name" label="字段名" width="150" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="required" label="必填" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.required ? 'danger' : 'info'" size="small">
                  {{ scope.row.required ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="document-list">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <h3>文档列表</h3>
              <el-input
                v-model="searchQuery"
                placeholder="搜索文档..."
                style="width: 300px"
                clearable
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
          </template>
          
          <el-table :data="filteredDocuments" v-loading="loading">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="filename" label="文件名" />
            <el-table-column prop="file_type" label="类型" width="100">
              <template #default="scope">
                <el-tag type="info">{{ scope.row.file_type.toUpperCase() }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="file_size" label="大小" width="120">
              <template #default="scope">
                {{ formatFileSize(scope.row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="120">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)">
                  {{ getStatusText(scope.row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="上传时间" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="scope">
                <el-button 
                  type="primary" 
                  size="small" 
                  @click="viewExtractions(scope.row)"
                  :disabled="scope.row.status !== 'uploaded'"
                >
                  查看提取
                </el-button>
                <el-button 
                  type="danger" 
                  size="small" 
                  @click="deleteDocument(scope.row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadDocuments"
            @current-change="loadDocuments"
            style="margin-top: 20px"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="extractionDialogVisible" title="提取结果" width="800px">
      <el-descriptions title="文档信息" :column="2" border v-if="currentDocument">
        <el-descriptions-item label="文件名">
          {{ currentDocument.filename }}
        </el-descriptions-item>
        <el-descriptions-item label="类型">
          {{ currentDocument.file_type }}
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider />
      
      <el-table :data="extractionRecords" v-loading="loadingExtractions">
        <el-table-column prop="id" label="记录ID" width="100" />
        <el-table-column prop="template_name" label="模板" width="150" />
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="scope">
            <el-progress :percentage="scope.row.confidence * 100" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'completed' ? 'success' : 'danger'">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提取时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button type="text" @click="viewExtractionData(scope.row)">
              查看数据
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="dataDialogVisible" title="提取数据详情" width="600px">
      <el-descriptions :column="1" border v-if="currentExtraction">
        <el-descriptions-item 
          v-for="(value, key) in currentExtraction.data" 
          :key="key"
          :label="key"
        >
          {{ value || '-' }}
        </el-descriptions-item>
      </el-descriptions>
      
      <template #footer>
        <el-button @click="dataDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const baseURL = 'http://localhost:5000/api'

const uploadRef = ref()
const fileList = ref([])
const templates = ref([])
const documents = ref([])
const loading = ref(false)
const uploading = ref(false)

const extractForm = ref({
  template_id: null
})

const selectedTemplate = ref(null)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const extractionDialogVisible = ref(false)
const dataDialogVisible = ref(false)
const loadingExtractions = ref(false)
const currentDocument = ref(null)
const currentExtraction = ref(null)
const extractionRecords = ref([])

const filteredDocuments = computed(() => {
  if (!searchQuery.value) return documents.value
  
  return documents.value.filter(doc => 
    doc.filename.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

onMounted(() => {
  loadDocuments()
  loadTemplates()
})

const loadDocuments = async () => {
  loading.value = true
  try {
    const response = await axios.get('/documents/list', {
      params: {
        page: currentPage.value,
        per_page: pageSize.value
      }
    })
    
    if (response.data.success) {
      documents.value = response.data.documents
      total.value = response.data.total
    }
  } catch (error) {
    ElMessage.error('加载文档列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadTemplates = async () => {
  try {
    const response = await axios.get('/templates/list', {
      params: { per_page: 100 }
    })
    
    if (response.data.success) {
      templates.value = response.data.templates
    }
  } catch (error) {
    console.error('加载模板列表失败', error)
  }
}

const loadTemplate = async () => {
  if (!extractForm.value.template_id) {
    selectedTemplate.value = null
    return
  }
  
  try {
    const response = await axios.get(`/templates/${extractForm.value.template_id}`)
    
    if (response.data.success) {
      selectedTemplate.value = response.data.template
      ElMessage.success('已加载模板')
    }
  } catch (error) {
    ElMessage.error('加载模板详情失败')
    console.error(error)
  }
}

const submitUpload = async () => {
  if (!extractForm.value.template_id) {
    ElMessage.warning('请先选择提取模板')
    return
  }
  
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  
  uploading.value = true
  
  try {
    for (const file of fileList.value) {
      const formData = new FormData()
      formData.append('file', file.raw)
      
      const uploadResponse = await axios.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      if (uploadResponse.data.success) {
        const docId = uploadResponse.data.document.id
        
        await axios.post(`/documents/${docId}/extract`, {
          template_id: extractForm.value.template_id
        })
      }
    }
    
    ElMessage.success('上传并提取完成')
    fileList.value = []
    loadDocuments()
  } catch (error) {
    ElMessage.error('处理失败')
    console.error(error)
  } finally {
    uploading.value = false
  }
}

const handleUploadSuccess = (response) => {
  ElMessage.success(`文件 ${response.document.filename} 上传成功`)
}

const handleUploadError = (error) => {
  ElMessage.error('上传失败')
  console.error(error)
}

const refreshList = () => {
  loadDocuments()
}

const viewExtractions = async (doc) => {
  currentDocument.value = doc
  extractionDialogVisible.value = true
  loadingExtractions.value = true
  
  try {
    const response = await axios.get(`/documents/${doc.id}/extractions`)
    
    if (response.data.success) {
      extractionRecords.value = response.data.extractions.map(e => ({
        ...e,
        confidence: e.confidence || 0,
        data: e.data
      }))
    }
  } catch (error) {
    ElMessage.error('加载提取记录失败')
    console.error(error)
  } finally {
    loadingExtractions.value = false
  }
}

const viewExtractionData = (record) => {
  currentExtraction.value = record
  dataDialogVisible.value = true
}

const deleteDocument = async (doc) => {
  try {
    await ElMessageBox.confirm('确定要删除这个文档吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await axios.delete(`/documents/${doc.id}`)
    
    if (response.data.success) {
      ElMessage.success('删除成功')
      loadDocuments()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const types = {
    pending: 'info',
    uploaded: 'primary',
    extracted: 'success',
    failed: 'danger',
    error: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    pending: '待处理',
    uploaded: '已上传',
    extracted: '已提取',
    failed: '失败',
    error: '错误'
  }
  return texts[status] || status
}
</script>

<style scoped>
.document-upload {
  padding: 20px;
}

.upload-section {
  margin-top: 20px;
}

.extract-form {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.document-list {
  margin-top: 20px;
}
</style>
