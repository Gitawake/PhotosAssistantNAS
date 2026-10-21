# 第三方组件

[English](THIRD_PARTY.md) | [简体中文](THIRD_PARTY.zh-CN.md)

源码仓库包含项目脚本、依赖锁定文件及上游许可证文本，不包含已下载的 SPK、解码器二进制文件、NAS 私有状态或生成的媒体。

| 组件 | 来源 | 处理方式 |
| --- | --- | --- |
| 最初的缩略图思路 | [参考项目](https://github.com/octavianx/synology-photos-server-side-thumbnailgen) | 保留 MIT 声明，见 [NOTICE.md](NOTICE.zh-CN.md) |
| ImageMagick 运行库 | [官方包](https://synocommunity.com/package/imagemagick) | 锁定官方下载地址和 SHA256；ImageMagick 许可证不能覆盖所有链接库 |
| FFmpeg 运行库 | [官方包](https://synocommunity.com/package/ffmpeg8) | 当前二进制启用 GPL、version3 及 nonfree，不能公开分发本项目二进制包 |
| 辅助动态库 | [官方包](https://synocommunity.com/package/synocli-videodriver) | 仅选择必要库及其依赖闭包；仍需逐组件审查许可证和源码 |
| 套件构建配方 | [spksrc](https://github.com/SynoCommunity/spksrc) | 配方链接不能替代精确匹配的对应源码 |

个人构建会清除 ELF 的 DT_RPATH/DT_RUNPATH，由私有库路径控制解析。ImageMagick 策略替换为禁止委托程序、仅允许 HEIC/JPEG 模块。相关实现在 `tools/private_elf.py` 和 `src/photos_assistant/policy.xml`。不运行厂商安装脚本、不替换系统编解码器、不安装内核驱动。

生成的 `runtime-manifest.json` 记录依赖 URL、SHA256、原始包 INFO、提取文件数、ELF 更改和检测到的 nonfree 状态。它用于辅助清点，不能证明所有依赖都可再分发。

`licenses/` 中的许可证文本仅供参考，不构成已完成的二进制合规材料。公开分发前的要求见 [分发说明](docs/distribution.zh-CN.md)。

主要参考资料：

- [FFmpeg 许可与分发说明](https://www.ffmpeg.org/legal.html)
- [FFmpeg 配置与许可详情](https://ffmpeg.org/doxygen/4.0/md_LICENSE.html)
- [ImageMagick 许可证](https://imagemagick.org/license/)

项目灵感、上游作者及依赖致谢见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.zh-CN.md)。

[GPU 后端说明](docs/hardware.zh-CN.md)。私有构建还从锁定的 VideoDriver 归档提取 Intel media-driver、旧版 i965、GMM 依赖闭包及 Media SDK 硬件运行库；不安装或替换内核驱动。
