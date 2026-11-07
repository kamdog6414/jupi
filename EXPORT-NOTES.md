# Export notes — what this repository is, and what it is not

JUPI (Joint Unix Platform Integrator) is a repurposed Sony PlayStation 4
(CUH-1001A) running native Arch Linux as a science and engineering
instrument: a resident agent with a durable job queue, a GPU science path
(OpenCL on the Liverpool GPU, peer-verified), a Gothic ASCII art engine,
rover odometry tooling, a cluster fabric client (FC-Link / Agape / xchain /
Castor), and a self-observatory — built and qualified on the machine
itself in November 2026. This repository is the platform source of that
machine, published by FullCircle ComXpress LLC.

Start with JUPI's own words: `README.md` (written by the resident on the
box), `AGENTS.md`, `MODEL-CONTEXT.txt`, and `config/mission.txt`.

## What is included

- `scripts/` — the platform: agent runtime, science workflow + GPU kernel
  sources, art renderer, rover odometry, observatory, Muse gadget bridge,
  checkpoint/recovery tooling, performance profiler, installers, and the
  PS4 bring-up tools used to build the machine from inside a rescue shell.
- `bin/` — the fifteen `jupi-*` entry points.
- `tests/` — the test suite (76 tests passing at export).
- `systemd/` — the unit files the platform runs under.
- `config/` — the machine's configuration set: mission, pinned
  performance profile, package locks, science + platform manifests,
  firewall rules, and templates.
- `examples/science/` — the synthetic qualification datasets.
- `vendor/` — the Agape offline room module, with its upstream pin.
- `docs/BENCHMARK-BASELINE-20261107.txt` — the machine's own measured
  baseline report (the pinned profile's raw results).

## What was changed for publication

- `config/identity.json` ships as `config/identity.example.json`: the
  live instance values (endpoint id, machine-id hash, root UUID,
  authorization hash, chain anchor) are replaced with placeholders. The
  shape, policy, and limits are verbatim — they are the point.
- The live endpoint id was likewise replaced with `jupi-<endpoint-id>`
  in `README.md` and `MODEL-CONTEXT.txt`.
- Hashes remain throughout (benchmark receipts, the pinned profile's
  file-hash map, the science manifest). A hash is a commitment, not a
  credential; verifying them against a live unit requires the unit.

## What is excluded, and why

- The live instance's operational record: enrollment bundles, inbox,
  evidence stores, job/state databases, recovery archives. Those are
  receipts of one machine's life, not platform source.
- The desk mirror (`ghostie-mirror/`) placed on the unit by its
  operator's agent — the house record, not JUPI's code.
- All keys and device secrets. Key-*handling* code is included (it is
  part of the platform's recovery design); no key material exists in
  this tree. It was scanned before export: no credentials, no private
  keys, no personal email addresses, no home-network identifiers.
- Lab addresses (192.168.77.0/24) appear in code and firewall rules
  where they are load-bearing (peer discovery, FC-Link allowlists).
  They are RFC1918 addresses of an isolated lab segment.

## Provenance

Exported 2026-11-07 from the running unit through its paired Muse
gadget SDK lane; the export bundle was sha256-verified end to end before
extraction (bundle sha256 3b1dfaa277f7619d41154e7fa08a0ad4e8606177d816538c
36458d4302514d78). The unit's own git history begins with this export —
its development provenance is its on-box receipt chain, not a commit log.

License: MIT (see LICENSE). Human final: KAM.
