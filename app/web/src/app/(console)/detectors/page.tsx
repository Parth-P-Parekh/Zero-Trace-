import { DetectorsView } from '@/components/views/DetectorsView';
import { escalationCurve, listDetectors } from '@/lib/client';

export const metadata = { title: 'Detectors · ZeroTrace' };

export default function DetectorsPage() {
  return <DetectorsView detectors={listDetectors()} curve={escalationCurve()} />;
}
