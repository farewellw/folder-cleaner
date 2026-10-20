#!/system/bin/sh
ui_print "******************************************"
ui_print "  文件夹自动清理 (WebUI)  v1.9.8"
ui_print "******************************************"

ui_print "- 停止旧的后台进程..."
killall cleaner-daemon.sh 2>/dev/null
killall httpd 2>/dev/null
sleep 1

DATA_DIR=/data/adb/folder-cleaner
ui_print "- 创建数据目录: $DATA_DIR"
mkdir -p "$DATA_DIR" 2>/dev/null

set_perm_recursive "$MODDIR" 0 0 0755 0644
set_perm "$MODDIR/service.sh"           0 0 0755
set_perm "$MODDIR/cleaner-daemon.sh"    0 0 0755
set_perm "$MODDIR/webui/cgi-bin/api.cgi" 0 0 0755

ui_print "- 安装完成，重启手机后生效。"
ui_print "- 浏览器访问 http://<手机IP>:8899"
