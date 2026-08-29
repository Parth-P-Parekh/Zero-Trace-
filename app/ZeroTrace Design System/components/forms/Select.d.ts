/** Native select with brand chrome and a chevron-down affordance. */
export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  /** Strings, or { value, label } pairs. */
  options?: Array<string | { value: string; label: string }>;
  size?: 'sm' | 'md';
  style?: React.CSSProperties;
}
export declare function Select(props: SelectProps): JSX.Element;
