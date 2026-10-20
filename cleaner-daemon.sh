#!/system/bin/sh
# 守护进程主循环（单目录 + 多配置切换版）
DATA_DIR=/data/adb/folder-cleaner
CONFIG=$DATA_DIR/config.conf
PROFILES=$DATA_DIR/profiles.conf
PIDFILE=$DATA_DIR/daemon.pid
LOGFILE=$DATA_DIR/cleaner.log
CLEANLOG=$DATA_DIR/cleanup.log

# 找 busybox
BB=""
for b in \
  /data/adb/magisk/busybox \
  /data/adb/ksu/bin/busybox \
  /data/adb/ap/bin/busybox \
  /system/bin/busybox \
  /system/xbin/busybox; do
  [ -x "$b" ] && BB="$b" && break
done
[ -z "$BB" ] && BB=busybox

echo $$ > "$PIDFILE"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOGFILE"; }

mkdir -p "$DATA_DIR" 2>/dev/null
[ -f "$LOGFILE" ] || touch "$LOGFILE"
[ -f "$CLEANLOG" ] || touch "$CLEANLOG"

# 初始化配置（不再自动创建默认配置，由用户手动新建）
[ -f "$CONFIG" ] || echo "ACTIVE_PROFILE=" > "$CONFIG"
[ -f "$PROFILES" ] || echo -n "" > "$PROFILES"

load_config() {
  . "$CONFIG"
  [ -z "$PORT" ] && PORT=8899
  WATCH_DIR=""
  THRESHOLD_GB=0
  INTERVAL_SEC=0
  KEEP_GB=0
  if [ -f "$PROFILES" ]; then
    while IFS='|' read -r name wd tg iv kg; do
      if [ "$name" = "$ACTIVE_PROFILE" ]; then
        WATCH_DIR="$wd"
        THRESHOLD_GB="$tg"
        INTERVAL_SEC="$iv"
        KEEP_GB="${kg:-0}"
        break
      fi
    done < "$PROFILES"
  fi
}

dir_size() {
  $BB du -sb "$1" 2>/dev/null | awk '{print $1}'
}

cleanup() {
  dir="$1"
  threshold_gb="$2"
  keep_gb="$3"
  [ -z "$keep_gb" ] && keep_gb=0
  threshold_bytes=$(awk -v g="$threshold_gb" 'BEGIN{printf "%.0f", g*1073741824}')
  keep_bytes=$(awk -v g="$keep_gb" 'BEGIN{printf "%.0f", g*1073741824}')
  [ "$threshold_bytes" -eq 0 ] && return 0
  current=$(dir_size "$dir")
  log "检查 $dir: 当前 ${current}, 阈值 ${threshold_bytes}, 保留 ${keep_bytes}"

  over=$(awk -v c="$current" -v t="$threshold_bytes" 'BEGIN{print (c>t)?1:0}')
  if [ "$over" -eq 0 ]; then return 0; fi

  target_bytes=$threshold_bytes
  if [ "$keep_bytes" -gt 0 ]; then target_bytes=$keep_bytes; fi

  tmpfiles="$DATA_DIR/.files.tmp"
  $BB find "$dir" -type f ! -name ".*" 2>/dev/null | while IFS= read -r f; do
    case "$f" in *.nomedia) continue ;; esac
    sz=$($BB stat -c %s "$f" 2>/dev/null)
    [ -z "$sz" ] && sz=0
    mt=$($BB stat -c %Y "$f" 2>/dev/null)
    echo "${mt}|${sz}|${f}"
  done | sort -n > "$tmpfiles"

  freed=0
  deleted_count=0
  deleted_files=""
  while IFS='|' read -r mt sz fpath; do
    cur=$(dir_size "$dir")
    still_over=$(awk -v c="$cur" -v t="$target_bytes" 'BEGIN{print (c>t)?1:0}')
    [ "$still_over" -eq 0 ] && break
    rm -f "$fpath" 2>/dev/null
    [ $? -eq 0 ] && {
      freed=$(awk -v a="$freed" -v b="$sz" 'BEGIN{print a+b}')
      deleted_count=$((deleted_count + 1))
      fname=$(basename "$fpath")
      if [ -n "$deleted_files" ]; then deleted_files="${deleted_files},"; fi
      deleted_files="${deleted_files}{\"name\":\"${fname}\",\"size\":${sz}}"
      log "已删除: $fpath (${sz}B)"
    }
  done < "$tmpfiles"
  rm -f "$tmpfiles" 2>/dev/null

  if [ "$deleted_count" -gt 0 ]; then
    new_size=$(dir_size "$dir")
    summary="$(date '+%Y-%m-%d %H:%M:%S') 从 $dir 清理 $deleted_count 个文件, 释放 ${freed}B, 剩余 ${new_size}B"
    log "$summary"
    echo "{\"time\":\"$(date '+%Y-%m-%d %H:%M:%S')\",\"path\":\"$dir\",\"deleted\":$deleted_count,\"freedBytes\":$freed,\"remainBytes\":$new_size,\"files\":[${deleted_files}]}" >> "$CLEANLOG"
  fi
}

start_httpd() {
  killall httpd 2>/dev/null
  MODDIR=/data/adb/modules/folder_cleaner
  chmod 755 "$MODDIR/webui/cgi-bin/api.cgi" 2>/dev/null
  cd "$MODDIR/webui" || exit 1
  nohup /data/adb/ksu/bin/busybox httpd -p "$PORT" -h "$MODDIR/webui" 2>/dev/null &
  log "Web UI 已启动端口 $PORT"
}

load_config
start_httpd
log "守护进程启动 (profile=$ACTIVE_PROFILE, dir=$WATCH_DIR, interval=${INTERVAL_SEC}s)"

last_hash=""
next_clean=$(date +%s)
while true; do
  sleep 2
  cur_hash=$(cat "$CONFIG" "$PROFILES" 2>/dev/null | md5sum | awk '{print $1}')
  if [ "$cur_hash" != "$last_hash" ]; then
    load_config
    log "配置已变更，重新加载 (profile=$ACTIVE_PROFILE, dir=$WATCH_DIR, interval=${INTERVAL_SEC}s)"
    last_hash="$cur_hash"
    next_clean=$(date +%s)
  fi

  if [ -z "$WATCH_DIR" ] || [ ! -d "$WATCH_DIR" ]; then sleep 5; continue; fi

  if [ -f "$DATA_DIR/force_clean" ]; then
    rm -f "$DATA_DIR/force_clean"
    log "手动触发清理"
    cleanup "$WATCH_DIR" "$THRESHOLD_GB" "$KEEP_GB"
    next_clean=$(($(date +%s) + INTERVAL_SEC))
  fi

  now=$(date +%s)
  if [ "$now" -ge "$next_clean" ]; then
    cleanup "$WATCH_DIR" "$THRESHOLD_GB" "$KEEP_GB"
    next_clean=$(($(date +%s) + INTERVAL_SEC))
  fi
done
