import Link from 'next/link';
import { redirect } from 'next/navigation';
import { Card, StatusDot, Wordmark } from '@/ds';
import { StubNote } from '@/components/Chrome';
import { LoginForm } from '@/components/LoginForm';
import { authAvailable, getSession, usingDemoCredential } from '@/lib/auth';

export const metadata = { title: 'Sign in · ZeroTrace' };
export const dynamic = 'force-dynamic';

function safeNext(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/traffic';
  return raw;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const next = safeNext(params.next);

  // Already signed in — no reason to make anyone type it twice.
  if (await getSession()) redirect(next);

  const available = authAvailable();
  const demo = usingDemoCredential();

  return (
    <div className="zt-login" style={{ display: 'flex', minHeight: '100vh', background: 'var(--paper)' }}>
      <aside
        className="zt-rail zt-login-aside"
        style={{
          flex: '0 0 42%', background: 'var(--surface-dark)', padding: '48px 48px 40px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}
      >
        <Wordmark size={20} tone="inverse" drain />
        <div>
          <p
            style={{
              font: 'var(--w-regular) clamp(24px, 2.6vw, 33px)/var(--lh-snug) var(--font-core)',
              letterSpacing: 'var(--tr-display)', color: 'var(--ink-inverse)',
              margin: 0, maxWidth: '19ch',
            }}
          >
            The console is closed by default.{' '}
            <span style={{ color: 'var(--text-on-dark-quiet)' }}>
              Nothing in it is readable without signing in.
            </span>
          </p>
          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', margin: '20px 0 0', maxWidth: '42ch' }}>
            In a deployed ZeroTrace, people arrive from the enterprise identity provider and services
            from their workload identity. While that integration is stubbed, one local admin
            credential opens the console.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusDot state="clean" size={6} live />
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>gateway live · 4 ms</span>
        </div>
      </aside>

      <main
        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}
      >
        <div style={{ width: '100%', maxWidth: 400, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card pad={28}>
            <h1 style={{ font: 'var(--type-h3)', margin: '0 0 6px' }}>Administrator sign-in</h1>
            <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', margin: '0 0 22px' }}>
              This credential is the only way in while single sign-on is stubbed.
            </p>

            <LoginForm next={next} available={available} />
          </Card>

          {!available ? (
            <StubNote
              capability="Sign-in"
              detail="Set ZT_ADMIN_ID, ZT_ADMIN_PASSWORD and ZT_SESSION_SECRET in the environment and restart. Until then nothing opens the console."
            />
          ) : demo ? (
            <StubNote
              capability="Single sign-on"
              detail="The console is opening on the shipped development credential — admin / zerotrace-demo. Override it with ZT_ADMIN_ID and ZT_ADMIN_PASSWORD before this runs anywhere real."
            />
          ) : (
            <StubNote
              capability="Single sign-on"
              detail="Access runs on a local admin credential until OIDC and SCIM land, and this page is the first thing that changes when they do."
            />
          )}

          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)', margin: 0, textAlign: 'center' }}>
            <Link href="/">Back to zerotrace.dev</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
