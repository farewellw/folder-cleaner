#!/system/bin/sh
DATA_DIR=/data/adb/folder-cleaner
CONFIG=$DATA_DIR/config.conf
LOGFILE=$DATA_DIR/cleaner.log
CLEANLOG=$DATA_DIR/cleanup.log
BB=""
for b in /data/adb/magisk/busybox /data/adb/ksu/bin/busybox /system/bin/busybox /system/xbin/busybox; do
  [ -x "$b" ] && BB="$b" && break
done
[ -z "$BB" ] && BB=busybox
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo ""
q="$QUERY_STRING"
urldecode() { local s="$1"; s=$(printf '%b' "$(echo "$s" | sed 's/+/ /g; s/%/\\x/g')"); echo "$s"; }
get_param() { echo "$q" | tr '&' '\n' | grep "^$1=" | head -n1 | cut -d= -f2-; }
json_escape() { echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
action=$(get_param action)
case "$action" in
  status)
    . "$CONFIG" 2>/dev/null
    cur=$($BB du -sb "$WATCH_DIR" 2>/dev/null | awk '{print $1}')
    [ -z "$cur" ] && cur=0
    dt=$($BB df -B1 /sdcard 2>/dev/null | awk 'NR==2 {print $2}')
    df=$($BB df -B1 /sdcard 2>/dev/null | awk 'NR==2 {print $4}')
    printf '{"watchDir":"%s","thresholdGb":%s,"intervalSec":%s,"port":%s,"currentBytes":%s,"diskTotal":%s,"diskFree":%s}\n' "$(json_escape "$WATCH_DIR")" "$THRESHOLD_GB" "$INTERVAL_SEC" "$PORT" "$cur" "$dt" "$df"
    ;;
  save)
    wd=$(urldecode "$(get_param watchDir)")
    tg=$(get_param thresholdGb); iv=$(get_param intervalSec); po=$(get_param port)
    [ -z "$tg" ] && tg=50; [ -z "$iv" ] && iv=60; [ -z "$po" ] && po=8899
    case "$tg$iv$po" in *[!0-9]*|'') tg=50; iv=60; po=8899 ;; esac
    [ "$tg" -lt 1 ] && tg=1; [ "$iv" -lt 10 ] && iv=10
    case "$wd" in /system/*|/data/*|/sdcard/Android/*|/storage/emulated/*) printf '{"ok":false,"error":"受保护路径"}\n'; exit 0 ;; esac
    cat > "$CONFIG" <<EOF
WATCH_DIR=$wd
THRESHOLD_GB=$tg
INTERVAL_SEC=$iv
PORT=$po
EOF
    chmod 0644 "$CONFIG"
    printf '{"ok":true}\n'
    ;;
  clean)
    touch "$DATA_DIR/force_clean"
    printf '{"ok":true,"msg":"已触发清理"}\n'
    ;;
  test)
    mode=$(get_param mode); . "$CONFIG" 2>/dev/null; WD="$WATCH_DIR"; [ -z "$WD" ] && WD=/sdcard/Test
    mkdir -p "$WD" 2>/dev/null
    case "$mode" in
      small) echo A > "$WD/t_a.txt"; echo B > "$WD/t_b.txt"; echo C > "$WD/t_c.txt"; printf '{"ok":true,"msg":"3个小文件"}\n";;
      big) dd if=/dev/zero of="$WD/test_big.img" bs=1024 count=2097152 2>/dev/null; printf '{"ok":true,"msg":"2GB大文件"}\n";;
      mixed) echo v > "$WD/t_v.mp4"; echo i > "$WD/t_i.jpg"; echo a > "$WD/t_a.mp3"; echo d > "$WD/t_d.txt"; printf '{"ok":true,"msg":"混合文件"}\n";;
      clear) find "$WD" -mindepth 1 -delete 2>/dev/null; printf '{"ok":true,"msg":"已清空"}\n";;
      *) printf '{"ok":false,"error":"未知模式"}\n";;
    esac
    ;;
  log)
    tail -n 40 "$LOGFILE" 2>/dev/null | awk 'BEGIN{printf "["} {gsub(/\\/,"\\\\");gsub(/"/,"\\\"");if(NR>1)printf ",";printf "\"%s\"",$0} END{print "]"}'
    ;;
  cleanup)
    if [ ! -f "$CLEANLOG" ]; then echo "[]"; else
      tail -n 200 "$CLEANLOG" 2>/dev/null | awk 'BEGIN{print "[";n=0} match($0,/\{.*\}/){if(n>0)printf ",";print substr($0,RSTART,RLENGTH);n++} END{print "]"}'
    fi
    ;;
  browse)
    p=$(urldecode "$(get_param path)"); [ -z "$p" ] && p="/storage/emulated/0"
    real=$($BB readlink -f "$p" 2>/dev/null); [ -n "$real" ] && p="$real"
    printf '{"path":"%s","dirs":[' "$(json_escape "$p")"
    first=1
    for name in $($BB ls -1 "$p" 2>/dev/null); do
      case "$name" in .*|Android|data|obb) continue ;; esac
      if [ -d "$p/$name" ]; then [ $first -eq 1 ] && first=0 || printf ","; printf '"%s"' "$name"; fi
    done
    printf "]}\n"
    ;;
  stats)
    . "$CONFIG" 2>/dev/null; WD="$WATCH_DIR"; [ -z "$WD" ] && WD=/sdcard/Test
    real=$($BB readlink -f "$WD" 2>/dev/null); [ -n "$real" ] && WD="$real"
    v=0;i=0;a=0;d=0;z=0;s=0;o=0;total=0;totalsz=0
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      sz=$($BB du -b "$f" 2>/dev/null | awk '{print $1}'); [ -z "$sz" ] && sz=0
      ext=$(echo "${f##*.}" | tr 'A-Z' 'a-z')
      case "$ext" in
        mp4|mkv|avi|mov|flv|webm|ts|m4v) v=$((v+1));;
        jpg|jpeg|png|gif|webp|bmp|heic) i=$((i+1));;
        mp3|wav|flac|aac|ogg|m4a) a=$((a+1));;
        txt|pdf|doc|docx|xls|xlsx|ppt|pptx|md) d=$((d+1));;
        zip|rar|7z|tar|gz) z=$((z+1));;
        srt|ass|sub) s=$((s+1));;
        *) o=$((o+1));;
      esac
      total=$((total+1))
      totalsz=$(awk -v a=$totalsz -v b=$sz 'BEGIN{print a+b}')
    done <<< "$($BB find "$WD" -type f 2>/dev/null)"
    printf '{"total":%d,"totalSize":%d,"categories":{"video":{"count":%d},"image":{"count":%d},"audio":{"count":%d},"document":{"count":%d},"archive":{"count":%d},"subtitle":{"count":%d},"other":{"count":%d}}}\n' "$total" "$totalsz" "$v" "$i" "$a" "$d" "$z" "$s" "$o"
    ;;
esac
