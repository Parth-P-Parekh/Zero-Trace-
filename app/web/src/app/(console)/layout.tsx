import { redirect } from 'next/navigation';
import { ConsoleShell } from '@/components/ConsoleShell';
import { getSession } from '@/lib/auth';
import { run } from '@/lib/benchmark';
import { compact } from '@/lib/format';

/** Every console route reads the session, so none of them can be prerendered. */
export const dynamic = 'force-dynamic';

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  // The gate. It sits in the layout rather than in each page so a route added
  // later is closed by default rather than open by omission.
  const session = await getSession();
  if (!session) redirect('/login');

  // Rail counts come from the run, so the badge beside a destination is the same
  // number the destination opens with. A count that disagrees with its own screen
  // is worse than no count.
  // Policy and Metering carry no count. Every other badge names the thing its screen
  // is a list of; policy's would have been "3 actions used", which is a number nobody
  // asked for sitting where a total belongs.
  const counts = {
    traffic: compact(run.status.total),
    findings: compact(run.outcomes.findings_total),
    detectors: run.detectors.length,
    coverage: Object.keys(run.coverage.harness).length,
  };

  return (
    <ConsoleShell counts={counts} signedInAs={session.sub}>
      {children}
    </ConsoleShell>
  );
}
