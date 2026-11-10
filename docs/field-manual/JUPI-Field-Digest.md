<div class="cover-mini" markdown="1">

```
JUPI  ::  FIELD DIGEST                                   PUBLIC EDITION
PS4 running Arch Linux from a 355 GiB image on its own HDD
as-built scan 2026-11-10 8:10 AM PST  ::  full manual: JUPI-Field-Manual.pdf
```

</div>

## TL;DR

- **What it is.** JUPI is a jailbroken PS4 running a full Arch Linux desktop and agent node. The
  console OS starts it with a homebrew payload. Root is an ext4 *image file* inside the PS4's
  encrypted UFS2 HDD partition. A small selector in the initramfs unlocks the partition, checks the
  image against hard identity pins, and loop-mounts it.
- **How it breaks.** 8 GB of RAM is *unified*: CPU and GPU share it. Xorg pins GPU (GTT) buffers
  up to a ~3.4 GiB cap and never gives them back while it runs. On Nov 10 that pin plus 4 GiB of
  full swap starved the box. Ping answered, every new SSH login failed, and nothing automatic
  could free the memory.
- **How it comes back.** `sudo systemctl restart lightdm`, then force the HDMI mode with `xrandr`.
  That freed 3.4 GiB of GTT and 4 GiB of swap in under 3 minutes. The real lesson: **keep a
  pre-opened SSH master connection**, because a fresh login is exactly what fails in a freeze.
- **The one thing never to do first:** power-cycle. Coming back needs a human at the console to
  launch the payload. Cold boot is **not verified**.

## Recovery runbook (condensed)

```
                ping answers? --NO--> cable/link, then physical console (power cycle LAST)
                     |YES
            command possible? --NO--> warm mux > open session > gadget lane > slow SSH retry
                     |YES               > wait for earlyoom (minutes only) > power cycle LAST
                  R1 gauge
           GREEN / AMBER / RED
    black screen   shed apps   restart X ---> re-handshake HDMI ---> gauge again
     -> R4 only    (R2)        (R3)            (R4)                  (expect GREEN)
```

**R0 · Pre-arm while healthy (on Roach).** Add a `Host jupi` entry with `ControlMaster auto`,
`ControlPersist yes` and `ServerAliveInterval 30`. Then `ssh -fN jupi` and confirm with
`ssh -O check jupi`.

**R1 · Gauge.**

```
ssh jupi 'free -m; swapon --show
  g=/sys/class/drm/card0/device
  echo "GTT $(( $(cat $g/mem_info_gtt_used)/1048576 )) / $(( $(cat $g/mem_info_gtt_total)/1048576 )) MiB"'
```

RED = available < 500 MiB **or** GTT > 2500 MiB **or** swap > 90 %.

**R2 · Shed (AMBER).** `pkill -TERM -x ChatGPT`. App memory returns. GTT does **not**, because
Xorg holds it. (The Grok Bot desktop app is also an agent lane, so close it knowingly.)

**R3 · Restart X (RED).** `ssh jupi 'sudo systemctl restart lightdm'`. Kills every desktop app.
Services and SSH links survive. Allow about 2.5 minutes. Make sure nobody else already issued it.

**R4 · Re-handshake HDMI (always after R3; also for a black screen).**

```
ssh jupi 'export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
  xset dpms force on; xset -dpms; xset s off
  xrandr --output HDMI-A-0 --off
  xrandr --output HDMI-A-0 --mode 1920x1080 --rate 60 --primary
  xrandr --query | grep HDMI-A-0; xset q | grep "DPMS is"'
```

Expect `HDMI-A-0 connected primary 1920x1080+0+0 … 0mm x 0mm` and `DPMS is Disabled`. Then R1
again: GTT ≈ 30–40 MiB and available > 3000 MiB.

**R5 · No login.** In order: warm mux → any open session → Muse gadget lane (responsiveness in a
freeze **UNKNOWN**) → slow SSH retry (`ConnectTimeout=25`, one machine only) → earlyoom (cannot free
Xorg GTT) → local desktop terminal (no VT switch, no SysRq) → **power cycle last** (needs a human at
the PS4).

**R6 · After any reboot.**

```
findmnt -no SOURCE,FSTYPE /      # /dev/loop0 ext4   (if /dev/sda2 psxitarch: FALLBACK, stop)
findmnt -no SOURCE,FSTYPE /ps4hdd # /dev/mapper/jupi-boot-internal ufs
swapon --show                    # zram1 zstd 200 + zram0 lz4 100
systemctl is-active earlyoom jupi-agent musegadget sshd lightdm
systemctl --failed --no-legend
```

**R7 · Undo Nov 10 memory changes.** `bash ~/groku-wire/rollback-step1.sh` (sha `372417fc…`),
then `sudo pacman -R earlyoom`.

## Key facts

| | |
|---|---|
| Hardware | PS4 (model number UNKNOWN): AMD Liverpool APU, 8× Jaguar @ 1.6 GHz, GCN GPU 18 CU, 8 GB GDDR5 unified |
| Memory | MemTotal 6,904 MiB (1 GiB carved for VRAM). GTT cap 3,450 MiB (half of RAM) |
| Swap | zram1 zstd 2 GiB prio 200 + zram0 lz4 2 GiB prio 100. swappiness 100, page-cluster 0 |
| OOM | earlyoom `-m 4,2 -s 10,5`. Prefers ChatGPT/grok-bot/codex/llama. Avoids Xorg/sshd/lightdm |
| Kernel | `6.15.4-crashnt-4.7_no-built-in-fw`, payload `linux-1024mb.bin` via GoldHEN AutoRun |
| Root | `/dev/loop0` ← `/ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img` (355 GiB ext4, UUID `70dbf870…`) |
| Backing | HDD partition 27, plain dm-crypt aes-xts → UFS2 at `/ps4hdd`. 333 GiB free |
| Fallback | USB `psxitarch` root (`/dev/sda2`). Selected silently if the HDD isn't ready in 5 s |
| Display | Xorg `-novtswitch`, output `HDMI-A-0`, EDID 0 bytes, 1920×1080@60 forced, DPMS off |
| Network | `eth0` <jupi-lan-ip> (DHCP). Default route via Roach <roach-lan-ip>. Reverse tunnel to Roach `127.0.0.1:22052` |
| Access | `pi` only, keys only, no root login. Keys: Roach, NIKOLAI, JUPI→Roach (fingerprints: manual §8) |
| Current boot | `5c74d073…`, up since Nov 7 11:15 PM PST. Cold boot **unverified** |
| Kernel source | USB boot partition vs internal HDD copy for this boot: **UNKNOWN** |
| Open issue | `~/.xsession-errors` +~180 KB/s from ChatGPT's GPU process after the Nov 10 GPU reset failures |
| Sealed | HDD unlock key, Grok Bot credential, Muse pairing file. Never printed, never copied |

<p class="endmark">— times PST · PUBLIC EDITION · source: as-built scan sha256 3559b934… —</p>
