# JUPI freeze & recovery runbook

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 7. Freeze & recovery runbook

Work top to bottom. Every command was used on JUPI on Nov 10 or read from its live configuration.
Run commands as `pi` unless shown with `sudo` (pi has passwordless sudo).

### 7.0 Triage: pick your entry point

```
                           +--------------------------+
                           |  Something is wrong      |
                           +------------+-------------+
                                        |
                      ping <jupi-lan-ip> answers?
                     /                                   \
                   NO                                     YES
                   |                                       |
        R6: network/kernel down              Can you run a command on JUPI?
        (check cable/link, then               (warm mux, open session, gadget lane)
         physical console; see R5e)          /                                \
                                           YES                                 NO
                                            |                                   |
                                  R1: read the gauge                 R5: no-login recovery
                                     |                               (warm mux > gadget lane >
                    +----------------+----------------+               wait for earlyoom >
                    |                |                |               power cycle LAST)
                  GREEN            AMBER             RED
                    |                |                |
           screen dark/blank?   R2: shed load    R3: restart X  --->  R4: re-handshake HDMI
           -> R4 only           (then re-gauge)                       --->  R1: verify GREEN
```

### R0 · Pre-arm (do this while healthy, on Roach)

The one thing that worked in a freeze was a session that **already existed**. A fresh SSH login needs
sshd to fork, allocate and complete a key exchange, which is what failed 37 times between 7:02 and
7:17 AM. A multiplexed master connection skips all of that for every later command.

`~/.ssh/config` on Roach. *Not present today: Roach has no ControlMaster entry for JUPI (checked at
8:24 AM).*

```
Host jupi
    HostName <jupi-lan-ip>
    User pi
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist yes
    ServerAliveInterval 30
    ServerAliveCountMax 6
```

```
ssh -fN jupi                 # open the master once, in the background
ssh -O check jupi            # -> "Master running (pid=...)"
ssh jupi 'uptime'            # rides the master: no new login on JUPI
```

The reverse tunnel is a second way in that does not depend on JUPI's LAN address:
`ssh -p 22052 pi@127.0.0.1` on Roach (JUPI's `jupi-link@roach` forwards Roach's loopback 22052 to
JUPI's sshd). It still needs a fresh key exchange on JUPI, so it does **not** survive a freeze by
itself. Put a ControlMaster on it too if you use it.

### R1 · Read the gauge (30 seconds)

```
ssh jupi 'free -m; swapon --show
  g=/sys/class/drm/card0/device
  echo "GTT $(( $(cat $g/mem_info_gtt_used)/1048576 )) / $(( $(cat $g/mem_info_gtt_total)/1048576 )) MiB"
  ps -eo pid,rss,comm --sort=-rss | head -8'

ssh jupi "sudo awk '/^pid/{p=\$2\" \"\$4} /byte GTT/{s[p]+=\$2}
  END{for(k in s) printf \"%8.1f MiB  %s\n\", s[k]/1048576, k}' \
  /sys/kernel/debug/dri/0/amdgpu_gem_info | sort -rn | head -5"
```

Classify with the zone table (field manual §6.3). **RED = MemAvailable < 500 MiB or GTT > 2500 MiB or swap
> 90 %.** If Xorg is the top GTT holder in RED, go straight to **R3**.

### R2 · Shed load (AMBER)

Close heavy desktop apps gracefully first. Use the app's own quit if someone is at the screen, or:

```
ssh jupi 'pkill -TERM -x ChatGPT; sleep 10; pgrep -a -x ChatGPT || echo "ChatGPT closed"'
```

> **Caution. `grok-bot` is also a lane.** The Grok Bot desktop app on JUPI hosts a local-exec daemon
> (`~/.grokbot/local-exec-daemon*.json`). Closing it may cut that agent's access. Close it only
> knowingly.

**Expect:** app RSS comes back and swap drains a little. **The GTT does not.** If GTT stays above
~2500 MiB after the apps exit, the hold is in Xorg. Go to R3.

### R3 · Release the pin: restart the X session

> **WARNING — what this kills.** Everything in the graphical session: ChatGPT/Codex desktop, Grok Bot
> app, browser windows, XFCE terminals, unsaved work. Services (`jupi-agent`, `ollama`, `musegadget`,
> `sshd`, the SSH links) are **not** affected. Never run this as a reflex from an automated loop, and
> check nobody else already issued it. On Nov 10 two operators raced.

```
ssh jupi 'sudo systemctl restart lightdm'
```

Observed timing on Nov 10: issued 7:47:03 → stopped 7:47:28 → started 7:47:46 → pi autologin
7:49:27. **Allow about 2.5 minutes** before judging. Then:

```
ssh jupi 'systemctl is-active lightdm; pgrep -a Xorg; loginctl list-sessions --no-legend | grep -c .'
```

Then **always** run R4, because the panel will not come back by itself.

### R4 · Re-handshake the HDMI panel (after every X restart, or a black screen)

The panel reports **zero EDID bytes**, so after Xorg restarts it may not light up or may pick a wrong
mode. Force the mode explicitly. The X output is **`HDMI-A-0`**. (The kernel calls the same
connector `card0-HDMI-A-1`. Do not mix them up.)

```
ssh jupi 'export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
  xset dpms force on
  xset -dpms
  xset s off
  xrandr --output HDMI-A-0 --off
  xrandr --output HDMI-A-0 --mode 1920x1080 --rate 60 --primary
  xrandr --query | grep HDMI-A-0
  xset q | grep -E "DPMS is|timeout"'
```

**Expect:**

```
HDMI-A-0 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
  timeout:  0    cycle:  0
  DPMS is Disabled
```

`0mm x 0mm` is normal here (no EDID). If you get `Can't open display`, autologin has not finished
yet. Wait 60 s. Or use the server's own auth file as root:
`sudo env DISPLAY=:0 XAUTHORITY=/run/lightdm/root/:0 xrandr --output HDMI-A-0 --mode 1920x1080 --rate 60 --primary`.

Then re-run **R1**. **Expect:** GTT ≈ 30–40 MiB, MemAvailable > 3000 MiB, swap draining
(Nov 10: 4095 → 183 MiB in under 3 minutes).

### R5 · No login possible, ping still answers

Try in this order:

| | Path | Notes |
|---|---|---|
| **a** | Warm mux from R0 | `ssh -O check jupi` then `ssh jupi 'sudo systemctl restart lightdm'`, then R4 |
| **b** | Any session already open | e.g. a long-running `ssh` or tmux someone left attached. Use it for R3 |
| **c** | Gadget lane (Muse Home Link, node `homelink-3364d7`) | `musegadget` is an already-running root service that runs commands as `pi` (`system.run`, socket `/run/musegadget/musegadget.sock`). It needs no new SSH login. Whether it stays responsive in a deep freeze is **UNKNOWN** (not exercised on Nov 10). The exact client invocation is outside this manual |
| **d** | Keep retrying SSH at a slow cadence | On Nov 10 a login got through at ~7:46 AM after 45 min of pressure. Use `ConnectTimeout=25`. Do not run parallel retry loops from several machines, because they compete for the same sshd |
| **e** | Wait for earlyoom | Fires only when available ≤ ~276 MiB **and** swap free ≤ ~410 MiB. Kills ChatGPT / grok-bot / codex / llama-* first. **Cannot release Xorg's GTT**, so it buys minutes, not a fix |
| **f** | Local keyboard on JUPI | Only if the XFCE desktop still responds: open a terminal and run R3. **Ctrl+Alt+F*n* does nothing** (`-novtswitch`). **No SysRq** in this kernel |
| **g** | Power cycle: **LAST RESORT** | See the warning below |

> **WARNING — power cycling JUPI is not a reboot button.** Returning to Linux needs the console OS
> and the homebrew loader to run first (Section 3, steps 0–2). Unattended return after power loss is
> **not verified**. Someone must be physically at the PS4 and ready to launch the payload. A hard
> power cut also lands on a running ext4 image inside a UFS2 filesystem. Afterwards, run R6
> before trusting the box.

### R6 · After any reboot: prove you are on the right root

```
findmnt -no SOURCE,FSTYPE /          # expect: /dev/loop0 ext4
findmnt -no SOURCE,FSTYPE /ps4hdd    # expect: /dev/mapper/jupi-boot-internal ufs
losetup -l | grep jupi-linux         # expect: /ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img
uname -r                             # expect: 6.15.4-crashnt-4.7_no-built-in-fw
cat /proc/sys/kernel/random/boot_id  # new boot -> new id; record it
swapon --show                        # expect: zram1 zstd prio 200 + zram0 lz4 prio 100
sysctl vm.swappiness vm.page-cluster # expect: 100 / 0
systemctl is-active earlyoom jupi-agent musegadget sshd lightdm jupi-link@roach fclink
systemctl --failed --no-legend
```

> **If `/` is `/dev/sda2` (label *psxitarch*)** the selector fell back (rc 1). You are on the old
> USB-era system, not JUPI. Do not run JUPI installers or restore jobs against it. Note any
> `JUPI_INTERNAL_UNAVAILABLE_*` line from the boot console and stop for review.

### R7 · Undo the Nov 10 memory changes (only if instructed)

Every Nov 10 change was additive and has a rollback:

```
# review first
sed -n '1,80p' /home/pi/groku-wire/rollback-step1.sh
sha256sum /home/pi/groku-wire/rollback-step1.sh
#   expect 372417fcd4bdc09fbfb76d9b98c577ebc8add9348665cded87479c36ffef2303
bash /home/pi/groku-wire/rollback-step1.sh    # zram1, 90-groku sysctl, OOM drop-ins, earlyoom drop-in
sudo pacman -R earlyoom                         # removes the package itself
```

Pre-change copies: `/home/pi/groku-wire/backup-20261110T135318Z/`. Change log (hash-chained):
`/home/pi/groku-wire/CHANGES.md`.

### R8 · Housekeeping: the runaway log (current open issue)

`~/.xsession-errors` is growing ~175–183 KB/s (≈15 GB/day). The cause is ChatGPT's GPU process
looping on `SharedContextState::InitializeGL failure` (field manual §10.1). When an operator approves:

```
ssh jupi 'pkill -TERM -x ChatGPT'                 # stop the writer (see R2 caution)
ssh jupi 'truncate -s 0 ~/.xsession-errors; ls -l ~/.xsession-errors'
```

*Not executed while this manual was written. JUPI was kept read-only.*

### Quick card (cut out and keep)

```
 GAUGE   free -m ; GTT = /sys/class/drm/card0/device/mem_info_gtt_{used,total}
 RED     avail < 500 MiB | GTT > 2500 MiB | swap > 90 %
 FIX     sudo systemctl restart lightdm          (kills desktop apps, not services)
 THEN    export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
         xset dpms force on; xset -dpms; xset s off
         xrandr --output HDMI-A-0 --off
         xrandr --output HDMI-A-0 --mode 1920x1080 --rate 60 --primary
 VERIFY  GTT ~30-40 MiB, avail > 3000 MiB, "DPMS is Disabled", findmnt / = /dev/loop0
 NEVER   power-cycle as a first move; it needs a human at the console to come back
```
