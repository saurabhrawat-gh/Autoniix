import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '../ErrorBoundary';

const throwControl = { shouldThrow: false };

function Boom() {
  if (throwControl.shouldThrow) throw new Error('Test explosion');
  return <div>All good</div>;
}

beforeEach(() => {
  throwControl.shouldThrow = false;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('All good')).toBeInTheDocument();
  });

  it('renders default fallback on error', () => {
    throwControl.shouldThrow = true;
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Test explosion')).toBeInTheDocument();
  });

  it('renders custom static fallback', () => {
    throwControl.shouldThrow = true;
    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Custom fallback')).toBeInTheDocument();
  });

  it('renders render-prop fallback with error and reset', () => {
    throwControl.shouldThrow = true;
    render(
      <ErrorBoundary fallback={(err, reset) => <button onClick={reset}>{err.message}</button>}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Test explosion')).toBeInTheDocument();
  });

  it('calls onError callback', () => {
    throwControl.shouldThrow = true;
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) }),
    );
  });

  it('resets to render children again after Try again click', () => {
    throwControl.shouldThrow = true;
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    // Disable throwing BEFORE reset so re-render succeeds
    throwControl.shouldThrow = false;
    fireEvent.click(screen.getByText('Try again'));
    expect(screen.getByText('All good')).toBeInTheDocument();
  });
});
