/**
 * The ZeroTrace wordmark: ZEROTRACE in Inter 400 caps at +0.04em, ink draining
 * left to right across the fixed nine-stop opacity ramp.
 *
 * @startingPoint section="Brand" subtitle="Wordmark, lockup and mono fallback" viewport="700x180"
 */
export interface WordmarkProps {
  /** Font size in px. Below 13px the mono fallback is forced (sheet §04). @default 24 */
  size?: number;
  /** Which ink the ramp resolves against. @default 'ink' */
  tone?: 'ink' | 'inverse' | 'current';
  /** 'mono' renders every letter at full density — one-colour, small, or uncontrolled repro. @default 'primary' */
  variant?: 'primary' | 'mono';
  /** Descriptor lockup text, e.g. "payload sweeper". Rendered as 12px caps in --muted. */
  descriptor?: string;
  /** Play the left-to-right drain on mount (--d-drain). @default false */
  drain?: boolean;
  /** Pad by 0.6 x cap height per sheet §03. @default false */
  clearspace?: boolean;
  style?: React.CSSProperties;
}
export declare function Wordmark(props: WordmarkProps): JSX.Element;
