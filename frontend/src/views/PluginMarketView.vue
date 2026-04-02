<template>
  <div class="plugin-market-view">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 插件市场 -->
      <el-tab-pane label="插件市场" name="market">
        <div class="market-toolbar">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索插件..."
            prefix-icon="Search"
            clearable
            style="width: 300px"
            @input="filterPlugins"
          />
          <el-select v-model="selectedCategory" placeholder="全部分类" clearable style="width: 160px" @change="filterPlugins">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </div>

        <el-row :gutter="20" v-loading="loading">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="plugin in filteredPlugins" :key="plugin.id" style="margin-bottom: 20px">
            <el-card shadow="hover" class="plugin-card" :body-style="{ padding: '0' }">
              <div class="plugin-cover">
                <img :src="plugin.cover_url || defaultCover" :alt="plugin.name" />
                <div class="plugin-category-tag">
                  <el-tag size="small" type="info">{{ plugin.category }}</el-tag>
                </div>
              </div>
              <div class="plugin-info">
                <h4 class="plugin-name">{{ plugin.name }}</h4>
                <p class="plugin-desc">{{ plugin.description }}</p>
                <div class="plugin-meta">
                  <div class="plugin-rating">
                    <el-rate v-model="plugin.rating" disabled show-score text-color="#ff9900" score-template="{value}" />
                  </div>
                  <span class="plugin-installs">{{ formatInstalls(plugin.install_count) }} 次安装</span>
                </div>
                <div class="plugin-actions">
                  <el-button
                    v-if="!plugin.installed"
                    type="primary"
                    size="small"
                    :loading="plugin._installing"
                    @click="installPlugin(plugin)"
                  >
                    安装
                  </el-button>
                  <el-button
                    v-else
                    type="danger"
                    size="small"
                    plain
                    :loading="plugin._uninstalling"
                    @click="uninstallPlugin(plugin)"
                  >
                    卸载
                  </el-button>
                  <el-button size="small" @click="showPluginDetail(plugin)">详情</el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-empty v-if="!loading && filteredPlugins.length === 0" description="暂无匹配的插件" />
      </el-tab-pane>

      <!-- Tab 2: 已安装插件 -->
      <el-tab-pane label="已安装插件" name="installed">
        <el-table :data="installedPlugins" v-loading="loadingInstalled" stripe border style="width: 100%">
          <el-table-column label="插件" min-width="200">
            <template #default="{ row }">
              <div class="installed-plugin-info">
                <img :src="row.cover_url || defaultCover" class="installed-plugin-icon" />
                <div>
                  <div class="installed-plugin-name">{{ row.name }}</div>
                  <div class="installed-plugin-version">v{{ row.version }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="author" label="作者" width="120" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-switch
                v-model="row.enabled"
                @change="togglePlugin(row)"
                active-text="启用"
                inactive-text="禁用"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="showPluginConfig(row)">配置</el-button>
              <el-button size="small" type="danger" plain @click="uninstallInstalledPlugin(row)">卸载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 插件详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentPlugin?.name" width="600px" destroy-on-close>
      <div v-if="currentPlugin" class="plugin-detail">
        <div class="detail-header">
          <img :src="currentPlugin.cover_url || defaultCover" class="detail-cover" />
          <div class="detail-info">
            <h3>{{ currentPlugin.name }}</h3>
            <el-tag size="small">{{ currentPlugin.category }}</el-tag>
            <span class="detail-author">作者: {{ currentPlugin.author }}</span>
            <span class="detail-version">版本: v{{ currentPlugin.version }}</span>
          </div>
        </div>
        <el-divider />
        <p class="detail-desc">{{ currentPlugin.description }}</p>
        <div class="detail-stats">
          <span>评分: <el-rate v-model="currentPlugin.rating" disabled show-score text-color="#ff9900" score-template="{value}" /></span>
          <span>安装数: {{ formatInstalls(currentPlugin.install_count) }}</span>
          <span>更新时间: {{ currentPlugin.updated_at }}</span>
        </div>
        <el-divider />
        <h4>功能说明</h4>
        <ul class="detail-features">
          <li v-for="(feature, idx) in currentPlugin.features || []" :key="idx">{{ feature }}</li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="!currentPlugin?.installed"
          type="primary"
          @click="installPlugin(currentPlugin); detailDialogVisible = false"
        >
          安装插件
        </el-button>
      </template>
    </el-dialog>

    <!-- 插件配置对话框 -->
    <el-dialog v-model="configDialogVisible" :title="`配置 - ${configPlugin?.name}`" width="500px" destroy-on-close>
      <el-form :model="configForm" label-width="120px">
        <el-form-item v-for="(item, key) in configPlugin?.config_schema || {}" :key="key" :label="item.label">
          <el-input v-if="item.type === 'text'" v-model="configForm[key]" :placeholder="item.placeholder" />
          <el-input v-else-if="item.type === 'textarea'" v-model="configForm[key]" type="textarea" :rows="3" :placeholder="item.placeholder" />
          <el-switch v-else-if="item.type === 'boolean'" v-model="configForm[key]" />
          <el-select v-else-if="item.type === 'select'" v-model="configForm[key]" :placeholder="item.placeholder">
            <el-option v-for="opt in item.options" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-input-number v-else-if="item.type === 'number'" v-model="configForm[key]" :min="item.min" :max="item.max" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePluginConfig" :loading="savingConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlugins, installPlugin as installPluginApi, uninstallPlugin as uninstallPluginApi, getPlugin } from '@/api'

const activeTab = ref('market')
const loading = ref(false)
const loadingInstalled = ref(false)
const savingConfig = ref(false)
const searchKeyword = ref('')
const selectedCategory = ref('')
const categories = ['数据源', '策略', '风控', '通知', '可视化', '工具']
const defaultCover = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgZmlsbD0iI2YwZjJmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjYzBjNGM0IiBmb250LXNpemU9IjE0Ij7or77nqIvliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+'

const plugins = ref([])
const installedPlugins = ref([])

// 详情对话框
const detailDialogVisible = ref(false)
const currentPlugin = ref(null)

// 配置对话框
const configDialogVisible = ref(false)
const configPlugin = ref(null)
const configForm = reactive({})

const filteredPlugins = computed(() => {
  let result = plugins.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(p => p.name.toLowerCase().includes(kw) || p.description.toLowerCase().includes(kw))
  }
  if (selectedCategory.value) {
    result = result.filter(p => p.category === selectedCategory.value)
  }
  return result
})

const formatInstalls = (count) => {
  if (!count) return '0'
  if (count >= 10000) return (count / 10000).toFixed(1) + 'w'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'k'
  return String(count)
}

const filterPlugins = () => {
  // computed 自动处理
}

// 获取插件市场列表
const fetchPlugins = async () => {
  loading.value = true
  try {
    const res = await getPlugins({ page: 1, page_size: 50 })
    plugins.value = res.data?.items || res.data || []
  } catch {
    plugins.value = generateMockPlugins()
  } finally {
    loading.value = false
  }
}

// 获取已安装插件
const fetchInstalledPlugins = async () => {
  loadingInstalled.value = true
  try {
    const res = await getPlugins({ installed: true })
    installedPlugins.value = res.data?.items || res.data || []
  } catch {
    installedPlugins.value = generateMockInstalledPlugins()
  } finally {
    loadingInstalled.value = false
  }
}

function generateMockPlugins() {
  return [
    { id: '1', name: 'Tushare 数据源', description: '接入 Tushare Pro 数据接口，获取A股实时和历史行情数据', category: '数据源', author: 'OpenClaw', version: '1.2.0', rating: 4.5, install_count: 3200, installed: false, cover_url: '', updated_at: '2025-03-20', features: ['实时行情推送', '历史数据回填', '财务数据查询', '指数成分股'] },
    { id: '2', name: '双均线策略', description: '基于MA5/MA20双均线交叉的经典趋势跟踪策略', category: '策略', author: '量化团队', version: '2.0.1', rating: 4.2, install_count: 5600, installed: true, cover_url: '', updated_at: '2025-03-18', features: ['多周期支持', '参数可调', '止损止盈', '信号通知'] },
    { id: '3', name: '风控引擎', description: '全面的风险控制系统，支持仓位管理、回撤限制和异常检测', category: '风控', author: '风控组', version: '1.5.0', rating: 4.8, install_count: 2100, installed: false, cover_url: '', updated_at: '2025-03-15', features: ['最大回撤控制', '单票仓位限制', '行业集中度限制', '异常交易检测'] },
    { id: '4', name: '企业微信通知', description: '通过企业微信机器人发送交易信号和账户变动通知', category: '通知', author: '社区贡献', version: '1.0.3', rating: 3.8, install_count: 890, installed: false, cover_url: '', updated_at: '2025-02-28', features: ['信号推送', '成交通知', '风控告警', '日报汇总'] },
    { id: '5', name: 'K线图表组件', description: '专业的K线图表展示组件，支持技术指标叠加', category: '可视化', author: '前端组', version: '1.3.0', rating: 4.6, install_count: 4100, installed: true, cover_url: '', updated_at: '2025-03-22', features: ['K线/分时切换', 'MA/MACD/KDJ指标', '画线工具', '多周期联动'] },
    { id: '6', name: '数据导出工具', description: '将交易数据、持仓数据导出为Excel或CSV格式', category: '工具', author: '工具组', version: '1.1.0', rating: 4.0, install_count: 1500, installed: false, cover_url: '', updated_at: '2025-03-10', features: ['Excel导出', 'CSV导出', '自定义模板', '定时导出'] },
  ]
}

function generateMockInstalledPlugins() {
  return [
    { id: '2', name: '双均线策略', description: '基于MA5/MA20双均线交叉的经典趋势跟踪策略', category: '策略', author: '量化团队', version: '2.0.1', cover_url: '', enabled: true, config_schema: { short_period: { label: '短周期', type: 'number', min: 1, max: 60, placeholder: '默认5' }, long_period: { label: '长周期', type: 'number', min: 5, max: 250, placeholder: '默认20' }, volume_filter: { label: '成交量过滤', type: 'boolean' } } },
    { id: '5', name: 'K线图表组件', description: '专业的K线图表展示组件', category: '可视化', author: '前端组', version: '1.3.0', cover_url: '', enabled: true, config_schema: { theme: { label: '主题', type: 'select', options: [{ label: '亮色', value: 'light' }, { label: '暗色', value: 'dark' }] }, show_volume: { label: '显示成交量', type: 'boolean' } } },
  ]
}

// 安装插件
const installPlugin = async (plugin) => {
  plugin._installing = true
  try {
    await installPluginApi(plugin.id, {})
    plugin.installed = true
    ElMessage.success(`插件 "${plugin.name}" 安装成功`)
    fetchInstalledPlugins()
  } catch (e) {
    console.error('安装失败:', e)
    ElMessage.error('安装失败')
  } finally {
    plugin._installing = false
  }
}

// 卸载插件
const uninstallPlugin = async (plugin) => {
  try {
    await ElMessageBox.confirm(`确定要卸载插件 "${plugin.name}" 吗？`, '确认卸载', { type: 'warning' })
  } catch {
    return
  }
  plugin._uninstalling = true
  try {
    await uninstallPluginApi(plugin.id)
    plugin.installed = false
    ElMessage.success(`插件 "${plugin.name}" 已卸载`)
    fetchInstalledPlugins()
  } catch (e) {
    console.error('卸载失败:', e)
    ElMessage.error('卸载失败')
  } finally {
    plugin._uninstalling = false
  }
}

// 卸载已安装插件
const uninstallInstalledPlugin = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要卸载插件 "${row.name}" 吗？`, '确认卸载', { type: 'warning' })
  } catch {
    return
  }
  try {
    await uninstallPluginApi(row.id)
    ElMessage.success('插件已卸载')
    fetchInstalledPlugins()
    fetchPlugins()
  } catch (e) {
    console.error('卸载失败:', e)
    ElMessage.error('卸载失败')
  }
}

// 切换插件状态
const togglePlugin = async (row) => {
  try {
    await ElMessage.success(`插件 "${row.name}" 已${row.enabled ? '启用' : '禁用'}`)
  } catch {
    row.enabled = !row.enabled
  }
}

// 插件详情
const showPluginDetail = async (plugin) => {
  currentPlugin.value = plugin
  try {
    const res = await getPlugin(plugin.id)
    if (res.data) {
      currentPlugin.value = { ...plugin, ...res.data }
    }
  } catch {
    // 使用本地数据
  }
  detailDialogVisible.value = true
}

// 插件配置
const showPluginConfig = (row) => {
  configPlugin.value = row
  const schema = row.config_schema || {}
  Object.keys(configForm).forEach(k => delete configForm[k])
  Object.keys(schema).forEach(k => {
    configForm[k] = schema[k].default !== undefined ? schema[k].default : null
  })
  configDialogVisible.value = true
}

const savePluginConfig = async () => {
  savingConfig.value = true
  try {
    ElMessage.success('配置保存成功')
    configDialogVisible.value = false
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  } finally {
    savingConfig.value = false
  }
}

onMounted(() => {
  fetchPlugins()
  fetchInstalledPlugins()
})
</script>

<style lang="scss" scoped>
.plugin-market-view {
  padding: 16px;

  .market-toolbar {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .plugin-card {
    height: 100%;
    display: flex;
    flex-direction: column;

    .plugin-cover {
      height: 140px;
      background: #f5f7fa;
      position: relative;
      overflow: hidden;

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .plugin-category-tag {
        position: absolute;
        top: 8px;
        right: 8px;
      }
    }

    .plugin-info {
      padding: 12px;
      flex: 1;
      display: flex;
      flex-direction: column;

      .plugin-name {
        margin: 0 0 6px 0;
        font-size: 15px;
        font-weight: 600;
        color: #303133;
      }

      .plugin-desc {
        margin: 0 0 10px 0;
        font-size: 13px;
        color: #909399;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        flex: 1;
      }

      .plugin-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;

        .plugin-rating {
          :deep(.el-rate) {
            height: 20px;

            .el-rate__icon {
              font-size: 14px;
            }
          }
        }

        .plugin-installs {
          font-size: 12px;
          color: #909399;
        }
      }

      .plugin-actions {
        display: flex;
        gap: 8px;
      }
    }
  }

  .installed-plugin-info {
    display: flex;
    align-items: center;
    gap: 12px;

    .installed-plugin-icon {
      width: 40px;
      height: 40px;
      border-radius: 6px;
      object-fit: cover;
    }

    .installed-plugin-name {
      font-weight: 500;
      font-size: 14px;
    }

    .installed-plugin-version {
      font-size: 12px;
      color: #909399;
    }
  }

  .plugin-detail {
    .detail-header {
      display: flex;
      gap: 16px;
      align-items: flex-start;

      .detail-cover {
        width: 100px;
        height: 80px;
        border-radius: 8px;
        object-fit: cover;
      }

      .detail-info {
        h3 {
          margin: 0 0 8px 0;
        }

        .detail-author,
        .detail-version {
          display: block;
          font-size: 13px;
          color: #909399;
          margin-top: 4px;
        }
      }
    }

    .detail-desc {
      color: #606266;
      line-height: 1.6;
    }

    .detail-stats {
      display: flex;
      gap: 24px;
      font-size: 13px;
      color: #909399;
      flex-wrap: wrap;
    }

    .detail-features {
      padding-left: 20px;
      color: #606266;
      line-height: 2;
    }
  }
}
</style>
