#!/bin/bash
# JUPI crypto top-up: the suite's combined openssl invocation aborted
# ("Unknown algorithm aes-256-gcm") on this build. Run each algorithm
# separately; probe what this openssl accepts. Writes OUT/crypto-topup.txt
set -u
OUT=/tmp/jupi-suite/OUT/crypto-topup.txt
{
echo "CRYPTO TOPUP $(date -Is)"
openssl version
echo "-- cipher algorithms containing aes/gcm --"
openssl list -cipher-algorithms 2>/dev/null | grep -iE "aes-256|gcm" | head -20
echo "-- sha256 --"
openssl speed -elapsed -seconds 3 sha256 2>&1 | tail -4
echo "-- aes-256-gcm via -evp --"
openssl speed -elapsed -seconds 3 -evp aes-256-gcm 2>&1 | tail -4
echo "-- aes-256-cbc --"
openssl speed -elapsed -seconds 3 aes-256-cbc 2>&1 | tail -4
echo "TOPUP DONE"
} > "$OUT" 2>&1
echo "topup written: $OUT"
