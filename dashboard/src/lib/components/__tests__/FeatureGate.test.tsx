import { render, screen } from '@testing-library/react';
import { FeatureFlagProvider, useFlag } from '../FeatureFlagProvider';
import { FeatureGate } from '../FeatureGate';

const mockFlagsApi = vi.hoisted(() => ({
  list: vi.fn(),
}));

vi.mock('@/lib/api-v2', () => ({
  flagsApi: mockFlagsApi,
}));

function FlagReader({ flag }: { flag: string }) {
  const enabled = useFlag(flag);
  return <div>{enabled ? 'on' : 'off'}</div>;
}

describe('FeatureGate', () => {
  beforeEach(() => {
    mockFlagsApi.list.mockResolvedValue({
      data: [
        { key: 'beta.dashboard', enabled: true, description: '', payload: {} },
        { key: 'beta.off', enabled: false, description: '', payload: {} },
      ],
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('hides children while flags are loading', () => {
    mockFlagsApi.list.mockReturnValue(new Promise(() => {}));
    const { container } = render(
      <FeatureFlagProvider>
        <FeatureGate flag="beta.dashboard">
          <div>gated content</div>
        </FeatureGate>
      </FeatureFlagProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders children when flag is enabled', async () => {
    render(
      <FeatureFlagProvider>
        <FeatureGate flag="beta.dashboard">
          <div>gated content</div>
        </FeatureGate>
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('gated content')).toBeInTheDocument();
  });

  it('renders fallback when flag is disabled', async () => {
    render(
      <FeatureFlagProvider>
        <FeatureGate flag="beta.off" fallback={<div>fallback shown</div>}>
          <div>gated content</div>
        </FeatureGate>
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('fallback shown')).toBeInTheDocument();
    expect(screen.queryByText('gated content')).not.toBeInTheDocument();
  });

  it('renders fallback for unknown flag (defaults false)', async () => {
    render(
      <FeatureFlagProvider>
        <FeatureGate flag="does.not.exist" fallback={<div>fallback</div>}>
          <div>hidden</div>
        </FeatureGate>
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('fallback')).toBeInTheDocument();
  });

  it('useFlag returns correct boolean for known flags', async () => {
    render(
      <FeatureFlagProvider>
        <FlagReader flag="beta.dashboard" />
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('on')).toBeInTheDocument();
  });

  it('useFlag returns false for unknown flag', async () => {
    render(
      <FeatureFlagProvider>
        <FlagReader flag="unknown.flag" />
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('off')).toBeInTheDocument();
  });

  it('useFlag returns false when API fails', async () => {
    mockFlagsApi.list.mockRejectedValue(new Error('network error'));
    render(
      <FeatureFlagProvider>
        <FlagReader flag="beta.dashboard" />
      </FeatureFlagProvider>,
    );
    expect(await screen.findByText('off')).toBeInTheDocument();
  });
});
