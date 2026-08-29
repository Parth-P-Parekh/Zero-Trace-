/** Two-to-four short mutually exclusive choices as a pill capsule. */
export interface SegmentedControlProps {
  /** Strings, or { value, label, dot } to prefix a segment with a StatusDot. */
  items?: Array<string | { value: string; label: string; dot?: 'clean' | 'redacted' | 'blocked' | 'info' | 'idle' }>;
  value?: string;
  onChange?: (value: string) => void;
  /** @default 'md' */
  size?: 'sm' | 'md';
  /** Adds sh-3 so it can float over a dark card, as in the reference chrome. @default false */
  floating?: boolean;
  style?: React.CSSProperties;
}
export declare function SegmentedControl(props: SegmentedControlProps): JSX.Element;
