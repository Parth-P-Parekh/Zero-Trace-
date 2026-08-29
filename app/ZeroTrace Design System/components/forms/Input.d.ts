/**
 * Single-line text field. 36px tall, 4px radius, hairline outline that goes to
 * full ink plus a focus ring on focus.
 *
 * @startingPoint section="Forms" subtitle="Inputs, select, checkbox, radio, switch" viewport="700x300"
 */
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  /** Quiet 12px helper under the field. */
  hint?: string;
  /** Replaces hint and turns the outline to --signal-blocked. */
  error?: string;
  /** Leading Lucide icon, e.g. 'search'. */
  icon?: string;
  /** Render the value in IBM Plex Mono — keys, patterns, URLs. @default false */
  mono?: boolean;
  /** Static mono prefix inside the field, e.g. 'https://'. */
  prefix?: string;
  /** @default 'md' */
  size?: 'sm' | 'md';
  style?: React.CSSProperties;
}
export declare function Input(props: InputProps): JSX.Element;
