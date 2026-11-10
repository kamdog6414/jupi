# JUPI as-built configuration

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 1. What JUPI is

**JUPI (Joint Unix Platform Integrator) is a Sony PlayStation 4 running Arch Linux as a lab
instrument.** It is x86_64 — AMD Jaguar cores, **not ARM** — even though its user is called `pi`
and its locale is `en-GB`/London. Those are leftovers from the 2022 community *psxitarch* PS4 Arch
image it grew out of, not signs of a Raspberry Pi.

Its root filesystem is **not on the USB stick**. Root is a 355 GiB ext4 *image file* stored on the
PS4's own internal 500 GB hard drive. The drive sits behind Sony's internal USB-SATA bridge and is
encrypted. Each boot, the initramfs decrypts the drive, mounts Sony's UFS2 filesystem at `/ps4hdd`,
attaches the image as `/dev/loop0` and boots it. The SanDisk stick is kept only as the fallback root
and as a boot medium.

```
 LAYER  WHAT                                   DETAIL                              WHERE
 -----  -------------------------------------  ----------------------------------  ----------------------
   7    Workloads                              jupi-agent, ollama, science tools,  / (loop0)
                                               XFCE desktop, ChatGPT, Grok Bot
   6    Userspace                              Arch Linux (rolling), systemd,      / (loop0)
                                               lightdm autologin pi -> XFCE
   5    Root filesystem                        ext4 "JUPIROOT", 355 GiB            /dev/loop0
   4    Image file                             jupi-linux-2a79fafeb62d61ff.img     /ps4hdd/home/
   3    Backing filesystem                     Sony UFS2, 414 GiB, mounted RW      /ps4hdd
   2    Disk decryption                        dm-crypt plain, aes-xts-plain64,    /dev/mapper/
                                               256-bit, map "jupi-boot-internal"   jupi-boot-internal
   1    Physical partition                     sdb27, 420.1 GiB (GPT, 15 parts)    internal HDD, 465.8 GiB
   0    Kernel + initramfs                     6.15.4-crashnt-4.7 + root selector  loaded by PS4 payload
                                                                                   (USB or HDD copy: UNKNOWN)
  -1    Console OS + homebrew loader           Orbis OS -> linux-1024mb.bin        PS4 firmware/HDD
```

### Hardware block diagram

```
 +-------------------------------- SONY PS4 ("playstation") ---------------------------------+
 |                                                                                           |
 |   AMD LIVERPOOL APU (one die)                         AEOLIA SOUTHBRIDGE (Sony 104d:9xxx) |
 |   +-------------------------------+                   +-------------------------------+   |
 |   | 8x Jaguar x86_64 @ 1593.8 MHz |    PCIe glue      | xHCI USB 3.0  (xhci_aeolia)   |   |
 |   |   family 22 / model 17        |<----------------->| Ethernet Marvell Yukon2 (sky2)|   |
 |   |   L2: 2x 2 MiB                |                   | AHCI SATA     (ahci)          |   |
 |   | GCN GPU "Liverpool" 18 CU     |                   | SD/MMC -> SDIO Wi-Fi/BT card  |   |
 |   |   amdgpu 3.63.0, card0        |                   +---------------+---------------+   |
 |   +---------------+---------------+                                   |                   |
 |                   |                                                   | USB               |
 |   8 GiB GDDR5 -- ONE POOL, shared CPU+GPU                             |                   |
 |   Linux sees 6.74 GiB RAM + 1 GiB "VRAM" carve-out                    |                   |
 |                                                                       |                   |
 |   +--------------------------------------+    +------------------------v--------------+   |
 |   | Internal HDD 465.8 GiB  (sdb)        |<---| Sony USB-SATA bridge 054c:084e 5 Gb/s |   |
 |   |   sdb27 420.1 GiB -> dm-crypt -> UFS2|    +---------------------------------------+   |
 |   +--------------------------------------+                                                |
 +-------------------------------------------------------------------------------------------+
        |  front USB (Genesys hubs)
        +--> SanDisk USB 114.6 GiB (sda): sda1 PS4BOOT vfat | sda2 psxitarch ext4 | sda3 swap
        +--> Microsoft Wired Keyboard 600, Razer DeathAdder V2
        +--> HDMI-A (1920x1080@60, panel EDID reads 0 bytes)      eth0 -> lab LAN
```

> **Why the HDD is "USB".** Linux sees the internal drive as `sdb` with model
> `USB-SATA Bridge` (Sony 054c:084e) on the Aeolia xHCI bus. Removing USB support would remove
> the internal drive too.

### Key facts

| Item | Value | Status |
|---|---|---|
| CPU | 8× AMD Jaguar (`DG1000FGF84HT`), x86_64, 1593.786 MHz TSC, 1 thread/core | observed |
| GPU | Liverpool GCN, 18 active CUs, `amdgpu`, VRAM 1 GiB, GTT cap 3,618,242,560 B (3.37 GiB) | observed |
| RAM | MemTotal 7,070,228 kB (6,904 MiB in `free -m`); unified with GPU | observed |
| Swap | zram0 2 GiB lz4 prio 100 + zram1 2 GiB zstd prio 200 = 4 GiB, RAM-backed | observed |
| Kernel | `6.15.4-crashnt-4.7_no-built-in-fw` #2, clang 18.1.3, built 2026-03-14 | observed |
| Root | `/dev/loop0` ← `/ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img`, 381,178,347,520 B | observed |
| Root usage | 350 G size, 33 G used, 313 G free (UFS backing: 333 G free) | observed 8:10 AM |
| Host / user | `playstation` / `pi` (uid 1000, wheel; passwordless sudo) | observed |
| Locale / TZ | en-GB / Europe/London (from the 2022 psxitarch image) | observed |
| Current boot | `5c74d073-6f75-42c5-b5d4-566cc6090faa`, up since Sat Nov 7 11:15:16 PM | observed |
| Network | eth0 <jupi-lan-ip>/24 (`proto dhcp`), default route via Roach <roach-lan-ip>; no wlan interface up | observed |
| Unattended cold boot | **Not verified** (`cold_boot_verified: false` in every boot receipt) | observed |
| Kernel loaded from USB or HDD copy this boot | **UNKNOWN** | — |

### The three things to remember

1. **Memory is one pool.** The GPU's working buffers (GTT) are carved out of the same 6.7 GiB the
   apps use. Xorg can hold ~3.4 GiB of it for desktop apps. When that happens the box freezes for new
   logins, and **only restarting the X session (lightdm) gives the memory back.** See Sections 6–7.
2. **After any X restart the HDMI panel must be re-handshaked** (it reports zero EDID bytes).
   Five commands, Section 7, step R4.
3. **Keep a pre-opened SSH connection.** During the Nov 10 freeze 37 fresh SSH logins failed while
   ping still worked. A connection opened *before* the freeze is the one that still works.


## 5. As-built OS configuration

All values were read from the 8:10 AM scan unless stated otherwise. Arch Linux rolling, 844 packages
installed (`pacman` count line also shows 150, most likely the explicitly-installed subset).

### 5.1 Kernel and sysctl

| Key | Live value | Set by |
|---|---|---|
| `vm.swappiness` | **100** | `/etc/sysctl.d/90-groku.conf` (overrides `80-jupi-memory.conf` = 10) |
| `vm.page-cluster` | **0** | `90-groku.conf` (single-page swap-in; right for zram) |
| `vm.min_free_kbytes` | 67584 | kernel default for this RAM size |
| `vm.watermark_scale_factor` | 10 | default |
| `vm.vfs_cache_pressure` | 100 | default |
| `vm.overcommit_memory` | 0 (heuristic) | default; Committed_AS 11.2 GB vs CommitLimit 7.7 GB |
| SysRq | **absent** (`/proc/sys/kernel/sysrq` does not exist) | kernel build |
| `CONFIG_CFS_BANDWIDTH` | **absent**, so `CPUQuota=` is not enforced; CPU affinity is used instead | kernel build |

*Why swappiness 100?* All swap is compressed RAM (zram). Swapping an idle anonymous page costs a
fast compression. Dropping a file page means re-reading it later from a loop image on an encrypted
HDD behind a USB bridge. *(The `90-groku.conf` comment still says "USB loop root". That wording is
stale. The idea still holds for the HDD loop root.)*

### 5.2 Swap: two zram devices

| Device | Algorithm | Size | Priority | Owner unit | Script sha256 |
|---|---|---|---|---|---|
| `/dev/zram1` `groku-zram` | zstd | 2 GiB | **200** (used first) | `groku-zram.service` (After=jupi-zram) | `e6d2ca3f…6c52bd` |
| `/dev/zram0` `JUPI_ZRAM` | lz4 | 2 GiB | 100 | `jupi-zram.service` (Before=lightdm) | `8d9d1f4f…a440f2` |

At scan: zram0 held 164.9 MiB of data in 73.8 MiB of RAM; zram1 held 15.2 MiB in 3 MiB.
The old 8 GiB USB swap partition is commented out of `/etc/fstab`. There is no disk swap.

### 5.3 earlyoom (installed Nov 10, armed 6:25 AM)

```
/usr/bin/earlyoom -m 4,2 -s 10,5 -r 300
   --prefer '^(llama-bench|llama-cli|llama-server|llama-simple|test-backend-op|grok-bot|chatgpt|ChatGPT|codex)$'
   --avoid  '^(sshd|sshd-session|musegadget|runtime\.py|Xorg|systemd|systemd-journal|systemd-logind|
             xfwm4|xfce4-session|earlyoom)$'
   (drop-in /etc/systemd/system/earlyoom.service.d/90-groku.conf, OOMScoreAdjust=-1000)
```

| Trigger | Condition (BOTH must hold) | In absolute terms on JUPI |
|---|---|---|
| SIGTERM | MemAvailable ≤ 4 % **and** swap free ≤ 10 % | ≤ ~276 MiB available and ≤ ~410 MiB swap free |
| SIGKILL | MemAvailable ≤ 2 % **and** swap free ≤ 5 % | ≤ ~138 MiB available and ≤ ~205 MiB swap free |

Package `earlyoom 1.9.0-1`, installed with `pacman -U` (sha256 `f54e18d5…3bba59`). It moves the
`jupi-profile` baseline off its pinned state. No kill events were logged up to the scan.

**OOM-score protections** (lower = kept alive longer):

| Process | oom_score_adj | Source |
|---|---|---|
| sshd | −1000 | pre-existing |
| earlyoom | −1000 | drop-in |
| jupi-agent (`runtime.py`) | −900 | `jupi-agent.service.d/90-groku-oom.conf` |
| musegadget | −900 | `musegadget.service.d/90-groku-oom.conf` |

### 5.4 systemd: what runs

`jupi-platform.target` (WantedBy multi-user) pulls in: `jupi-agent`, `jupi-health.timer`,
`jupi-zram`, `jupi-link@roach`, `jupi-firewall`, `sshd`, `musegadget`, `jupi-nerves.timer`,
`fclink`, `jupi-link@fclink`, `jupi-observe.timer`, `ollama`.

| Service | Runs as | Limits / notes |
|---|---|---|
| `jupi-agent.service` | pi, nice 10 | MemoryHigh 768M, MemoryMax 1536M, CPUAffinity **0 2**, TasksMax 96; durable SQLite job queue |
| `ollama.service` | ollama, nice 10 | 127.0.0.1:11434, 1 model, 1 parallel, ctx 2048, keep-alive 60 s, `OLLAMA_NO_CLOUD=1`, MemoryHigh 1600M / Max 2300M, all 8 CPUs |
| `musegadget.service` | **root**, commands as pi | Muse Home Link; RuntimeDirectory `/run/musegadget`; Restart on-failure |
| `jupi-link@roach` / `@fclink` | pi | persistent outbound SSH to Roach (field manual §8), Restart always 15 s |
| `fclink.service` | (unit is root-only, not readable) | FC-Link v1, HMAC, binds <jupi-lan-ip> + 127.0.0.1 :8765 |
| `jupi-firewall.service` | root, oneshot | loads `/etc/jupi/firewall.nft` (table `inet jupi`) |
| `jupi-zram` / `groku-zram` | root, oneshot | the two swap devices |
| `jupi-boot-record.service` | root, oneshot | startup receipt; requires agent + ollama + zram |
| `earlyoom.service` | dynamic user | see 5.3 |
| `lightdm.service` | root | autologin `pi`, session `xfce` |

| Timer → service | Cadence (from timer listing) | What it does |
|---|---|---|
| `ghostie-usb-guardian` | ~1 min | revives a dead xHCI controller, pins hub power, logs churn |
| `jupi-nerves` | ~1 min | local "nervous-system" pulse (timeout 20 s, MemoryMax 128M) |
| `jupi-host-watch` | ~1 min | bounded host resource/service sample (timeout 15 s) |
| `ghostie-display-keeper` | ~2 min | `xset dpms 0 0 0; s off; s 0 0; s noblank; -dpms` |
| `jupi-observe` | ~5 min | hardware + cluster observation (CPUQuota 50 %, idle I/O) |
| `jupi-knowledge` | ~15 min | private archive compile + evidence probes (timeout 300 s) |
| `jupi-health` | ~15 min | inventory + health receipt → `/var/lib/jupi/health.json` |

At scan time `jupi-health.service` was **failed**, along with one `systemd-coredump@` unit. Since the
journal's oldest entry (Nov 9, 7:54 AM) the observers have logged many timeouts: jupi-nerves 201,
jupi-host-watch 196, jupi-observe 45, jupi-knowledge 16, jupi-health 16. When those happened is
not broken down. *(Inferred: most likely during memory pressure.)*

Sleep, suspend, hibernate, hybrid-sleep and suspend-then-hibernate targets are masked
(symlinked to `/dev/null`). No cron is installed. Systemd timers are the only scheduler.

### 5.5 Display stack

| Piece | Setting |
|---|---|
| Kernel connector | `card0-HDMI-A-1`, status connected, **EDID 0 bytes**, cmdline forces `1920x1080@60` |
| X output name | **`HDMI-A-0`** (xf86-video-amdgpu numbers from 0; the kernel numbers from 1) |
| Xorg | `/usr/lib/Xorg :0 -seat seat0 -auth /run/lightdm/root/:0 -nolisten tcp vt7 -novtswitch` |
| Driver stack | `xf86-video-amdgpu-ps4 21.0.0-2`, `mesa-ps4 21.3.2-1` (+lib32), LLVM 13 compat libs in `/usr/local/lib/jupi-gpu-compat` |
| DPMS / blanking | Off. `/etc/X11/xorg.conf.d/10-ghostie-nodpms.conf` (root-only) + the display-keeper timer |
| Session | lightdm → autologin `pi` → XFCE; `~/.xsession-errors` collects all X client stderr |

> `-novtswitch` means **Ctrl+Alt+F*n* will not take you to a text console.** Together with the
> missing SysRq, a frozen desktop cannot be escaped from the local keyboard.

### 5.6 Journal, firewall, packages

**journald:** persistent, `SystemMaxUse=128M`, `SystemKeepFree=1G`, 14-day retention, sync every
5 min. It was at 126.3 MiB at scan, so only **Nov 9 7:54 AM onward** is still in the journal. Older
history comes from receipts.

**nftables** (`table inet jupi`, input policy **drop**):

```
iifname "lo" accept
ct state established,related accept ; ct state invalid drop
meta l4proto { icmp, ipv6-icmp } accept
udp 67->68, udp 547->546 accept          # DHCP renewal
tcp dport 22 accept                      # SSH, any source
iifname "eth0" ip saddr { <lab-gateway-ip>, <roach-lan-ip> } tcp dport 8765 accept   # signed FC-Link
counter drop
```

**Foreign (non-repo) packages:** `mesa-ps4 21.3.2-1`, `lib32-mesa-ps4 21.3.2-1`,
`xf86-video-amdgpu-ps4 21.0.0-2`, `lib32-libvdpau 1.5-1`, `neofetch`, `python-nspektr 0.4.0-1`,
`yay-bin 11.2.0-1`. `pacman.conf` has **no `IgnorePkg`** line. A blanket `pacman -Syu` is not fenced
off from the PS4 graphics stack. The kernel is not a pacman package, so pacman cannot replace it.

**sshd** (drop-in): `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
`PubkeyAuthentication yes`, `MaxAuthTries 3`, `LoginGraceTime 30`, `ClientAliveInterval 60` ×3,
`X11Forwarding no`, `GatewayPorts no`, `LogLevel VERBOSE`.


## 8. Lanes & access map

### 8.1 Map

```
                                     LAB LAN  (eth0, <lab-lan>/24)
  +-------------------------+                                         +----------------------------+
  | ROACH  (Ubuntu, roach)  |  (1) ssh pi@JUPI:22  key "roach@roach"  |  JUPI  host "playstation"  |
  | <roach-lan-ip>          |---------------------------------------->|  <jupi-lan-ip>             |
  | default gw for JUPI     |                                         |  sshd :22 (keys only)      |
  |                         |  (2) jupi-link@roach  JUPI -> roach:22  |                            |
  |  127.0.0.1:22052  <=====|<========================================|  RemoteForward 22052 -> 22 |
  |   (reverse SSH to JUPI) |      key "JUPI-to-Roach unattended"     |                            |
  |                         |                                         |  jupi-link@fclink:         |
  |  fclink :8765 (lo)  <---|<----- (3) JUPI 127.0.0.1:18766 ---------|   LocalForward 18766       |
  +-----------+-------------+                                         |   LocalForward 18765 ------+--+
              |  "nikolai" alias (tailnet)                            |                            |  |
              v                                                       |  fclink.service :8765      |  |
  +-------------------------+   (4) Codex-NIKOLAI-to-JUPI key         |   HMAC; LAN bind only from |  |
  | NIKOLAI                 |------- arrives via Roach -------------->|   gw + Roach (nftables)    |  |
  | fclink <tailnet-ip>     |<------------------------------------------------------------------------+
  |   :8765 (tailnet)       |   (3) JUPI :18765 -> Roach -> here      |                            |
  +-------------------------+                                         |                            |
                                                                      |  musegadget (root, run-as  |
                     (5) Muse Home Link cloud  <======= TLS 443 ======|   pi) node homelink-3364d7 |
                         "system.run" gadget lane                     |  /run/musegadget/*.sock    |
                                                                      |                            |
                                                                      |  LOCAL ONLY:               |
                                                                      |   ollama 127.0.0.1:11434   |
                                                                      |   serve_console 127.0.0.1: |
                                                                      |     18773                  |
                                                                      |   jupi-agent unix socket   |
                                                                      +----------------------------+
```

### 8.2 Lane table

| # | Lane | Direction / transport | Auth | Notes |
|---|---|---|---|---|
| 1 | **Direct SSH** | Roach → JUPI tcp/22 | `pi` authorized_keys line 1: `roach@roach` | The lane used for the scan and this manual. Fresh logins failed in the freeze (R0) |
| 2 | **Reverse tunnel** | JUPI → `roach@Roach:22`; RemoteForward Roach `127.0.0.1:22052` → JUPI `127.0.0.1:22` | JUPI key `JUPI-to-Roach unattended transport`; Roach host key pinned (`StrictHostKeyChecking yes`) | `jupi-link@roach.service`, Restart always/15 s, ServerAlive 30 s×3. Use from Roach: `ssh -p 22052 pi@127.0.0.1` |
| 3 | **FC-Link tunnel** | JUPI `127.0.0.1:18765` → NIKOLAI `<nikolai-tailnet-ip>:8765` (via Roach); `127.0.0.1:18766` → Roach loopback `:8765` | same JUPI→Roach key | `jupi-link@fclink.service`. FC-Link itself is HMAC-authenticated |
| 3′ | **FC-Link server** | inbound tcp/8765 on <jupi-lan-ip> + 127.0.0.1 | HMAC; nftables allows LAN only from <lab-gateway-ip>, <roach-lan-ip> | `fclink.service` (fclink 1.3.3) |
| 4 | **NIKOLAI Codex** | NIKOLAI → (via Roach) → JUPI tcp/22 | `pi` authorized_keys line 4: `Codex-NIKOLAI-to-JUPI` | Last seen Nov 10 7:54 AM from Roach's address |
| 5 | **Gadget lane** | JUPI → Muse cloud, TLS 443 (outbound only) | Muse pairing (sealed, not documented) | `musegadget.service` as **root**, `--run-as pi`; display name JUPI; node `homelink-3364d7`; `system.run` via `/run/musegadget/musegadget.sock` (`srw-rw---- root:pi`) |
| 6 | **jupi-agent** | local unix socket, pi/root only | filesystem permissions | durable jobs; `jupi-agent run --peer` executes on Roach as `roach` |
| 7 | **Desktop agents** | outbound 443 | app logins (sealed) | ChatGPT 26.1103.32239 + `codex app-server`; Grok Bot 0.79.3 (local-exec daemon in `~/.grokbot`) |

There is no Tailscale on JUPI (`tailscale` not installed). Tailnet reachability is only through Roach.

### 8.3 Keys: fingerprints and comments only

| Where | Fingerprint | Comment / role |
|---|---|---|
| JUPI `~pi/.ssh/authorized_keys` #1 | `SHA256:aEMbT86C…ZlQ` | `roach@roach` (ED25519): Roach's operator key |
| JUPI `~pi/.ssh/authorized_keys` #4 | `SHA256:XbrOkDNu…ZKU` | `Codex-NIKOLAI-to-JUPI` (ED25519) |
| JUPI `~pi/.ssh/jupi_roach_ed25519.pub` | `SHA256:9cfyEz78…Dso` | `JUPI-to-Roach unattended transport` (ED25519). Private half stays on JUPI |
| Roach host key pinned by JUPI | `SHA256:KveFQm/M…H7A` | in `/etc/jupi/ssh/roach.known_hosts` |
| JUPI host key ED25519 | `SHA256:awkaTxgG…zrM` | `root@playstation`. First seen Nov 5 11:51 PM, unchanged since |
| JUPI host key ECDSA | `SHA256:op1XSU8w…b+Y` | `root@playstation` |
| JUPI host key RSA-3072 | `SHA256:GRg4YZiy…uz8` | `root@playstation` |
| JUPI host key MLDSA44-ED25519 | `SHA256:Y7jG1Xer…ZD8` | `root@playstation` (post-quantum hybrid) |
| root `authorized_keys` | — | does not exist; root SSH login is disabled anyway |

Lines 2–3 of pi's `authorized_keys` are a blank line and a comment. `~pi/.ssh/authorized_key`
(no *s*, 0 bytes) is a harmless fossil of a Nov 6 typo in pi's shell history
(`curl … >> ~/.ssh/authorized_key`).

**Sealed. Never printed, copied or documented:** the HDD unlock key (sealed root-only copy), the
JUPI→Roach private key, the Grok Bot local-exec credential ((sealed credential file)),
the Muse pairing material, app logins, and the fleet ledger directories.
