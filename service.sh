#!/system/bin/sh
# Runs in late_start service mode, root, after boot.
MODDIR=${0%/*}

# Wait until system boot is fully completed
while [ "$(getprop sys.boot_completed 2>/dev/null)" != "1" ]; do
  sleep 2
done
# 轮询检测 sdcard 挂载，最多等 30 秒
for i in $(seq 1 15); do
  [ -d /storage/emulated/0 ] && break
  sleep 2
done

# Fix permissions
chmod 755 "$MODDIR/cleaner-daemon.sh" "$MODDIR/service.sh" "$MODDIR/webui/cgi-bin/api.cgi" 2>/dev/null

# Launch daemon detached
nohup sh "$MODDIR/cleaner-daemon.sh" >/dev/null 2>&1 &
