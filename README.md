# lms-client-sdk

一个从 HAR 抓包反向工程而来的 UMU LMS（学习管理系统）Python SDK + Web 管理工具。

> 面向 `www.umu.cn` 企业版 API 的客户端 SDK，提供 HTTP 客户端、认证处理、API 端点封装、本地数据持久化（SQLite/PostgreSQL）及数据导出（CSV/Excel/JSON）能力。配套 Flask Web 应用提供可视化数据同步与课程治理审核界面。

---

## 架构概览

项目采用**双层架构**，SDK 核心层与 Web 应用层职责分明、松耦合：

```
Web 应用层 (src/web/)
├── Flask 路由 (app.py) — REST API + SSE + 页面渲染
├── 后台同步服务 (sync_service.py) — 用户/课程数据同步
├── 治理审核服务 (governance_service.py) — 课程合规检查
└── 前端模板 + 静态资源 — Jinja2 + Vanilla JS
         ↓ 调用 SDK
SDK 核心层 (src/lms_client/)
├── HTTP 客户端 (client.py) — 请求/重试/分页/批量
├── 认证模块 (auth.py) — Cookie / Token / AES 加密
├── API 端点 (endpoints/) — 各域业务方法封装
├── 持久化 (storage/) — ORM + 导出
└── CLI (cli.py) — 命令行工具
```

**设计原则**：SDK 层可独立作为 Python 包使用（`pip install`），Web 层基于 SDK 构建可视化界面。

---

## 技术选型

| 领域 | 技术 | 最低版本 |
|------|------|---------|
| 编程语言 | Python | >= 3.10 |
| HTTP 客户端 | `requests` | >= 2.31.0 |
| 数据验证 | `pydantic` | >= 2.5.0 |
| ORM / 数据库 | `SQLAlchemy` | >= 2.0.0 |
| 数据导出 | `pandas` + `openpyxl` | >= 2.1.0 / >= 3.1.0 |
| Web 框架 | `Flask` | >= 3.0.0 |
| 密码加密 | `cryptography` | >= 42.0.0 |
| 配置管理 | `python-dotenv` | >= 1.0.0 |

---

## SDK 核心

### HTTP 客户端 (`client.py`)

基于 `requests.Session` 封装，面向 UMU API 提供以下能力：

**路径参数替换**
```python
client.get("/uapi/v1/course/{course_id}", path_params={"course_id": "12345"})
```

**自动重试与指数退避**
- `LMSAuthError` (401/403) — 触发认证刷新后重试
- `LMSRateLimitError` (429) — 退避后重试
- `requests.RequestException` — 网络层故障重试

**分页自动遍历** — `list_all()` 智能识别 UMU 分页格式，提取 `total_page_num` 精确遍历全部页面：
```python
users = client.list_all("/uapi/v1/enterprise/user-list", data_key="data")
```

**批量并发操作** — `batch_get()` / `batch_create()` 使用 `ThreadPoolExecutor`（默认 5 并发），单点失败不影响整体：
```python
results = client.batch_get(
    ids=[1, 2, 3],
    path_template="/uapi/v1/course/{id}",
    id_key="id"
)
```

### 认证模块 (`auth.py`)

采用**策略模式**，通过 `AuthBase` 抽象接口统一不同认证方式：

| 策略 | 类名 | 机制 |
|------|------|------|
| Cookie 会话 | `SessionAuth` | 复用 `requests.Session` 自动管理 Cookies |
| Bearer Token | `TokenAuth` | 注入 `Authorization: Bearer` 头，支持 Token 自动刷新 |
| UMU 专属会话 | `UMUSessionAuth` | Cookie 登录 + AES-256-CBC 密码加密 |

**UMU 登录流程**（`UMUSessionAuth`）：
1. GET `/auth/login` 获取页面内联 JS 中的 anti-CSRF token
2. 使用 `cryptography` 的 AES/CBC/PKCS7 模式加密密码
3. POST `/passport/ajax/account/login` 建立 Cookie 会话

**AuthFactory** 支持从 HAR 分析元数据自动选择认证策略：
```python
auth = AuthFactory.create_from_har_analysis(har_auth_info)
client = LMSClient(auth=auth)
```

### API 端点 (`endpoints/`)

每个域独立成模块，采用**显式方法**设计——为每个发现的 API 路由定义精确命名的方法，使代码与实际 UMU 接口一一对应：

```python
# organizations.py
class OrganizationEndpoint(EndpointBase):
    def list_departments_by_level(self, level: int = 1) -> list[dict]: ...
    def batch_add_user_to_group(self, user_ids: list[str], group_id: str) -> dict: ...
```

`EndpointBase` 提供通用基础方法（`list/get/create/update/delete`），具体类在此基础上扩展业务方法。

### 持久化与导出 (`storage/`)

**数据库层**
- `DatabaseManager`：SQLAlchemy 封装，支持 SQLite 和 PostgreSQL 双后端
- `models.py`：声明式 ORM 模型（`User`、`Course`、`Organization`、`Session`、`GovernanceRun` 等）
- `save()`：使用 `session.merge()` 实现 bulk upsert（按主键插入或更新）
- `migrate_columns()`：轻量级列迁移，运行时自动检测并添加缺失列，无需 alembic

**数据导出** — `DataExporter` 基于 pandas 将数据库查询结果导出为 CSV、Excel（xlsx）或 JSON 格式，支持批量导出所有表。

---

## Web 应用

采用**混合模式**：页面路由由 Flask 渲染 Jinja2 模板，数据交互使用 RESTful JSON API + Server-Sent Events (SSE) 实时推送。

| 文件 | 职责 |
|------|------|
| `app.py` | Flask 路由：登录/登出、同步 API、治理 API、SSE 流、Excel 导出 |
| `sync_service.py` | 后台用户同步、课程同步、小节级联拉取 |
| `governance_service.py` | 课程合规审核引擎（8 条规则） |
| `templates/` | 登录页和主应用页（Jinja2） |
| `static/` | CSS 样式和前端 JS 逻辑 |

### 后台同步服务

`SyncService` 使用 `threading.Thread`（daemon）在后台执行数据同步：

- **用户同步**：调用 `/ajax/enterprise/getUserList`，分页拉取普通用户和管理员，以 `umu_id` 为主键 upsert
- **课程同步**：调用 `/ajax/enterprise/getReportGroupList`，支持日期范围筛选，级联拉取课程小节，处理章节容器嵌套，检测封面图片变化

### 治理审核引擎

`GovernanceService` 实现可配置的课程合规审核规则引擎，共 **8 条规则**：

| 规则 | 名称 | 检查内容 |
|------|------|---------|
| 1 | 课程名称 | 标题是否涉及非培训禁词（含例外词白名单） |
| 2 | 课程形式 | 标题与 lesson_type 是否一致 |
| 3 | 内容分类 | 是否包含通用力/专业力/领导力/新兴力分类 |
| 4 | 课程介绍 | 描述非空、非占位符，或含图片介绍 |
| 5 | 课程学时 | 是否设置学时且不超过最大阈值 |
| 6 | 课程评价/考试 | 是否包含评价或考试小节 |
| 7 | 必修小节 | 不能所有小节均为选修 |
| 8 | 课程课件 | 是否上传有效课件文档 |

- **规则配置化**：所有参数持久化到 `governance_configs` 表，支持运行时动态调整
- **断点续审**：应用重启时自动将遗留的 `running` 状态标记为 `interrupted`，续审时跳过已审核课程

### 实时进度推送 (SSE)

同步和治理任务使用 Server-Sent Events 向浏览器推送实时进度，前端通过 `EventSource` 接收事件驱动进度条更新，无需轮询。

**会话管理**：UMU 的 `requests.Session` cookies 经 **pickle + base64 序列化** 存入 Flask session，后台线程通过 `deserialize_session()` 还原会话。

**权限控制**：基于 UMU API 返回的 `role_type == "4"` 判断管理员身份，所有同步和治理操作要求 `is_admin == true`。

---

## 错误处理

`exceptions.py` 定义了以 `LMSAPIError` 为根的异常层次：

| HTTP 状态码 | 异常类 | 场景 | 自动重试 |
|-------------|--------|------|---------|
| 401 / 403 | `LMSAuthError` | 认证失败 / 权限不足 | 是（触发 refresh） |
| 404 | `LMSNotFoundError` | 资源不存在 | 否 |
| 429 | `LMSRateLimitError` | 请求频率限制 | 是（指数退避） |
| 400 / 422 | `LMSValidationError` | 参数校验失败 | 否 |
| 网络层 | `LMSAPIError` | 连接超时 / DNS 失败 | 是 |

---

## CLI 入口

`cli.py` 提供命令行工具 `lms-cli`（由 `pyproject.toml` 注册入口点）：

| 命令 | 功能 |
|------|------|
| `lms-cli login` | 认证测试，验证账号密码 |
| `lms-cli list-users` | 导出用户列表为 CSV / Excel / JSON |
| `lms-cli sync` | 同步 API 数据到本地 SQLite 数据库 |
| `lms-cli export-all` | 批量导出所有数据表 |

---

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 运行测试
pytest

# 启动 Web 应用
python src/web/run.py

# CLI 使用
lms-cli --help
```

---

## 设计目标

1. **可靠性** — 指数退避重试、`total_page_num` 精确分页、治理审核断点续审
2. **性能** — `ThreadPoolExecutor` 批量并发、SSE 实时推送替代轮询、数据库批量 upsert
3. **可扩展性** — SDK 与 Web 解耦、AuthBase 策略模式、治理参数运行时可调
4. **数据完整性** — ORM merge 主键级 upsert、课程同步级联拉取、Session cookies 序列化复用

---

*文档生成时间：2026/05/13 | lms-client-sdk v0.1.0*
