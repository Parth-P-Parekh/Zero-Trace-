/**
 * The outbound LLM payload as ZeroTrace sees it, with detected values masked
 * in place. One per screen — this is the dark focal card.
 *
 * @startingPoint section="Product" subtitle="Payload inspector, sweep rows, rule rows" viewport="700x340"
 */
export type PayloadLine = Array<string | { mask?: string; length?: number; type?: string }>;
export interface PayloadViewProps {
  /** Payload id, shown quiet in mono at the foot, e.g. 'pl_8f3a21c9e04b'. */
  id?: string;
  /** @default 'POST' */
  method?: string;
  /** @default '/v1/chat/completions' */
  path?: string;
  /** Upstream model, shown as a dark Badge. */
  model?: string;
  /** Lines of the payload. Each line is a string or an array of string / mask parts. */
  lines?: Array<string | PayloadLine>;
  /** Result state driving the header dot. @default 'redacted' */
  status?: 'clean' | 'redacted' | 'blocked' | 'info' | 'idle';
  /** Unit-tagged latency string, e.g. '240 ms'. */
  latency?: string;
  /** Run the scanline and mask sweep. @default false */
  scanning?: boolean;
  onCopy?: () => void;
  style?: React.CSSProperties;
}
export declare function PayloadView(props: PayloadViewProps): JSX.Element;
