# 致谢与项目来源

[English](ACKNOWLEDGEMENTS.md) | [简体中文](ACKNOWLEDGEMENTS.zh-CN.md)

PhotosAssistantNAS 建立在开源社区长期维护的媒体工具和打包成果之上。感谢以下项目的作者、维护者和贡献者。列出项目表示来源与感谢，不表示这些项目为本项目背书。

## 灵感来源

本项目最初的方向来自用户提供的 [Gitawake/synology-photos-server-side-thumbnailgen](https://github.com/Gitawake/synology-photos-server-side-thumbnailgen)：在 NAS 服务端补齐 Synology Photos 的媒体预览，减少对客户端处理的依赖。

参考版本为 `11ed028780d51d00f8056b123b22bc716ba6a0ec`。该项目的版权声明为 **Copyright (c) 2026 octavianx，MIT License**；相关版权与许可声明保留在本项目 [LICENSE](LICENSE) 和 [NOTICE.md](NOTICE.zh-CN.md)。感谢原作者及 Gitawake 仓库维护者对这一方向的探索和分享。

目前的 SSH 部署、无 Photos 登录的本机接口协调、隔离解码、只读文件句柄视频输入和卸载机制是本项目当前实现。灵感来源不代表本项目与参考项目采用相同的系统接入方式，也不意味着它们的作者对本项目的数据安全或兼容性负责。

## 直接使用的工具与打包成果

| 项目 / 团队 | 在本项目中的用途 | 来源与许可入口 |
| --- | --- | --- |
| FFmpeg 项目及贡献者 | FFprobe 探测、视频缩略图、H.264/AAC 兼容副本、可随机定位的只读 `fd:` 输入 | [官网](https://ffmpeg.org/) · [许可说明](https://ffmpeg.org/legal.html) |
| ImageMagick Studio 及贡献者 | HEIC/HEIF 解码、方向处理及 JPEG 缩略图 | [官网](https://imagemagick.org/) · [许可证](https://imagemagick.org/license/) |
| SynoCommunity 维护者与贡献者 | 适用于 DSM 的媒体工具、私有动态库的原始构建和包配方 | [spksrc](https://github.com/SynoCommunity/spksrc) · [FFmpeg 包](https://synocommunity.com/package/ffmpeg8) · [ImageMagick 包](https://synocommunity.com/package/imagemagick) · [视频运行库包](https://synocommunity.com/package/synocli-videodriver) |
| Python Software Foundation 与 Python 贡献者 | 安装、卸载、任务协调和构建脚本使用的标准库 | [Python](https://www.python.org/) · [许可证](https://docs.python.org/3/license.html) |
| Linux / systemd 项目及贡献者 | 文件句柄、进程权限隔离和服务管理 | [Linux](https://www.kernel.org/) · [systemd](https://systemd.io/) |

感谢 hgy59 对 ImageMagick/libheif 适配的贡献，参考 [spksrc PR #6744](https://github.com/SynoCommunity/spksrc/pull/6744)。原参考项目还列出了其自身的背景资料与致谢，见 [原项目 Credits](https://github.com/Gitawake/synology-photos-server-side-thumbnailgen#credits)。

## 底层媒体与图形库

上游运行时还包含或链接其他开源组件。以下是本项目主要功能涉及的代表性项目；实际提取的库文件及上游包信息以构建后的 `runtime-manifest.json` 为准，不应将此表当作完整的许可证合规清单。

| 项目 | 作用 | 上游 |
| --- | --- | --- |
| libheif | HEIF/HEIC 容器和解码接口 | [strukturag/libheif](https://github.com/strukturag/libheif) |
| libde265 | HEVC 图像解码 | [strukturag/libde265](https://github.com/strukturag/libde265) |
| libjpeg-turbo | JPEG 编解码 | [libjpeg-turbo](https://github.com/libjpeg-turbo/libjpeg-turbo) |
| x264 | H.264 编码 | [VideoLAN x264](https://www.videolan.org/developers/x264.html) |
| libva / libdrm | 视频工具所需的用户态动态库 | [libva](https://github.com/intel/libva) · [libdrm](https://gitlab.freedesktop.org/mesa/drm) |
| oneVPL / Media SDK | FFmpeg 构建所需的媒体接口运行库 | [oneVPL](https://github.com/oneapi-src/oneVPL) · [Media SDK](https://github.com/Intel-Media-SDK/MediaSDK) |
| shaderc / glslang / SPIRV-Tools | 上游 FFmpeg 图形处理依赖链 | [shaderc](https://github.com/google/shaderc) · [glslang](https://github.com/KhronosGroup/glslang) · [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |

本项目没有自行实现这些编解码器，也不宣称拥有上述第三方成果。各组件适用各自的许可证与版权声明；本项目的 MIT 许可证不覆盖第三方运行库。具体分发限制、原始包、固定版本及校验值见 [THIRD_PARTY.md](THIRD_PARTY.zh-CN.md)、[vendor/lock.json](vendor/lock.json) 和 [分发说明](docs/distribution.zh-CN.md)。

Synology Photos 是目标平台，不是本项目提供或重新分发的依赖。感谢 Synology 提供的相册产品；本项目与 Synology 无隶属或背书关系。
