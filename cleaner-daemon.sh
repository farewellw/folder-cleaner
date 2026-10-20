#!/system/bin/sh
MODDIR=${0%/*}
DATA_DIR=/data/adb/folder-cleaner
CONFIG=$DATA_DIR/config.conf
PIDFILE=$DATA_DIR/daemon.pid
LOGFILE=$DATA_DIR/cleaner.log
CLEANLOG=$DATA_DIR/cleanup.log
FORCE_FLAG=$DATA_DIR/force_clean
mkdir -p "$DATA_DIR"
BB=""
for b in /data/adb/magisk/busybox /data/adb/ksu/bin/busybox /system/bin/busybox /system/xbin/busybox; do
  [ -x "$b" ] && BB="$b" && break
done
[ -z "$BB" ] && BB=busybox
if [ -f "$PIDFILE" ]; then
  oldpid=$(cat "$PIDFILE" 2>/dev/null)
  if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then exit 0; fi
fi
echo $$ > "$PIDFILE"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOGFILE"; }
json_escape() { echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
cleanlog() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$CLEANLOG"; }
