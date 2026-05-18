<template>
  <div class="template-manager">
    <el-page-header @back="$router.back()" content="模板管理">
      <template #extra>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          创建模板
        </el-button>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="filter-section">
      <el-col :span="24">
        <el-card>
          <el-form :inline="true">
            <el-form-item label="文档类型">
              <el-select v-model="filterDocumentType" placeholder="全部类型" clearable @change="loadTemplates">
                <el-option
                  v-for="type in documentTypes"
                  :key="type[0]"
                  :label="type[1]"
                  :value="type[0]"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="搜索">
              <el-input v-model="searchQuery" placeholder="模板名称..." clearable @input="handleSearch">
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="template-list">
      <el-col :span="24">
        <el-card>
          <el-table :data="filteredTemplates" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="模板名称" width="200" />
            <el-table-column prop="document_type" label="文档类型" width="150">
              <template #default="scope">
                <el-tag type="primary">{{ getDocumentTypeName(scope.row.document_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="fields_count" label="字段数" width="100" align="center" />
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="scope">
                <el-button type="primary" size="small" @click="viewTemplate(scope.row)">
                  查看
                </el-button>
                <el-button type="success" size="small" @click="editTemplate(scope.row)">
                  编辑
                </el-button>
                <el-button type="warning" size="small" @click="duplicateTemplate(scope.row)">
                  复制
                </el-button>
                <el-button type="danger" size="small" @click="deleteTemplate(scope.row)">
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
            @size-change="loadTemplates"
            @current-change="loadTemplates"
            style="margin-top: 20px"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '创建模板' : '编辑模板'"
      width="900px"
    >
      <el-form :model="templateForm" label-width="120px">
        <el-form-item label="模板名称" required>
          <el-input v-model="templateForm.name" placeholder="请输入模板名称" />
        </el-form-item>

        <el-form-item label="文档类型" required>
          <el-select v-model="templateForm.document_type" placeholder="请选择文档类型">
            <el-option
              v-for="type in documentTypes"
              :key="type[0]"
              :label="type[1]"
              :value="type[0]"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="templateForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入模板描述"
          />
        </el-form-item>

        <el-form-item label="提取字段">
          <div class="fields-container">
            <div v-for="(field, index) in templateForm.fields" :key="index" class="field-item">
              <el-input v-model="field.name" placeholder="字段名" style="width: 150px" />
              <el-input v-model="field.description" placeholder="字段描述" style="flex: 1" />
              <el-select v-model="field.type" placeholder="类型" style="width: 120px">
                <el-option label="文本" value="string" />
                <el-option label="数字" value="number" />
                <el-option label="日期" value="date" />
                <el-option label="布尔" value="boolean" />
              </el-select>
              <el-checkbox v-model="field.required">必填</el-checkbox>
              <el-button type="danger" size="small" @click="removeField(index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button type="primary" plain @click="addField">
              <el-icon><Plus /></el-icon>
              添加字段
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="验证规则">
          <div class="validation-container">
            <div v-for="(rule, index) in templateForm.validation_rules" :key="index" class="rule-item">
              <el-select v-model="rule.type" placeholder="规则类型" style="width: 120px">
                <el-option label="等式" value="equation" />
                <el-option label="范围" value="range" />
                <el-option label="必填" value="required" />
              </el-select>
              <el-input v-model="rule.field" placeholder="字段名" style="width: 150px" />
              <el-input v-model="rule.rule" placeholder="规则描述" style="flex: 1" />
              <el-button type="danger" size="small" @click="removeRule(index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button type="primary" plain @click="addRule">
              <el-icon><Plus /></el-icon>
              添加规则
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTemplate" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="viewDialogVisible" title="模板详情" width="900px">
      <el-descriptions :column="2" border v-if="currentTemplate">
        <el-descriptions-item label="模板名称">
          {{ currentTemplate.name }}
        </el-descriptions-item>
        <el-descriptions-item label="文档类型">
          {{ getDocumentTypeName(currentTemplate.document_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          {{ currentTemplate.description || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatDate(currentTemplate.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDate(currentTemplate.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider>提取字段</el-divider>

      <el-table :data="currentTemplate?.fields || []" stripe>
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

      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="aiDialogVisible" title="AI生成模板" width="600px">
      <el-form>
        <el-form-item label="文档类型">
          <el-select v-model="aiForm.document_type" placeholder="选择文档类型">
            <el-option
              v-for="type in documentTypes"
              :key="type[0]"
              :label="type[1]"
              :value="type[0]"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="需求描述">
          <el-input
            v-model="aiForm.description"
            type="textarea"
            :rows="6"
            placeholder="例如：提取发票上的不含税金额和税额，用于财务记账"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="generateTemplateByAI" :loading="generating">
          生成模板
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
const submitting = ref(false)
const generating = ref(false)

const templates = ref([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const aiDialogVisible = ref(false)

const dialogMode = ref('create')
const currentTemplate = ref(null)
const currentTemplateId = ref(null)

const filterDocumentType = ref('')
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const documentTypes = ref([])

const templateForm = ref({
  name: '',
  document_type: '',
  description: '',
  fields: [],
  validation_rules: []
})

const aiForm = ref({
  document_type: '',
  description: ''
})

const filteredTemplates = computed(() => {
  if (!searchQuery.value) return templates.value
  
  return templates.value.filter(t => 
    t.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

onMounted(() => {
  loadTemplates()
  loadDocumentTypes()
})

const loadTemplates = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize.value
    }
    
    if (filterDocumentType.value) {
      params.document_type = filterDocumentType.value
    }
    
    const response = await axios.get('/templates/list', { params })
    
    if (response.data.success) {
      templates.value = response.data.templates
      total.value = response.data.total
    }
  } catch (error) {
    ElMessage.error('加载模板列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadDocumentTypes = async () => {
  try {
    const response = await axios.get('/templates/types')
    if (response.data.success) {
      documentTypes.value = response.data.types
    }
  } catch (error) {
    console.error('加载文档类型失败', error)
  }
}

const getDocumentTypeName = (typeCode) => {
  const type = documentTypes.value.find(t => t[0] === typeCode)
  return type ? type[1] : typeCode
}

const handleSearch = () => {
  currentPage.value = 1
}

const showCreateDialog = () => {
  dialogMode.value = 'create'
  templateForm.value = {
    name: '',
    document_type: '',
    description: '',
    fields: [],
    validation_rules: []
  }
  dialogVisible.value = true
}

const addField = () => {
  templateForm.value.fields.push({
    name: '',
    description: '',
    type: 'string',
    required: false
  })
}

const removeField = (index) => {
  templateForm.value.fields.splice(index, 1)
}

const addRule = () => {
  templateForm.value.validation_rules.push({
    type: 'equation',
    field: '',
    rule: '',
    message: ''
  })
}

const removeRule = (index) => {
  templateForm.value.validation_rules.splice(index, 1)
}

const submitTemplate = async () => {
  if (!templateForm.value.name) {
    ElMessage.warning('请输入模板名称')
    return
  }
  
  if (!templateForm.value.document_type) {
    ElMessage.warning('请选择文档类型')
    return
  }
  
  if (templateForm.value.fields.length === 0) {
    ElMessage.warning('请至少添加一个提取字段')
    return
  }
  
  submitting.value = true
  
  try {
    let response
    
    if (dialogMode.value === 'create') {
      response = await axios.post('/templates', templateForm.value)
    } else {
      response = await axios.put(`/templates/${currentTemplateId.value}`, templateForm.value)
    }
    
    if (response.data.success) {
      ElMessage.success(dialogMode.value === 'create' ? '模板创建成功' : '模板更新成功')
      dialogVisible.value = false
      loadTemplates()
    }
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  } finally {
    submitting.value = false
  }
}

const viewTemplate = async (template) => {
  try {
    const response = await axios.get(`/templates/${template.id}`)
    
    if (response.data.success) {
      currentTemplate.value = response.data.template
      viewDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('加载模板详情失败')
    console.error(error)
  }
}

const editTemplate = async (template) => {
  try {
    const response = await axios.get(`/templates/${template.id}`)
    
    if (response.data.success) {
      dialogMode.value = 'edit'
      currentTemplateId.value = template.id
      templateForm.value = {
        name: response.data.template.name,
        document_type: response.data.template.document_type,
        description: response.data.template.description,
        fields: response.data.template.fields || [],
        validation_rules: response.data.template.validation_rules || []
      }
      dialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('加载模板失败')
    console.error(error)
  }
}

const duplicateTemplate = async (template) => {
  try {
    const response = await axios.post(`/templates/${template.id}/duplicate`, {
      new_name: `${template.name} (副本)`
    })
    
    if (response.data.success) {
      ElMessage.success('模板复制成功')
      loadTemplates()
    }
  } catch (error) {
    ElMessage.error('复制失败')
    console.error(error)
  }
}

const deleteTemplate = async (template) => {
  try {
    await ElMessageBox.confirm('确定要删除这个模板吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await axios.delete(`/templates/${template.id}`)
    
    if (response.data.success) {
      ElMessage.success('删除成功')
      loadTemplates()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const generateTemplateByAI = async () => {
  if (!aiForm.value.description) {
    ElMessage.warning('请输入需求描述')
    return
  }
  
  generating.value = true
  
  try {
    const response = await axios.post('/templates/generate-from-description', aiForm.value)
    
    if (response.data.success) {
      const generated = response.data.template
      
      dialogMode.value = 'create'
      templateForm.value = {
        name: generated.name,
        document_type: generated.document_type,
        description: generated.description,
        fields: generated.fields || [],
        validation_rules: generated.validation_rules || []
      }
      
      aiDialogVisible.value = false
      dialogVisible.value = true
      
      ElMessage.success('模板生成成功，请检查并调整')
    }
  } catch (error) {
    ElMessage.error('生成失败')
    console.error(error)
  } finally {
    generating.value = false
  }
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}
</script>

<style scoped>
.template-manager {
  padding: 20px;
}

.filter-section {
  margin-top: 20px;
}

.template-list {
  margin-top: 20px;
}

.fields-container,
.validation-container {
  width: 100%;
}

.field-item,
.rule-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}
</style>
