# Git + uv 部署

本页说明从 Git 仓库部署当前审阅版。Linux 示例采用单实例运行。Windows Server 可按下节启动，也支持使用 Git bundle 离线更新。

## Windows Server

在服务器上克隆仓库，进入项目目录，在 PowerShell 中运行：

```powershell
uv sync --frozen
$env:EXPERIMENT_CONFIG = (Resolve-Path 'configs/study.json').Path
uv run --frozen streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

更新时先停服，在现有仓库执行 `git pull --ff-only`，再重跑上述命令。使用离线发布包时，可将 `git pull` 替换为以下命令，路径按实际文件调整：

```powershell
git fetch C:\deploy\CounterSpeech.bundle main
git merge --ff-only FETCH_HEAD
```

可在服务器本机浏览器访问演示。供合作者访问时，配置 HTTPS 反向代理并转发 WebSocket。长期运行可设 Windows 服务或计划任务。

## 1. 安装与重建环境

安装 Git、uv。uv 官方安装说明：https://docs.astral.sh/uv/getting-started/installation/

```bash
git clone YOUR_REPOSITORY_URL CounterSpeech
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

在 HTTPS 反向代理中把演示域名转发至 127.0.0.1:8502，允许 WebSocket 升级并保留 query string。可分享演示首页，或添加 `?condition=review_direct_mixed` 的固定条件链接。

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
