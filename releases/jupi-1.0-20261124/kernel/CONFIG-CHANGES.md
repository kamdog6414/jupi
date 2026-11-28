# jupi-1.0 config vs the live kernel (groku, Nov 24 2026)

Base: the live kernel's embedded config (`pidfs-embedded.config`, sha256 946438262aba...ddef, same on JUPI 1 and JUPI 2).
Full diff: `artifacts/config-diff-vs-live.txt` (19 lines). Rule used: nothing may change runtime behavior unless Kam turns it on.

| Change | Why | Default at runtime | Turn on with | Risk |
|---|---|---|---|---|
| CONFIG_PSI=y, CONFIG_PSI_DEFAULT_DISABLED=y | Pressure stall info (CPU/memory/IO) for agent admission and for a better swap gate than "swap > 25%". Codex's review lists it first. | OFF (static key, /proc/pressure absent) | boot arg `psi=1` | Low. Small scheduler-path cost only when on (not measured on Jaguar). |
| CONFIG_CPUSETS=y (CPUSETS_V1 off) | cgroup v2 cpuset controller, so units can be placed off CPU 1 (JUPI 1) or pinned per workload (Codex measured different best masks per console). | Unused until a unit sets AllowedCPUs= (none do today, checked on both) | `AllowedCPUs=` in a unit | Low. |
| CONFIG_LRU_GEN=y, LRU_GEN_ENABLED off, LRU_GEN_STATS off | Multi-gen LRU reclaim as a memory/zram experiment for mixed local workloads. | OFF (`/sys/kernel/mm/lru_gen/enabled` = 0x0000) | `echo y > /sys/kernel/mm/lru_gen/enabled` (root) | Low. Gain UNSOURCED on these boxes. |
| CONFIG_LRU_GEN_WALKS_MMU=y, CONFIG_UNION_FIND=y | Pulled in automatically by the two above (olddefconfig). | n/a | n/a | none |

Unchanged on purpose: kernel.release (`6.15.4-crashnt-4.7_no-built-in-fw`), HZ=1000, PREEMPT_DYNAMIC, mitigations (already off), THP always, zram/zswap, I/O schedulers, amdgpu, SKY2/MWIFIEX built in, firmware set (10 files, verified identical).

## Held (behavior-changing; Kam decides)
| Option | What would change | Evidence |
|---|---|---|
| CFS_BANDWIDTH | JUPI 1's CPUQuota= lines start enforcing: ollama capped to 3 cores, jupi-agent to 2, jupi-observe to 0.5. | CONFIRMED unit lines today |
| CGROUP_BPF | systemd IPAddressDeny/Allow and BPF device rules start enforcing (journald and others ship them; jupi-agent/jupi-observe units carry related directives). Could cut a link if a rule is wrong. | CONFIRMED journald warning on both |
| USB_ACM / USB_SERIAL | Serial console via USB adapter for supervised boots. Would also bind any CDC-ACM gadget plugged in (the Muse Home Link is ESP32-C5 based; whether it exposes CDC-ACM: UNSOURCED). | — |
| IRQ_TIME_ACCOUNTING | More honest IRQ/softirq time numbers; also changes task runtime accounting. | — |
| kernel.release rename to `-jupi-1.0` | JUPI 1 boot audit (`qualified_kernel_release_matches`), warm-boot bundle gate and perf-profile drift all compare `uname -r` to /etc/jupi/boot.json. A rename makes them fail until boot.json is updated. | CONFIRMED in /usr/local/lib/jupi-agent/{boot_manager,warm_boot_bundle,performance_profile}.py |
