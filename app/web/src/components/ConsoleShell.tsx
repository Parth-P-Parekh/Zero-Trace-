'use client';

/**
 * The console shell, inherited verbatim from the design system's console kit:
 * dark 232px rail, sticky; 56px topbar at 82% paper with the panel blur and an
 * inset bottom hairline.
 *
 * The one extension: the rail is grouped, and the groups are named as questions
 * rather than as subsystems. "Control" and "Assurance" are what the parts are
 * called internally; "How it decides" and "Proof" are what someone opening the
 * console is trying to find out.
 */
import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Badge, Button, IconButton, RailItem, StatusDot, Tooltip, Wordmark } from '@/ds';

type NavItem = { href: string; icon: string; label: string; count?: number | string };
type NavGroup = { label: string; items: NavItem[] };

export interface ConsoleShellProps {
  children: React.ReactNode;
  /** Breadcrumb tail in the topbar. Derived from the route unless given. */
  title?: string;
  counts?: Record<string, number | string>;
  /** Right-hand slot in the topbar for page-level controls. */
  actions?: React.ReactNode;
  /** The signed-in admin, from the session. */
  signedInAs?: string;
}

const ROUTE_TITLES: Array<[string, string]> = [
  ['/traffic', 'Requests'],
  ['/findings', 'What we found'],
  ['/detectors', 'Detection'],
  ['/policy', 'Rules'],
  ['/coverage', 'Coverage'],
  ['/environments', 'Environments'],
  ['/licence', 'Usage'],
  ['/method', 'How it works'],
];

function titleFor(pathname: string): string {
  if (/^\/traffic\/[^/]+$/.test(pathname)) return 'Requests · One request';
  const hit = ROUTE_TITLES.find(([base]) => pathname.startsWith(base));
  return hit ? hit[1] : 'Console';
}

/**
 * Eight destinations under three headings, ordered by the question each answers:
 * what happened, how it decided, and whether any of it can be proved.
 *
 * "What we found" is its own route rather than a tab on Requests, because one
 * request can carry six findings - they are different counts and belong on
 * different screens.
 */
const GROUPS = (counts: Record<string, number | string>): NavGroup[] => [
  {
    label: 'What happened',
    items: [
      { href: '/traffic', icon: 'scan-line', label: 'Requests', count: counts.traffic },
      { href: '/findings', icon: 'eye-off', label: 'What we found', count: counts.findings },
    ],
  },
  {
    label: 'How it decides',
    items: [
      { href: '/detectors', icon: 'activity', label: 'Detection', count: counts.detectors },
      { href: '/policy', icon: 'list-filter', label: 'Rules' },
    ],
  },
  {
    label: 'Proof',
    items: [
      { href: '/coverage', icon: 'shield', label: 'Coverage', count: counts.coverage },
      { href: '/licence', icon: 'file-text', label: 'Usage' },
      { href: '/method', icon: 'book-open', label: 'How it works' },
    ],
  },
];

export function ConsoleShell({
  children, title, counts = {}, actions, signedInAs,
}: ConsoleShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const heading = title ?? titleFor(pathname);
  const [signingOut, setSigningOut] = useState(false);

  const initials = (signedInAs ?? 'admin').slice(0, 2).toUpperCase();

  async function signOut() {
    if (signingOut) return;
    setSigningOut(true);
    await fetch('/api/session', { method: 'DELETE' });
    router.push('/login');
    router.refresh();
  }

  return (
    <div className="zt-shell" style={{ display: 'flex', minHeight: '100vh', background: 'var(--paper)' }}>
      <aside
        className="zt-rail"
        style={{
          position: 'sticky', top: 0, alignSelf: 'flex-start', height: '100vh',
          width: 'var(--rail-w)', flex: '0 0 var(--rail-w)', background: 'var(--surface-dark)',
          display: 'flex', flexDirection: 'column', padding: 12,
        }}
      >
        <div style={{ padding: '6px 10px 20px' }}>
          <Link href="/traffic" aria-label="ZeroTrace console" style={{ textDecoration: 'none' }}>
            <Wordmark size={17} tone="inverse" />
          </Link>
        </div>

        {GROUPS(counts).map((group, gi) => (
          <div key={group.label} className="zt-rail-group" style={{ marginTop: gi === 0 ? 0 : 20 }}>
            <div
              className="zt-eyebrow zt-rail-label"
              style={{ padding: '0 10px 8px', color: 'rgba(242,242,240,0.36)' }}
            >
              {group.label}
            </div>
            <div className="zt-rail-items" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {group.items.map((item) => {
                const [base] = item.href.split('?');
                const active = pathname === base || (base !== '/traffic' && pathname.startsWith(base));
                return (
                  <Link key={item.href} href={item.href} style={{ textDecoration: 'none' }}>
                    <RailItem icon={item.icon} label={item.label} count={item.count} active={active} />
                  </Link>
                );
              })}
            </div>
          </div>
        ))}

        {/* Environments is a destination, not decoration. The two entries carried no
            link before and could not be reached; both now open the comparison, which
            is the only screen where one environment means anything. */}
        <div className="zt-rail-secondary" style={{ marginTop: 20 }}>
          <div className="zt-eyebrow zt-rail-label" style={{ padding: '0 10px 8px', color: 'rgba(242,242,240,0.36)' }}>
            Environments
          </div>
          <div className="zt-rail-items" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {([['production', 'Live', 'acting'], ['staging', 'Test', 'watching']] as const).map(
              ([slug, label, state]) => (
                <Link key={slug} href={`/environments#${slug}`} style={{ textDecoration: 'none' }}>
                  <RailItem
                    icon={slug === 'production' ? 'shield' : 'activity'}
                    label={label}
                    count={state}
                    active={pathname.startsWith('/environments')}
                  />
                </Link>
              ),
            )}
          </div>
        </div>

        <div className="zt-rail-secondary" style={{ flex: 1 }} />

        <div
          className="zt-rail-secondary"
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '10px 10px 6px',
            boxShadow: 'inset 0 1px 0 var(--border-on-dark)',
          }}
        >
          <StatusDot state="clean" size={6} live />
          <span className="zt-mono-sm" style={{ color: 'var(--text-on-dark-quiet)' }}>
            protection on
          </span>
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <header
          style={{
            position: 'sticky', top: 0, zIndex: 20, height: 'var(--topbar-h)', display: 'flex',
            alignItems: 'center', gap: 12, padding: '0 24px',
            background: 'rgba(232,232,230,0.82)', backdropFilter: 'var(--blur-panel)',
            boxShadow: 'inset 0 -1px 0 var(--border-hairline)',
          }}
        >
          <span className="zt-eyebrow">ZeroTrace</span>
          <span style={{ color: 'var(--text-faint)' }}>·</span>
          <span style={{ font: 'var(--type-body-sm)' }}>{heading}</span>
          <span style={{ flex: 1 }} />
          {actions}
          <Badge status="clean" tone="clean">Protecting</Badge>
          <Tooltip label="Documentation">
            <IconButton name="book-open" label="Documentation" />
          </Tooltip>
          <Tooltip label={`Signed in as ${signedInAs ?? 'admin'}`} mono>
            <div
              style={{
                width: 26, height: 26, borderRadius: '50%', background: 'var(--ink)',
                color: 'var(--ink-inverse)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', font: 'var(--type-eyebrow)',
              }}
            >
              {initials}
            </div>
          </Tooltip>
          <Button size="sm" variant="ghost" onClick={signOut} disabled={signingOut}>
            {signingOut ? 'Signing out' : 'Sign out'}
          </Button>
        </header>

        <div className="zt-content" style={{ padding: '24px 24px 64px', flex: 1 }}>{children}</div>
      </main>
    </div>
  );
}
