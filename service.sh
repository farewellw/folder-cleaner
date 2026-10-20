#!/system/bin/sh
MODDIR=${0%/*}
while [ "$(getprop sys.boot_completed 2>/dev/null)" != "1" ]; do
  sleep 5
done
sleep 15
nohup sh "$MODDIR/cleaner-daemon.sh" >/dev/null 2>&1 &
