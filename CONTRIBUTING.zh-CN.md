# 贡献指南

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md)

提交更改前，请运行只依赖 Python 标准库的检查：

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public.py
python3 tools/package_source.py
```

使用合成媒体，并在测试数据中使用 `test-user` 等虚构用户名。不要提交私人 NAS 地址、账号标识、密码、OTP、会话、密钥、原始媒体、解码器二进制文件、已下载的套件或原始诊断记录。

支持新的 Photos 版本，需要在真实 NAS 上用范围受限的合成素材验证：缺失结果、生成、Photos 接收、停止与启动、卸载，以及原件和生成资源均被保留。明确说明未测试的客户端和格式。

保持协调进程的更改范围较小，审查权限、文件路径、进程生命周期及错误处理的影响。涉及 API 认证、root 部署、版本检查、解码隔离或依赖许可证的更改，需要额外审查。

当前锁定的 nonfree FFmpeg 构建阻止公开分发二进制包。不要添加上传私有构建产物或需要 NAS 凭据的工作流。提出发布自动化前，请阅读 [分发说明](docs/distribution.zh-CN.md)。

NAS 上安装的程序与开发仓库相互独立；测试和构建不得自动 SSH 登录或更新用户的 NAS。
