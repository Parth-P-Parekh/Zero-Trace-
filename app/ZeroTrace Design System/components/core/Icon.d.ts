/** A Lucide glyph, masked to currentColor. Never coloured independently of its text. */
export interface IconProps {
  /** Lucide icon name, kebab-case, e.g. 'scan-line', 'eye-off', 'key-round'. */
  name: string;
  /** Box size in px. 14 inside pills, 16 in UI, 18 on rail items. @default 16 */
  size?: number;
  style?: React.CSSProperties;
}
export declare function Icon(props: IconProps): JSX.Element;
