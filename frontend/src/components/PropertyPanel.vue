<template>
  <div class="property-panel">
    <div class="panel-header">
      <span>属性</span>
    </div>
    
    <div class="panel-content" v-if="selectedObject">
      <!-- Basic Info -->
      <div class="property-section">
        <div class="section-title">基本信息</div>
        <div class="property-row">
          <label>名称</label>
          <el-input 
            v-model="objectName" 
            size="small" 
            @change="updateName"
            placeholder="对象名称"
          />
        </div>
        <div class="property-row">
          <label>类型</label>
          <span class="value-display">{{ getTypeLabel(selectedObject.type) }}</span>
        </div>
      </div>
      
      <!-- Transform -->
      <div class="property-section">
        <div class="section-title">变换</div>
        
        <div class="property-row">
          <label>位置</label>
          <div class="vec3-input">
            <el-input-number 
              v-model="position.x" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updatePosition"
            />
            <el-input-number 
              v-model="position.y" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updatePosition"
            />
            <el-input-number 
              v-model="position.z" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updatePosition"
            />
          </div>
        </div>
        
        <div class="property-row">
          <label>旋转</label>
          <div class="vec3-input">
            <el-input-number 
              v-model="rotation.x" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updateRotation"
            />
            <el-input-number 
              v-model="rotation.y" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updateRotation"
            />
            <el-input-number 
              v-model="rotation.z" 
              size="small" 
              :step="0.1" 
              controls-position="right"
              @change="updateRotation"
            />
          </div>
        </div>
        
        <div class="property-row">
          <label>缩放</label>
          <div class="vec3-input">
            <el-input-number 
              v-model="scale.x" 
              size="small" 
              :step="0.1" 
              :min="0.01" 
              controls-position="right"
              @change="updateScale"
            />
            <el-input-number 
              v-model="scale.y" 
              size="small" 
              :step="0.1" 
              :min="0.01" 
              controls-position="right"
              @change="updateScale"
            />
            <el-input-number 
              v-model="scale.z" 
              size="small" 
              :step="0.1" 
              :min="0.01" 
              controls-position="right"
              @change="updateScale"
            />
          </div>
        </div>
      </div>
      
      <!-- Material -->
      <div class="property-section">
        <div class="section-title">材质</div>
        
        <div class="property-row">
          <label>颜色</label>
          <el-color-picker 
            v-model="materialColor" 
            size="small"
            @change="updateMaterialColor"
          />
        </div>
        
        <div class="property-row">
          <label>粗糙度</label>
          <div class="slider-input">
            <el-slider 
              v-model="roughness" 
              :min="0" 
              :max="1" 
              :step="0.01"
              :show-tooltip="true"
              @change="updateMaterial"
            />
            <span class="slider-value">{{ roughness.toFixed(2) }}</span>
          </div>
        </div>
        
        <div class="property-row">
          <label>金属度</label>
          <div class="slider-input">
            <el-slider 
              v-model="metalness" 
              :min="0" 
              :max="1" 
              :step="0.01"
              :show-tooltip="true"
              @change="updateMaterial"
            />
            <span class="slider-value">{{ metalness.toFixed(2) }}</span>
          </div>
        </div>
      </div>
      
      <!-- Actions -->
      <div class="property-section">
        <el-button type="danger" size="small" @click="deleteObject" style="width: 100%;">
          删除对象
        </el-button>
      </div>
    </div>
    
    <div class="empty-state" v-else>
      <el-icon :size="40" color="#999"><Setting /></el-icon>
      <p>未选择对象</p>
      <p class="hint">从场景树或视口中选择对象</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useSceneStore } from '@/stores/scene'
import { Setting } from '@element-plus/icons-vue'

const store = useSceneStore()

const selectedObject = computed(() => store.selectedObject)

// Local state for form fields
const objectName = ref('')
const position = ref({ x: 0, y: 0, z: 0 })
const rotation = ref({ x: 0, y: 0, z: 0 })
const scale = ref({ x: 1, y: 1, z: 1 })
const materialColor = ref('#4488ff')
const roughness = ref(0.5)
const metalness = ref(0.3)

// Sync with selected object
watch(selectedObject, (obj) => {
  if (obj) {
    objectName.value = obj.name
    position.value = {
      x: obj.mesh.position.x,
      y: obj.mesh.position.y,
      z: obj.mesh.position.z
    }
    rotation.value = {
      x: obj.mesh.rotation.x,
      y: obj.mesh.rotation.y,
      z: obj.mesh.rotation.z
    }
    scale.value = {
      x: obj.mesh.scale.x,
      y: obj.mesh.scale.y,
      z: obj.mesh.scale.z
    }
    
    // Material
    if (obj.mesh.material) {
      const color = obj.mesh.material.color
      if (color) {
        materialColor.value = '#' + color.getHexString()
      }
      roughness.value = obj.mesh.material.roughness ?? 0.5
      metalness.value = obj.mesh.material.metalness ?? 0.3
    }
  }
}, { immediate: true, deep: true })

function getTypeLabel(type) {
  const labels = {
    box: '立方体',
    sphere: '球体',
    cylinder: '圆柱体'
  }
  return labels[type] || type
}

function updateName() {
  if (selectedObject.value) {
    const obj = store.objects.find(o => o.id === selectedObject.value.id)
    if (obj) {
      obj.name = objectName.value
    }
  }
}

function updatePosition() {
  if (selectedObject.value) {
    store.updateObjectPosition(selectedObject.value.id, position.value)
  }
}

function updateRotation() {
  if (selectedObject.value) {
    store.updateObjectRotation(selectedObject.value.id, rotation.value)
  }
}

function updateScale() {
  if (selectedObject.value) {
    store.updateObjectScale(selectedObject.value.id, scale.value)
  }
}

function updateMaterialColor() {
  if (selectedObject.value && selectedObject.value.mesh.material) {
    selectedObject.value.mesh.material.color.set(materialColor.value)
  }
}

function updateMaterial() {
  if (selectedObject.value && selectedObject.value.mesh.material) {
    selectedObject.value.mesh.material.roughness = roughness.value
    selectedObject.value.mesh.material.metalness = metalness.value
    selectedObject.value.mesh.material.needsUpdate = true
  }
}

function deleteObject() {
  if (selectedObject.value) {
    store.removeObject(selectedObject.value.id)
  }
}
</script>

<style scoped>
.property-panel {
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

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.property-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid #444;
}

.property-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 12px;
}

.property-row label {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 5px;
}

.value-display {
  font-size: 13px;
  color: #ddd;
}

.vec3-input {
  display: flex;
  gap: 5px;
}

.vec3-input :deep(.el-input-number) {
  flex: 1;
}

.vec3-input :deep(.el-input-number .el-input__wrapper) {
  padding: 0 5px;
}

.slider-input {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider-input :deep(.el-slider) {
  flex: 1;
}

.slider-value {
  font-size: 12px;
  color: #888;
  min-width: 40px;
  text-align: right;
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