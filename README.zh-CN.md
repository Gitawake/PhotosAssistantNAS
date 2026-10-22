# PhotosAssistantNAS

[English](README.md) | [简体中文](README.zh-CN.md)

**让群晖相册的 HEIC/HEVC 处理，重新回到 NAS。**

PhotosAssistantNAS 为 Synology Photos 补回服务端媒体处理能力：在 NAS 上生成 HEIC/HEIF 照片预览、视频缩略图及 H.264/AAC 兼容视频副本，承担原本需要客户端 Image Assistant 完成的这些工作。通过 SSH 一键部署，无需 Photos 账号、密码或 OTP，不依赖 Container Manager。

**主要适用于通过 Photos 网页、File Station 或 SMB 导入相册的场景：** 让 NAS 自己补齐缺失资源，不必安装桌面 Image Assistant 及浏览器扩展，也不必让客户端持续运行来处理相册。

在 DSM 7.2.2 前后相关调整中，群晖将部分媒体处理转向终端设备，Photos 的 HEIC/HEVC 预览与兼容副本因此可能需要客户端协助。本项目的目标是让 NAS 自己完成这部分后台工作：原片仍在原处，相册仍用 Synology Photos。背景见 [群晖官方说明](https://www.synology.com/en-us/products/status/eol-video-codec-support) 和 [Image Assistant 常见问题](https://kb.synology.com/en-global/DSM/tutorial/Frequently_asked_questions_about_Synology_Image_Assistant)。

它补齐的是相册的预览和兼容副本生成，不是还原全部旧版 DSM 功能，也不提供实时转码播放。

**实验性项目，目前仅发布源码。** 已验证 x86_64、DSM 7.4.1-90080 Update 1、Synology Photos **1.9.1-10928**。使用未公开的本机 Photos 接口；Photos 升级后会拒绝继续处理，不能视为任意 DSM 7 或未来版本通用。项目与 Synology 无隶属关系。

> **数据损坏风险：** 设计上保留原件，不代表不会发生损坏或丢失。缺陷、接口变化、权限错误、断电及存储故障都可能影响数据和相册可用性。部署前请完成独立备份并验证恢复能力，先用少量非重要素材测试。详见 [数据安全免责声明](DISCLAIMER.zh-CN.md)。

## 哪些用户适合使用

| 使用方式 | 本项目的作用 |
| --- | --- |
| 通过 Photos 网页上传 | 不想安装桌面 Image Assistant 和浏览器扩展，希望 NAS 自己生成预览与兼容视频 |
| 通过 File Station、SMB 或其他方式复制素材 | 素材进入 Photos 已索引目录后，希望 NAS 后台自动补齐缺失资源 |
| 主要通过 Photos 手机 App 备份 | 如果已有预览和播放都正常，通常没有必要安装本项目 |
| 素材放在 NAS 的其他位置 | 未进入 Photos 索引就不在处理范围；本项目不是全 NAS 的编解码替换 |

Photos 手机 App 本身已有 **更多 → 设置 → Image Assistant** 开关。开启后，可为正在浏览的项目生成 JPEG 预览，包括通过网页、File Station 或 SMB 导入的 HEIC/HEVC。**手机端不生成压缩兼容视频副本**，视频播放仍依赖设备本身的解码能力。详见[群晖对桌面端和移动端行为的说明](https://kb.synology.com/en-eu/DSM/tutorial/Unable_to_view_HEIC_photos_HEVC_videos_on_Synology_Photos)。

本项目把受支持的后台生成任务交给 NAS，不依赖手机逐项浏览或电脑客户端处理；如果官方移动端流程已经满足需求，本项目并非必装。是否实际处理某个项目，仍取决于受支持的缺失/损坏状态及已验证的 Photos 版本。

## 工作方式

![PhotosAssistantNAS：在 NAS 上完成媒体处理](docs/media/overview.svg)

上图是流程示意，不是实机录像。详见 [NAS 验证与可复现演示步骤](docs/demo.zh-CN.md)；也可以使用[社区介绍帖草稿](docs/community-post.zh-CN.md)，连同已验证范围和限制一起介绍项目。

## 行为与边界

- 无需 Photos 账号、密码、OTP 或会话令牌；不创建 DSM 登录账号。
- 保留原始文件、文件名、目录结构；通过 Photos 接口保存附加结果，不另建相册库。
- 只补已知缺失/损坏状态的缩略图与 high 兼容副本，跳过已有可用结果。
- 生成 JPEG 与最高 720p 范围的 H.264/AAC MP4；不是实时转码。编码、码率、帧率及 HDR 映射不保证与官方 Assistant 完全相同。
- root 协调进程调用 DSM 本机接口；解码子进程使用未注册的数值 UID、独立网络命名空间、禁止提权并限制资源。详细边界见 [安全说明](SECURITY.zh-CN.md)。
- 卸载移除本服务程序、systemd 注册、运行状态与临时文件，**保留 Photos 已接收的预览和兼容视频**。系统审计日志、用户自行保留的下载文件不会被抹除。

## 私有依赖

截至 2026-10-21，选择 SynoCommunity 官方提供的最新适用 DSM x64 构建，固定下载地址及 SHA256（见 `vendor/lock.json`）：

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| FFmpeg / FFprobe | 8.1.3-5 | 只读句柄视频输入、缩略图和 H.264/AAC 兼容输出 |
| ImageMagick | 7.1.2-16 | HEIC/HEIF 与 JPEG 缩略图 |
| SynoCli Video Drivers | 1.5-9 | 私有加载所需动态库及其依赖闭包 |

仅提取所需文件，不执行这些套件的安装脚本。系统自带 Python、systemd、glibc 和 DSM 本机接口不由本项目升级；不逐个混换上游构建内的底层库，以免破坏 ABI 兼容。依赖更新通过新的已验证源码提交进行，不静默追随最新版。

## SSH 在线一键安装

GitHub 只托管源码与引导脚本，不提供远程 SSH 代理，也不接收 NAS 或 Photos 凭据。不使用 GitHub Releases。

在 **NAS 自己的 SSH 终端**执行：

```sh
curl -fsSL https://raw.githubusercontent.com/Gitawake/PhotosAssistantNAS/main/bootstrap.sh -o "$HOME/photos-assistant-install.sh" && sudo sh "$HOME/photos-assistant-install.sh"
```

引导程序先显示数据风险提示并检查 NAS 环境，将 `main` 解析为一个固定提交，下载该提交的源码，在 NAS 上下载并校验锁定的上游依赖、本机构建，再安装服务。依赖、源码和构建临时文件在结束后清理。整个过程无需 Photos 账号、密码或 OTP；sudo 仍是 DSM 管理员安装权限。

如果网络无法访问 `raw.githubusercontent.com`，可改用 GitHub 官方 API 下载同一入口（仍校验 HTTPS）：

```sh
curl -fsSL -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/Gitawake/PhotosAssistantNAS/contents/bootstrap.sh?ref=main' -o "$HOME/photos-assistant-install.sh" && sudo sh "$HOME/photos-assistant-install.sh"
```

查看已下载的脚本后再执行也可以。需要固定版本时，应从同一完整提交的 raw URL 下载入口，并传入 `--ref <40位提交SHA>`。只检查环境而不下载或安装可加 `--check`；只下载并构建、验证完成即清理而不安装可加 `--build-only`；其他卷使用 `--volume /volume2`。需要能访问 GitHub 和 SynoCommunity 的 HTTPS 网络，临时构建至少需要 2 GiB 空间。

在线卸载：

```sh
curl -fsSL https://raw.githubusercontent.com/Gitawake/PhotosAssistantNAS/main/uninstall.sh -o "$HOME/photos-assistant-uninstall.sh" && sudo sh "$HOME/photos-assistant-uninstall.sh"
```

在线卸载入口调用已安装的 root 控制卸载程序，保留所有已经提交给 Photos 的预览与兼容视频。GitHub 不可用时，仍可直接使用下方的本机卸载命令。

## 手动构建并安装（可选）


构建脚本使用 Python 3.8+；开发 CI 覆盖 Python 3.9 与 3.12。没有 PyPI 依赖，无需 root 构建；NAS 安装使用 DSM 自带 Python 3 和管理员权限。

```sh
python3 tools/build.py
```

构建脚本从锁定的 SynoCommunity 官方地址下载三个原始 SPK，校验 SHA256，仅提取运行时文件，**不执行 SPK 安装脚本、不依赖本地旧版 SPK**。结果位于 `dist/PhotosAssistantNAS-0.6.1-x64.private.tar`。

**这个构建结果仅供个人使用，不应上传到公开 Releases。** 当前锁定 FFmpeg 启用了 `--enable-gpl --enable-version3 --enable-nonfree`。公开分发前需要更换为可再分发的构建，并逐项完成来源、许可证及对应源码审计，不能只附几份许可证。见 [分发说明](docs/distribution.zh-CN.md)。

把构建结果复制到自己的 NAS，解压后在 SSH 中执行：

```sh
sudo sh install.sh
```

这里的 sudo 是 DSM 管理员安装授权，不是 Photos 登录。默认安装到 `/volume1/@PhotosAssistantNAS`，支持 `--volume /volume2`。安装会注册并启动 `photos-assistant-nas.service`、启用开机运行。开始后会扫描已有媒体并生成缺失副本，可能消耗 CPU 与额外存储空间。

## 管理与卸载

```sh
sudo systemctl status photos-assistant-nas.service
sudo systemctl stop photos-assistant-nas.service
sudo systemctl start photos-assistant-nas.service
sudo /bin/python3 -I /volume1/@PhotosAssistantNAS/uninstall.py
```

也可在解压后的安装目录执行 `sudo sh uninstall.sh`。安装到其他卷时，卸载命令也加 `--volume /volume2`。

视频不设置固定源文件大小上限，最长 6 小时。root 只读打开原视频，将一个文件句柄传给隔离进程；私有 FFmpeg 使用可随机定位的 `fd:` 协议流式读取，**不复制或克隆整份源视频、不修改原文件权限，也不依赖 Btrfs**。HEIC/HEIF 图片同样使用继承的只读句柄：私有 Python/ctypes 桥接将 libheif 的可定位读取接口连接到 ImageMagick 的内存 MagickWand 接口，不创建原图副本、中间 PNG/JPEG 或像素缓存文件，只写最终缩略图及其发布暂存。图片限制为 64 Mi 像素、单边不超过 32768 像素，ICC 配置最多 4 MiB，ImageMagick 像素缓存最多 768 MiB；这是上限，不是预占空间，也不是整个进程的内存上限。图片禁用磁盘及映射缓存，分配失败则中止任务、留待重试。解码仍需内存和原文件读取，操作系统也可能将内存换出到磁盘。按时长与目标码率预留解码输出、发布暂存、Photos 最终副本三份输出及临时空间，解码期间每 5 秒检查至少 4 GiB 可用空间，不足则中止；其他程序仍可能同时写满磁盘，这不是空间配额。单个生成文件最多 16 GiB，保留线程、优先级限制及失败一小时后重试。兼容副本会额外占用容量；不要为清理副本而删除整个 `@eaDir`。

## 测试、兼容性与贡献

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public.py
python3 tools/package_source.py
```

- [兼容性与实机验证](docs/compatibility.zh-CN.md)：区分已验证、未验证能力。
- [架构与权限](docs/architecture.zh-CN.md)：说明 root 协调与解码隔离。
- [开发指南](CONTRIBUTING.zh-CN.md)：使用合成素材，不提交 NAS 地址、凭据或私人媒体。
- [许可证及来源](THIRD_PARTY.zh-CN.md)：项目源码采用 MIT；第三方运行时不因此变为 MIT。

源码包只包含公开文件，不包含私有运行时、实验安装包或原始调试记录。完整数据风险说明见 [DISCLAIMER.md](DISCLAIMER.zh-CN.md)。

## 项目灵感与致谢

本项目的初始灵感来自 [octavianx/synology-photos-server-side-thumbnailgen](https://github.com/octavianx/synology-photos-server-side-thumbnailgen)：将相册媒体处理放回 NAS 服务端。感谢原作者 octavianx，以及 FFmpeg、ImageMagick、SynoCommunity 和所有底层依赖的贡献者。原有 MIT 版权声明已保留；完整来源、依赖引用和致谢见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.zh-CN.md)，第三方使用与许可边界见 [THIRD_PARTY.md](THIRD_PARTY.zh-CN.md)。

[硬件加速及后端验证状态](docs/hardware.zh-CN.md)。

[事件驱动处理及恢复](docs/events.zh-CN.md)。
