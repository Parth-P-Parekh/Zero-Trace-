/** Transient confirmation of something that already happened. Always dark, always one line. */
export interface ToastProps {
  children?: React.ReactNode;
  /** Dot state. @default 'info' */
  status?: 'clean' | 'redacted' | 'blocked' | 'info' | 'idle';
  /** Inline text action, e.g. 'View patch'. */
  action?: string;
  onAction?: () => void;
  onDismiss?: () => void;
  style?: React.CSSProperties;
}
export declare function Toast(props: ToastProps): JSX.Element;
