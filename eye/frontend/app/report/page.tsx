import type { Metadata } from "next";
import ReportClient from "./ReportClient";
import { getReportServer } from "@/lib/server-api";

type SearchParams = Promise<{ job?: string }>;

function summarize(md: string, max = 280): string {
  const text = md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#*_`>~\-]+/g, " ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > max ? text.slice(0, max).trim() + "…" : text;
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<Metadata> {
  const { job } = await searchParams;
  const jobLabel = job ? ` (job ${job.slice(0, 8)})` : "";
  const title = `Report${jobLabel}`;
  let description =
    "Full narrative report: executive summary, key findings, evidence chains, and actionable recommendations.";
  if (job) {
    const md = await getReportServer(job);
    if (md) description = summarize(md);
  }
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { title, description },
  };
}

export default async function ReportPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { job } = await searchParams;
  const markdown = job ? await getReportServer(job) : null;

  return (
    <>
      {markdown && (
        <section
          aria-label="report_preview"
          className="sr-only"
          data-ssr-preview="report"
        >
          <h1>Report (job {job})</h1>
          <pre style={{ whiteSpace: "pre-wrap" }}>{markdown}</pre>
        </section>
      )}
      <ReportClient />
    </>
  );
}
