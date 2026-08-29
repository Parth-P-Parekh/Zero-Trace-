/** Names an unlabelled control or expands a truncated machine value. */
export interface TooltipProps {
  label: React.ReactNode;
  children?: React.ReactNode;
  /** @default 'top' */
  side?: 'top' | 'bottom' | 'left' | 'right';
  /** Render in mono for ids, hashes, full patterns. @default false */
  mono?: boolean;
  style?: React.CSSProperties;
}
export declare function Tooltip(props: TooltipProps): JSX.Element;
