'use client';

/**
 * Typed bridge to the ZeroTrace Design System.
 *
 * This directive is why the bridge exists at all. The design system's components
 * use hooks but carry no `'use client'` of their own, and the folder is
 * read-only — so the boundary is declared here instead. Server components import
 * from `@/ds` and get client components back, and the design system stays
 * untouched.
 *
 * The design system at `app/ZeroTrace Design System/` is read-only. Nothing is
 * copied, wrapped or re-implemented here — these are the real components, given
 * the prop types their `.d.ts` files describe, restated against a real React
 * import so they type-check inside this app.
 *
 * Import components from `@/ds` and never from the design system directly, so
 * there is exactly one place to look when the design system moves.
 */
import type { CSSProperties, ChangeEventHandler, ReactNode, ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, FC } from 'react';

import { Wordmark as WordmarkImpl } from '@ds/components/brand/Wordmark.jsx';
import { RedactionMask as RedactionMaskImpl } from '@ds/components/brand/RedactionMask.jsx';
import { Button as ButtonImpl } from '@ds/components/core/Button.jsx';
import { IconButton as IconButtonImpl } from '@ds/components/core/IconButton.jsx';
import { Icon as IconImpl } from '@ds/components/core/Icon.jsx';
import { Card as CardImpl } from '@ds/components/core/Card.jsx';
import { Badge as BadgeImpl } from '@ds/components/core/Badge.jsx';
import { Tag as TagImpl } from '@ds/components/core/Tag.jsx';
import { Metric as MetricImpl } from '@ds/components/core/Metric.jsx';
import { StatusDot as StatusDotImpl } from '@ds/components/core/StatusDot.jsx';
import { Input as InputImpl } from '@ds/components/forms/Input.jsx';
import { Select as SelectImpl } from '@ds/components/forms/Select.jsx';
import { Checkbox as CheckboxImpl } from '@ds/components/forms/Checkbox.jsx';
import { Switch as SwitchImpl } from '@ds/components/forms/Switch.jsx';
import { Tabs as TabsImpl } from '@ds/components/navigation/Tabs.jsx';
import { SegmentedControl as SegmentedControlImpl } from '@ds/components/navigation/SegmentedControl.jsx';
import { RailItem as RailItemImpl } from '@ds/components/navigation/RailItem.jsx';
import { Dialog as DialogImpl } from '@ds/components/feedback/Dialog.jsx';
import { Toast as ToastImpl } from '@ds/components/feedback/Toast.jsx';
import { Tooltip as TooltipImpl } from '@ds/components/feedback/Tooltip.jsx';
import { EmptyState as EmptyStateImpl } from '@ds/components/feedback/EmptyState.jsx';
import { PayloadView as PayloadViewImpl } from '@ds/components/product/PayloadView.jsx';
import { SweepRow as SweepRowImpl } from '@ds/components/product/SweepRow.jsx';
import { RuleRow as RuleRowImpl } from '@ds/components/product/RuleRow.jsx';

/** The four functional signal inks, plus idle. Every use pairs the dot with a word. */
export type SignalState = 'clean' | 'redacted' | 'blocked' | 'info' | 'idle';

export interface WordmarkProps {
  size?: number;
  tone?: 'ink' | 'inverse' | 'current';
  variant?: 'primary' | 'mono';
  descriptor?: string;
  drain?: boolean;
  clearspace?: boolean;
  style?: CSSProperties;
}

export interface RedactionMaskProps {
  children?: ReactNode;
  length?: number;
  type?: string;
  revealed?: boolean;
  animate?: boolean;
  tone?: 'ink' | 'inverse';
  style?: CSSProperties;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'inverse';
  size?: 'sm' | 'md' | 'lg';
  icon?: string;
  iconEnd?: string;
  pill?: boolean;
  full?: boolean;
  onDark?: boolean;
}

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  name: string;
  label: string;
  size?: number;
  onDark?: boolean;
  active?: boolean;
}

export interface IconProps {
  name: string;
  size?: number;
  style?: CSSProperties;
}

export interface CardProps {
  children?: ReactNode;
  tone?: 'paper' | 'sunken' | 'dark' | 'shell';
  pad?: number;
  radius?: number | string;
  interactive?: boolean;
  style?: CSSProperties;
}

export interface BadgeProps {
  children?: ReactNode;
  status?: SignalState;
  tone?: 'neutral' | 'clean' | 'redacted' | 'blocked' | 'info' | 'ink';
  onDark?: boolean;
  style?: CSSProperties;
}

export interface TagProps {
  children?: ReactNode;
  mono?: boolean;
  removable?: boolean;
  onRemove?: () => void;
  style?: CSSProperties;
}

export interface MetricProps {
  label: string;
  value: ReactNode;
  unit?: string;
  note?: string;
  size?: 'sm' | 'md' | 'lg';
  onDark?: boolean;
  style?: CSSProperties;
}

export interface StatusDotProps {
  state?: SignalState | 'ink';
  size?: number;
  live?: boolean;
  style?: CSSProperties;
}

// `size` is narrowed away from the DOM's numeric attribute on both of these —
// in this system it names a density step, not a character width.
export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'prefix'> {
  label?: string;
  hint?: string;
  error?: string;
  icon?: string;
  mono?: boolean;
  prefix?: string;
  size?: 'sm' | 'md';
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  hint?: string;
  options?: Array<string | { value: string; label: string }>;
  size?: 'sm' | 'md';
}

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: ReactNode;
  hint?: string;
}

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: ReactNode;
  hint?: string;
  onDark?: boolean;
}

export interface TabsProps {
  items?: Array<string | { value: string; label: string; count?: number }>;
  value?: string;
  onChange?: (value: string) => void;
  onDark?: boolean;
  style?: CSSProperties;
}

export interface SegmentedControlProps {
  items?: Array<string | { value: string; label: string; dot?: SignalState }>;
  value?: string;
  onChange?: (value: string) => void;
  size?: 'sm' | 'md';
  floating?: boolean;
  style?: CSSProperties;
}

export interface RailItemProps {
  icon?: string;
  label: ReactNode;
  count?: number | string;
  active?: boolean;
  onClick?: () => void;
  onDark?: boolean;
  style?: CSSProperties;
}

export interface DialogProps {
  open?: boolean;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm?: () => void;
  onCancel?: () => void;
  width?: number;
}

export interface ToastProps {
  children?: ReactNode;
  status?: SignalState;
  action?: string;
  onAction?: () => void;
  onDismiss?: () => void;
  style?: CSSProperties;
}

export interface TooltipProps {
  label: ReactNode;
  children?: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  mono?: boolean;
  style?: CSSProperties;
}

export interface EmptyStateProps {
  icon?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  style?: CSSProperties;
}

/** A payload line is plain text, or a run of text and masked spans. */
export type PayloadLine = Array<string | { mask?: string; length?: number; type?: string }>;

export interface PayloadViewProps {
  id?: string;
  method?: string;
  path?: string;
  model?: string;
  lines?: Array<string | PayloadLine>;
  status?: SignalState;
  latency?: string;
  scanning?: boolean;
  onCopy?: () => void;
  style?: CSSProperties;
}

export interface SweepRowProps {
  time?: string;
  path?: string;
  model?: string;
  findings?: Array<string | { type: string }>;
  status?: 'clean' | 'redacted' | 'blocked' | 'idle';
  latency?: string;
  active?: boolean;
  onClick?: () => void;
  style?: CSSProperties;
}

export interface RuleRowProps {
  name?: ReactNode;
  pattern?: string;
  action?: string;
  hits?: ReactNode;
  active?: boolean;
  onToggle?: ChangeEventHandler<HTMLInputElement>;
  onEdit?: () => void;
  style?: CSSProperties;
}

export const Wordmark = WordmarkImpl as FC<WordmarkProps>;
export const RedactionMask = RedactionMaskImpl as FC<RedactionMaskProps>;
export const Button = ButtonImpl as FC<ButtonProps>;
export const IconButton = IconButtonImpl as FC<IconButtonProps>;
export const Icon = IconImpl as FC<IconProps>;
export const Card = CardImpl as FC<CardProps>;
export const Badge = BadgeImpl as FC<BadgeProps>;
export const Tag = TagImpl as FC<TagProps>;
export const Metric = MetricImpl as FC<MetricProps>;
export const StatusDot = StatusDotImpl as FC<StatusDotProps>;
export const Input = InputImpl as FC<InputProps>;
export const Select = SelectImpl as FC<SelectProps>;
export const Checkbox = CheckboxImpl as FC<CheckboxProps>;
export const Switch = SwitchImpl as FC<SwitchProps>;
export const Tabs = TabsImpl as FC<TabsProps>;
export const SegmentedControl = SegmentedControlImpl as FC<SegmentedControlProps>;
export const RailItem = RailItemImpl as FC<RailItemProps>;
export const Dialog = DialogImpl as FC<DialogProps>;
export const Toast = ToastImpl as FC<ToastProps>;
export const Tooltip = TooltipImpl as FC<TooltipProps>;
export const EmptyState = EmptyStateImpl as FC<EmptyStateProps>;
export const PayloadView = PayloadViewImpl as FC<PayloadViewProps>;
export const SweepRow = SweepRowImpl as FC<SweepRowProps>;
export const RuleRow = RuleRowImpl as FC<RuleRowProps>;
