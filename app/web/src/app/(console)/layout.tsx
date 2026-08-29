import { ConsoleShell } from '@/components/ConsoleShell';
import { listDetectors, listRequests, listExceptions, getCoverage } from '@/lib/client';

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const requests = listRequests();
  const counts = {
    traffic: requests.length,
    findings: requests.reduce((n, r) => n + r.findings.length, 0),
    detectors: listDetectors().filter((d) => d.status === 'active').length,
    policy: listExceptions().length,
    coverage: getCoverage().events.filter((e) => e.verdict === 'direct_egress').length,
  };

  return <ConsoleShell counts={counts}>{children}</ConsoleShell>;
}
