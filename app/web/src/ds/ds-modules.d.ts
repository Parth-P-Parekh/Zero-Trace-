/**
 * The design system ships `.jsx` sources with sibling `.d.ts` files that assume a
 * global `React` namespace. Rather than modify the design system — it is read-only —
 * these imports are declared loose here and re-typed in `index.ts`, where the prop
 * contracts are restated against a real React import.
 */
declare module '@ds/components/*';
