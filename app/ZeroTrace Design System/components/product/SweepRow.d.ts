/** One inspected payload in the sweep log. 40px tall, hairline separated, no zebra striping. */
export interface SweepRowProps {
  /** Mono timestamp, e.g. '14:02:11'. */
  time?: string;
  /** Request path, mono. */
  path?: string;
  /** Upstream model name. */
  model?: string;
  /** Finding types, e.g. ['us_ssn','api_key'], or finding objects with a `type` field. Truncates to two plus a +n badge. */
  findings?: Array<string | { type: string }>;
  /** @default 'clean' */
  status?: 'clean' | 'redacted' | 'blocked' | 'idle';
  /** Unit-tagged, e.g. '240 ms'. */
  latency?: string;
  /** Row is the one open in the inspector. @default false */
  active?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function SweepRow(props: SweepRowProps): JSX.Element;
