'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { createArcCurve, type ArcData } from './globePoints';
import { latLonToVec3 } from './globePoints';

const ARC_COLOR   = new THREE.Color('#04D793'); // Caribbean Green arc lines
const DOT_COLOR   = new THREE.Color('#FFFFFF'); // white traveling dot
const PULSE_COLOR = new THREE.Color('#04D793'); // Caribbean Green pulse
const ARC_SEGMENTS = 64;

interface ArcProps {
  arc: ArcData;
  radius?: number;
}

export default function Arc({ arc, radius = 1 }: ArcProps) {
  const dotRef = useRef<THREE.Mesh>(null);
  const pulseFromRef = useRef<THREE.Mesh>(null);
  const pulseToRef = useRef<THREE.Mesh>(null);

  const curve = useMemo(
    () => createArcCurve(arc.from, arc.to, radius),
    [arc.from, arc.to, radius]
  );

  // Build a THREE.Line object imperatively with 0.28 opacity
  const lineObj = useMemo(() => {
    const points = curve.getPoints(ARC_SEGMENTS);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: ARC_COLOR,
      transparent: true,
      opacity: 0.45,
    });
    return new THREE.Line(geometry, material);
  }, [curve]);

  const fromPos = useMemo(() => latLonToVec3(arc.from.lat, arc.from.lon, radius), [arc.from, radius]);
  const toPos = useMemo(() => latLonToVec3(arc.to.lat, arc.to.lon, radius), [arc.to, radius]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();

    // Traveling dot
    if (dotRef.current) {
      const progress = ((t + arc.offset) % arc.duration) / arc.duration;
      const point = curve.getPoint(progress);
      dotRef.current.position.copy(point);
    }

    // Endpoint pulses animation range: 0.15 -> 0.45
    const pulsePhase = (Math.sin(t * Math.PI) + 1) / 2; // 0 to 1
    const targetOpacity = 0.15 + pulsePhase * 0.3;
    if (pulseFromRef.current) {
      (pulseFromRef.current.material as THREE.MeshBasicMaterial).opacity = targetOpacity;
    }
    if (pulseToRef.current) {
      (pulseToRef.current.material as THREE.MeshBasicMaterial).opacity = targetOpacity;
    }
  });

  return (
    <group>
      {/* Arc line — use primitive to avoid JSX <line> / SVG conflict */}
      <primitive object={lineObj} />

      {/* Traveling dot — mint, visible */}
      <mesh ref={dotRef}>
        <sphereGeometry args={[0.012, 8, 8]} />
        <meshBasicMaterial
          color={DOT_COLOR}
          transparent
          opacity={0.75}
        />
      </mesh>

      {/* Endpoint pulse — from (opacity controlled dynamically in useFrame) */}
      <mesh ref={pulseFromRef} position={fromPos}>
        <sphereGeometry args={[0.015, 8, 8]} />
        <meshBasicMaterial
          color={PULSE_COLOR}
          transparent
          opacity={0.15}
        />
      </mesh>

      {/* Endpoint pulse — to */}
      <mesh ref={pulseToRef} position={toPos}>
        <sphereGeometry args={[0.015, 8, 8]} />
        <meshBasicMaterial
          color={PULSE_COLOR}
          transparent
          opacity={0.15}
        />
      </mesh>
    </group>
  );
}
