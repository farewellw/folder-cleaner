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

# 迁移：旧版 default 改名为 默认，清空监听目录
if [ -f "$PROFILES" ] && $BB grep -q '^default|' "$PROFILES" 2>/dev/null; then
  tmpf="$DATA_DIR/profiles.tmp"
  > "$tmpf"
  while IFS='|' read -r name wd tg iv kg; do
    if [ "$name" = "default" ]; then
      echo "默认||${tg:-0}|${iv:-0}|${kg:-0}" >> "$tmpf"
    else
      echo "${name}|${wd}|${tg}|${iv}|${kg}" >> "$tmpf"
    fi
  done < "$PROFILES"
  mv "$tmpf" "$PROFILES" 2>/dev/null
  # 同步 config.conf
  if [ -f "$CONFIG" ] && $BB grep -q 'ACTIVE_PROFILE=default' "$CONFIG" 2>/dev/null; then
    sed -i 's/ACTIVE_PROFILE=default/ACTIVE_PROFILE=默认/' "$CONFIG"
  fi
  log "已迁移: default → 默认，监听目录已清空"
fi

load_config() {
  . "$CONFIG"
  [ -z "$PORT" ] && PORT=8899
  WATCH_DIR=""
  THRESHOLD_GB=50
  INTERVAL_SEC=60
  KEEP_GB=0
  # 只有存在已激活的配置时才填充，否则 WATCH_DIR 保持为空（守护进程不清理任何目录）
  if [ -n "$ACTIVE_PROFILE" ] && [ -f "$PROFILES" ]; then
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
  [ -z "$THRESHOLD_GB" ] && THRESHOLD_GB=50
  [ -z "$INTERVAL_SEC" ] && INTERVAL_SEC=60
  [ -z "$KEEP_GB" ] && KEEP_GB=0
}

# 计算目录总大小（字节），用 awk 避免 32 位溢出
dir_size() {
  $BB du -sb "$1" 2>/dev/null | awk '{print $1}'
}

# 清理函数：删除最旧文件直到降到保留值
cleanup() {
  dir="$1"
  threshold_gb="$2"
  keep_gb="$3"
  [ -z "$keep_gb" ] && keep_gb=0
  threshold_bytes=$(awk -v g="$threshold_gb" 'BEGIN{printf "%.0f", g*1073741824}')
  keep_bytes=$(awk -v g="$keep_gb" 'BEGIN{printf "%.0f", g*1073741824}')
  # 阈值为0表示不启用清理
  [ "$threshold_bytes" -eq 0 ] && return 0
  current=$(dir_size "$dir")
  log "检查 $dir: 当前 ${current}, 阈值 ${threshold_bytes}, 保留 ${keep_bytes}"

  over=$(awk -v c="$current" -v t="$threshold_bytes" 'BEGIN{print (c>t)?1:0}')
  if [ "$over" -eq 0 ]; then
    return 0
  fi

  # 如果 keep_bytes=0，删到阈值以下；否则删到 keep_bytes 以下
  target_bytes=$threshold_bytes
  if [ "$keep_bytes" -gt 0 ]; then
    target_bytes=$keep_bytes
  fi

  # 收集文件列表：修改时间|大小|路径，跳过隐藏文件和白名单后缀
  tmpfiles="$DATA_DIR/.files.tmp"
  $BB find "$dir" -type f ! -name ".*" 2>/dev/null | while IFS= read -r f; do
    # 白名单后缀：这些文件永远不删
    case "$f" in
      *.nomedia|*.nomedia) continue ;;
    esac
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
      if [ -n "$deleted_files" ]; then
        deleted_files="${deleted_files},"
      fi
      deleted_files="${deleted_files}{\"name\":\"${fname}\",\"size\":${sz}}"
      log "已删除: $fpath (${sz}B)"
    }
  done < "$tmpfiles"
  rm -f "$tmpfiles" 2>/dev/null

  if [ "$deleted_count" -gt 0 ]; then
    new_size=$(dir_size "$dir")
    summary="$(date '+%Y-%m-%d %H:%M:%S') 从 $dir 清理 $deleted_count 个文件, 释放 ${freed}B, 剩余 ${new_size}B"
    log "$summary"
    # 写清理记录 JSON（含来源目录和文件列表）
    echo "{\"time\":\"$(date '+%Y-%m-%d %H:%M:%S')\",\"path\":\"$dir\",\"deleted\":$deleted_count,\"freedBytes\":$freed,\"remainBytes\":$new_size,\"files\":[${deleted_files}]}" >> "$CLEANLOG"
  fi
}

# 启动 Web UI
start_httpd() {
  killall httpd 2>/dev/null
  MODDIR=/data/adb/modules/folder_cleaner
  chmod 755 "$MODDIR/webui/cgi-bin/api.cgi" 2>/dev/null
  cd "$MODDIR/webui" 2>/dev/null || { log "警告: WebUI 目录不存在: $MODDIR/webui"; return 1; }
  # 使用探测到的 busybox 启动 httpd（不再写死 KSU 路径）
  HTTPD_BIN="$BB"
  [ -z "$HTTPD_BIN" ] || [ ! -x "$HTTPD_BIN" ] && HTTPD_BIN=busybox
  if [ -x "$HTTPD_BIN" ] || command -v "$HTTPD_BIN" >/dev/null 2>&1; then
    nohup "$HTTPD_BIN" httpd -p "$PORT" -h "$MODDIR/webui" >/dev/null 2>&1 &
    log "Web UI 已启动端口 $PORT ($HTTPD_BIN)"
  else
    log "警告: 未找到可用的 httpd (busybox)，Web UI 无法启动，请安装 BusyBox"
  fi
}

# 首次加载
load_config
start_httpd
log "守护进程启动 (profile=$ACTIVE_PROFILE, dir=${WATCH_DIR:-(未设置)}, interval=${INTERVAL_SEC}s)"

# 记录上次配置哈希，用于检测变更
last_hash=""
next_clean=$(date +%s)
while true; do
  sleep 2
  cur_hash=$(cat "$CONFIG" "$PROFILES" 2>/dev/null | md5sum | awk '{print $1}')
  if [ "$cur_hash" != "$last_hash" ]; then
    load_config
    log "配置已变更，重新加载 (profile=$ACTIVE_PROFILE, dir=${WATCH_DIR:-(未设置)}, interval=${INTERVAL_SEC}s)"
    last_hash="$cur_hash"
    next_clean=$(date +%s)
  fi

  # 路径检查：为空或不存在时跳过清理
  if [ -z "$WATCH_DIR" ] || [ ! -d "$WATCH_DIR" ]; then
    sleep 5
    continue
  fi

  # 强制清理信号
  if [ -f "$DATA_DIR/force_clean" ]; then
    rm -f "$DATA_DIR/force_clean"
    log "手动触发清理"
    cleanup "$WATCH_DIR" "$THRESHOLD_GB" "$KEEP_GB"
    next_clean=$(($(date +%s) + INTERVAL_SEC))
  fi

  # 定时清理（短循环轮询，配置变更后立即生效）
  now=$(date +%s)
  if [ "$now" -ge "$next_clean" ]; then
    cleanup "$WATCH_DIR" "$THRESHOLD_GB" "$KEEP_GB"
    next_clean=$(($(date +%s) + INTERVAL_SEC))
  fi
done
