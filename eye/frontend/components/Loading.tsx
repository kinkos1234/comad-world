"use client";

interface Props {
  /** Number of skeleton rows to render (default 3) */
  rows?: number;
  /** Show a pulsing bar instead of rows (for graph/canvas placeholders) */
  variant?: "rows" | "block";
  label?: string;
  className?: string;
}

export default function Loading({
  rows = 3,
  variant = "rows",
  label,
  className = "",
}: Props) {
  if (variant === "block") {
    return (
      <div
        className={`bg-bg-card rounded-2xl p-6 space-y-3 ${className}`}
        aria-label={label ?? "loading"}
        aria-busy="true"
      >
        {label && (
          <p className="font-mono text-[11px] text-text-secondary/80 mb-2">
            // {label}
          </p>
        )}
        <div className="w-full h-48 bg-bg-elevated rounded-xl animate-pulse" />
        <div className="flex gap-2">
          <div className="h-2 w-1/3 bg-bg-elevated rounded-full animate-pulse" />
          <div className="h-2 w-1/4 bg-bg-placeholder rounded-full animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-bg-card rounded-2xl p-6 space-y-3 ${className}`}
      aria-label={label ?? "loading"}
      aria-busy="true"
    >
      {label && (
        <p className="font-mono text-[11px] text-text-secondary/80 mb-2">
          // {label}
        </p>
      )}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <div
            className="h-2 rounded-full bg-bg-elevated animate-pulse flex-shrink-0"
            style={{ width: "1rem", animationDelay: `${i * 80}ms` }}
          />
          <div
            className="h-2 rounded-full bg-bg-elevated animate-pulse flex-1"
            style={{
              maxWidth: `${75 - i * 12}%`,
              animationDelay: `${i * 80 + 40}ms`,
            }}
          />
        </div>
      ))}
    </div>
  );
}

/** Inline spinner — use inside buttons or small containers */
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block w-3 h-3 rounded-full border-2 border-accent-teal border-t-transparent animate-spin ${className}`}
      aria-label="loading"
    />
  );
}
