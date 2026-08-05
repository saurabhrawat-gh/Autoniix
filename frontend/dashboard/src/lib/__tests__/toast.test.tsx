import { render, screen, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, useToast } from '../toast';

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: {
      ...actual.motion,
      div: ({ children, layout: _l, initial: _i, animate: _a, exit: _e, transition: _t, ref: _r, ...rest }: any) =>
        <div {...rest}>{children}</div>,
    },
    useAnimate: () => [{ current: document.createElement('div') }, vi.fn()],
    useReducedMotion: () => true,
  };
});

vi.mock('../components/AnimatedCheckmark', () => ({
  AnimatedCheckmark: ({ size }: { size: number }) => <span data-testid="checkmark" data-size={size} />,
}));
vi.mock('../components/CountdownRing', () => ({
  CountdownRing: () => <span data-testid="countdown-ring" />,
}));

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function Trigger({ msg, variant }: { msg: string; variant?: string }) {
  const { showToast } = useToast();
  return (
    <button onClick={() => showToast(msg, (variant as any) ?? 'info')}>show</button>
  );
}

describe('ToastProvider / useToast', () => {
  it('renders toast message after showToast', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger msg="Hello toast" variant="info" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByText('Hello toast')).toBeInTheDocument();
  });

  it('error toast renders with role=alert', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger msg="Something broke" variant="error" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('success toast renders with role=status and AnimatedCheckmark', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger msg="Saved" variant="success" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByTestId('checkmark')).toBeInTheDocument();
  });

  it('info toast renders with role=status', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger msg="FYI" variant="info" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('dismiss button removes the toast', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger msg="Dismiss me" variant="info" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByText('Dismiss me')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument();
  });

  it('renders action button and calls onAct on click', async () => {
    const onAct = vi.fn();
    function TriggerWithAction() {
      const { showToast } = useToast();
      return (
        <button
          onClick={() =>
            showToast('Undo?', { variant: 'info', action: { label: 'Undo', onAct } })
          }
        >
          show
        </button>
      );
    }
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TriggerWithAction />
      </ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'show' }));
    const undoBtn = screen.getByRole('button', { name: 'Undo' });
    expect(undoBtn).toBeInTheDocument();
    await user.click(undoBtn);
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Undo?')).not.toBeInTheDocument();
  });

  it('auto-dismisses after duration elapses', async () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger msg="AutoGone" variant="info" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByText('AutoGone')).toBeInTheDocument();
    act(() => { vi.runAllTimers(); });
    expect(screen.queryByText('AutoGone')).not.toBeInTheDocument();
  });

  it('multiple toasts stack and each has its own dismiss', () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger msg="First" variant="info" />
        <Trigger msg="Second" variant="success" />
      </ToastProvider>,
    );
    const [btn1, btn2] = screen.getAllByRole('button', { name: 'show' });
    fireEvent.click(btn1!);
    fireEvent.click(btn2!);
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();

    const dismissButtons = screen.getAllByRole('button', { name: /dismiss/i });
    fireEvent.click(dismissButtons[0]!);
    expect(screen.queryByText('First')).not.toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('accepts options object (variant + duration:0 means no auto-dismiss)', async () => {
    vi.useFakeTimers();
    function TriggerOpts() {
      const { showToast } = useToast();
      return (
        <button
          onClick={() => showToast('Opts toast', { variant: 'warning', duration: 0 })}
        >
          show
        </button>
      );
    }
    render(
      <ToastProvider>
        <TriggerOpts />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'show' }));
    expect(screen.getByText('Opts toast')).toBeInTheDocument();
    act(() => { vi.runAllTimers(); });
    expect(screen.getByText('Opts toast')).toBeInTheDocument();
  });
});
