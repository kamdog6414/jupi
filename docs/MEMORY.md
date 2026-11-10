# JUPI unified memory and memory discipline

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 6. Unified memory model

A PC has RAM for the CPU and separate VRAM on the graphics card. A PS4 does not. CPU and GPU share
one pool of GDDR5. On JUPI that means **a desktop app's graphics buffers come out of the same memory
the kernel, the agent and SSH need to survive.**

### 6.1 Where the 8 GiB goes

```
 PHYSICAL GDDR5 (8 GiB, PS4 spec) -- one pool
 +--------------------+-----------------+---------------------------------------------------+
 | firmware / Sony    | GPU "VRAM"      | LINUX RAM  (MemTotal 7,070,228 kB = 6.74 GiB)     |
 | reserved: UNKNOWN  | carve-out 1 GiB |                                                   |
 | exact split        | (1024mb loader) |                                                   |
 +--------------------+-----------------+---------------------------------------------------+
                                         |
                    inside Linux RAM     v
 +---------------+-------------+--------------+--------------------------------------------+
 | app memory    | page cache  | kernel slab  | GTT: system RAM the GPU maps               |
 | (anon, swap-  | (reclaimable| ~1.3 GiB     | cap 3,618,242,560 B = 3.37 GiB             |
 |  pable to     |  instantly) | (1.21 GiB    | = half of MemTotal (amdgpu default sizing) |
 |  zram)        |             |  unreclaim.) | buffers held by Xorg for X clients do NOT  |
 |               |             |              | come back under pressure                   |
 +---------------+-------------+--------------+--------------------------------------------+
 swap: 4 GiB of zram -- it also lives in this same RAM (compressed)
```

Every layer competes for the same 6.74 GiB. Swap brings no new memory. zram only compresses what is
already in RAM. So once the GTT holds 3.4 GiB, everything else (the kernel, sshd, the agent, the page
cache that holds your shell binaries) fights over about 3.3 GiB, and zram fills too.

### 6.2 Anatomy of the Nov 10 freeze

```
 TIME (PST)  AVAILABLE   SWAP USED      GTT USED / CAP          WHAT HAPPENED
 ----------  ---------   ------------   ---------------------   ---------------------------------
 ~6:2x AM     ~190 MB    4024/4095 MB   3,615,711,232 / 3.62 G  GTT at 99.93 % of cap (Xorg)
 7:02-7:17         --              --   (unreachable)           37 fresh SSH logins fail; ping OK
 7:31-7:36    107 MB     4095/4095 MB   --                      Grok Bot app killed: NO relief
 7:43:33      100 MB     4095/4095 MB   --                      still pinned
 7:47:03    -------- sudo systemctl restart lightdm (pi, from a session that got in) --------
 7:50:01     4343 MB      183/4095 MB   --                      RAM back
 7:50:18     4076 MB      183/4095 MB   32,657,408 (31 MiB)     GTT released
 8:10        3135 MB      183/4095 MB   31,875,072 (30 MiB)     as-built scan
 8:24        3111 MB      199/4095 MB   31,875,072 (30 MiB)     this manual's spot check
```

Three lessons, all from the record above:

1. **Killing the app is not enough.** The 3.4 GiB was attributed to **Xorg**, which holds the buffers
   on behalf of its clients. Killing the Grok Bot desktop app at 7:31–7:36 left available memory at
   107 MB.
2. **Restarting the X session is the release valve.** When lightdm stopped (7:47:28), Xorg exited and
   the kernel freed its GTT. lightdm's own unit summary reads *"614.9M memory peak, **3.4G memory swap
   peak**"*.
3. **earlyoom cannot fix this on its own.** It avoids `Xorg` by design and kills only apps
   (ChatGPT, grok-bot, codex, llama-*). That buys time but cannot release Xorg's hold. Use it as the
   seatbelt and the lightdm restart as the brake.

### 6.3 The health gauge: always read two numbers

`free -m` alone lies by omission, because GTT shows up as "used" with no owner. Read **MemAvailable
and GTT together**:

```
free -m
g=/sys/class/drm/card0/device
echo "GTT $(( $(cat $g/mem_info_gtt_used)/1048576 )) / $(( $(cat $g/mem_info_gtt_total)/1048576 )) MiB"

# who holds it (root; per-process sum of GTT buffer objects from the amdgpu debug node)
sudo awk '/^pid/{p=$2" "$4} /byte GTT/{s[p]+=$2}
  END{for(k in s) printf "%8.1f MiB  %s\n", s[k]/1048576, k}' \
  /sys/kernel/debug/dri/0/amdgpu_gem_info | sort -rn | head
```

Healthy output at 8:24 AM: `GTT 30 / 3450 MiB`; holders `Xorg 11.2`, `xfwm4 10.0`, `ChatGPT 2.0`,
`xfce4-session 2.0` MiB.

| Zone | MemAvailable | GTT used | Swap used | Action |
|---|---|---|---|---|
| **GREEN** | > 1500 MiB | < 1024 MiB | < 50 % | Carry on |
| **AMBER** | 500–1500 MiB | 1024–2500 MiB | 50–90 % | R2: shed desktop apps, plan an X restart |
| **RED** | < 500 MiB | > 2500 MiB | > 90 % | R3 now, while you still have a session |

*Zone thresholds are operator guidance proposed in this manual, not measured limits. The measured
failure point was ~100–190 MB available, 4095/4095 swap, GTT 99.9 % of cap.*

### 6.4 Two operating profiles

These are **operator conventions**. No JUPI config file encodes them (checked at scan).

| | **DESKTOP** (interactive / light) | **COMPUTE** (heavy work) |
|---|---|---|
| Desktop apps | XFCE + at most one heavy Electron app (ChatGPT *or* Grok Bot) | Close ChatGPT, Grok Bot, browsers. Or restart X and launch nothing |
| Allowed jobs | editing, light agent jobs, qwen3:0.6b prompts | ollama bigger models, `jupi-pipeline-bench`, GPU/UMA benches, builds |
| Budget ceilings already enforced | jupi-agent ≤ 1536 MiB, ollama ≤ 2300 MiB (systemd MemoryMax) | same; GTT then free for compute |
| Gauge cadence | every few hours, and before starting anything big | before and after each heavy job |
| Exit | X restart (R3 + R4) if GTT trends up for hours | relaunch desktop apps afterwards |

*Rule of thumb (inferred from the incident): GTT climbs slowly while Electron apps sit in the
desktop. Watch the trend. A single reading will not show it.*

### 6.5 Other memory observations at scan

- **Unreclaimable slab: 1,210,648 kB (≈1.15 GiB).** That is 17 % of MemTotal, and the cause is **UNKNOWN**
  (candidates: zram/TTM bookkeeping, driver allocations). Watch whether it grows.
- `Committed_AS` 11.2 GB on a 7.7 GB CommitLimit. Fine under heuristic overcommit, but allocations
  are promised beyond what physically exists.
- VRAM carve-out: 1,073,741,824 B total, 109 MB used. The GPU uses GTT for the rest.
