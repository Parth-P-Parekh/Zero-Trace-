/** A 6px filled dot — the only permitted use of signal colour outside a soft badge. */
export interface StatusDotProps {
  /** @default 'idle' */
  state?: 'clean' | 'redacted' | 'blocked' | 'info' | 'idle' | 'ink';
  /** Diameter in px. Keep at 6–10. @default 6 */
  size?: number;
  /** Slow opacity pulse for an active stream. @default false */
  live?: boolean;
  style?: React.CSSProperties;
}
export declare function StatusDot(props: StatusDotProps): JSX.Element;
