# Rhumb — Passage Monitor

An offline passage-plan monitor that runs entirely in the browser. Import an ECDIS
route file (`.rtm`), GPX, CSV or a pasted passage plan, and watch position, SOG, COG,
distance to go, ETA, cross-track error and percentage complete against it.

The chart is a vector coastline held inside `index.html` — no tile server, no internet,
no chart licence.

## Files

| File | What it is |
|---|---|
| `index.html` | The whole application, including the coastline data |
| `manifest.webmanifest` | Lets Chrome install it as an app |
| `sw.js` | Service worker — precaches everything for offline use |
| `icon.svg`, `icons/`, `favicon.ico` | Compass-rose icon set |

## Publishing

Push these files to a GitHub repository, then **Settings → Pages → Deploy from a branch
→ `main` / `/ (root)`**. Wait for the green tick and open the published URL in Chrome.

GPS only works over `https`, which GitHub Pages provides.

## Not a navigation system

This is a situational-awareness aid. It carries no official charts, no depths and no
navigational warnings. It must never be used for navigation or to replace the approved
passage plan.
