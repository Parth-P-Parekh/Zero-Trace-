import { NextResponse } from 'next/server';
import {
  SESSION_COOKIE, SESSION_TTL_SECONDS, adminConfig, attemptAllowed, checkCredential,
  clearAttempts, mintSession, secondsUntilReset,
} from '@/lib/auth';

export const runtime = 'nodejs';

/** POST /api/session — sign in. */
export async function POST(request: Request) {
  const cfg = adminConfig();

  let id = '';
  let password = '';
  let next = '/traffic';
  try {
    const body = (await request.json()) as { id?: string; password?: string; next?: string };
    id = String(body.id ?? '');
    password = String(body.password ?? '');
    if (typeof body.next === 'string') next = body.next;
  } catch {
    return NextResponse.json({ error: 'Send a JSON body with an id and a password.' }, { status: 400 });
  }

  // Only same-origin paths. An open redirect on a sign-in page is how a
  // credential ends up on someone else's host.
  if (!next.startsWith('/') || next.startsWith('//')) next = '/traffic';

  const key = request.headers.get('x-forwarded-for') ?? 'local';
  if (!attemptAllowed(key)) {
    const retryAfter = secondsUntilReset(key);
    return NextResponse.json(
      { error: `Too many attempts. Try again in ${retryAfter} s.`, retryAfter },
      { status: 429, headers: { 'Retry-After': String(retryAfter) } },
    );
  }

  const result = checkCredential(id, password);
  if (!result.ok || !cfg) {
    return NextResponse.json({ error: result.error }, { status: 401 });
  }

  clearAttempts(key);

  const response = NextResponse.json({ ok: true, next });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: mintSession(cfg.id, cfg.secret),
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_TTL_SECONDS,
  });
  return response;
}

/** DELETE /api/session — sign out. */
export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: SESSION_COOKIE, value: '', httpOnly: true, sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 0,
  });
  return response;
}
