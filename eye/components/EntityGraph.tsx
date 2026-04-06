"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { EntitySummary } from "@/lib/api";

interface GraphNode extends EntitySummary {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

interface Props {
  entities: EntitySummary[];
  relationships: GraphEdge[];
  width?: number;
  height?: number;
}

const COMMUNITY_COLORS = [
  "#14b8a6", // teal
  "#f97316", // orange
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#eab308", // yellow
  "#22c55e", // green
  "#ef4444", // red
];

function communityColor(id: string | null): string {
  if (!id) return "#64748b";
  const idx = Math.abs(hashCode(id)) % COMMUNITY_COLORS.length;
  return COMMUNITY_COLORS[idx];
}

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return h;
}

function nodeRadius(entity: EntitySummary): number {
  return 6 + (entity.influence_score || 0) * 14;
}

export default function EntityGraph({
  entities,
  relationships,
  width = 800,
  height = 500,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const rafRef = useRef<number>(0);
  const [, forceRender] = useState(0);
  const [hovered, setHovered] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const dragOffset = useRef({ x: 0, y: 0 });

  // Initialize nodes
  useEffect(() => {
    const cx = width / 2;
    const cy = height / 2;
    nodesRef.current = entities.map((e, i) => {
      const angle = (2 * Math.PI * i) / entities.length;
      const r = Math.min(width, height) * 0.35;
      return {
        ...e,
        x: cx + r * Math.cos(angle) + (Math.random() - 0.5) * 40,
        y: cy + r * Math.sin(angle) + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
      };
    });
    forceRender((n) => n + 1);
  }, [entities, width, height]);

  // Force simulation
  useEffect(() => {
    const nodes = nodesRef.current;
    if (nodes.length === 0) return;

    let tickCount = 0;
    const maxTicks = 200;
    const alpha0 = 0.3;

    function tick() {
      if (tickCount >= maxTicks) return;
      tickCount++;
      const alpha = alpha0 * (1 - tickCount / maxTicks);
      if (alpha < 0.001) return;

      const cx = width / 2;
      const cy = height / 2;

      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          let dx = nodes[j].x - nodes[i].x;
          let dy = nodes[j].y - nodes[i].y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const repulse = 2000 / (dist * dist);
          const fx = (dx / dist) * repulse * alpha;
          const fy = (dy / dist) * repulse * alpha;
          nodes[i].vx -= fx;
          nodes[i].vy -= fy;
          nodes[j].vx += fx;
          nodes[j].vy += fy;
        }
      }

      // Attraction (edges)
      for (const rel of relationships) {
        const a = nodes.find((n) => n.uid === rel.source);
        const b = nodes.find((n) => n.uid === rel.target);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const strength = 0.05 * (rel.weight || 1);
        const fx = dx * strength * alpha;
        const fy = dy * strength * alpha;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }

      // Center gravity
      for (const n of nodes) {
        n.vx += (cx - n.x) * 0.01 * alpha;
        n.vy += (cy - n.y) * 0.01 * alpha;
      }

      // Apply velocities with damping
      for (const n of nodes) {
        if (n.uid === dragging) continue;
        n.vx *= 0.6;
        n.vy *= 0.6;
        n.x += n.vx;
        n.y += n.vy;
        // Bounds
        const r = nodeRadius(n);
        n.x = Math.max(r, Math.min(width - r, n.x));
        n.y = Math.max(r, Math.min(height - r, n.y));
      }

      forceRender((c) => c + 1);
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [entities, relationships, width, height, dragging]);

  // Drag handlers
  const handleMouseDown = useCallback(
    (uid: string, e: React.MouseEvent) => {
      e.preventDefault();
      const node = nodesRef.current.find((n) => n.uid === uid);
      if (!node) return;
      setDragging(uid);
      dragOffset.current = { x: e.clientX - node.x, y: e.clientY - node.y };
    },
    []
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging) return;
      const node = nodesRef.current.find((n) => n.uid === dragging);
      if (!node) return;
      node.x = e.clientX - dragOffset.current.x;
      node.y = e.clientY - dragOffset.current.y;
      node.vx = 0;
      node.vy = 0;
      forceRender((c) => c + 1);
    },
    [dragging]
  );

  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  const nodes = nodesRef.current;

  // Find connected nodes for hover highlight
  const connectedSet = new Set<string>();
  if (hovered) {
    connectedSet.add(hovered);
    for (const rel of relationships) {
      if (rel.source === hovered) connectedSet.add(rel.target);
      if (rel.target === hovered) connectedSet.add(rel.source);
    }
  }

  return (
    <div className="bg-bg-card rounded-2xl p-4 overflow-hidden">
      <p className="font-mono text-[11px] text-text-secondary/80 mb-2">
        // entity_network_graph
      </p>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full"
        style={{ maxHeight: height }}
        viewBox={`0 0 ${width} ${height}`}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Edges */}
        {relationships.map((rel, i) => {
          const a = nodes.find((n) => n.uid === rel.source);
          const b = nodes.find((n) => n.uid === rel.target);
          if (!a || !b) return null;
          const isHighlight =
            hovered && (connectedSet.has(a.uid) && connectedSet.has(b.uid));
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={isHighlight ? "#14b8a6" : "#334155"}
              strokeWidth={isHighlight ? 1.5 : 0.7}
              strokeOpacity={hovered ? (isHighlight ? 0.8 : 0.15) : 0.4}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const r = nodeRadius(node);
          const color = communityColor(node.community_id);
          const isActive = !hovered || connectedSet.has(node.uid);
          const isHov = hovered === node.uid;
          return (
            <g
              key={node.uid}
              style={{ cursor: "grab" }}
              onMouseDown={(e) => handleMouseDown(node.uid, e)}
              onMouseEnter={() => setHovered(node.uid)}
              onMouseLeave={() => setHovered(null)}
              opacity={isActive ? 1 : 0.2}
            >
              {/* Glow */}
              {isHov && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r + 4}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  strokeOpacity={0.5}
                />
              )}
              {/* Volatility ring */}
              {node.volatility > 0.3 && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r + 2}
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth={1}
                  strokeOpacity={node.volatility * 0.8}
                  strokeDasharray="2 2"
                />
              )}
              <circle cx={node.x} cy={node.y} r={r} fill={color} />
              {/* Label */}
              {(isHov || r > 10) && (
                <text
                  x={node.x}
                  y={node.y + r + 12}
                  textAnchor="middle"
                  fill="#e2e8f0"
                  fontSize={isHov ? 11 : 9}
                  fontFamily="monospace"
                  fontWeight={isHov ? "bold" : "normal"}
                >
                  {node.name.length > 16
                    ? node.name.slice(0, 14) + "..."
                    : node.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Hover tooltip */}
      {(() => {
        const hovNode = hovered ? nodes.find((n) => n.uid === hovered) : null;
        if (!hovNode) return null;
        return (
          <div className="mt-2 flex items-center gap-4 font-mono text-[11px]">
            <span className="text-text-primary font-bold">{hovNode.name}</span>
            <span className="text-text-secondary">{hovNode.object_type}</span>
            <span className="text-accent-teal">
              stance: {hovNode.stance?.toFixed(2) ?? "N/A"}
            </span>
            <span className="text-accent-orange">
              vol: {hovNode.volatility?.toFixed(2) ?? "N/A"}
            </span>
            <span className="text-text-secondary">
              influence: {hovNode.influence_score?.toFixed(2) ?? "N/A"}
            </span>
          </div>
        );
      })()}

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-3 font-mono text-[10px] text-text-secondary/60">
        <span>Size = influence</span>
        <span>Color = community</span>
        <span className="text-[#ef4444]">--- = high volatility</span>
      </div>
    </div>
  );
}
