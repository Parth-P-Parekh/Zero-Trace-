/** Nothing-here state. Says what is absent and the one next step that fills it. */
export interface EmptyStateProps {
  /** Lucide name, rendered at 22px and ramp .22. @default 'scan-line' */
  icon?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Usually a single Button. */
  action?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function EmptyState(props: EmptyStateProps): JSX.Element;
