'use client';

import React, { Suspense, useRef, useMemo, useEffect, useState, Component, type ReactNode, type ErrorInfo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
// EffectComposer removed — crashes on some WebGL contexts (null alpha read).
// Vignette is handled by CSS (.globe-vignette). Bloom not needed at current opacity.
import Arc from './Arc';
import {
  generateArcs,
  latLonToVec3,
  type ArcData,
} from './globePoints';

// ── WebGL & Hydration Error Protection ───────────────────────────────

function isWebGLAvailable(): boolean {
  if (typeof window === 'undefined') return false;
  
  // Allow manual override for simulation / testing
  if (
    (window as any).FORCE_NO_WEBGL || 
    (typeof localStorage !== 'undefined' && localStorage.getItem('force_no_webgl') === 'true')
  ) {
    return false;
  }

  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch (e) {
    return false;
  }
}

interface ErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class GlobeErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false
  };

  public static getDerivedStateFromError(_error: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error inside GlobeErrorBoundary:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}

// Premium desaturated 2D fallback component
function GlobeFallback() {
  return (
    <div className="globe-container">
      <div style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Faint cyan ambient glow */}
        <div style={{
          position: 'absolute',
          bottom: '-10%',
          right: '-10%',
          width: '80%',
          height: '80%',
          background: 'radial-gradient(circle at 60% 60%, rgba(0, 230, 118, 0.07) 0%, rgba(0, 180, 80, 0.02) 50%, transparent 80%)',
          borderRadius: '50%',
          filter: 'blur(40px)',
        }} />
        {/* Concentric rings — cyan tint */}
        <div style={{
          position: 'absolute',
          bottom: '10%',
          right: '10%',
          width: '500px',
          height: '500px',
          border: '1px solid rgba(45, 226, 230, 0.04)',
          borderRadius: '50%',
          transform: 'translate(30%, 30%)',
        }} />
        <div style={{
          position: 'absolute',
          bottom: '10%',
          right: '10%',
          width: '300px',
          height: '300px',
          border: '1px dashed rgba(45, 226, 230, 0.03)',
          borderRadius: '50%',
          transform: 'translate(30%, 30%) rotate(45deg)',
        }} />
      </div>
    </div>
  );
}


// ── Land dots — simplified procedural approach ──────────────────────

function generateLandDots(count: number = 1200, radius: number = 1): Float32Array {
  const continents = [
    { latMin: 15, latMax: 70, lonMin: -170, lonMax: -50, density: 0.2 },
    { latMin: -55, latMax: 12, lonMin: -82, lonMax: -35, density: 0.15 },
    { latMin: 35, latMax: 71, lonMin: -10, lonMax: 40, density: 0.25 },
    { latMin: -35, latMax: 37, lonMin: -18, lonMax: 52, density: 0.2 },
    { latMin: 5, latMax: 75, lonMin: 25, lonMax: 150, density: 0.25 },
    { latMin: -47, latMax: -10, lonMin: 110, lonMax: 180, density: 0.1 },
  ];

  const positions: number[] = [];
  const totalWeight = continents.reduce((s, c) => s + c.density, 0);

  for (const continent of continents) {
    const share = Math.floor(count * (continent.density / totalWeight));
    for (let i = 0; i < share; i++) {
      const lat = continent.latMin + Math.random() * (continent.latMax - continent.latMin);
      const lon = continent.lonMin + Math.random() * (continent.lonMax - continent.lonMin);
      const v = latLonToVec3(lat, lon, radius * 1.001);
      positions.push(v.x, v.y, v.z);
    }
  }

  return new Float32Array(positions);
}

// ── Globe Scene ─────────────────────────────────────────────────────

function GlobeScene() {
  const groupRef = useRef<THREE.Group>(null);

  // Mouse position for parallax
  const mouse = useRef({ x: 0, y: 0 });

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      mouse.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouse.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    }
    window.addEventListener('mousemove', onMouseMove);
    return () => window.removeEventListener('mousemove', onMouseMove);
  }, []);

  // Generate data once
  const landDotPositions = useMemo(() => generateLandDots(1200, 1), []);
  const arcs = useMemo(() => generateArcs(10), []);

  // Wireframe — built imperatively from edges of a SphereGeometry to be barely visible
  const wireframeObj = useMemo(() => {
    const geo = new THREE.SphereGeometry(1, 24, 16);
    const edges = new THREE.EdgesGeometry(geo);
    const mat = new THREE.LineBasicMaterial({
      color: '#0A4E43',     /* Deep Teal wireframe */
      transparent: true,
      opacity: 0.65,
    });
    return new THREE.LineSegments(edges, mat);
  }, []);

  // Land dots — use InstancedMesh for performance
  const landDotCount = landDotPositions.length / 3;
  const landDotMeshRef = useRef<THREE.InstancedMesh>(null);

  useEffect(() => {
    if (!landDotMeshRef.current) return;
    const dummy = new THREE.Object3D();
    for (let i = 0; i < landDotCount; i++) {
      dummy.position.set(
        landDotPositions[i * 3],
        landDotPositions[i * 3 + 1],
        landDotPositions[i * 3 + 2],
      );
      dummy.scale.setScalar(1);
      dummy.updateMatrix();
      landDotMeshRef.current.setMatrixAt(i, dummy.matrix);
    }
    landDotMeshRef.current.instanceMatrix.needsUpdate = true;
  }, [landDotPositions, landDotCount]);

  // Slow orbit + mouse parallax
  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const t = clock.getElapsedTime();

    // Base rotation — slow orbit
    groupRef.current.rotation.y = t * 0.04;

    // Mouse parallax (clamped ±0.05 rad)
    const targetX = THREE.MathUtils.clamp(mouse.current.y * 0.05, -0.05, 0.05);
    const targetZ = THREE.MathUtils.clamp(mouse.current.x * 0.05, -0.05, 0.05);
    groupRef.current.rotation.x += (targetX - groupRef.current.rotation.x) * 0.02;
    groupRef.current.rotation.z += (targetZ - groupRef.current.rotation.z) * 0.02;
  });

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight
        position={[5, 3, 5]}
        intensity={0.5}
        color="#04D793"
      />

      {/* Globe sits deep in the bottom-right — scaled back, not dominating */}
      <group ref={groupRef} position={[1.4, -0.8, -0.6]} scale={[0.85, 0.85, 0.85]}>
        {/* Wireframe globe */}
        <primitive object={wireframeObj} />

        {/* Continental land dots */}
        <instancedMesh
          ref={landDotMeshRef}
          args={[undefined, undefined, landDotCount]}
        >
          <sphereGeometry args={[0.011, 6, 6]} />
          <meshBasicMaterial color="#067D5D" transparent opacity={0.55} />
        </instancedMesh>

        {/* Network arcs */}
        {arcs.map((arc: ArcData, i: number) => (
          <Arc key={i} arc={arc} radius={1} />
        ))}
      </group>

      {/* Post-processing removed — vignette handled by .globe-vignette CSS overlay */}
    </>
  );
}

// ── Main Export ──────────────────────────────────────────────────────

export default function NetworkGlobe() {
  const [visible, setVisible] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [webGlSupported, setWebGlSupported] = useState<boolean>(() => isWebGLAvailable());

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', handler);

    function onVisibility() {
      setVisible(document.visibilityState === 'visible');
    }
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      mq.removeEventListener('change', handler);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  if (reducedMotion) {
    return (
      <div className="globe-container" style={{ opacity: 0.18 }}>
        <div style={{
          width: '100%',
          height: '100%',
          background: 'radial-gradient(ellipse at 72% 72%, rgba(0, 230, 118, 0.08) 0%, rgba(0, 150, 60, 0.04) 50%, transparent 75%)',
        }} />
      </div>
    );
  }

  if (!webGlSupported) {
    return <GlobeFallback />;
  }

  return (
    <GlobeErrorBoundary fallback={<GlobeFallback />}>
      <div className="globe-container">
        <Canvas
          dpr={[1, 1.5]}
          camera={{
            position: [1.6, -0.9, 3.0], // shifts globe up-left from viewer's POV
            fov: 32, // tighter framing
            near: 0.1,
            far: 100,
          }}
          frameloop={visible ? 'always' : 'never'}
          style={{ background: 'transparent' }}
          gl={{ alpha: true, antialias: true, powerPreference: 'default' }}
        >
          <Suspense fallback={null}>
            <GlobeScene />
          </Suspense>
        </Canvas>
      </div>
    </GlobeErrorBoundary>
  );
}
