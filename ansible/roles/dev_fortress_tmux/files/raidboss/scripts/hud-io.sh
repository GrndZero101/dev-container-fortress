#!/bin/sh
# hud-io.sh disk|net: disk IOPS and throughput, or network throughput,
# over one second, for tmux-raidboss's HUD line. tmux runs #() jobs in the
# background, so the one-second sample never blocks the status line.
#
# Linux only: it reads /proc. Elsewhere it prints nothing, so the module
# shows an empty pill instead of an error in the status line.
set -eu

# Bytes as 1024-based units, like free -h and htop
human() {
  awk -v b="$1" 'BEGIN {
    split("B K M G T", u); i = 1
    while (b >= 1024 && i < 5) { b /= 1024; i++ }
    printf((i == 1 || b >= 10) ? "%.0f%s" : "%.1f%s", b, u[i])
  }'
}

# Whole disks only. Partitions, device-mapper and md devices repeat I/O
# their disks already count; loop, ram, zram and optical drives are noise
disks() {
  for d in /sys/block/*; do
    case ${d##*/} in
      loop* | ram* | zram* | dm-* | md* | sr*) ;;
      *) printf '%s ' "${d##*/}" ;;
    esac
  done
}

# Prints "ios bytes". diskstats sectors are always 512 bytes
disk_sample() {
  awk -v list=" $wanted " 'index(list, " " $3 " ") {
    ios += $4 + $8; bytes += ($6 + $10) * 512
  } END { printf "%.0f %.0f\n", ios, bytes }' /proc/diskstats
}

# Prints "rx tx" in bytes. Virtual interfaces (containers, bridges) carry
# traffic the real interface also counts
net_sample() {
  awk 'NR > 2 {
    sub(/^ +/, ""); split($0, a, ":"); split(a[2], f, " ")
    if (a[1] !~ /^(lo|veth|docker|br-|virbr|cni|flannel)/) { rx += f[1]; tx += f[9] }
  } END { printf "%.0f %.0f\n", rx, tx }' /proc/net/dev
}

case ${1:-} in
  disk)
    [ -r /proc/diskstats ] || exit 0
    wanted=$(disks)
    ;;
  net) [ -r /proc/net/dev ] || exit 0 ;;
  *)
    printf 'usage: %s disk|net\n' "$0" >&2
    exit 2
    ;;
esac

# shellcheck disable=SC2046 # each sample is two numbers, split on purpose
set -- $("${1}_sample") "$1"
a1=$1 b1=$2 kind=$3
sleep 1
# shellcheck disable=SC2046 # as above
set -- $("${kind}_sample")
a=$(($1 - a1)) b=$(($2 - b1))

if [ "$kind" = disk ]; then
  printf '%s IOPS %s/s\n' "$a" "$(human "$b")"
else
  printf '↓%s/s ↑%s/s\n' "$(human "$a")" "$(human "$b")"
fi
