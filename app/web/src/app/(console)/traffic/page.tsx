import { TrafficView } from '@/components/views/TrafficView';
import { sampleFeed } from '@/lib/benchmark';

export const metadata = { title: 'Requests · ZeroTrace' };

export default function TrafficPage() {
  return <TrafficView rows={sampleFeed()} />;
}
