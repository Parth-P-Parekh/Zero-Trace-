/** Outlined metadata pill — versions, data types, model names, rule patterns. */
export interface TagProps {
  children?: React.ReactNode;
  /** Set for machine data (patterns, ids, versions) so it renders in IBM Plex Mono. @default false */
  mono?: boolean;
  removable?: boolean;
  onRemove?: () => void;
  style?: React.CSSProperties;
}
export declare function Tag(props: TagProps): JSX.Element;
