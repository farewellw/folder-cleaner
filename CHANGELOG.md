# 更新日志

本项目所有显著变更都会记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [v1.9.8] - 2026-10-21

本版本重点修复"全新安装无法正常启动 / Web UI 打不开"与"测试工具增加文件看似无效"两类问题，并将默认行为改为"零预置配置 + 首次进入引导新建"。

### 修复

- **修复全新安装后 Web UI 无法启动的问题（Magisk 设备）**：`cleaner-daemon.sh` 的 `start_httpd()` 之前把 httpd 的启动路径写死为 KernelSU 专用路径 `/data/adb/ksu/bin/busybox`，导致在 Magisk（非 KernelSU）设备上 httpd 静默失败，而日志却无条件打印 `Web UI 已启动端口 8899` 假成功。现改为使用脚本自动探测到的 busybox（Magisk / KernelSU / AP 均可），找不到时在日志中打印真实告警。
- **修复"升级迁移"在全新安装上被误触发**：旧版升级专用的 `default → 默认` 迁移逻辑会匹配 `customize.sh` 在全新安装时写入的 `default` 配置，导致首次开机就把监听目录清空、配置被改名。现全新安装不再预置任何配置，该迁移只对真正的旧版本升级生效。
- **修复测试工具"增加文件"看似无效**：`api.cgi` 的 `test` 接口此前把测试文件写入固定的 `/storage/emulated/0/FolderCleanerTest`，与页面顶栏实时显示的监听目录不一致，导致点击后占用/进度无变化。现测试文件写入当前激活的监听目录（未设置或不存在时回退到测试目录），并在各分支校验写入结果，写入失败返回真实错误，不再假成功。

### 变更

- **不再预置"默认"与"测试"两个配置**：全新安装后配置区为空，未建配置前守护进程不清理任何目录。
- **首次进入引导新建配置**：打开 Web UI 时若检测到没有任何配置，自动弹出配置页并进入"新建配置"流程；新建保存后该配置即被激活。
- 守护进程启动日志在未设置监听目录时显示 `dir=(未设置)`，不再显示空字符串。
- 测试工具弹窗说明与真实行为对齐：明确"生成到当前监听目录 / 未设置则回退测试目录 / 清空仅针对测试目录"。

### 新增

- 全新安装的首登引导流程（前端 `index.html`：`openConfig()` 空配置分支 + 初始化时自动弹出）。
- 后端 `test` 接口的写入结果校验（生成文件后检查文件真实存在，避免假成功）。

### 说明

- 老用户升级时已存在的配置会原样保留，守护进程会按需执行旧版 `default → 默认` 迁移；若想从零开始，可执行 `rm -f /data/adb/folder-cleaner/profiles.conf` 后重启。
- 数据目录位置：`/data/adb/folder-cleaner/`（`config.conf`、`profiles.conf`、`cleaner.log`、`cleanup.log`、`daemon.pid`）。
