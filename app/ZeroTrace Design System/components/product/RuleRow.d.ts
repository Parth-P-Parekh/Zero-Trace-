/** One policy rule: what is matched, what happens to it, and whether it is live. */
export interface RuleRowProps {
  /** Sentence-case rule name, e.g. 'no raw card numbers'. */
  name?: React.ReactNode;
  /** Match pattern or detector id, shown as a mono Tag. */
  pattern?: string;
  /** 'Redact' | 'Block' | 'Log only'. @default 'Redact' */
  action?: string;
  /** Mono hit count, e.g. '(27)'. */
  hits?: React.ReactNode;
  /** @default true */
  active?: boolean;
  onToggle?: React.ChangeEventHandler<HTMLInputElement>;
  onEdit?: () => void;
  style?: React.CSSProperties;
}
export declare function RuleRow(props: RuleRowProps): JSX.Element;
