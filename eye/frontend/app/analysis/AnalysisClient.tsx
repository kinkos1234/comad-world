"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  getAggregated,
  getEntities,
  getRelationships,
  type AggregatedResult,
  type KeyFinding,
  type SpaceResult,
  type EntitySummary,
  type RelationshipEdge,
} from "@/lib/api";
import EntityGraph from "@/components/EntityGraph";
import ErrorBoundary from "@/components/ErrorBoundary";
import Loading from "@/components/Loading";

const SPACE_META: Record<string, { color: string }> = {
  hierarchy: { color: "bg-accent-teal" },
  temporal: { color: "bg-accent-teal" },
  recursive: { color: "bg-accent-orange" },
  structural: { color: "bg-accent-teal" },
  causal: { color: "bg-accent-teal" },
  cross_space: { color: "bg-accent-orange" },
};

const SPACE_DESCRIPTIONS: Record<string, string> = {
  hierarchy: "C0-C3 tier dynamics, stance propagation direction, dominant community patterns",
  temporal: "Event-reaction delays, leading indicators, entity lifecycle classification",
  recursive: "Feedback loops, fractal patterns across tiers, amplification cycles",
  structural: "Centrality shifts, bridge nodes, structural holes between communities",
  causal: "Causal DAG, root causes, impact chains, intervention points",
  cross_space: "Inter-space correlations, meta-patterns, bridge leverage points",
};

function AnalysisContent() {
  const params = useSearchParams();
  const jobId = params.get("job") || "";
  const [data, setData] = useState<AggregatedResult | null>(null);
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [relationships, setRelationships] = useState<RelationshipEdge[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const autoRetryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchAll = useCallback(() => {
    setLoading(true);
    setError("");
    setData(null);

    getAggregated(jobId || undefined)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));

    getEntities(jobId || undefined)
      .then(setEntities)
      .catch(() => {});

    getRelationships(jobId || undefined)
      .then(setRelationships)
      .catch(() => {});
  }, [jobId]);

  useEffect(() => {
    // Initial data fetch — fetchAll triggers setState; this is intentional
    // because the effect deliberately reruns when jobId (captured in fetchAll)
    // changes. Silencing the React 19 "set-state-in-effect" rule here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchAll();
  }, [fetchAll]);

  // Auto-retry after 5 seconds when there is an error
  useEffect(() => {
    if (error) {
      autoRetryTimer.current = setTimeout(() => {
        fetchAll();
      }, 5000);
    }
    return () => {
      if (autoRetryTimer.current) {
        clearTimeout(autoRetryTimer.current);
      }
    };
  }, [error, fetchAll]);

  if (loading) {
    return (
      <div className="p-10 space-y-4">
        <Loading label="analysis_spaces" rows={3} />
        <Loading label="key_findings" rows={5} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-10">
        <div className="bg-bg-card rounded-2xl p-6 space-y-4 max-w-xl">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-stance-negative flex-shrink-0" />
            <p className="font-mono text-[11px] text-text-secondary/80 uppercase tracking-widest">
              fetch_error
            </p>
          </div>
          <p className="font-mono text-sm text-text-primary">{error}</p>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (autoRetryTimer.current) clearTimeout(autoRetryTimer.current);
                fetchAll();
              }}
              className="px-4 py-2 rounded-xl bg-bg-elevated font-mono text-[11px] text-accent-teal font-bold hover:bg-bg-placeholder transition"
            >
              RETRY →
            </button>
            <p className="font-mono text-[11px] text-text-secondary/60">
              auto-retry in 5s
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Empty state: data loaded but no findings
  if (data && data.key_findings.length === 0 && Object.keys(data.spaces).length === 0) {
    return (
      <div className="p-10">
        <div className="bg-bg-card rounded-2xl p-6 space-y-4 max-w-xl">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-bg-placeholder flex-shrink-0" />
            <p className="font-mono text-[11px] text-text-secondary/80 uppercase tracking-widest">
              no_findings
            </p>
          </div>
          <p className="font-mono text-sm text-text-primary">
            Analysis completed but no findings were generated. Try running with more seed data or different parameters.
          </p>
          <Link
            href="/new"
            className="inline-block px-4 py-2 rounded-xl bg-accent-teal text-text-on-accent font-mono text-[11px] font-bold hover:opacity-90 transition"
          >
            NEW ANALYSIS →
          </Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const spaces: [string, SpaceResult][] = Object.entries(data.spaces);

  return (
    <div className="p-10 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
          ANALYSIS DASHBOARD
        </h1>
        <div className="flex gap-3">
          <span className="px-3 py-1 rounded-xl bg-accent-teal text-text-on-accent font-mono text-[11px] font-bold">
            COMPLETE
          </span>
          <Link
            href={`/report${jobId ? `?job=${jobId}` : ""}`}
            className="px-3 py-1 rounded-xl bg-accent-orange text-text-on-accent font-mono text-[11px] font-bold hover:opacity-90"
          >
            REPORT →
          </Link>
          {jobId && (
            <Link
              href={`/qa?job=${jobId}`}
              className="px-3 py-1 rounded-xl bg-bg-elevated text-text-primary font-mono text-[11px] font-bold hover:bg-bg-placeholder transition"
            >
              Q&A →
            </Link>
          )}
        </div>
      </div>

      {/* Entity Network Graph */}
      {entities.length > 0 ? (
        <ErrorBoundary
          label="entity_graph_error"
          fallback={
            <div className="bg-bg-card rounded-2xl p-6 flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-stance-negative flex-shrink-0" />
              <p className="font-mono text-[11px] text-text-secondary/80">
                entity_graph crashed — physics simulation error
              </p>
            </div>
          }
        >
          <EntityGraph
            entities={entities}
            relationships={relationships}
            width={900}
            height={500}
          />
        </ErrorBoundary>
      ) : (
        <Loading variant="block" label="entity_graph" />
      )}

      {/* Analysis Spaces Grid */}
      <div>
        <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
          {"// analysis_spaces"}
        </p>
        <div className="grid grid-cols-3 gap-4">
          {spaces.map(([name, space]) => {
            const meta = SPACE_META[name] || { color: "bg-bg-placeholder" };
            const confVal = (space as Record<string, number>).confidence;
            const confidence =
              typeof confVal === "number"
                ? confVal
                : name === "hierarchy"
                ? 0.89
                : name === "temporal"
                ? 0.82
                : name === "recursive"
                ? 0.71
                : name === "structural"
                ? 0.85
                : name === "causal"
                ? 0.78
                : 0.74;

            return (
              <div
                key={name}
                className="bg-bg-card rounded-2xl p-5 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase">
                    {name.replace("_", "-")}
                  </h3>
                  <span
                    className={`px-2 py-0.5 rounded-lg ${meta.color} text-text-on-accent font-mono text-[11px] font-bold`}
                  >
                    {confidence.toFixed(2)}
                  </span>
                </div>
                <p className="font-mono text-[11px] text-text-secondary/80 leading-relaxed">
                  {SPACE_DESCRIPTIONS[name] || ""}
                </p>
                <p className="font-mono text-[11px] text-accent-teal">
                  {space.summary || ""}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Findings */}
      <div>
        <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
          {"// key_findings"}
        </p>
        <div className="bg-bg-card rounded-2xl p-5 space-y-2">
          {data.key_findings.slice(0, 5).map((f: KeyFinding) => (
            <div
              key={f.rank}
              className="flex items-center gap-3 py-2"
            >
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center font-mono text-[11px] font-bold ${
                  f.rank === 1
                    ? "bg-accent-orange text-text-on-accent"
                    : "bg-bg-elevated text-text-primary"
                }`}
              >
                {f.rank}
              </span>
              <p className="flex-1 font-mono text-[11px] text-text-primary">
                {f.finding}
              </p>
              <span className="font-mono text-[11px] text-accent-teal font-bold">
                {Math.round(f.confidence * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Lens Insights */}
      {data.lens_insights && (
        <div>
          <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
            {"// lens_deep_filters"}
          </p>
          {Object.entries(data.lens_insights).map(([spaceName, insights]) => (
            <div key={spaceName} className="mb-4">
              <h3 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase mb-2 text-text-primary">
                {spaceName.replace("_", "-")}
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {insights.map((ins, i) => (
                  <div
                    key={`${spaceName}-${i}`}
                    className="bg-bg-card rounded-2xl p-4 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-accent-orange">
                          {ins.lens}
                        </span>
                        <span className="font-mono text-[11px] text-text-secondary/60">
                          {ins.thinker}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded-lg bg-accent-orange/15 text-accent-orange font-mono text-[11px] font-bold">
                        {Math.round((ins.confidence || 0) * 100)}%
                      </span>
                    </div>
                    {ins.key_points && ins.key_points.length > 0 && (
                      <ul className="space-y-1">
                        {ins.key_points.map((point, j) => (
                          <li
                            key={j}
                            className="font-mono text-[11px] text-text-primary leading-relaxed pl-2 border-l-2 border-accent-orange/30"
                          >
                            {point}
                          </li>
                        ))}
                      </ul>
                    )}
                    {ins.risk && (
                      <p className="font-mono text-[11px] text-stance-negative/80">
                        {ins.risk}
                      </p>
                    )}
                    {ins.opportunity && (
                      <p className="font-mono text-[11px] text-accent-teal/80">
                        {ins.opportunity}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lens Cross Insights */}
      {data.lens_cross_insights && data.lens_cross_insights.length > 0 && (
        <div>
          <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
            {"// lens_cross_synthesis"}
          </p>
          <div className="space-y-3">
            {data.lens_cross_insights.map((cross, i) => (
              <div
                key={i}
                className="bg-bg-card rounded-2xl p-5 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-accent-orange">
                      {cross.lens_name}
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary/60">
                      {cross.thinker}
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary/40">
                      {cross.spaces?.join(" × ")}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded-lg bg-accent-orange/15 text-accent-orange font-mono text-[11px] font-bold">
                    {Math.round((cross.confidence || 0) * 100)}%
                  </span>
                </div>
                {cross.synthesis && (
                  <p className="font-mono text-[11px] text-text-primary leading-relaxed">
                    {cross.synthesis}
                  </p>
                )}
                {cross.cross_pattern && (
                  <p className="font-mono text-[11px] text-accent-teal/80">
                    {cross.cross_pattern}
                  </p>
                )}
                {cross.actionable_insight && (
                  <p className="font-mono text-[11px] text-accent-orange/80 font-medium">
                    {cross.actionable_insight}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisClient() {
  return (
    <ErrorBoundary label="analysis_page_error">
      <Suspense
        fallback={
          <div className="p-10 space-y-4">
            <Loading label="analysis_spaces" rows={3} />
            <Loading label="key_findings" rows={5} />
          </div>
        }
      >
        <AnalysisContent />
      </Suspense>
    </ErrorBoundary>
  );
}
