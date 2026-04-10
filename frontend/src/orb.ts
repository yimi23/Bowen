/**
 * orb.ts — BOWEN 3D particle orb using Three.js.
 *
 * 2000 particles orbiting in a sphere, color-shifting between BOWEN's
 * Summit palette. State-driven animation via setOrbState().
 *
 * States:
 *  idle     — slow rotation, soft breathing scale
 *  listening — inward pulse, particles tighten toward center
 *  thinking  — fast spiral swirl
 *  speaking  — wave ripple propagating outward
 *  working   — rapid rotation + color flash to tan
 */

import * as THREE from 'three'
import type { OrbState } from './types'

const PARTICLE_COUNT = 2000
const SPHERE_RADIUS = 1.8

// BOWEN Summit palette
const COLORS = {
  base: new THREE.Color('#c8b89a'),      // tan
  cream: new THREE.Color('#f5f2ee'),     // cream
  deep: new THREE.Color('#8a7a6a'),      // deep tan
  active: new THREE.Color('#e8d4b8'),    // bright tan
  working: new THREE.Color('#d4a574'),   // warm amber
}

function spherePoint(radius: number): THREE.Vector3 {
  const u = Math.random()
  const v = Math.random()
  const theta = 2 * Math.PI * u
  const phi = Math.acos(2 * v - 1)
  return new THREE.Vector3(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.sin(phi) * Math.sin(theta),
    radius * Math.cos(phi),
  )
}

export class Orb {
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private renderer: THREE.WebGLRenderer
  private particles!: THREE.Points
  private geometry!: THREE.BufferGeometry
  private positions!: Float32Array
  private origins!: Float32Array
  private colors!: Float32Array
  private phases!: Float32Array

  private state: OrbState = 'idle'
  private clock = new THREE.Clock()
  private animFrame = 0

  constructor(canvas: HTMLCanvasElement) {
    this.scene = new THREE.Scene()

    this.camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100)
    this.camera.position.z = 5

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.setClearColor(0x000000, 0)

    this._buildParticles()
    this._startRender()
  }

  setOrbState(state: OrbState): void {
    this.state = state
  }

  resize(width: number, height: number): void {
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(width, height)
  }

  destroy(): void {
    cancelAnimationFrame(this.animFrame)
    this.renderer.dispose()
  }

  private _buildParticles(): void {
    this.geometry = new THREE.BufferGeometry()
    this.positions = new Float32Array(PARTICLE_COUNT * 3)
    this.origins = new Float32Array(PARTICLE_COUNT * 3)
    this.colors = new Float32Array(PARTICLE_COUNT * 3)
    this.phases = new Float32Array(PARTICLE_COUNT)

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const p = spherePoint(SPHERE_RADIUS)
      this.origins[i * 3] = p.x
      this.origins[i * 3 + 1] = p.y
      this.origins[i * 3 + 2] = p.z
      this.positions[i * 3] = p.x
      this.positions[i * 3 + 1] = p.y
      this.positions[i * 3 + 2] = p.z
      this.phases[i] = Math.random() * Math.PI * 2

      // Mix base and cream colors per particle
      const t = Math.random()
      const c = COLORS.base.clone().lerp(COLORS.cream, t * 0.4)
      this.colors[i * 3] = c.r
      this.colors[i * 3 + 1] = c.g
      this.colors[i * 3 + 2] = c.b
    }

    this.geometry.setAttribute('position', new THREE.BufferAttribute(this.positions, 3))
    this.geometry.setAttribute('color', new THREE.BufferAttribute(this.colors, 3))

    const material = new THREE.PointsMaterial({
      size: 0.018,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      sizeAttenuation: true,
      depthWrite: false,
    })

    this.particles = new THREE.Points(this.geometry, material)
    this.scene.add(this.particles)
  }

  private _startRender(): void {
    const tick = () => {
      this.animFrame = requestAnimationFrame(tick)
      const t = this.clock.getElapsedTime()
      this._animate(t)
      this.renderer.render(this.scene, this.camera)
    }
    tick()
  }

  private _animate(t: number): void {
    const pos = this.positions
    const orig = this.origins
    const col = this.colors
    const ph = this.phases
    const mat = this.particles.material as THREE.PointsMaterial

    switch (this.state) {
      case 'idle': {
        // Slow rotation + subtle breathing
        this.particles.rotation.y = t * 0.08
        this.particles.rotation.x = Math.sin(t * 0.04) * 0.1
        const breathe = 1 + Math.sin(t * 0.6) * 0.025
        this.particles.scale.setScalar(breathe)
        mat.opacity = 0.8 + Math.sin(t * 0.5) * 0.05

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          pos[i * 3] = orig[i * 3]
          pos[i * 3 + 1] = orig[i * 3 + 1]
          pos[i * 3 + 2] = orig[i * 3 + 2]
          const c = COLORS.base.clone().lerp(COLORS.cream, Math.sin(ph[i] + t * 0.3) * 0.5 + 0.5)
          col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
        }
        break
      }

      case 'listening': {
        // Particles drift slightly inward, soft pulse
        this.particles.rotation.y = t * 0.12
        this.particles.scale.setScalar(1)
        const pulse = 0.85 + Math.sin(t * 2.5) * 0.1

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          pos[i * 3] = orig[i * 3] * pulse
          pos[i * 3 + 1] = orig[i * 3 + 1] * pulse
          pos[i * 3 + 2] = orig[i * 3 + 2] * pulse
          const bright = 0.7 + Math.abs(Math.sin(ph[i] + t * 1.5)) * 0.3
          const c = COLORS.active.clone().multiplyScalar(bright)
          col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
        }
        mat.opacity = 0.9
        break
      }

      case 'thinking': {
        // Fast spiral swirl
        this.particles.rotation.y = t * 0.5
        this.particles.rotation.z = t * 0.2
        this.particles.scale.setScalar(1)

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          const ox = orig[i * 3], oy = orig[i * 3 + 1], oz = orig[i * 3 + 2]
          const angle = ph[i] + t * 1.2
          const r = Math.sqrt(ox * ox + oy * oy)
          pos[i * 3] = ox + Math.cos(angle) * r * 0.08
          pos[i * 3 + 1] = oy + Math.sin(angle) * 0.06
          pos[i * 3 + 2] = oz + Math.sin(angle) * r * 0.06
          const c = COLORS.deep.clone().lerp(COLORS.cream, Math.sin(ph[i] + t) * 0.5 + 0.5)
          col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
        }
        mat.opacity = 0.85
        break
      }

      case 'speaking': {
        // Radial wave ripple
        this.particles.rotation.y = t * 0.1
        this.particles.scale.setScalar(1)

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          const d = Math.sqrt(orig[i*3]**2 + orig[i*3+1]**2 + orig[i*3+2]**2)
          const wave = Math.sin(d * 3 - t * 4 + ph[i]) * 0.12
          const norm = d > 0 ? 1 / d : 1
          pos[i * 3] = orig[i * 3] + orig[i * 3] * norm * wave
          pos[i * 3 + 1] = orig[i * 3 + 1] + orig[i * 3 + 1] * norm * wave
          pos[i * 3 + 2] = orig[i * 3 + 2] + orig[i * 3 + 2] * norm * wave
          const bright = 0.8 + wave * 2
          const c = COLORS.active.clone().multiplyScalar(Math.max(0.4, Math.min(1.2, bright)))
          col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
        }
        mat.opacity = 0.9
        break
      }

      case 'working': {
        // Rapid rotation + amber flash
        this.particles.rotation.y = t * 1.0
        this.particles.rotation.x = t * 0.3
        const flash = 1 + Math.sin(t * 8) * 0.04
        this.particles.scale.setScalar(flash)

        for (let i = 0; i < PARTICLE_COUNT; i++) {
          pos[i * 3] = orig[i * 3]
          pos[i * 3 + 1] = orig[i * 3 + 1]
          pos[i * 3 + 2] = orig[i * 3 + 2]
          const tval = Math.sin(ph[i] + t * 3) * 0.5 + 0.5
          const c = COLORS.working.clone().lerp(COLORS.cream, tval * 0.5)
          col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b
        }
        mat.opacity = 0.95
        break
      }
    }

    this.geometry.attributes['position'].needsUpdate = true
    this.geometry.attributes['color'].needsUpdate = true
  }
}
