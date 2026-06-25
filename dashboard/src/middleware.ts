import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_PATHS = new Set([
  '/login',
  '/register',
  '/forgot',
  '/reset',
  '/accept-invite',
]);

const ONBOARDING_PATH = '/onboarding';
const LOGIN_PATH = '/login';
const DASHBOARD_PATH = '/dashboard';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Let Next.js internals, API routes and static assets pass through.
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/fonts') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // `auth_status=1` is a non-HttpOnly cookie set by both the Rust gateway
  // and Python backend to signal that a valid session exists. It is not a
  // security gate (the real auth check is the HttpOnly JWT cookie validated
  // by the gateway), but it is safe to use here for redirect UX.
  const isAuthenticated = request.cookies.has('auth_status');

  const isPublicPath = PUBLIC_PATHS.has(pathname) || PUBLIC_PATHS.has(pathname.replace(/\/$/, ''));
  const isDashboardPath = pathname === DASHBOARD_PATH || pathname.startsWith(`${DASHBOARD_PATH}/`);
  const isOnboardingPath = pathname === ONBOARDING_PATH;
  const isRootPath = pathname === '/';

  // Unauthenticated: redirect to login from protected routes.
  if (!isAuthenticated && (isDashboardPath || isOnboardingPath)) {
    const url = request.nextUrl.clone();
    url.pathname = LOGIN_PATH;
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  // Authenticated: redirect away from auth pages.
  if (isAuthenticated && (isPublicPath || isRootPath)) {
    const url = request.nextUrl.clone();
    url.pathname = DASHBOARD_PATH;
    url.search = '';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.*|.*\\.png$|.*\\.svg$).*)',
  ],
};
