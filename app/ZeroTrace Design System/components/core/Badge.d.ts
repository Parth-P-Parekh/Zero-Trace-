/** Small state pill. The only place signal colour appears as a fill, and only softly. */
export interface BadgeProps {
  children?: React.ReactNode;
  /** Adds a 6px StatusDot before the label. */
  status?: 'clean' | 'redacted' | 'blocked' | 'info' | 'idle';
  /** @default 'neutral' */
  tone?: 'neutral' | 'clean' | 'redacted' | 'blocked' | 'info' | 'ink';
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function Badge(props: BadgeProps): JSX.Element;
