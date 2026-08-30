'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, StatusDot } from '@/ds';

export function LoginForm({
  next,
  available,
}: {
  /** Where to land after signing in. Same-origin paths only; the route handler re-checks. */
  next: string;
  /** False when the deployment has no admin credential configured at all. */
  available: boolean;
}) {
  const router = useRouter();
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);

    try {
      const response = await fetch('/api/session', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id, password, next }),
      });
      const body = (await response.json()) as { ok?: boolean; next?: string; error?: string };

      if (!response.ok || !body.ok) {
        setError(body.error ?? 'Sign-in failed. Try again.');
        setPassword('');
        setBusy(false);
        return;
      }
      // Keep the button busy through the transition — the console is a full
      // navigation and a button that springs back reads as a failure.
      router.push(body.next ?? next);
      router.refresh();
    } catch {
      setError('The console did not respond. Check that the server is running, then try again.');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Input
          label="Login ID"
          value={id}
          onChange={(e) => setId(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          mono
          disabled={!available || busy}
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          disabled={!available || busy}
          required
        />
      </div>

      {error ? (
        <p
          role="alert"
          style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, margin: '16px 0 0',
            font: 'var(--type-body-sm)', color: 'var(--text-body)',
          }}
        >
          <span style={{ marginTop: 6, flex: '0 0 auto' }}>
            <StatusDot state="blocked" size={6} />
          </span>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 20 }}>
        <Button type="submit" full icon="key-round" disabled={!available || busy}>
          {busy ? 'Opening the console' : 'Sign in'}
        </Button>
      </div>
    </form>
  );
}
