/**
 * An inline redaction block standing in for a detected value — the visual form
 * of what ZeroTrace does to a payload.
 */
export interface RedactionMaskProps {
  /** The original string. Used only for length and for the revealed state; never rendered when masked. */
  children?: React.ReactNode;
  /** Explicit character count when the original value isn't available. */
  length?: number;
  /** Finding type, e.g. 'us_ssn', 'api_key'. Shown inside the block when it fits; always in the tooltip. */
  type?: string;
  /** Show the original value instead of the mask. @default false */
  revealed?: boolean;
  /** Play the 900ms left-to-right sweep as the mask fills in. @default false */
  animate?: boolean;
  /** Ink the mask resolves against. @default 'ink' */
  tone?: 'ink' | 'inverse';
  style?: React.CSSProperties;
}
export declare function RedactionMask(props: RedactionMaskProps): JSX.Element;
