"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getReport } from "@/lib/api";

function ReportContent() {
  const params = useSearchParams();
  const jobId = params.get("job") || "default";
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getReport(jobId)
      .then((md) => {
        setMarkdown(md);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [jobId]);

  const handleDownload = () => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `comadeye-report-${jobId === "default" ? "latest" : jobId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="p-10">
        <p className="font-mono text-text-secondary text-sm">Loading report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-10 space-y-4">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
          REPORT
        </h1>
        <div className="bg-bg-card rounded-2xl p-6">
          <p className="font-mono text-stance-negative text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-10 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
          REPORT
        </h1>
        <div className="flex gap-3">
          <button
            onClick={handleDownload}
            className="px-4 py-1.5 rounded-xl bg-accent-orange text-text-on-accent font-mono text-[11px] font-bold hover:opacity-90 transition"
          >
            DOWNLOAD .MD
          </button>
          {jobId !== "default" && (
            <Link
              href={`/qa?job=${jobId}`}
              className="px-4 py-1.5 rounded-xl bg-bg-elevated text-text-primary font-mono text-[11px] font-bold hover:bg-bg-placeholder transition"
            >
              Q&A →
            </Link>
          )}
        </div>
      </div>

      {/* Job Info */}
      <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-bg-card border border-bg-elevated">
        <span className="w-2 h-2 rounded-full bg-accent-teal flex-shrink-0" />
        <span className="font-mono text-[11px] text-text-secondary/80">
          job_id:
        </span>
        <span className="font-mono text-[11px] text-accent-teal">
          {jobId === "default" ? "latest" : jobId.slice(0, 8)}
        </span>
      </div>

      {/* Report Body */}
      <div className="bg-bg-card rounded-2xl p-8 report-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10">
          <p className="font-mono text-text-secondary">Loading...</p>
        </div>
      }
    >
      <ReportContent />
    </Suspense>
  );
}
