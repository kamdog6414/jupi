# Kernel memory held by dead memory cgroups (JUPI and JUPI 2), 2026-11-19

```
FINDING  Both consoles had ~5 GB of 6.9 GB held by the kernel itself, as
         unreclaimable slab plus per-CPU memory. The cause is ~100,000
         "dying" memory cgroups: cgroups whose units or sessions have exited
         but that the kernel has not freed.

                              JUPI 2 (PS4 Pro)   JUPI (PS4)
MemTotal                      6,904 MiB          6,904 MiB
SUnreclaim                    3,533 MiB          3,495 MiB
Percpu                        1,442 MiB          1,130 MiB
nr_dying_descendants          105,235            82,192
live cgroups                  72                 71
uptime at measurement         6 d 17 h           2 d 18 h
```

Source: /sys/fs/cgroup/cgroup.stat and /proc/meminfo. [M]
Cost: about 48 KB per dead cgroup ((3,536 + 1,443) MiB / 105k on JUPI 2).

## What creates them

Every transient unit or login session gets a cgroup. Unit start/finish events
in a 10-minute journal window:

```
JUPI 2   81   31 of them serial-getty@ttyS0 restarts
JUPI    265   50 serial-getty, 55 one network unit, ~10 each from observer timers
```

serial-getty@ttyS0 is spawned because the boot line has console=ttyS0. On
these consoles agetty fails every time ("failed to get terminal attributes:
Input/output error"), and systemd restarts it 100 ms later, forever. Restart
counters: 56,729 (JUPI 2), 22,008 (JUPI).

## What was tried

```
drop_caches 1 and 3      no effect. Dead cgroups +8 (JUPI 2) / +40 (JUPI),
                         Percpu and SUnreclaim unchanged. Page cache is not
                         what pins them. It also caused a ~7 min cold model
                         reload from the HDD.
mask serial-getty@ttyS0  growth per minute:
                         JUPI 2  11.8 -> 5.2 to 7.6
                         JUPI    19.8 -> 14.0 to 16.6
                         rollback: systemctl unmask + start
```

## Not yet tried

```
soft-reboot   systemd 262 supports `systemctl soft-reboot`. It keeps the
              kernel, so it probably does not free these [S]. One attended
              test is planned.
full reboot   frees them for certain. On these consoles it needs the
              console-side payload step, so it needs a person present.
```

No boot-line or kernel changes were made.
