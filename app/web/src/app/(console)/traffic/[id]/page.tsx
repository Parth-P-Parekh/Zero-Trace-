import { notFound } from 'next/navigation';
import { InspectorView } from '@/components/views/InspectorView';
import { sampleById } from '@/lib/benchmark';

// Not prerendered: the console layout gates on the session, so these render per
// request like every other route behind the gate.

export default async function InspectorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const row = sampleById(id);
  if (!row) notFound();
  return <InspectorView row={row} />;
}
