import { CoverageView } from '@/components/views/CoverageView';
import { getCounterfactual, getCoverage, getHarnessCoverage, getLedger, getStub } from '@/lib/client';

export const metadata = { title: 'Coverage · ZeroTrace' };

export default async function CoveragePage() {
  const harnessCoverage = await getHarnessCoverage();
  return (
    <CoverageView
      report={getCoverage()}
      harnessCoverage={harnessCoverage}
      counterfactual={getCounterfactual()}
      ledger={getLedger()}
      stub={getStub('coverage')}
    />
  );
}
