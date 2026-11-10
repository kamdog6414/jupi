# JUPI Field Manual (public edition)

| File | What |
|---|---|
| [`JUPI-Field-Manual.pdf`](JUPI-Field-Manual.pdf) | 28-page black-and-white field manual: architecture, boot chain, as-built OS config, unified memory, freeze & recovery runbook, lanes, timeline, receipts |
| [`JUPI-Field-Digest.pdf`](JUPI-Field-Digest.pdf) | 2-page digest: TL;DR, condensed runbook, key facts |
| `JUPI-Field-Manual.md`, `JUPI-Field-Digest.md` | Markdown sources of the PDFs above |
| `manual.css`, `build.py` | Typesetting (python-markdown → headless Chrome). `python3 build.py` re-renders both PDFs |

Source of truth: `JUPI-ASBUILT-SCAN-20261110T1610Z.txt` (279,105 B, sha256
`3559b9342a67edecf5f9adcfbc196f875b53b1e989f1552fab9eb7e496053c8d`). It was a read-only scan,
and nothing on JUPI was changed to produce this manual.

**Redactions in this edition:** LAN and tailnet addresses, the unlock-key file paths, the MAC address,
the console user id and operator home paths are replaced with role placeholders (`<jupi-lan-ip>`,
`<roach-lan-ip>`, …). SSH fingerprints are truncated. No private key, credential, unlock key or pairing
material appears in any edition. A private edition with real addresses exists off-repo for the operator.

Style rule: black and white only. Monospace for code, paths and receipts. Line/ASCII diagrams. No color.
