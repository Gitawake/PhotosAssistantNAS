# 社区介绍帖草稿

[English](community-post.md) | [简体中文](community-post.zh-CN.md)

下面的标题和正文可用于介绍项目。这是待发布草稿，不表示已经向任何社区发帖。

## 标题

让群晖 NAS 自己生成 HEIC/HEVC 相册预览：PhotosAssistantNAS，无需客户端 Assistant 协助这些任务

## 正文

群晖将部分 HEIC/HEVC 处理转移到终端设备后，我希望 NAS 能重新承担相册预览与兼容视频副本生成，因此做了一个实验性开源项目 **PhotosAssistantNAS**。

项目地址：[Gitawake/PhotosAssistantNAS](https://github.com/Gitawake/PhotosAssistantNAS)

它在 NAS 上补齐缺失的 HEIC/HEIF 照片预览、视频缩略图和 H.264/AAC 兼容视频副本，再通过 Photos 接口交回相册使用。原始文件、文件名与相册目录保持原处；卸载移除本服务，保留 Photos 已接收的资源。

通过 SSH 部署，需要管理员权限，但不需要 Photos 密码、OTP、保存的登录会话或 Container Manager。媒体解码使用私有依赖，以非特权身份在独立网络命名空间运行。目前图片通过原件只读句柄交给 libheif 和 ImageMagick，不复制原图，也不生成编码中间图。

**实测环境为 x64、DSM 7.4.1-90080 Update 1、Photos 1.9.1-10928。** 未验证的 Photos 版本会被程序主动拒绝。项目使用未公开的本机接口，并运行 root 协调服务，请准备可恢复的独立备份，先测试非重要素材。原生手机 App 播放尚未充分验证。这是后台生成资源，不是实时转码，也不承诺恢复全部旧版 DSM 功能。

目前验证了三张现有 HEIC、带旋转的 10 位及透明通道合成图片、48 MP 合成 HEIC、隔离视频处理，以及损坏文件清理。这些是单台 NAS 的测试，不代表所有机型兼容。[流程图及测试步骤](https://github.com/Gitawake/PhotosAssistantNAS/blob/main/docs/demo.zh-CN.md) · [完整验证记录](https://github.com/Gitawake/PhotosAssistantNAS/blob/main/docs/compatibility.zh-CN.md)。

安装前请阅读 [README 和免责声明](https://github.com/Gitawake/PhotosAssistantNAS/blob/main/README.zh-CN.md)，然后在 NAS 的 SSH 终端运行：

```sh
curl -fsSL https://raw.githubusercontent.com/Gitawake/PhotosAssistantNAS/main/bootstrap.sh -o "$HOME/photos-assistant-install.sh" && sudo sh "$HOME/photos-assistant-install.sh"
```

GitHub 提供源码和入口脚本，由 NAS 下载锁定依赖并组装安装；不发布二进制 Releases。项目源码和底层运行库的许可不同，具体见仓库分发说明。

灵感来自 [octavianx/synology-photos-server-side-thumbnailgen](https://github.com/octavianx/synology-photos-server-side-thumbnailgen)。感谢原作者，以及 FFmpeg、ImageMagick、libheif 和 SynoCommunity 的贡献者。

欢迎提供可复现反馈：NAS CPU 架构、完整 DSM/Photos 版本、素材编码、预览与兼容播放是否正常。日志请先脱敏，不要公开凭据、NAS 地址或私人素材。若 Photos 版本尚未支持，请反馈版本，不要绕过版本检查。
