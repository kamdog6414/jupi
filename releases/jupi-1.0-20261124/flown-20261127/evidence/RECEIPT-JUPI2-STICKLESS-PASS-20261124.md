# RECEIPT: JUPI 2 stickless HDD boot of jupi-1.0 — PASS
Tue Nov 24 2026 evening PST. Watch authorized by pt3890u ("Expect Jupi 2 within 30 seconds"). Read-only; no writes, no guard status, JUPI 1 was not shut down by groku. - groku

## Verdict: PASS (CONFIRMED)
JUPI 2 booted #jupi-1.0 from the internal HDD with the stick out. Root is loop0 proroot. The stick is absent from lsblk (no sdb, no PS4PROBIN). eth0 is up at 1000 Mbps full and pings Roach. dmesg is clean. The 5-minute recheck matched.

## Times (America/Los_Angeles, PST)
- Watch started 19:33:21 PST. Direct ping/SSH to <lab-ip> and <lab-ip> were down; the JUPI 2 ssh path was not yet up.
- First SSH: 19:33:45 PST, via the lab reverse tunnel on Roach, not via a direct route to <lab-ip>. uname already `#jupi-1.0`.
- Clock note: the first `uptime -s` printed 19:25:57 (before NTP). After `System clock synchronized: yes`, `uptime -s` is 19:32:54 and `/proc/uptime` at 19:34:06 was 71.72 s, which agrees. Boot time: 19:32:54 PST (CONFIRMED).
- First full verify: 19:34:07 PST, ~73 s up, script rc 0.
- 5-minute recheck: 19:38:08 PST, 5 min up, script rc 0.

## Key values (first verify, reconfirmed at 5 min unless noted)
- uname -v: `#jupi-1.0 SMP PREEMPT_DYNAMIC Tue Nov 24 15:26:06 PST 2026`
- uname -r: `6.15.4-crashnt-4.7_no-built-in-fw`
- /proc/cmdline: the payload default, no `sky2.aeolia_poll_phy` (correct for Belize)
- root: `/dev/loop0` ext4 LABEL=proroot
- /ps4hdd: `/dev/mapper/pro-boot-internal` ufs2 rw
- lsblk: internal HGST sda only; no 149G sdb, no PS4PROBIN (CONFIRMED stick out). uname is also proof: a stick-in boot would have been pidfsfix `#1 … Nov 20`.
- HDD files still: bzImage `a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e`, initramfs `53dfd78b1402caf05568968b6ba5bf37c8cb8f773fb1792f2aedc8736e527cd7`
- eth0: operstate=up, carrier=1, 1000 Mbps full; addresses <lab-ip> and <lab-ip>; mlan0 <lab-ip> up. tailscale <tailnet-ip> present by the 5-min check.
- ping Roach <lab-ip>: 5/5, ~1.5–1.7 ms, both checks
- dmesg: no Oops/BUG/nobody cared/Disabling IRQ/ufs error. sky2: Link is up at 34.7 s. No `jupi: Aeolia PHY poll mode` line (poll stays off on Belize).
- systemctl --failed: empty
- IRQ 24 (eth0) ~2/s at 19:35:08; IRQ 18 = 0/s. CPU 1 softirq not stuck.
- load: 4.71 at 1 min (normal boot), 0.25 at 5 min, 0.07 at 8 min. At 5 min, 5 s of /proc/stat showed 0 new softirqs.

## Direct path from Roach (observation, not a fail)
Roach could not ping <lab-ip> or <lab-ip> even after eth0 held those addresses. SSH worked through the always-on reverse tunnel. JUPI 2 could ping Roach. This is OBSERVED and was already true at first contact; it did not block the verify. Before the shutdown, Roach could ping <lab-ip>, so the direct path is different this boot. Not investigated further (read-only brief).

## JUPI 1 during this watch (not shut down by groku; report only)
- 19:34:33 PST: JUPI 1 SSH still up, `#jupi-1.0`, up 1 h 21 m. (CONFIRMED)
- 19:38:13 PST: SSH to JUPI 1 from Roach timed out during the 5-min JUPI 2 recheck.
- 19:38:33–19:38:50: all Roach access paths down. Tailscale: offline, last seen ~1 min earlier. (OBSERVED)
- 19:39:24: from JUPI 2, ping <lab-ip> failed, ARP FAILED. (CONFIRMED)
- 19:39:42–19:39:52: pair-link ping to <lab-ip> came back, 0.4 ms, MAC <mac> (JUPI 1's eth0). SSH to port 22: Connection refused. (CONFIRMED)
- 19:40:07–19:40:31: still refused; 19:40:39 timeout; 19:40:52 no route.
- 19:41:14: pair-link ping failed again, ARP FAILED. Tailscale still offline. JUPI 2 itself still healthy (8 min up). (CONFIRMED)

Groku issued no shutdown or writes on JUPI 1. The box answered ICMP briefly with the right MAC, then dropped off again, and sshd never accepted a login. Kam should check the JUPI 1 light and screen. I have not touched it.

## Files
jupi2-stickless-watch.log, jupi2-stickless-verify-1.txt, jupi2-stickless-verify-5min.txt, this receipt.
