# 项目智能体 - 代码审查报告

**审查日期**: 2026-04-10  
**审查范围**: 认证机制、数据库连接、错误处理、安全漏洞  
**严重程度**: 🔴 严重 | 🟠 高危 | 🟡 中等 | 🟢 低危

---

## 🔴 严重问题

### 1. 数据库连接池泄漏 (CRITICAL)

**位置**: `backend/app/main.py` 全文件  
**影响**: 导致连接池耗尽，服务崩溃

**问题描述**:
- 文件中有 **89 处** `create_engine()` 调用
- 每次调用都创建新的连接池（默认 5 个连接）
- 没有调用 `engine.dispose()` 释放连接
- 高并发时快速耗尽 PostgreSQL 最大连接数（默认 100）

**现状**:
```python
# 每个函数内部都这样写（89 次！）
db_url = os.getenv("DATABASE_URL", "postgresql://...")
engine = create_engine(db_url)  # 每次创建新连接池
with engine.connect() as conn:
    ...
# 没有 engine.dispose()！
```

**风险场景**:
- 100 个并发请求 = 500 个数据库连接
- PostgreSQL 默认 max_connections = 100
- 连接耗尽后所有服务崩溃

**修复方案**:
1. 创建全局单例引擎
2. 配置连接池参数
3. 在应用关闭时释放

```python
# 推荐方案
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 全局单例
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            os.getenv("DATABASE_URL"),
            pool_size=10,           # 连接池大小
            max_overflow=20,        # 最大溢出连接
            pool_recycle=3600,      # 连接回收时间（秒）
            pool_pre_ping=True,     # 连接健康检查
            echo=False
        )
    return _engine

# 使用依赖注入
def get_db():
    engine = get_engine()
    with engine.connect() as conn:
        yield conn
```

---

### 2. 敏感信息硬编码 (CRITICAL)

**位置**: `backend/app/main.py` 多处  
**影响**: 数据库密码泄露风险

**问题描述**:
```python
db_url = os.getenv("DATABASE_URL", 
    "postgresql://yjydb:qv52A03xcxAQCoDglUJelm4Sb@localhost:5432/project_cost_tracking")
```

**风险**:
- 密码明文硬编码在代码中
- Git 历史中永久保留
- 代码泄露 = 数据库泄露

**修复方案**:
1. 移除所有硬编码密码
2. 强制从环境变量读取
3. 使用 `.env` 文件（不提交到 Git）
4. 使用密钥管理服务（生产环境）

```python
# 正确做法
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL environment variable not set")
```

---

### 3. 内存缓存无过期机制 (HIGH)

**位置**: `backend/app/main.py:1353-1360`

**问题描述**:
```python
_token_storage: Dict[str, str] = {}
_user_info_storage: Dict[str, Dict] = {}
_current_user_cache: Dict[str, Dict] = {}
```

**风险**:
- 缓存永不过期，内存持续增长
- 服务重启后所有用户需要重新登录
- 多进程部署时缓存不同步

**修复方案**:
1. 使用 Redis 替代内存缓存
2. 或使用 TTL 缓存（如 `cachetools.TTLCache`）

```python
from cachetools import TTLCache

# 带 TTL 的缓存
_token_storage = TTLCache(maxsize=1000, ttl=28800)  # 8小时
_user_info_storage = TTLCache(maxsize=1000, ttl=3600)  # 1小时
```

---

### 4. Token 刷新机制缺陷 (HIGH) - 已修复

**位置**: `backend/app/main.py:1416-1500`

**问题描述** (已修复):
- 原代码返回同一个 token，没有真正刷新
- 导致无限重试循环

**修复状态**: ✅ 已修复 (2026-04-10)

---

## 🟠 高危问题

### 5. 错误处理不完善

**问题描述**:
- 103 个 `except` 块，但大部分只打印日志
- 部分异常被静默忽略
- 没有统一错误上报机制

**示例**:
```python
except Exception as e:
    print(f"[Auth] 获取用户信息失败: {e}")
    # 没有重试、没有报警、用户看到错误
```

**修复方案**:
1. 区分可恢复错误和致命错误
2. 实现重试机制
3. 关键错误上报（邮件/Slack）

---

### 6. 缺少请求限流

**问题描述**:
- 没有实现 API 限流
- 容易被恶意请求攻击
- 可能导致服务过载

**修复方案**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/agent/daily/create")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def create_daily_report(...):
    ...
```

---

### 7. SQL 注入风险检查

**状态**: ✅ 已使用参数化查询
**代码中所有 SQL 都使用了 `text()` + 参数绑定**

```python
# 安全示例
conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

---

## 🟡 中等问题

### 8. 日志记录不规范

**问题描述**:
- 766 处 `print()` 语句
- 没有使用 `logging` 模块
- 生产环境无法关闭调试日志

**修复方案**:
```python
import logging

logger = logging.getLogger(__name__)
logger.info("用户登录成功")
logger.error("数据库连接失败", exc_info=True)
```

---

### 9. 缺少请求超时配置

**问题描述**:
- 部分外部请求超时 10 秒
- 部分请求没有超时限制
- 可能导致请求堆积

**修复方案**:
统一配置超时时间，建议：
- 数据库查询: 5 秒
- 外部 API: 10 秒
- AI 接口: 30 秒

---

### 10. CORS 配置过于宽松

**位置**: `backend/app/main.py:25-32`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**风险**: 生产环境应限制允许的域名

---

## 📊 统计摘要

| 类别 | 数量 | 严重程度 |
|------|------|----------|
| 数据库连接泄漏 | 89 处 | 🔴 严重 |
| 硬编码密码 | 多处 | 🔴 严重 |
| 内存缓存无过期 | 3 个缓存 | 🟠 高危 |
| print() 日志 | 766 处 | 🟡 中等 |
| except 块 | 103 处 | 需检查 |

---

## 🛠️ 修复优先级

1. **立即修复** (本次迭代)
   - ✅ Token 刷新机制
   - ⏳ 数据库连接池（待修复）
   - ⏳ 移除硬编码密码（待修复）

2. **近期修复** (下个迭代)
   - 内存缓存 TTL
   - 请求限流
   - 日志规范化

3. **长期优化**
   - 迁移到 Redis
   - 统一错误处理
   - 性能监控

---

## 📝 下一步行动

1. 创建数据库连接池单例模块
2. 清理硬编码密码，改用环境变量
3. 实现缓存 TTL 机制
4. 添加 API 限流中间件

---

**审查人**: 张衡  
**审查时间**: 2026-04-10 09:35
