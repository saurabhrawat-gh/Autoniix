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

  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/fonts') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  const isAuthenticated = request.cookies.has('auth_status');

  const isPublicPath = PUBLIC_PATHS.has(pathname) || PUBLIC_PATHS.has(pathname.replace(/\/$/, ''));
  const isDashboardPath = pathname === DASHBOARD_PATH || pathname.startsWith(`${DASHBOARD_PATH}/`);
  const isOnboardingPath = pathname === ONBOARDING_PATH;
  const isRootPath = pathname === '/';

  if (!isAuthenticated && (isDashboardPath || isOnboardingPath)) {
    const url = request.nextUrl.clone();
    url.pathname = LOGIN_PATH;
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

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
