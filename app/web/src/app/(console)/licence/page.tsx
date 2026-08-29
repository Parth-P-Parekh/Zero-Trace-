import { LicenceView } from '@/components/views/LicenceView';
import { getLicence, getStub } from '@/lib/client';

export const metadata = { title: 'Licence · ZeroTrace' };

export default function LicencePage() {
  return <LicenceView licence={getLicence()} stub={getStub('billing')} />;
}
