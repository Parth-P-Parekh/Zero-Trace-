/** A bare glyph action — toolbar, row affordance, panel close. Always labelled. */
export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Lucide icon name. */
  name: string;
  /** Accessible label, also the tooltip. Required. */
  label: string;
  /** Square size in px. @default 28 */
  size?: number;
  onDark?: boolean;
  /** Held-open / toggled state. @default false */
  active?: boolean;
  disabled?: boolean;
  style?: React.CSSProperties;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
