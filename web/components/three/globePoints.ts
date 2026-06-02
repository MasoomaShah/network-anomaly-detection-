/**
 * globePoints.ts — Utilities for the 3D wireframe globe
 *
 * - Lat/lon → 3D sphere coordinates
 * - City data for arc endpoints
 * - Land point generation from TopoJSON
 */

import * as THREE from 'three';

// ── Coordinate conversion ───────────────────────────────────────────

/**
 * Convert lat/lon (degrees) to a 3D point on a sphere of given radius.
 */
export function latLonToVec3(lat: number, lon: number, radius: number = 1): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

// ── Data center cities for arc endpoints ────────────────────────────

export interface CityNode {
  name: string;
  lat: number;
  lon: number;
}

export const CITIES: CityNode[] = [
  { name: 'New York',    lat: 40.71,  lon: -74.01  },
  { name: 'London',      lat: 51.51,  lon: -0.13   },
  { name: 'Tokyo',       lat: 35.68,  lon: 139.69  },
  { name: 'Singapore',   lat: 1.35,   lon: 103.82  },
  { name: 'Frankfurt',   lat: 50.11,  lon: 8.68    },
  { name: 'São Paulo',   lat: -23.55, lon: -46.63  },
  { name: 'Sydney',      lat: -33.87, lon: 151.21  },
  { name: 'Cape Town',   lat: -33.92, lon: 18.42   },
  { name: 'Mumbai',      lat: 19.08,  lon: 72.88   },
  { name: 'Dubai',       lat: 25.20,  lon: 55.27   },
  { name: 'Toronto',     lat: 43.65,  lon: -79.38  },
  { name: 'Seoul',       lat: 37.57,  lon: 126.98  },
  { name: 'Amsterdam',   lat: 52.37,  lon: 4.90    },
  { name: 'Hong Kong',   lat: 22.32,  lon: 114.17  },
  { name: 'Los Angeles', lat: 34.05,  lon: -118.24 },
  { name: 'Chicago',     lat: 41.88,  lon: -87.63  },
  { name: 'Johannesburg',lat: -26.20, lon: 28.05   },
  { name: 'Moscow',      lat: 55.76,  lon: 37.62   },
  { name: 'Jakarta',     lat: -6.21,  lon: 106.85  },
  { name: 'Buenos Aires',lat: -34.60, lon: -58.38  },
];

// ── Generate random arc pairs from city list ────────────────────────

export interface ArcData {
  from: CityNode;
  to: CityNode;
  offset: number; // stagger offset in seconds
  duration: number; // travel time in seconds
}

/**
 * Generate N random arcs between distinct city pairs.
 */
export function generateArcs(count: number = 10): ArcData[] {
  const arcs: ArcData[] = [];
  const used = new Set<string>();

  for (let i = 0; i < count && arcs.length < count; i++) {
    const fromIdx = Math.floor(Math.random() * CITIES.length);
    let toIdx = Math.floor(Math.random() * CITIES.length);
    while (toIdx === fromIdx) {
      toIdx = Math.floor(Math.random() * CITIES.length);
    }

    const key = `${Math.min(fromIdx, toIdx)}-${Math.max(fromIdx, toIdx)}`;
    if (used.has(key)) continue;
    used.add(key);

    arcs.push({
      from: CITIES[fromIdx],
      to: CITIES[toIdx],
      offset: Math.random() * 6,
      duration: 4 + Math.random() * 4, // 4–8 seconds
    });
  }

  return arcs;
}

// ── Great-circle arc curve ──────────────────────────────────────────

/**
 * Create a quadratic Bezier curve for a great-circle arc on the globe.
 * The control point is lifted above the globe surface to create the arc effect.
 */
export function createArcCurve(
  from: CityNode,
  to: CityNode,
  radius: number = 1,
  arcHeight: number = 0.25,
): THREE.QuadraticBezierCurve3 {
  const start = latLonToVec3(from.lat, from.lon, radius);
  const end = latLonToVec3(to.lat, to.lon, radius);

  // Midpoint raised above the surface
  const mid = new THREE.Vector3()
    .addVectors(start, end)
    .multiplyScalar(0.5);

  // Normalize midpoint outward and scale by radius + height
  const dist = start.distanceTo(end);
  const liftAmount = radius + arcHeight + dist * 0.15;
  mid.normalize().multiplyScalar(liftAmount);

  return new THREE.QuadraticBezierCurve3(start, mid, end);
}

// ── Wireframe sphere geometry ───────────────────────────────────────

/**
 * Generate line segments for a wireframe sphere (lat/lon grid).
 */
export function createWireframePoints(
  radius: number = 1,
  latLines: number = 14,
  lonLines: number = 24,
  pointsPerLine: number = 64,
): Float32Array {
  const points: number[] = [];

  // Latitude circles
  for (let i = 1; i < latLines; i++) {
    const lat = -90 + (180 * i) / latLines;
    for (let j = 0; j <= pointsPerLine; j++) {
      const lon = -180 + (360 * j) / pointsPerLine;
      const v = latLonToVec3(lat, lon, radius);
      points.push(v.x, v.y, v.z);
    }
  }

  // Longitude circles
  for (let i = 0; i < lonLines; i++) {
    const lon = -180 + (360 * i) / lonLines;
    for (let j = 0; j <= pointsPerLine; j++) {
      const lat = -90 + (180 * j) / pointsPerLine;
      const v = latLonToVec3(lat, lon, radius);
      points.push(v.x, v.y, v.z);
    }
  }

  return new Float32Array(points);
}
