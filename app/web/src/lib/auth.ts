/**
 * Console access control.
 *
 * A note on what this is and is not. PROD-01 C22 has actors resolving from the
 * enterprise IdP - OIDC/SAML for people, SPIFFE for services - and the product
 * holds no accounts of its own. That is still the position. What lives here is a
 * **break-glass local admin**: the one credential that opens the console while
 * SSO is stubbed, so the console is not simply open to anyone who knows the URL.
 * It is labelled that way in the interface, and it is the first thing to delete
 * when the directory integration is real.
 *
 * Server-only. Never import this from a client component.
 */
import { createHmac, randomBytes, timingSafeEqual, createHash } from 'node:crypto';
import { cookies } from 'next/headers';

export const SESSION_COOKIE = 'zt_session';
const SESSION_TTL_SECONDS = 60 * 60 * 8; // one working day
const IS_PROD = process.env.NODE_ENV === 'production';

/** Dev-only fallbacks. In production every one of these must come from the environment. */
const DEV_ADMIN_ID = 'admin';
const DEV_ADMIN_PASSWORD = 'zerotrace-demo';
const DEV_SESSION_SECRET = 'zerotrace-dev-session-secret-not-for-production';

export interface AdminConfig {
  id: string;
  password: string;
  secret: string;
  /** True when the credential came from the environment rather than the dev fallback. */
  configured: boolean;
}

/**
 * Resolves the admin credential. In production nothing is defaulted: an
 * unconfigured deployment refuses every sign-in rather than falling back to a
 * shipped password, which is the failure mode that turns a demo credential into
 * a real incident.
 */
export function adminConfig(): AdminConfig | null {
  const id = process.env.ZT_ADMIN_ID;
  const password = process.env.ZT_ADMIN_PASSWORD;
  const secret = process.env.ZT_SESSION_SECRET;

  if (id && password && secret) {
    return { id, password, secret, configured: true };
  }
  if (IS_PROD) return null;

  return {
    id: id || DEV_ADMIN_ID,
    password: password || DEV_ADMIN_PASSWORD,
    secret: secret || DEV_SESSION_SECRET,
    configured: false,
  };
}

/** Whether the console can be opened at all in this deployment. */
export function authAvailable(): boolean {
  return adminConfig() !== null;
}

/** True when the shipped dev credential is in use, so the UI can say so. */
export function usingDemoCredential(): boolean {
  const cfg = adminConfig();
  return cfg !== null && !cfg.configured;
}

function digest(value: string): Buffer {
  return createHash('sha256').update(value, 'utf8').digest();
}

/** Constant-time compare over fixed-length digests, so length never leaks. */
function matches(supplied: string, expected: string): boolean {
  return timingSafeEqual(digest(supplied), digest(expected));
}

function b64url(input: Buffer | string): string {
  return Buffer.from(input).toString('base64url');
}

function sign(payload: string, secret: string): string {
  return createHmac('sha256', secret).update(payload).digest('base64url');
}

export interface Session {
  sub: string;
  exp: number;
}

/** Mints a signed session token. The cookie carries no secret, only a claim and its signature. */
export function mintSession(sub: string, secret: string): string {
  const body: Session = { sub, exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS };
  const payload = b64url(JSON.stringify(body));
  return `${payload}.${sign(payload, secret)}`;
}

export function verifySession(token: string | undefined, secret: string): Session | null {
  if (!token) return null;
  const [payload, signature] = token.split('.');
  if (!payload || !signature) return null;

  const expected = sign(payload, secret);
  if (expected.length !== signature.length) return null;
  if (!timingSafeEqual(Buffer.from(expected), Buffer.from(signature))) return null;

  try {
    const body = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as Session;
    if (typeof body.exp !== 'number' || body.exp * 1000 < Date.now()) return null;
    return body;
  } catch {
    return null;
  }
}

/** Reads and validates the session on the current request. */
export async function getSession(): Promise<Session | null> {
  const cfg = adminConfig();
  if (!cfg) return null;
  const store = await cookies();
  return verifySession(store.get(SESSION_COOKIE)?.value, cfg.secret);
}

// --- Attempt limiting ----------------------------------------------------
// A single admin credential with no limiter is a credential you can guess at
// leisure. In-memory is the right size for a single-node console; a real
// deployment moves this to Redis alongside everything else.

const WINDOW_MS = 60_000;
const MAX_ATTEMPTS = 5;
const attempts = new Map<string, { count: number; first: number }>();

export function attemptAllowed(key: string): boolean {
  const now = Date.now();
  const entry = attempts.get(key);
  if (!entry || now - entry.first > WINDOW_MS) {
    attempts.set(key, { count: 1, first: now });
    return true;
  }
  entry.count += 1;
  return entry.count <= MAX_ATTEMPTS;
}

export function clearAttempts(key: string): void {
  attempts.delete(key);
}

export function secondsUntilReset(key: string): number {
  const entry = attempts.get(key);
  if (!entry) return 0;
  return Math.max(0, Math.ceil((WINDOW_MS - (Date.now() - entry.first)) / 1000));
}

export interface SignInResult {
  ok: boolean;
  /** Names the problem and the recovery, never just "invalid". */
  error?: string;
  retryAfter?: number;
}

export function checkCredential(id: string, password: string): SignInResult {
  const cfg = adminConfig();
  if (!cfg) {
    return {
      ok: false,
      error: 'No admin credential is configured for this deployment. Set ZT_ADMIN_ID, ZT_ADMIN_PASSWORD and ZT_SESSION_SECRET, then restart.',
    };
  }
  // Both compares always run, so a wrong id and a wrong password cost the same.
  const idOk = matches(id, cfg.id);
  const pwOk = matches(password, cfg.password);
  if (!idOk || !pwOk) {
    return { ok: false, error: 'That login ID and password do not match the admin credential.' };
  }
  return { ok: true };
}

export { SESSION_TTL_SECONDS, randomBytes };
