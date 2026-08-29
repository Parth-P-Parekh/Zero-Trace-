/** A single number with a caps eyebrow. Weight 600 is reserved for these numerals. */
export interface MetricProps {
  /** Caps eyebrow, e.g. 'PAYLOADS SWEPT'. */
  label: string;
  value: React.ReactNode;
  /** Unit suffix, e.g. 'ms', '/s'. Always tag units. */
  unit?: string;
  /** One quiet line under the number. */
  note?: string;
  /** @default 'md' */
  size?: 'sm' | 'md' | 'lg';
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function Metric(props: MetricProps): JSX.Element;
