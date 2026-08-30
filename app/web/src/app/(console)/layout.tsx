import { redirect } from 'next/navigation';
import { ConsoleShell } from '@/components/ConsoleShell';
import { getSession } from '@/lib/auth';
import { listDetectors, listRequests, listExceptions, getCoverage } from '@/lib/client';

/** Every console route reads the session, so none of them can be prerendered. */
export const dynamic = 'force-dynamic';

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  // The gate. It sits in the layout rather than in each page so a route added
  // later is closed by default rather than open by omission.
  const session = await getSession();
  if (!session) redirect('/login');

  const requests = listRequests();
  const counts = {
    traffic: requests.length,
    findings: requests.reduce((n, r) => n + r.findings.length, 0),
    detectors: listDetectors().filter((d) => d.status === 'active').length,
    policy: listExceptions().length,
    coverage: getCoverage().events.filter((e) => e.verdict === 'direct_egress').length,
  };

  return (
    <ConsoleShell counts={counts} signedInAs={session.sub}>
      {children}
    </ConsoleShell>
  );
}
