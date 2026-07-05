import { renderHook, act } from '@testing-library/react';
import { usePermissions, hasPermission, invalidatePermissionsCache } from '../usePermissions';

const mockAuthApi = vi.hoisted(() => ({ me: vi.fn() }));

vi.mock('@/lib/api-v2', () => ({ authApi: mockAuthApi }));

const FULL_PERMS = ['content.create', 'jobs.read', 'channels.manage', 'library.read'];

describe('hasPermission (pure function)', () => {
  it('returns true when permission is in list', () => {
    expect(hasPermission(FULL_PERMS, 'jobs.read')).toBe(true);
  });

  it('returns false when permission is absent', () => {
    expect(hasPermission(FULL_PERMS, 'admin.delete')).toBe(false);
  });

  it('returns false for empty permissions array', () => {
    expect(hasPermission([], 'content.create')).toBe(false);
  });

  it('is case-sensitive', () => {
    expect(hasPermission(['Content.Create'], 'content.create')).toBe(false);
  });
});

describe('usePermissions hook', () => {
  beforeEach(() => {
    mockAuthApi.me.mockResolvedValue({
      data: { permissions: FULL_PERMS, role: 'member', global_role: 'user' },
    });
    invalidatePermissionsCache();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('starts in loading state with empty permissions', () => {
    mockAuthApi.me.mockReturnValue(new Promise(() => {}));
    invalidatePermissionsCache();
    const { result } = renderHook(() => usePermissions());
    expect(result.current.loading).toBe(true);
    expect(result.current.permissions).toEqual([]);
  });

  it('resolves permissions after successful load', async () => {
    const { result } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(false);
    expect(result.current.permissions).toEqual(FULL_PERMS);
  });

  it('resolves role and globalRole', async () => {
    const { result } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(result.current.role).toBe('member');
    expect(result.current.globalRole).toBe('user');
  });

  it('hasPermission returns true for granted permission', async () => {
    const { result } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(result.current.hasPermission('channels.manage')).toBe(true);
  });

  it('hasPermission returns false for ungrant permission', async () => {
    const { result } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(result.current.hasPermission('system.superadmin')).toBe(false);
  });

  it('falls back to safe defaults on API error', async () => {
    mockAuthApi.me.mockRejectedValue(new Error('network error'));
    invalidatePermissionsCache();
    const { result } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(result.current.error).toBe(true);
    expect(result.current.loading).toBe(false);
    expect(result.current.permissions).toEqual([]);
    expect(result.current.role).toBe('viewer');
    expect(result.current.globalRole).toBe('user');
  });

  it('multiple hook instances share the same cached state', async () => {
    const { result: r1 } = renderHook(() => usePermissions());
    const { result: r2 } = renderHook(() => usePermissions());
    await act(async () => {});
    expect(r1.current.permissions).toEqual(r2.current.permissions);
    expect(r1.current.permissions).toEqual(FULL_PERMS);
  });
});
