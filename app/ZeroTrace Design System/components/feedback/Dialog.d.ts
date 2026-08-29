/**
 * Modal confirm or short form. Scrim is ink at .36; the panel fades up 6px in 200ms.
 *
 * @startingPoint section="Feedback" subtitle="Dialog, toast, tooltip, empty state" viewport="700x300"
 */
export interface DialogProps {
  open?: boolean;
  title?: React.ReactNode;
  /** One or two sentences saying what will happen and what won't. */
  description?: React.ReactNode;
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Tints only the confirm button with --signal-blocked. @default false */
  destructive?: boolean;
  onConfirm?: () => void;
  onCancel?: () => void;
  /** Panel width in px. @default 440 */
  width?: number;
}
export declare function Dialog(props: DialogProps): JSX.Element | null;
