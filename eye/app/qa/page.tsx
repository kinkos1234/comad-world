"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { askQuestion, getAggregated, getJob } from "@/lib/api";
import ErrorBoundary from "@/components/ErrorBoundary";
import Loading, { Spinner } from "@/components/Loading";

interface Message {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

interface SpaceInfo {
  name: string;
  summary: string;
}

// Threshold in ms after which we show "Still generating..."
const SLOW_RESPONSE_THRESHOLD = 15000;

function ErrorBanner({
  message,
  onRetry,
  onDismiss,
}: {
  message: string;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-stance-negative/10 border border-stance-negative/30 mb-3">
      <span className="w-2 h-2 rounded-full bg-stance-negative flex-shrink-0" />
      <p className="flex-1 font-mono text-[11px] text-stance-negative">
        {message}
      </p>
      <button
        onClick={onRetry}
        className="px-3 py-1 rounded-lg bg-bg-elevated font-mono text-[11px] text-accent-teal font-bold hover:bg-bg-placeholder transition flex-shrink-0"
      >
        RETRY
      </button>
      <button
        onClick={onDismiss}
        className="font-mono text-[11px] text-text-secondary/60 hover:text-text-secondary transition flex-shrink-0"
        aria-label="Dismiss error"
      >
        ✕
      </button>
    </div>
  );
}

function QAContent() {
  const params = useSearchParams();
  const jobId = params.get("job") || "default";
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [slowResponse, setSlowResponse] = useState(false);
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [spaces, setSpaces] = useState<SpaceInfo[]>([]);
  const [seedExcerpt, setSeedExcerpt] = useState("");
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>("");
  const chatRef = useRef<HTMLDivElement>(null);
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (jobId !== "default") {
      getJob(jobId)
        .then((job) => {
          if (job.seed_text) {
            setSeedExcerpt(job.seed_text);
          }
        })
        .catch(() => {});
    }
  }, [jobId]);

  useEffect(() => {
    getAggregated()
      .then((data) => {
        const s = Object.entries(data.spaces).map(([name, space]) => ({
          name,
          summary:
            typeof space === "object" && space !== null
              ? (space as { summary?: string }).summary || ""
              : "",
        }));
        setSpaces(s);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight);
  }, [messages, loading]);

  // Clear slow timer on unmount
  useEffect(() => {
    return () => {
      if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
    };
  }, []);

  const sendQuestion = useCallback(
    async (question: string) => {
      setInput("");
      setLastQuestion(question);
      setMessages((prev) => [...prev, { role: "user", content: question }]);
      setFollowUps([]);
      setLoading(true);
      setSlowResponse(false);
      setErrorBanner(null);

      // Show "Still generating..." after 15 seconds
      slowTimerRef.current = setTimeout(() => {
        setSlowResponse(true);
      }, SLOW_RESPONSE_THRESHOLD);

      try {
        const res = await askQuestion(jobId, question);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.answer },
        ]);
        setFollowUps(res.follow_ups || []);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setErrorBanner(`Failed to get response: ${msg}`);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "답변을 생성할 수 없습니다. 다시 시도해주세요.",
            isError: true,
          },
        ]);
      } finally {
        if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
        setLoading(false);
        setSlowResponse(false);
      }
    },
    [jobId]
  );

  const handleSend = (question?: string) => {
    const q = question || input.trim();
    if (!q || loading) return;
    sendQuestion(q);
  };

  const handleRetryLastQuestion = () => {
    if (!lastQuestion || loading) return;
    setErrorBanner(null);
    // Remove the last assistant error message before retrying
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.isError) {
        return prev.slice(0, -1);
      }
      return prev;
    });
    sendQuestion(lastQuestion);
  };

  return (
    <div className="flex h-screen">
      {/* Chat Panel */}
      <div className="flex-1 flex flex-col p-10">
        {/* Header */}
        <div className="mb-6 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
              Q&A SESSION
            </h1>
            <span className="px-3 py-1 rounded-xl bg-bg-elevated font-mono text-[11px] text-text-secondary/80 font-bold">
              {messages.filter((m) => m.role === "user").length} turns
            </span>
          </div>
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-bg-card border border-bg-elevated">
            <span className="w-2 h-2 rounded-full bg-accent-teal flex-shrink-0" />
            <p className="font-mono text-[11px] text-text-secondary/80 truncate flex-1">
              {seedExcerpt
                ? seedExcerpt.length > 80
                  ? seedExcerpt.slice(0, 80) + "..."
                  : seedExcerpt
                : "분석 데이터 없음"}
            </p>
            <span className="font-mono text-[11px] text-text-secondary/80 flex-shrink-0">
              {jobId === "default" ? "latest" : jobId.slice(0, 8)}
            </span>
          </div>
        </div>

        {/* Error Banner */}
        {errorBanner && (
          <ErrorBanner
            message={errorBanner}
            onRetry={handleRetryLastQuestion}
            onDismiss={() => setErrorBanner(null)}
          />
        )}

        {/* Messages */}
        <div
          ref={chatRef}
          className="flex-1 overflow-y-auto space-y-5 mb-6"
        >
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <p className="font-mono text-sm text-text-secondary">
                질문을 입력하세요
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className="flex gap-3">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-[family-name:var(--font-display)] text-sm font-bold ${
                  msg.role === "user"
                    ? "bg-accent-orange text-text-on-accent"
                    : msg.isError
                    ? "bg-stance-negative/20 text-stance-negative"
                    : "bg-accent-teal text-text-on-accent"
                }`}
              >
                {msg.role === "user" ? "U" : "C"}
              </div>
              <div
                className={`flex-1 rounded-2xl p-4 font-mono text-[11px] leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-bg-elevated text-text-primary"
                    : msg.isError
                    ? "bg-stance-negative/10 text-stance-negative border border-stance-negative/20"
                    : "bg-bg-card text-text-primary"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div
              className="flex gap-3"
              aria-label="AI is thinking"
              aria-live="polite"
            >
              <div className="w-8 h-8 rounded-full bg-accent-teal flex items-center justify-center font-[family-name:var(--font-display)] text-sm font-bold text-text-on-accent flex-shrink-0">
                C
              </div>
              <div className="bg-bg-card rounded-2xl p-4 flex items-center gap-3">
                <Spinner />
                <span className="font-mono text-[11px] text-text-secondary/80">
                  {slowResponse
                    ? "Still generating... LLM response may take up to 90s"
                    : "generating response..."}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Follow-up Chips */}
        {followUps.length > 0 && (
          <div className="flex gap-2 mb-3 flex-wrap">
            {followUps.map((q, i) => (
              <button
                key={i}
                onClick={() => handleSend(q)}
                className="px-3 py-1.5 rounded-xl bg-bg-elevated font-mono text-[11px] text-accent-teal hover:bg-bg-placeholder transition"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="flex gap-3">
          <input
            type="text"
            className="flex-1 h-11 bg-bg-card rounded-xl px-4 font-mono text-[11px] text-text-primary placeholder:text-bg-placeholder focus:outline-none focus:ring-2 focus:ring-accent-orange/50"
            placeholder="질문을 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="w-11 h-11 bg-accent-orange rounded-xl flex items-center justify-center font-mono text-lg text-text-on-accent font-bold disabled:opacity-40 hover:opacity-90 transition"
            aria-label={loading ? "Sending…" : "Send"}
          >
            {loading ? (
              <Spinner className="border-text-on-accent border-t-transparent" />
            ) : (
              "→"
            )}
          </button>
        </div>
      </div>

      {/* Context Panel */}
      <div className="w-[320px] bg-bg-card p-6 space-y-5 overflow-y-auto">
        <h2 className="font-[family-name:var(--font-display)] text-base font-bold">
          CONTEXT
        </h2>

        <div>
          <p className="font-mono text-[11px] text-text-secondary/80 mb-2">
            // related_spaces
          </p>
          <div className="space-y-2">
            {spaces.map((s) => (
              <div key={s.name} className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-teal" />
                <span className="font-mono text-[11px] text-text-primary">
                  {s.name}
                </span>
              </div>
            ))}
          </div>
        </div>

        {spaces.length > 0 && (
          <div>
            <p className="font-mono text-[11px] text-text-secondary/80 mb-2">
              // space_summaries
            </p>
            <div className="space-y-3">
              {spaces.slice(0, 3).map((s) => (
                <div
                  key={s.name}
                  className="bg-bg-elevated rounded-xl p-3 space-y-1"
                >
                  <p className="font-mono text-[11px] text-accent-orange font-bold">
                    {s.name}
                  </p>
                  <p className="font-mono text-[11px] text-text-secondary/80">
                    {s.summary}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function QAPage() {
  return (
    <ErrorBoundary label="qa_page_error">
      <Suspense
        fallback={
          <div className="p-10">
            <Loading label="qa_session" rows={4} />
          </div>
        }
      >
        <QAContent />
      </Suspense>
    </ErrorBoundary>
  );
}
