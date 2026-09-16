'use client';

import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.props.onError?.(error, info);
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const { fallback } = this.props;
    if (typeof fallback === 'function') return fallback(error, this.reset);
    if (fallback) return fallback;

    return (
      <div
        role="alert"
        aria-live="assertive"
        className="rounded-xl border border-status-error/30 bg-status-error/5 p-5 space-y-3"
      >
        <p className="text-sm font-semibold text-status-error">Something went wrong</p>
        <p className="text-xs text-content-secondary font-mono break-words">{error.message}</p>
        <button
          onClick={this.reset}
          className="text-xs underline text-content-tertiary hover:text-content-primary"
        >
          Try again
        </button>
      </div>
    );
  }
}
