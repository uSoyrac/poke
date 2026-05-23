# Design bundle — cached locally

These are the relevant source files extracted from the design-bundle URLs
below. Cached here so a fresh agent can read them directly without
re-fetching 3.3 MB gzipped archives.

## URLs (only fetch if you need binary assets — screenshots, etc.)

| Bundle | URL |
|---|---|
| Poker Table | `https://api.anthropic.com/v1/design/h/F_M6HFBVSLnhvl1LEi-r0g?open_file=Poker+Table.html` |
| Style Guide | `https://api.anthropic.com/v1/design/h/zXOGR9AImpY9DLg-rtRoDA?open_file=Style+Guide.html` |

Both bundles return the same project tree; the two open-file params just
hint which file the user had open when they triggered the handoff. The
key files are mirrored here.

## Files in this folder

| File | Purpose |
|---|---|
| `UI_GUIDE.md` | Full design system spec — tokens, type, components, patterns, motion, shortcuts (§ 8 maps to the app's poker action keys), animations, voice & copy, dos and don'ts. **Read this first** for any styling question. |
| `theme.css` | All design tokens (colors, typography, animations, app chrome rules) as the original CSS. Most rules are already ported to `app/ui/theme/dark_flat.qss`; come back here when you need the canonical value of a token. |
| `poker-table.css` | Component-level rules for `.pt`, `.pt-seat`, `.pt-felt`, `.pt-pot`, `.pt-bet`, action chips, dealer button. Mirrored in `app/ui/components/poker_table.py`. |
| `poker-table.jsx` | Reference React implementation — LAYOUTS dict (seat % positions for HU/3/6/8/9), seat tone logic, hero hole-card offset, bet-chip placement. The PySide6 port follows this structure. |
| `Poker-Table.html` | The full Poke spec page (artboards, anatomy, contexts, handoff sheet). Open in a browser to see what the table is *supposed* to look like across every layout. |
| `Style-Guide.html` | One-page visual stickersheet — every component, every tag, every KPI shape. Useful when you need to verify a component's visual against the canon. |

## Don't render

Per the design's own README: **don't open these in a browser unless the
user explicitly asks**. Everything you need is in the source — read it
directly. Screenshots cost the user time and tokens.
