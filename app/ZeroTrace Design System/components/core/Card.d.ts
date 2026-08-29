/**
 * Surface container. Two species from the reference chrome: paper cards for
 * content, one dark card per screen for the thing that matters most.
 *
 * @startingPoint section="Core" subtitle="Paper, sunken, dark and shell surfaces" viewport="700x280"
 */
export interface CardProps {
  children?: React.ReactNode;
  /** 'paper' white + hairline + sh-2 · 'sunken' no lift · 'dark' near-black, no border · 'shell' outer group container, r20 + sh-4. @default 'paper' */
  tone?: 'paper' | 'sunken' | 'dark' | 'shell';
  /** Padding in px. @default 24 */
  pad?: number;
  /** Override radius; defaults to 12px, or 20px for 'shell'. */
  radius?: number | string;
  /** Lift on hover (sh-2 → sh-3) with no translation. @default false */
  interactive?: boolean;
  style?: React.CSSProperties;
}
export declare function Card(props: CardProps): JSX.Element;
