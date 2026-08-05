import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { _apiError, isLoggedIn, setToken, clearToken } from '../client';

describe('_apiError', () => {
  it('uses string detail as message', () => {
    const err = _apiError(400, { detail: 'bad_request' });
    expect(err.message).toBe('bad_request');
    expect(err.status).toBe(400);
  });

  it('uses detail.message when detail is an object', () => {
    const err = _apiError(422, { detail: { code: 'invalid_email', message: 'Email is invalid' } });
    expect(err.message).toBe('Email is invalid');
    expect(err.code).toBe('invalid_email');
    expect(err.status).toBe(422);
  });

  it('falls back to detail.code when message absent', () => {
    const err = _apiError(422, { detail: { code: 'no_message' } });
    expect(err.message).toBe('no_message');
  });

  it('falls back to error field', () => {
    const err = _apiError(503, { error: 'service_unavailable' });
    expect(err.message).toBe('service_unavailable');
  });

  it('falls back to HTTP status string', () => {
    const err = _apiError(500, {});
    expect(err.message).toBe('HTTP 500');
    expect(err.status).toBe(500);
  });

  it('attaches structured detail on error', () => {
    const err = _apiError(422, { detail: { code: 'err', message: 'oops' } });
    expect(err.detail).toEqual({ code: 'err', message: 'oops' });
  });

  it('handles null/undefined body gracefully', () => {
    const err = _apiError(500, null);
    expect(err.message).toBe('HTTP 500');
    expect(err.status).toBe(500);
  });
});

describe('isLoggedIn', () => {
  it('returns false when auth_status cookie absent', () => {
    Object.defineProperty(document, 'cookie', { value: '', configurable: true, writable: true });
    expect(isLoggedIn()).toBe(false);
  });

  it('returns true when auth_status=1 cookie present', () => {
    Object.defineProperty(document, 'cookie', { value: 'auth_status=1', configurable: true, writable: true });
    expect(isLoggedIn()).toBe(true);
  });

  it('returns false when auth_status has different value', () => {
    Object.defineProperty(document, 'cookie', { value: 'auth_status=0', configurable: true, writable: true });
    expect(isLoggedIn()).toBe(false);
  });
});

describe('setToken / clearToken', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('stores token in localStorage', () => {
    setToken('tok123');
    expect(localStorage.getItem('dashboard_token')).toBe('tok123');
  });

  it('clearToken removes token', () => {
    setToken('tok123');
    clearToken();
    expect(localStorage.getItem('dashboard_token')).toBeNull();
  });

  it('stores expiry timestamp when expiresIn provided', () => {
    const before = Date.now();
    setToken('tok', 3600);
    const stored = Number(localStorage.getItem('dashboard_token_expires'));
    expect(stored).toBeGreaterThanOrEqual(before + 3_600_000);
    expect(stored).toBeLessThan(before + 3_601_000);
  });

  it('clearToken also removes expires key', () => {
    setToken('tok', 3600);
    clearToken();
    expect(localStorage.getItem('dashboard_token_expires')).toBeNull();
  });

  it('calling setToken twice overwrites with latest token', () => {
    setToken('first');
    setToken('second');
    expect(localStorage.getItem('dashboard_token')).toBe('second');
  });
});
