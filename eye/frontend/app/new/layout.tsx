import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "New Analysis",
  description:
    "Start a new knowledge-graph analysis: ingest text sources, configure seeds, and launch a full multi-space simulation.",
  openGraph: {
    title: "New Analysis",
    description:
      "Start a new knowledge-graph analysis: ingest text sources, configure seeds, and launch a full multi-space simulation.",
  },
};

export default function NewLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
