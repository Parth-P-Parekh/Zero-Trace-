'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button, Wordmark } from '@/ds';
import { SHELL } from './Shared';

const NAV = [
  ['problem', 'Problem'],
  ['gaps', 'Gaps'],
  ['solution', 'Solution'],
  ['who', 'Who'],
  ['gtm', 'Market'],
  ['pricing', 'Pricing'],
];

/**
 * Sticky nav with a 1px scroll rule beneath it.
 *
 * The page is a pitch told across eight sections, and a reader who has scrolled
 * for two minutes deserves to know how much argument is left. The rule is
 * ink-on-ramp at 1px, which is the quietest wayfinding device the system allows
 * and the only one that does not compete with the payload widget.
 */
export function SiteNav() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0);
      });
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <header
      style={{
        position: 'sticky', top: 0, zIndex: 30, background: 'rgba(232,232,230,0.82)',
        backdropFilter: 'var(--blur-panel)',
      }}
    >
      <nav style={{ ...SHELL, height: 64, display: 'flex', alignItems: 'center', gap: 28 }}>
        <Link href="/" aria-label="ZeroTrace" style={{ textDecoration: 'none', display: 'inline-flex' }}>
          <Wordmark size={16} />
        </Link>
        <span style={{ flex: 1 }} />
        <div className="zt-nav-links" style={{ display: 'flex', gap: 22 }}>
          {NAV.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              style={{
                font: 'var(--type-body-sm)', textDecoration: 'none', color: 'var(--text-quiet)',
                transition: 'color var(--d-fast) var(--ease-out)',
              }}
            >
              {label}
            </a>
          ))}
        </div>
        <Link href="/login" style={{ textDecoration: 'none' }}>
          <Button size="sm" variant="secondary" pill>Sign in</Button>
        </Link>
      </nav>
      <div style={{ height: 1, background: 'var(--border-hairline)' }}>
        <div
          style={{
            height: 1, width: `${progress * 100}%`, background: 'var(--ink)',
            transition: 'width 80ms linear',
          }}
        />
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer style={{ background: 'var(--surface-dark)' }}>
      <div
        style={{
          ...SHELL, paddingTop: 56, paddingBottom: 64, display: 'flex',
          alignItems: 'flex-start', justifyContent: 'space-between', gap: 40, flexWrap: 'wrap',
        }}
      >
        <div>
          <Wordmark size={15} tone="inverse" descriptor="egress firewall for AI traffic" />
        </div>
        <div style={{ display: 'flex', gap: 56, flexWrap: 'wrap' }}>
          <FooterCol title="Product" links={['Console', 'Architecture', 'Evidence ledger', 'Detection pack']} />
          <FooterCol title="Deploy" links={['In your VPC', 'Air-gapped', 'Sovereign cloud']} />
          <FooterCol title="Public sector" links={['Exposure audit', 'DPDP readiness', 'GeM and STQC']} />
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 14 }}>
        {title}
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 9 }}>
        {links.map((l) => (
          <li key={l} style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-quiet)' }}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
