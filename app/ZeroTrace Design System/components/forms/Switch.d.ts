/** Immediate on/off for a live setting — a rule being active, streaming being on. */
export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: React.ReactNode;
  hint?: string;
  checked?: boolean;
  disabled?: boolean;
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function Switch(props: SwitchProps): JSX.Element;
