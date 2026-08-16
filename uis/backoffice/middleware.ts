import { NextResponse, type NextRequest } from 'next/server';

/**
 * Routes that do NOT require authentication.
 * The website public site and auth pages remain open.
 */
const PUBLIC_PATHS = ['/login', '/register', '/website', '/api'];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + '/')
  );
}

/**
 * Check if the request carries a valid session cookie.
 */
function hasTokenCookie(request: NextRequest): boolean {
  const cookie = request.cookies.get('nexova_token');
  return !!cookie?.value;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow Next.js internal paths and static assets
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Public paths are always accessible
  if (isPublicPath(pathname)) {
    // If already authenticated and visiting login/register, redirect to home
    if (hasTokenCookie(request) && (pathname === '/login' || pathname === '/register')) {
      return NextResponse.redirect(new URL('/', request.url));
    }
    return NextResponse.next();
  }

  // Protected routes: check for token cookie
  if (!hasTokenCookie(request)) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
