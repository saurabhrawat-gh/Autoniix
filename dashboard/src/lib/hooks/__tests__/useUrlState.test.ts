import { renderHook, act } from '@testing-library/react';
import { useUrlState } from '../useUrlState';

const { mockReplace, stableRouter } = vi.hoisted(() => {
  const mockReplace = vi.fn();
  return { mockReplace, stableRouter: { replace: mockReplace } };
});
let mockRawParam: string | null = null;

vi.mock('next/navigation', () => ({
  useRouter: () => stableRouter,
  usePathname: () => '/test-page',
  useSearchParams: () => ({
    get: (_key: string) => mockRawParam,
    toString: () => (mockRawParam ? `tab=${mockRawParam}` : ''),
  }),
}));

describe('useUrlState', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockRawParam = null;
  });

  it('returns defaultValue when URL param is absent', () => {
    const { result } = renderHook(() => useUrlState('tab', { defaultValue: 'all' }));
    expect(result.current[0]).toBe('all');
  });

  it('reads initial value from URL param', () => {
    mockRawParam = 'active';
    const { result } = renderHook(() => useUrlState('tab', { defaultValue: 'all' }));
    expect(result.current[0]).toBe('active');
  });

  it('calls router.replace with encoded param on setValue', () => {
    const { result } = renderHook(() => useUrlState('tab', { defaultValue: 'all' }));
    act(() => result.current[1]('active'));
    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining('tab=active'),
      { scroll: false },
    );
  });

  it('omits param from URL when value equals defaultValue', () => {
    mockRawParam = 'active';
    const { result } = renderHook(() => useUrlState('tab', { defaultValue: 'all' }));
    act(() => result.current[1]('all'));
    const [url] = mockReplace.mock.calls[0] as [string, unknown];
    expect(url).not.toContain('tab=');
  });

  it('omits param from URL when value is null', () => {
    const { result } = renderHook(() =>
      useUrlState<string | null>('filter', { defaultValue: null }),
    );
    act(() => result.current[1](null));
    const [url] = mockReplace.mock.calls[0] as [string, unknown];
    expect(url).not.toContain('filter=');
  });

  it('uses custom serialize function', () => {
    const { result } = renderHook(() =>
      useUrlState<number>('page', {
        defaultValue: 1,
        serialize: (v) => (v === 1 ? null : String(v)),
        deserialize: (raw) => (raw ? Number(raw) : 1),
      }),
    );
    act(() => result.current[1](5));
    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining('page=5'),
      { scroll: false },
    );
  });

  it('uses custom deserialize function to read URL param', () => {
    mockRawParam = '3';
    const { result } = renderHook(() =>
      useUrlState<number>('page', {
        defaultValue: 1,
        deserialize: (raw) => (raw ? Number(raw) : 1),
      }),
    );
    expect(result.current[0]).toBe(3);
  });

  it('serializing defaultValue omits param from URL', () => {
    const { result } = renderHook(() =>
      useUrlState<number>('page', {
        defaultValue: 1,
        serialize: (v) => (v === 1 ? null : String(v)),
        deserialize: (raw) => (raw ? Number(raw) : 1),
      }),
    );
    act(() => result.current[1](1));
    const [url] = mockReplace.mock.calls[0] as [string, unknown];
    expect(url).not.toContain('page=');
  });

  it('setValue works consistently across re-renders', () => {
    const { result, rerender } = renderHook(() => useUrlState('x', { defaultValue: '' }));
    act(() => result.current[1]('hello'));
    expect(mockReplace).toHaveBeenCalledWith('/test-page?x=hello', { scroll: false });
    mockReplace.mockClear();
    rerender();
    act(() => result.current[1]('world'));
    expect(mockReplace).toHaveBeenCalledWith('/test-page?x=world', { scroll: false });
  });
});
