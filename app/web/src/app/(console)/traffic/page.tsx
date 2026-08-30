import { TrafficView } from '@/components/views/TrafficView';
import { sampleFeed } from '@/lib/benchmark';

export const metadata = { title: 'Traffic · ZeroTrace' };

export default function TrafficPage() {
  return <TrafficView rows={sampleFeed()} />;
}
