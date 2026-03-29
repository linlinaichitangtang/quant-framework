<template>
  <div class="scene-tree-panel">
    <div class="panel-header">
      <span>场景树</span>
      <el-icon class="refresh-btn" @click="refreshTree" title="刷新">
        <Refresh />
      </el-icon>
    </div>
    <div class="tree-container" v-if="objects.length > 0">
      <div
        v-for="obj in objects"
        :key="obj.id"
        class="tree-item"
        :class="{ selected: selectedObjectId === obj.id }"
        @click="selectObject(obj.id)"
      >
        <span class="item-icon">
          <el-icon>
            <component :is="getTypeIcon(obj.type)" />
          </el-icon>
        </span>
        <span class="item-name" :title="obj.name">{{ obj.name }}</span>
        <div class="item-actions">
          <el-tooltip content="切换可见性" placement="top">
            <el-icon 
              class="action-icon" 
              :class="{ 'invisible': !obj.visible }"
              @click.stop="toggleVisibility(obj.id)"
            >
              <View v-if="obj.visible" />
              <Hide v-else />
            </el-icon>
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-icon class="action-icon delete" @click.stop="deleteObject(obj.id)">
              <Delete />
            </el-icon>
          </el-tooltip>
        </div>
      </div>
    </div>
    <div class="empty-state" v-else>
      <el-icon :size="40" color="#999"><Folder /></el-icon>
      <p>场景为空</p>
      <p class="hint">使用工具栏创建几何体</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSceneStore } from '@/stores/scene'
import { Refresh, View, Hide, Delete, Box, CircleCheck, Histogram, Folder } from '@element-plus/icons-vue'

const store = useSceneStore()

const objects = computed(() => store.objects)
const selectedObjectId = computed(() => store.selectedObjectId)

function getTypeIcon(type) {
  switch (type) {
    case 'box': return Box
    case 'sphere': return CircleCheck
    case 'cylinder': return Histogram
    default: return Box
  }
}

function selectObject(id) {
  store.selectObject(id)
}

function toggleVisibility(id) {
  const obj = store.objects.find(o => o.id === id)
  if (obj) {
    store.setObjectVisibility(id, !obj.visible)
  }
}

function deleteObject(id) {
  store.removeObject(id)
}

function refreshTree() {
  // Force reactivity update
}
</script>

<style scoped>
.scene-tree-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #2d2d2d;
  color: #e0e0e0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  border-bottom: 1px solid #444;
  font-weight: 500;
  font-size: 14px;
}

.refresh-btn {
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.refresh-btn:hover {
  background: #444;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.tree-item {
  display: flex;
  align-items: center;
  padding: 8px 15px;
  cursor: pointer;
  transition: background 0.2s;
  border-left: 3px solid transparent;
}

.tree-item:hover {
  background: #383838;
}

.tree-item.selected {
  background: #409eff30;
  border-left-color: #409eff;
}

.item-icon {
  margin-right: 10px;
  color: #888;
  display: flex;
  align-items: center;
}

.tree-item.selected .item-icon {
  color: #409eff;
}

.item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.item-actions {
  display: none;
  gap: 8px;
  align-items: center;
}

.tree-item:hover .item-actions {
  display: flex;
}

.action-icon {
  cursor: pointer;
  padding: 4px;
  border-radius: 3px;
  color: #888;
  transition: all 0.2s;
}

.action-icon:hover {
  background: #555;
  color: #fff;
}

.action-icon.delete:hover {
  color: #f56c6c;
}

.action-icon.invisible {
  color: #666;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
}

.empty-state p {
  margin: 10px 0 0;
  font-size: 13px;
}

.empty-state .hint {
  font-size: 12px;
  color: #555;
}
</style>