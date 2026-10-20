#!/system/bin/sh
ui_print "******************************************"
ui_print "  文件夹自动清理 (WebUI)  v1.3.4"
ui_print "******************************************"
killall cleaner-daemon.sh 2>/dev/null
killall httpd 2>/dev/null
sleep 1
DATA_DIR=/data/adb/folder-cleaner
ui_print "- 创建数据目录: $DATA_DIR"
mkdir -p "$DATA_DIR" 2>/dev/null
if [ ! -f "$DATA_DIR/config.conf" ]; then
  ui_print "- 写入默认配置"
  cat > "$DATA_DIR/config.conf" <<EOF
WATCH_DIR=/sdcard/Test
THRESHOLD_GB=50
INTERVAL_SEC=60
PORT=8899
EOF
  chmod 0644 "$DATA_DIR/config.conf"
  mkdir -p /sdcard/Test 2>/dev/null
fi
set_perm_recursive "$MODDIR" 0 0 0755 0644
set_perm "$MODDIR/service.sh"           0 0 0755
set_perm "$MODDIR/cleaner-daemon.sh"    0 0 0755
set_perm "$MODDIR/webui/cgi-bin/api.cgi" 0 0 0755
ui_print "- 安装完成，重启手机后生效。"
