import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * The design system lives one level up, outside this app, and is never modified.
 * Turbopack's root is widened to `app/` so its `.jsx` sources compile in place —
 * there is no copy to drift and no build step that can fall behind it.
 */
const APP_ROOT = path.join(here, '..');
const DESIGN_SYSTEM = path.join(APP_ROOT, 'ZeroTrace Design System');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next 16 writes AGENTS.md and CLAUDE.md into the app on first dev run. This
  // repo manages its own agent instructions, so it stays off.
  agentRules: false,
  turbopack: {
    root: APP_ROOT,
    resolveAlias: {
      '@ds': DESIGN_SYSTEM,
    },
  },
  // Kept so `next build --webpack` and any tooling that still uses webpack resolve
  // the design system identically.
  webpack: (config) => {
    config.resolve.alias = { ...config.resolve.alias, '@ds': DESIGN_SYSTEM };
    return config;
  },
};

export default nextConfig;
