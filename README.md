# CounterSpeech 微博实验

在模拟微博信息流中测试反驳评论及其赞踩反馈。当前审阅版包含三个婚育场景，三种反驳方式与三档反馈交叉成九个条件。流程为前测、浏览与互动、后测和 JSON 完成页。

## 本地启动

项目使用 Python 3.10。在仓库根目录运行：

```powershell
uv sync --frozen
uv run --frozen streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

打开 [本地演示](http://127.0.0.1:8502/)，在页面顶部选择反驳方式和反馈档位。已有 Windows 项目虚拟环境时，也可运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

`uv.lock` 固定依赖版本。使用 pip 的环境可从 `requirements.txt` 安装。

## 应用入口

用相同的启动命令替换脚本和端口即可打开其他入口。

| 脚本 | 用途 | 建议端口 |
| --- | --- | ---: |
| `demo.py` | 固定条件演示，供审阅材料和流程 | 8502 |
| `app.py` | 正式参与者入口，按服务端分配条件 | 8501 |
| `admin.py` | 研究者配置与预览 | 8503 |
| `data_view.py` | 只读数据浏览 | 8504 |

当前配置启用 `review_only`，正式入口暂停招募。管理页仅供本机或受控内网使用。启动数据浏览入口前，在运行进程的环境中设置 `RESEARCHER_PASSWORD`。部署配置见[服务器部署说明](docs/DEPLOYMENT.md)。

## 目录

```text
counterspeech/      共享应用代码、配置校验、分配、交互记录
frontend/           Streamlit 组件的 JavaScript 和 CSS
configs/study.json  当前演示材料、前后测与九个实验条件
configs/examples/  历史示例配置，供兼容性测试及配置参考
assets/            头像、示例图片、省市区数据和来源说明
docs/              配置、部署和历史设计记录
tests/             Python 和前端回归测试
```

## 配置与数据

在 `configs/study.json` 修改原帖、评论、反驳文案、赞踩档位和前后测。通过 `EXPERIMENT_CONFIG` 可为启动进程指定其他配置文件。字段说明和管理页操作见[实验配置与数据](docs/CONFIGURATION.md)。

`data/` 存放本机草稿和回收数据库，演示、正式回收及管理预览使用各自的数据库。该目录与虚拟环境、日志、缓存和密钥文件都在 Git 忽略范围内。

早期发布说明和原始交互稿见[历史记录](docs/archive/)。

## 测试

```powershell
uv run --frozen python -m unittest discover -s tests -v
```

安装 Node.js 后会一并运行前端组件的 JavaScript 回归检查。
