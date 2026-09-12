# SmartSharing

An interactive digital-asset marketplace concept and research report for smartsharing.in.

## Experience

- `/`: Creator asset discovery, search and category filters, session bookmarks, license options, illustrative payout splits, demo receipts and session-only listing drafts.
- `/research`: Detailed product assessment, four-concept comparison, competitor evidence, Hedera architecture, access-control limitations, India-specific diligence boundaries, launch experiments and 17 source references.
- Three.js sculpture with drag rotation, pause, reset, reduced-motion support, viewport-aware rendering and a raster fallback.
- Generated original artwork lives in `public/art/`.

## Scope

All marketplace creators, assets, prices and product specifications are illustrative. No real asset is delivered and no legal license is issued. No payment provider, wallet, live Hedera contract, durable backend, authentication, or upload workflow is connected. State is intentionally limited to the current browser session and clears on reload. No custom domain is configured.

The research was reviewed on 12 September 2026. Scenario inputs and validation milestones are assumptions. Current India-specific legal classification and detailed tax treatment remain open diligence items. The FIU register's 2026 guideline update was located but the full updated PDF could not be extracted; historical guidance is labeled as background.

## Validation

- Production build passed.
- TypeScript check passed.
- Local artwork paths and report anchor targets checked.
- Base unit economics checked: ₹999 order value produces −₹28.59 contribution at 3%, or ₹61.32 at 12%, under the disclosed assumptions.
- Browser visual and end-to-end QA was not run in this environment.
- Optional WebMCP tools expose search and asset-preview staging through the same UI state. Feature-detected registration is cleaned up with AbortSignal. Runtime WebMCP validation was unavailable because no permitted supported browser context was used.

## Development

Use the existing pnpm lockfile. Framework build and scripts are provided by the Sites Vinext starter. The checkout-local Sites execution profile controls compatible build and preview commands. The canonical project identity is in `.openai/hosting.json`.
