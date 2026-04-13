import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Q&A Session",
  description:
    "Interactive Q&A over the knowledge graph: ask free-form questions and get evidence-backed answers grounded in the analysis result.",
  openGraph: {
    title: "Q&A Session",
    description:
      "Interactive Q&A over the knowledge graph: ask free-form questions and get evidence-backed answers grounded in the analysis result.",
  },
};

export default function QaLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
