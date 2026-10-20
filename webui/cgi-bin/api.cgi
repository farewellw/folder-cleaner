#!/system/bin/sh
# Web UI 后端接口
DATA_DIR=/data/adb/folder-cleaner
CONFIG=$DATA_DIR/config.conf
PROFILES=$DATA_DIR/profiles.conf
LOGFILE=$DATA_DIR/cleaner.log
CLEANLOG=$DATA_DIR/cleanup.log

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

echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo "Pragma: no-cache"
echo ""

q="$QUERY_STRING"

urldecode() {
  local s="$1"
  s=$(printf '%b' "$(echo "$s" | sed 's/+/ /g; s/%/\\x/g')")
  echo "$s"
}

get_param() {
  echo "$q" | tr '&' '\n' | grep "^$1=" | head -n1 | cut -d= -f2-
}

json_escape() {
  echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

load_global() {
  ACTIVE_PROFILE=""
  PORT=8899
  [ -f "$CONFIG" ] && . "$CONFIG"
  [ -z "$PORT" ] && PORT=8899
}

load_profile() {
  load_global
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

profiles_json() {
  echo "["
  first=1
  if [ -f "$PROFILES" ]; then
    while IFS='|' read -r name wd tg iv kg; do
      [ -z "$name" ] && continue
      [ $first -eq 1 ] && first=0 || printf ","
      printf '{"name":"%s","watchDir":"%s","thresholdGb":%s,"intervalSec":%s,"keepGb":%s,"active":%s}' \
        "$(json_escape "$name")" "$(json_escape "$wd")" "$tg" "$iv" "${kg:-0}" \
        "([ "$name" = "$ACTIVE_PROFILE" ] && echo 1 || echo 0)"
    done < "$PROFILES"
  fi
  echo "]"
}

action=$(get_param action)

case "$action" in
  status)
    load_profile
    cur=$($BB du -sb "$WATCH_DIR" 2>/dev/null | awk '{print $1}')
    [ -z "$cur" ] && cur=0
    disk_total=$($BB df -B1 /sdcard 2>/dev/null | awk 'NR==2 {print $2}')
    disk_free=$($BB df -B1 /sdcard 2>/dev/null | awk 'NR==2 {print $4}')
    [ -z "$disk_total" ] && disk_total=0
    [ -z "$disk_free" ] && disk_free=0
    pj=$(profiles_json)
    printf '{"watchDir":"%s","thresholdGb":%s,"keepGb":%s,"intervalSec":%s,"port":%s,"currentBytes":%s,"diskTotal":%s,"diskFree":%s,"activeProfile":"%s","profiles":%s}\n' \
      "$(json_escape "$WATCH_DIR")" "$THRESHOLD_GB" "$KEEP_GB" "$INTERVAL_SEC" "$PORT" "$cur" "$disk_total" "$disk_free" "$ACTIVE_PROFILE" "$pj"
    ;;

  save)
    wd=$(urldecode "$(get_param watchDir)")
    tg=$(get_param thresholdGb)
    kg=$(get_param keepGb)
    iv=$(get_param intervalSec)
    pname=$(urldecode "$(get_param profileName)")
    [ -z "$pname" ] && pname="$ACTIVE_PROFILE"
    [ -z "$tg" ] && tg=0
    [ -z "$kg" ] && kg=0
    [ -z "$iv" ] && iv=0
    echo "$iv" | grep -qE '^[0-9]+$' || iv=0
    echo "$tg" | grep -qE '^[0-9]+(\.[0-9]+)?$' || tg=0
    echo "$kg" | grep -qE '^[0-9]+(\.[0-9]+)?$' || kg=0
    over=$(awk -v k="$kg" -v t="$tg" 'BEGIN{print (k>=t)?1:0}')
    [ "$over" -eq 1 ] && kg=0

    case "$wd" in
      /|/system/*|/data/adb/*|/sdcard/Android/*|/root/*|/dev/*|/proc/*|/sys/*|/vendor/*|/product/*)
        printf '{"ok":false,"error":"受保护路径"}\n'
        exit 0
        ;;
    esac
    if [ "$(awk -v g="$tg" 'BEGIN{print (g>0)?1:0}')" -eq 1 ]; then
      [ -z "$wd" ] && { printf '{"ok":false,"error":"启用清理时必须填写监听路径"}\n'; exit 0; }
      [ ! -d "$wd" ] && { printf '{"ok":false,"error":"路径不存在: %s"}\n' "$wd"; exit 0; }
    fi

    tmpf="$DATA_DIR/profiles.tmp"
    > "$tmpf"
    found=0
    if [ -f "$PROFILES" ]; then
      while IFS='|' read -r name pwd ptg piv pkg; do
        [ -z "$pkg" ] && pkg=0
        if [ "$name" = "$pname" ]; then
          echo "${pname}|${wd}|${tg}|${iv}|${kg}" >> "$tmpf"
          found=1
        else
          echo "${name}|${pwd}|${ptg}|${piv}|${pkg}" >> "$tmpf"
        fi
      done < "$PROFILES"
    fi
    [ "$found" -eq 0 ] && echo "${pname}|${wd}|${tg}|${iv}|${kg}" >> "$tmpf"
    mv "$tmpf" "$PROFILES"

    cat > "$CONFIG" <<EOF
ACTIVE_PROFILE=$pname
PORT=$PORT
EOF
    chmod 0644 "$CONFIG"
    printf '{"ok":true}\n'
    ;;

  switch)
    pname=$(urldecode "$(get_param name)")
    [ -z "$pname" ] && exit 0
    if [ -f "$PROFILES" ]; then
      while IFS='|' read -r name wd tg iv kg; do
        if [ "$name" = "$pname" ]; then
          cat > "$CONFIG" <<EOF
ACTIVE_PROFILE=$pname
PORT=$PORT
EOF
          chmod 0644 "$CONFIG"
          printf '{"ok":true,"msg":"已切换到 %s"}\n' "$(json_escape "$pname")"
          exit 0
        fi
      done < "$PROFILES"
    fi
    printf '{"ok":false,"error":"配置不存在"}\n'
    ;;

  delete)
    pname=$(urldecode "$(get_param name)")
    [ -z "$pname" ] && { printf '{"ok":false,"error":"缺少名称"}\n'; exit 0; }
    . "$CONFIG" 2>/dev/null
    [ "$pname" = "$ACTIVE_PROFILE" ] && { printf '{"ok":false,"error":"不能删除正在使用的配置，请先切换"}\n'; exit 0; }
    tmpf="$DATA_DIR/profiles.tmp"
    > "$tmpf"
    if [ -f "$PROFILES" ]; then
      while IFS='|' read -r name wd tg iv kg; do
        [ -z "$name" ] && continue
        [ "$name" = "$pname" ] && continue
        echo "${name}|${wd}|${tg}|${iv}|${kg}" >> "$tmpf"
      done < "$PROFILES"
    fi
    mv "$tmpf" "$PROFILES"
    printf '{"ok":true,"msg":"已删除 %s"}\n' "$(json_escape "$pname")"
    ;;

  rename)
    old=$(urldecode "$(get_param old)")
    new=$(urldecode "$(get_param new)")
    [ -z "$old" ] || [ -z "$new" ] && { printf '{"ok":false,"error":"缺少参数"}\n'; exit 0; }
    if [ -f "$PROFILES" ]; then
      while IFS='|' read -r name wd tg iv kg; do
        [ "$name" = "$new" ] && { printf '{"ok":false,"error":"名称已存在"}\n'; exit 0; }
      done < "$PROFILES"
    fi
    tmpf="$DATA_DIR/profiles.tmp"
    > "$tmpf"
    if [ -f "$PROFILES" ]; then
      while IFS='|' read -r name wd tg iv kg; do
        [ -z "$name" ] && continue
        [ "$name" = "$old" ] && name="$new"
        echo "${name}|${wd}|${tg}|${iv}|${kg}" >> "$tmpf"
      done < "$PROFILES"
    fi
    mv "$tmpf" "$PROFILES"
    . "$CONFIG" 2>/dev/null
    if [ "$old" = "$ACTIVE_PROFILE" ]; then
      cat > "$CONFIG" <<EOF
ACTIVE_PROFILE=$new
PORT=$PORT
EOF
      chmod 0644 "$CONFIG"
    fi
    printf '{"ok":true,"msg":"已重命名为 %s"}\n' "$(json_escape "$new")"
    ;;

  clean)
    touch "$DATA_DIR/force_clean"
    printf '{"ok":true,"msg":"已触发清理"}\n'
    ;;

  test)
    mode=$(get_param mode)
    WD=/storage/emulated/0/FolderCleanerTest
    mkdir -p "$WD" 2>/dev/null
    case "$mode" in
      small)
        echo "A" > "$WD/t_a.txt"; echo "B" > "$WD/t_b.txt"; echo "C" > "$WD/t_c.txt"
        printf '{"ok":true,"msg":"已生成 3 个小文件"}\n'
        ;;
      big)
        dd if=/dev/zero of="$WD/test_big.img" bs=1024 count=2097152 2>/dev/null
        printf '{"ok":true,"msg":"已生成 2GB 大文件"}\n'
        ;;
      mixed)
        echo "v" > "$WD/t_v.mp4"; echo "i" > "$WD/t_i.jpg"; echo "a" > "$WD/t_a.mp3"; echo "d" > "$WD/t_d.txt"
        printf '{"ok":true,"msg":"已生成混合文件"}\n'
        ;;
      mid5)
        i=1
        while [ $i -le 5 ]; do
          dd if=/dev/zero of="$WD/mid_${i}.bin" bs=1024 count=51200 2>/dev/null
          i=$((i+1))
        done
        printf '{"ok":true,"msg":"已生成 5 个 50MB 文件 (共 250MB)"}\n'
        ;;
      clear)
        find "$WD" -mindepth 1 -delete 2>/dev/null
        printf '{"ok":true,"msg":"已清空测试目录"}\n'
        ;;
      *)
        printf '{"ok":false,"error":"未知模式"}\n'
        ;;
    esac
    ;;

  log)
    tail -n 40 "$LOGFILE" 2>/dev/null | awk '
      BEGIN { printf "[" }
      { gsub(/\\\\/, "\\\\\\\\"); gsub(/"/, "\\\\""); if (NR > 1) printf ","; printf "\"%s\"", $0 }
      END { print "]" }
    '
    ;;

  cleanup)
    if [ ! -f "$CLEANLOG" ]; then echo "[]"; else
      tail -n 200 "$CLEANLOG" 2>/dev/null | awk '
        BEGIN { print "["; n=0 }
        match($0, /\{.*\}/) { if (n>0) printf ","; print substr($0, RSTART, RLENGTH); n++ }
        END { print "]" }
      '
    fi
    ;;

  browse)
    p=$(urldecode "$(get_param path)")
    [ -z "$p" ] && p="/storage/emulated/0"
    real=$($BB readlink -f "$p" 2>/dev/null)
    [ -z "$real" ] && real="$p"
    [ ! -d "$real" ] && real="/storage/emulated/0"
    p="$real"
    printf '{"path":"%s","dirs":[' "$(json_escape "$p")"
    first=1
    for name in $($BB ls -1 "$p" 2>/dev/null); do
      case "$name" in .*|Android|data|obb) continue ;; esac
      if [ -d "$p/$name" ]; then
        if [ $first -eq 1 ]; then first=0; else printf ","; fi
        printf '"%s"' "$(json_escape "$name")"
      fi
    done
    printf "]}\n"
    ;;

  stats)
    load_profile
    WD="$WATCH_DIR"
    real=$($BB readlink -f "$WD" 2>/dev/null)
    [ -n "$real" ] && WD="$real"
    total=$($BB find "$WD" -type f 2>/dev/null | wc -l)
    cache_file="$DATA_DIR/.stats_$(echo "$WD" | md5sum | awk '{print $1}')"
    if [ -f "$cache_file" ]; then
      cached_count=$($BB grep -o '"total":[0-9]*' "$cache_file" | awk -F: '{print $2}')
      if [ "$cached_count" = "$total" ]; then
        cat "$cache_file"
        exit 0
      fi
    fi
    totalsz=$($BB du -sb "$WD" 2>/dev/null | awk '{print $1}')
    [ -z "$totalsz" ] && totalsz=0
    cat_stats=$($BB find "$WD" -type f 2>/dev/null | while IFS= read -r f; do
      sz=$($BB stat -c %s "$f" 2>/dev/null)
      [ -z "$sz" ] && sz=0
      printf '%s|%s\n' "$sz" "$f"
    done | awk -F'|' '
      BEGIN { vc=0;vs=0;ic=0;is=0;ac=0;as=0;dc=0;ds=0;zc=0;zs=0;sc=0;ss=0;pc=0;ps=0;oc=0;os=0 }
      { sz=$1; path=$2; n=split(path,p,"."); ext=(n>1)?tolower(p[n]):""
        if (ext~/^(mp4|mkv|avi|mov|flv|webm|m4v|ts|wmv)$/) {vc++;vs+=sz}
        else if (ext~/^(jpg|jpeg|png|gif|webp|bmp|heic)$/) {ic++;is+=sz}
        else if (ext~/^(mp3|wav|flac|aac|ogg|m4a)$/) {ac++;as+=sz}
        else if (ext~/^(txt|pdf|doc|docx|xls|xlsx|ppt|pptx|csv)$/) {dc++;ds+=sz}
        else if (ext~/^(zip|rar|7z|tar|gz|bz2|xz)$/) {zc++;zs+=sz}
        else if (ext~/^(srt|ass|ssa|vtt)$/) {sc++;ss+=sz}
        else if (ext~/^(apk|exe|msi|dmg|deb)$/) {pc++;ps+=sz}
        else {oc++;os+=sz} }
      END { printf "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d",vc,vs,ic,is,ac,as,dc,ds,zc,zs,sc,ss,pc,ps,oc,os }
    ')
    set -- $cat_stats
    out=$(printf '{"path":"%s","total":%d,"totalSize":%d,"categories":{"video":{"count":%d,"size":%d},"image":{"count":%d,"size":%d},"audio":{"count":%d,"size":%d},"document":{"count":%d,"size":%d},"archive":{"count":%d,"size":%d},"subtitle":{"count":%d,"size":%d},"package":{"count":%d,"size":%d},"other":{"count":%d,"size":%d}}}\n' \
      "$(json_escape "$WD")" "$total" "$totalsz" \
      "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" "${11}" "${12}" "${13}" "${14}" "${15}" "${16}")
    echo "$out" > "$cache_file"
    echo "$out"
    ;;

  *)
    printf '{"error":"未知操作: %s"}\n' "$(json_escape "$action")"
    ;;
esac
