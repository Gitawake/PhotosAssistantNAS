# 源码发布与二进制分发

[English](distribution.md) | [简体中文](distribution.zh-CN.md)

## 当前状态：仅发布源码

发布项目源码、文档、测试、依赖锁定文件和许可证文本。不要把个人构建的安装 tar、已下载的 SPK 或运行库二进制文件上传为 GitHub Release 附件。CI 仅检查并打包源码，不发布二进制文件或部署到 NAS。

已检查当前锁定的 FFmpeg 二进制，其包含 `--enable-gpl`、`--enable-version3` 和 **`--enable-nonfree`**。FFmpeg 文档说明 nonfree 配置可能生成不可再分发的二进制文件。附加源码链接或许可证文本不能解除这一限制。个人本地构建与对外再分发是不同的行为。

## 考虑公开二进制分发之前

1. 替换为完整依赖集合均允许再分发的 FFmpeg 构建。在支持的 NAS 上重新验证解码、HDR 转换、AVC/AAC 输出和私有动态链接。
2. 清点所有库和数据文件，记录版本、来源、许可证、补丁及构建配置，同时审查 ImageMagick 和辅助库依赖树。
3. 对适用 copyleft 条款的组件，提供精确匹配的对应源码及必要构建脚本，包括本地更改。最新上游分支链接或若干许可证文件并不足够。
4. 为每个组件保留必要声明、署名和许可证文本。项目 MIT 条款适用于项目代码，不自动覆盖运行库。
5. 生成来源记录、校验值及可审计构建清单，完成干净构建和兼容性测试后，才手动发布产物。

开源许可证与编解码专利许可是不同问题。本项目不承诺提供覆盖所有编解码器或部署地区的专利许可。

主要文档：

- [FFmpeg 许可与分发说明](https://www.ffmpeg.org/legal.html)
- [FFmpeg 配置与许可详情](https://ffmpeg.org/doxygen/4.0/md_LICENSE.html)
- [ImageMagick 许可证](https://imagemagick.org/license/)
