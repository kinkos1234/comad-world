import type { Metadata } from "next";
import AnalysisClient from "./AnalysisClient";
import { getAggregatedServer } from "@/lib/server-api";

type SearchParams = Promise<{ job?: string }>;

export async function generateMetadata({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<Metadata> {
  const { job } = await searchParams;
  const jobLabel = job ? ` (job ${job.slice(0, 8)})` : "";
  const title = `Analysis${jobLabel}`;
  let description = job
    ? `Multi-space knowledge graph analysis for job ${job}.`
    : "Multi-space knowledge graph analysis: hierarchy, temporal, recursive, structural, causal, and cross-space insights.";

  const data = await getAggregatedServer(job);
  if (data?.key_findings?.length) {
    const top = data.key_findings
      .slice(0, 3)
      .map((f) => f.finding)
      .join(" · ");
    if (top) description = top.slice(0, 300);
  }

  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { title, description },
  };
}

export default async function AnalysisPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { job } = await searchParams;
  const data = await getAggregatedServer(job);

  return (
    <>
      {data && (
        <section
          aria-label="analysis_preview"
          className="sr-only"
          data-ssr-preview="analysis"
        >
          <h1>Analysis{job ? ` (job ${job})` : ""}</h1>
          {data.key_findings?.length > 0 && (
            <>
              <h2>Key findings</h2>
              <ol>
                {data.key_findings.slice(0, 10).map((f) => (
                  <li key={f.rank}>
                    {f.finding} (confidence{" "}
                    {Math.round((f.confidence || 0) * 100)}%)
                  </li>
                ))}
              </ol>
            </>
          )}
          {data.spaces && Object.keys(data.spaces).length > 0 && (
            <>
              <h2>Analysis spaces</h2>
              <dl>
                {Object.entries(data.spaces).map(([name, space]) => (
                  <div key={name}>
                    <dt>{name.replace("_", "-")}</dt>
                    <dd>{space.summary || ""}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      )}
      <AnalysisClient />
    </>
  );
}
