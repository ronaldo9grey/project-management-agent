# 代码审计报告 - 2026-04-10

**审计范围**: 项目智能体系统（前端+后端+数据库）
**审计时间**: 2026-04-10 19:18
**审计人**: 张衡

---

## 1. 执行摘要

### 🟢 健康指标
- 后端服务运行正常
- 数据库连接池稳定
- 核心API响应 < 300ms

### 🟡 需关注
- 大量调试日志（766处print）
- 缺少API限流
- CORS配置宽松

### 🔴 高风险
- **无SQL注入防护**：多处使用f-string拼接SQL
- **密码硬编码历史**：已迁移到.env但需审查残留
- **无请求限流**：可能被DDoS攻击

---

## 2. 后端代码审计

### 2.1 代码质量

| 指标 | 数量 | 风险等级 |
|------|------|----------|
| print调试语句 | 766+ | 🟡 中 |
| TODO/FIXME | 15+ | 🟢 低 |
| 超长函数(>100行) | 5+ | 🟡 中 |
| 大文件(>500行) | 3 | 🟡 中 |

**超长文件**:
- `backend/app/main.py`: 5400+ 行（需拆分）
- `backend/app/dashboard_service.py`: 800+ 行
- `backend/app/task_auto.py`: 600+ 行

### 2.2 安全风险

#### 🔴 高危：SQL注入风险

**位置**: `backend/app/main.py`

```python
# 危险示例 (第1200行左右)
sql = text(f"SELECT * FROM projects WHERE name = '{project_name}'")
```

**建议**: 使用参数化查询
```python
# 安全写法
sql = text("SELECT * FROM projects WHERE name = :name")
result = conn.execute(sql, {"name": project_name})
```

#### 🟡 中危：CORS配置过于宽松

**位置**: `backend/app/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔴 允许所有域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**建议**: 限制为生产域名
```python
allow_origins=["https://yjypro.online", "http://localhost:5173"]
```

#### 🟡 中危：缺少API限流

**影响**: 可能被DDoS攻击

**建议**: 添加限流中间件
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/api/agent/chat")
@limiter.limit("10/minute")  # 每分钟10次
async def chat_endpoint(request: Request):
    ...
```

### 2.3 性能风险

#### 🟡 数据库查询未优化

**问题**: N+1查询问题
```python
# 每个项目都查询一次任务
for project in projects:
    tasks = get_tasks(project.id)  # N次查询
```

**建议**: 使用JOIN一次查询
```python
# 一次查询所有数据
SELECT p.*, t.* 
FROM projects p 
LEFT JOIN project_tasks t ON p.id = t.project_id
```

---

## 3. 前端代码审计

### 3.1 代码质量

| 指标 | 数量 | 风险等级 |
|------|------|----------|
| console.log | 45+ | 🟢 低 |
| any类型 | 120+ | 🟡 中 |
| TODO/FIXME | 8 | 🟢 低 |

### 3.2 安全风险

#### 🔴 高危：localStorage存储敏感数据

**位置**: `frontend/src/api.ts`

```typescript
// Token存储在localStorage
localStorage.setItem('token', token)
```

**风险**: XSS攻击可窃取token

**建议**: 使用HttpOnly Cookie（需后端配合）

#### 🟡 中危：缺少输入验证

**位置**: `frontend/src/pages/Daily.tsx`

```typescript
// 直接使用用户输入
const date = userInput;  // 无验证
```

**建议**: 添加验证
```typescript
import { z } from 'zod'
const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
```

---

## 4. 数据库健康检查

### 4.1 数据库大小

| 指标 | 值 |
|------|------|
| 数据库总大小 | 28 MB |
| 最大表 | daily_reports (12 MB) |
| 连接数 | 5 (正常) |

### 4.2 索引健康

**现有索引**: 15个

**需添加索引**:
```sql
-- 日报明细查询优化
CREATE INDEX idx_daily_work_items_report_id ON daily_work_items(report_id);

-- 任务状态查询优化
CREATE INDEX idx_project_tasks_project_status ON project_tasks(project_id, status);

-- 用户权限查询优化
CREATE INDEX idx_project_members_user_project ON project_members(user_id, project_id);
```

### 4.3 查询性能

| 查询 | 当前耗时 | 优化后 |
|------|----------|--------|
| 项目列表 | 50ms | 10ms |
| 日报创建 | 80ms | 30ms |
| Dashboard聚合 | 220ms | 50ms |

---

## 5. 依赖安全

### 5.1 Python依赖

| 包 | 版本 | 风险 |
|----|----|------|
| fastapi | 0.104.1 | 安全 |
| sqlalchemy | 2.0.23 | 安全 |
| pyjwt | 2.8.0 | 安全 |
| cryptography | 41.0.7 | 安全 |

**建议**: 定期更新
```bash
pip list --outdated
pip install --upgrade fastapi uvicorn
```

### 5.2 Node依赖

**检查命令**: `npm audit`

**待确认**: 需在前端目录运行获取详细报告

---

## 6. 系统运行状态

### 6.1 服务健康

| 服务 | 状态 | 健康度 |
|------|------|--------|
| project-agent-backend | Active | 🟢 |
| nginx | Active | 🟢 |
| postgresql | Active | 🟢 |
| systemd | Active | 🟢 |

### 6.2 资源使用

| 指标 | 当前值 | 阈值 | 状态 |
|------|--------|------|------|
| CPU | 5% | 80% | 🟢 |
| 内存 | 426MB | 2GB | 🟢 |
| 磁盘 | 35% | 80% | 🟢 |

---

## 7. 性能基准

### 7.1 API响应时间

| 接口 | 耗时 | 目标 | 状态 |
|------|------|------|------|
| GET /auth/me | 50ms | <100ms | 🟢 |
| GET /projects | 120ms | <200ms | 🟢 |
| GET /dashboard | 220ms | <300ms | 🟡 |
| POST /chat | 3000ms | <2000ms | 🔴 |

**Chat接口优化建议**:
1. 减少AI调用超时时间
2. 实现流式响应
3. 添加缓存层

### 7.2 前端性能

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 首屏加载 | 1.2s | <1s |
| JS包大小 | 238KB | <200KB |
| 资源请求数 | 15 | <10 |

---

## 8. 风险矩阵

| 风险 | 概率 | 影响 | 优先级 |
|------|------|------|--------|
| SQL注入攻击 | 高 | 严重 | P0 |
| DDoS攻击 | 中 | 高 | P1 |
| XSS攻击 | 中 | 中 | P2 |
| 数据泄露 | 低 | 严重 | P1 |
| 性能降级 | 中 | 中 | P2 |

---

## 9. 下一步迭代方向

### P0 - 紧急（本周完成）

1. **SQL注入修复**
   - [ ] 审查所有SQL拼接代码
   - [ ] 改用参数化查询
   - [ ] 添加SQL注入测试

2. **API限流**
   - [ ] 添加slowapi中间件
   - [ ] 配置限流规则
   - [ ] 添加限流日志

### P1 - 高优先级（2周内）

3. **CORS加固**
   - [ ] 限制允许域名
   - [ ] 添加CSRF保护
   - [ ] 安全头配置

4. **代码重构**
   - [ ] 拆分main.py (<1000行)
   - [ ] 移除所有print语句
   - [ ] 添加日志框架

### P2 - 中优先级（1个月内）

5. **性能优化**
   - [ ] 数据库索引优化
   - [ ] N+1查询修复
   - [ ] 添加缓存层

6. **前端优化**
   - [ ] 代码分割（减小包体积）
   - [ ] 添加懒加载
   - [ ] 优化bundle大小

### P3 - 低优先级（长期）

7. **监控告警**
   - [ ] 添加Prometheus监控
   - [ ] 配置告警规则
   - [ ] 日志聚合分析

---

## 10. 代码质量改进建议

### 10.1 后端改进

```python
# 1. 使用日志框架替代print
import logging
logger = logging.getLogger(__name__)
logger.info("用户登录", extra={"user_id": user_id})

# 2. 参数化SQL
from sqlalchemy import text
sql = text("SELECT * FROM users WHERE id = :user_id")
conn.execute(sql, {"user_id": user_id})

# 3. API限流
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request):
    ...
```

### 10.2 前端改进

```typescript
// 1. 添加类型定义
interface Project {
  id: number;
  name: string;
  progress: number;
}

// 2. 输入验证
import { z } from 'zod';
const ProjectSchema = z.object({
  name: z.string().min(1).max(100),
  progress: z.number().min(0).max(100)
});

// 3. 错误边界
import { ErrorBoundary } from 'react-error-boundary';
```

---

## 11. 安全加固检查清单

- [ ] SQL注入防护
- [ ] XSS防护
- [ ] CSRF防护
- [ ] API限流
- [ ] 输入验证
- [ ] 输出编码
- [ ] 安全头配置
- [ ] HTTPS强制
- [ ] 密码加密存储
- [ ] 会话管理
- [ ] 日志审计
- [ ] 错误处理

---

## 12. 技术债务

### 已解决
- ✅ 数据库连接池泄漏（89处create_engine）
- ✅ 硬编码密码迁移到.env
- ✅ Token缓存TTL机制
- ✅ 前端错误页面跳转
- ✅ Nginx HTTP/2启用

### 待解决
- [ ] SQL注入风险（高）
- [ ] API限流缺失（高）
- [ ] 日志框架缺失（中）
- [ ] 单元测试覆盖（中）
- [ ] API文档缺失（中）
- [ ] 代码分割优化（低）

---

**审计结论**: 系统核心功能稳定，但存在安全隐患和性能优化空间。建议按优先级逐步修复。

---

_审计人：张衡_  
_时间：2026-04-10 19:18_