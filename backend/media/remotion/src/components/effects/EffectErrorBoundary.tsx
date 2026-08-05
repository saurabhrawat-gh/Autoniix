import React from "react";

interface Props {
  children: React.ReactNode;
  /** Optional fallback to render on error. Defaults to rendering nothing. */
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catches rendering errors in effect/overlay components so a single broken
 * effect doesn't crash the entire composition. Logs the error and renders
 * either a provided fallback or nothing.
 */
export class EffectErrorBoundary extends React.Component<Props, State> {
  override state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[EffectErrorBoundary] Effect crashed:", error, info.componentStack);
  }

  override render(): React.ReactNode {
    if (this.state.hasError) {
      return this.state.error ? (this.props.fallback ?? null) : null;
    }
    return this.props.children;
  }
}
