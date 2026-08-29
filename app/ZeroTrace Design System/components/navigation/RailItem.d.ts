/** One row in the console's 232px fixed rail. Rest opacity .52, hover .86, active 1.00. */
export interface RailItemProps {
  /** Lucide icon name, 16px. */
  icon?: string;
  label: React.ReactNode;
  /** Trailing mono count. */
  count?: number | string;
  active?: boolean;
  onClick?: () => void;
  /** The rail is dark by default. @default true */
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function RailItem(props: RailItemProps): JSX.Element;
