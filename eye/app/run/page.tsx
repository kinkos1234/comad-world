"use client";

import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { streamStatus, retryJob, type StageUpdate } from "@/lib/api";

const STAGES = [
  "ingestion",
  "graph",
  "community",
  "simulation",
  "analysis",
  "report",
] as const;

const STAGE_LABELS: Record<string, string> = {
  ingestion: "INGESTION",
  graph: "GRAPH",
  community: "COMMUNITY",
  simulation: "SIMULATION",
  analysis: "ANALYSIS",
  report: "REPORT",
};

function RunPageContent() {
  const params = useSearchParams();
  const jobId = params.get("job") || "";
  const [stages, setStages] = useState<Record<string, string>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [chunkProgress, setChunkProgress] = useState<{
    completed: number;
    total: number;
    failed: number;
    retrying: number;
  } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const handleUpdate = useCallback(
    (update: StageUpdate) => {
      if (update.stage === "done") {
        setDone(true);
        if (update.status === "completed") {
          setLogs((prev) => [...prev, `[✓] 파이프라인 완료`]);
        } else {
          setFailed(true);
          setLogs((prev) => [
            ...prev,
            `[✗] 파이프라인 실패: ${update.error || "unknown"}`,
          ]);
        }
        return;
      }

      setStages((prev) => ({ ...prev, [update.stage]: update.status }));
      if (update.message) {
        const icon = update.status === "completed" ? "✓" : "▶";
        setLogs((prev) => [...prev, `[${icon}] ${update.message}`]);
      }
      if (update.data && Object.keys(update.data).length > 0) {
        // Track chunk progress for ingestion stage
        if (
          update.data.chunk_total !== undefined &&
          update.data.chunk_completed !== undefined
        ) {
          setChunkProgress({
            completed: update.data.chunk_completed as number,
            total: update.data.chunk_total as number,
            failed: (update.data.chunk_failed as number) || 0,
            retrying: (update.data.chunk_retrying as number) || 0,
          });
        }
        setStats((prev) => ({ ...prev, ...update.data }));
      }
    },
    [jobId]
  );

  useEffect(() => {
    if (!jobId) return;
    const es = streamStatus(jobId, handleUpdate);
    return () => es.close();
  }, [jobId, handleUpdate]);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [logs]);

  const getStageStatus = (stage: string) => {
    const s = stages[stage];
    if (s === "completed") return "completed";
    if (s === "running") return "running";
    return "pending";
  };

  return (
    <div className="p-10 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
          PIPELINE PROGRESS
        </h1>
        <span
          className={`px-3 py-1 rounded-xl font-mono text-[11px] font-bold ${
            done
              ? "bg-accent-teal text-text-on-accent"
              : "bg-accent-orange text-text-on-accent"
          }`}
        >
          {done ? "COMPLETE" : "RUNNING"}
        </span>
      </div>

      {/* Pipeline Stages */}
      <div>
        <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
          // pipeline_stages
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          {STAGES.map((stage, i) => {
            const status = getStageStatus(stage);
            return (
              <div key={stage} className="flex items-center gap-2">
                <span
                  className={`px-4 py-2.5 rounded-lg font-mono text-[11px] font-bold ${
                    status === "completed"
                      ? "bg-accent-teal text-text-on-accent"
                      : status === "running"
                      ? "bg-accent-orange text-text-on-accent"
                      : "bg-bg-placeholder text-text-secondary"
                  }`}
                >
                  {status === "completed"
                    ? "✓"
                    : status === "running"
                    ? "▶"
                    : "○"}{" "}
                  {STAGE_LABELS[stage]}
                </span>
                {i < STAGES.length - 1 && (
                  <span className="text-text-secondary font-mono text-sm">→</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Chunk Progress Bar */}
      {chunkProgress && chunkProgress.total > 0 && (
        <div className="bg-bg-card rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[11px] text-text-secondary/80">
              // chunk_progress
            </p>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] text-text-primary">
                {chunkProgress.completed}/{chunkProgress.total}
              </span>
              {chunkProgress.failed > 0 && (
                <span className="font-mono text-[11px] text-stance-negative">
                  {chunkProgress.failed} failed
                </span>
              )}
              {chunkProgress.retrying > 0 && (
                <span className="font-mono text-[11px] text-accent-orange">
                  {chunkProgress.retrying} retrying
                </span>
              )}
            </div>
          </div>
          <div className="w-full h-2 bg-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-accent-teal rounded-full transition-all duration-300"
              style={{
                width: `${Math.round((chunkProgress.completed / chunkProgress.total) * 100)}%`,
              }}
            />
          </div>
          <p className="font-mono text-[11px] text-text-secondary/60">
            {Math.round((chunkProgress.completed / chunkProgress.total) * 100)}% 완료
            {chunkProgress.total > 0 && chunkProgress.completed > 0 && chunkProgress.completed < chunkProgress.total && (
              <> — 남은 배치: {chunkProgress.total - chunkProgress.completed}</>
            )}
          </p>
        </div>
      )}

      {/* Log + Stats */}
      <div className="flex gap-6">
        {/* Log Panel */}
        <div className="flex-1 bg-bg-card rounded-2xl p-6 space-y-3">
          <p className="font-mono text-[11px] text-text-secondary/80">
            // real_time_log
          </p>
          <div
            ref={logRef}
            className="h-[350px] bg-[#141414] rounded-lg p-4 overflow-y-auto space-y-1"
          >
            {logs.map((log, i) => (
              <p
                key={i}
                className={`font-mono text-[11px] ${
                  log.includes("✓")
                    ? "text-accent-teal"
                    : log.includes("▶")
                    ? "text-accent-orange"
                    : log.includes("✗")
                    ? "text-stance-negative"
                    : "text-text-secondary"
                }`}
              >
                {log}
              </p>
            ))}
            {!done && (
              <span className="inline-block w-2 h-4 bg-accent-orange animate-pulse" />
            )}
          </div>
        </div>

        {/* Stats Panel */}
        <div className="w-[320px] space-y-4">
          <p className="font-mono text-[11px] text-text-secondary/80">
            // round_summary
          </p>
          <div className="bg-bg-card rounded-2xl p-5 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <StatBox
                label="total_rounds"
                value={String(stats.total_rounds ?? "—")}
              />
              <StatBox
                label="total_events"
                value={String(stats.total_events ?? "—")}
              />
              <StatBox
                label="total_actions"
                value={String(stats.total_actions ?? "—")}
              />
              <StatBox
                label="key_findings"
                value={String(stats.key_findings_count ?? "—")}
                accent
              />
            </div>
          </div>
        </div>
      </div>

      {/* Completion Actions */}
      {done && !failed && (
        <div className="flex gap-3">
          <Link
            href={`/report?job=${jobId}`}
            className="px-6 py-3 bg-accent-orange text-text-on-accent rounded-2xl font-[family-name:var(--font-display)] text-sm font-bold tracking-wider hover:opacity-90 transition"
          >
            VIEW REPORT →
          </Link>
          <Link
            href={`/analysis?job=${jobId}`}
            className="px-6 py-3 bg-bg-elevated text-text-primary rounded-2xl font-[family-name:var(--font-display)] text-sm font-bold tracking-wider hover:bg-bg-placeholder transition"
          >
            ANALYSIS DASHBOARD
          </Link>
          <Link
            href={`/qa?job=${jobId}`}
            className="px-6 py-3 bg-bg-elevated text-text-primary rounded-2xl font-[family-name:var(--font-display)] text-sm font-bold tracking-wider hover:bg-bg-placeholder transition"
          >
            Q&A SESSION
          </Link>
        </div>
      )}

      {/* Failure Recovery */}
      {done && failed && (
        <div className="bg-bg-card rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-stance-negative" />
            <p className="font-mono text-sm text-stance-negative font-bold">
              파이프라인 실패
            </p>
          </div>
          <p className="font-mono text-[11px] text-text-secondary/80">
            아래 옵션으로 재시도하거나 부분 결과를 확인할 수 있습니다.
          </p>
          <div className="flex gap-3 flex-wrap">
            <button
              onClick={async () => {
                if (retrying) return;
                setRetrying(true);
                try {
                  const { job_id } = await retryJob(jobId);
                  router.push(`/run?job=${job_id}`);
                } catch {
                  setRetrying(false);
                }
              }}
              disabled={retrying}
              className="px-5 py-2.5 bg-accent-orange text-text-on-accent rounded-xl font-mono text-[11px] font-bold hover:opacity-90 transition disabled:opacity-40"
            >
              {retrying ? "재시도 중..." : "캐시 사용 재시도"}
            </button>
            <Link
              href={`/analysis?job=${jobId}`}
              className="px-5 py-2.5 bg-bg-elevated text-text-primary rounded-xl font-mono text-[11px] font-bold hover:bg-bg-placeholder transition"
            >
              부분 결과 확인
            </Link>
            <Link
              href="/new"
              className="px-5 py-2.5 bg-bg-elevated text-text-secondary rounded-xl font-mono text-[11px] font-bold hover:bg-bg-placeholder transition"
            >
              새 분석
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="bg-bg-elevated rounded-lg p-3 space-y-1">
      <p className="font-mono text-[11px] text-text-secondary/80">{label}</p>
      <p
        className={`font-mono text-lg font-bold ${
          accent ? "text-accent-teal" : "text-text-primary"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10">
          <p className="font-mono text-text-secondary">Loading...</p>
        </div>
      }
    >
      <RunPageContent />
    </Suspense>
  );
}
