# 2026-11-25 maintenance supplement

This is portable source and a reproducible test set for two maintenance fixes:
safe trial-kernel file transactions, and read-only inspection of concatenated
`newc` initramfs archives. It is a local review supplement, with no installer,
service activation, package transaction, kernel installation or reboot command.
The original export's machine configuration and historical benchmarks remain
dated evidence.

## Run the portable checks

On Linux with Python 3, Bash, GNU coreutils and `flock`, from this directory:

```sh
bash -n jupi-trial-guard.sh
python3 -B -m unittest -v test_archive_sequence test_trial_transactions
```

The 18 archive tests construct synthetic archives in memory. They never open a
device, extract an archive, read an existing key or execute archive contents.
The supplement test uses a deliberately synthetic 32-byte value solely to
prove the strict writer's original-member preservation contract.

The 15 guard tests use owned temporary directories, explicit
`JUPI_TRIAL_NOMOUNT=1`, redirected boot/version files, and local command stubs.
They do not access mounted boot media, real services or a network. They test
file-transaction decisions. They do not prove FAT power-loss durability or that
a kernel was physically booted.

## Trial guard changes

`jupi-trial-guard.sh` preserves the `arm`, `check`, `revert` and `status`
interfaces. Important failure behavior now has explicit coverage:

- A trial armed during the current boot waits for a distinct boot and cannot
  earn `PASSED` by inspecting the old running kernel.
- Failed image staging or pending-record commit preserves the prior selection.
  Failed activation leaves the pending transaction and recovery copy available.
- An authoritative content-sealed boot record binds the trial digest, observed
  boot ID and count. Its diagnostic numeric mirror must agree. An incomplete
  update holds for inspection; it cannot be retried into an approval.
- A second trial boot is reverted before updating the observed boot record.
  This closes an independently reproduced defect where an ID-only commit plus
  a failed counter replacement made a retry look like the first trial boot.
- A durable terminal receipt can reconcile interrupted cleanup. A truncated or
  hash-invalid receipt cannot approve a pending trial.
- File names cannot alias `bzImage` or the guard's `TRIAL*` state on FAT through
  case changes or trailing dots. Canonical device and filesystem identity are
  rechecked around live mount operations.

The published peer default is the RFC 5737 documentation address `192.0.2.3`.
An operator must provide their own trusted configuration before using this on
real media. This source is not a generic PS4 boot solution. It contains no
reboot, driver reset or controller operation. Its health check retains the
existing conservative whole-boot fault-log policy.

## Archive inspection changes

`boot_archive.py` is the unchanged strict single-archive parser and supplement
writer. `audit_sequence.py` contains the exact audit-only function extracted
from the native boot manager, with explicit `stat` and `boot_archive` imports
so it works as an independent module. Tests import that actual module; the
host-bound boot manager is not copied.

The audit helper accepts a bounded sequence of complete `newc` archives,
selects later duplicate paths as effective entries, and rejects unsafe paths,
malformed trailers, hard-linked files, count overflow and trailing junk. The
original strict writer still rejects concatenated archives. The caller must
separately check required selector metadata and compare configured digests;
the helper alone does not certify a boot selector or boot a machine.

## Scope and source lineage

`SOURCE-LINEAGE.json` records source digests and the single guard redaction.
The reviewed native guard source passed 48 owned-loopback FAT fault cases,
with all filesystems clean under read-only checking. That qualification used
mocked health and injected command failures; it did not involve either PS4
booting. The published guard has a different digest because its peer default
was sanitized. It was checked separately with the portable transaction tests
above. The native FAT result must not be represented as a FAT run of these
different published bytes.

The maintenance session also repaired a native health self-latch without
editing the boot-pinned original CLI, and prepared graphics package holds from
each model's actual package ownership and ABI evidence. Those changes depend
on a source-pinned per-host status reader and model-specific installed stack.
They are not imported here as a new generic reader, live configuration or
installation recipe. An intentional protected device hold must remain visible
without being mistaken for a missing core service. Genuine root, SSH, memory,
boot-asset and other-service failures must remain failures.

CPU affinity and memory controls must be distinguished from unsupported CPU
bandwidth quotas. A unit's `CPUQuota=` declaration is not evidence that its
custom kernel enforces it. The two console models also have different service
sets and graphics dependencies; copying one model's runtime profile onto the
other is not qualified by this supplement.

No cold-boot, USB-absent boot, kexec or physical-robot qualification is promoted.
No historical performance result is rewritten. No operational receipts, live
configuration, private keys, archives, media images or lab addresses are part
of this supplement.
