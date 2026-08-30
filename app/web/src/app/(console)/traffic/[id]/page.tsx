import { notFound } from 'next/navigation';
import { InspectorView } from '@/components/views/InspectorView';
import { getPayload, getRequest } from '@/lib/client';

// Not prerendered: the console layout gates on the session, so these render per
// request like every other route behind the gate.

export default async function InspectorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const request = getRequest(id);
  if (!request) notFound();
  return <InspectorView request={request} payloads={getPayload(id)} />;
}
