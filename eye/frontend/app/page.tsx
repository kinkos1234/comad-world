"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJobs, getSystemStatus, deleteJob } from "@/lib/api";

import type { SystemStatusResponse } from "@/lib/api";

interface Job {
  job_id: string;
  status: string;
  seed_text: string;
  created_at: string;
}

export default function Dashboard() {
  const [system, setSystem] = useState<SystemStatusResponse | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [deleting, setDeleting] = useState<Set<string>>(new Set());

  useEffect(() => {
    getSystemStatus().then(setSystem).catch(() => {});
    getJobs().then(setJobs).catch(() => {});
  }, []);

  const handleDelete = async (jobId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`분석 이력 ${jobId}을(를) 삭제하시겠습니까?`)) return;
    setDeleting((prev) => new Set(prev).add(jobId));
    try {
      await deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
    } catch {
      alert("삭제에 실패했습니다.");
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    }
  };

  return (
    <div className="p-10 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
          DASHBOARD
        </h1>
        <Link
          href="/new"
          className="bg-accent-orange text-text-on-accent px-4 py-2 rounded-xl font-mono text-xs font-bold hover:opacity-90 transition"
        >
          + new_analysis
        </Link>
      </div>

      {/* System Status */}
      <div>
        <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
          {"// system_status"}
        </p>
        <div className="grid grid-cols-4 gap-4">
          <StatusCard
            label="neo4j"
            value={system?.neo4j ? "connected" : "offline"}
            ok={system?.neo4j ?? false}
          />
          <StatusCard
            label="ollama"
            value={system?.ollama ? "connected" : "offline"}
            ok={system?.ollama ?? false}
          />
          <StatusCard
            label="llm_model"
            value={system?.llm_model || "—"}
            ok={!!system?.llm_model}
          />
          <StatusCard
            label="device"
            value={
              system?.device?.total_ram_gb
                ? `${system.device.total_ram_gb}GB / ${system.device.gpu_type.toUpperCase()}`
                : "—"
            }
            ok={!!system?.device?.total_ram_gb}
          />
        </div>
      </div>

      {/* Recent Analyses */}
      <div>
        <p className="font-mono text-[11px] text-text-secondary/80 mb-3">
          {"// recent_analyses"}
        </p>
        {jobs.length === 0 ? (
          <div className="bg-bg-card rounded-2xl p-8 text-center">
            <p className="font-mono text-sm text-text-secondary">
              아직 분석 이력이 없습니다
            </p>
            <Link
              href="/new"
              className="inline-block mt-4 bg-accent-orange text-text-on-accent px-6 py-2 rounded-xl font-mono text-xs font-bold"
            >
              첫 분석 시작하기
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {jobs.slice(0, 9).map((job) => (
              <Link
                key={job.job_id}
                href={
                  job.status === "completed"
                    ? `/analysis?job=${job.job_id}`
                    : job.status === "running"
                    ? `/run?job=${job.job_id}`
                    : `/new`
                }
                className="bg-bg-card rounded-2xl p-5 hover:bg-bg-elevated transition space-y-3 relative group"
              >
                <div className="flex items-center justify-between">
                  <p className="font-mono text-sm text-text-primary">
                    {job.job_id}
                  </p>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                        job.status === "completed"
                          ? "bg-accent-teal text-text-on-accent"
                          : job.status === "running"
                          ? "bg-accent-orange text-text-on-accent"
                          : job.status === "failed"
                          ? "bg-stance-negative text-text-on-accent"
                          : "bg-bg-placeholder text-text-secondary"
                      }`}
                    >
                      {job.status}
                    </span>
                    {job.status !== "running" && (
                      <button
                        onClick={(e) => handleDelete(job.job_id, e)}
                        disabled={deleting.has(job.job_id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 rounded text-[11px] font-mono text-text-secondary hover:text-stance-negative hover:bg-stance-negative/10"
                        title="삭제"
                      >
                        {deleting.has(job.job_id) ? "..." : "×"}
                      </button>
                    )}
                  </div>
                </div>
                {job.seed_text && (
                  <p className="font-mono text-[11px] text-text-secondary/80 line-clamp-2 leading-relaxed">
                    {job.seed_text}
                  </p>
                )}
                {job.created_at && (
                  <p className="font-mono text-[11px] text-text-secondary/60">
                    {new Date(job.created_at).toLocaleString("ko-KR", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <div className="bg-bg-card rounded-2xl p-4 space-y-2">
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${
            ok ? "bg-accent-teal" : "bg-stance-negative"
          }`}
        />
        <span className="font-mono text-[11px] text-text-secondary/80">
          {label}
        </span>
      </div>
      <p className="font-mono text-sm text-text-primary">{value}</p>
    </div>
  );
}
