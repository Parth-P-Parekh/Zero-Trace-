'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button, Wordmark } from '@/ds';
import { SHELL } from './Shared';

const NAV = [
  ['problem', 'Problem'],
  ['gaps', 'Gaps'],
  ['solution', 'Product'],
  ['who', 'Who buys it'],
  ['gtm', 'Go to market'],
  ['moat', 'Moat'],
  ['pricing', 'Pricing'],
];

/**
 * Sticky nav with a 1px scroll rule beneath it, and the section the reader is
 * actually in held at full ink.
 *
 * The page is a pitch told across eight sections, and a reader who has scrolled
 * for two minutes deserves to know both how much argument is left and which
 * part of it they are inside. The rule is ink-on-ramp at 1px, which is the
 * quietest wayfinding device the system allows and the only one that does not
 * compete with the payload widget.
 */
export function SiteNav() {
  const [progress, setProgress] = useState(0);
  const [active, setActive] = useState<string>('');

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

  /* The band the reader is reading is the one crossing the upper third of the
     viewport - not the one merely visible, which on a tall section is the one
     they finished a screen ago. */
  useEffect(() => {
    const sections = NAV.map(([id]) => document.getElementById(id)).filter(
      (el): el is HTMLElement => Boolean(el),
    );
    if (!sections.length) return;

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id);
        });
      },
      { rootMargin: '-64px 0px -66% 0px', threshold: 0 },
    );

    sections.forEach((el) => io.observe(el));
    return () => io.disconnect();
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
        <div className="zt-nav-links" style={{ display: 'flex', gap: 20 }}>
          {NAV.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className="zt-nav-link"
              data-active={active === id}
              aria-current={active === id ? 'true' : undefined}
              style={{
                font: 'var(--type-body-sm)', textDecoration: 'none', color: 'var(--text-quiet)',
                transition: 'color var(--d-fast) var(--ease-out)', whiteSpace: 'nowrap',
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
    <footer style={{ background: 'var(--surface-dark)' }} className="zt-on-dark">
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
          <FooterCol
            title="Public sector"
            links={[
              ['Exposure run, 30 days', undefined],
              ['DPDP Rules 2025', 'https://www.meity.gov.in/data-protection-framework'],
              ['GFR 2017, Rules 154–155', 'https://doe.gov.in/general-financial-rules'],
              ['STQC and CERT-In', 'https://www.stqc.gov.in/'],
            ]}
          />
        </div>
      </div>
    </footer>
  );
}

type FooterLink = string | [string, string | undefined];

function FooterCol({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <div>
      <div className="zt-eyebrow" style={{ color: 'rgba(242,242,240,0.52)', marginBottom: 14 }}>
        {title}
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 9 }}>
        {links.map((l) => {
          const [label, href] = Array.isArray(l) ? l : [l, undefined];
          return (
            <li key={label} style={{ font: 'var(--type-body-sm)', color: 'var(--text-on-dark-quiet)' }}>
              {href ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    textDecoration: 'underline',
                    textDecorationColor: 'rgba(242,242,240,0.22)',
                    textUnderlineOffset: 3,
                  }}
                >
                  {label}
                </a>
              ) : (
                label
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
