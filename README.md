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
| `icon-*.png`, `icon.svg`, `favicon.ico` | Compass-rose icon set (keep these in the same folder) |
| `nmea-bridge.py` | Hands a WiFi AIS transponder's NMEA feed to the browser |

## Publishing

Push these files to a GitHub repository, then **Settings → Pages → Deploy from a branch
→ `main` / `/ (root)`**. Wait for the green tick and open the published URL in Chrome.

GPS only works over `https`, which GitHub Pages provides.

## AIS

A browser cannot open a raw TCP or UDP socket, so it cannot read a WiFi AIS
transponder directly. Run the bridge on any machine on the ship's WiFi:

    python3 nmea-bridge.py --ksn11w      # KSNTEK KSN11-W (tcp 192.168.1.1:8888)
    python3 nmea-bridge.py --scan        # find the transponder automatically
    python3 nmea-bridge.py --tcp 192.168.1.1:8888
    python3 nmea-bridge.py --udp 10110   # units that broadcast

Python 3.7+ and the standard library only — nothing to install. It prints the
two addresses you need: one to open Rhumb, one to paste into AIS → Source.

Position sentences in the same stream (`RMC`, `GGA`, `VTG`, `AIVDO`) are used as
the ship's fix, so the app still knows where you are without browser GPS.

## Not a navigation system

This is a situational-awareness aid. It carries no official charts, no depths and no
navigational warnings. It must never be used for navigation or to replace the approved
passage plan.
