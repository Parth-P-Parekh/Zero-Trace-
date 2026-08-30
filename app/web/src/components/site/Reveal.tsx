'use client';

/**
 * The scroll reveal, and the only piece of machinery the marketing page adds.
 *
 * The design system has one authored gesture - ink arriving left to right -
 * and this hands that gesture to the whole scroll instead of inventing a
 * second one for it. `sweep` uncovers left to right, `rule` draws a hairline
 * from its left edge, and the default fades and rises 8px. Everything below
 * that is the design system's own motion budget: no bounce, no overshoot, no
 * spring, nothing longer than `--d-drain`.
 *
 * It fires once per element. A section that re-animates every time it crosses
 * the viewport is a distraction on the second pass and a nuisance on the
 * fourth, and `prefers-reduced-motion` zeroes the durations in CSS rather than
 * here, so the reduced path is a plain appearance and never a jump.
 */
import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from 'react';

type Variant = 'fade' | 'sweep' | 'rule';

const CLASS: Record<Variant, string> = {
  fade: 'zt-r',
  sweep: 'zt-r-sweep',
  rule: 'zt-r-rule',
};

export function Reveal({
  children,
  variant = 'fade',
  delay = 0,
  as: Tag = 'div',
  className,
  style,
  id,
}: {
  children: ReactNode;
  variant?: Variant;
  /** Stagger index, not milliseconds - the ladder is set once, in CSS. */
  delay?: number;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  id?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;

    // A tall section should start arriving before its top edge is centred, so
    // the reader meets it already legible rather than watching it assemble.
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.01 },
    );

    io.observe(el);
    return () => io.disconnect();
  }, [seen]);

  /**
   * The sweep clips the element to zero width until it arrives, and an element
   * clipped to zero area never reports as intersecting - so the thing that is
   * observed and the thing that is clipped cannot be the same node. The clip
   * moves to an inner block, and the outer keeps its own box, its class and its
   * layout role. Fade and rule do not shrink the box, so they stay on the
   * element itself and nothing that relies on being a grid or flex child is
   * wrapped.
   */
  if (variant === 'sweep') {
    return (
      <Tag ref={ref} id={id} className={className} style={style}>
        <span
          className={`zt-r-sweep${seen ? ' is-in' : ''}`}
          style={{ display: 'block', ['--i' as string]: delay }}
        >
          {children}
        </span>
      </Tag>
    );
  }

  return (
    <Tag
      ref={ref}
      id={id}
      className={[CLASS[variant], seen ? 'is-in' : '', className].filter(Boolean).join(' ')}
      style={{ ...style, ['--i' as string]: delay }}
    >
      {children}
    </Tag>
  );
}

/**
 * A group whose children reveal in sequence. Used where the members are peers
 * - a row list, a stat band - so the eye is given an order to read them in
 * rather than being handed all of them at once.
 */
export function RevealGroup({
  children,
  className,
  style,
  id,
  as: Tag = 'div',
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  id?: string;
  as?: ElementType;
}) {
  const ref = useRef<HTMLElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.01 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen]);

  return (
    <Tag
      ref={ref}
      id={id}
      className={[seen ? 'is-in' : '', className].filter(Boolean).join(' ')}
      style={style}
    >
      {children}
    </Tag>
  );
}

/**
 * A member of a `RevealGroup`. It carries the variant class but not the
 * observer - the group decides when the whole set arrives, and `index` decides
 * the order within it.
 */
export function RevealItem({
  children,
  index = 0,
  variant = 'fade',
  as: Tag = 'div',
  className,
  style,
}: {
  children: ReactNode;
  index?: number;
  variant?: Variant;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <Tag
      className={[CLASS[variant], className].filter(Boolean).join(' ')}
      style={{ ...style, ['--i' as string]: index }}
    >
      {children}
    </Tag>
  );
}
