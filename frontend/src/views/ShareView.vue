<template>
  <div class="share-page">
    <!-- Tab切换 -->
    <el-tabs v-model="activeTab" class="share-tabs">
      <!-- 项目导入导出 -->
      <el-tab-pane label="项目导入导出" name="export">
        <div class="page-card">
          <h3>导出项目</h3>
          <el-alert
            title="导出说明"
            type="info"
            :closable="false"
            style="margin-bottom: 16px;">
            <template #default>
              导出会包含以下内容：数据库、模型文件、仿真结果、配置文件等全部项目数据。
              导出的ZIP文件可用于备份或迁移到其他环境。
            </template>
          </el-alert>
          <el-form :inline="true">
            <el-form-item label="项目名称">
              <el-input v-model="exportName" placeholder="输入导出项目名称" style="width: 200px;" />
            </el-form-item>
            <el-form-item label="导出范围">
              <el-checkbox-group v-model="exportInclude">
                <el-checkbox label="database">数据库</el-checkbox>
                <el-checkbox label="models">模型文件</el-checkbox>
                <el-checkbox label="results">仿真结果</el-checkbox>
                <el-checkbox label="config">配置文件</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleExport" :loading="exporting">
                <el-icon v-if="!exporting"><Download /></el-icon>
                开始导出
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 导出历史 -->
          <h3 style="margin-top: 32px;">导出历史</h3>
          <el-table :data="exportHistory" stripe>
            <el-table-column prop="name" label="文件名" min-width="200" />
            <el-table-column prop="size" label="大小" width="100" />
            <el-table-column prop="created_at" label="导出时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" @click="downloadExport(row)">下载</el-button>
                <el-button size="small" type="danger" @click="deleteExport(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="page-card" style="margin-top: 16px;">
          <h3>导入项目</h3>
          <el-alert
            title="导入说明"
            type="warning"
            :closable="false"
            style="margin-bottom: 16px;">
            导入会解压ZIP文件并覆盖当前项目数据，请谨慎操作。建议先导出备份。
          </el-alert>
          <el-upload
            drag
            :action="importUrl"
            :headers="uploadHeaders"
            :before-upload="beforeUpload"
            :on-success="handleImportSuccess"
            :on-error="handleImportError"
            accept=".zip"
            class="upload-area"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽ZIP文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 .zip 格式，文件大小不超过 500MB</div>
            </template>
          </el-upload>
        </div>
      </el-tab-pane>

      <!-- 项目模板 -->
      <el-tab-pane label="项目模板" name="template">
        <div class="page-card">
          <div class="template-header">
            <h3>我的模板</h3>
            <el-button type="primary" @click="showSaveTemplateDialog = true">
              <el-icon><DocumentAdd /></el-icon>
              保存为模板
            </el-button>
          </div>
          
          <el-row :gutter="16" class="template-grid">
            <el-col :span="6" v-for="tpl in myTemplates" :key="tpl.id">
              <div class="template-card" @click="useTemplate(tpl)">
                <div class="template-cover">
                  <img v-if="tpl.cover" :src="tpl.cover" alt="cover" />
                  <div v-else class="template-cover-placeholder">
                    <el-icon :size="48"><Folder /></el-icon>
                  </div>
                </div>
                <div class="template-info">
                  <h4>{{ tpl.name }}</h4>
                  <p class="template-desc">{{ tpl.description || '暂无描述' }}</p>
                  <div class="template-meta">
                    <span><el-icon><Timer /></el-icon> {{ formatTime(tpl.created_at) }}</span>
                  </div>
                </div>
                <div class="template-actions" @click.stop>
                  <el-button size="small" type="primary" @click="useTemplate(tpl)">使用</el-button>
                  <el-button size="small" @click="editTemplate(tpl)">编辑</el-button>
                  <el-button size="small" type="danger" @click="deleteTemplate(tpl)">删除</el-button>
                </div>
              </div>
            </el-col>
          </el-row>

          <el-empty v-if="myTemplates.length === 0" description="暂无模板">
            <el-button type="primary" @click="showSaveTemplateDialog = true">创建第一个模板</el-button>
          </el-empty>
        </div>

        <!-- 模板市场 -->
        <div class="page-card" style="margin-top: 16px;">
          <h3>模板市场</h3>
          <div class="filter-bar">
            <el-select v-model="templateCategory" placeholder="全部分类" @change="fetchMarketTemplates">
              <el-option label="全部分类" value="" />
              <el-option label="选股策略" value="stock_selection" />
              <el-option label="风控模型" value="risk_control" />
              <el-option label="回测模板" value="backtest" />
              <el-option label="信号策略" value="signal" />
            </el-select>
            <el-input v-model="templateSearch" placeholder="搜索模板" style="width: 200px;" @keyup.enter="fetchMarketTemplates">
              <template #append>
                <el-button @click="fetchMarketTemplates"><el-icon><Search /></el-icon></el-button>
              </template>
            </el-input>
          </div>

          <el-row :gutter="16" class="template-grid">
            <el-col :span="6" v-for="tpl in marketTemplates" :key="tpl.id">
              <div class="template-card">
                <div class="template-cover">
                  <img v-if="tpl.cover" :src="tpl.cover" alt="cover" />
                  <div v-else class="template-cover-placeholder">
                    <el-icon :size="48"><Folder /></el-icon>
                  </div>
                </div>
                <div class="template-info">
                  <h4>{{ tpl.name }}</h4>
                  <p class="template-desc">{{ tpl.description || '暂无描述' }}</p>
                  <div class="template-meta">
                    <el-tag size="small" type="info">{{ tpl.category }}</el-tag>
                    <span><el-icon><User /></el-icon> {{ tpl.author }}</span>
                  </div>
                </div>
                <div class="template-actions">
                  <el-button size="small" type="success" @click="previewTemplate(tpl)">预览</el-button>
                  <el-button size="small" type="primary" @click="installTemplate(tpl)">安装</el-button>
                </div>
              </div>
            </el-col>
          </el-row>

          <el-empty v-if="marketTemplates.length === 0" description="暂无模板，请稍后再试" />
        </div>
      </el-tab-pane>

      <!-- 协作功能 -->
      <el-tab-pane label="协作与分享" name="collab">
        <div class="page-card">
          <h3>项目权限</h3>
          <el-form label-width="120px">
            <el-form-item label="当前权限">
              <el-tag :type="currentPermission === 'edit' ? 'success' : 'info'">
                {{ currentPermission === 'edit' ? '可编辑' : '只读' }}
              </el-tag>
              <span style="margin-left: 12px; color: #909399;">
                {{ currentPermission === 'edit' ? '您可以修改项目内容' : '您只能查看项目内容' }}
              </span>
            </el-form-item>
            <el-form-item label="修改权限">
              <el-radio-group v-model="newPermission">
                <el-radio label="read">只读</el-radio>
                <el-radio label="edit">可编辑</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="updatePermission">保存设置</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="page-card" style="margin-top: 16px;">
          <h3>分享链接</h3>
          <el-alert
            title="分享说明"
            type="info"
            :closable="false"
            style="margin-bottom: 16px;">
            生成分享链接后，其他人可以通过链接访问您的项目。链接会携带权限标识。
          </el-alert>
          
          <el-form :inline="true">
            <el-form-item label="链接权限">
              <el-select v-model="sharePermission" style="width: 150px;">
                <el-option label="只读" value="read" />
                <el-option label="可编辑" value="edit" />
              </el-select>
            </el-form-item>
            <el-form-item label="有效期">
              <el-select v-model="shareExpire" style="width: 150px;">
                <el-option label="7天" :value="7" />
                <el-option label="30天" :value="30" />
                <el-option label="90天" :value="90" />
                <el-option label="永久" :value="0" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="generateShareLink">
                <el-icon><Link /></el-icon>
                生成链接
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 已生成的链接 -->
          <div v-if="shareLinks.length > 0" style="margin-top: 20px;">
            <h4>已生成的分享链接</h4>
            <el-table :data="shareLinks" stripe>
              <el-table-column prop="url" label="链接" min-width="250">
                <template #default="{ row }">
                  <el-input v-model="row.url" readonly size="small" style="width: 100%;">
                    <template #append>
                      <el-button @click="copyLink(row.url)" size="small">复制</el-button>
                    </template>
                  </el-input>
                </template>
              </el-table-column>
              <el-table-column prop="permission" label="权限" width="100">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.permission === 'edit' ? '可编辑' : '只读' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="expires_at" label="有效期" width="150">
                <template #default="{ row }">
                  {{ row.expires_at ? formatTime(row.expires_at) : '永久' }}
                </template>
              </el-table-column>
              <el-table-column prop="views" label="访问量" width="80" />
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" type="danger" @click="revokeLink(row)">撤销</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <div class="page-card" style="margin-top: 16px;">
          <h3>访问统计</h3>
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-title">总访问次数</div>
                <div class="stat-value">{{ accessStats.total_views }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-title">今日访问</div>
                <div class="stat-value">{{ accessStats.today_views }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-title">独立访客</div>
                <div class="stat-value">{{ accessStats.unique_visitors }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-title">活跃分享链接</div>
                <div class="stat-value">{{ accessStats.active_links }}</div>
              </div>
            </el-col>
          </el-row>

          <!-- 访问趋势图 -->
          <div ref="accessChartRef" style="width: 100%; height: 300px; margin-top: 20px;"></div>

          <!-- 最近访问记录 -->
          <h4 style="margin-top: 24px;">最近访问记录</h4>
          <el-table :data="recentAccess" stripe>
            <el-table-column prop="visitor" label="访客" width="150" />
            <el-table-column prop="permission" label="权限" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.permission === 'edit' ? '可编辑' : '只读' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="accessed_at" label="访问时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.accessed_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="ip" label="IP地址" width="150" />
            <el-table-column prop="action" label="操作" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 保存为模板对话框 -->
    <el-dialog v-model="showSaveTemplateDialog" title="保存为模板" width="500px">
      <el-form :model="templateForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="templateForm.name" placeholder="输入模板名称" />
        </el-form-item>
        <el-form-item label="模板描述">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" placeholder="描述模板用途" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="templateForm.category" placeholder="选择分类">
            <el-option label="选股策略" value="stock_selection" />
            <el-option label="风控模型" value="risk_control" />
            <el-option label="回测模板" value="backtest" />
            <el-option label="信号策略" value="signal" />
          </el-select>
        </el-form-item>
        <el-form-item label="封面图片">
          <el-upload
            :action="templateCoverUrl"
            :headers="uploadHeaders"
            :limit="1"
            accept="image/*"
            :on-success="handleCoverUploadSuccess"
          >
            <el-button>上传封面</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveTemplateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate" :loading="savingTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download, UploadFilled, DocumentAdd, Folder, Timer, User, Search, Link
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  exportProject, importProject, getExportHistory, downloadExportFile, deleteExportFile,
  getMyTemplates, saveTemplate as apiSaveTemplate, updateTemplate, deleteTemplate as apiDeleteTemplate,
  useTemplate as apiUseTemplate, getMarketTemplates, installTemplate as apiInstallTemplate,
  uploadTemplateCover,
  getShareLinks, createShareLink, revokeShareLink, getAccessStats, getRecentAccess,
  updateProjectPermission
} from '@/api'

const activeTab = ref('export')

// 导出相关
const exportName = ref('')
const exportInclude = ref(['database', 'models', 'results', 'config'])
const exporting = ref(false)
const exportHistory = ref([])

// 导入相关
const importUrl = '/api/project/import'
const uploadHeaders = {}

// 模板相关
const showSaveTemplateDialog = ref(false)
const savingTemplate = ref(false)
const templateForm = ref({
  name: '',
  description: '',
  category: '',
  cover: ''
})
const templateCoverUrl = '/api/template/cover'
const myTemplates = ref([])
const templateCategory = ref('')
const templateSearch = ref('')
const marketTemplates = ref([])

// 协作相关
const currentPermission = ref('edit')
const newPermission = ref('edit')
const sharePermission = ref('read')
const shareExpire = ref(30)
const shareLinks = ref([])
const accessStats = ref({
  total_views: 0,
  today_views: 0,
  unique_visitors: 0,
  active_links: 0
})
const recentAccess = ref([])
const accessChartRef = ref(null)
let accessChart = null

onMounted(() => {
  fetchExportHistory()
  fetchMyTemplates()
  fetchMarketTemplates()
  fetchShareLinks()
  fetchAccessStats()
  fetchRecentAccess()
  initAccessChart()
})

onUnmounted(() => {
  if (accessChart) {
    accessChart.dispose()
  }
})

// 导出功能
async function handleExport() {
  if (!exportName.value.trim()) {
    ElMessage.warning('请输入导出项目名称')
    return
  }
  if (exportInclude.value.length === 0) {
    ElMessage.warning('请至少选择一个导出范围')
    return
  }
  
  exporting.value = true
  try {
    await exportProject({
      name: exportName.value,
      include: exportInclude.value
    })
    ElMessage.success('导出任务已创建，请等待完成')
    fetchExportHistory()
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    exporting.value = false
  }
}

async function fetchExportHistory() {
  try {
    const data = await getExportHistory()
    exportHistory.value = data.data || []
  } catch (e) {
    console.error('获取导出历史失败:', e)
    exportHistory.value = []
  }
}

async function downloadExport(row) {
  try {
    const res = await downloadExportFile(row.id)
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.name || 'export.zip'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('开始下载: ' + row.name)
  } catch (e) {
    ElMessage.error('下载失败: ' + (e?.response?.data?.detail || e.message))
  }
}

async function deleteExport(row) {
  try {
    await ElMessageBox.confirm('确定要删除这个导出文件吗？', '提示')
    await deleteExportFile(row.id)
    exportHistory.value = exportHistory.value.filter(e => e.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e?.response?.data?.detail || e.message))
    }
  }
}

// 导入功能
function beforeUpload(file) {
  const isZip = file.name.endsWith('.zip')
  const isLt500M = file.size / 1024 / 1024 < 500

  if (!isZip) {
    ElMessage.error('只能上传ZIP文件')
    return false
  }
  if (!isLt500M) {
    ElMessage.error('文件大小不能超过500MB')
    return false
  }
  return true
}

function handleImportSuccess(res) {
  ElMessage.success('导入成功')
}

function handleImportError(err) {
  ElMessage.error('导入失败: ' + (err.message || '未知错误'))
}

// 模板功能
async function saveTemplate() {
  if (!templateForm.value.name.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }

  savingTemplate.value = true
  try {
    await apiSaveTemplate({
      name: templateForm.value.name,
      description: templateForm.value.description,
      category: templateForm.value.category,
      cover_url: templateForm.value.cover,
      is_public: templateForm.value.isPublic,
      config: JSON.stringify({ type: 'strategy', params: {} }),
    })
    ElMessage.success('模板已保存')
    showSaveTemplateDialog.value = false
    templateForm.value = { name: '', description: '', category: 'other', cover: '', isPublic: false }
    fetchMyTemplates()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    savingTemplate.value = false
  }
}

function handleCoverUploadSuccess(res) {
  templateForm.value.cover = res.cover_url || res.url
  ElMessage.success('封面上传成功')
}

async function fetchMyTemplates() {
  try {
    const data = await getMyTemplates({ page: 1, page_size: 50 })
    myTemplates.value = data.data || []
  } catch (e) {
    console.error('获取模板列表失败:', e)
    myTemplates.value = []
  }
}

async function fetchMarketTemplates() {
  try {
    const params = { page: 1, page_size: 50 }
    if (templateCategory.value) params.category = templateCategory.value
    if (templateSearch.value) params.search = templateSearch.value
    const data = await getMarketTemplates(params)
    marketTemplates.value = data.data || []
  } catch (e) {
    console.error('获取市场模板失败:', e)
    marketTemplates.value = []
  }
}

function useTemplate(tpl) {
  ElMessageBox.confirm(`确定要使用模板 "${tpl.name}" 创建新项目吗？`, '使用模板', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info'
  }).then(async () => {
    try {
      await apiUseTemplate(tpl.id)
      ElMessage.success('已使用模板创建新项目')
    } catch (e) {
      ElMessage.error('使用模板失败')
    }
  }).catch(() => {})
}

function editTemplate(tpl) {
  ElMessage.info('编辑功能开发中')
}

async function deleteTemplate(tpl) {
  try {
    await ElMessageBox.confirm(`确定要删除模板 "${tpl.name}" 吗？`, '删除模板')
    await apiDeleteTemplate(tpl.id)
    myTemplates.value = myTemplates.value.filter(t => t.id !== tpl.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function previewTemplate(tpl) {
  ElMessage.info('预览功能开发中')
}

async function installTemplate(tpl) {
  try {
    await ElMessageBox.confirm(`确定要安装模板 "${tpl.name}" 吗？`, '安装模板')
    await apiInstallTemplate(tpl.id)
    ElMessage.success('模板安装成功')
    fetchMyTemplates()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('安装失败')
  }
}

// 协作功能
async function updatePermission() {
  try {
    await updateProjectPermission({ permission: newPermission.value })
    currentPermission.value = newPermission.value
    ElMessage.success('权限已更新')
  } catch (e) {
    ElMessage.error('更新权限失败: ' + (e?.response?.data?.detail || e.message))
  }
}

async function generateShareLink() {
  try {
    const res = await createShareLink({
      permission: sharePermission.value,
      expires_days: shareExpire.value
    })
    const linkData = res.data || res
    const newLink = {
      id: linkData.id,
      url: linkData.url || `https://example.com/share/${linkData.token}`,
      permission: sharePermission.value,
      expires_at: shareExpire.value > 0 ? new Date(Date.now() + shareExpire.value * 86400000).toISOString() : null,
      views: 0
    }
    shareLinks.value.push(newLink)
    ElMessage.success('分享链接已生成')
  } catch (e) {
    ElMessage.error('生成失败: ' + (e?.response?.data?.detail || e.message))
  }
}

function copyLink(url) {
  navigator.clipboard.writeText(url).then(() => {
    ElMessage.success('链接已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

async function revokeLink(row) {
  try {
    await ElMessageBox.confirm('确定要撤销这个分享链接吗？', '撤销链接')
    await revokeShareLink(row.id)
    shareLinks.value = shareLinks.value.filter(l => l.id !== row.id)
    ElMessage.success('链接已撤销')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('撤销失败: ' + (e?.response?.data?.detail || e.message))
    }
  }
}

async function fetchShareLinks() {
  try {
    const data = await getShareLinks()
    shareLinks.value = data.data || []
  } catch (e) {
    console.error('获取分享链接失败:', e)
    shareLinks.value = []
  }
}

async function fetchAccessStats() {
  try {
    const data = await getAccessStats()
    accessStats.value = data.data || {
      total_views: 0,
      today_views: 0,
      unique_visitors: 0,
      active_links: 0
    }
  } catch (e) {
    console.error('获取访问统计失败:', e)
    accessStats.value = {
      total_views: 0,
      today_views: 0,
      unique_visitors: 0,
      active_links: 0
    }
  }
}

async function fetchRecentAccess() {
  try {
    const data = await getRecentAccess()
    recentAccess.value = data.data || []
  } catch (e) {
    console.error('获取最近访问失败:', e)
    recentAccess.value = []
  }
}

function initAccessChart() {
  if (!accessChartRef.value) return
  
  accessChart = echarts.init(accessChartRef.value)
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['访问次数', '独立访客']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['03-24', '03-25', '03-26', '03-27', '03-28', '03-29', '03-30']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '访问次数',
        type: 'line',
        smooth: true,
        data: [12, 15, 8, 20, 18, 14, 12],
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ])
        }
      },
      {
        name: '独立访客',
        type: 'line',
        smooth: true,
        data: [5, 7, 4, 9, 8, 6, 5]
      }
    ]
  }
  accessChart.setOption(option)
}

// 响应式
window.addEventListener('resize', () => {
  accessChart?.resize()
})

// 工具函数
function formatTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.share-page {
  padding: 0;
}

.share-tabs {
  padding: 0 20px;
}

h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

h4 {
  margin: 16px 0 12px;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.page-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.template-grid {
  margin-top: 16px;
}

.template-card {
  background: #fff;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 16px;
}

.template-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.template-cover {
  height: 120px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.template-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.template-cover-placeholder {
  color: #c0c4cc;
}

.template-info {
  padding: 12px;
}

.template-info h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 500;
}

.template-desc {
  color: #909399;
  font-size: 12px;
  margin: 0 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 12px;
}

.template-meta .el-icon {
  margin-right: 2px;
}

.template-actions {
  padding: 12px;
  border-top: 1px solid #eaeaea;
  display: flex;
  gap: 8px;
}

.upload-area {
  width: 100%;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  padding: 20px;
  color: #fff;
  text-align: center;
}

.stat-card:nth-child(2) {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-card:nth-child(3) {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.stat-card:nth-child(4) {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stat-title {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>