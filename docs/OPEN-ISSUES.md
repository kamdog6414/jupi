# JUPI known open issues

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 10. Known open issues

Ordered by operational risk. None of these were changed while writing this manual.

### 10.1 Runaway `~/.xsession-errors` (ACTIVE)

```
 8:08 AM   183,732,736 B
 8:09 AM   +5,491,898 B / 30 s   (~183 KB/s, ~15.8 GB/day)   watch window 8:09:13-8:09:43
 8:24 AM   357,581,223 B          (~175 KB/s over 16.5 min)
 writer    ChatGPT --type=gpu-process (pid 346148), repeating:
           SharedContextState::InitializeGL failure driver error : 33364
           ContextResult::kFatalFailure: Failed to Initialize GL for SharedContextState
           GpuChannel: Failed to create SharedImageStub
```

Memory is otherwise fine (≈3.1 GB available, GTT flat ≈30 MiB). Disk is the slow fuse. The log
lands in the root image, so it eats the sparse image's real blocks *and* the UFS backing (333 GiB
free). That gives weeks, not hours, but it never stops on its own.

**Correlated kernel events (hypothesis):** right after the 7:47 AM X restart the kernel logged
`amdgpu: GPU reset(20) failed`, `GPU reset(21) failed`, `GPU Recovery Failed`,
`asic atom init failed!` and repeated DisplayPort link-training failures (7:50–7:51 AM). A GPU left
in a partly recovered state would explain an Electron GPU process that can no longer create a GL
context. **UNKNOWN** whether desktop GL works for other clients right now. Fix path: Runbook R8 (stop
the writer, truncate). Whether a full GPU recovery needs a kernel reboot, with its cold-boot
caveats, is **UNKNOWN**.

### 10.2 The GTT pin can recur

Nothing on JUPI watches GTT. earlyoom watches RAM and swap only, and it avoids Xorg. With ChatGPT,
Codex and Grok Bot all running, expect the climb to repeat over hours to days. **Mitigation:** the
gauge (6.3) on a schedule, plus the DESKTOP/COMPUTE discipline (6.4). *A GTT watch timer would be a
natural next addition. It is proposed here and not built.*

### 10.3 No warm way in

Roach has no ControlMaster/ControlPersist entry for JUPI (checked 8:24 AM). The next freeze will
hit the same wall as 7:02–7:17 AM unless R0 is done first.

### 10.4 No local escape hatch

Xorg runs with `-novtswitch`, the kernel has no SysRq, and the ttyS0 UART is not initialized. A wedged
desktop at the console has no keyboard-only way out.

### 10.5 Power loss is not self-healing

`cold_boot_verified: false` in every receipt. Return to Linux needs the console OS plus the homebrew
loader. Treat JUPI as **must-not-lose-power** until an unattended path is proven.

### 10.6 Possible silent fallback to the USB root

The selector waits 5 s. In the rescue era the HDD bridge appeared at 6.65 s. If it is late, rc 1
boots the old USB root quietly. After any reboot, check `findmnt /` (R6).

### 10.7 Smaller items

| Item | Detail |
|---|---|
| Observer timeouts | jupi-nerves 201, host-watch 196, observe 45, knowledge 16, health 16 timeouts since Nov 9 7:54 AM; `jupi-health.service` failed at scan |
| HDMI EDID = 0 bytes | panel reports `0mm x 0mm`; mode must be forced after each X restart (R4) |
| No `IgnorePkg` | `mesa-ps4`, `xf86-video-amdgpu-ps4` not fenced from a blanket `pacman -Syu` |
| Baseline drift | earlyoom (and zram1, sysctl 90-groku) differ from the `jupi-profile` pinned baseline |
| Stale comment | `90-groku.conf` says "USB loop root". The root is the HDD loop |
| Unreclaimable slab | 1.15 GiB SUnreclaim at scan, cause **UNKNOWN** |
| Kernel source this boot | USB `PS4BOOT` copy vs HDD copy: **UNKNOWN** |
| `systemd-coredump@0-4100-327613-0` | failed unit left over from a core dump. Which process crashed is not in the scan (**UNKNOWN**) |
