'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export type AgentState = null | 'thinking' | 'listening' | 'speaking';

const PARAMS: Record<string, { speed: number; amp: number; freq: number }> = {
  null:      { speed: 0.25, amp: 0.10, freq: 1.0 },
  thinking:  { speed: 1.1,  amp: 0.28, freq: 2.2 },
  listening: { speed: 0.55, amp: 0.20, freq: 1.6 },
  speaking:  { speed: 1.9,  amp: 0.44, freq: 3.0 },
};

function noise3(x: number, y: number, z: number, t: number): number {
  return (
    Math.sin(x * 2.1 + t) * 0.28 +
    Math.sin(y * 3.7 + t * 0.7) * 0.28 +
    Math.sin(z * 2.9 + t * 0.5) * 0.24 +
    Math.sin((x + y) * 1.5 + t * 0.9) * 0.20
  );
}

function BlobMesh({ agentState, colors }: { agentState: AgentState; colors: [string, string] }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const clockRef = useRef(0);
  const curP = useRef({ ...PARAMS['null'] });

  const geometry = useMemo(() => new THREE.IcosahedronGeometry(1, 4), []);

  const origPos = useMemo(
    () => Float32Array.from(geometry.attributes.position.array as ArrayLike<number>),
    [geometry],
  );

  const material = useMemo(() => {
    const c1 = new THREE.Color(colors[0]);
    const c2 = new THREE.Color(colors[1]);
    return new THREE.MeshPhongMaterial({
      color: c1.clone().lerp(c2, 0.4),
      emissive: c1,
      emissiveIntensity: 0.4,
      shininess: 50,
      transparent: true,
      opacity: 0.92,
    });
  }, [colors]);

  const target = PARAMS[agentState === null ? 'null' : agentState];

  useFrame((_, dt) => {
    if (!meshRef.current) return;
    const cp = curP.current;
    const lp = Math.min(1, dt * 2.5);
    cp.speed += (target.speed - cp.speed) * lp;
    cp.amp   += (target.amp   - cp.amp)   * lp;
    cp.freq  += (target.freq  - cp.freq)  * lp;

    clockRef.current += dt * cp.speed;
    const t = clockRef.current;
    const posAttr = geometry.attributes.position as THREE.BufferAttribute;
    const pos = posAttr.array as Float32Array;

    for (let i = 0; i < origPos.length / 3; i++) {
      const ox = origPos[i * 3], oy = origPos[i * 3 + 1], oz = origPos[i * 3 + 2];
      const n = noise3(ox * cp.freq, oy * cp.freq, oz * cp.freq, t);
      const s = 1 + n * cp.amp;
      pos[i * 3] = ox * s; pos[i * 3 + 1] = oy * s; pos[i * 3 + 2] = oz * s;
    }

    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();
    meshRef.current.rotation.y += dt * 0.09 * cp.speed;
  });

  return <mesh ref={meshRef} geometry={geometry} material={material} />;
}

export interface OrbProps {
  agentState?: AgentState;
  colors?: [string, string];
}

export function Orb({ agentState = null, colors = ['#3d5c1a', '#fcffe1'] }: OrbProps) {
  return (
    <Canvas
      camera={{ position: [0, 0, 2.8], fov: 45 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: 'transparent' }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={1.2} />
      <pointLight position={[-4, -3, -4]} intensity={0.5} color={colors[1]} />
      <BlobMesh agentState={agentState} colors={colors} />
    </Canvas>
  );
}
