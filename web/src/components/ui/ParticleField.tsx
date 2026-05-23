'use client'

import { useEffect, useRef } from 'react'

/**
 * Antigravity-style animated dot cluster.
 * Renders ~400 small purple/blue particles arranged in a sphere
 * pattern that gently drift / twinkle. Pure canvas. Zero deps.
 *
 * Position: absolute fill of parent (parent must be position: relative).
 */
type Props = {
  /** how dense the field is. default 380 */
  count?: number
  /** main accent (defaults to violet) */
  color?: string
  /** secondary accent for variety */
  altColor?: string
  /** push the cluster off-center to the right (0-1). default 0.7 */
  centerX?: number
  /** vertical center (0-1). default 0.5 */
  centerY?: number
  /** radius as fraction of min(width,height). default 0.55 */
  radius?: number
}

export default function ParticleField({
  count = 380,
  color = '#7C3AED',
  altColor = '#06B6D4',
  centerX = 0.7,
  centerY = 0.5,
  radius = 0.55,
}: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>()

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let w = 0
    let h = 0
    let particles: Particle[] = []

    type Particle = {
      // base spherical coords
      theta: number
      phi: number
      r: number
      // jitter offsets
      ox: number
      oy: number
      // size + color
      size: number
      col: string
      // twinkle phase
      tw: number
      twSpeed: number
      // drift
      dx: number
      dy: number
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      w = rect.width
      h = rect.height
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      seed()
    }

    const seed = () => {
      particles = []
      const baseR = Math.min(w, h) * radius
      for (let i = 0; i < count; i++) {
        // Spherical-ish distribution — biased toward outer shell
        const u = Math.random()
        const v = Math.random()
        const theta = 2 * Math.PI * u
        const phi = Math.acos(2 * v - 1)
        // shell-biased radius (Math.cbrt gives uniform vol; we bias outward)
        const r = baseR * (0.55 + Math.random() * 0.45)
        particles.push({
          theta,
          phi,
          r,
          ox: 0,
          oy: 0,
          size: 0.6 + Math.random() * 1.6,
          col: Math.random() < 0.18 ? altColor : color,
          tw: Math.random() * Math.PI * 2,
          twSpeed: 0.005 + Math.random() * 0.012,
          dx: (Math.random() - 0.5) * 0.06,
          dy: (Math.random() - 0.5) * 0.06,
        })
      }
    }

    let t = 0
    const draw = () => {
      ctx.clearRect(0, 0, w, h)

      const cx = w * centerX
      const cy = h * centerY

      // gentle global rotation
      const rotY = t * 0.0006
      const rotX = Math.sin(t * 0.0004) * 0.2

      for (const p of particles) {
        // 3D point on sphere
        const x0 = p.r * Math.sin(p.phi) * Math.cos(p.theta + rotY)
        const y0 = p.r * Math.cos(p.phi)
        const z0 = p.r * Math.sin(p.phi) * Math.sin(p.theta + rotY)
        // pitch
        const y1 = y0 * Math.cos(rotX) - z0 * Math.sin(rotX)
        const z1 = y0 * Math.sin(rotX) + z0 * Math.cos(rotX)
        // depth-based fade (z1 > 0 = closer)
        const depth = (z1 + p.r) / (2 * p.r) // 0..1
        // gentle drift jitter
        p.ox += p.dx
        p.oy += p.dy
        if (Math.abs(p.ox) > 6) p.dx *= -1
        if (Math.abs(p.oy) > 6) p.dy *= -1

        const px = cx + x0 + p.ox
        const py = cy + y1 + p.oy

        // twinkle
        p.tw += p.twSpeed
        const twinkle = 0.5 + 0.5 * Math.sin(p.tw)

        const alpha = (0.25 + 0.75 * depth) * (0.55 + 0.45 * twinkle)
        ctx.beginPath()
        ctx.arc(px, py, p.size * (0.6 + 0.6 * depth), 0, Math.PI * 2)
        ctx.fillStyle = hexToRgba(p.col, alpha)
        ctx.fill()
      }

      t += 1
      rafRef.current = requestAnimationFrame(draw)
    }

    resize()
    draw()

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    return () => {
      ro.disconnect()
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [count, color, altColor, centerX, centerY, radius])

  return (
    <div className="particle-field">
      <canvas ref={ref} />
    </div>
  )
}

/* helper */
function hexToRgba(hex: string, a: number) {
  const m = hex.replace('#', '')
  const r = parseInt(m.substring(0, 2), 16)
  const g = parseInt(m.substring(2, 4), 16)
  const b = parseInt(m.substring(4, 6), 16)
  return `rgba(${r},${g},${b},${a})`
}
