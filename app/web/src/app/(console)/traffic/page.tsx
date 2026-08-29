import { TrafficView } from '@/components/views/TrafficView';
import { listRequests, trafficSummary } from '@/lib/client';

export const metadata = { title: 'Traffic · ZeroTrace' };

export default function TrafficPage() {
  return <TrafficView rows={listRequests()} summary={trafficSummary()} />;
}
