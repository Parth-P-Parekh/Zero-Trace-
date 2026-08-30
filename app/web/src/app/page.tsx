import { SiteNav, SiteFooter } from '@/components/site/SiteChrome';
import { Hero } from '@/components/site/Hero';
import { Problem } from '@/components/site/Problem';
import { Competitors } from '@/components/site/Competitors';
import { Solution } from '@/components/site/Solution';
import { ICP } from '@/components/site/ICP';
import { GTM } from '@/components/site/GTM';
import { Pricing } from '@/components/site/Pricing';
import { Demo } from '@/components/site/Demo';

export const metadata = {
  title: 'ZeroTrace - an egress firewall for AI traffic',
  description:
    'Government runs on citizen data. AI runs on prompts. ZeroTrace takes citizen data out of the outbound payload, restores it in the response, stops any prompt carrying a credential, and writes a tamper-evident record of every decision.',
};

/**
 * One page, one argument, told in eight moves.
 *
 * The order is the pitch: the contradiction, then why prohibition fails, then
 * why nobody currently sells the answer, then what we built and what cannot be
 * copied, then who buys it, then how we reach them and why they choose us,
 * then what it costs and why it is shaped that way, then the proof. Each
 * section hands the next one its premise, so the scroll reads as a case rather
 * than a catalogue.
 */
export default function SitePage() {
  return (
    <>
      <SiteNav />
      <main>
        <Hero />
        <Problem />
        <Competitors />
        <Solution />
        <ICP />
        <GTM />
        <Pricing />
        <Demo />
      </main>
      <SiteFooter />
    </>
  );
}
