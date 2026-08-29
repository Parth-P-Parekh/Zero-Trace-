/**
 * The primary action control. Ink-filled by default; hover lightens, press
 * darkens, nothing scales.
 *
 * @startingPoint section="Core" subtitle="Ink, outline, ghost and inverse buttons" viewport="700x160"
 */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children?: React.ReactNode;
  /** 'primary' solid ink · 'secondary' hairline outline on white · 'ghost' wash only · 'inverse' paper on dark. @default 'primary' */
  variant?: 'primary' | 'secondary' | 'ghost' | 'inverse';
  /** @default 'md' */
  size?: 'sm' | 'md' | 'lg';
  /** Leading Lucide icon name. */
  icon?: string;
  /** Trailing Lucide icon name — use 'arrow-right' for forward actions. */
  iconEnd?: string;
  /** Fully rounded, per the reference chrome's pill controls. @default false */
  pill?: boolean;
  disabled?: boolean;
  /** Stretch to container width. @default false */
  full?: boolean;
  /** Set on dark surfaces so secondary/ghost invert their washes. @default false */
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function Button(props: ButtonProps): JSX.Element;
