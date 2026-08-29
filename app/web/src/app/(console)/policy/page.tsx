import { PolicyView } from '@/components/views/PolicyView';
import { activePolicy, listExceptions, listPolicyVersions } from '@/lib/client';

export const metadata = { title: 'Policy · ZeroTrace' };

export default function PolicyPage() {
  return (
    <PolicyView
      active={activePolicy()}
      versions={listPolicyVersions()}
      exceptions={listExceptions()}
    />
  );
}
