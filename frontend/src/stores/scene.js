/**
 * 3D Scene Store - Manages the 3D modeling scene state
 */
import { defineStore } from 'pinia'
import * as THREE from 'three'

export const useSceneStore = defineStore('scene', {
  state: () => ({
    // Scene objects
    objects: [], // { id, name, type, mesh, visible, locked }
    
    // Selection state
    selectedObjectId: null,
    
    // Editor mode
    mode: 'select', // 'select' | 'move' | 'rotate' | 'scale'
    
    // Create tool
    createTool: null, // 'box' | 'sphere' | 'cylinder'
    
    // History for undo/redo
    history: [],
    historyIndex: -1
  }),
  
  getters: {
    selectedObject: (state) => {
      return state.objects.find(obj => obj.id === state.selectedObjectId)
    },
    
    sceneTree: (state) => {
      return state.objects.map(obj => ({
        id: obj.id,
        name: obj.name,
        type: obj.type,
        visible: obj.visible,
        locked: obj.locked,
        hasChildren: false
      }))
    }
  },
  
  actions: {
    addObject(mesh, name, type) {
      const id = `obj_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      const obj = {
        id,
        name: name || `${type}_${this.objects.length + 1}`,
        type,
        mesh,
        visible: true,
        locked: false
      }
      this.objects.push(obj)
      this.selectedObjectId = id
      this.saveHistory()
      return id
    },
    
    removeObject(id) {
      const index = this.objects.findIndex(obj => obj.id === id)
      if (index !== -1) {
        const obj = this.objects[index]
        // Dispose geometry and material
        if (obj.mesh.geometry) obj.mesh.geometry.dispose()
        if (obj.mesh.material) {
          if (Array.isArray(obj.mesh.material)) {
            obj.mesh.material.forEach(m => m.dispose())
          } else {
            obj.mesh.material.dispose()
          }
        }
        this.objects.splice(index, 1)
        if (this.selectedObjectId === id) {
          this.selectedObjectId = null
        }
        this.saveHistory()
      }
    },
    
    selectObject(id) {
      this.selectedObjectId = id
    },
    
    updateObjectProperty(id, property, value) {
      const obj = this.objects.find(o => o.id === id)
      if (obj) {
        if (property in obj.mesh) {
          obj.mesh[property] = value
        }
        this.saveHistory()
      }
    },
    
    updateObjectPosition(id, position) {
      const obj = this.objects.find(o => o.id === id)
      if (obj) {
        obj.mesh.position.set(position.x, position.y, position.z)
        this.saveHistory()
      }
    },
    
    updateObjectRotation(id, rotation) {
      const obj = this.objects.find(o => o.id === id)
      if (obj) {
        obj.mesh.rotation.set(rotation.x, rotation.y, rotation.z)
        this.saveHistory()
      }
    },
    
    updateObjectScale(id, scale) {
      const obj = this.objects.find(o => o.id === id)
      if (obj) {
        obj.mesh.scale.set(scale.x, scale.y, scale.z)
        this.saveHistory()
      }
    },
    
    setObjectVisibility(id, visible) {
      const obj = this.objects.find(o => o.id === id)
      if (obj) {
        obj.visible = visible
        obj.mesh.visible = visible
      }
    },
    
    setMode(mode) {
      this.mode = mode
    },
    
    setCreateTool(tool) {
      this.createTool = tool
    },
    
    clearScene() {
      this.objects.forEach(obj => {
        if (obj.mesh.geometry) obj.mesh.geometry.dispose()
        if (obj.mesh.material) {
          if (Array.isArray(obj.mesh.material)) {
            obj.mesh.material.forEach(m => m.dispose())
          } else {
            obj.mesh.material.dispose()
          }
        }
      })
      this.objects = []
      this.selectedObjectId = null
      this.saveHistory()
    },
    
    saveHistory() {
      // Simple history - just mark the point
      this.historyIndex++
      if (this.historyIndex < this.history.length) {
        this.history = this.history.slice(0, this.historyIndex)
      }
      this.history.push({ timestamp: Date.now() })
      if (this.history.length > 50) {
        this.history.shift()
        this.historyIndex--
      }
    },
    
    undo() {
      if (this.historyIndex > 0) {
        this.historyIndex--
        // In a full implementation, would restore object states
      }
    },
    
    redo() {
      if (this.historyIndex < this.history.length - 1) {
        this.historyIndex++
      }
    }
  }
})