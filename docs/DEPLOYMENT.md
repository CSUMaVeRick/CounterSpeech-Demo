# Git + uv 部署

Windows Server 可按下节使用 Git bundle；后续章节以单实例 Linux 服务器为例。

## Windows Server：通过 bundle 更新

无需 Nginx、Caddy 或宝塔即可直接运行。0.1.1 修复了公网 HTTP 下 `crypto.randomUUID is not a function` 的启动错误；HTTP 仍不提供传输加密，正式回收应配置 HTTPS。

先在运行 Streamlit 的终端按 Ctrl+C 停服，把新 bundle 上传到服务器。在已有项目目录运行以下 PowerShell 命令，将 bundle 路径改为实际位置：

```powershell
git fetch C:\deploy\CounterSpeech-v0.1.1.bundle main
git merge --ff-only FETCH_HEAD
uv sync --frozen
uv run --frozen streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

然后刷新原来的 IP 地址页面。合作者演示可将 `app.py` 换成 `demo.py`。更新不包含数据库或本地管理草稿，也不会清空已有回收记录。如果 Git 提示本地修改冲突，先保留修改，不要使用强制重置。

新安装时先安装 Git 和 uv，再运行 `git clone C:\deploy\CounterSpeech-v0.1.1.bundle CounterSpeech`、`cd CounterSpeech`，接着执行上面的 `uv sync` 和启动命令。云安全组及 Windows 防火墙需允许选定端口。终端前台运行适合验证；正式持续运行需另设 Windows 服务或任务计划。

启用 HTTPS 需要证书和 TLS 服务入口，Streamlit 本身也有证书配置选项。反向代理是常见方案，但不是唯一方式。没有域名也可以申请公网 IP 证书；Let's Encrypt 的 IP 证书有效期约六天，必须安排自动续期。自签证书会触发浏览器信任警告，不适合直接向被试分发。

参考：[Let's Encrypt IP 证书](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)、[Streamlit 配置](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)。

## 1. 安装与重建环境

安装 Git、uv。uv 官方安装说明：https://docs.astral.sh/uv/getting-started/installation/

```bash
git clone <你的仓库地址> CounterSpeech
cd CounterSpeech
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
```

提交到 Git 的是 Python 版本声明与锁文件，而不是 .venv。uv 在服务器本地创建适合该系统的环境。

## 2. 先开放合作者演示

```bash
export EXPERIMENT_CONFIG="$PWD/configs/study.json"
uv run --frozen streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

在 HTTPS 反向代理中把演示域名转发至 127.0.0.1:8502，允许 WebSocket 升级并保留 query string。可分享条件选择首页，或添加 `?condition=local_province` / `?condition=other_province` 的固定条件链接。

通过 SSH 临时试用也可将远端 8502 转发到本机：`ssh -L 8502:127.0.0.1:8502 <服务器>`。此时本机用 localhost 访问；正式公网访问使用 HTTPS 保护传输中的回答与会话令牌。

前台命令用于验证；长期运行可采用服务器现有的 systemd 管理。示例 unit 如下，将仓库路径、用户、uv 路径替换为真实值：

```ini
[Unit]
Description=CounterSpeech collaborator demo
After=network.target

[Service]
User=research
WorkingDirectory=/srv/CounterSpeech
Environment=EXPERIMENT_CONFIG=/srv/CounterSpeech/configs/study.json
ExecStart=/home/research/.local/bin/uv run --frozen streamlit run demo.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

这是示例，不会自动创建服务、监听公网或修改防火墙。无需在本版同时开放全部四个入口。

## 3. 数据与管理

- data/ 是本机持久目录，不进 Git；部署账号需有写权限。备份数据库应使用 SQLite backup API 或在停服后复制，不能只拷贝活跃数据库主文件而遗漏 WAL。
- 演示数据写 demo.sqlite3，正式 app.py 写 responses.sqlite3，预览另存。合作者试用不会写入正式回收库。
- 正式招募前，锁定经审阅的 JSON，用 app.py 替代 demo.py 启动单独服务；正式入口不会接受 URL 指定条件。
- admin.py 仅对研究者的内网／SSH 转发开放，当前没有单独登录验证。
- data_view.py 应设 RESEARCHER_PASSWORD，并使用独立的研究者 HTTPS 入口。密码通过服务环境或限制权限的服务器环境文件提供，不放进 Git 或 URL。
- 服务器部署账号与静态文件配置不能把 data/、.env 或整个仓库作为可下载目录公开。

## 4. 更新

先停止实验服务，再执行：

```bash
git pull --ff-only
uv sync --frozen
```

核对 EXPERIMENT_CONFIG 版本，再启动服务。Git 更新不会替换被忽略的回收数据库和工作草稿。正在采集的版本不应直接更新材料；先在演示环境验证。

## 参考

- uv 项目结构与锁文件：https://docs.astral.sh/uv/guides/projects/
- 冻结依赖同步：https://docs.astral.sh/uv/concepts/projects/sync/
- Streamlit 部署概念：https://docs.streamlit.io/deploy/concepts
- 多入口反向代理：https://docs.streamlit.io/knowledge-base/deploy/deploy-multiple-streamlit-apps-different-subdomains
