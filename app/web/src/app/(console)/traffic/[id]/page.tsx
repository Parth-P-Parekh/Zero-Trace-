import { notFound } from 'next/navigation';
import { InspectorView } from '@/components/views/InspectorView';
import { getPayload, getRequest, listRequests } from '@/lib/client';

export function generateStaticParams() {
  return listRequests().map((r) => ({ id: r.id }));
}

export default async function InspectorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const request = getRequest(id);
  if (!request) notFound();
  return <InspectorView request={request} payloads={getPayload(id)} />;
}
