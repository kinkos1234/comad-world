"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  label?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="bg-bg-card rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-stance-negative flex-shrink-0" />
            <p className="font-mono text-[11px] text-text-secondary/80 uppercase tracking-widest">
              {this.props.label ?? "render_error"}
            </p>
          </div>
          <p className="font-mono text-sm text-text-primary">
            {this.state.error?.message ?? "An unexpected error occurred."}
          </p>
          {this.state.error?.stack && (
            <pre className="font-mono text-[10px] text-text-secondary/60 bg-bg-elevated rounded-xl p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {this.state.error.stack.split("\n").slice(0, 6).join("\n")}
            </pre>
          )}
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 rounded-xl bg-bg-elevated font-mono text-[11px] text-accent-teal font-bold hover:bg-bg-placeholder transition"
          >
            RETRY →
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
