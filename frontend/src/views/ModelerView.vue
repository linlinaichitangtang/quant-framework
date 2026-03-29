<template>
  <div class="modeler-view">
    <div class="modeler-container">
      <!-- Left Panel: Scene Tree -->
      <div class="panel scene-tree">
        <SceneTreePanel />
      </div>
      
      <!-- Center: 3D Viewport -->
      <div class="viewport-container">
        <Viewport3D />
      </div>
      
      <!-- Right Panel: Properties -->
      <div class="panel property-panel">
        <PropertyPanel />
      </div>
    </div>
  </div>
</template>

<script setup>
import SceneTreePanel from '@/components/SceneTreePanel.vue'
import PropertyPanel from '@/components/PropertyPanel.vue'
import Viewport3D from '@/components/Viewport3D.vue'
</script>

<style scoped>
.modeler-view {
  height: calc(100vh - 60px);
  padding: 15px;
  background: #1a1a2e;
}

.modeler-container {
  display: flex;
  height: 100%;
  gap: 10px;
}

.panel {
  background: #2d2d2d;
  border-radius: 8px;
  overflow: hidden;
}

.scene-tree {
  width: 220px;
  min-width: 180px;
}

.property-panel {
  width: 280px;
  min-width: 240px;
}

.viewport-container {
  flex: 1;
  border-radius: 8px;
  overflow: hidden;
  min-width: 400px;
}
</style>