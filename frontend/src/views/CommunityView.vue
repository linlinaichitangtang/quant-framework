<template>
  <div class="community-page">
    <el-tabs v-model="activeTab" class="community-tabs">
      <!-- Tab 1: 讨论区 -->
      <el-tab-pane label="讨论区" name="discuss">
        <div class="tab-header">
          <!-- 分类筛选 -->
          <div class="filter-bar">
            <el-radio-group v-model="postCategory" size="small" @change="loadPosts">
              <el-radio-button label="all">全部</el-radio-button>
              <el-radio-button label="strategy">策略</el-radio-button>
              <el-radio-button label="market">市场</el-radio-button>
              <el-radio-button label="risk">风控</el-radio-button>
              <el-radio-button label="question">问答</el-radio-button>
            </el-radio-group>
            <!-- 排序 -->
            <el-radio-group v-model="postSort" size="small" @change="loadPosts" style="margin-left: 12px;">
              <el-radio-button label="latest">最新</el-radio-button>
              <el-radio-button label="hot">最热</el-radio-button>
              <el-radio-button label="featured">精华</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 帖子列表 -->
        <div v-loading="postsLoading" class="post-list">
          <el-card
            v-for="post in posts"
            :key="post.id"
            class="post-card"
            shadow="hover"
            @click="viewPost(post)"
          >
            <div class="post-header">
              <el-avatar :size="36" :src="post.author_avatar || undefined">
                {{ post.author_name?.charAt(0) || '?' }}
              </el-avatar>
              <div class="post-meta">
                <span class="post-author">{{ post.author_name }}</span>
                <span class="post-time">{{ formatTime(post.created_at) }}</span>
              </div>
              <el-tag v-if="post.is_pinned" type="warning" size="small" style="margin-left: auto;">置顶</el-tag>
              <el-tag v-if="post.is_featured" type="success" size="small" style="margin-left: 4px;">精华</el-tag>
            </div>
            <div class="post-title">{{ post.title }}</div>
            <div class="post-content">{{ post.content?.substring(0, 150) }}{{ post.content?.length > 150 ? '...' : '' }}</div>
            <div class="post-tags" v-if="post.tags && post.tags.length">
              <el-tag v-for="tag in post.tags" :key="tag" size="small" type="info" style="margin-right: 4px;">{{ tag }}</el-tag>
            </div>
            <div class="post-actions">
              <span class="action-item" :class="{ liked: post.is_liked }" @click.stop="toggleLike(post)">
                <el-icon><Star /></el-icon> {{ post.likes_count }}
              </span>
              <span class="action-item">
                <el-icon><ChatLineSquare /></el-icon> {{ post.comments_count }}
              </span>
              <span class="action-item">
                <el-icon><View /></el-icon> {{ post.views_count }}
              </span>
            </div>
          </el-card>

          <el-empty v-if="!postsLoading && posts.length === 0" description="暂无帖子" />
        </div>

        <!-- 分页 -->
        <div class="pagination-wrapper" v-if="postsTotal > postPageSize">
          <el-pagination
            v-model:current-page="postPage"
            :page-size="postPageSize"
            :total="postsTotal"
            layout="prev, pager, next"
            @current-change="loadPosts"
          />
        </div>

        <!-- 发帖浮动按钮 -->
        <el-button
          type="primary"
          class="fab-button"
          :icon="Edit"
          circle
          @click="showCreatePost = true"
        />

        <!-- 发帖对话框 -->
        <el-dialog v-model="showCreatePost" title="发布帖子" width="600px" :close-on-click-modal="false">
          <el-form :model="newPost" label-width="80px">
            <el-form-item label="标题">
              <el-input v-model="newPost.title" placeholder="请输入帖子标题" maxlength="200" show-word-limit />
            </el-form-item>
            <el-form-item label="分类">
              <el-select v-model="newPost.category" style="width: 100%;">
                <el-option label="综合" value="general" />
                <el-option label="策略" value="strategy" />
                <el-option label="市场" value="market" />
                <el-option label="风控" value="risk" />
                <el-option label="问答" value="question" />
              </el-select>
            </el-form-item>
            <el-form-item label="内容">
              <el-input v-model="newPost.content" type="textarea" :rows="6" placeholder="请输入帖子内容" />
            </el-form-item>
            <el-form-item label="标签">
              <el-select v-model="newPost.tags" multiple filterable allow-create default-first-option placeholder="输入标签后回车" style="width: 100%;">
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showCreatePost = false">取消</el-button>
            <el-button type="primary" :loading="submitting" @click="submitPost">发布</el-button>
          </template>
        </el-dialog>

        <!-- 帖子详情对话框 -->
        <el-dialog v-model="showPostDetail" :title="currentPost?.title" width="700px" top="5vh">
          <div v-if="currentPost" class="post-detail">
            <div class="post-header">
              <el-avatar :size="40" :src="currentPost.author_avatar || undefined">
                {{ currentPost.author_name?.charAt(0) || '?' }}
              </el-avatar>
              <div class="post-meta">
                <span class="post-author">{{ currentPost.author_name }}</span>
                <span class="post-time">{{ formatTime(currentPost.created_at) }}</span>
              </div>
            </div>
            <div class="post-detail-content">{{ currentPost.content }}</div>
            <div class="post-tags" v-if="currentPost.tags && currentPost.tags.length" style="margin-top: 12px;">
              <el-tag v-for="tag in currentPost.tags" :key="tag" size="small" type="info" style="margin-right: 4px;">{{ tag }}</el-tag>
            </div>
            <div class="post-actions" style="margin-top: 12px;">
              <span class="action-item" :class="{ liked: currentPost.is_liked }" @click="toggleLike(currentPost)">
                <el-icon><Star /></el-icon> {{ currentPost.likes_count }}
              </span>
              <span class="action-item">
                <el-icon><ChatLineSquare /></el-icon> {{ currentPost.comments_count }}
              </span>
              <span class="action-item">
                <el-icon><View /></el-icon> {{ currentPost.views_count }}
              </span>
            </div>

            <!-- 评论区 -->
            <el-divider>评论</el-divider>
            <div class="comment-list">
              <div v-for="comment in postComments" :key="comment.id" class="comment-item">
                <div class="comment-header">
                  <el-avatar :size="28">{{ comment.author_name?.charAt(0) || '?' }}</el-avatar>
                  <span class="comment-author">{{ comment.author_name }}</span>
                  <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
                </div>
                <div class="comment-content">{{ comment.content }}</div>
                <!-- 子评论 -->
                <div v-if="comment.replies && comment.replies.length" class="reply-list">
                  <div v-for="reply in comment.replies" :key="reply.id" class="reply-item">
                    <el-avatar :size="22">{{ reply.author_name?.charAt(0) || '?' }}</el-avatar>
                    <span class="reply-author">{{ reply.author_name }}</span>
                    <span class="reply-content">{{ reply.content }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-if="postComments.length === 0" description="暂无评论" :image-size="60" />
            </div>

            <!-- 发表评论 -->
            <div class="comment-input">
              <el-input
                v-model="newComment"
                placeholder="发表评论..."
                @keyup.enter="submitComment"
              >
                <template #append>
                  <el-button :loading="commentSubmitting" @click="submitComment">发送</el-button>
                </template>
              </el-input>
            </div>
          </div>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 2: 交易分享 -->
      <el-tab-pane label="交易分享" name="trades">
        <div class="tab-header" style="justify-content: flex-end;">
          <el-button type="primary" size="small" @click="showShareTrade = true">分享交易</el-button>
        </div>

        <div v-loading="tradesLoading" class="trade-list">
          <el-card v-for="trade in sharedTrades" :key="trade.id" class="trade-card" shadow="hover">
            <div class="trade-header">
              <el-avatar :size="32" v-if="!trade.is_anonymous">
                {{ trade.username?.charAt(0) || '?' }}
              </el-avatar>
              <el-avatar :size="32" v-else>
                <el-icon><Hide /></el-icon>
              </el-avatar>
              <div class="trade-meta">
                <span class="trade-user">{{ trade.is_anonymous ? '匿名用户' : trade.username }}</span>
                <span class="trade-time">{{ formatTime(trade.created_at) }}</span>
              </div>
              <el-tag :type="trade.side === 'BUY' ? 'danger' : 'success'" size="small">
                {{ trade.side === 'BUY' ? '买入' : '卖出' }}
              </el-tag>
            </div>
            <div class="trade-info">
              <div class="trade-symbol">
                <span class="symbol-code">{{ trade.symbol }}</span>
                <el-tag size="small" type="info">{{ trade.market }}</el-tag>
              </div>
              <div class="trade-prices">
                <span v-if="trade.entry_price">入场: {{ trade.entry_price }}</span>
                <span v-if="trade.exit_price">出场: {{ trade.exit_price }}</span>
              </div>
              <div class="trade-pnl" v-if="trade.pnl != null">
                <span :class="trade.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'">
                  {{ trade.pnl >= 0 ? '+' : '' }}{{ trade.pnl?.toFixed(2) }}
                </span>
                <span v-if="trade.pnl_pct != null" :class="trade.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'" style="margin-left: 8px;">
                  {{ trade.pnl_pct >= 0 ? '+' : '' }}{{ trade.pnl_pct?.toFixed(2) }}%
                </span>
              </div>
            </div>
            <div class="trade-reasoning" v-if="trade.reasoning">
              {{ trade.reasoning }}
            </div>
            <div class="trade-strategy" v-if="trade.strategy_name">
              <el-tag size="small" type="warning">{{ trade.strategy_name }}</el-tag>
            </div>
            <div class="trade-actions">
              <span class="action-item">
                <el-icon><Star /></el-icon> {{ trade.likes_count }}
              </span>
              <span class="action-item">
                <el-icon><ChatLineSquare /></el-icon> {{ trade.comments_count }}
              </span>
            </div>
          </el-card>

          <el-empty v-if="!tradesLoading && sharedTrades.length === 0" description="暂无交易分享" />
        </div>

        <div class="pagination-wrapper" v-if="tradesTotal > tradePageSize">
          <el-pagination
            v-model:current-page="tradePage"
            :page-size="tradePageSize"
            :total="tradesTotal"
            layout="prev, pager, next"
            @current-change="loadSharedTrades"
          />
        </div>

        <!-- 分享交易对话框 -->
        <el-dialog v-model="showShareTrade" title="分享交易" width="550px" :close-on-click-modal="false">
          <el-form :model="newTrade" label-width="80px">
            <el-form-item label="匿名分享">
              <el-switch v-model="newTrade.is_anonymous" />
            </el-form-item>
            <el-form-item label="股票代码">
              <el-input v-model="newTrade.symbol" placeholder="如 600519" />
            </el-form-item>
            <el-form-item label="市场">
              <el-select v-model="newTrade.market" style="width: 100%;">
                <el-option label="A股" value="A" />
                <el-option label="港股" value="HK" />
                <el-option label="美股" value="US" />
              </el-select>
            </el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="newTrade.side">
                <el-radio label="BUY">买入</el-radio>
                <el-radio label="SELL">卖出</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="入场价">
              <el-input-number v-model="newTrade.entry_price" :precision="2" :controls="false" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="出场价">
              <el-input-number v-model="newTrade.exit_price" :precision="2" :controls="false" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="数量">
              <el-input-number v-model="newTrade.quantity" :precision="0" :controls="false" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="盈亏金额">
              <el-input-number v-model="newTrade.pnl" :precision="2" :controls="false" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="盈亏比例">
              <el-input-number v-model="newTrade.pnl_pct" :precision="2" :controls="false" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="策略名称">
              <el-input v-model="newTrade.strategy_name" placeholder="使用的策略名称" />
            </el-form-item>
            <el-form-item label="交易逻辑">
              <el-input v-model="newTrade.reasoning" type="textarea" :rows="3" placeholder="分享你的交易逻辑" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showShareTrade = false">取消</el-button>
            <el-button type="primary" :loading="tradeSubmitting" @click="submitTradeShare">分享</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 3: 排行榜 -->
      <el-tab-pane label="排行榜" name="leaderboard">
        <div class="tab-header">
          <!-- 时间筛选 -->
          <el-radio-group v-model="leaderboardPeriod" size="small" @change="loadLeaderboard">
            <el-radio-button label="daily">日榜</el-radio-button>
            <el-radio-button label="weekly">周榜</el-radio-button>
            <el-radio-button label="monthly">月榜</el-radio-button>
            <el-radio-button label="total">总榜</el-radio-button>
          </el-radio-group>
          <!-- 指标切换 -->
          <el-radio-group v-model="leaderboardMetric" size="small" @change="loadLeaderboard" style="margin-left: 12px;">
            <el-radio-button label="total_return">收益率</el-radio-button>
            <el-radio-button label="win_rate">胜率</el-radio-button>
            <el-radio-button label="trade_count">交易数</el-radio-button>
          </el-radio-group>
        </div>

        <div v-loading="leaderboardLoading" class="leaderboard-table">
          <el-table :data="leaderboardData" stripe style="width: 100%;">
            <el-table-column label="排名" width="80" align="center">
              <template #default="{ row }">
                <span v-if="row.rank === 1" class="rank-badge rank-gold">1</span>
                <span v-else-if="row.rank === 2" class="rank-badge rank-silver">2</span>
                <span v-else-if="row.rank === 3" class="rank-badge rank-bronze">3</span>
                <span v-else>{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column label="用户" min-width="150">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <el-avatar :size="32" :src="row.avatar_url || undefined">
                    {{ row.username?.charAt(0) || '?' }}
                  </el-avatar>
                  <div>
                    <div class="lb-username">{{ row.display_name || row.username }}</div>
                    <div class="lb-userid">@{{ row.username }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column :label="metricLabel" width="120" align="right">
              <template #default="{ row }">
                <span :class="row.value >= 0 ? 'pnl-positive' : 'pnl-negative'" class="lb-value">
                  {{ formatMetricValue(row.value) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="交易数" width="100" align="right">
              <template #default="{ row }">{{ row.total_trades }}</template>
            </el-table-column>
            <el-table-column label="胜率" width="100" align="right">
              <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="总盈亏" width="120" align="right">
              <template #default="{ row }">
                <span :class="row.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'">
                  {{ row.total_pnl >= 0 ? '+' : '' }}{{ row.total_pnl?.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!leaderboardLoading && leaderboardData.length === 0" description="暂无排行数据" />
        </div>
      </el-tab-pane>

      <!-- Tab 4: 私信 -->
      <el-tab-pane label="私信" name="messages">
        <div class="messages-layout">
          <!-- 左侧会话列表 -->
          <div class="conversation-list">
            <div class="conv-header">
              <el-input v-model="searchUserQuery" placeholder="搜索用户..." size="small" clearable @keyup.enter="doSearchUsers">
                <template #append>
                  <el-button @click="doSearchUsers"><el-icon><Search /></el-icon></el-button>
                </template>
              </el-input>
            </div>
            <div v-if="searchResults.length > 0" class="search-results">
              <div v-for="user in searchResults" :key="user.user_id" class="conv-item" @click="startConversation(user)">
                <el-avatar :size="36">{{ user.username?.charAt(0) || '?' }}</el-avatar>
                <div class="conv-info">
                  <div class="conv-name">{{ user.display_name || user.username }}</div>
                  <div class="conv-bio">{{ user.bio || '暂无简介' }}</div>
                </div>
              </div>
            </div>
            <div v-else>
              <div
                v-for="conv in conversations"
                :key="conv.other_user_id"
                class="conv-item"
                :class="{ active: currentConvUser?.other_user_id === conv.other_user_id }"
                @click="openConversation(conv)"
              >
                <el-badge :value="conv.unread_count" :hidden="conv.unread_count === 0" :max="99">
                  <el-avatar :size="36" :src="conv.other_user_avatar || undefined">
                    {{ conv.other_user_name?.charAt(0) || '?' }}
                  </el-avatar>
                </el-badge>
                <div class="conv-info">
                  <div class="conv-name">{{ conv.other_user_name }}</div>
                  <div class="conv-last-msg">{{ conv.last_message || '暂无消息' }}</div>
                </div>
                <div class="conv-time" v-if="conv.last_message_time">{{ formatTime(conv.last_message_time) }}</div>
              </div>
              <el-empty v-if="conversations.length === 0" description="暂无会话" :image-size="60" />
            </div>
          </div>

          <!-- 右侧聊天窗口 -->
          <div class="chat-window" v-if="currentConvUser">
            <div class="chat-header">
              <span>{{ currentConvUser.other_user_name }}</span>
            </div>
            <div class="chat-messages" ref="chatMessagesRef">
              <div
                v-for="msg in chatMessages"
                :key="msg.id"
                class="chat-msg"
                :class="{ 'msg-self': msg.sender_id === myUserId, 'msg-other': msg.sender_id !== myUserId }"
              >
                <div class="msg-bubble">{{ msg.content }}</div>
                <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
              </div>
              <el-empty v-if="chatMessages.length === 0" description="暂无消息，发送第一条消息吧" :image-size="60" />
            </div>
            <div class="chat-input">
              <el-input
                v-model="newMessage"
                placeholder="输入消息..."
                @keyup.enter="sendMsg"
                :disabled="msgSending"
              >
                <template #append>
                  <el-button :loading="msgSending" @click="sendMsg">发送</el-button>
                </template>
              </el-input>
            </div>
          </div>
          <div class="chat-placeholder" v-else>
            <el-empty description="选择一个会话开始聊天" />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Star, ChatLineSquare, View, Hide, Search } from '@element-plus/icons-vue'
import {
  getPosts, createPost, getPost, likePost, createComment,
  getSharedTrades, shareTrade,
  getLeaderboard,
  getConversations, getMessages, sendMessage,
  searchUsers
} from '@/api'

// ==================== 通用状态 ====================
const activeTab = ref('discuss')

// ==================== Tab 1: 讨论区 ====================
const postsLoading = ref(false)
const posts = ref([])
const postsTotal = ref(0)
const postPage = ref(1)
const postPageSize = 20
const postCategory = ref('all')
const postSort = ref('latest')

const showCreatePost = ref(false)
const submitting = ref(false)
const newPost = ref({
  title: '',
  content: '',
  category: 'general',
  tags: []
})

const showPostDetail = ref(false)
const currentPost = ref(null)
const postComments = ref([])
const newComment = ref('')
const commentSubmitting = ref(false)

/** 加载帖子列表 */
async function loadPosts() {
  postsLoading.value = true
  try {
    const params = {
      page: postPage.value,
      page_size: postPageSize,
      sort: postSort.value
    }
    if (postCategory.value !== 'all') {
      params.category = postCategory.value
    }
    const res = await getPosts(params)
    const data = res.data?.data || res.data
    posts.value = data?.data || []
    postsTotal.value = data?.total || 0
  } catch (e) {
    console.error('加载帖子失败:', e)
  } finally {
    postsLoading.value = false
  }
}

/** 查看帖子详情 */
async function viewPost(post) {
  try {
    const res = await getPost(post.id)
    const data = res.data?.data || res.data
    currentPost.value = data
    postComments.value = data?.comments || []
    showPostDetail.value = true
  } catch (e) {
    ElMessage.error('加载帖子详情失败')
  }
}

/** 点赞/取消点赞 */
async function toggleLike(post) {
  try {
    const res = await likePost(post.id)
    const data = res.data?.data || res.data
    post.is_liked = data?.is_liked
    post.likes_count += data?.is_liked ? 1 : -1
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

/** 发布帖子 */
async function submitPost() {
  if (!newPost.value.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (!newPost.value.content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  submitting.value = true
  try {
    await createPost(newPost.value)
    ElMessage.success('发布成功')
    showCreatePost.value = false
    newPost.value = { title: '', content: '', category: 'general', tags: [] }
    loadPosts()
  } catch (e) {
    ElMessage.error('发布失败')
  } finally {
    submitting.value = false
  }
}

/** 提交评论 */
async function submitComment() {
  if (!newComment.value.trim()) return
  commentSubmitting.value = true
  try {
    const res = await createComment(currentPost.value.id, { content: newComment.value })
    const data = res.data?.data || res.data
    postComments.value.push(data)
    currentPost.value.comments_count += 1
    newComment.value = ''
  } catch (e) {
    ElMessage.error('评论失败')
  } finally {
    commentSubmitting.value = false
  }
}

// ==================== Tab 2: 交易分享 ====================
const tradesLoading = ref(false)
const sharedTrades = ref([])
const tradesTotal = ref(0)
const tradePage = ref(1)
const tradePageSize = 20

const showShareTrade = ref(false)
const tradeSubmitting = ref(false)
const newTrade = ref({
  is_anonymous: false,
  symbol: '',
  market: 'A',
  side: 'BUY',
  entry_price: null,
  exit_price: null,
  quantity: null,
  pnl: null,
  pnl_pct: null,
  strategy_name: '',
  reasoning: ''
})

/** 加载交易分享列表 */
async function loadSharedTrades() {
  tradesLoading.value = true
  try {
    const res = await getSharedTrades({ page: tradePage.value, page_size: tradePageSize })
    const data = res.data?.data || res.data
    sharedTrades.value = data?.data || []
    tradesTotal.value = data?.total || 0
  } catch (e) {
    console.error('加载交易分享失败:', e)
  } finally {
    tradesLoading.value = false
  }
}

/** 提交交易分享 */
async function submitTradeShare() {
  if (!newTrade.value.symbol.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  tradeSubmitting.value = true
  try {
    await shareTrade(newTrade.value)
    ElMessage.success('分享成功')
    showShareTrade.value = false
    newTrade.value = {
      is_anonymous: false, symbol: '', market: 'A', side: 'BUY',
      entry_price: null, exit_price: null, quantity: null,
      pnl: null, pnl_pct: null, strategy_name: '', reasoning: ''
    }
    loadSharedTrades()
  } catch (e) {
    ElMessage.error('分享失败')
  } finally {
    tradeSubmitting.value = false
  }
}

// ==================== Tab 3: 排行榜 ====================
const leaderboardLoading = ref(false)
const leaderboardData = ref([])
const leaderboardPeriod = ref('total')
const leaderboardMetric = ref('total_return')

const metricLabel = computed(() => {
  const map = { total_return: '收益率', win_rate: '胜率', trade_count: '交易数' }
  return map[leaderboardMetric.value] || '收益率'
})

/** 格式化排行值 */
function formatMetricValue(value) {
  if (leaderboardMetric.value === 'win_rate') {
    return (value * 100).toFixed(1) + '%'
  } else if (leaderboardMetric.value === 'trade_count') {
    return value
  } else {
    return (value >= 0 ? '+' : '') + value?.toFixed(2) + '%'
  }
}

/** 加载排行榜 */
async function loadLeaderboard() {
  leaderboardLoading.value = true
  try {
    const res = await getLeaderboard({
      period: leaderboardPeriod.value,
      metric: leaderboardMetric.value,
      page: 1,
      page_size: 50
    })
    const data = res.data?.data || res.data
    leaderboardData.value = data?.data || []
  } catch (e) {
    console.error('加载排行榜失败:', e)
  } finally {
    leaderboardLoading.value = false
  }
}

// ==================== Tab 4: 私信 ====================
const conversations = ref([])
const currentConvUser = ref(null)
const chatMessages = ref([])
const chatMessagesRef = ref(null)
const newMessage = ref('')
const msgSending = ref(false)
const myUserId = ref(null)
const searchUserQuery = ref('')
const searchResults = ref([])

/** 加载会话列表 */
async function loadConversations() {
  try {
    const res = await getConversations()
    const data = res.data?.data || res.data
    conversations.value = data || []
  } catch (e) {
    console.error('加载会话失败:', e)
  }
}

/** 打开会话 */
async function openConversation(conv) {
  currentConvUser.value = conv
  await loadChatMessages(conv.other_user_id)
}

/** 加载聊天消息 */
async function loadChatMessages(otherUserId) {
  try {
    const res = await getMessages(otherUserId, { page: 1, page_size: 100 })
    const data = res.data?.data || res.data
    chatMessages.value = data?.data || []
    // 滚动到底部
    await nextTick()
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  } catch (e) {
    console.error('加载消息失败:', e)
  }
}

/** 发送消息 */
async function sendMsg() {
  if (!newMessage.value.trim() || !currentConvUser.value) return
  msgSending.value = true
  try {
    const res = await sendMessage({
      receiver_id: currentConvUser.value.other_user_id,
      content: newMessage.value
    })
    const data = res.data?.data || res.data
    chatMessages.value.push(data)
    newMessage.value = ''
    // 滚动到底部
    await nextTick()
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    msgSending.value = false
  }
}

/** 搜索用户 */
async function doSearchUsers() {
  if (!searchUserQuery.value.trim()) {
    searchResults.value = []
    return
  }
  try {
    const res = await searchUsers({ q: searchUserQuery.value, page: 1, page_size: 10 })
    const data = res.data?.data || res.data
    searchResults.value = data?.data || []
  } catch (e) {
    console.error('搜索用户失败:', e)
  }
}

/** 从搜索结果开始会话 */
function startConversation(user) {
  searchResults.value = []
  searchUserQuery.value = ''
  // 查找是否已有会话
  const existing = conversations.value.find(c => c.other_user_id === user.user_id)
  if (existing) {
    openConversation(existing)
  } else {
    currentConvUser.value = {
      other_user_id: user.user_id,
      other_user_name: user.display_name || user.username,
      other_user_avatar: user.avatar_url,
      last_message: null,
      last_message_time: null,
      unread_count: 0
    }
    chatMessages.value = []
  }
}

// ==================== 通用工具 ====================

/** 格式化时间 */
function formatTime(timeStr) {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  return date.toLocaleDateString('zh-CN')
}

/** 获取当前用户ID */
async function fetchMyUserId() {
  try {
    const { getCurrentUser } = await import('@/api')
    const res = await getCurrentUser()
    const data = res.data?.data || res.data
    myUserId.value = data?.id || data?.user_id
  } catch (e) {
    console.error('获取用户信息失败:', e)
  }
}

// ==================== Tab 切换监听 ====================
watch(activeTab, (tab) => {
  if (tab === 'discuss') loadPosts()
  else if (tab === 'trades') loadSharedTrades()
  else if (tab === 'leaderboard') loadLeaderboard()
  else if (tab === 'messages') loadConversations()
})

// ==================== 初始化 ====================
onMounted(() => {
  fetchMyUserId()
  loadPosts()
})
</script>

<style lang="scss" scoped>
.community-page {
  padding: 0;
}

.community-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 16px;
    background: #fff;
    padding: 0 16px;
    border-radius: 8px;
  }
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

/* 帖子列表 */
.post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post-card {
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }
}

.post-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.post-meta {
  display: flex;
  flex-direction: column;
}

.post-author {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
}

.post-time {
  font-size: 12px;
  color: #909399;
}

.post-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  line-height: 1.5;
}

.post-content {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 8px;
}

.post-tags {
  margin-bottom: 8px;
}

.post-actions {
  display: flex;
  gap: 20px;
  padding-top: 8px;
  border-top: 1px solid #f0f2f5;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: #409EFF;
  }

  &.liked {
    color: #f56c6c;
  }
}

/* 浮动按钮 */
.fab-button {
  position: fixed;
  right: 40px;
  bottom: 40px;
  z-index: 100;
  width: 50px;
  height: 50px;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

/* 帖子详情 */
.post-detail-content {
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
}

.comment-list {
  max-height: 400px;
  overflow-y: auto;
}

.comment-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f2f5;

  &:last-child {
    border-bottom: none;
  }
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.comment-author {
  font-weight: 500;
  font-size: 13px;
  color: #303133;
}

.comment-time {
  font-size: 12px;
  color: #909399;
}

.comment-content {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  padding-left: 36px;
}

.reply-list {
  margin-left: 36px;
  margin-top: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

.reply-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
}

.reply-author {
  font-weight: 500;
  color: #409EFF;
}

.reply-content {
  color: #606266;
}

.comment-input {
  margin-top: 16px;
}

/* 交易分享 */
.trade-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.trade-card {
  .trade-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }

  .trade-meta {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .trade-user {
    font-weight: 500;
    font-size: 14px;
  }

  .trade-time {
    font-size: 12px;
    color: #909399;
  }

  .trade-info {
    margin-bottom: 8px;
  }

  .trade-symbol {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .symbol-code {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
  }

  .trade-prices {
    font-size: 13px;
    color: #606266;
    display: flex;
    gap: 16px;
  }

  .trade-pnl {
    font-size: 16px;
    font-weight: 600;
    margin-top: 4px;
  }

  .trade-reasoning {
    font-size: 13px;
    color: #606266;
    line-height: 1.5;
    margin-top: 8px;
    padding: 8px;
    background: #f5f7fa;
    border-radius: 4px;
  }

  .trade-strategy {
    margin-top: 8px;
  }

  .trade-actions {
    display: flex;
    gap: 16px;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid #f0f2f5;
  }
}

/* 盈亏颜色 */
.pnl-positive {
  color: #f56c6c;
}

.pnl-negative {
  color: #67c23a;
}

/* 排行榜 */
.leaderboard-table {
  margin-top: 8px;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 14px;
  color: #fff;
}

.rank-gold {
  background: linear-gradient(135deg, #FFD700, #FFA500);
}

.rank-silver {
  background: linear-gradient(135deg, #C0C0C0, #A0A0A0);
}

.rank-bronze {
  background: linear-gradient(135deg, #CD7F32, #A0522D);
}

.lb-username {
  font-weight: 500;
  font-size: 14px;
}

.lb-userid {
  font-size: 12px;
  color: #909399;
}

.lb-value {
  font-weight: 600;
  font-size: 15px;
}

/* 私信布局 */
.messages-layout {
  display: flex;
  height: calc(100vh - 200px);
  min-height: 500px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.conversation-list {
  width: 280px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.conv-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.search-results {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #f0f2f5;

  &:hover {
    background: #f5f7fa;
  }

  &.active {
    background: #ecf5ff;
  }
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-name {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
}

.conv-bio {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-last-msg {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 11px;
  color: #c0c4cc;
  flex-shrink: 0;
}

/* 聊天窗口 */
.chat-window {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chat-header {
  padding: 14px 16px;
  font-weight: 600;
  font-size: 15px;
  border-bottom: 1px solid #e4e7ed;
  color: #303133;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}

.msg-self {
  align-self: flex-end;
  align-items: flex-end;
}

.msg-other {
  align-self: flex-start;
  align-items: flex-start;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.msg-self .msg-bubble {
  background: #409EFF;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-other .msg-bubble {
  background: #f0f2f5;
  color: #303133;
  border-bottom-left-radius: 4px;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}

.chat-input {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.chat-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}

/* 响应式适配 */
@media screen and (max-width: 767px) {
  .trade-list {
    grid-template-columns: 1fr;
  }

  .messages-layout {
    flex-direction: column;
    height: auto;
    min-height: auto;
  }

  .conversation-list {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid #e4e7ed;
  }

  .chat-window {
    min-height: 400px;
  }

  .fab-button {
    right: 20px;
    bottom: 20px;
    width: 44px;
    height: 44px;
  }

  .filter-bar {
    width: 100%;
    overflow-x: auto;
    flex-wrap: nowrap;
  }

  .post-detail-content {
    font-size: 14px;
  }
}
</style>
