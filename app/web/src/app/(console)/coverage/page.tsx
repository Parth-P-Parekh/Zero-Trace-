import { CoverageView } from '@/components/views/CoverageView';
import { getCounterfactual, getCoverage, getLedger, getStub } from '@/lib/client';

export const metadata = { title: 'Coverage · ZeroTrace' };

export default function CoveragePage() {
  return (
    <CoverageView
      report={getCoverage()}
      counterfactual={getCounterfactual()}
      ledger={getLedger()}
      stub={getStub('coverage')}
    />
  );
}
