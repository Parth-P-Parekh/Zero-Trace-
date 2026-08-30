import { SiteNav, SiteFooter } from '@/components/site/SiteChrome';
import { Hero } from '@/components/site/Hero';
import { Problem } from '@/components/site/Problem';
import { Competitors } from '@/components/site/Competitors';
import { Solution } from '@/components/site/Solution';
import { ICP } from '@/components/site/ICP';
import { GTM } from '@/components/site/GTM';
import { Moat } from '@/components/site/Moat';
import { Pricing } from '@/components/site/Pricing';
import { Demo } from '@/components/site/Demo';

/**
 * The description is what a search result and a shared link show, so it carries
 * the headline's own words rather than the framing the page used to open with.
 * It also drops the claim that redacted values come back on the response leg -
 * they do not. Tokens are one-way and there is no restoration path, and a meta
 * tag is a bad place to keep a promise the product does not make.
 */
export const metadata = {
  title: 'ZeroTrace - the simplest firewall for frontier LLMs',
  description:
    'An egress firewall for AI traffic. It sits between your apps and the model, swaps names, ID numbers and card details for stand-ins on the way out, and stops any message carrying a live key. Every decision lands in a tamper-evident record.',
};

/**
 * One page, one argument, told in eight moves.
 *
 * The order is the pitch: why a ban is not a control, why nobody currently
 * sells the answer, what we built and what it measured, whose desk it enters
 * through, the six months that reach that desk, why crossing to us is expensive
 * for anyone else, what it costs and who is allowed to sign for it, and then
 * the proof. Each section hands the next one its premise, so the scroll reads
 * as a case rather than a catalogue.
 *
 * The five-year horizon and the market-size band that used to sit between the
 * moat and the price are gone. Neither was something a reader could act on this
 * quarter, and both were competing with the two sections that are.
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
        <Moat />
        <Pricing />
        <Demo />
      </main>
      <SiteFooter />
    </>
  );
}
