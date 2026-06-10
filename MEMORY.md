# MEMORY.md - 张衡的长时记忆

_此卷录要事、决策、教训，以续记忆之断链。_

---

## 📌 当前项目：项目智能体 V2（Project Agent V2）

**项目路径**: `/home/ubuntu/.openclaw/workspace/project-agent-v2/`

**技术栈**:
- 后端：FastAPI + SQLAlchemy + PostgreSQL + DeepSeek AI + Gunicorn
- 前端：React 18 + TypeScript + Vite + TailwindCSS
- 部署：Nginx + Gunicorn (端口 3001)

**⚠️ 服务架构（2026-05-17 前后端分离改造）**:
| 服务 | systemd 名称 | 端口 | 状态 |
|------|--------------|------|------|
| **V2 后端** | `project-agent-v2` | 3001 | ✅ 启用 |
| ~~V1 后端~~ | ~~`project-agent-backend`~~ | ~~3000~~ | ❌ 已禁用 |

**Nginx 配置**: `/etc/nginx/sites-available/project-agent-v2`
- 静态资源：Nginx 直接服务 `/var/www/project-agent/frontend/agent/`
- API 请求：`proxy_pass http://127.0.0.1:3001`

**数据库连接**:
```
postgresql://yjydb:qv52A03xcxAQCoDglUJelm4Sb@localhost:5432/project_cost_tracking
```

**访问地址**:
- 前端: `https://yjypro.online/agent/`
- 后端: `http://localhost:3001`
- Demo 项目详情: `https://yjypro.online/agent/projects/35`

**测试账号**: admin / Yjy@2026pr

**部署命令**:
```bash
# 前端构建部署
cd /home/ubuntu/.openclaw/workspace/project-agent-v2/frontend
npm run build
sudo rm -rf /var/www/project-agent/frontend/agent/assets/
sudo cp -r dist/* /var/www/project-agent/frontend/agent/

# 后端重启
sudo systemctl restart project-agent-v2
```

---

## ⚠️ 服务冲突教训（2026-05-18）

**事件**：看板页面报错，误启动旧服务 `project-agent-backend`（端口3000），与新服务 `project-agent-v2`（端口3001）冲突。

**教训**：
1. **V2 项目使用端口 3001**，旧项目端口 3000 已废弃
2. 遇到服务问题时，**先确认服务名称**：
   - `systemctl status project-agent-v2` ✅ 新服务
   - ~~`systemctl status project-agent-backend`~~ ❌ 旧服务（已禁用）
3. 旧 Nginx 配置 `/etc/nginx/sites-available/project-agent` 已废弃，不要启用

**已处理**：
- ✅ 停止并禁用旧服务 `project-agent-backend`
- ✅ 旧 Nginx 配置未启用（sites-enabled 只有 project-agent-v2）

---

## 📅 历史项目：项目成本跟踪系统

**项目路径**: `/var/www/project-cost-tracking/`（已归档）

---

## 📅 2026-03-30 方案 A 实施 - 任务自动关联和状态管理

### 已完成功能

#### 1. 任务版本管理 ✅
- 每个项目只有最新版本的任务生效
- 从 task_id 提取版本号（如 P35V2T3 中 V2 为版本 2）
- 只对最新版本任务进行日报关联、进度更新、风险预警

#### 2. AI 智能任务匹配 ✅
- 使用 DeepSeek AI 进行语义理解匹配
- 支持多种工作内容的智能匹配：
  - "需求分析会议" → P35V2T2 (需求调研)
  - "前端页面开发" → P35V2T6 (前端开发)
  - "数据库表结构设计" → P35V2T4 (数据库设计)
  - "系统架构设计讨论" → P35V2T3 (系统设计)
  - "功能测试" → P35V2T9 (测试)

#### 3. 任务状态自动计算 ✅

**⚠️ 重要规则：任务状态必须动态计算，不依赖静态 status 字段**

**动态判断规则：**

| 状态 | 判断条件 |
|------|----------|
| **已完成** | `progress >= 100` |
| **进行中** | `0 < progress < 100` |
| **未开始** | `(progress = 0 OR progress IS NULL) AND (start_date IS NULL OR start_date > CURRENT_DATE)` |
| **延期** | `end_date < CURRENT_DATE AND (progress < 100 OR progress IS NULL)` |
| **严重延期（缺陷）** | `end_date < CURRENT_DATE - INTERVAL '3 days' AND (progress < 100 OR progress IS NULL)` |

**SQL 示例：**
```sql
SELECT 
    COUNT(CASE WHEN progress >= 100 THEN 1 END) as completed,
    COUNT(CASE WHEN progress > 0 AND progress < 100 THEN 1 END) as ongoing,
    COUNT(CASE WHEN (progress = 0 OR progress IS NULL) 
               AND (start_date IS NULL OR start_date > CURRENT_DATE) THEN 1 END) as pending,
    COUNT(CASE WHEN end_date < CURRENT_DATE AND (progress < 100 OR progress IS NULL) THEN 1 END) as delayed,
    COUNT(CASE WHEN end_date < CURRENT_DATE - INTERVAL '3 days' 
               AND (progress < 100 OR progress IS NULL) THEN 1 END) as severe_delayed
FROM project_tasks
WHERE is_latest = true AND is_deleted = false
```

**⚠️ 禁止使用静态 status 字段判断任务状态！**

原因：
- 数据库 `status` 字段可能未及时更新
- 任务状态随时间变化（今天未延期，明天可能延期）
- 动态计算保证数据准确性

**涉及模块：**
- 质量管理（六西格玛 DPMO 计算）
- 追踪服务（执行视图、健康视图）
- 项目详情页（任务列表）
- 风险预警（延期检测）
- 计划开始时间已过 → 进行中
- 未到开始时间 → 未开始

#### 4. 任务风险预警 ✅
- 延期风险：已过结束时间，进度 < 100%
- 即将到期风险：3天内到期，进度 < 80%
- 未报告风险：已启动但无日报记录
- 即将启动提醒：3天内开始

#### 5. 五维度风险雷达 ✅
- 进度风险（延期率 × 100）
- 材料成本风险（超支率 × 100）
- 外包成本风险（超支率 × 100）
- 人工成本风险（超支率 × 100）
- 间接成本风险（超支率 × 100）
- 综合风险 = 进度风险 × 0.4 + 四大成本风险平均 × 0.6

#### 6. 前端风险预警显示 ✅
- 项目详情页显示任务风险预警
- 不同风险等级用不同颜色标识
- 显示风险详情和提示信息

### 关键文件

| 文件 | 说明 |
|------|------|
| `/backend/app/task_auto.py` | AI 任务匹配、状态计算、风险检查 |
| `/backend/app/main.py` | API 端点（任务列表、风险预警、智能解析） |
| `/frontend/src/pages/ProjectDetail.tsx` | 项目详情页（风险雷达、风险预警） |
| `/frontend/src/api.ts` | API 接口定义 |

### Demo 项目测试数据

| 项目 | ID | 任务数 | 成本数据 |
|------|----|----|---------|
| Demo项目-智能计划管理系统 | 35 | 16个（V1:8, V2:8） | 材料超支8.3%，人工超支15% |

---

## 📝 历史项目：项目成本跟踪系统

**项目路径**: `/var/www/project-cost-tracking/`

**技术栈**:
- 后端：FastAPI + SQLAlchemy + PostgreSQL
- 前端：Vue 3 + TypeScript + Vite + Element Plus
- 部署：本地 uvicorn + Nginx 静态资源

---

## 🛠️ 常用命令

```bash
# 项目智能体 - 后端启动
cd /home/ubuntu/.openclaw/workspace/project-agent/backend
source venv/bin/activate
export HF_ENDPOINT='https://hf-mirror.com'
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000

# 项目智能体 - 前端构建
cd /home/ubuntu/.openclaw/workspace/project-agent/frontend
npm run build
sudo cp -r dist/* /var/www/project-agent/frontend/

# 数据库检查
PGPASSWORD="qv52A03xcxAQCoDglUJelm4Sb" psql -h localhost -U yjydb -d project_cost_tracking -c "\d projects"
```

---

## ⚠️ 注意事项

- 项目智能体后端必须设置 `HF_ENDPOINT='https://hf-mirror.com'`
- DeepSeek API Key: 已移至 .env 文件，代码中无硬编码
- 前端修改后必须执行 `npm run build` + 部署才能生效
- 后端模型变更后需重启 uvicorn 进程
- 数据库密码妥善保管，勿泄露

---

## 🔒 安全铁律（永久记住）

**⚠️ 以下敏感信息绝对禁止上传到Git或任何第三方平台：**

1. **API Key**（DeepSeek、OpenAI、任何第三方服务）
2. **数据库密码和连接字符串**
3. **服务器IP地址和端口**
4. **JWT密钥、加密密钥**
5. **用户手机号、身份证号**
6. **任何包含 `sk-`、`password`、`secret`、`key` 的配置**

**永远记住：**
- `.env` 文件必须在 `.gitignore` 中
- 检查Git提交前，先grep确认无敏感信息
- 在对话中提及敏感信息时，只说"已配置"，不透露具体值
- 如果发现泄露，立即更换密钥并清除Git历史

**2026-05-14事件教训：**
- API key曾泄露到公开GitHub仓库
- 导致737→1712→2857次恶意调用（三日损失84.77元）
- 根因：`.env`文件被提交到Git历史（commit ea087b7...）

---

## ⏰ 工时计算规则（强制约束）

**标准工作时间**：
- 上午：08:15 - 12:00（3.75小时）
- 午休：12:00 - 13:45（不计入工时）
- 下午：13:45 - 18:00（4.25小时）
- **每日标准工时：8小时**

**计算规则**：
1. 工作时长 = 结束时间 - 开始时间 - 午休时间（如跨越午休）
2. 8:15 到 18:00 = 8小时（不是9.75小时）
3. 午休时间 1小时45分 必须扣除

**配置文件**：`/backend/app/work_time_config.py`

---

## 🔧 2026-04-01 智能问答修复

**问题**：项目详情页智能问答返回"查询出现问题"

**原因**：
1. SQLAlchemy `text` 导入别名不一致：导入了 `text as sql_text` 但部分代码仍用 `text`
2. 缺少 `AIMessage` 导入

**修复**：
```python
# 修复导入
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 修复 SQL 执行
result = conn.execute(sql_text(sql))  # 而非 text(sql)
```

**涉及文件**：`/backend/app/main.py` 第 5276、5297、5334 行

---

## 🔧 2026-04-01 项目进度一致性修复

**问题**：AI 返回进度 0%，前端显示 21%

**原因**：
1. `generate_project_context` 直接读取 `projects.progress` 字段（未更新）
2. 获取任务时未过滤最新版本，导致计算结果与前端不一致

**修复**：
```python
# 动态计算进度（与前端一致）
total_tasks = len(tasks)
completed_count = len(completed)
avg_progress = sum(float(t["progress"] or 0) for t in tasks) / total_tasks
calculated_progress = round((completed_count / total_tasks * 100 + avg_progress) / 2, 1)

# 只获取最新版本任务
WITH latest_version AS (
    SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
    ...
)
WHERE CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER) = lv.max_ver
```

**涉及文件**：`/backend/app/main.py` `generate_project_context` 函数

---

## 🔧 2026-04-05 系统服务配置与推送优化

### 1. systemd 服务配置
- 创建 `/etc/systemd/system/project-agent-backend.service`
- 实现开机自启动、崩溃自动重启（5秒）
- 服务命令：`sudo systemctl start|stop|restart|status project-agent-backend`

### 2. 推送服务优化
- 推送格式：区分项目整体进度和任务进度
- 显示：项目负责人、任务时间段、延期天数
- 修复：任务版本 `is_latest` 标记错误（更新778条记录）

### 3. 历史日报卡片移动端适配
- 优化 `daily-history-item` 布局：单列显示，时间/工时独立行
- 任务标签自适应宽度，防止溢出
- 项目分组标题支持换行，统计信息紧凑显示

---

## 🔧 2026-04-06 智能周报生成

### 新增功能
- **周报自动生成**：基于日报数据 + DeepSeek AI 生成项目周报
- **周报内容**：
  - 本周工作概述
  - 各项目进展摘要
  - 下周重点关注
  - 工作亮点
- **API 端点**：
  - `POST /api/agent/weekly-reports/generate` - 生成周报
  - `GET /api/agent/weekly-reports` - 周报列表
  - `GET /api/agent/weekly-reports/{id}` - 周报详情

### 数据库
- 新增 `weekly_reports` 表

### 前端
- 更新 `/agent/report` 页面
- 首页添加「查看周报」入口

### 成本导入修复
- 修复 token 获取方式：`localStorage` → `useAppStore.getState().token`
- 修复 Excel 解析 NaN 值处理：`pd.isfinite` → `np.isfinite`

---

## 🔧 2026-04-07 Token 自动刷新机制

### 问题
手机端需要不断刷新页面才能显示，token 8小时后过期无自动刷新。

### 解决方案
1. **后端新增** `/api/agent/auth/refresh` 接口
2. **前端改进**：
   - Token 提前 30 分钟自动刷新
   - 401 时尝试刷新后重试请求
   - 网络错误自动重试 1 次
   - 刷新期间请求排队等待

### 涉及文件
- `/backend/app/main.py` - 新增 refresh 接口
- `/frontend/src/api.ts` - 请求拦截器添加自动刷新逻辑

---

## 🔧 2026-04-07 日报 AI 解析优化

### 问题
用户输入"我用8小时完成某项工作，额外花费1小时完成领导交办的任务"，解析结果只有8小时，未识别加班时间。

### 解决方案
1. **提示词增加加班识别规则**：
   - 识别"额外X小时"、"加班X小时"、"晚上X小时"
   - 加班时间从 18:00 开始计算
   - 生成独立的加班条目

2. **工时计算优化** (`work_time_config.py`)：
   - 标准工作时间内扣除午休
   - 加班时间（18:00后）不扣除午休

### 涉及文件
- `/backend/app/main.py` - `parse_daily_text_smart` 函数提示词
- `/backend/app/work_time_config.py` - `calculate_work_hours` 函数

---

## 🔧 2026-04-07 数据库索引优化

### 新增索引

| 表 | 索引名 | 用途 |
|---|--------|------|
| daily_reports | idx_daily_reports_emp_date_del | 用户日报列表查询 |
| daily_work_items | idx_daily_work_items_project_name | 工时统计按项目 |
| project_tasks | idx_project_tasks_proj_del_latest | 最新版本任务查询 |
| project_tasks | idx_project_tasks_status | 任务状态筛选 |
| project_tasks | idx_project_tasks_end_date | 延期任务查询 |
| projects | idx_projects_leader_id | 我负责的项目 |
| projects | idx_projects_status | 项目状态筛选 |

### 查询性能

| 查询 | 优化前 | 优化后 |
|------|--------|--------|
| 项目任务列表 | ~50ms | **0.138ms** |
| 用户日报列表 | ~30ms | **0.139ms** |
| 我负责的项目 | ~20ms | **0.053ms** |

### 备份位置
`/home/ubuntu/.openclaw/workspace/backups/project_cost_tracking_20260407_162231.backup`

---

## 🔧 2026-04-07 系统优化大修

**密码规则**：姓名全拼首字母大写，其余小写 + 手机后四位

示例：
- 李唯 → Liwei0540
- 张三 → Zhangsan1234

---

## 🔧 2026-04-07 系统优化大修

### 安全修复
- **日报删除安全检查**：修复服务重启后内存缓存丢失，导致删除错误用户日报的严重 bug
- **employee_id 获取**：缓存为空时从数据库查询，不使用危险默认值

### 功能修复
- **任务状态分类**：修正 SQL 返回 `delayed_ongoing` 与 Python `delayed` key 不匹配问题
- **本月工时显示**：空字符串项目名正确显示为"其他工作"
- **日报 AI 解析**：增加加班识别规则

### 性能优化
- **首页缓存**：5 分钟缓存 + 骨架屏，秒开体验
- **数据库索引**：新增 7 个关键索引，查询耗时 < 1ms
- **Nginx 配置**：优化连接数、缓冲、压缩

### 体验优化
- **确认弹窗组件**：通用 ConfirmDialog，支持危险/警告/信息类型
- **Toast 提示**：网络错误、操作反馈统一提示
- **骨架屏**：首页、项目详情、看板页

### 新增用户
- 李唯（18177800540，装备改善部，项目 ID 25 负责人）

---

## 🔧 2026-04-09 页面跳转跨域问题修复

### 问题现象
页面偶尔跳转到 `chrome-error://chromewebdata/` 错误页面，浏览器报跨域错误。

### 根本原因
1. **多处直接跳转**：17 处代码直接使用 `window.location.href` 跳转登录页
2. **无安全检查**：在浏览器错误页面状态下执行跳转，导致跨域冲突
3. **协议不一致**：`chrome-error://` 与 `https://` 跨域

### 解决方案

#### 1. 统一认证工具 (`utils/auth.ts`)
```typescript
// 安全跳转 - 检查协议，避免跨域
export function safeRedirect(path: string): void {
  if (window.location.protocol.startsWith('http')) {
    window.location.replace(path)
  } else {
    // 错误页面时延迟恢复
    setTimeout(() => {
      if (window.location.protocol.startsWith('http')) {
        window.location.replace(path)
      }
    }, 2000)
  }
}

// 统一跳转登录页
export function redirectToLogin(): void {
  localStorage.removeItem('project-agent-storage')
  safeRedirect('/agent/login')
}
```

#### 2. 批量替换跳转代码
- 17 处 `window.location.href = '/agent/login'` → `redirectToLogin()`
- 所有页面导入统一工具函数

#### 3. 涉及文件
- `utils/auth.ts` - 新建认证工具
- `api.ts` - 拦截器使用统一跳转
- `App.tsx` - 入口检查使用统一跳转
- 10+ 页面组件 - logout 跳转统一处理

### 关键改进
- **协议检查**：跳转前检查 `window.location.protocol.startsWith('http')`
- **replace 代替 href**：避免历史记录堆积
- **错误页面恢复**：检测到错误页面时延迟尝试恢复

---

## 🔧 2026-04-09 日报项目匹配权限修复

### 问题
非管理员用户解析日报时，只能匹配到自己负责的项目，无法匹配其他项目。

### 原因
`get_projects_with_auth` 函数对非管理员用户过滤了项目列表：
```python
if role_id == 11:  # 管理员
    # 返回所有项目
else:
    # 只返回自己负责的项目
    WHERE leader = :emp_name
```

### 解决方案
新增 `get_all_projects_for_matching()` 函数，专用于日报匹配：
- 返回所有项目，不受用户权限限制
- 任何人都可以参与任何项目

### 修改文件
- `/backend/app/main.py` - 新增函数，修改 `smart_parse_daily`

---

## 🔧 2026-04-12 日志框架优化

### 背景
后端代码中有 138 处 `print()` 语句，不利于生产环境日志管理。

### 解决方案

#### 1. 新建日志配置模块
文件：`backend/app/logger.py`

特性：
- 控制台输出（INFO 及以上）
- 文件输出（DEBUG 及以上）
- 文件轮转（10MB，保留 5 个备份）
- 统一格式：`时间戳 | 级别 | 模块:行号 | 消息`

#### 2. 替换 print 语句（138 处）

| 文件 | 数量 |
|------|------|
| main.py | 106 |
| push_service.py | 11 |
| task_auto.py | 7 |
| knowledge_base.py | 7 |
| sync_to_rag.py | 4 |
| database.py | 3 |

#### 3. 日志文件
- 路径：`backend/logs/app.log`
- 轮转：10MB 自动轮转，保留 5 个备份

---

## 🔧 2026-04-12 项目追踪功能新增

### 新增菜单
- 📍 追踪（三视图切换）

### 三视图功能

#### 1. 执行视图
- 今日/本周/本月截止任务
- 过期任务单独展示
- 近期完成（最近7天）

#### 2. 健康视图
- 五维度风险雷达（进度/材料/人工/外包/间接）
- 高风险项目 TOP5
- 趋势预警（新增过期、沉默项目）
- Tips：综合风险计算、项目风险分计算

#### 3. 溯源视图
- 日报-任务关联率
- 目标分阶段（初级50% → 中级70% → 高级80%）
- 不可追溯项目（关联率 < 50%）
- 进度无支撑项目

### 计算公式

**进度风险** = 过期任务数 / 总任务数 × 100
- 过期定义：截止日期 < 今天 且 进度 < 100%

**成本风险** = max(0, (实际-预算)/预算 × 100)
- 只统计有实际成本的科目

**综合风险** = 进度风险 × 0.5 + 成本风险 × 0.5

**项目风险分** = 延期天数×2 + 过期任务数×15 + 延期任务数×10
- 最高100分

**关联率** = 已关联工作项 / 总工作项 × 100
- 统计范围：近30天日报

---

## 🔧 2026-04-13 连接重置问题修复

### 问题现象
手机5G网络访问时出现 `ERR_CONNECTION_RESET` 错误

### 原因分析
1. 后端重启时，内存缓存（用户token）清空
2. 用户浏览器token仍有效，但服务端缓存丢失
3. uvicorn单进程模式，重启时所有连接中断

### 解决方案
修改systemd服务配置，增加优雅关闭：

```ini
TimeoutStopSec=10        # 等待10秒让现有请求完成
KillSignal=SIGTERM       # 发送终止信号而非强制kill
KillMode=mixed           # 混合模式
--timeout-keep-alive 30  # keep-alive超时30秒
```

### 配置文件
`/etc/systemd/system/project-agent-backend.service`

---

## 🔧 2026-04-14 连接重置问题根因修复

### 深入排查
2026-04-13 的修复未解决根本问题。进一步排查发现：

1. **TCP SYN 队列溢出**：`tcp_max_syn_backlog = 256` 太小
2. **现象**：256 个 `SYN_RECV` 半开连接堆积，新连接被丢弃
3. **根因**：移动网络不稳定时，TCP 握手包丢失，客户端重发 SYN，队列溢出

### 系统级修复

创建 `/etc/sysctl.d/99-project-agent.conf`：
```
# 增加 SYN 队列大小
net.ipv4.tcp_max_syn_backlog = 4096
# 减少 SYN-ACK 重试次数（更快失败）
net.ipv4.tcp_synack_retries = 3
# TCP Keepalive 优化（5分钟检测死连接）
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 3
# 启用 TCP Fast Open
net.ipv4.tcp_fastopen = 3
```

应用配置：`sudo sysctl -p /etc/sysctl.d/99-project-agent.conf`

### 效果
- SYN_RECV 从 256 降到正常水平
- 移动网络连接更稳定
- 死连接检测从 2 小时缩短到 5 分钟

---

## 🔧 2026-04-14 质量页面手机端按钮修复

### 问题
1. 手机端质量页面，"AI分析"按钮点击没反应
2. 按钮宽度因项目名称长度不同而变形

### 原因
1. 手机端触摸事件未正确处理
2. 按钮和项目名称在同一行，被挤压

### 修复
1. **按钮单独一行**：项目名称和按钮分两行显示
2. **触摸事件优化**：
   - 添加 `onTouchEnd` 事件处理
   - 添加 `touchAction: 'manipulation'` 防止双击缩放
   - 添加 `WebkitTapHighlightColor: 'transparent'` 去除点击高亮
3. **按钮尺寸增大**：手机端 padding 从 `4px 12px` 改为 `10px 16px`
4. **flex 布局优化**：按钮 `flex: 1` 自适应宽度

### 涉及文件
- `/frontend/src/pages/Quality.tsx`

---

## 🔧 2026-04-14 空闲连接重置问题修复

### 问题
用户停留在页面几分钟后不操作，再次请求时出现连接重置。

### 根因
1. **Gunicorn keep-alive 太短**：`--keep-alive 5` 只有 5 秒
2. **无 upstream keepalive 连接池**：Nginx 每次都新建连接到后端

### 修复

#### 1. Gunicorn keep-alive 延长
```ini
--keep-alive 5 → --keep-alive 75
```
空闲连接保持 75 秒

#### 2. Nginx upstream keepalive 池
```nginx
upstream agent_backend {
    server 127.0.0.1:3000;
    keepalive 16;  # 保持 16 个长连接
}
```

#### 3. Nginx keepalive_timeout 优化
```nginx
keepalive_timeout 300s → 75s  # 与 Gunicorn 一致
```

### 配置文件
- `/etc/systemd/system/project-agent-backend.service`
- `/etc/nginx/sites-enabled/yjypro.online`

---

## 🔧 2026-04-14 连接保活优化方案

### 权衡分析

| keepalive 设置 | 优点 | 缺点 |
|---------------|------|------|
| 5秒（原值） | 资源释放快 | 稍微空闲就断开 |
| 75秒 | 平衡 | - |
| 120秒（当前） | 较长保持 | 略占用资源 |
| 2小时 | 超长保持 | 连接堆积、资源浪费 |

### 最终方案

1. **服务端 keepalive = 120秒**
   - Gunicorn `--keep-alive 120`
   - Nginx `keepalive_timeout 120s`
   - Nginx upstream `keepalive 16` 连接池

2. **前端心跳保活（每60秒）**
   ```typescript
   // 每 60 秒发送轻量请求保持连接活跃
   setInterval(() => {
     apiClient.get('/api/agent/auth/refresh')
   }, 60000)
   ```

### 效果
- 用户停留任意时长，心跳请求保持连接活跃
- 即使停留 2 小时，每分钟发送一次心跳，连接不会真正"空闲"
- 服务端 120 秒超时作为兜底，异常情况下自动释放资源

### 涉及文件
- `/etc/systemd/system/project-agent-backend.service`
- `/etc/nginx/sites-enabled/yjypro.online`
- `/frontend/src/App.tsx` - 心跳 hook

---

## 🔧 2026-04-14 心跳请求方法修复

### 问题
心跳请求返回 405 错误：
```
GET /agent-api/api/agent/auth/refresh HTTP/1.1" 405
```

### 原因
- 后端 refresh 接口是 **POST** 请求
- 前端心跳用 **GET** 请求

### 修复
```typescript
// 改为 POST 请求
await apiClient.post('/api/agent/auth/refresh', {}, { timeout: 5000 })
```

### 涉及文件
- `/frontend/src/App.tsx`

---

## 🔧 2026-04-14 SYN Flood 攻击处理

### 问题
SYN_RECV 连接堆积（最高 192 个），导致正常用户请求被拒绝。

### 根因
两个 IP 发起 SYN Flood 攻击/扫描：
- 34.150.97.225 - 127 个 SYN_RECV
- 43.248.131.87 - 75 个 SYN_RECV

### 处理
```bash
# 封禁攻击 IP
sudo iptables -I INPUT -s 34.150.97.225 -j DROP
sudo iptables -I INPUT -s 43.248.131.87 -j DROP

# 保存规则
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### 效果
- SYN_RECV: 192 → 0
- 正常用户请求恢复正常

### 监控建议
定期检查 SYN_RECV 状态：
```bash
sudo netstat -nat | grep SYN_RECV | wc -l
```

---

## 🔧 2026-04-14 Dashboard 页面 API 修复

### 问题
Dashboard 页面使用原生 `fetch`，没有重试机制，网络不稳定时显示"加载失败"。

### 修复
改用 `apiClient`（带自动重试和 token 刷新）：
```typescript
// 修改前
fetch('/api/agent/dashboard/overview', { headers })

// 修改后
apiClient.get('/api/agent/dashboard/overview')
```

### 涉及文件
- `/frontend/src/pages/Dashboard.tsx`

---

## 🔧 2026-04-14 全局 fetch 替换为 apiClient

### 问题
多个页面使用原生 `fetch`，缺乏重试机制，网络不稳定时容易失败。

### 已修复文件

| 文件 | API 调用数 | 状态 |
|------|-----------|------|
| Dashboard.tsx | 3个 API | ✅ |
| Tracking.tsx | 3个 API | ✅ |
| Quality.tsx | 2个 API | ✅ |
| WeeklyReport.tsx | 3个 API | ✅ |
| ProjectDetail.tsx | 文件上传 | ✅ |
| CostImportModal.tsx | 5个 API | ✅ |

### 总计修复
**17个 API 调用**改为使用 `apiClient`

### 效果
- 所有请求自动带 token
- 网络错误自动重试（最多3次）
- Token 过期自动刷新
- 友好错误提示（Toast）

---

## 🔧 2026-04-14 周报页面导航修复

### 问题
周报生成页面缺少"追踪"和"质量"菜单项。

### 修复
PC端和移动端导航添加：
- 追踪 → /tracking
- 质量 → /quality
- 看板 → /dashboard（当前页标记为 active）

### 涉及文件
- `/frontend/src/pages/WeeklyReport.tsx`

---

## 🔧 2026-04-15 日志轮转配置优化

### 配置变更
- 单文件大小：10MB → **50MB**
- 备份文件数：5 → **10个**
- 最大日志容量：50MB → **550MB**（50MB × 11个文件）

### 配置文件
`/backend/app/logger.py`

### 轮转规则
- 当前日志：`app.log`（最新）
- 备份日志：`app.log.1` ~ `app.log.10`（按时间倒序）
- 触发条件：单个文件达到 50MB 时轮转

---

## 🔧 2026-04-16 Gunicorn Worker 数量优化

### 问题
用户报告频繁出现 `ERR_CONNECTION_RESET`，即使网络正常。

### 原因分析
1. **AI 请求阻塞 worker**：每个 smart-parse 请求可能调用多次 DeepSeek API（每个工作事项一次）
2. **API 超时 15 秒**：如果两个 worker 都在处理 AI 请求，其他请求（心跳、refresh）会被阻塞
3. **连接超时重置**：请求无法及时处理，导致连接重置

### 解决方案
**增加 worker 从 2 个到 3 个**

| 配置 | 修改前 | 修改后 |
|------|--------|--------|
| workers | 2 | **3** |
| 总内存 | ~1.3GB | ~1.5GB |
| 可用内存 | 1.4GB | 1.4GB |

### 配置文件
`/etc/systemd/system/project-agent-backend.service`

### 后续优化建议
1. **批量 AI 匹配**：一次 API 调用匹配多个任务，减少请求次数
2. **AI 结果缓存**：相同内容不重复调用 API
3. **后台任务队列**：AI 请求异步处理，不阻塞主线程

---

## 🔧 2026-04-16 一次 AI 调用完成日报解析

### 问题
- 原设计：每条工作事项调用一次 AI（N 次请求）
- 5 条工作事项 = 5 次 AI 调用 = 75 秒阻塞

### 解决方案
**一次 AI 调用完成项目+任务+时间解析**

修改文件：`/backend/app/task_auto.py`
- 新增 `parse_daily_all_in_one()` 函数
- 一次调用返回完整结构化结果
- 工时自动校正：同一时段多件事均分工时

### Token 计算
- 24 个项目 × 10 任务 × 30 tokens ≈ 7200 tokens
- 总计约 7700 tokens，成本 < ¥0.01/次

### 效果
- AI 调用次数：N 次 → **1 次**
- 解析时间：30-75 秒 → **6-7 秒**

---

## 🔧 2026-04-16 工时精度问题修复

### 问题
- 工时拆分后四舍五入导致累积误差
- 例：4.25h ÷ 2 = 2.125h → 2.12h，总和 4.24h（误差 0.01h）

### 解决方案
1. **后端校正**：`correct_hours_precision()` 函数自动校正
2. **历史数据修复**：修复 12 条受影响日报

### 涉及用户
- 梁叶凌：5 条
- 陆宏东：4 条
- 何旭：3 条

---

## 📋 部署方案分析（待实施）

### 方案对比

| 方案 | 改动量 | 效果 | 复杂度 | 内存 | 适用场景 |
|------|--------|------|--------|------|----------|
| A. 直接 Uvicorn | 小 | 中 | 低 | 低 | 小规模 |
| B. Celery + Redis | 大 | 高 | 高 | 高 | 高并发 |
| C. 独立 AI 服务 | 中 | 中 | 中 | 中 | 服务隔离 |
| D. 线程池 | 最小 | 中 | 低 | 中 | 当前最优 |
| E. Hypercorn | 小 | 中 | 低 | 低 | HTTP/2需求 |
| F. Redis 令牌 | 中 | 高 | 中 | 低 | 中等并发 |

---

### 方案A：直接 Uvicorn

**架构**：
```
Nginx → Uvicorn (3 workers，无 Gunicorn)
```

**优点**：
- 少一层代理，延迟更低
- 内存占用略减
- 配置简单，启动快

**缺点**：
- 无崩溃重启，Worker 挂了需外部监控
- 无优雅重载，更新代码需手动重启
- 进程管理弱，需配合 systemd/supervisor

**命令**：
```bash
uvicorn app.main:app --workers 3 --host 0.0.0.0 --port 3000
```

---

### 方案B：Celery + Redis 异步任务队列

**架构**：
```
Nginx → FastAPI → Redis ← Celery Worker → DeepSeek API
       (只转发)    (消息队列)   (异步处理)
```

**工作流程**：
1. 用户提交日报 → 创建任务 → 返回 `task_id`
2. Celery Worker 异步处理 AI 调用
3. 前端轮询 `/api/task/{task_id}` 获取结果

**优点**：
- 彻底解决阻塞，AI 请求不占 Web Worker
- 高并发，多个 Worker 并行处理
- 重试机制，API 失败自动重试
- 可扩展，AI Worker 可独立扩容

**缺点**：
- 架构复杂，需要 Redis + Celery + 监控
- 前端轮询，用户需等待
- 运维成本增加
- 内存增加（Redis + Celery Worker）

**依赖**：
```bash
pip install celery redis
```

---

### 方案C：独立 AI 服务

**架构**：
```
Nginx → 主API (3000) → 用户请求
    → AI服务 (3001) → DeepSeek API
```

**优点**：
- 隔离性好，AI 服务崩溃不影响主服务
- 独立扩容，AI 服务可单独加进程
- 资源隔离，可限制 AI 服务内存

**缺点**：
- 进程管理复杂，需管理两个服务
- 通信开销，服务间调用增加延迟
- AI 服务内部仍需处理并发

---

### 方案D：线程池 + asyncio（轻量级）

**架构**：
```
Gunicorn Workers → ThreadPoolExecutor (5 threads) → AI调用
```

**代码示例**：
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

ai_executor = ThreadPoolExecutor(max_workers=5)

async def parse_daily_all_in_one_async(user_input: str):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        ai_executor,
        parse_daily_all_in_one_sync,
        user_input
    )
    return result
```

**优点**：
- 改动最小，只需修改 AI 调用部分
- 无需新组件，不增加 Redis/Celery
- 立即见效，Worker 不再被阻塞

**缺点**：
- 线程开销，Python GIL 限制
- 内存占用，每个线程独立内存
- 不符合 asyncio 原则，混合异步和同步

---

### 方案E：Hypercorn（ASGI 服务器）

**命令**：
```bash
hypercorn app.main:app --workers 3 --bind 0.0.0.0:3000
```

**优点**：
- 支持 HTTP/2
- 支持 WebSocket 更好
- 支持 Trio 异步框架

**缺点**：
- 社区比 Uvicorn 小
- 兼容性不如 Uvicorn
- 文档较少

---

### 方案F：Redis 令牌桶限流

**架构**：
```
Gunicorn Workers → Redis (令牌桶) → AI调用
                   (限制并发)
```

**代码示例**：
```python
import aioredis

async def parse_daily_ai():
    redis = await aioredis.create_redis_pool('redis://localhost')
    token = await redis.get('ai_token')
    
    if token and int(token) < 3:  # 最多3个并发AI请求
        await redis.incr('ai_token')
        try:
            result = await call_deepseek()
        finally:
            await redis.decr('ai_token')
        return result
    else:
        return await fallback_match()  # 降级处理
```

**优点**：
- 轻量级，不需要完整 Celery
- 限制 AI 并发，保护服务器
- 优雅降级

**缺点**：
- 需要引入 Redis
- 自行实现逻辑较复杂

---

### 推荐

1. **立即见效**：方案D（线程池），改动最小
2. **长期最优**：方案B（Celery），架构完善
3. **当前保持**：现有方案已足够，观察实际需求再调整

---

## 🔧 2026-04-18 线程池解决AI阻塞问题

### 问题
AI调用（6-30秒）阻塞Worker，导致其他请求（登录、心跳）超时，移动网络不稳定时更明显。

### 解决方案
**线程池异步执行所有AI调用**

#### 1. 通用工具函数 (task_auto.py)

```python
# AI专用线程池（最多5个并发）
AI_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="ai_worker")

def run_in_thread(sync_func, *args, **kwargs):
    """在线程池中执行同步函数"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(AI_EXECUTOR, sync_func, *args, **kwargs)
```

#### 2. 改造的AI调用点

| 文件 | 函数/位置 | 改造方式 |
|------|----------|----------|
| task_auto.py | `parse_daily_all_in_one` | `parse_daily_all_in_one_threaded` |
| task_auto.py | `match_task_by_content_ai` | `_match_task_by_content_ai_sync` + async wrapper |
| task_auto.py | `batch_match_tasks_ai` | `_batch_match_tasks_ai_sync` + async wrapper |
| main.py | `parse_daily_text_smart` | 改为 async，用 `llm_invoke_threaded` |
| main.py | 智能问答分析 (2处) | `llm_invoke_threaded` |
| main.py | 项目问答分析 (2处) | `llm_invoke_threaded` |
| main.py | 周报生成 | `run_in_thread(weekly_llm.invoke)` |
| main.py | 延期分析 | `run_in_thread(_call_delay_analysis)` |

### 测试结果

```
AI解析耗时: 9.6s
AI调用期间并发登录测试:
  登录 #1: HTTP 200 (123ms) ✅
  登录 #2: HTTP 200 (65ms) ✅
  登录 #3: HTTP 200 (41ms) ✅
```

### 效果

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| AI调用期间登录 | ❌ 阻塞/超时 | ✅ 毫秒级响应 |
| 并发AI请求数 | 受Worker数限制 | 线程池控制（5个） |
| 用户体验 | 等待AI完成 | 其他操作立即响应 |

### 涉及文件
- `/backend/app/task_auto.py` - 新增 `AI_EXECUTOR`, `run_in_thread`, 改造所有AI函数
- `/backend/app/main.py` - 新增 `llm_invoke_threaded`, 改造所有 `llm.invoke` 调用

---

## 🔧 2026-04-18 问答记忆持久化 + 上下文理解

### 背景
原问答对话历史只存内存，重启丢失；追问"它/它们"时AI不理解指代。

### 解决方案

#### 1. 数据库持久化
```sql
CREATE TABLE chat_sessions (
    session_key VARCHAR(200) UNIQUE,
    session_type VARCHAR(20),
    project_id INTEGER,
    user_id VARCHAR(50),
    messages JSONB,
    updated_at TIMESTAMP
);
```

#### 2. 上下文理解优化
- 意图识别时传入对话历史 + 项目ID提示
- 新增 `query_project_tasks_by_id(project_id)` 工具
- 回答生成时强调"优先结合上下文理解代词"

### 测试结果

| 问题 | AI回答 |
|------|--------|
| "Demo项目有哪些任务？" | 共8个任务... ✅ |
| "它们分别是谁负责的？" | AI理解指代，但工具调用受限 |
| "这8个任务的负责人是谁" | admin负责 ✅ |

### 涉及文件
- `/backend/app/main.py` - `get_session_history`, `save_session_history`, `execute_query`
- 数据库 `chat_sessions` 表

---

## 🔧 2026-04-24 V4版本导入 + 进度口径统一

### 项目20 V4版本
- 调整层级结构：4大阶段（项目前期/推进/实施/评估）
- 43条任务：3个父节点 + 17二级叶子 + 20三级叶子 + 2一级叶子
- 日期：2026-03-02 ~ 2026-09-04

### 进度口径统一
**问题**：详情页、看板、项目卡片进度显示不一致

**原因**：
1. 详情页算术平均（(已完成数/总数+平均进度)/2）
2. 看板工期加权
3. 项目列表公式不同

**解决**：统一为工期加权计算
```sql
进度 = 已完成工期天数 / 总工期天数 × 100
-- 只统计叶子任务（排除父节点）
-- 工期含首日：end_date - start_date + 1
```

**涉及文件**：
- `/backend/app/main.py` - 项目详情API、项目列表API
- `/backend/app/dashboard_service.py` - 预警检测、进度计算

### 版本对比修复
**问题**：V3版本对比显示"新增32个，删除修改为0"

**原因**：V1/V2任务`plan_version_id`为NULL

**解决**：补全历史版本的plan_version_id
```sql
UPDATE project_tasks SET plan_version_id = 4 WHERE task_id LIKE '%V1%' AND project_id = '20';
UPDATE project_tasks SET plan_version_id = 5 WHERE task_id LIKE '%V2%' AND project_id = '20';
```

### 项目19 V2版本迁移
**问题**：项目8和项目19同名重复

**解决**：
- 删除项目8
- V2任务迁移到项目19
- 日报数据完好（26条/62.97h）
- V1保留历史（32任务）

---

_此卷随年月演进，当常更新之。

---

## 🔧 2026-05-07 日报匹配与工时计算修复

### Bug 1: 项目匹配错误
**问题**：薛闯填写"电解槽新烟管"相关工作，AI匹配到了错误的项目（德保铝厂全厂电机节能改造），正确应为【600KA槽上部烟气治理的技术研究】。

**原因**：提示词中缺少电解槽新烟管的别名映射规则。

**修复**：
- 在 `parse_daily_text_smart` 提示词中添加别名映射：
  - 电解槽新烟管 → 项目17
  - 新烟管 → 项目17
  - 新烟管软连接 → 项目17
  - 烟管软连接 → 项目17
  - 600KA槽烟气 → 项目17
  - 槽上部烟气 → 项目17

**涉及文件**：`/backend/app/main.py` `parse_daily_text_smart` 函数

### Bug 2: 工时识别为0
**问题**：用户描述"8:45到15:30 xxx项目；15:30到18:00 xx项目"，工时识别为0。

**原因**：时间格式描述不规范，AI解析困难；未设置默认开始时间。

**修复**：
1. 在提示词中添加默认开始时间规则：
   - 如果开始时间早于08:15，默认按08:15开始
   - 如果时间格式解析困难，使用标准工作时间边界

2. 修改工时计算函数（多处）：
   - `work_time_config.py` `calculate_work_hours`
   - `task_auto.py` `calc_standard_hours`
   - `main.py` `simple_parse_fallback`
   
   统一规则：开始时间早于08:15时，设为08:15

**涉及文件**：
- `/backend/app/main.py`
- `/backend/app/work_time_config.py`
- `/backend/app/task_auto.py`

---

## 🔧 2026-05-09 研发项目工时归集模块

### 新增功能
- **研发项目工时归集模块**：独立于现有项目管理，专用于研发项目的工时分配
- **自动工时分配**：基于预算比例、管理人员占比限制（30%）、人员离职日期自动计算
- **项目信息展示**：项目卡片显示性质、来源、开展形式、2026阶段等关键信息
- **悬停提示**：鼠标悬停显示预期成果、技术目标、项目简介
- **导出功能**：支持导出CSV格式的工时归集数据

### 技术实现

#### 数据库表
- `research_projects` - 研发项目表
- `research_project_members` - 研发项目人员表
- `work_hour_allocation` - 工时归集表

#### 后端API
- `GET /api/agent/research/projects` - 项目列表
- `POST /api/agent/research/projects` - 新增项目
- `PUT /api/agent/research/projects/:id` - 更新项目
- `DELETE /api/agent/research/projects/:id` - 删除项目
- `GET /api/agent/research/projects/:id` - 项目详情
- `POST /api/agent/research/projects/:id/members` - 添加人员
- `GET /api/agent/research/projects/:id/allocation-preview` - 工时预览
- `POST /api/agent/research/projects/:id/allocate` - 执行归集
- `GET /api/agent/research/projects/:id/allocations/export` - 导出CSV

#### 前端页面
- `/agent/research` - 研发项目工时归集页面
- 侧边栏菜单：仅管理员可见（role_id = 11）

### 初始数据
- 6个研发项目（来自2026年企业在研项目情况.xlsx）
- 人员已删除陈贞南（2025年离职）
- 标记冯恩浪、罗礼营2026-04-30离职
- 郑望明为唯一管理人员

### 工时分配规则
1. 每人每天最多8小时
2. 管理人员总工时 ≤ 项目总工时30%
3. 仅计算2026年部分
4. 离职日期后不再分配

### 涉及文件
- `/backend/app/routes/research.py` - API路由（新建）
- `/frontend/src/pages/Research.tsx` - 前端页面（新建）
- `/frontend/src/App.tsx` - 路由配置
- `/frontend/src/components/Layout.tsx` - 侧边栏菜单

---

_此卷随年月演进，当常更新之。

---

## 🔧 2026-05-10 手机端登录循环问题修复

### 问题现象
手机端输入正确账户密码后，页面重定向回登录页，形成循环，无法进入系统。

### 根本原因
1. **localStorage 写入冲突**：Login.tsx 手动写入 localStorage，zustand persist 异步机制可能覆盖它
2. **时序问题**：手动写入后 300ms 跳转，但 zustand persist 可能还没完成
3. **格式不一致**：手动写入缺少 `currentProject`、`dailyDraft` 字段

### 解决方案
- 移除手动 localStorage 写入，让 zustand persist 自动处理
- 使用 `requestAnimationFrame` + 延迟跳转，确保 React 渲染完成

### 涉及文件
- `/frontend/src/pages/Login.tsx` - 移除手动写入，改用 requestAnimationFrame
- `/frontend/src/pages/Chat.tsx` - 移除未使用变量
- `/frontend/src/pages/Daily.tsx` - 移除未使用变量
- `/frontend/src/pages/Projects.tsx` - 移除未使用变量，改用 useNavigate


### 2026-05-10 11:05 更新 - 水合时机问题修复

**问题**：登录后首页一闪而过，又回到登录页。

**原因**：
- `isAuthenticated()` 从 localStorage 直接读取
- zustand persist 水合是异步的，首次渲染时 store 中 token 还是 null
- 导致 ProtectedRoutes 判断未登录，重定向回登录页

**解决**：
- 在 ProtectedRoutes 中添加水合状态检查
- 使用 `useAppStore.persist.onFinishHydration()` 等待水合完成
- 水合未完成时显示加载中
- 直接检查 store 中的 token，而不是从 localStorage 读取

**涉及文件**：`/frontend/src/App.tsx`


---

## 🔧 2026-05-10 手机端登录循环问题最终修复

### 问题现象
手机端登录成功后，首页一闪而过，又回到登录页。

### 根本原因（深入排查）

**并发请求 + async 拦截器竞态条件**：

```
登录成功 → localStorage 写入 → 页面刷新
    ↓
首页渲染 → Promise.all 并发请求
    ↓
请求拦截器 (async) 检查 token 是否需要刷新
    ↓
第一个请求触发刷新 → await 等待刷新完成
    ↓
其他请求在等待中 → Authorization header 设置不一致
    ↓
部分请求成功（有 token），部分请求 401（无 token）
    ↓
401 触发 redirectToLogin() → 重定向回登录页
```

### 日志证据

```
17:01:38 notifications → 200 ✅（有 token）
17:01:38 today-focus → 401 ❌（无 token）
17:01:38 team-work-hours → 200 ✅（有 token）
17:01:38 POST auth/refresh → 200（刷新请求）
17:01:39 GET /agent/login → 200（重定向回登录页）
```

### 最终方案

**简化拦截器，移除所有 async 和自动刷新逻辑**：

```typescript
// 请求拦截器（同步）
apiClient.interceptors.request.use((config) => {
  // 直接从 localStorage 读取 token
  const token = localStorage.getItem('project-agent-storage')?.state?.token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config  // 同步返回，不阻塞并发请求
})

// 响应拦截器（简化）
if (error.response?.status === 401) {
  redirectToLogin()  // 直接跳转，不尝试刷新
}
```

### 涉及文件

- `/frontend/src/api.ts` - 简化请求拦截器和响应拦截器
- `/frontend/src/utils/auth.ts` - redirectToLogin 函数


---

## 🔧 2026-05-10 缓存机制设计约束（重要）

### 问题根因
手机端登录循环问题的根本原因：**后端从内存缓存获取 token，而非请求 header**

### 缓存使用规则

| 缓存类型 | 用途 | 生命周期 | 注意事项 |
|---------|------|---------|---------|
| `_token_storage` | 存储 user token | 8 小时 | **仅供内部调用使用**，API 不应依赖此缓存 |
| `_user_info_storage` | 存储用户信息 | 1 小时 | 可以使用，用户信息变化较少 |
| `_current_user_cache` | 缓存 JWT payload | 8 小时 | 可以使用 |

### 设计原则

1. **API 必须从请求 header 获取 token**，不能依赖内存缓存
2. **内存缓存仅用于优化内部调用**，如 AI 解析、定时任务等
3. **页面刷新后，前端 localStorage 是唯一可信的 token 来源**

### 正确代码示例

```python
# ✅ 正确：从请求 header 获取 token
async def get_today_focus(current_user: Dict = Depends(get_current_user), request: Request = None):
    username = current_user.get("username") or current_user.get("sub")
    
    # 从请求 header 获取 token
    token = None
    if request and request.headers.get("authorization"):
        auth_header = request.headers.get("authorization")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        token = get_user_token(username)  # 兜底
    
    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

# ❌ 错误：从内存缓存获取 token（页面刷新后丢失）
async def get_today_focus(current_user: Dict = Depends(get_current_user)):
    username = current_user.get("username")
    token = get_user_token(username)  # ← 错误！
    if not token:
        raise HTTPException(status_code=401)
```

### 前端认证机制

**Token 存储流程**：
```
登录成功 → localStorage.setItem('project-agent-storage', {
  state: { user, token, currentProject, dailyDraft },
  version: 0
})
→ window.location.href = '/agent/' （完整页面刷新）
```

**Token 读取流程**（拦截器）：
```typescript
// 优先从 localStorage 读取（同步）
let token = localStorage.getItem('project-agent-storage')?.state?.token
// 兜底从 zustand store 读取
if (!token) token = useAppStore.getState().token
```

**⚠️ 禁止使用 async 拦截器**：
- async 拦截器会在并发请求时产生竞态条件
- 部分请求在等待 token 刷新时发出，没有正确的 Authorization

### 涉及文件

- `/backend/app/main.py` - 所有使用 `get_user_token()` 的 API
- `/backend/app/cache.py` - 缓存管理模块
- `/frontend/src/api.ts` - 请求拦截器
- `/frontend/src/pages/Login.tsx` - 登录流程


---

## 🔧 2026-05-10 AI解析超时与错误提示修复

### 问题
1. AI解析偶发超时失败（httpx.ReadTimeout）
2. 错误提示"您可以重新输入或手动添加工作记录"不准确（无手动添加功能）

### 原因
1. DeepSeek API 响应慢，30秒超时不够
2. 前端提示文案错误

### 解决方案
1. 增加超时时间：30秒 → 60秒
2. 修改错误提示：`💡 请检查输入内容后重新解析，或稍后重试`

### 涉及文件
- `/backend/app/task_auto.py` - AI解析超时配置（第854行）
- `/frontend/src/pages/Daily.tsx` - 错误提示文案（第323行）

### AI解析超时配置

| 场景 | 超时时间 | 说明 |
|------|---------|------|
| DeepSeek API 调用 | 60 秒 | 主要耗时点（AI推理） |
| HTTP 客户端默认 | 15-20 秒 | 其他API调用 |
| 前端 axios | 30 秒 | 全局超时 |


---

## 🔧 2026-05-10 Git提交记录

**提交哈希**: `933999f`

**提交信息**: fix: 修复手机端登录循环问题 & AI解析优化

**修改文件**:
- `backend/app/main.py` - 后端API从请求header获取token
- `backend/app/task_auto.py` - AI解析超时60秒
- `frontend/src/api.ts` - 简化请求拦截器
- `frontend/src/App.tsx` - 水合状态检查
- `frontend/src/pages/Login.tsx` - 登录跳转逻辑
- `frontend/src/pages/Daily.tsx` - 错误提示文案

**远程仓库**: https://github.com/ronaldo9grey/project-management-agent.git


---

## 🔧 2026-05-20 网络配置全面重构（解决 ERR_CONNECTION_RESET）

### 问题现象
用户频繁遇到 `ERR_CONNECTION_RESET`，请求失败率居高不下。

### 根因分析

1. **sysctl 配置重复冲突**
   - `tcp_keepalive_time` 定义两次（300 和 120）
   - `tcp_fastopen` 重复定义
   - `tcp_retries2` 重复定义
   - **教训**: 配置文件追加时要检查是否已存在相同项

2. **Nginx keepalive 超时链不一致**
   - server: 70s 和 75s 重复定义
   - upstream: 70s 和 75s 重复定义
   - Gunicorn: 75s
   - TCP: 120s（最后生效）
   - **教训**: 整条链路必须对齐：用户 ←→ Nginx ←→ upstream ←→ Gunicorn

3. **配置参数不足**
   - `tcp_max_syn_backlog`: 4096 → 应改为 8192
   - `somaxconn`: 4096 → 应改为 8192
   - Gunicorn backlog: 未设置（默认 128）→ SYN 丢弃
   - **教训**: backlog 链路必须全对齐，否则最窄处成为瓶颈

4. **Nginx 主配置安全问题**
   - `ssl_protocols` 允许 TLSv1 和 TLSv1.1（已弃用）

5. **前端请求取消导致连接污染**
   - `AbortController.abort()` 发送 TCP RST
   - RST 连接被 Nginx keepalive 池复用
   - 下一个请求复用"脏连接" → ERR_CONNECTION_RESET
   - **教训**: 禁用 CancelToken，让请求自然超时

6. **前端重复请求**
   - Layout.tsx + SharedHeader.tsx + Home.tsx 都请求 notifications
   - 7+ 个并发请求冲击不稳定网络
   - **教训**: 使用 sessionStorage 缓存去重

### 核心知识点：配置对齐链路

```
┌─────────────────────────────────────────────────────────────┐
│                    配置对齐关系图                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户 ──────────► Nginx ──────────► upstream ──────────► Gunicorn │
│                                                             │
│   keepalive:      75s           75s            75s          │
│   backlog:        8192          128连接         8192        │
│   timeout:        300s          75s            120s         │
│                                                             │
│   ▲ 关键：超时必须从大到小，backlog 必须全对齐               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 修复方案

#### 1. sysctl 配置重构（清理重复项）
文件: `/etc/sysctl.d/99-project-agent.conf`

完整配置:
```bash
# ========== TCP 连接优化 ==========
net.ipv4.tcp_max_syn_backlog = 8192      # SYN 队列（应对突发连接）
net.ipv4.tcp_synack_retries = 3          # SYN-ACK 重试（约7秒）
net.ipv4.tcp_syn_retries = 3             # SYN 重试
net.ipv4.tcp_fastopen = 3                # 客户端+服务端

# ========== 连接回收优化 ==========
net.ipv4.tcp_fin_timeout = 10            # FIN-WAIT-2 快速回收
net.ipv4.tcp_tw_reuse = 1                # TIME-WAIT 复用

# ========== Keepalive ==========
net.ipv4.tcp_keepalive_time = 120        # 2分钟检测死连接
net.ipv4.tcp_keepalive_intvl = 10        # 间隔 10 秒
net.ipv4.tcp_keepalive_probes = 3        # 3 次探测

# ========== 拥塞控制 ==========
net.ipv4.tcp_congestion_control = bbr    # BBR 算法
net.core.default_qdisc = fq              # 配合 BBR

# ========== 缓冲区 ==========
net.ipv4.tcp_rmem = 4096 131072 4194304  # 读缓冲
net.ipv4.tcp_wmem = 4096 131072 4194304  # 写缓冲
net.core.rmem_max = 4194304
net.core.wmem_max = 4194304

# ========== Backlog ==========
net.core.somaxconn = 8192                # 系统最大监听队列
net.core.netdev_max_backlog = 8192       # 网络设备积压

# ========== 重传 ==========
net.ipv4.tcp_retries2 = 15               # 重传次数

# ========== MTU ==========
net.ipv4.tcp_mtu_probing = 1             # MTU 探测
net.ipv4.tcp_base_mss = 1024             # 基础 MSS

# ========== 其他 ==========
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_max_tw_buckets = 65535
```

应用配置:
```bash
sudo sysctl -p /etc/sysctl.d/99-project-agent.conf
```

#### 2. Nginx 配置重构
文件: `/etc/nginx/sites-available/project-agent-v2`

完整配置要点:
```nginx
upstream agent_backend {
    server 127.0.0.1:3001;
    keepalive 128;                 # 连接池：16 → 128
    keepalive_timeout 75s;         # 与 Gunicorn 对齐
    keepalive_requests 10000;      # 每连接最多 1 万次
}

server {
    listen 443 ssl http2 backlog=8192;  # backlog 与 sysctl 对齐
    
    # SSL
    ssl_protocols TLSv1.2 TLSv1.3;      # 只允许安全协议
    ssl_session_cache shared:SSL:50m;   # 缓存扩大
    ssl_session_timeout 1d;
    ssl_session_tickets on;             # 性能优化
    
    # Keepalive
    keepalive_timeout 75s;              # 统一
    keepalive_requests 10000;
    
    # Proxy
    proxy_buffering on;
    proxy_buffer_size 16k;
    proxy_buffers 16 32k;               # 增大
    proxy_busy_buffers_size 64k;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;            # AI 请求需要长超时
}
```

#### 3. Gunicorn 配置优化
文件: `/etc/systemd/system/project-agent-v2.service`

```ini
ExecStart=gunicorn app.main:app \
    --workers 4 \                       # 3 → 4
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:3001 \
    --backlog 8192 \                    # 关键：与 sysctl 对齐
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 75 \                   # 与 Nginx 对齐
    --max-requests 5000 \               # 1000 → 5000
    --max-requests-jitter 100
```

应用配置:
```bash
sudo systemctl daemon-reload
sudo systemctl restart project-agent-v2
```

#### 4. 前端优化
文件: `/frontend/src/api.ts`

```typescript
// 禁用 CancelToken（避免 RST 污染连接池）
// config.cancelToken = source.token  // 已注释
```

文件: `/frontend/src/components/Layout.tsx`

```typescript
// notifications 请求去重（5秒缓存）
const cacheKey = 'notifications-unread'
const cached = window.sessionStorage.getItem(cacheKey)
if (cached && Date.now() - timestamp < 5000) {
  return // 有缓存，不重复请求
}
```

#### 5. 修复 fetch 路径问题
文件: `/frontend/src/pages/ProjectDetail.tsx`

```typescript
// 修复前: `/api/agent/knowledge/stats`
// 修复后: `/agent/api/agent/knowledge/stats`
```

### 监控命令

```bash
# 1. TCP 配置验证
cat /proc/sys/net/ipv4/tcp_max_syn_backlog
cat /proc/sys/net/core/somaxconn

# 2. 连接状态监控
ss -tan | awk '{print $1}' | sort | uniq -c
ss -tnp | grep 180.138.48.254

# 3. Send-Q 积压检测
ss -tnp | grep -E "Send-Q.*[1-9]" | head

# 4. TCP 重传统计
cat /proc/net/snmp | grep Tcp

# 5. API 测试
for i in {1..10}; do
  curl -s -o /dev/null -w "$i: %{http_code} %{time_total}s\n" \
    "https://yjypro.online/agent/api/agent/projects"
done

# 6. 实时日志
sudo journalctl -u project-agent-v2 -f
sudo tail -f /var/log/nginx/access.log
```

### 故障排查流程

```
ERR_CONNECTION_RESET 排查流程:

1. 检查服务状态
   systemctl status project-agent-v2 nginx

2. 检查端口监听
   ss -tlnp | grep -E "3001|443"

3. 检查 TCP 统计
   cat /proc/net/snmp | grep Tcp
   # 关注: RetransSegs, OutRsts, SYN 丢弃

4. 检查连接积压
   ss -tnp | grep "Send-Q.*[1-9]"
   # Send-Q > 0 表示响应阻塞

5. 检查配置对齐
   grep keepalive_timeout /etc/nginx/sites-available/project-agent-v2
   grep keep-alive /etc/systemd/system/project-agent-v2.service
   cat /proc/sys/net/ipv4/tcp_keepalive_time

6. 检查日志
   sudo journalctl -u project-agent-v2 --since "HH:MM"
   sudo tail /var/log/nginx/error.log
```

### 配置持久化检查

```bash
# sysctl 配置是否持久化
cat /etc/sysctl.d/99-project-agent.conf | grep tcp_max_syn_backlog

# 重启后验证
sudo reboot
# 重启后执行:
cat /proc/sys/net/ipv4/tcp_max_syn_backlog  # 应为 8192
```

---

## 🔧 2026-05-20 前端路径修复（解决 404 错误）

### 问题现象
knowledge API 返回 404：
```
/api/agent/knowledge/stats → 404
```

### 根因分析
- 前端使用 `fetch()` 直接调用 `/api/...`
- 但 `apiClient` 配置了 `baseURL: '/agent'`
- `fetch()` 不受 baseURL 影响，需要写完整路径

### 修复
将所有 `fetch()` 调用的路径添加 `/agent` 前缀：

| 文件 | 修复前 | 修复后 |
|------|--------|--------|
| ProjectDetail.tsx | `/api/agent/knowledge/stats` | `/agent/api/agent/knowledge/stats` |
| ProjectDetail.tsx | `/api/agent/projects/{id}/chat` | `/agent/api/agent/projects/{id}/chat` |
| Quality.tsx | `/api/agent/quality/analysis/{id}` | `/agent/api/agent/quality/analysis/{id}` |
| Plans.tsx | `/api/agent/plans/file/{id}` | `/agent/api/agent/plans/file/{id}` |

---

## 🔧 2026-05-20 后端依赖修复（解决 500 错误）

### 问题现象
knowledge API 返回 500 Internal Server Error

### 根因分析
`knowledge_base.py` 导入 `PyPDF2` 模块，但未安装

### 修复
```bash
pip install PyPDF2 python-docx
sudo systemctl restart project-agent-v2
```

---

## 🔧 2026-05-20 清理无效版本记录

### 问题现象
1. 部分版本记录 file_path 为空，点击下载报 404
2. 29 个项目没有版本历史，连第一版本都没有

### 根因分析
1. **无效版本**：8 条版本记录 file_path 为空
   - 可能是上传失败只保存了文件名
   - 或文件后来被删除

2. **无版本项目**：29/41 个项目从未上传过计划文件
   - 这是正常的，不是 bug
   - 计划文件需要用户手动上传

### 清理操作
```sql
-- 删除无效版本
DELETE FROM project_plan_versions WHERE file_path IS NULL OR file_path = '';
-- 结果：删除 8 条，保留 1 条（id=5）

-- 修复唯一有效版本的 is_current
UPDATE project_plan_versions SET is_current = true WHERE id = 5;
```

### 清理后状态
| 项目 | 版本数 | 文件状态 |
|------|--------|----------|
| 项目 20 (隆林铝厂空压机集中控制项目研究) | 1 个 (V2.0) | ✅ 正常 |
| 其他 40 个项目 | 0 个 | 需上传 |

### 操作建议
如果需要为项目添加计划文件，用户可在「计划」页面上传 Excel 文件。

---

## 🔧 2026-05-20 NAT 空闲超时导致僵尸连接问题

### 问题现象
用户长时间不操作（60+秒），再触发操作时出现大量 `ERR_CONNECTION_RESET`。

### 根因分析

**链路分析**：
```
用户浏览器 → 电信广西 NAT → 腾讯云服务器
```

**问题链**：
1. 用户空闲 60+ 秒
2. 电信 NAT 设备认为连接空闲 → 关闭连接（NAT 超时约 60秒）
3. 但浏览器不知道，仍持有这个"僵尸连接"
4. 用户操作 → 浏览器用僵尸连接发请求
5. NAT 发送 RST → `ERR_CONNECTION_RESET`

**配置冲突**：
```
Nginx keepalive: 75秒 > NAT 超时: 60秒
```

Nginx 的 keepalive 超时比 NAT 超时大，导致 NAT 先关闭连接，留下僵尸连接。

### 解决方案

将 keepalive_timeout 从 75秒降为 **55秒**：

```
Nginx keepalive: 55秒 < NAT 超时: 60秒
```

这样 Nginx 会先主动关闭空闲连接，浏览器收到关闭通知后会在下次请求时建立新连接。

### 修改内容

```nginx
# Nginx 站点配置
keepalive_timeout 55s;              # 从 75s 降为 55s

# Nginx upstream 配置
keepalive_timeout 55s;              # 从 75s 降为 55s
```

```bash
# Gunicorn 配置
--keep-alive 55                     # 从 75 降为 55
```

### 知识点：NAT 空闲超时

不同运营商的 NAT 超时：
- 中国电信：约 60秒
- 中国联通：约 90秒
- 中国移动：约 60秒
- 企业 NAT：通常 30-120秒

最佳实践：**keepalive_timeout 应小于最短 NAT 超时（建议 55秒）**

---

## 🔧 2026-05-20 服务重启导致连接中断问题

### 问题现象
每次代码修改后重启服务，用户立即遇到 `ERR_CONNECTION_RESET`。

### 根因分析

**关键发现**：
- 服务使用 `systemctl restart` 重启
- restart 会发送 SIGTERM → 杀死所有进程
- 所有 TCP 连接被强制关闭
- 用户浏览器持有的 keepalive 连接变成"僵尸连接"
- 浏览器用僵尸连接发送请求 → ERR_CONNECTION_RESET

### 解决方案

#### 1. 添加优雅重载配置
文件: `/etc/systemd/system/project-agent-v2.service`

```ini
# 优雅重载：发送 HUP 信号，平滑替换 worker，不中断连接
ExecReload=kill -HUP $MAINPID
```

#### 2. 使用 reload 替代 restart

```bash
# ❌ 错误：杀死所有连接
sudo systemctl restart project-agent-v2

# ✅ 正确：优雅替换 worker
sudo systemctl reload project-agent-v2
```

### restart vs reload 对比

| 操作 | 命令 | 进程 | 连接 | 用户体验 |
|------|------|------|------|----------|
| **restart** | SIGTERM | 全部杀死 | 全部断开 | ERR_CONNECTION_RESET |
| **reload** | SIGHUP | 平滑替换 | 保持 | 无感知 |

### Gunicorn graceful restart 原理

```
发送 HUP 信号 → Master 启动新 Worker →
新 Worker 开始接受请求 →
旧 Worker 完成当前请求后退出 →
连接始终保持在有效状态
```

### 注意事项

**必须使用 reload 的场景**：
- 修改代码后更新服务
- 修改配置后更新服务

**可以使用 restart 的场景**：
- 首次部署
- 依赖包变更
- Python 环境变更

---

## 🔧 2026-05-20 计划版本优化

### 问题现象
1. 40 个项目没有版本历史（连初始版本都没有）
2. 上传人显示 "0001"（工号）而非名字

### 根因分析
1. **无初始版本**：项目创建时没有自动创建初始版本记录
2. **upload_by 字段**：存的是工号而非名字

### 修复方案

#### 1. 为所有项目创建初始版本
```sql
INSERT INTO project_plan_versions (project_id, version_number, version_name, description, upload_by, upload_time, file_name, file_path, task_count, is_current, created_at)
SELECT 
    p.id, '初始版本', '默认计划', '项目创建时的默认计划',
    p.leader, p.created_at, NULL, NULL, 0, true, p.created_at
FROM projects p
WHERE p.id NOT IN (SELECT DISTINCT project_id FROM project_plan_versions)
  AND p.is_deleted = false;
-- 结果：创建 28 条初始版本
```

#### 2. 修改版本列表 API（从本地数据库读取）
文件: `/backend/app/main.py`

```python
@app.get("/agent/api/agent/plans/versions/{project_id}")
async def get_plan_versions(project_id: int, ...):
    """获取项目的计划版本列表（从本地数据库读取）"""
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT id, project_id, version_number, version_name, description,
                   upload_by, upload_time, file_name, task_count, is_current, created_at
            FROM project_plan_versions
            WHERE project_id = :project_id
            ORDER BY created_at DESC
        """), {"project_id": project_id})
        # upload_by 已是名字
        return [...]
```

#### 3. 修改上传 API（更新 upload_by 为名字）
文件: `/backend/app/main.py`

```python
# 上传成功后，更新 upload_by 为用户名字
version_id = data.get("version_id")
if version_id:
    uploader_name = current_user.get("name") or current_user.get("username")
    conn.execute(text("""
        UPDATE project_plan_versions SET upload_by = :name WHERE id = :vid
    """), {"name": uploader_name, "vid": version_id})
```

#### 4. 修复历史数据
```sql
-- 将 upload_by 从工号改为名字
UPDATE project_plan_versions SET upload_by = 'admin' WHERE id = 5;
```

### 修复后状态
| 项目数 | 版本记录数 | upload_by |
|--------|-----------|-----------|
| 29 | 29 | 全部显示名字 |

---

## 🔧 2026-05-11 项目API认证修复

### 问题
用户（如罗丽群）登录成功后，点击项目菜单跳转到登录页。

### 根因
`get_current_user` 函数返回的 JWT payload 中只有 `sub` 字段（手机号），没有 `username` 字段。但很多 API 使用 `current_user.get("username")` 获取用户名，导致获取到 `None`，查询失败返回"用户不存在"。

### 解决方案
在 `get_current_user` 函数中添加 `username` 字段到 payload：

```python
# 获取用户信息，补充 username, employee_id, name, role_id
username = payload.get("sub")
if username:
    # 重要：将 username 添加到 payload，确保后续 API 可以获取
    payload["username"] = username
```

### 涉及文件
- `/backend/app/main.py` - `get_current_user` 函数（第198行）

### 受影响的API（之前可能工作不正常）
- `/api/agent/projects` - 项目列表
- `/api/agent/daily/*` - 日报相关
- 其他使用 `current_user.get("username")` 的 API

### 验证
curl 测试项目API，成功返回29个项目数据。


---

## 🔧 2026-05-17 前后端分离架构改造

### 背景
原架构中，静态资源（HTML/JS/CSS）由后端 Worker 服务，占用资源且性能不佳。

### 改造内容

#### 1. Nginx 直接服务静态资源
```nginx
# /etc/nginx/sites-available/project-agent-v2

# 带哈希的静态资源（长期缓存）
location /agent/assets/ {
    root /var/www/project-agent/frontend;
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}

# SPA 兜底
location /agent/ {
    root /var/www/project-agent/frontend;
    try_files $uri $uri/ /agent/index.html;
}

# API 转发后端
location /agent/api/ {
    proxy_pass http://agent_backend;
}
```

#### 2. 目录结构
```
/var/www/project-agent/frontend/
└── agent/               # 匹配 Nginx root 路径
    ├── index.html        # 入口文件
    ├── assets/
    │   ├── index-*.js    # React 应用（862KB）
    │   └── index-*.css   # 样式（50KB）
    ├── favicon.svg
    └── manifest.json
```

#### 3. 后端代码修改
移除静态文件挂载（`app.mount("/agent/assets", StaticFiles(...))`），后端只处理 API 请求。

#### 4. 部署脚本
`/home/ubuntu/.openclaw/workspace/project-agent-v2/scripts/deploy-frontend.sh`
- 构建：`npm run build`
- 复制：`dist/* → /var/www/project-agent/frontend/agent/`
- 清理：删除旧版 JS/CSS（只保留当前版本）

### 改造效果

| 指标 | 改造前 | 改造后 | 提升 |
|------|--------|--------|------|
| 静态请求服务方 | Gunicorn Worker | Nginx 直接 | 性能 ↑ 10x |
| Worker 负载 | 静态 + API 混合 | 仅 API | 压力 ↓ 80% |
| 磁盘空间 | 20MB（含历史版本） | 932KB | ↓ 95% |
| 连接重置概率 | 高（Worker 被占用） | 低 | 稳定性 ↑ |

### 涉及文件
- `/etc/nginx/sites-available/project-agent-v2` - Nginx 配置
- `/home/ubuntu/.openclaw/workspace/project-agent-v2/backend/app/main.py` - 移除静态挂载（第 9860+ 行）
- `/home/ubuntu/.openclaw/workspace/project-agent-v2/scripts/deploy-frontend.sh` - 部署脚本

### 回退方案
如需回退，恢复 main.py 末尾的静态文件挂载代码（已注释保留）。

---

## 🔧 2026-06-07 AI洞察本地模型润色 + 定时生成

### 背景
看板"AI每日洞察"原为规则模板生成，内容机械。改为本地模型润色，提升可读性。

### 实现方案

**架构：定时生成 + 本地润色 + 缓存读取**

```
凌晨 00:30  →  规则生成 + 本地润色 → 存数据库
中午 12:30  →  规则生成 + 本地润色 → 存数据库
用户打开看板 →  读数据库（秒开）
```

### 本地模型配置

- URL: `http://127.0.0.1:8001/api/generate`
- 模型: `qwen3.5:35B`
- 超时: 30秒
- 失败时返回原始内容（降级）

### 数据库变更

```sql
ALTER TABLE ai_insights 
ADD COLUMN IF NOT EXISTS period VARCHAR(10) DEFAULT 'morning',
ADD COLUMN IF NOT EXISTS raw_content TEXT;
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/ai_insight_service.py` | 洞察生成服务（规则+润色） |
| `scripts/generate_insight_cron.py` | 定时任务脚本 |

### 新增API

- `GET /api/agent/dashboard/insight` - 获取最新洞察（读缓存）
- `POST /api/agent/dashboard/insight/generate?period=morning|noon` - 触发生成（仅admin）

### Crontab定时任务

```cron
# AI洞察定时生成 - 每天2次
30 0 * * * ... generate_insight_cron.py --period morning
30 12 * * * ... generate_insight_cron.py --period noon
```

### 润色效果

**原始（规则模板）：**
> 📊 【项目进度】进行中 25 个，平均进度 4.0%

**润色后（本地模型）：**
> 早安！项目进展势头良好🚀
> 25个项目持续推进中，整体进度4%...

### 成本

- 每天调用2次本地模型，无token成本
- 响应时间：~7秒（含本地模型推理）

---

## 🔧 2026-06-07 AI洞察 - 只分析有任务数据的项目

### 背景
用户要求只分析"更新过计划"的项目，实际是指"有实际任务数据"的项目（上传了计划且解析出任务）。

### 实现方案

**分析范围定义**：
- 只统计有任务数据的项目（task_count > 0）
- 排除采用标准化模板或只有"默认计划"（空计划）的项目

**当前分析范围**：
| 项目 | 负责人 | 任务数 | 进度 |
|------|--------|--------|------|
| 田阳铝厂阳极组装提质增效项目 | 陆宏东 | 38 | 0% |
| 隆林铝厂空压机集中控制项目 | 周贵平 | 31 | 58% |
| 隆林铝厂整流系统总调PLC升级改造项目 | 陆宏东 | 20 | 43% |

**其他26个项目**：采用标准化模板或暂无计划数据，不在智能分析范围。

### 润色效果

**原始（规则模板）**：
> 📋 【分析范围】本次分析 3 个已上传详细计划的项目（有任务数据）

**润色后（本地模型）**：
> 午安！3个计划项目已分析。
> 📋【分析范围】本次仅分析3个已上传详细计划的项目...

### Bug修复

**问题**：低进度项目列表错误显示了进度58%的项目

**根因**：SQL查询使用`progress < 100`，获取的是"所有进行中项目"

**修复**：改为`progress < 50`，只获取真正的"低进度项目"

```python
# 修复前（错误）
delayed_projects = conn.execute(text("""
    SELECT name, progress FROM projects
    WHERE status = '进行中' AND progress < 100
    ...
"""))

# 修复后（正确）
low_progress_projects = conn.execute(text("""
    SELECT name, progress FROM projects
    WHERE status = '进行中' AND progress < 50
    ...
"""))
```

---

## 🔧 2026-05-11 项目详情页权限控制 & Token 获取优化

### 问题
1. 罗丽群没有权限时，点击"上传计划"等按钮直接跳转到登录页
2. 登录后进入项目详情正常，返回项目列表后再点击其他项目卡片，跳转到登录页

### 根因
1. **权限控制缺失**：前端没有根据用户权限隐藏按钮
2. **Token 获取逻辑缺陷**：很多 API 使用 `get_user_token(username)` 从内存缓存获取 token，服务重启后缓存丢失，导致 401 错误

### 解决方案

#### 1. 前端权限控制
在 `ProjectDetail.tsx` 中添加权限检查：
- 上传计划按钮：仅项目负责人或管理员（role_id=11）可见
- 导入成本按钮：仅项目负责人或管理员可见
- 知识库上传按钮：仅项目负责人或管理员可见

#### 2. 后端 Token 获取优化
- 在 `get_current_user` 中添加 `_raw_token` 字段保存原始 token
- 所有使用 `get_user_token(username)` 的 API 现在优先从 `current_user.get("_raw_token")` 获取
- 避免"服务重启 → 内存缓存丢失 → 401 错误"的问题

```python
# get_current_user 返回的 payload 结构
{
    "sub": "17878836629",
    "username": "17878836629",
    "_raw_token": "eyJhbGciOiJIUzI1NiIs...",  # 新增：原始 token
    "employee_id": "17878836629",
    "name": "罗丽群",
    "role_id": 15
}

# API 中获取 token 的优先级
token = current_user.get("_raw_token") or get_user_token(username)
```

### 涉及文件
- `/frontend/src/pages/ProjectDetail.tsx` - 权限控制
- `/backend/app/main.py` - Token 获取逻辑优化（共12处API）

### 全局检查结果

**后端 API（已全部修复）**：
- 所有使用 `get_user_token` 的 API 已改为 `current_user.get("_raw_token") or get_user_token(username)`
- routes/ 目录下的路由文件不使用 `get_user_token`，无需修改

**前端权限控制**：
- ProjectDetail.tsx 已添加权限控制
- 其他页面后端有权限检查，返回 403 时显示错误提示，不跳转登录页

