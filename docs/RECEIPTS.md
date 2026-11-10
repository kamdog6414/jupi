# JUPI receipts

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 11. Receipts appendix

### 11.1 Source documents for this manual

| Document | Location | Size | sha256 |
|---|---|---|---|
| As-built scan (primary) | JUPI `~/groku-wire/`, NIKOLAI `~/groku-relay/inbox/`, Roach `~/groku2/jupi-map/` | 279,105 B | `3559b9342a67edecf5f9adcfbc196f875b53b1e989f1552fab9eb7e496053c8d` (verified on Roach and NIKOLAI copies, Nov 10 8:23 AM) |
| Per-layer working files L1–L6, `usbroot.after.sh`, `irfs/current.cpio.gz` | Roach `~/groku2/jupi-map/` | — | initramfs `cdeaefdb…7d11e21` (matches live) |
| X-restart verification | JUPI `~/groku-wire/RESULTS-xrestart-20261110T155109Z.md` | 3,066 B | `85c79208fd1cf8a340b35b65127f7fa20ecde67aafcf8c0e652df05b83b5b755` |
| Freeze recovery attempt log | NIKOLAI `~/groku-relay/inbox/RECOVERY-ATTEMPT-20261110T151745Z.md` | — | — |
| Change log (hash-chained) | JUPI `~/groku-wire/CHANGES.md` | 2,008 B | chain heads `f4efa078…`, `a058f987…` |
| Origin diagnostics | Roach `~/ps4-linux/diagnostics/` | — | payload receipt `PAYLOAD-SEND-20261105T234546-0800-ROACH2.json` |

### 11.2 Boot-critical files

| File | Bytes | sha256 |
|---|---|---|
| `/ps4hdd/data/linux/boot/bzImage` (= USB copy) | 15,692,800 | `f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293` |
| `/ps4hdd/data/linux/boot/initramfs.cpio.gz` (active) | 6,778,642 | `cdeaefdb30c7b60ad25fa478ef41eb365fb5132795257011f753578537d11e21` |
| `…/initramfs.before-disk-only-20261107T051314Z.cpio.gz` | 6,795,645 | `7eec9f0e7ac9c23b4982e7f3f6c08abcc40142b9b53068e601ddc815d7df39a2` |
| `usbroot.sh` (root selector, in initramfs) | 9,685 | `f65941df0ea77cbfc542105e5b1f3f4ffecd26ce16be4fdcc9aa8eb9634ac797` |
| `init` (better-initramfs, in initramfs) | 4,003 | `06cb53715d3beaf97abad7c88a2cf6902cd110dffdda258c430484a1420da8af` |
| `/usr/local/bin/jupi` (selector-pinned) | 11,944 | `3f5d4eee5787f8991f9a9447e7cfc2f7e1438b77d3b885e2f98e4bdceca12bb1` |
| `linux-1024mb.bin` (payload) | 329,088 | `e11da9d2f772bd2619587d1bc3bd49b257876d1b298fd4f01e1a1139414b6646` |
| `/usr/local/lib/jupi-boot/kexec` | — | `fa5d442d88e24cbf02f322f1edb09130990aac9c9842c3abf9c0701508733254` |
| `/usr/local/sbin/jupi-zram` | — | `8d9d1f4f499a219aeb74efc5c1908df54900234f232a6696ccab2d5830a440f2` |
| `/usr/local/sbin/groku-zram` | — | `e6d2ca3fd6f62176ea17367da3a03e51397ce094f56af69d0e5444bc5b6c52bd` |
| Root image `jupi-linux-2a79fafeb62d61ff.img` | 381,178,347,520 | not hashed (live, 355 GiB) |

### 11.3 Rescue-shell and repair checkpoints

| Checkpoint | Item | sha256 |
|---|---|---|
| CP01 | `system.txt` | `9e511a79921b573ea0f850e79eff35e577b295aeb2b42a0bb5121cc966ed5a68` |
| CP01 | `boot-hashes.txt` | `a4c440e0240eaaecc5bfbff4193bfb95fbec5fb018efe79f798c694e0d7171a1` |
| CP01 | `kernel-log.txt` | `c37d21405cee5726b2564b4cfd6b1b8600877b2b4812c46d96bbb3ac028183ed` |
| CP02 | `fc.sh` (the `/ps4hss` script) | `4c4f902b33743f4441124bf2c4033855f9727fe6630abbf8f42fd21c2fe6143b` |
| CP02 | `init` | `5fb35223732bded5653ae72e2a0cec8f8b6d68a3dfd4c805d07da1a354d24de4` |
| CP02 | `functions.sh` | `807f36708317373bd2a206b33df822b07690befb5a446b83b68035baa3358b4d` |
| CP03 | `initramfs.pre-v3.cpio.gz` | `3a77c2a183d1f8bbd9a3b36fecb30d737020645922260db4a110e22bf95170bf` |
| CP05 | source archive (selector with `}`) | `8888da8f165bdb1a81612031166bc890cbd6490395cd223ba5691230e9e63d91` |
| CP05 | repaired archive (6,775,692 B) | `fa7d6f7763ffb5f9f74bf1b32154bd4a961e94b3a9e98e26b53dc187b88fc4d9` |
| CP05 | repaired `usbroot.sh` | `c3baf9caf3fadf0e49fb40589048a3c49338eadc09df671996d127d2e8ded5d8` |

### 11.4 Nov 10 change receipts

| Item | sha256 |
|---|---|
| `rollback-step1.sh` | `372417fcd4bdc09fbfb76d9b98c577ebc8add9348665cded87479c36ffef2303` |
| `earlyoom-1.9.0-1-x86_64.pkg.tar.zst` | `f54e18d52be814ceaed9b2e4829ed158c534f8e6b83900af57817198ef3bba59` |
| `recover.sh` (staged during the freeze, **never executed**) | `bfceda99d6ba000df175e0fea4a33abb4509727e7dfa13c2eec68a4203c76a70` |
| `RESULTS-xrestart-20261110T155109Z.md` | `85c79208fd1cf8a340b35b65127f7fa20ecde67aafcf8c0e652df05b83b5b755` |

### 11.5 Boot list

| Boot ID | Root | Came up (PST) | Evidence |
|---|---|---|---|
| `7e1177e5-de33-4a4d-a2f4-fe99367a1fe8` | `loop0` ← `linux.img` (50 GiB stock) | Nov 5 ~11:47 PM | autostart report (initial boot ID) |
| `a6a81461-e092-489a-923b-db43b6e695e1` | `/dev/sda2` USB | before Nov 6 1:06 PM | CP05 report |
| `b00c61e1-6e1e-4d26-ab31-0caf281bcd82` | `/dev/sda2` USB (111.5 GB fs) | Nov 6 ~1:21 PM | boot receipt (uptime 6405 s at 3:08 PM) |
| `54f4c94e-2a9d-443a-8c03-321c3ae6a714` | `loop0` ← JUPI image, 40 GiB | Nov 6 ~8:48 PM | boot receipt (written 8:50 PM) |
| soft-return `f3be767b-…` | same kernel boot, userspace restart | Nov 7 ~11:56 AM | `SOFT-RETURN-*.json` |
| **`5c74d073-6f75-42c5-b5d4-566cc6090faa`** | `loop0` ← JUPI image, 355 GiB | **Nov 7 11:15:16 PM** (btime 1794122116) | boot receipt, journal |

### 11.6 Identity anchors

| Item | Value |
|---|---|
| Root FS UUID | `70dbf870-bcb6-4be9-9fb5-f25c4718b71a` (label `JUPIROOT`) |
| USB boot partition | `891E-578E` (`PS4BOOT`) |
| USB fallback root | `2ec1035f-9275-4d5b-bd46-c6e40122ea8d` (`psxitarch`) |
| HDD GPT disk GUID | `66FB93BD-D972-11F1-8753-709E29577E23` |
| Endpoint ID | `jupi-f04a6e42c85374a67f331992` (`/etc/jupi/identity.json`) |
| Muse node | `homelink-3364d7`, display name `JUPI` |
| Castor anchor | `07b1bb90149ff0e24e4dbf5902dcbfdbf3d81f89132cd572cecd25a7fb2b56ce` |

Key fingerprints: Section 8.3.
