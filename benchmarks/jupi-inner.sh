#!/bin/bash
# Runs ON JUPI (via ssh from Roach, or directly). Internal state snapshot.
echo "HOST $(hostname)"; date -Is
echo "BOOT $(cat /proc/sys/kernel/random/boot_id)"
uptime
grep -m1 "model name" /proc/cpuinfo
grep -E "MemTotal|MemAvailable" /proc/meminfo
echo "--- SENSORS ---"; sensors 2>/dev/null | head -10
echo "--- AMDGPU SYSFS NAMES ---"; ls /sys/class/drm/card0/device/ 2>/dev/null | grep -E "dpm|busy|clk|power|temp" 
echo "--- GPU BUSY ---"; cat /sys/class/drm/card0/device/gpu_busy_percent 2>/dev/null || echo "gpu_busy_percent absent"
echo "--- DPM SCLK ---"; cat /sys/class/drm/card0/device/pp_dpm_sclk 2>/dev/null || echo "pp_dpm_sclk absent"
echo "--- HWMON ---"; for h in /sys/class/drm/card0/device/hwmon/hwmon* /sys/class/hwmon/hwmon*; do [ -d "$h" ] && { echo "$h $(cat $h/name 2>/dev/null)"; for t in $h/temp*_input $h/freq*_input; do [ -f "$t" ] && echo "  $t = $(cat $t)"; done; }; done
echo "--- STORAGE ---"; df -h / /home/pi/ChatGPT/JUPI 2>/dev/null | tail -3; lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null | head -12
echo "--- OLLAMA PS ---"; curl -s http://127.0.0.1:11434/api/ps
echo; echo "INNER DONE"
