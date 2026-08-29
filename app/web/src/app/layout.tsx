import type { Metadata } from 'next';
import '@ds/styles.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'ZeroTrace',
  description:
    'An enterprise egress firewall for AI traffic. It redacts secrets and personal data out of outbound and inbound model payloads, one way, and logs every decision.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
