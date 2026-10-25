# CounterSpeech 微博实验

Streamlit + 原生 JavaScript 组件。流程：前测填写 → 变量解析 → 微博交互 → 后测 → 提交成功与完成码。

合作者演示版：见 [发布说明](docs/RELEASE.md) 和 [服务器部署步骤](docs/DEPLOYMENT.md)。分享用固定材料位于 `configs/study.json`，包含恢复的 p02、u06 和新增前测题。

## 推荐启动方式：uv

安装 uv 后，在项目目录执行：

```powershell
uv sync --frozen
uv run --frozen streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

本机 uv 的实际路径为 `C:\Users\ADMIN\.local\bin\uv.exe`；如命令尚未加入 PATH，可用 `& 'C:\Users\ADMIN\.local\bin\uv.exe'` 替代上述 uv。

`pyproject.toml` 声明依赖，`.python-version` 指定 Python 3.10，`uv.lock` 固定解析结果。服务器通过 `git clone` 和 `uv sync --frozen` 重建环境；`.venv` 不进入 Git、不跨系统复制。

## 四种入口

在 PowerShell 中先进入项目：

```powershell
cd C:\Users\ADMIN\Desktop\CounterSpeech
```

正式入口（创建会话时，由服务端对已配置条件组合等概率随机分配）：

```powershell
& 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe' -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

固定条件演示入口（研究者选择完整组合，或使用 `?condition=local_province` 等链接）：

```powershell
& 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe' -m streamlit run demo.py --server.address 127.0.0.1 --server.port 8502
```

管理与预览入口：

```powershell
& 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe' -m streamlit run admin.py --server.address 127.0.0.1 --server.port 8503
```

分别访问 `http://127.0.0.1:8501`、`http://127.0.0.1:8502`、`http://127.0.0.1:8503`。保持终端打开，Ctrl+C 停止。这些命令不会安装依赖。本轮开发后未自动启动任何服务。

数据回收浏览入口（PowerShell 7，先设置当前终端的访问密码）：

```powershell
$env:RESEARCHER_PASSWORD = Read-Host '设置研究者访问密码' -MaskInput
& 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe' -m streamlit run data_view.py --server.address 127.0.0.1 --server.port 8504
```

打开 `http://127.0.0.1:8504` 并输入刚设置的密码。部署时由服务器环境变量提供密码，并通过 HTTPS／反向代理访问；不要把密码放进 URL 或提交到配置文件。未设置密码时，此页不会读取或显示回收数据。配置管理页仍应仅限本机或已有研究者认证的内网入口。

正式入口忽略链接中的条件参数。演示入口与正式入口使用独立的浏览器恢复标识和数据库；管理预览也单独保存。随机为每个新会话独立抽样，不保证最终样本量严格相等。新开标签页会恢复同一浏览器中的已有会话。

## JSON 与管理页

运行入口默认优先读取已发布的 `data/study.draft.json`，其次为仓库内的 `configs/study.json`，再回退至 `docs/study.example.json`。设置 `$env:EXPERIMENT_CONFIG = '配置路径.json'` 可覆盖来源。分享及服务器演示建议明确指定 configs/study.json。

管理端会自动保存当前工作到 `data/admin.work.json`（可用 ADMIN_WORKING_CONFIG 指定路径），并在刷新或重启后恢复。这里仅保存研究者预设，不包含被试回答；即使工作状态尚未通过校验也可保留。应用编辑不等于发布：点击“校验并发布配置”才更新供参与者读取的 data/study.draft.json，保存失败继续保留先前运行版本。原有旧模板和草稿不自动删除。

示例只保留 `local_province`（本省）和 `other_province`（其他省）两个条件。它们是可运行的流程示例，条件组合和量表须按正式方案修改；管理端仍可新增其他独立组合。

管理页可编辑：

- 发布者资料：支持新增用户，再编辑昵称、头像、认证、简介、IP 属地、关注数与粉丝数。
- 帖子和评论：支持新增帖子，从已有帖子复制独立材料及 10 条评论，再修改正文、来源、时间、初始赞数、图片与回复树。新帖子需在“条件组合”中勾选才会展示；首次加入组合默认平铺评论，随后可设置回复树并检查必展示目标。
- 实验变量：注册变量名和用途，在正文使用 `{展示地名}` 等占位符。
- 条件组合：显式新增入口，以当前组合为模板创建独立组合；可调整所选帖子、变量规则及评论树。
- 前后测题目：独立的新增／编辑表单，自动提供题目 ID、有效题块和插入位置，按题型显示相关字段。支持新增题块、调整固定顺序或随机顺序，并附字段说明。
- 浏览完成条件与完整流程预览：包括前测、解析后的帖子、后测和最终提交。

先提交各编辑表单，工作草稿会自动保存；确认后点“校验并发布配置”。修改已发布配置时更新版本号；失败不会覆盖运行版本。选择题选项可每行一个，或使用单行逗号列表（如 `1,2,3,4,5,6,7`）；多行选项中的逗号保留在选项文字里。JSON 下载入口位于预览页。

## 前后测结构

`flow.pre` 与 `flow.post` 采用同样结构：

```json
{
  "block_order": "fixed",
  "blocks": [{
    "id": "attitudes",
    "question_order": "random",
    "questions": [{
      "id": "q01",
      "label": "题目内容",
      "type": "single_choice",
      "required": true,
      "options": ["选项一", "选项二"]
    }]
  }]
}
```

`block_order` 控制块之间的顺序，`question_order` 控制块内题序，均可为 `fixed` 或 `random`。数组先后即固定顺序。实际题序在创建会话时生成一次并保存，刷新不重排；每个阶段当前在同一页面展示。

支持 `text`（可设 max_length）、`single_choice`、`multiple_choice`、`number`（可设 min/max）、`location`。量表可使用单选选项实现。location 为前测省市区联动题，保存行政代码及显示名，当前最多一个。题目和题块 ID 跨前后测唯一，题干可以调整，正式采集期间保持 ID 与版本稳定。

## 变量规则

每个条件的 `variable_rules` 对注册变量分别配置 `{kind, value}`：

| kind | value |
| --- | --- |
| answer | 前测题目 ID，或 province / city / district |
| literal | 固定文本 |
| other_province | 候选省级代码，例如 `31,44` |
| other_district | 候选区县代码，例如 `310101,310104` |

候选按配置顺序取第一个不同于被试的地点，后面的候选即备用。other_district 不自动保证同市、相邻或具体公里距离；研究者须明确候选地点的含义。没有可用候选时拒绝进入交互。变量依赖题必须设为必答。

前测确认后按分配条件解析并固定，不能返回更改。保存前测回答、原始文本模板、最终变量值及实际展示文本。替换只处理注册占位符，不执行表达式。省市区数据为本地快照，覆盖 31 个省级条目，来源与许可证见 `assets/SOURCES.md`，正式使用前核对覆盖范围和版本。

用于正文的省／市名称使用自然简称，如上海市→上海、广东省→广东、广西壮族自治区→广西。前测中的行政全名与代码仍完整记录，literal 固定文本不自动修改。示例正文为“最近有不少外国人来{展示地名}工作和旅游……”。

### 用户 IP 属地变量

发布者资料新增“IP 属地显示方式”：

| 方式 | 配置示例 | 作用 |
| --- | --- | --- |
| 固定地名 | location_mode=literal，location=上海 | 始终显示上海；留空不显示 |
| 前测字段 | location_mode=answer，location=province | 显示被试前测省份的自然简称 |
| 注册变量 | location_mode=variable，location=展示地名 | 使用该条件解析后的展示地名，可能为本省或其他省 |
| 文本模板 | location_mode=template，location={province} | 替换模板中的前测字段或注册变量 |

旧配置未声明 location_mode 而直接填 province/city/district 时，也会按前测来源解析。其他普通地名保持固定文字。动态属地依赖的前测题必须为必答，引用错误会在保存时阻止通过。

属地在确认前测时与正文变量一起固定，实际显示值和原始设置均保存；修改对新会话生效，不重写旧会话。这里控制的是模拟账户显示的属地，不采集或定位被试的真实网络 IP。

## 交互与数据

微博信息流点击评论数原位展开，点击发布时间进入正文。SVG 操作图标，JSON 驱动的头像和资料弹窗，`img` 配图及放大查看。点赞可取消，回复与新评论可提交；转发位置仅静态展示。预设评论不按热度重排。

默认要求必展示评论正文至少 50% 连续可见 2 秒，页面在前台且未被资料／图片弹窗遮挡。达成后才能进入后测。展示机会不能证明阅读。

管理页将这一设置称为“浏览完成条件”，并解释比例、连续时长、中断与保存规则。它不改变评论顺序或将目标置顶。

评论的 `relative_time_minutes` 是晚于原帖发布的分钟数。帖子的 `age_minutes` 是固定模拟浏览时点距原帖发布的分钟数；评论显示距当前模拟时点 `age_minutes - relative_time_minutes` 分钟。例如原帖 60 分钟前发布、评论晚于原帖 5 分钟，则显示 55 分钟前。不存在真实系统时间戳加法，不同被试看到相同配置的时间。回复不能早于父评论，所有评论均不能晚于模拟浏览时点。旧配置没有相对时长时仍支持原时间文案。

| 数据库 | 用途 |
| --- | --- |
| data/responses.sqlite3 | 正式入口会话、条件、题序、回答、交互事件及最终完成码 |
| data/demo.sqlite3 | 固定条件演示（保留旧 demo 数据） |
| data/admin-preview.sqlite3 | 管理预览 |

SQLite 事务保存，事件 ID 去重；最终提交重试不会生成多份回答。完成码在后测成功落库后生成。浏览器 localStorage 仅存恢复令牌与尚待确认的事件，服务端存令牌哈希；链接不带居住信息或恢复令牌。不自动实现跨设备恢复或真人去重。图片文件不要原路径覆盖，以免改变已有会话的刺激材料。

## 数据回收浏览页

`data_view.py` 是独立的只读页面，默认查看正式回收，也可切换演示或管理预览数据。顶部显示会话总数、已提交、未提交及当前筛选数量；支持按阶段、条件 ID、完成码或记录 ID 筛选，分页显示并手动刷新。

每条记录初始折叠为一行摘要，点击向下展开：

- 前后测回答：按保存的实际题序展示，对照该会话的题干版本。
- 行为时间线：服务端接收时间、操作对象、点赞变化、曝光时长和已提交文本。
- 实际展示材料：变量结果、用户资料、帖子与评论，以及原始模板。
- 原始记录：完整状态、配置快照与事件 JSON。

时间统一显示为北京时间。一次会话不等于一个独立真人样本；未提交的会话可能仍在填写，不能据此判定退出。旧版仅完成交互的记录不计为“已提交后测”。只读连接不创建缺失数据库，也不提供删除或修改操作。

## 验证与当前边界

```powershell
& 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe' -m unittest discover -s tests -v
```

2026-10-25：在 uv.lock 重建的干净环境中，28 项测试通过。新增工作草稿刷新／重启恢复、未完成工作不覆盖已发布配置检查，原有属地、登录、只读浏览与实验流程回归通过。AppTest 的表单测试隔离了自定义 JS 预览渲染；本轮未启动浏览器做新版全流程测试，也未部署服务器。

管理页没有登录验证，保持仅本机访问。正式部署需为 `app.py` 配置 HTTPS 和持久存储，并锁定正式 JSON；管理页与演示入口不作为招募入口公开。当前 SQLite 适合单实例试用，尚未做并发负载、断网恢复、真实手机和 Safari 验证。示例题目与材料不是经过验证的量表，正式采集前须替换与预测试。
