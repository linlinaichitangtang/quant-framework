<template>
  <div class="viewport-3d" ref="containerRef">
    <canvas ref="canvasRef"></canvas>
    <div class="viewport-controls">
      <el-button-group>
        <el-tooltip content="选择模式" placement="left">
          <el-button :type="mode === 'select' ? 'primary' : ''" @click="setMode('select')">
            <el-icon><Pointer /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="移动模式" placement="left">
          <el-button :type="mode === 'move' ? 'primary' : ''" @click="setMode('move')">
            <el-icon><Move /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="旋转模式" placement="left">
          <el-button :type="mode === 'rotate' ? 'primary' : ''" @click="setMode('rotate')">
            <el-icon><RefreshRight /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="缩放模式" placement="left">
          <el-button :type="mode === 'scale' ? 'primary' : ''" @click="setMode('scale')">
            <el-icon><ZoomIn /></el-icon>
          </el-button>
        </el-tooltip>
      </el-button-group>
    </div>
    <div class="viewport-toolbar">
      <el-button-group>
        <el-tooltip content="创建立方体" placement="top">
          <el-button :type="createTool === 'box' ? 'success' : ''" @click="setCreateTool('box')">
            <el-icon><Box /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="创建球体" placement="top">
          <el-button :type="createTool === 'sphere' ? 'success' : ''" @click="setCreateTool('sphere')">
            <el-icon><CircleCheck /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="创建圆柱体" placement="top">
          <el-button :type="createTool === 'cylinder' ? 'success' : ''" @click="setCreateTool('cylinder')">
            <el-icon><Histogram /></el-icon>
          </el-button>
        </el-tooltip>
      </el-button-group>
      <el-divider direction="vertical" />
      <el-button-group>
        <el-tooltip content="撤销" placement="top">
          <el-button @click="undo" :disabled="historyIndex <= 0">
            <el-icon><Back /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="重做" placement="top">
          <el-button @click="redo" :disabled="historyIndex >= history.length - 1">
            <el-icon><Right /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="清空场景" placement="top">
          <el-button @click="clearScene" :disabled="objects.length === 0">
            <el-icon><Delete /></el-icon>
          </el-button>
        </el-tooltip>
      </el-button-group>
    </div>
    <div class="viewport-info">
      <span>{{ objects.length }} 对象</span>
      <span v-if="selectedObject">| {{ selectedObject.name }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { useSceneStore } from '@/stores/scene'
import { Pointer, Position, RefreshRight, ZoomIn, Box, CircleCheck, Histogram, Back, Right, Delete } from '@element-plus/icons-vue'

const containerRef = ref(null)
const canvasRef = ref(null)

// Three.js instances
let scene, camera, renderer, controls
let raycaster, mouse
let transformControls = null

// Store
const store = useSceneStore()

const mode = computed(() => store.mode)
const createTool = computed(() => store.createTool)
const objects = computed(() => store.objects)
const selectedObject = computed(() => store.selectedObject)
const historyIndex = computed(() => store.historyIndex)
const history = computed(() => store.history)

function init() {
  const container = containerRef.value
  const canvas = canvasRef.value
  
  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)
  
  // Camera
  const aspect = container.clientWidth / container.clientHeight
  camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000)
  camera.position.set(5, 5, 5)
  
  // Renderer
  renderer = new THREE.WebGLRenderer({ 
    canvas, 
    antialias: true,
    alpha: true
  })
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  
  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.screenSpacePanning = true
  controls.minDistance = 1
  controls.maxDistance = 100
  
  // Grid
  const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222)
  scene.add(gridHelper)
  
  // Axes helper
  const axesHelper = new THREE.AxesHelper(2)
  scene.add(axesHelper)
  
  // Lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
  scene.add(ambientLight)
  
  const directionalLight = new THREE.DirectionalLight(0xffffff, 1)
  directionalLight.position.set(10, 20, 10)
  directionalLight.castShadow = true
  directionalLight.shadow.mapSize.width = 2048
  directionalLight.shadow.mapSize.height = 2048
  directionalLight.shadow.camera.near = 0.5
  directionalLight.shadow.camera.far = 50
  directionalLight.shadow.camera.left = -20
  directionalLight.shadow.camera.right = 20
  directionalLight.shadow.camera.top = 20
  directionalLight.shadow.camera.bottom = -20
  scene.add(directionalLight)
  
  const fillLight = new THREE.DirectionalLight(0x4488ff, 0.3)
  fillLight.position.set(-10, 5, -10)
  scene.add(fillLight)
  
  // Raycaster for selection
  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  
  // Ground plane for shadows
  const groundGeometry = new THREE.PlaneGeometry(20, 20)
  const groundMaterial = new THREE.ShadowMaterial({ opacity: 0.3 })
  const ground = new THREE.Mesh(groundGeometry, groundMaterial)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  ground.name = '__ground__'
  scene.add(ground)
  
  // Sync store objects to scene
  syncStoreToScene()
  
  // Animation loop
  animate()
}

function syncStoreToScene() {
  // Clear non-persistent objects
  const toRemove = []
  scene.traverse((child) => {
    if (child.userData.storeId && !store.objects.find(o => o.id === child.userData.storeId)) {
      toRemove.push(child)
    }
  })
  toRemove.forEach(child => {
    scene.remove(child)
  })
  
  // Add store objects to scene
  store.objects.forEach(obj => {
    if (!scene.getObjectByProperty('userData.storeId', obj.id)) {
      obj.mesh.userData.storeId = obj.id
      scene.add(obj.mesh)
    } else {
      // Update existing
      const existing = scene.getObjectByProperty('userData.storeId', obj.id)
      if (existing !== obj.mesh) {
        scene.remove(existing)
        obj.mesh.userData.storeId = obj.id
        scene.add(obj.mesh)
      }
    }
  })
}

function animate() {
  requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

function handleResize() {
  if (!containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function handleClick(event) {
  if (mode.value !== 'select') return
  
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  
  raycaster.setFromCamera(mouse, camera)
  
  // Get all meshes from store objects
  const meshes = store.objects.map(o => o.mesh)
  const intersects = raycaster.intersectObjects(meshes, false)
  
  if (intersects.length > 0) {
    const selectedMesh = intersects[0].object
    const obj = store.objects.find(o => o.id === selectedMesh.userData.storeId)
    if (obj) {
      store.selectObject(obj.id)
      highlightObject(selectedMesh, true)
    }
  } else {
    store.selectObject(null)
    // Clear previous selection highlight
    store.objects.forEach(o => {
      if (o.mesh.material && !Array.isArray(o.mesh.material)) {
        if (o.mesh.material.emissive) {
          o.mesh.material.emissive.setHex(0x000000)
        }
      }
    })
  }
}

function highlightObject(mesh, selected) {
  if (mesh.material && !Array.isArray(mesh.material)) {
    if (selected) {
      mesh.material.emissive = mesh.material.emissive || new THREE.Color(0x444444)
      mesh.material.emissive.setHex(0x444444)
    } else if (mesh.material.emissive) {
      mesh.material.emissive.setHex(0x000000)
    }
  }
}

function handlePointerDown(event) {
  if (createTool.value && event.button === 0) {
    createObjectAtCursor(event)
  }
}

function createObjectAtCursor(event) {
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  
  raycaster.setFromCamera(mouse, camera)
  
  // Calculate intersection with ground plane (y=0)
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
  const intersection = new THREE.Vector3()
  raycaster.ray.intersectPlane(plane, intersection)
  
  if (intersection) {
    let geometry, material, mesh
    const tool = createTool.value
    
    material = new THREE.MeshStandardMaterial({
      color: 0x4488ff,
      roughness: 0.5,
      metalness: 0.3
    })
    
    switch (tool) {
      case 'box':
        geometry = new THREE.BoxGeometry(1, 1, 1)
        break
      case 'sphere':
        geometry = new THREE.SphereGeometry(0.5, 32, 32)
        break
      case 'cylinder':
        geometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 32)
        break
      default:
        return
    }
    
    mesh = new THREE.Mesh(geometry, material)
    mesh.position.copy(intersection)
    mesh.castShadow = true
    mesh.receiveShadow = true
    
    // Snap to grid
    mesh.position.x = Math.round(mesh.position.x * 2) / 2
    mesh.position.z = Math.round(mesh.position.z * 2) / 2
    
    store.addObject(mesh, null, tool)
    syncStoreToScene()
    
    // Clear create tool after creation
    store.setCreateTool(null)
  }
}

// Actions
function setMode(m) {
  store.setMode(m)
}

function setCreateTool(tool) {
  store.setCreateTool(tool)
}

function undo() {
  store.undo()
}

function redo() {
  store.redo()
}

function clearScene() {
  store.clearScene()
  syncStoreToScene()
}

// Watch for store changes
watch(() => store.objects, () => {
  syncStoreToScene()
}, { deep: true })

watch(() => store.selectedObjectId, (newId) => {
  // Update selection highlight
  store.objects.forEach(obj => {
    const isSelected = obj.id === newId
    highlightObject(obj.mesh, isSelected)
  })
})

// Lifecycle
onMounted(() => {
  init()
  window.addEventListener('resize', handleResize)
  canvasRef.value?.addEventListener('click', handleClick)
  canvasRef.value?.addEventListener('pointerdown', handlePointerDown)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  canvasRef.value?.removeEventListener('click', handleClick)
  canvasRef.value?.removeEventListener('pointerdown', handlePointerDown)
  
  // Dispose Three.js resources
  if (renderer) {
    renderer.dispose()
  }
  store.clearScene()
})
</script>

<style scoped>
.viewport-3d {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1a1a2e;
  overflow: hidden;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.viewport-controls {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
}

.viewport-toolbar {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.6);
  padding: 10px;
  border-radius: 8px;
}

.viewport-info {
  position: absolute;
  bottom: 20px;
  right: 20px;
  color: #aaa;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.6);
  padding: 5px 10px;
  border-radius: 4px;
}
</style>