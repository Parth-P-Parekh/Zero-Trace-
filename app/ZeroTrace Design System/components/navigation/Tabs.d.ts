/**
 * Section switch inside a view. Selected tab is full ink with a 2px ink underline —
 * the only 2px rule in the system besides focus.
 *
 * @startingPoint section="Navigation" subtitle="Tabs, segmented pills, sidebar rail" viewport="700x260"
 */
export interface TabsProps {
  /** Strings, or { value, label, count } for counted tabs. */
  items?: Array<string | { value: string; label: string; count?: number }>;
  value?: string;
  onChange?: (value: string) => void;
  onDark?: boolean;
  style?: React.CSSProperties;
}
export declare function Tabs(props: TabsProps): JSX.Element;
