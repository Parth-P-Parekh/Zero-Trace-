import Link from 'next/link';
import { Button, Card, StatusDot, Wordmark } from '@/ds';
import { StubNote } from '@/components/Chrome';
import { getStub } from '@/lib/client';

export const metadata = { title: 'Sign in · ZeroTrace' };

export default function LoginPage() {
  const stub = getStub('identity');

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--paper)' }}>
      <aside
        className="zt-rail"
        style={{
          flex: '0 0 42%', background: 'var(--surface-dark)', padding: '48px 48px 40px',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}
      >
        <Wordmark size={20} tone="inverse" drain />
        <div>
          <p
            style={{
              font: 'var(--w-regular) var(--t-33)/var(--lh-snug) var(--font-core)',
              letterSpacing: 'var(--tr-display)', color: 'var(--ink-inverse)',
              margin: 0, maxWidth: '18ch',
            }}
          >
            Sign in with the directory.{' '}
            <span style={{ color: 'var(--text-on-dark-quiet)' }}>
              ZeroTrace does not hold accounts of its own.
            </span>
          </p>
          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-body)', margin: '20px 0 0', maxWidth: '42ch' }}>
            People come from the enterprise identity provider, services from their workload identity.
            There are no ZeroTrace passwords and no developer-held keys anywhere in the product.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusDot state="clean" size={6} live />
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>gateway live · 4 ms</span>
        </div>
      </aside>

      <main
        style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 32,
        }}
      >
        <div style={{ width: '100%', maxWidth: 380, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card pad={28}>
            <h1 style={{ font: 'var(--type-h3)', margin: '0 0 6px' }}>Sign in</h1>
            <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', margin: '0 0 22px' }}>
              You will be returned here after your provider authenticates you.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Link href="/traffic" style={{ textDecoration: 'none' }}>
                <Button full icon="key-round">Continue with SSO</Button>
              </Link>
              <Link href="/traffic" style={{ textDecoration: 'none' }}>
                <Button full variant="secondary" icon="terminal">Continue with a workload certificate</Button>
              </Link>
            </div>

            <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-quiet)', margin: '22px 0 0' }}>
              Your role and groups come from the directory. Changing what you can read is a change in
              the directory, not here.
            </p>
          </Card>

          <StubNote capability={stub.capability} detail={stub.detail} />

          <p style={{ font: 'var(--type-body-sm)', color: 'var(--text-faint)', margin: 0, textAlign: 'center' }}>
            <Link href="/">Back to zerotrace.dev</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
