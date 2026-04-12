# 项目管理智能体 - 后端服务
# FastAPI + LangChain/LangGraph + DeepSeek

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime, timedelta
import httpx
import asyncio
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# LangChain imports
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# API限流配置
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="项目管理智能体",
    description="基于LangChain/LangGraph的项目管理AI服务",
    version="0.1.0"
)

# 添加限流处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS配置
# ============== API限流配置 ==============
limiter = Limiter(key_func=get_remote_address)

# ============== FastAPI应用 ==============
app = FastAPI(
    title="项目智能体API",
    description="项目管理智能助手后端服务",
    version="1.0.0"
)

# 添加限流处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yjypro.online",      # 生产环境
        "http://localhost:5173",      # 本地开发
        "http://127.0.0.1:5173",      # 本地开发（IP）
        "https://open.feishu.cn",     # 飞书机器人回调
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 配置
class Settings:
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    UPLOAD_DIR = "/tmp/project-agent/uploads"
    # JWT配置（与现有后端一致）
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    # 工作时间配置
    WORK_TIME_MORNING_START = os.getenv("WORK_TIME_MORNING_START", "08:15")
    WORK_TIME_MORNING_END = os.getenv("WORK_TIME_MORNING_END", "12:00")
    WORK_TIME_AFTERNOON_START = os.getenv("WORK_TIME_AFTERNOON_START", "13:45")
    WORK_TIME_AFTERNOON_END = os.getenv("WORK_TIME_AFTERNOON_END", "18:00")
    WORK_HOURS_PER_DAY = float(os.getenv("WORK_HOURS_PER_DAY", "8.0"))

settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# ============== 数据库连接池（单例） ==============
from .database import get_engine, get_connection, text, dispose_engine

# ============== 日志框架 ==============
from .logger import get_logger
logger = get_logger(__name__)

# ============== 缓存管理（带 TTL） ==============
from .cache import cache_manager, store_user_token, get_user_token, get_user_info_cache

# ============== 定时任务 ==============

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

async def daily_alert_detection_job():
    """每日预警检测任务（凌晨1点执行）"""
    try:
        from .dashboard_service import run_daily_alert_detection
        count = run_daily_alert_detection()
        logger.info(f" 完成 {count} 个项目的预警检测")

        # 推送每日摘要到微信
        from .dashboard_service import get_dashboard_overview
        from .push_service import push_daily_summary_to_wechat

        overview = get_dashboard_overview()
        push_daily_summary_to_wechat(overview['stats'])

    except Exception as e:
        logger.error(f" {e}")

# ============== 认证相关 ==============

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/agent/auth/login")


def verify_token(token: str) -> Optional[Dict]:
    """验证JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return {"username": username, "user_id": payload.get("user_id")}
    except JWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="认证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 检查缓存（使用 cache_manager）
    cached_user = cache_manager.get_current_user(token)
    if cached_user:
        return cached_user

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    # 获取用户信息，补充 employee_id
    username = payload.get("sub")
    if username:
        # 优先从缓存获取
        user_info = get_user_info_cache(username)
        
        # 如果缓存没有，从数据库查询
        if not user_info:
            try:
                # text 已从 database 模块导入
                from dotenv import load_dotenv
                load_dotenv()                
                with get_connection() as conn:
                    result = conn.execute(text("""
                        SELECT employee_id, name, department, position
                        FROM personnel WHERE employee_id = :username
                    """), {"username": username}).fetchone()
                    
                    if result:
                        user_info = {
                            "employee_id": result[0],
                            "name": result[1],
                            "department": result[2],
                            "position": result[3]
                        }
                        # 存入缓存
                        cache_manager.store_user_info(username, user_info)
            except Exception as e:
                logger.error(f" {e}")
        
        if user_info:
            payload["employee_id"] = user_info.get("employee_id", username)
            payload["name"] = user_info.get("name", "")
            payload["department"] = user_info.get("department", "")
            payload["position"] = user_info.get("position", "")

    # 确保 employee_id 存在
    if "employee_id" not in payload:
        payload["employee_id"] = username  # 使用 username 作为 employee_id

    # 缓存用户信息（使用 cache_manager）
    cache_manager.store_current_user(token, payload)
    return payload

async def get_user_info(token: str) -> Dict:
    """获取用户详细信息（包含角色、部门、岗位）"""
    try:
        # 获取当前用户信息
        response = await http_client.get(
            f"{settings.BACKEND_API_URL}/api/v1/auth/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            user_data = data.get("data", data)
            
            # 从 personnel 表补充部门、岗位信息
            # text 已从 database 模块导入
            from dotenv import load_dotenv
            load_dotenv()            
            employee_id = user_data.get("employee_id") or user_data.get("username")
            if employee_id:
                with get_connection() as conn:
                    person_result = conn.execute(text("""
                        SELECT name, department, position, phone, email
                        FROM personnel
                        WHERE employee_id = :employee_id
                    """), {"employee_id": employee_id}).fetchone()
                    
                    if person_result:
                        user_data["name"] = person_result[0] or user_data.get("name", employee_id)
                        user_data["department"] = person_result[1] or ""
                        user_data["position"] = person_result[2] or ""
                        user_data["phone"] = person_result[3] or ""
                        user_data["email"] = person_result[4] or ""
            
            logger.info(f": employee_id={user_data.get('employee_id')}, name={user_data.get('name')}, department={user_data.get('department')}, position={user_data.get('position')}")
            return user_data
        return {}
    except Exception as e:
        logger.error(f" {e}")
        return {}

async def get_projects_with_auth(token: str, user_info: Dict = None) -> List[Dict]:
    """获取项目列表，根据用户角色过滤，并计算进度"""
    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    with get_connection() as conn:
        # 判断用户角色
        if user_info:
            role_id = user_info.get("role_id")
            employee_name = user_info.get("name", "")

            # role_id=11 是系统管理员，可以看到所有项目
            if role_id == 11:
                logger.debug("管理员用户，返回所有项目")
                result = conn.execute(text("""
                    SELECT id, name, leader, status FROM projects
                    WHERE is_deleted = false ORDER BY id
                """))
            else:
                # 其他角色，只查询自己负责的项目
                logger.debug(f"普通用户 {employee_name}，查询负责的项目")
                result = conn.execute(text("""
                    SELECT id, name, leader, status FROM projects
                    WHERE is_deleted = false AND leader = :emp_name
                    ORDER BY id
                """), {"emp_name": employee_name})
        else:
            # 无用户信息，返回所有项目
            result = conn.execute(text("""
                SELECT id, name, leader, status FROM projects
                WHERE is_deleted = false ORDER BY id
            """))

        # 计算每个项目的进度
        projects = []
        for row in result:
            project_id = row[0]
            try:
                task_stats = conn.execute(text("""
                    SELECT
                        COUNT(*) as total_tasks,
                        SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed_tasks,
                        AVG(progress) as avg_progress
                    FROM project_tasks
                    WHERE project_id::integer = :pid
                      AND is_deleted = false
                      AND is_latest = true
                """), {"pid": project_id})
                ts = task_stats.fetchone()
                progress = round((ts[1] / ts[0] * 100 + float(ts[2] or 0)) / 2, 1) if ts and ts[0] else 0
            except:
                progress = 0

            projects.append({
                "id": project_id,
                "name": row[1],
                "leader": row[2],
                "status": row[3] or "进行中",
                "progress": progress
            })

        logger.debug(f"返回项目数: {len(projects)}")
        return projects

async def get_all_projects_for_matching() -> List[Dict]:
    """获取所有项目用于日报匹配（不受权限限制）"""
    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT id, name, leader, status FROM projects
            WHERE is_deleted = false ORDER BY id
        """))

        projects = []
        for row in result:
            project_id = row[0]
            try:
                task_stats = conn.execute(text("""
                    SELECT
                        COUNT(*) as total_tasks,
                        SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed_tasks,
                        AVG(progress) as avg_progress
                    FROM project_tasks
                    WHERE project_id::integer = :pid
                      AND is_deleted = false
                      AND is_latest = true
                """), {"pid": project_id})
                ts = task_stats.fetchone()
                progress = round((ts[1] / ts[0] * 100 + float(ts[2] or 0)) / 2, 1) if ts and ts[0] else 0
            except:
                progress = 0

            projects.append({
                "id": project_id,
                "name": row[1],
                "leader": row[2],
                "status": row[3] or "进行中",
                "progress": progress
            })

        logger.info(f" 返回所有项目数: {len(projects)}")
        return projects

async def get_tasks_with_auth(project_id: int, token: str) -> List[Dict]:
    """使用认证token获取任务列表"""
    try:
        response = await http_client.get(
            f"{settings.BACKEND_API_URL}/api/v1/projects/{project_id}/tasks/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            # 处理可能的嵌套结构
            if isinstance(data, dict):
                return data.get("data", data)
            return data
        return []
    except Exception as e:
        logger.error(f" {e}")
        return []

# 全局HTTP客户端（会在 startup/shutdown 中管理）
http_client: Optional[httpx.AsyncClient] = None

# LLM初始化 (DeepSeek)
llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0.2
)

# ============== 数据模型 ==============

class DailyEntry(BaseModel):
    start_time: str
    end_time: str
    location: Optional[str] = None
    content: str
    project_hint: Optional[str] = None
    hours: float = 0
    # 智能匹配结果
    matched_project_id: Optional[int] = None
    matched_project_name: Optional[str] = None
    matched_task_id: Optional[str] = None
    matched_task_name: Optional[str] = None
    match_confidence: float = 0.0

class ParseDailyRequest(BaseModel):
    text: str
    user_id: Optional[str] = None

class ParseDailyResponse(BaseModel):
    entries: List[DailyEntry]
    confidence: float
    issues: List[str] = []

class ProjectInfo(BaseModel):
    id: int
    name: str
    leader: str
    status: str
    progress: float

class TaskInfo(BaseModel):
    task_id: str
    task_name: str
    assignee: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str

# ============== 现有后端API对接 ==============

async def get_projects_from_backend() -> List[Dict]:
    """从现有后端获取项目列表"""
    try:
        # 注意：现有后端需要认证，这里简化处理
        # 实际应该使用 service token 或用户 token
        response = await http_client.get(f"{settings.BACKEND_API_URL}/api/projects")
        if response.status_code == 200:
            data = response.json()
            # 根据实际返回结构调整
            return data.get("data", {}).get("list", [])
        return []
    except Exception as e:
        logger.error(f" {e}")
        return []

async def get_tasks_from_backend(project_id: int) -> List[Dict]:
    """从现有后端获取项目任务列表"""
    try:
        response = await http_client.get(
            f"{settings.BACKEND_API_URL}/api/projects/{project_id}/tasks"
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f" {e}")
        return []

# 缓存项目列表（简化版，生产环境用Redis）
_projects_cache: List[Dict] = []
_projects_cache_time: Optional[datetime] = None

async def get_cached_projects() -> List[Dict]:
    """获取缓存的项目列表"""
    global _projects_cache, _projects_cache_time

    # 缓存5分钟
    if (_projects_cache_time is None or
        datetime.now() - _projects_cache_time > timedelta(minutes=5) or
        not _projects_cache):
        _projects_cache = await get_projects_from_backend()
        _projects_cache_time = datetime.now()

    return _projects_cache

# ============== AI智能匹配 ==============

def match_project_by_name(project_hint: str, projects: List[Dict]) -> Optional[Dict]:
    """根据项目名称关键词匹配项目（支持模糊匹配）"""
    if not project_hint or not projects:
        return None

    import re
    
    # 提取关键词（去掉通用词）
    def extract_keywords(text):
        # 去掉通用词
        text = text.replace("项目", "").replace("工程", "").replace("系统", "").replace("研究", "").replace("开发", "").replace("协调", "")
        # 提取中文词组（2-10个字）
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,10}', text)
        return [k.lower() for k in keywords]
    
    hint_keywords = extract_keywords(project_hint)
    hint = project_hint.lower()
    best_match = None
    best_score = 0

    for project in projects:
        name = project.get("name", "")
        name_lower = name.lower()
        name_keywords = extract_keywords(name)
        
        score = 0
        
        # 完全匹配
        if hint == name_lower:
            return project
        
        # 包含匹配
        if hint in name_lower:
            score = max(score, len(hint) / len(name_lower))
        
        # 关键词匹配（模糊匹配）
        for hk in hint_keywords:
            for nk in name_keywords:
                if hk == nk:
                    score = max(score, 0.8)
                elif hk in nk or nk in hk:
                    score = max(score, 0.5)
        
        if score > best_score:
            best_score = score
            best_match = project

    # 阈值0.3以上认为是匹配
    if best_score >= 0.3:
        return best_match
    return None

def match_task_by_content(content: str, tasks: List[Dict]) -> Optional[Dict]:
    """根据工作内容匹配任务"""
    if not content or not tasks:
        return None

    content_lower = content.lower()
    keywords = ["图纸", "审查", "设计", "招标", "采购", "施工", "勘察", "会议", "协调"]

    best_match = None
    best_score = 0

    for task in tasks:
        task_name = task.get("task_name", "").lower()

        # 关键词匹配
        score = 0
        for kw in keywords:
            if kw in content_lower and kw in task_name:
                score += 0.3

        # 相似度匹配
        if task_name in content_lower or content_lower in task_name:
            score += 0.5

        if score > best_score:
            best_score = score
            best_match = task

    if best_score >= 0.3:
        return best_match
    return None

# ============== 日报解析（智能版） ==============

def parse_daily_text_smart(text: str, projects: List[Dict], current_date: str = None) -> Dict[str, Any]:
    """
    智能解析日报文本，自动匹配项目和任务

    Args:
        text: 日报文本
        projects: 项目列表（用于匹配）
        current_date: 当前日期
    """
    if current_date is None:
        current_date = datetime.now().strftime("%Y-%m-%d")

    # 构建项目提示信息（包含项目名称关键词）
    project_list = "\n".join([
        f"- {p.get('id')}: {p.get('name')} (关键词: {p.get('name').replace('项目', '').replace('工程', '').strip()[:10]})"
        for p in projects[:20]
    ])

    system_prompt = f"""你是项目管理助手，专门解析工程人员的日报文本。

可匹配的项目列表：
{project_list}

## 解析规则

### 1. 时间识别
- 支持："9点"、"09:00"、"上午"、"下午2点半"
- 标准工作时间：上午 08:15-12:00，下午 13:45-18:00
- 输出格式：HH:MM（24小时制）

### 2. 时间段共享（非常重要！）
- 如果用户说"下午13:45-18:00做了4件事"，这表示【共享时间段】
- **正确做法**：为每个任务生成独立条目，所有条目使用相同的时间
- **错误做法**：把时间累加
- hours 字段填 0，系统会自动计算

### 3. 序号内容分组（重要！）
当用户使用序号（1. 2. 3. 4.）列出多项工作时，要正确识别每项的边界：

**识别规则**：
- 序号后到下一个序号之前的内容，都属于该项
- 如果某项后面有逗号分隔的内容，仍属于该项
- 例如："4.隆林铝厂空压机项目研究，合同线下审批"
  - "隆林铝厂空压机项目研究"和"合同线下审批"都属于第4项
  - 应该合并为一个条目："推进隆林铝厂空压机项目研究，完成合同线下审批"
  
**错误示例**：
```
输入："1.xxx，2.xxx，3.xxx，4.xxx，yyy"
错误：把"yyy"单独分成一个条目
正确：第4项是"xxx，yyy"，合并为一个条目
```

**正确示例**：
```
输入："下午协调1.隆林铝厂除尘器研究，2.田林铝厂供电项目，3.隆林铝厂整流改造，4.隆林铝厂空压机项目，合同线下审批"

正确解析为4个条目：
1. 隆林铝厂除尘器研究
2. 田林铝厂供电项目
3. 隆林铝厂整流改造
4. 隆林铝厂空压机项目研究，完成合同线下审批（合并！）
```

### 4. 加班识别
- "额外X小时"、"加班X小时"、"晚上X小时" 表示加班
- 加班时间从 18:00 开始计算
- 必须生成独立的加班条目

### 4. 项目匹配
- 使用【模糊匹配】：检查日报中的项目关键词
- 关键词提取：去掉"项目"、"工程"、"研究"等通用词
- 例如："隆林铝厂除尘器" → 匹配 "隆林铝厂除尘器布袋脉冲精准控制研究项目"

### 5. 内容润色（重要！按STAR原则改写）
每条工作内容需要润色为规范的结果汇报格式：

**STAR原则**：
- **S**pecific（具体）：使用动词开头，明确动作
- **T**ime-bound（时效）：体现当期进展
- **A**chievable（成果）：强调产出和结果
- **R**elevant（相关）：关联项目背景

**润色规则**：
1. 使用动词开头：完成、协调、审核、编制、讨论、推进、优化、落实
2. 量化成果：如有数据、文档数、进度百分比，务必保留
3. 去掉冗余：删除"协调"、"处理"等模糊词，改为具体动作
4. 控制长度：15-40字，简洁有力
5. 结果导向：强调"完成"、"提交"、"通过"等结果状态

**润色示例**：
- 原文："协调4个铝厂一种新型电解铝多功能天车抓斗结构的设计及产业化项目审核技术文件"
- 润色："审核电解铝多功能天车抓斗产业化项目技术文件，完成4个铝厂技术评审"

- 原文："隆林铝厂除尘器布袋脉冲精准控制研究"
- 润色："推进隆林铝厂除尘器布袋脉冲精准控制研究，完成技术方案讨论"

- 原文："合同线下审批"
- 润色："完成合同线下审批流程"

### 6. 工时计算
- hours 字段统一填 0，由系统自动计算
- 系统会自动扣除午休时间（12:00-13:45）

示例输入：
"上午8:15-12:00协调4个铝厂一种新型电解铝多功能天车抓斗结构的设计及产业化项目审核技术文件；下午13:45-18:00协调1.隆林铝厂除尘器布袋脉冲精准控制研究，2.田林铝厂供电整流PLC控制系统稳定性研发项目，3.隆林铝厂整流系统总调PLC升级改造项目，4.隆林铝厂空压机集中控制项目研究，合同线下审批"

正确输出（注意：第4项"空压机项目研究，合同线下审批"合并为一个条目）：
{{
  "entries": [
    {{
      "start_time": "08:15",
      "end_time": "12:00",
      "location": "办公室",
      "content": "审核电解铝多功能天车抓斗产业化项目技术文件，完成4个铝厂技术评审",
      "project_hint": "电解铝多功能天车抓斗",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }},
    {{
      "start_time": "13:45",
      "end_time": "18:00",
      "location": "办公室",
      "content": "推进隆林铝厂除尘器布袋脉冲精准控制研究，完成技术方案讨论",
      "project_hint": "隆林铝厂除尘器",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }},
    {{
      "start_time": "13:45",
      "end_time": "18:00",
      "location": "办公室",
      "content": "推进田林铝厂供电整流PLC控制系统稳定性研发，完成需求对接",
      "project_hint": "田林铝厂供电整流",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }},
    {{
      "start_time": "13:45",
      "end_time": "18:00",
      "location": "办公室",
      "content": "推进隆林铝厂整流系统总调PLC升级改造，完成方案评审",
      "project_hint": "隆林铝厂整流系统",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }},
    {{
      "start_time": "13:45",
      "end_time": "18:00",
      "location": "办公室",
      "content": "推进隆林铝厂空压机集中控制项目研究，完成合同线下审批",
      "project_hint": "隆林铝厂空压机",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }}
  ],
  "confidence": 0.95,
  "issues": []
}}

输出格式（严格JSON）：
{{
  "entries": [
    {{
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "location": "地点",
      "content": "工作内容",
      "project_hint": "项目关键词",
      "matched_project_id": 项目ID或null,
      "matched_project_name": "项目名或空",
      "hours": 0
    }}
  ],
  "confidence": 0.95,
  "issues": []
}}"""

    user_prompt = f"当前日期：{current_date}\n\n日报文本：{text}\n\n请解析并返回JSON格式结果："

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        logger.debug(f" 调用 DeepSeek API...")
        response = llm.invoke(messages)
        logger.debug(f" API 返回: {response.content[:200]}...")

        # 清理响应内容
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        # 后处理：验证和补充
        entries = result.get("entries", [])

        # 如果没有解析出条目，尝试简单解析
        if not entries:
            logger.debug(f" 未解析出条目，尝试兜底解析...")
            entries = simple_parse_fallback(text, projects)

        # 先识别共享时间段，再计算工时
        # 按时间段分组
        time_groups = {}
        for i, entry in enumerate(entries):
            if entry.get("start_time") and entry.get("end_time"):
                time_key = f"{entry['start_time']}-{entry['end_time']}"
                if time_key not in time_groups:
                    time_groups[time_key] = []
                time_groups[time_key].append(i)

        # 计算工时（共享时间段平均分配）
        for time_key, indices in time_groups.items():
            start_time, end_time = time_key.split("-")
            try:
                from app.work_time_config import calculate_work_hours
                total_hours = calculate_work_hours(start_time, end_time)
                # 平均分配
                avg_hours = total_hours / len(indices)
                for idx in indices:
                    entries[idx]["hours"] = round(avg_hours, 2)
            except:
                pass

        # 项目匹配
        for entry in entries:
            if not entry.get("matched_project_id") and entry.get("project_hint"):
                matched = match_project_by_name(entry["project_hint"], projects)
                if matched:
                    entry["matched_project_id"] = matched.get("id")
                    entry["matched_project_name"] = matched.get("name")
                    entry["match_confidence"] = 0.7

        result["entries"] = entries
        return result

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()

        # 兜底：简单解析
        entries = simple_parse_fallback(text, projects)

        return {
            "entries": entries,
            "confidence": 0.5,
            "issues": [f"AI解析失败，已使用基础解析: {str(e)}"]
        }

def simple_parse_fallback(text: str, projects: List[Dict]) -> List[Dict]:
    """
    简单解析兜底方案：当AI解析失败时使用
    """
    entries = []

    # 提取工时信息（如果用户明确说了"做了X小时"）
    import re
    hours_pattern = r'(\d+(?:\.\d+)?)\s*小时'
    hours_matches = re.findall(hours_pattern, text)
    explicit_hours = float(hours_matches[0]) if hours_matches else None

    # 提取项目关键词
    for project in projects:
        project_name = project.get("name", "")
        # 去掉"项目"、"工程"等通用词
        keywords = project_name.replace("项目", "").replace("工程", "").replace("系统", "").strip()

        if keywords and keywords in text:
            # 找到匹配的项目，使用标准工作时间
            entries.append({
                "start_time": "08:15",
                "end_time": "18:00",
                "location": "办公室",
                "content": text[:50],
                "project_hint": keywords,
                "matched_project_id": project.get("id"),
                "matched_project_name": project_name,
                "hours": explicit_hours if explicit_hours else 0  # 如果明确说了工时则用，否则让系统计算
            })
            break

    # 如果还是没找到，创建一个默认条目
    if not entries:
        entries.append({
            "start_time": "08:15",
            "end_time": "18:00",
            "location": "办公室",
            "content": text[:50] if len(text) > 50 else text,
            "project_hint": "",
            "matched_project_id": None,
            "matched_project_name": "",
            "hours": 0  # 让系统自动计算
        })

    return entries

async def enrich_with_tasks(entries: List[Dict]) -> List[Dict]:
    """为每个条目匹配任务"""
    for entry in entries:
        project_id = entry.get("matched_project_id")
        if project_id:
            tasks = await get_tasks_from_backend(project_id)
            matched_task = match_task_by_content(entry.get("content", ""), tasks)
            if matched_task:
                entry["matched_task_id"] = matched_task.get("task_id")
                entry["matched_task_name"] = matched_task.get("task_name")
                entry["match_confidence"] = max(entry.get("match_confidence", 0), 0.6)
    return entries

# ============== LangGraph工作流 ==============

class DailyParseState(dict):
    text: str
    user_id: Optional[str]
    projects: List[Dict]
    parsed_entries: List[Dict]
    confidence: float
    issues: List[str]

async def parse_node(state: DailyParseState):
    """解析节点"""
    result = parse_daily_text_smart(
        state["text"],
        state.get("projects", []),
        datetime.now().strftime("%Y-%m-%d")
    )
    return {
        "parsed_entries": result.get("entries", []),
        "confidence": result.get("confidence", 0),
        "issues": result.get("issues", [])
    }

async def match_tasks_node(state: DailyParseState):
    """匹配任务节点"""
    entries = state.get("parsed_entries", [])
    enriched = await enrich_with_tasks(entries)
    return {"parsed_entries": enriched}

# 构建工作流（顺序执行）
from langgraph.graph import StateGraph, END

daily_workflow = StateGraph(DailyParseState)
daily_workflow.add_node("parse", parse_node)
daily_workflow.add_node("match_tasks", match_tasks_node)
daily_workflow.set_entry_point("parse")
daily_workflow.add_edge("parse", "match_tasks")
daily_workflow.add_edge("match_tasks", END)
daily_agent = daily_workflow.compile()

# ============== API路由 ==============

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "backend_url": settings.BACKEND_API_URL
    }

# ============== 新增：智能解析代理接口 ==============

class SmartParseRequest(BaseModel):
    """智能解析请求"""
    text: str
    report_date: Optional[str] = None

@app.post("/api/agent/daily/smart-parse")
async def smart_parse_daily(
    request: SmartParseRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    智能解析日报文本 - 使用 DeepSeek AI 解析 + 项目任务匹配

    支持多次输入，每次解析会覆盖之前的内容

    返回：
    - matched_projects: 匹配到的项目列表
    - unmatched_projects: 未匹配的项目名称
    - entries: 解析出的工作事项（含匹配的 task_id）
    - warnings: 警告信息
    """
    try:
        # 导入任务匹配函数
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from task_auto import match_task_by_content_ai

        username = current_user.get("username")
        token = get_user_token(username)

        if not token:
            raise HTTPException(status_code=401, detail="未找到用户认证信息")

        # 获取所有项目用于匹配（不受权限限制，任何人都可以参与任何项目）
        projects = await get_all_projects_for_matching()

        # 使用本地智能解析函数（调用 DeepSeek API）
        logger.debug(f" 开始解析: {request.text[:50]}...")
        parsed = parse_daily_text_smart(request.text, projects, request.report_date)

        # 为每个条目匹配任务
        entries = []
        matched_projects_list = []
        unmatched_projects_list = []

        for entry in parsed.get("entries", []):
            # 如果匹配到项目，尝试匹配任务
            if entry.get("matched_project_id"):
                matched_task = await match_task_by_content_ai(
                    entry.get("content", ""),
                    entry["matched_project_id"],
                    entry.get("matched_project_name", "")
                )
                if matched_task:
                    entry["matched_task_id"] = matched_task.get("task_id")
                    entry["matched_task_name"] = matched_task.get("task_name")

                # 记录匹配的项目
                if entry["matched_project_name"] not in [p.get("name") for p in matched_projects_list]:
                    matched_projects_list.append({
                        "id": entry["matched_project_id"],
                        "name": entry["matched_project_name"]
                    })

            entries.append(entry)

        # 收集未匹配的项目
        for entry in parsed.get("entries", []):
            if entry.get("project_hint") and not entry.get("matched_project_id"):
                if entry["project_hint"] not in unmatched_projects_list:
                    unmatched_projects_list.append(entry["project_hint"])

        # 构建警告信息
        warnings = []
        if unmatched_projects_list:
            for project_name in unmatched_projects_list:
                warnings.append(f"⚠️ 项目「{project_name}」在系统中未找到匹配，请确认项目名称是否正确")

        if not entries:
            warnings.append("⚠️ 未识别到有效的工作事项，请检查输入格式")

        return {
            "entries": entries,
            "matched_projects": matched_projects_list,
            "unmatched_projects": unmatched_projects_list,
            "warnings": warnings,
            "confidence": parsed.get("confidence", 0.7),
            "issues": warnings
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


class CreateReportRequest(BaseModel):
    """创建日报请求"""
    report_date: str
    work_items: List[Dict[str, Any]]
    work_target: Optional[str] = None
    tomorrow_plan: Optional[str] = None
    original_input: Optional[str] = None  # 原始自然语言输入
    ai_parsed_data: Optional[Dict[str, Any]] = None  # AI解析结果

@app.post("/api/agent/daily/create")
async def create_daily_report(
    request: CreateReportRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    创建日报 - 智能体专用（支持覆盖已有日报）

    如果该日期已存在日报，先删除旧日报，再创建新日报
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        import json
        load_dotenv()
        username = current_user.get("username") or current_user.get("sub")
        employee_id = current_user.get("employee_id")
        token = get_user_token(username)

        # 安全检查：确保 employee_id 存在
        if not employee_id:
            logger.warning(f" 用户 {username} 缺少 employee_id，使用 username 作为标识")
            employee_id = username

        if not token:
            raise HTTPException(status_code=401, detail="未找到用户认证信息")

        # 先删除该日期的旧日报（智能体专用：支持覆盖）
        # 安全检查：同时匹配 employee_id 和 employee_name
        with get_connection() as conn:
            # 获取用户姓名
            user_name = current_user.get("name", "")
            
            # 查找旧日报（同时匹配 employee_id 和 employee_name）
            result = conn.execute(text("""
                SELECT id, employee_id, employee_name FROM daily_reports
                WHERE employee_id = :eid AND report_date = :date AND is_deleted = false
            """), {"eid": employee_id, "date": request.report_date})

            old_report = result.fetchone()

            if old_report:
                # 额外安全检查：确认日报属于当前用户
                if old_report[1] != employee_id:
                    logger.error(f" 日报归属检查失败：期望 {employee_id}，实际 {old_report[1]}")
                    raise HTTPException(status_code=403, detail="无权删除此日报")
                
                # 删除旧日报的工作项
                conn.execute(text("""
                    DELETE FROM daily_work_items WHERE report_id = :rid
                """), {"rid": old_report[0]})

                # 删除旧日报
                conn.execute(text("""
                    DELETE FROM daily_reports WHERE id = :rid
                """), {"rid": old_report[0]})

                conn.commit()
                logger.info(f" 已删除 {request.report_date} 的旧日报 (ID: {old_report[0]}, 用户: {old_report[2]})")

        # 调用主后端创建接口
        response = await http_client.post(
            f"{settings.BACKEND_API_URL}/api/v1/ai-daily/create-from-parse",
            json={
                "report_date": request.report_date,
                "work_items": request.work_items,
                "work_target": request.work_target,
                "tomorrow_plan": request.tomorrow_plan
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            data = result.get("data", result)
            report_id = data.get("report_id")

            # 保存原始输入和AI解析结果
            if report_id and (request.original_input or request.ai_parsed_data):
                with get_connection() as conn:
                    conn.execute(text("""
                        UPDATE daily_reports
                        SET original_input = :input,
                            ai_parsed_data = :parsed,
                            parse_mode = 'free',
                            status = '已提交'
                        WHERE id = :rid
                    """), {
                        "input": request.original_input,
                        "parsed": json.dumps(request.ai_parsed_data) if request.ai_parsed_data else None,
                        "rid": report_id
                    })
                    conn.commit()
            
            # 更新工作项的时间字段（从 ai_parsed_data 中读取）
            if report_id and request.ai_parsed_data:
                entries = request.ai_parsed_data.get('entries', [])
                if entries:
                    with get_connection() as conn:
                        # 获取该日报的所有工作项
                        work_items_result = conn.execute(text("""
                            SELECT id FROM daily_work_items 
                            WHERE report_id = :rid 
                            ORDER BY id
                        """), {"rid": report_id})
                        work_item_ids = [row[0] for row in work_items_result.fetchall()]
                        
                        # 按顺序更新时间
                        for idx, entry in enumerate(entries):
                            if idx < len(work_item_ids) and entry.get('start_time') and entry.get('end_time'):
                                conn.execute(text("""
                                    UPDATE daily_work_items 
                                    SET start_time = :start_time, end_time = :end_time
                                    WHERE id = :wid
                                """), {
                                    "start_time": entry['start_time'],
                                    "end_time": entry['end_time'],
                                    "wid": work_item_ids[idx]
                                })
                        conn.commit()
                        logger.info(f" 已更新 {min(len(entries), len(work_item_ids))} 个工作项的时间字段")

            # 更新任务进度
            try:
                import sys
                sys.path.insert(0, os.path.dirname(__file__))
                from task_auto import update_task_progress_from_daily
                updated_tasks = update_task_progress_from_daily(request.work_items)
                if updated_tasks:
                    logger.info(f"已更新 {len(updated_tasks)} 个任务进度: {updated_tasks}")
            except Exception as e:
                logger.error(f"更新任务进度失败（不影响日报保存）: {e}")
                import traceback
                traceback.print_exc()

            return {
                "success": True,
                "message": "日报创建成功",
                "report_id": report_id,
                "updated_tasks": len(updated_tasks) if 'updated_tasks' in locals() else 0
            }
        else:
            logger.error(f" {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"创建失败: {response.text}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@app.get("/api/agent/daily/my-reports")
async def get_my_daily_reports(
    page: int = 1,
    size: int = 10,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取我的日报列表 - 从本地数据库直接查询
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        username = current_user.get("username") or current_user.get("sub")
        employee_id = current_user.get("employee_id") or username

        with get_connection() as conn:
            # 获取日报列表
            offset = (page - 1) * size
            result = conn.execute(text("""
                SELECT dr.id, dr.report_date, dr.status,
                       to_char(dr.create_time, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                       COUNT(dwi.id) as item_count,
                       COALESCE(SUM(dwi.hours_spent), 0) as total_hours
                FROM daily_reports dr
                LEFT JOIN daily_work_items dwi ON dwi.report_id = dr.id
                WHERE dr.employee_id = :eid
                  AND dr.is_deleted = false
                GROUP BY dr.id, dr.report_date, dr.status, dr.create_time
                ORDER BY dr.report_date DESC
                LIMIT :size OFFSET :offset
            """), {"eid": employee_id, "size": size, "offset": offset})

            reports = []
            for row in result:
                report_id = row[0]

                # 获取工作项
                items_result = conn.execute(text("""
                    SELECT work_content, project_name, start_time, end_time,
                           hours_spent, task_id, task_name
                    FROM daily_work_items
                    WHERE report_id = :rid
                    ORDER BY project_name, id
                """), {"rid": report_id})

                items = []
                for item in items_result:
                    items.append({
                        "work_content": item[0] or "",
                        "project_name": item[1] or "",
                        "start_time": item[2] or "",  # 空值显示为空，不显示假时间
                        "end_time": item[3] or "",    # 空值显示为空
                        "hours_spent": float(item[4] or 0),
                        "task_id": item[5],
                        "task_name": item[6]
                    })

                # 获取原始输入和AI解析数据
                meta_result = conn.execute(text("""
                    SELECT original_input, ai_parsed_data
                    FROM daily_reports
                    WHERE id = :rid
                """), {"rid": report_id})
                meta_row = meta_result.fetchone()

                original_input = meta_row[0] if meta_row else None
                ai_parsed_data = meta_row[1] if meta_row and meta_row[1] else None

                reports.append({
                    "id": report_id,
                    "report_date": str(row[1]),
                    "total_hours": float(row[5] or 0),
                    "status": row[2] or "已提交",
                    "created_at": row[3],  # 已格式化为 'YYYY-MM-DD HH24:MI:SS'
                    "items": items,
                    "original_input": original_input,
                    "ai_parsed_data": ai_parsed_data,
                    "ai_parsed": len(items) > 0 and any(item.get("task_id") for item in items)
                })

            # 获取总数
            count_result = conn.execute(text("""
                SELECT COUNT(DISTINCT id) FROM daily_reports
                WHERE employee_id = :eid AND is_deleted = false
            """), {"eid": employee_id})
            total = count_result.fetchone()[0]

            return {
                "items": reports,
                "total": total,
                "page": page,
                "size": size
            }

    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        return {"items": [], "total": 0, "page": page, "size": size}

@app.post("/api/agent/auth/login")
@limiter.limit("5/minute")  # 防暴力破解：每分钟最多5次
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    登录接口 - 代理到现有后端认证

    用户名/密码与现有管理系统一致
    """
    try:
        # 调用现有后端登录接口
        response = await http_client.post(
            f"{settings.BACKEND_API_URL}/api/v1/auth/login",
            data={
                "username": form_data.username,
                "password": form_data.password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            logger.debug(f"后端返回: {data}")

            # 处理不同可能的返回格式
            response_data = data.get("data", data)

            token = (response_data.get("access_token") or
                    response_data.get("token"))

            user = response_data.get("user")

            if token:
                # 从 JWT 中解析用户标识作为 key
                try:
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    user_key = payload.get("sub") or form_data.username
                except:
                    user_key = form_data.username

                # 获取用户详细信息（包含角色）
                user_info = await get_user_info(token)
                logger.debug(f"用户信息: {user_info}")

                # 存储用户token和信息用于后续请求
                store_user_token(user_key, token, user_info)
                logger.debug(f"存储token: key={user_key}")

                return {
                    "access_token": token,
                    "token_type": "bearer",
                    "user": {
                        "id": user_info.get("employee_id"),
                        "name": user_info.get("name"),
                        "username": user_key,
                        "role_id": user_info.get("role_id")
                    }
                }
            else:
                return data
        else:
            error_data = response.json()
            detail = error_data.get("detail") or error_data.get("message") or "用户名或密码错误"
            raise HTTPException(
                status_code=401,
                detail=detail
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail="登录服务异常")


@app.get("/api/agent/auth/me")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """
    获取当前用户详细信息（含角色、部门、岗位）
    """
    try:
        username = current_user.get("username")

        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            # 从 users 表获取基本信息
            result = conn.execute(text("""
                SELECT id, username, role FROM users WHERE username = :username
            """), {"username": username}).fetchone()

            if result:
                current_user["id"] = result[0]
                current_user["role"] = result[2] or "user"

            # 从 personnel 表获取部门、岗位信息
            person_result = conn.execute(text("""
                SELECT name, department, position, phone, email
                FROM personnel
                WHERE employee_id = :username
            """), {"username": username}).fetchone()

            if person_result:
                current_user["name"] = person_result[0] or username
                current_user["department"] = person_result[1] or ""
                current_user["position"] = person_result[2] or ""
                current_user["phone"] = person_result[3] or ""
                current_user["email"] = person_result[4] or ""

        return current_user
    except Exception as e:
        logger.error(f" {e}")
        current_user["role"] = "user"
        return current_user


@app.post("/api/agent/auth/refresh")
async def refresh_token(current_user: Dict = Depends(get_current_user)):
    """
    刷新 Token - 调用现有后端获取新 token
    
    前端检测到 token 即将过期时自动调用
    """
    try:
        username = current_user.get("username") or current_user.get("sub")
        
        # 从存储中获取当前 token
        current_token = get_user_token(username)
        if not current_token:
            raise HTTPException(status_code=401, detail="未找到登录状态")
        
        # 调用现有后端的 refresh 接口获取新 token
        try:
            response = await http_client.post(
                f"{settings.BACKEND_API_URL}/api/v1/auth/refresh",
                headers={"Authorization": f"Bearer {current_token}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("data", {}).get("access_token") or data.get("access_token")
                
                if new_token:
                    # 更新本地缓存的 token
                    store_user_token(username, new_token)
                    
                    # 获取用户信息
                    user_info = await get_user_info(new_token)
                    
                    return {
                        "access_token": new_token,
                        "token_type": "bearer",
                        "user": {
                            "id": user_info.get("employee_id"),
                            "name": user_info.get("name"),
                            "username": username,
                            "role_id": user_info.get("role_id")
                        }
                    }
                else:
                    logger.exception(f" {data}")
            else:
                logger.warning(f" 刷新失败，状态码: {response.status_code}")
                # 如果现有后端返回 401，说明 token 完全失效，需要重新登录
                if response.status_code == 401:
                    raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
        except httpx.HTTPError as e:
            logger.error(f" {e}")
        
        # 如果刷新失败，尝试返回当前 token（降级处理）
        user_info = await get_user_info(current_token)
        return {
            "access_token": current_token,
            "token_type": "bearer",
            "user": {
                "id": user_info.get("employee_id"),
                "name": user_info.get("name"),
                "username": username,
                "role_id": user_info.get("role_id")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")


@app.put("/api/agent/auth/push-token")
async def update_push_token(
    push_token: str = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    更新用户的微信推送Token
    
    请求体：
    {
        "push_token": "your_pushplus_token"
    }
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        from pydantic import BaseModel
        load_dotenv()
        
        # 定义请求体模型
        class PushTokenRequest(BaseModel):
            push_token: str        
        username = current_user.get("username")
        
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE users SET push_token = :token WHERE username = :username
            """), {"token": push_token, "username": username})
            conn.commit()
        
        return {"success": True, "message": "推送Token已更新"}
    
    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


def require_role(allowed_roles: List[str]):
    """角色权限检查装饰器"""
    async def role_checker(current_user: Dict = Depends(get_current_user)):
        # 先从数据库获取用户角色
        username = current_user.get("username")

        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT role FROM users WHERE username = :username
            """), {"username": username}).fetchone()

            user_role = result[0] if result else "user"

        # 同时检查 role_id（兼容旧系统）
        user_info = get_user_info_cache(username)
        role_id = user_info.get("role_id") if user_info else None

        # admin 判断：role=admin 或 role_id=11
        if "admin" in allowed_roles and (user_role == "admin" or role_id == 11):
            return current_user

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：需要 {allowed_roles} 角色"
            )
        return current_user
    return role_checker


@app.get("/api/agent/work-hours/stats")
async def get_work_hours_stats(current_user: Dict = Depends(get_current_user)):
    """
    获取工时统计数据

    返回：今日、本周、本月工时，项目工时分布
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        # 获取用户信息
        user_info = get_user_info_cache(username)
        employee_id = user_info.get("employee_id") if user_info else username

        # 计算日期范围
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())  # 本周一
        month_start = today.replace(day=1)  # 本月1号

        # 直接从数据库查询（更准确）
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            # 今日工时
            result = conn.execute(text("""
                SELECT COALESCE(SUM(hours_spent), 0) as hours
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                WHERE dr.employee_id = :emp_id
                AND dr.report_date = :today
                AND dr.is_deleted = false
            """), {"emp_id": employee_id, "today": today})
            today_hours = float(result.fetchone()[0] or 0)

            # 本周工时
            result = conn.execute(text("""
                SELECT COALESCE(SUM(hours_spent), 0) as hours
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                WHERE dr.employee_id = :emp_id
                AND dr.report_date >= :week_start
                AND dr.report_date <= :today
                AND dr.is_deleted = false
            """), {"emp_id": employee_id, "week_start": week_start, "today": today})
            week_hours = float(result.fetchone()[0] or 0)

            # 本月工时及项目分布
            # 使用 NULLIF 将空字符串转为 NULL，再用 COALESCE 替换为"其他工作"
            # "其他工作"按顺序放在最后一位
            result = conn.execute(text("""
                SELECT
                    COALESCE(NULLIF(TRIM(dwi.project_name), ''), '其他工作') as project_name,
                    SUM(dwi.hours_spent) as hours
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                WHERE dr.employee_id = :emp_id
                AND dr.report_date >= :month_start
                AND dr.report_date <= :today
                AND dr.is_deleted = false
                GROUP BY COALESCE(NULLIF(TRIM(dwi.project_name), ''), '其他工作')
                ORDER BY 
                    CASE WHEN COALESCE(NULLIF(TRIM(dwi.project_name), ''), '其他工作') = '其他工作' THEN 1 ELSE 0 END,
                    hours DESC
                LIMIT 5
            """), {"emp_id": employee_id, "month_start": month_start, "today": today})

            project_hours = {}
            month_total = 0
            for row in result:
                name = row[0]
                hours = float(row[1] or 0)
                project_hours[name] = hours
                month_total += hours

        # 计算项目工时分布
        project_distribution = []
        for name, hours in sorted(project_hours.items(), key=lambda x: -x[1]):
            percent = round(hours / month_total * 100) if month_total > 0 else 0
            project_distribution.append({
                "name": name,
                "hours": round(hours, 1),
                "percent": percent
            })

        return {
            "today": round(today_hours, 1),
            "week": round(week_hours, 1),
            "month": round(month_total, 1),
            "projects": project_distribution
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "today": 0,
            "week": 0,
            "month": 0,
            "projects": []
        }


# ============== 今日聚焦看板 API ==============

@app.get("/api/agent/dashboard/today-focus")
async def get_today_focus(current_user: Dict = Depends(get_current_user)):
    """
    获取今日聚焦数据

    返回：
    - today_tasks: 今日待办任务
    - delayed_tasks: 延期任务
    - month_goals: 本月目标进度
    - daily_report_status: 日报填报状态
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        # 获取用户信息
        user_info = get_user_info_cache(username)
        employee_id = user_info.get("employee_id") if user_info else username
        employee_name = user_info.get("name") if user_info else username

        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()
        current_month = today.strftime("%Y-%m")

        with get_connection() as conn:
            # 1. 今日待办任务（截止日期在今天）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       pt.start_date, pt.end_date, pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.end_date = :today
                  AND pt.actual_end_date IS NULL
                ORDER BY pt.end_date
                LIMIT 10
            """), {"emp_id": employee_id, "today": today})

            today_tasks = []
            for row in result:
                today_tasks.append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_id": row[2],
                    "project_name": row[3],
                    "start_date": str(row[4]) if row[4] else None,
                    "end_date": str(row[5]) if row[5] else None,
                    "status": row[6],
                    "progress": float(row[7] or 0)
                })

            # 2. 延期任务（已超期未完成）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       pt.start_date, pt.end_date,
                       CURRENT_DATE - pt.end_date as delay_days,
                       pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                ORDER BY delay_days DESC
                LIMIT 5
            """), {"emp_id": employee_id})

            delayed_tasks = []
            for row in result:
                delayed_tasks.append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_id": row[2],
                    "project_name": row[3],
                    "start_date": str(row[4]) if row[4] else None,
                    "end_date": str(row[5]) if row[5] else None,
                    "delay_days": row[6],
                    "status": row[7],
                    "progress": float(row[8] or 0)
                })

            # 3. 本月目标进度 - 从项目计划中自动获取（只取最新版本）
            from datetime import timedelta
            month_start = today.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            month_goals = []

            # 获取本月要开始的任务（计划开始日期在本月）- 只取最新版本
            month_start_result = conn.execute(text("""
                WITH latest_tasks AS (
                    SELECT pt.*,
                           CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) as version,
                           MAX(CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER)) OVER (
                               PARTITION BY pt.project_id, SUBSTRING(pt.task_id FROM 'T[0-9]+$')
                           ) as max_version
                    FROM project_tasks pt
                    JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                    WHERE pt.is_deleted = false
                      AND p.is_deleted = false
                      AND (pt.assignee_id = :emp_id OR p.leader = :emp_name OR p.leader = :username)
                )
                SELECT task_id, task_name, start_date, end_date, progress, status
                FROM latest_tasks
                WHERE version = max_version
                  AND start_date >= :month_start
                  AND start_date <= :month_end
                ORDER BY start_date
            """), {"emp_id": employee_id, "emp_name": employee_name, "username": username, "month_start": month_start, "month_end": month_end})

            for row in month_start_result:
                month_goals.append({
                    "id": f"start_{row[0]}",
                    "title": f"🚀 {row[1]}",
                    "progress_rate": float(row[4] or 0),
                    "status": row[5],
                    "type": "本月启动",
                    "date": str(row[2]) if row[2] else None,
                    "end_date": str(row[3]) if row[3] else None
                })

            # 获取本月要完成的任务（计划结束日期在本月）- 只取最新版本
            month_end_result = conn.execute(text("""
                WITH latest_tasks AS (
                    SELECT pt.*,
                           CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) as version,
                           MAX(CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER)) OVER (
                               PARTITION BY pt.project_id, SUBSTRING(pt.task_id FROM 'T[0-9]+$')
                           ) as max_version
                    FROM project_tasks pt
                    JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                    WHERE pt.is_deleted = false
                      AND p.is_deleted = false
                      AND (pt.assignee_id = :emp_id OR p.leader = :emp_name OR p.leader = :username)
                )
                SELECT task_id, task_name, start_date, end_date, progress, status
                FROM latest_tasks
                WHERE version = max_version
                  AND end_date >= :month_start
                  AND end_date <= :month_end
                  AND status != '已完成'
                ORDER BY end_date
            """), {"emp_id": employee_id, "emp_name": employee_name, "username": username, "month_start": month_start, "month_end": month_end})

            for row in month_end_result:
                # 避免重复（如果一个任务既在本月开始又在本月结束，只显示一次）
                existing = next((g for g in month_goals if g["id"] == f"end_{row[0]}"), None)
                if not existing:
                    month_goals.append({
                        "id": f"end_{row[0]}",
                        "title": f"🎯 {row[1]}",
                        "progress_rate": float(row[4] or 0),
                        "status": row[5],
                        "type": "本月完成",
                        "date": str(row[2]) if row[2] else None,
                        "end_date": str(row[3]) if row[3] else None
                    })

            # 4. 今日日报填报状态
            result = conn.execute(text("""
                SELECT id, report_date, status
                FROM daily_reports
                WHERE is_deleted = false
                  AND employee_id = :emp_id
                  AND report_date = :today
                LIMIT 1
            """), {"emp_id": employee_id, "today": today})

            daily_report_row = result.fetchone()
            daily_report_status = {
                "submitted": daily_report_row is not None,
                "report_id": daily_report_row[0] if daily_report_row else None,
                "status": daily_report_row[2] if daily_report_row else None
            }

            # 5. 本周工作概览
            week_start = today - timedelta(days=today.weekday())
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT dr.id) as report_count,
                    COALESCE(SUM(dwi.hours_spent), 0) as total_hours,
                    COUNT(DISTINCT dwi.project_id) as project_count
                FROM daily_reports dr
                LEFT JOIN daily_work_items dwi ON dr.id = dwi.report_id
                WHERE dr.is_deleted = false
                  AND dr.employee_id = :emp_id
                  AND dr.report_date >= :week_start
                  AND dr.report_date <= :today
            """), {"emp_id": employee_id, "week_start": week_start, "today": today})

            week_row = result.fetchone()
            week_overview = {
                "report_count": week_row[0] if week_row else 0,
                "total_hours": float(week_row[1] or 0) if week_row else 0,
                "project_count": week_row[2] if week_row else 0
            }

        return {
            "today_tasks": today_tasks,
            "delayed_tasks": delayed_tasks,
            "month_goals": month_goals,
            "daily_report_status": daily_report_status,
            "week_overview": week_overview,
            "date": today.isoformat(),
            "employee_name": employee_name
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "today_tasks": [],
            "delayed_tasks": [],
            "month_goals": [],
            "daily_report_status": {"submitted": False},
            "week_overview": {"report_count": 0, "total_hours": 0, "project_count": 0},
            "date": datetime.now().date().isoformat(),
            "employee_name": ""
        }


@app.get("/api/agent/dashboard/risk-alerts")
async def get_risk_alerts(current_user: Dict = Depends(get_current_user)):
    """
    获取风险预警数据（管理员视角）

    返回：
    - delayed_projects: 延期项目列表
    - unreported_users: 今日未填报人员
    - high_risk_projects: 高风险项目
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        user_info = get_user_info_cache(username)
        role_id = user_info.get("role_id") if user_info else None

        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        with get_connection() as conn:
            # 1. 延期任务统计（按项目）
            result = conn.execute(text("""
                SELECT p.id, p.name, p.leader,
                       COUNT(*) as delayed_count,
                       MAX(CURRENT_DATE - pt.end_date) as max_delay_days
                FROM projects p
                JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE p.is_deleted = false
                  AND pt.is_deleted = false
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                GROUP BY p.id, p.name, p.leader
                ORDER BY delayed_count DESC
                LIMIT 10
            """))

            delayed_projects = []
            for row in result:
                delayed_projects.append({
                    "project_id": row[0],
                    "project_name": row[1],
                    "leader": row[2],
                    "delayed_count": row[3],
                    "max_delay_days": row[4]
                })

            # 2. 今日未填报人员（仅管理员可见）
            unreported_users = []
            if role_id == 11:  # 系统管理员
                result = conn.execute(text("""
                    SELECT p.employee_id, p.name, p.department
                    FROM personnel p
                    WHERE p.is_deleted = false
                      AND p.role_id IN (13, 14)
                      AND p.employee_id NOT IN (
                          SELECT DISTINCT employee_id
                          FROM daily_reports
                          WHERE report_date = :today AND is_deleted = false
                      )
                    ORDER BY p.name
                    LIMIT 20
                """), {"today": today})

                for row in result:
                    unreported_users.append({
                        "employee_id": row[0],
                        "name": row[1],
                        "department": row[2]
                    })

            # 3. 高风险项目（延期率>30%）
            result = conn.execute(text("""
                SELECT p.id, p.name, p.leader,
                       COUNT(pt.task_id) as total_tasks,
                       SUM(CASE WHEN pt.end_date < CURRENT_DATE
                                AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END) as delayed_tasks,
                       ROUND(100.0 * SUM(CASE WHEN pt.end_date < CURRENT_DATE
                                              AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END)
                             / NULLIF(COUNT(pt.task_id), 0), 1) as delay_rate
                FROM projects p
                JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE p.is_deleted = false
                  AND pt.is_deleted = false
                GROUP BY p.id, p.name, p.leader
                HAVING 100.0 * SUM(CASE WHEN pt.end_date < CURRENT_DATE
                                        AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END)
                       / NULLIF(COUNT(pt.task_id), 0) > 30
                ORDER BY delay_rate DESC
                LIMIT 5
            """))

            high_risk_projects = []
            for row in result:
                high_risk_projects.append({
                    "project_id": row[0],
                    "project_name": row[1],
                    "leader": row[2],
                    "total_tasks": row[3],
                    "delayed_tasks": row[4],
                    "delay_rate": float(row[5] or 0)
                })

        return {
            "delayed_projects": delayed_projects,
            "unreported_users": unreported_users,
            "high_risk_projects": high_risk_projects,
            "is_admin": role_id == 11
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "delayed_projects": [],
            "unreported_users": [],
            "high_risk_projects": [],
            "is_admin": False
        }


@app.get("/api/agent/dashboard/my-project-risks")
async def get_my_project_risks(current_user: Dict = Depends(get_current_user)):
    """
    获取我负责的项目风险预警

    返回用户作为项目负责人的所有项目的风险信息
    """
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username

    if not employee_id:
        return []

    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    with get_connection() as conn:
        # 先通过 employee_id 查询员工信息（包括内部 id）
        emp_result = conn.execute(text("""
            SELECT id, name FROM personnel 
            WHERE employee_id = :emp_id AND is_deleted = false
            LIMIT 1
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[1] if emp_row else None
        personnel_id = emp_row[0] if emp_row else None  # personnel 表的内部 id

        # 查询用户负责的项目（通过 leader 字段匹配姓名或 leader_id 匹配 personnel.id）
        if personnel_id:
            result = conn.execute(text("""
                SELECT
                    p.id as project_id,
                    p.name as project_name,
                    p.leader
                FROM projects p
                WHERE p.is_deleted = false
                  AND (p.leader = :emp_name OR p.leader_id = :pid)
                ORDER BY p.id
            """), {"emp_name": employee_name or "", "pid": personnel_id})
        else:
            result = conn.execute(text("""
                SELECT
                    p.id as project_id,
                    p.name as project_name,
                    p.leader
                FROM projects p
                WHERE p.is_deleted = false
                  AND p.leader = :emp_name
                ORDER BY p.id
            """), {"emp_name": employee_name or ""})

        risks = []
        for row in result:
            project_id = row[0]

            # 查询最新版本的任务列表
            # 分类逻辑：
            # - completed: 按时完成（actual_end_date <= end_date）
            # - delayed_completed: 延期完成（actual_end_date > end_date）
            # - ongoing: 进行中（start_date <= 今天 <= end_date，未完成）
            # - delayed: 延期未完成（end_date < 今天，未完成）
            # - not_started: 未开始（start_date > 今天）
            tasks_result = conn.execute(text("""
                WITH max_ver AS (
                    SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as mv
                    FROM project_tasks
                    WHERE CAST(project_id AS INTEGER) = :project_id AND is_deleted = false
                )
                SELECT
                    task_id, task_name, status, progress, start_date, end_date, actual_end_date, assignee_id,
                    CASE
                        WHEN actual_end_date IS NOT NULL AND actual_end_date > end_date THEN actual_end_date - end_date
                        WHEN end_date < CURRENT_DATE AND actual_end_date IS NULL THEN CURRENT_DATE - end_date
                        ELSE 0
                    END as delay_days,
                    CASE
                        WHEN actual_end_date IS NOT NULL AND actual_end_date > end_date THEN 'delayed_completed'
                        WHEN actual_end_date IS NOT NULL AND actual_end_date <= end_date THEN 'completed'
                        WHEN end_date < CURRENT_DATE AND actual_end_date IS NULL THEN 'delayed'
                        WHEN start_date IS NOT NULL AND start_date <= CURRENT_DATE AND actual_end_date IS NULL THEN 'ongoing'
                        ELSE 'not_started'
                    END as task_status
                FROM project_tasks, max_ver
                WHERE CAST(project_id AS INTEGER) = :project_id
                  AND is_deleted = false
                  AND COALESCE(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER), 0) = COALESCE(max_ver.mv, 0)
            """), {"project_id": project_id})

            tasks = {"completed": [], "delayed_completed": [], "ongoing": [], "delayed": [], "not_started": []}

            for task in tasks_result:
                task_data = {
                    "task_id": task[0], "task_name": task[1], "status": task[2],
                    "progress": float(task[3] or 0),
                    "start_date": str(task[4]) if task[4] else None,
                    "end_date": str(task[5]) if task[5] else None,
                    "actual_end_date": str(task[6]) if task[6] else None,
                    "assignee_id": task[7], "delay_days": task[8] or 0,
                    "task_status": task[9] or 'ongoing'
                }
                status = task_data["task_status"]
                if status in tasks:
                    tasks[status].append(task_data)

            total_tasks = sum(len(tasks[k]) for k in tasks)
            delayed_count = len(tasks["delayed"]) + len(tasks["delayed_completed"])
            completed_count = len(tasks["completed"]) + len(tasks["delayed_completed"])
            all_tasks = [t for k in tasks for t in tasks[k]]
            avg_progress = sum(t["progress"] for t in all_tasks) / total_tasks if total_tasks > 0 else 0
            project_progress = round((completed_count / total_tasks * 100 + avg_progress) / 2, 1) if total_tasks > 0 else 0

            risks.append({
                "project_id": row[0], "project_name": row[1], "leader": row[2],
                "total_tasks": total_tasks, "progress": project_progress,
                "delayed_tasks": len(tasks["delayed"]), "delayed_count": delayed_count,
                "tasks": tasks
            })

        return risks


@app.get("/api/agent/stats/team-work-hours")
async def get_team_work_hours(current_user: Dict = Depends(get_current_user)):
    """
    获取团队工时统计（项目负责人视角）

    返回用户负责的项目下所有成员的工时分布
    """
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username

    if not employee_id:
        return []

    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    # 获取本月第一天和最后一天
    today = datetime.now().date()
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    with get_connection() as conn:
        # 查询员工姓名
        emp_result = conn.execute(text("""
            SELECT name FROM personnel 
            WHERE employee_id = :emp_id AND is_deleted = false
            LIMIT 1
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[0] if emp_row else None

        # 查询用户负责的项目
        projects_result = conn.execute(text("""
            SELECT id, name FROM projects
            WHERE is_deleted = false AND leader = :emp_name
        """), {"emp_name": employee_name or ""})

        project_ids = [row[0] for row in projects_result]
        if not project_ids:
            return []

        # 查询这些项目下所有成员的工时
        result = conn.execute(text("""
            SELECT
                p.name as project_name,
                per.name as member_name,
                SUM(dwi.hours_spent) as total_hours
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            JOIN personnel per ON per.employee_id = dr.employee_id
            JOIN projects p ON dwi.project_name LIKE '%' || p.name || '%'
            WHERE p.id = ANY(:project_ids)
              AND dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
            GROUP BY p.name, per.name
            ORDER BY p.name, total_hours DESC
        """), {
            "project_ids": project_ids,
            "month_start": month_start,
            "month_end": month_end
        })

        # 按项目分组
        project_hours = {}
        for row in result:
            project_name = row[0]
            member_name = row[1]
            hours = float(row[2] or 0)

            if project_name not in project_hours:
                project_hours[project_name] = {
                    "project_name": project_name,
                    "members": [],
                    "total_hours": 0
                }

            project_hours[project_name]["members"].append({
                "name": member_name,
                "hours": round(hours, 1),
                "percent": 0  # 稍后计算
            })
            project_hours[project_name]["total_hours"] += hours

        # 计算百分比
        result_list = []
        for project_data in project_hours.values():
            total = project_data["total_hours"]
            for member in project_data["members"]:
                member["percent"] = round(100 * member["hours"] / total, 1) if total > 0 else 0
            project_data["total_hours"] = round(total, 1)
            result_list.append(project_data)

        return result_list


# ============== Phase 14: 数据可视化 API ==============

@app.get("/api/agent/dashboard/project-board")
async def get_project_board(current_user: Dict = Depends(get_current_user)):
    """
    获取项目看板数据

    返回所有项目的进度、风险等级、延期任务数
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        user_info = get_user_info_cache(username)

        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            # 获取项目列表及风险评分
            result = conn.execute(text("""
                SELECT p.id, p.name, p.leader, p.status, p.progress,
                       COUNT(pt.task_id) as total_tasks,
                       SUM(CASE WHEN pt.end_date < CURRENT_DATE
                                AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END) as delayed_tasks
                FROM projects p
                LEFT JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                    AND pt.is_deleted = false
                WHERE p.is_deleted = false
                GROUP BY p.id, p.name, p.leader, p.status, p.progress
                ORDER BY p.id DESC
            """))

            projects = []
            for row in result:
                total = row[5] or 0
                delayed = row[6] or 0

                # 计算风险等级
                if total > 0:
                    delay_rate = delayed / total * 100
                    if delay_rate > 30:
                        risk_level = "high"
                    elif delay_rate > 15:
                        risk_level = "medium"
                    else:
                        risk_level = "low"
                else:
                    risk_level = "low"

                projects.append({
                    "id": row[0],
                    "name": row[1],
                    "leader": row[2],
                    "status": row[3] or "进行中",
                    "progress": float(row[4] or 0),
                    "risk_level": risk_level,
                    "delayed_tasks": delayed,
                    "total_tasks": total
                })

            return {"projects": projects}

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {"projects": []}


@app.get("/api/agent/dashboard/risk-matrix")
async def get_risk_matrix(current_user: Dict = Depends(get_current_user)):
    """
    获取风险矩阵数据

    返回所有项目的进度风险、资源风险、综合风险
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT p.id, p.name,
                       COUNT(pt.task_id) as total_tasks,
                       SUM(CASE WHEN pt.end_date < :today AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END) as delayed_tasks,
                       COUNT(DISTINCT pt.assignee_id) as team_size,
                       SUM(COALESCE(pt.planned_hours, 0)) as planned_hours
                FROM projects p
                LEFT JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                    AND pt.is_deleted = false
                WHERE p.is_deleted = false
                GROUP BY p.id, p.name
                ORDER BY p.id
            """), {"today": today})

            projects = []
            for row in result:
                total = row[2] or 0
                delayed = row[3] or 0
                team_size = row[4] or 1
                planned_hours = float(row[5] or 0)

                # 进度风险
                if total > 0:
                    schedule_risk = min(100, delayed / total * 100)
                else:
                    schedule_risk = 0

                # 资源风险（简单估算：团队规模 vs 任务量）
                if team_size > 0 and total > 0:
                    tasks_per_person = total / team_size
                    resource_risk = min(100, tasks_per_person * 10)  # 每人超过10个任务开始计风险
                else:
                    resource_risk = 0

                # 综合风险
                overall_risk = (schedule_risk * 0.6 + resource_risk * 0.4)

                projects.append({
                    "project_id": row[0],
                    "project_name": row[1],
                    "schedule_risk": round(schedule_risk, 1),
                    "resource_risk": round(resource_risk, 1),
                    "overall_risk": round(overall_risk, 1)
                })

            return {"projects": projects}

    except Exception as e:
        logger.error(f" {e}")
        return {"projects": []}


# ============== Phase 15: 智能推荐 API ==============

@app.get("/api/agent/dashboard/smart-assistant")
async def get_smart_assistant(current_user: Dict = Depends(get_current_user)):
    """
    智能助手 - 整合今日优先任务 + 延期预警 + 工时预测 + 智能建议

    返回用户登录后应该看到的所有关键信息
    """
    # 直接从 current_user 获取 employee_id
    employee_id = current_user.get("username")

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        result_data = {
            "priority_tasks": [],      # 今日优先任务（排序后）
            "delayed_warnings": [],    # 延期预警
            "hours_prediction": {},    # 工时预测
            "suggestions": [],         # 智能建议
            "daily_report_status": {}  # 日报状态
        }

        with get_connection() as conn:
            # 1. 今日优先任务（按紧急程度排序）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       pt.end_date, pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.actual_end_date IS NULL
                  AND pt.end_date <= CURRENT_DATE + INTERVAL '3 days'
                ORDER BY
                    CASE WHEN pt.end_date < CURRENT_DATE THEN 0
                         WHEN pt.end_date = CURRENT_DATE THEN 1
                         ELSE 2 END,
                    pt.end_date
                LIMIT 5
            """), {"emp_id": employee_id})

            for row in result:
                end_date = row[4]
                is_delayed = end_date < today if end_date else False
                is_today = end_date == today if end_date else False

                # 计算紧急程度
                if is_delayed:
                    urgency = "urgent"
                    urgency_label = "🔴 延期"
                elif is_today:
                    urgency = "high"
                    urgency_label = "🟠 今日截止"
                else:
                    urgency = "medium"
                    urgency_label = "🟡 即将到期"

                result_data["priority_tasks"].append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_id": row[2],
                    "project_name": row[3],
                    "end_date": str(end_date) if end_date else None,
                    "status": row[5],
                    "progress": float(row[6] or 0),
                    "urgency": urgency,
                    "urgency_label": urgency_label,
                    "suggestion": _get_task_suggestion(urgency, row[6] or 0)
                })

            # 2. 延期预警（详细）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       CURRENT_DATE - pt.end_date as delay_days,
                       pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                ORDER BY delay_days DESC
                LIMIT 5
            """), {"emp_id": employee_id})

            for row in result:
                result_data["delayed_warnings"].append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_name": row[3],
                    "delay_days": row[4],
                    "progress": float(row[6] or 0),
                    "suggestion": f"已延期{row[4]}天，建议立即处理或申请延期"
                })

            # 移除工时预测
            result_data["hours_prediction"] = {}

            # 4. 日报状态
            result = conn.execute(text("""
                SELECT id, status FROM daily_reports
                WHERE employee_id = :emp_id
                  AND is_deleted = false
                  AND report_date = :today
                LIMIT 1
            """), {"emp_id": employee_id, "today": today})

            report_row = result.fetchone()
            if report_row:
                result_data["daily_report_status"] = {
                    "submitted": True,
                    "report_id": report_row[0],
                    "status": report_row[1]
                }
            else:
                result_data["daily_report_status"] = {
                    "submitted": False,
                    "suggestion": "今日日报尚未填报"
                }

            # 5. 智能建议（综合）
            suggestions = []

            if result_data["delayed_warnings"]:
                suggestions.append({
                    "type": "delayed",
                    "priority": 1,
                    "message": f"您有 {len(result_data['delayed_warnings'])} 项任务延期，建议优先处理"
                })

            if not result_data["daily_report_status"].get("submitted"):
                suggestions.append({
                    "type": "report",
                    "priority": 2,
                    "message": "今日日报尚未填报，建议下午 5 点前完成"
                })

            # 移除工时预警建议

            if result_data["priority_tasks"]:
                urgent_count = sum(1 for t in result_data["priority_tasks"] if t["urgency"] == "urgent")
                if urgent_count > 0:
                    suggestions.append({
                        "type": "urgent",
                        "priority": 0,
                        "message": f"有 {urgent_count} 项紧急任务，建议立即处理"
                    })

            result_data["suggestions"] = sorted(suggestions, key=lambda x: x["priority"])

        return result_data

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "priority_tasks": [],
            "delayed_warnings": [],
            "hours_prediction": {},
            "suggestions": [],
            "daily_report_status": {}
        }


def _get_task_suggestion(urgency: str, progress: float) -> str:
    """根据紧急程度和进度生成建议"""
    if urgency == "urgent":
        if progress < 30:
            return "建议立即启动，必要时申请资源支持"
        else:
            return "建议优先完成，如遇阻塞及时上报"
    elif urgency == "high":
        if progress < 50:
            return "建议上午完成，预留下午评审时间"
        else:
            return "继续保持，今日可完成"
    else:
        return "合理安排时间，按计划推进"


@app.get("/api/agent/dashboard/smart-assistant")
async def get_smart_assistant(current_user: Dict = Depends(get_current_user)):
    """
    智能助手 - 整合今日优先任务 + 延期预警 + 工时预测 + 智能建议

    返回用户登录后应该看到的所有关键信息
    """
    # 直接从 current_user 获取 employee_id
    employee_id = current_user.get("username")

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        result_data = {
            "priority_tasks": [],      # 今日优先任务（排序后）
            "delayed_warnings": [],    # 延期预警
            "hours_prediction": {},    # 工时预测
            "suggestions": [],         # 智能建议
            "daily_report_status": {}  # 日报状态
        }

        with get_connection() as conn:
            # 1. 今日优先任务（按紧急程度排序）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       pt.end_date, pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.actual_end_date IS NULL
                  AND pt.end_date <= CURRENT_DATE + INTERVAL '3 days'
                ORDER BY
                    CASE WHEN pt.end_date < CURRENT_DATE THEN 0
                         WHEN pt.end_date = CURRENT_DATE THEN 1
                         ELSE 2 END,
                    pt.end_date
                LIMIT 5
            """), {"emp_id": employee_id})

            for row in result:
                end_date = row[4]
                is_delayed = end_date < today if end_date else False
                is_today = end_date == today if end_date else False

                # 计算紧急程度
                if is_delayed:
                    urgency = "urgent"
                    urgency_label = "🔴 延期"
                elif is_today:
                    urgency = "high"
                    urgency_label = "🟠 今日截止"
                else:
                    urgency = "medium"
                    urgency_label = "🟡 即将到期"

                result_data["priority_tasks"].append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_id": row[2],
                    "project_name": row[3],
                    "end_date": str(end_date) if end_date else None,
                    "status": row[5],
                    "progress": float(row[6] or 0),
                    "urgency": urgency,
                    "urgency_label": urgency_label,
                    "suggestion": _get_task_suggestion(urgency, row[6] or 0)
                })

            # 2. 延期预警（详细）
            result = conn.execute(text("""
                SELECT pt.task_id, pt.task_name, pt.project_id, p.name as project_name,
                       CURRENT_DATE - pt.end_date as delay_days,
                       pt.status, pt.progress
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND p.is_deleted = false
                  AND pt.assignee_id = :emp_id
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                ORDER BY delay_days DESC
                LIMIT 5
            """), {"emp_id": employee_id})

            for row in result:
                result_data["delayed_warnings"].append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "project_name": row[3],
                    "delay_days": row[4],
                    "progress": float(row[6] or 0),
                    "suggestion": f"已延期{row[4]}天，建议立即处理或申请延期"
                })

            # 移除工时预测
            result_data["hours_prediction"] = {}
            # 4. 日报状态
            result = conn.execute(text("""
                SELECT id, status FROM daily_reports
                WHERE employee_id = :emp_id
                  AND is_deleted = false
                  AND report_date = :today
                LIMIT 1
            """), {"emp_id": employee_id, "today": today})

            report_row = result.fetchone()
            if report_row:
                result_data["daily_report_status"] = {
                    "submitted": True,
                    "report_id": report_row[0],
                    "status": report_row[1]
                }
            else:
                result_data["daily_report_status"] = {
                    "submitted": False,
                    "suggestion": "今日日报尚未填报"
                }

            # 5. 智能建议（综合）
            suggestions = []

            if result_data["delayed_warnings"]:
                suggestions.append({
                    "type": "delayed",
                    "priority": 1,
                    "message": f"您有 {len(result_data['delayed_warnings'])} 项任务延期，建议优先处理"
                })

            if not result_data["daily_report_status"].get("submitted"):
                suggestions.append({
                    "type": "report",
                    "priority": 2,
                    "message": "今日日报尚未填报，建议下午 5 点前完成"
                })

            # 移除工时预警
            # if is_warning:
            #     suggestions.append({
            #         "type": "hours",
            #         "priority": 3,
            #         "message": f"本月工时预计 {int(predicted_hours)}h，接近预警线"
            #     })

            if result_data["priority_tasks"]:
                urgent_count = sum(1 for t in result_data["priority_tasks"] if t["urgency"] == "urgent")
                if urgent_count > 0:
                    suggestions.append({
                        "type": "urgent",
                        "priority": 0,
                        "message": f"有 {urgent_count} 项紧急任务，建议立即处理"
                    })

            # 6. 进度和成本预警
            # 查询用户负责的项目进度和成本情况
            result = conn.execute(text("""
                SELECT p.id, p.name, p.progress, p.start_date, p.end_date,
                       p.budget_total_cost, p.actual_total_cost
                FROM projects p
                WHERE p.is_deleted = false
                  AND p.leader_id = :emp_id
                  AND p.status = '进行中'
            """), {"emp_id": employee_id})

            for row in result:
                pid = row[0]
                pname = row[1]
                pprogress = float(row[2] or 0)
                pstart = row[3]
                pend = row[4]
                pbudget = float(row[5] or 0)
                pactual = float(row[6] or 0)

                # 计算计划进度
                if pstart and pend:
                    from datetime import datetime as dt_cls
                    start_dt = pstart if isinstance(pstart, date) else dt_cls.strptime(str(pstart), '%Y-%m-%d').date()
                    end_dt = pend if isinstance(pend, date) else dt_cls.strptime(str(pend), '%Y-%m-%d').date()
                    total_d = (end_dt - start_dt).days
                    elapsed_d = (today - start_dt).days
                    planned_pct = round(elapsed_d / total_d * 100, 1) if total_d > 0 else 0
                else:
                    planned_pct = 0

                # 进度滞后预警
                if pprogress < planned_pct - 10:
                    lag_amt = planned_pct - pprogress
                    suggestions.append({
                        "type": "progress",
                        "priority": 2,
                        "message": f"【{pname}】进度滞后 {lag_amt:.1f}%，建议加快推进"
                    })

                # 成本超支预警
                if pbudget > 0 and pactual > pbudget:
                    over_pct = (pactual - pbudget) / pbudget * 100
                    suggestions.append({
                        "type": "cost",
                        "priority": 2,
                        "message": f"【{pname}】成本超支 {over_pct:.1f}%，请注意控制"
                    })

            result_data["suggestions"] = sorted(suggestions, key=lambda x: x["priority"])

        return result_data

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "priority_tasks": [],
            "delayed_warnings": [],
            "hours_prediction": {},
            "suggestions": [],
            "daily_report_status": {}
        }


@app.get("/api/agent/stats/hours-trend")
async def get_hours_trend(
    time_range: str = "week",
    current_user: Dict = Depends(get_current_user)
):
    """
    获取工时趋势数据

    Args:
        time_range: week 或 month
    """
    # 直接从 current_user 获取 employee_id
    employee_id = current_user.get("username")  # username 就是 employee_id
    logger.debug(f" hours_trend: employee_id={employee_id}, time_range={time_range}")

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        if time_range == "week":
            days = 7
        else:
            days = 30

        start_date = today - timedelta(days=days-1)
        logger.debug(f" today={today}, start_date={start_date}")

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT dr.report_date, SUM(dwi.hours_spent) as hours
                FROM daily_reports dr
                JOIN daily_work_items dwi ON dr.id = dwi.report_id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start
                  AND dr.report_date <= :today
                GROUP BY dr.report_date
                ORDER BY dr.report_date
            """), {"emp_id": employee_id, "start": start_date, "today": today})

            # 构建日期序列
            dates = []
            actual = []
            data_map = {}

            for row in result:
                data_map[str(row[0])] = float(row[1] or 0)
                logger.debug(f" Found data: {row[0]} -> {row[1]}")

            logger.debug(f" data_map: {data_map}")

            for i in range(days):
                d = start_date + timedelta(days=i)
                date_str = d.strftime("%Y-%m-%d")
                dates.append(d.strftime("%m-%d"))
                actual.append(data_map.get(date_str, 0))

            # 预测线（简单移动平均）
            predicted = []
            window = 3
            for i in range(len(actual)):
                if i < window:
                    predicted.append(actual[i])
                else:
                    avg = sum(actual[i-window:i]) / window
                    predicted.append(round(avg, 1))

            return {
                "dates": dates,
                "actual": actual,
                "predicted": predicted
            }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {"dates": [], "actual": [], "predicted": []}


@app.get("/api/agent/stats/project-distribution")
async def get_project_distribution(current_user: Dict = Depends(get_current_user)):
    """
    获取项目工时分布（饼图）
    """
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()
        month_start = today.replace(day=1)

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT COALESCE(p.name, '其他') as name, SUM(dwi.hours_spent) as value
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                LEFT JOIN projects p ON CAST(dwi.project_id AS INTEGER) = p.id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start
                  AND dr.report_date <= :today
                GROUP BY p.name
                ORDER BY value DESC
                LIMIT 10
            """), {"emp_id": employee_id, "start": month_start, "today": today})

            distribution = []
            for row in result:
                distribution.append({
                    "name": row[0],
                    "value": float(row[1] or 0)
                })

            return distribution

    except Exception as e:
        logger.error(f" {e}")
        return []


# ============== 项目风险雷达 API ==============

@app.get("/api/agent/projects/{project_id}/risk-radar")
async def get_project_risk_radar(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取项目风险雷达数据

    返回五个维度的风险评分（0-100，分数越高风险越大）：
    - schedule_risk: 进度风险（延期任务比例）
    - material_risk: 材料成本风险（材料成本超支率）
    - outsourcing_risk: 外包成本风险（外包成本超支率）
    - labor_risk: 人工成本风险（人工成本超支率）
    - indirect_risk: 间接成本风险（间接成本超支率）
    """
    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    today = datetime.now().date()

    with get_connection() as conn:
        # 1. 进度风险：延期任务比例
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_tasks,
                SUM(CASE WHEN pt.end_date < :today AND pt.actual_end_date IS NULL THEN 1 ELSE 0 END) as delayed_tasks,
                SUM(CASE WHEN pt.actual_end_date IS NOT NULL THEN 1 ELSE 0 END) as completed_tasks
            FROM project_tasks pt
            WHERE pt.project_id = :project_id
              AND pt.is_deleted = false
        """), {"project_id": str(project_id), "today": today})

        task_row = result.fetchone()
        total_tasks = task_row[0] or 0
        delayed_tasks = task_row[1] or 0
        completed_tasks = task_row[2] or 0

        # 进度风险评分：延期率 × 100
        schedule_risk = round((delayed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)

        # 2. 四大成本风险：从项目表获取
        result = conn.execute(text("""
            SELECT
                material_budget, material_cost,
                outsourcing_budget, outsourcing_cost,
                labor_budget, labor_cost,
                indirect_budget, indirect_cost,
                p.end_date, p.start_date
            FROM projects p
            WHERE p.id = :project_id
        """), {"project_id": project_id})

        cost_row = result.fetchone()

        if cost_row:
            # 材料成本风险
            material_budget = float(cost_row[0] or 0)
            material_cost = float(cost_row[1] or 0)
            if material_budget > 0:
                material_risk = max(0, round((material_cost - material_budget) / material_budget * 100, 1))
            else:
                material_risk = 0

            # 外包成本风险
            outsourcing_budget = float(cost_row[2] or 0)
            outsourcing_cost = float(cost_row[3] or 0)
            if outsourcing_budget > 0:
                outsourcing_risk = max(0, round((outsourcing_cost - outsourcing_budget) / outsourcing_budget * 100, 1))
            else:
                outsourcing_risk = 0

            # 人工成本风险
            labor_budget = float(cost_row[4] or 0)
            labor_cost = float(cost_row[5] or 0)
            if labor_budget > 0:
                labor_risk = max(0, round((labor_cost - labor_budget) / labor_budget * 100, 1))
            else:
                labor_risk = 0

            # 间接成本风险
            indirect_budget = float(cost_row[6] or 0)
            indirect_cost = float(cost_row[7] or 0)
            if indirect_budget > 0:
                indirect_risk = max(0, round((indirect_cost - indirect_budget) / indirect_budget * 100, 1))
            else:
                indirect_risk = 0

            project_end_date = cost_row[8]
        else:
            material_budget = material_cost = 0
            outsourcing_budget = outsourcing_cost = 0
            labor_budget = labor_cost = 0
            indirect_budget = indirect_cost = 0
            material_risk = outsourcing_risk = labor_risk = indirect_risk = 0
            project_end_date = None

        # 计算剩余任务数
        result = conn.execute(text("""
            SELECT COUNT(pt.task_id) as remaining_tasks
            FROM project_tasks pt
            WHERE pt.project_id = :project_id
              AND pt.actual_end_date IS NULL
              AND pt.is_deleted = false
        """), {"project_id": str(project_id)})

        remaining_tasks = result.fetchone()[0] or 0

        # 计算剩余天数
        if project_end_date:
            days_remaining = (project_end_date - today).days
        else:
            days_remaining = None

        # 综合风险评分：进度40% + 四大成本平均60%
        cost_avg_risk = (material_risk + outsourcing_risk + labor_risk + indirect_risk) / 4
        overall_risk = round(schedule_risk * 0.4 + cost_avg_risk * 0.6, 1)

        # 风险等级
        if overall_risk >= 70:
            risk_level = "high"
            risk_label = "高风险"
        elif overall_risk >= 40:
            risk_level = "medium"
            risk_label = "中风险"
        else:
            risk_level = "low"
            risk_label = "低风险"

        return {
            "project_id": project_id,
            "radar": {
                "schedule_risk": schedule_risk,
                "material_risk": material_risk,
                "outsourcing_risk": outsourcing_risk,
                "labor_risk": labor_risk,
                "indirect_risk": indirect_risk
            },
            "overall_risk": overall_risk,
            "risk_level": risk_level,
            "risk_label": risk_label,
            "details": {
                "total_tasks": total_tasks,
                "delayed_tasks": delayed_tasks,
                "completed_tasks": completed_tasks,
                "days_remaining": days_remaining,
                "remaining_tasks": remaining_tasks,
                "cost_details": {
                    "material": {"budget": material_budget, "actual": material_cost},
                    "outsourcing": {"budget": outsourcing_budget, "actual": outsourcing_cost},
                    "labor": {"budget": labor_budget, "actual": labor_cost},
                    "indirect": {"budget": indirect_budget, "actual": indirect_cost}
                }
            }
        }


@app.get("/api/agent/projects/{project_id}/task-risks")
async def get_project_task_risks(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取项目任务风险预警

    检查项：
    - 延期风险：计划结束时间已过，进度 < 100%
    - 即将到期风险：3天内到期，进度 < 80%
    - 未报告风险：已启动但无日报记录
    - 即将启动提醒：3天内开始
    """
    # 导入风险检查函数
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from task_auto import check_task_risks
    risks = check_task_risks(project_id)

    # 按风险等级排序
    risk_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda x: risk_order.get(x["risk_level"], 3))

    return {
        "project_id": project_id,
        "risks": risks,
        "risk_count": len(risks),
        "high_risk_count": sum(1 for r in risks if r["risk_level"] == "high"),
        "medium_risk_count": sum(1 for r in risks if r["risk_level"] == "medium"),
        "low_risk_count": sum(1 for r in risks if r["risk_level"] == "low")
    }


@app.post("/api/agent/projects/{project_id}/update-task-status")
async def update_project_task_status(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    更新项目所有任务状态（自动计算）

    根据进度和时间自动计算任务状态：
    - 未开始：计划开始时间未到
    - 进行中：在计划周期内
    - 延期：计划结束时间已过，进度 < 100%
    - 已完成：进度 >= 100%
    """
    try:
        from .task_auto import get_latest_version_tasks, calculate_task_status
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        tasks = get_latest_version_tasks(project_id)
        updated_tasks = []

        with get_connection() as conn:
            for task in tasks:
                new_status, changed = calculate_task_status(task)

                if changed:
                    # 更新状态
                    update_fields = ["status = :status", "update_time = CURRENT_TIMESTAMP"]
                    params = {"tid": task["task_id"], "status": new_status}

                    # 如果完成，设置实际完成时间
                    if new_status == "已完成" and not task["actual_end_date"]:
                        update_fields.append("actual_end_date = CURRENT_DATE")

                    # 安全构建SET子句（白名单验证字段名）
                    allowed_fields = {"status", "progress", "actual_end_date", "updated_at"}
                    set_clause = ", ".join(f"{field} = :{field}" for field in update_fields if field.split("=")[0].strip() in allowed_fields)
                    if set_clause:
                        conn.execute(text(f"""
                            UPDATE project_tasks
                            SET {set_clause}
                            WHERE task_id = :tid
                        """), params)

                    updated_tasks.append({
                        "task_id": task["task_id"],
                        "task_name": task["task_name"],
                        "old_status": task["status"],
                        "new_status": new_status
                    })

            conn.commit()

        return {
            "project_id": project_id,
            "updated_count": len(updated_tasks),
            "updated_tasks": updated_tasks
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@app.get("/api/agent/projects", response_model=List[ProjectInfo])
async def get_projects(current_user: Dict = Depends(get_current_user)):
    """
    获取项目列表（需要认证）

    admin 可以看到所有项目
    项目经理只能看到自己负责的项目
    """
    username = current_user.get("username")
    token = get_user_token(username)

    logger.debug(f"获取项目: username={username}, token存在={bool(token)}")

    if token:
        # 获取用户信息
        user_info = get_user_info_cache(username)
        if not user_info:
            user_info = await get_user_info(token)
            if user_info:
                cache_manager.store_user_info(username, user_info)

        # 使用用户token获取项目列表，并过滤
        projects = await get_projects_with_auth(token, user_info)
        logger.debug(f"获取到项目数量: {len(projects)}")
    else:
        # 降级：使用缓存
        projects = await get_cached_projects()

    return [ProjectInfo(**p) for p in projects]


@app.get("/api/agent/projects/{project_id}")
async def get_project_detail(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取项目详情（包含工时统计、成本数据、进度计算）
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        # 从数据库直接查询项目信息
        with get_connection() as conn:
            # 项目基本信息
            project_result = conn.execute(text("""
                SELECT id, name, leader, status,
                       start_date, end_date,
                       budget_total_cost, contract_amount,
                       material_budget, material_cost,
                       outsourcing_budget, outsourcing_cost,
                       labor_budget, labor_cost,
                       indirect_budget, indirect_cost,
                       project_category, project_subject,
                       implementation_mode, project_level
                FROM projects
                WHERE id = :pid
            """), {"pid": project_id})

            project_row = project_result.fetchone()
            if not project_row:
                raise HTTPException(status_code=404, detail="项目不存在")

            # 获取最新版本任务的时间范围和进度
            task_stats = conn.execute(text("""
                WITH latest_version AS (
                    SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
                    FROM project_tasks
                    WHERE project_id::integer = :pid AND is_deleted = false
                )
                SELECT
                    MIN(start_date) as plan_start,
                    MAX(end_date) as plan_end,
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed_tasks,
                    AVG(progress) as avg_progress
                FROM project_tasks pt, latest_version lv
                WHERE pt.project_id::integer = :pid
                  AND pt.is_deleted = false
                  AND COALESCE(CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER), 0) = COALESCE(lv.max_ver, 0)
            """), {"pid": project_id})

            task_row = task_stats.fetchone()

            # 计算项目进度
            total_tasks = task_row[2] or 0
            completed_tasks = task_row[3] or 0
            avg_progress = float(task_row[4] or 0)

            # 进度计算：已完成任务占比 + 平均进度占比
            if total_tasks > 0:
                project_progress = (completed_tasks / total_tasks * 100 + avg_progress) / 2
            else:
                project_progress = 0

            # 项目总工时
            hours_result = conn.execute(text("""
                SELECT COALESCE(SUM(hours_spent), 0) as hours
                FROM daily_work_items
                WHERE project_id = :pid
            """), {"pid": str(project_id)})
            total_hours = float(hours_result.fetchone()[0] or 0)

            # 计算人力成本（基于费率表）
            labor_cost_result = conn.execute(text("""
                SELECT COALESCE(SUM(
                    dwi.hours_spent * COALESCE(pr.hourly_rate, 0)
                ), 0) as labor_cost
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                LEFT JOIN personnel p ON dr.employee_id = p.employee_id
                LEFT JOIN personnel_rates pr ON p.id = pr.personnel_id
                    AND pr.year = TO_CHAR(dr.report_date, 'YYYY')
                    AND pr.month = TO_CHAR(dr.report_date, 'MM')
                    AND pr.is_deleted = false
                WHERE dwi.project_id = :pid
            """), {"pid": str(project_id)})

            calculated_labor_cost = float(labor_cost_result.fetchone()[0] or 0)

            # 如果计算的人力成本大于数据库中的，使用计算的值
            labor_cost_from_db = float(project_row[13] or 0)
            labor_cost = calculated_labor_cost if calculated_labor_cost > labor_cost_from_db else labor_cost_from_db

            # 各人员工时
            worker_result = conn.execute(text("""
                SELECT
                    dr.employee_name,
                    SUM(dwi.hours_spent) as hours
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                WHERE dwi.project_id = :pid
                GROUP BY dr.employee_name
                ORDER BY hours DESC
                LIMIT 5
            """), {"pid": str(project_id)})

            worker_hours = []
            for row in worker_result:
                worker_hours.append({
                    "name": row[0],
                    "hours": float(row[1] or 0)
                })

        return {
            "id": project_row[0],
            "name": project_row[1],
            "leader": project_row[2],
            "status": project_row[3],
            "start_date": str(project_row[4]) if project_row[4] else None,
            "end_date": str(project_row[5]) if project_row[5] else None,
            "budget": float(project_row[6] or 0),
            "contract_amount": float(project_row[7] or 0),
            # 成本数据
            "material_budget": float(project_row[8] or 0),
            "material_cost": float(project_row[9] or 0),
            "outsourcing_budget": float(project_row[10] or 0),
            "outsourcing_cost": float(project_row[11] or 0),
            "labor_budget": float(project_row[12] or 0),
            "labor_cost": labor_cost,  # 使用计算的人力成本
            "indirect_budget": float(project_row[14] or 0),
            "indirect_cost": float(project_row[15] or 0),
            # 分类信息
            "project_category": project_row[16],
            "project_subject": project_row[17],
            "implementation_mode": project_row[18],
            "project_level": project_row[19],
            # 计算数据
            "plan_start_date": str(task_row[0]) if task_row[0] else None,
            "plan_end_date": str(task_row[1]) if task_row[1] else None,
            "progress": round(project_progress, 1),
            "progress_formula": f"({completed_tasks}/{total_tasks}×100 + {round(avg_progress, 1)})÷2 = {round(project_progress, 1)}%",
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "total_hours": round(total_hours, 1),
            "worker_hours": worker_hours,
            "description": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取项目详情失败: {str(e)}")


@app.get("/api/agent/projects/{project_id}/tasks")
async def get_project_tasks(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取项目任务列表（从本地数据库，只返回最新版本）
    版本规则：task_id 包含 V{版本号}，返回最大版本号的任务
    """
    # text 已从 database 模块导入
    from dotenv import load_dotenv
    load_dotenv()
    with get_connection() as conn:
        # 获取最新版本号
        version_result = conn.execute(text("""
            SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_version
            FROM project_tasks
            WHERE project_id::integer = :pid
              AND is_deleted = false
        """), {"pid": project_id})

        max_version_row = version_result.fetchone()
        max_version = max_version_row[0] if max_version_row and max_version_row[0] else 1

        # 获取指定版本的任务
        result = conn.execute(text("""
            SELECT pt.task_id, pt.task_name, pt.assignee, pt.start_date, pt.end_date,
                   pt.status, pt.progress, pt.planned_hours,
                   COALESCE(
                       json_agg(
                           json_build_object(
                               'report_date', dr.report_date,
                               'work_content', dwi.work_content,
                               'hours_spent', dwi.hours_spent
                           )
                           ORDER BY dr.report_date
                       ) FILTER (WHERE dwi.id IS NOT NULL),
                       '[]'::json
                   ) as daily_reports
            FROM project_tasks pt
            LEFT JOIN daily_work_items dwi ON dwi.task_id = pt.task_id
            LEFT JOIN daily_reports dr ON dr.id = dwi.report_id
            WHERE pt.project_id::integer = :pid
              AND pt.is_deleted = false
              AND CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) = :max_version
            GROUP BY pt.task_id, pt.task_name, pt.assignee, pt.start_date, pt.end_date,
                     pt.status, pt.progress, pt.planned_hours
            ORDER BY pt.end_date NULLS LAST
        """), {"pid": project_id, "max_version": max_version})

        tasks = []
        for row in result:
            tasks.append({
                "task_id": row[0],
                "task_name": row[1],
                "assignee": row[2],
                "start_date": str(row[3]) if row[3] else None,
                "end_date": str(row[4]) if row[4] else None,
                "status": row[5] or "未开始",
                "progress": float(row[6] or 0),
                "planned_hours": float(row[7] or 0),
                "daily_reports": row[8] if row[8] else []
            })

        return tasks

@app.post("/api/agent/daily/parse", response_model=ParseDailyResponse)
async def parse_daily(
    request: ParseDailyRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    智能解析日报文本（需要认证）

    - 提取时间、地点、内容
    - 自动匹配项目
    - 推荐关联任务
    """
    try:
        username = current_user.get("username")
        token = get_user_token(username)

        # 获取项目列表（用于匹配）
        if token:
            projects = await get_projects_with_auth(token)
        else:
            projects = await get_cached_projects()

        logger.debug(f"获取到 {len(projects)} 个项目用于匹配")

        # 执行工作流
        result = await daily_agent.ainvoke({
            "text": request.text,
            "user_id": username or request.user_id,
            "projects": projects
        })

        entries = [DailyEntry(**e) for e in result.get("parsed_entries", [])]

        return ParseDailyResponse(
            entries=entries,
            confidence=result.get("confidence", 0),
            issues=result.get("issues", [])
        )
    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class SubmitDailyRequest(BaseModel):
    """提交日报请求"""
    date: str  # YYYY-MM-DD格式
    entries: List[DailyEntry]
    employee_id: str
    employee_name: str


@app.post("/api/agent/daily/submit")
async def submit_daily(
    request: SubmitDailyRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    提交日报到现有后端

    使用当前用户的token，调用现有后端API创建日报
    """
    try:
        username = current_user.get("username")
        token = get_user_token(username)

        if not token:
            raise HTTPException(status_code=401, detail="未找到用户认证信息")

        # 获取员工信息
        # 简化：使用username作为employee_id，实际应该查数据库
        employee_id = request.employee_id or username
        employee_name = request.employee_name or username

        # 构建工作事项列表
        work_items = []
        total_hours = 0

        for entry in request.entries:
            hours = entry.hours or 0
            total_hours += hours

            work_items.append({
                "work_content": entry.content,
                "project_id": str(entry.matched_project_id) if entry.matched_project_id else None,
                "project_name": entry.matched_project_name or entry.project_hint,
                "task_id": entry.matched_task_id,
                "task_name": entry.matched_task_name,
                "start_time": entry.start_time,
                "end_time": entry.end_time,
                "hours_spent": hours,
                "progress_status": "正常",
                "progress_percentage": 0
            })

        # 构建日报数据
        daily_report_data = {
            "report": {
                "report_date": request.date,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "work_target": "完成日常工作",
                "planned_hours": total_hours,
                "key_work_tracking": None,
                "tomorrow_plan": None
            },
            "work_items": work_items
        }

        logger.debug(f"提交日报数据: {json.dumps(daily_report_data, ensure_ascii=False)}")

        # 调用现有后端API (/api/v1/daily-report 而非 /api/v1/daily)
        response = await http_client.post(
            f"{settings.BACKEND_API_URL}/api/v1/daily-report/my-reports/with-items",
            json=daily_report_data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            # 后端直接返回日报对象，不是嵌套在 data 中
            report_id = result.get("id")
            return {
                "success": True,
                "message": "日报提交成功",
                "report_id": report_id
            }
        else:
            logger.error(f" {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"提交失败: {response.text}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

# ============== 计划版本管理 API ==============

@app.post("/api/agent/plans/upload/{project_id}")
@limiter.limit("20/hour")  # 上传限流：每小时最多20次
async def upload_plan_excel(
    request: Request,
    project_id: int,
    file: UploadFile = File(...),
    version_name: Optional[str] = None,
    description: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    上传Excel计划并解析导入

    Excel格式要求：
    - 第一行为表头
    - 必须包含列：任务名称
    - 可选列：负责人、开始日期、结束日期、工时、状态、备注
    """
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    # 检查文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")

    try:
        # 读取文件内容
        content = await file.read()

        # 构建multipart/form-data请求
        files = {
            "file": (file.filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }

        params = {}
        if version_name:
            params["version_name"] = version_name
        if description:
            params["description"] = description

        # 调用主后端上传接口
        response = await http_client.post(
            f"{settings.BACKEND_API_URL}/api/v1/plan-versions/upload-excel/{project_id}",
            files=files,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0
        )

        if response.status_code == 200:
            result = response.json()
            data = result.get("data", result)
            return {
                "success": True,
                "message": f"成功导入 {data.get('task_count', 0)} 个任务",
                "version_id": data.get("version_id"),
                "version_number": data.get("version_number"),
                "version_name": data.get("version_name"),
                "task_count": data.get("task_count"),
                "tasks": data.get("tasks", [])
            }
        else:
            error_msg = "上传失败"
            try:
                error_data = response.json()
                error_msg = error_data.get("detail") or error_data.get("message") or error_msg
            except:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.get("/api/agent/plans/versions/{project_id}")
async def get_plan_versions(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """获取项目的计划版本列表"""
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        response = await http_client.get(
            f"{settings.BACKEND_API_URL}/api/v1/plan-versions/project/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("data", result)
        return []
    except Exception as e:
        logger.error(f" {e}")
        return []


@app.get("/api/agent/plans/compare/{version_id1}/{version_id2}")
async def compare_plan_versions(
    version_id1: int,
    version_id2: int,
    current_user: Dict = Depends(get_current_user)
):
    """对比两个计划版本"""
    username = current_user.get("username")
    token = get_user_token(username)

    if not token:
        raise HTTPException(status_code=401, detail="未找到用户认证信息")

    try:
        response = await http_client.get(
            f"{settings.BACKEND_API_URL}/api/v1/plan-versions/compare/{version_id1}/{version_id2}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("data", result)
        raise HTTPException(status_code=response.status_code, detail="对比失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")

# ============== 智能问答工具 ==============

# 全局数据库引擎（懒加载）
_db_engine = None

# 数据库引擎单例（已废弃，改用 database 模块的全局单例）
# 保留 _db_engine 变量以兼容可能的引用
_db_engine = None

def get_db_engine():
    """获取数据库引擎（使用 database 模块的全局单例）"""
    return get_engine()


# 定义查询工具（简化版，不用LangChain tools）
def execute_query(tool_name: str, params: dict) -> str:
    """执行查询工具"""
    try:
        engine = get_db_engine()
        from sqlalchemy import text

        with get_connection() as conn:
            if tool_name == "query_projects":
                sql = """
                    SELECT id, name, leader, status, progress
                    FROM projects WHERE is_deleted = false
                """
                conditions = []
                if params.get("keyword"):
                    conditions.append(f"name LIKE '%{params['keyword']}%'")
                if params.get("leader"):
                    conditions.append(f"leader LIKE '%{params['leader']}%'")
                if conditions:
                    sql += " AND " + " AND ".join(conditions)
                sql += " LIMIT 20"

                result = conn.execute(text(sql))
                return json.dumps([{
                    "id": r[0], "name": r[1], "leader": r[2],
                    "status": r[3], "progress": r[4]
                } for r in result], ensure_ascii=False)

            elif tool_name == "query_tasks":
                today = datetime.now().date()
                sql = """
                    SELECT pt.task_name, pt.project_id, p.name as project_name,
                           pt.assignee, pt.end_date, pt.status
                    FROM project_tasks pt
                    LEFT JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                    WHERE pt.is_deleted = false
                """
                conditions = []
                if params.get("assignee"):
                    conditions.append(f"pt.assignee LIKE '%{params['assignee']}%'")
                if params.get("days"):
                    end_date = today + timedelta(days=params["days"])
                    conditions.append(f"pt.end_date >= '{today}' AND pt.end_date <= '{end_date}'")
                if conditions:
                    sql += " AND " + " AND ".join(conditions)
                sql += " LIMIT 50"

                result = conn.execute(text(sql))
                return json.dumps([{
                    "task_name": r[0], "project_id": r[1], "project_name": r[2],
                    "assignee": r[3], "end_date": str(r[4]) if r[4] else None, "status": r[5]
                } for r in result], ensure_ascii=False)

            elif tool_name == "query_risks":
                sql = """
                    SELECT p.name, p.leader, COUNT(*) as delayed_count
                    FROM projects p
                    JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                    WHERE p.is_deleted = false AND pt.is_deleted = false
                      AND pt.end_date < CURRENT_DATE AND pt.actual_end_date IS NULL
                    GROUP BY p.id, p.name, p.leader
                    ORDER BY delayed_count DESC LIMIT 10
                """
                result = conn.execute(text(sql))
                return json.dumps([{
                    "project_name": r[0], "leader": r[1], "delayed_count": r[2]
                } for r in result], ensure_ascii=False)

            elif tool_name == "query_work_hours":
                today = datetime.now().date()
                month = params.get("month", today.strftime("%Y-%m"))
                month_start = datetime.strptime(month + "-01", "%Y-%m-%d").date()

                sql = f"""
                    SELECT dr.employee_name, SUM(dwi.hours_spent) as total_hours
                    FROM daily_reports dr
                    JOIN daily_work_items dwi ON dr.id = dwi.report_id
                    WHERE dr.is_deleted = false
                      AND dr.report_date >= '{month_start}'
                      AND dr.report_date <= '{today}'
                """
                if params.get("employee_name"):
                    sql += f" AND dr.employee_name LIKE '%{params['employee_name']}%'"
                sql += " GROUP BY dr.employee_name ORDER BY total_hours DESC LIMIT 10"

                result = conn.execute(text(sql))
                return json.dumps([{
                    "employee_name": r[0], "total_hours": float(r[1] or 0)
                } for r in result], ensure_ascii=False)

            elif tool_name == "query_goals":
                # 方案：根据本月任务自动生成月度目标（不再依赖 monthly_goals 表）
                month = datetime.now().strftime("%Y-%m")
                month_start = datetime.now().replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

                # 查询用户本月负责的任务
                sql = f"""
                    SELECT pt.task_id, pt.task_name, pt.status, pt.progress,
                           pt.start_date, pt.end_date, p.name as project_name
                    FROM project_tasks pt
                    JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                    WHERE pt.is_deleted = false
                      AND p.is_deleted = false
                      AND (
                        (pt.start_date >= '{month_start}' AND pt.start_date <= '{month_end}')
                        OR (pt.end_date >= '{month_start}' AND pt.end_date <= '{month_end}')
                        OR (pt.start_date < '{month_start}' AND pt.end_date > '{month_end}')
                      )
                """

                if params.get("employee_name"):
                    sql += f" AND pt.assignee LIKE '%{params['employee_name']}%'"

                sql += " ORDER BY pt.end_date LIMIT 20"

                result = conn.execute(text(sql))
                tasks = []
                for r in result:
                    tasks.append({
                        "task_id": r[0],
                        "task_name": r[1],
                        "status": r[2],
                        "progress": float(r[3] or 0),
                        "start_date": str(r[4]) if r[4] else None,
                        "end_date": str(r[5]) if r[5] else None,
                        "project_name": r[6]
                    })

                # 根据任务自动推断月度目标
                if tasks:
                    # 按项目分组
                    project_tasks = {}
                    for task in tasks:
                        pname = task["project_name"]
                        if pname not in project_tasks:
                            project_tasks[pname] = []
                        project_tasks[pname].append(task)

                    # 生成月度目标描述
                    goals = []
                    for pname, ptasks in project_tasks.items():
                        ongoing = [t for t in ptasks if t["status"] in ["进行中", "未开始"]]
                        completed = [t for t in ptasks if t["status"] == "已完成"]
                        delayed = [t for t in ptasks if t["status"] == "延期"]

                        if ongoing:
                            goals.append(f"{pname}：推进{len(ongoing)}个任务")
                        if completed:
                            goals.append(f"{pname}：已完成{len(completed)}个任务")
                        if delayed:
                            goals.append(f"{pname}：{len(delayed)}个任务延期")

                    return json.dumps({
                        "month": month,
                        "tasks": tasks,
                        "goals_summary": goals,
                        "total_tasks": len(tasks),
                        "ongoing_count": len([t for t in tasks if t["status"] in ["进行中", "未开始"]]),
                        "completed_count": len([t for t in tasks if t["status"] == "已完成"]),
                        "delayed_count": len([t for t in tasks if t["status"] == "延期"])
                    }, ensure_ascii=False)
                else:
                    return json.dumps({
                        "month": month,
                        "tasks": [],
                        "goals_summary": ["本月暂无分配任务"],
                        "total_tasks": 0
                    }, ensure_ascii=False)

            else:
                return json.dumps({"error": f"未知工具: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


# 工具描述（用于提示LLM）
TOOL_DESCRIPTIONS = """
可用工具：
1. query_projects(keyword, leader) - 查询项目列表
   参数：keyword(项目名关键词，如"600KA"、"烟气治理"), leader(负责人姓名)
   用途：根据项目名称或负责人查询项目信息

2. query_tasks(assignee, days) - 查询任务
   参数：assignee(负责人姓名), days(未来N天)

3. query_risks() - 查询延期风险项目

4. query_work_hours(employee_name, month) - 查询工时
   参数：employee_name(员工姓名), month(月份YYYY-MM)

5. query_goals(employee_name) - 查询月度目标
   参数：employee_name(员工姓名)
"""


# ============== 智能周报生成 API ==============

@app.get("/api/agent/reports/weekly")
async def generate_weekly_report(
    week_start: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    生成智能周报

    Args:
        week_start: 周起始日期（YYYY-MM-DD），默认本周一

    Returns:
        周报内容（工时、项目、任务、风险）
    """
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username
    employee_name = user_info.get("name") if user_info else username

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()

        # 计算本周起始日期（周一）
        if week_start:
            start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        else:
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(days=6)

        with get_connection() as conn:
            # 1. 工时统计
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT dr.id) as report_count,
                    COALESCE(SUM(dwi.hours_spent), 0) as total_hours,
                    COUNT(DISTINCT dwi.project_id) as project_count
                FROM daily_reports dr
                LEFT JOIN daily_work_items dwi ON dr.id = dwi.report_id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start_date
                  AND dr.report_date <= :end_date
            """), {"emp_id": employee_id, "start_date": start_date, "end_date": end_date})

            hours_row = result.fetchone()
            report_count = hours_row[0] or 0
            total_hours = float(hours_row[1] or 0)
            project_count = hours_row[2] or 0

            # 2. 项目工时分布
            result = conn.execute(text("""
                SELECT
                    COALESCE(p.name, '其他') as project_name,
                    SUM(dwi.hours_spent) as hours,
                    COUNT(*) as item_count
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                LEFT JOIN projects p ON CAST(dwi.project_id AS INTEGER) = p.id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start_date
                  AND dr.report_date <= :end_date
                GROUP BY p.name
                ORDER BY hours DESC
            """), {"emp_id": employee_id, "start_date": start_date, "end_date": end_date})

            project_hours = []
            for row in result:
                project_hours.append({
                    "project_name": row[0],
                    "hours": float(row[1] or 0),
                    "item_count": row[2]
                })

            # 3. 工作事项汇总（按项目分组）
            result = conn.execute(text("""
                SELECT
                    COALESCE(p.name, '其他') as project_name,
                    string_agg(DISTINCT dwi.work_content, '；') as contents,
                    SUM(dwi.hours_spent) as total_hours
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                LEFT JOIN projects p ON CAST(dwi.project_id AS INTEGER) = p.id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start_date
                  AND dr.report_date <= :end_date
                GROUP BY p.name
                ORDER BY total_hours DESC
            """), {"emp_id": employee_id, "start_date": start_date, "end_date": end_date})

            work_summary = []
            for row in result:
                contents = row[1][:300] if row[1] and len(row[1]) > 300 else row[1]  # 截取前300字
                work_summary.append({
                    "project_name": row[0],
                    "contents": contents,
                    "hours": float(row[2] or 0)
                })

            # 4. 任务完成情况
            result = conn.execute(text("""
                SELECT
                    pt.task_name,
                    p.name as project_name,
                    pt.status,
                    pt.progress
                FROM project_tasks pt
                LEFT JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.assignee_id = :emp_id
                  AND pt.is_deleted = false
                  AND (
                    (pt.actual_end_date >= :start_date AND pt.actual_end_date <= :end_date)
                    OR (pt.end_date >= :start_date AND pt.end_date <= :end_date)
                  )
                ORDER BY pt.end_date
            """), {"emp_id": employee_id, "start_date": start_date, "end_date": end_date})

            tasks = []
            completed_count = 0
            for row in result:
                tasks.append({
                    "task_name": row[0],
                    "project_name": row[1],
                    "status": row[2],
                    "progress": float(row[3] or 0)
                })
                if row[2] == "已完成":
                    completed_count += 1

            # 5. 延期任务
            result = conn.execute(text("""
                SELECT
                    pt.task_name,
                    p.name as project_name,
                    CURRENT_DATE - pt.end_date as delay_days
                FROM project_tasks pt
                LEFT JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.assignee_id = :emp_id
                  AND pt.is_deleted = false
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                ORDER BY delay_days DESC
                LIMIT 5
            """), {"emp_id": employee_id})

            delayed_tasks = []
            for row in result:
                delayed_tasks.append({
                    "task_name": row[0],
                    "project_name": row[1],
                    "delay_days": row[2]
                })

            # 6. 月度目标进度
            result = conn.execute(text("""
                SELECT title, progress_rate
                FROM monthly_goals
                WHERE user_id = :emp_id
                  AND is_deleted = false
                  AND month = :month
            """), {"emp_id": employee_id, "month": today.strftime("%Y-%m")})

            goals = []
            for row in result:
                goals.append({
                    "title": row[0],
                    "progress_rate": float(row[1] or 0)
                })

        # 生成周报文本
        week_number = start_date.isocalendar()[1]

        report_markdown = f"""# 周报 ({start_date.strftime('%m.%d')}-{end_date.strftime('%m.%d')})

## 基本信息
- **姓名**：{employee_name}
- **周次**：第{week_number}周
- **填报天数**：{report_count}天
- **累计工时**：{total_hours}小时
- **涉及项目**：{project_count}个

## 本周工作内容

"""

        if work_summary:
            for i, work in enumerate(work_summary, 1):
                report_markdown += f"### {i}. {work['project_name']}（{work['hours']}h）\n"
                report_markdown += f"{work['contents']}\n\n"
        else:
            report_markdown += "_暂无工作记录_\n\n"

        if tasks:
            report_markdown += f"## 任务完成情况\n\n"
            report_markdown += f"- 本周任务：{len(tasks)}项\n"
            report_markdown += f"- 已完成：{completed_count}项\n\n"

            if completed_count > 0:
                report_markdown += "**已完成任务**：\n"
                for t in tasks:
                    if t['status'] == '已完成':
                        report_markdown += f"- ✅ {t['task_name']}（{t['project_name']}）\n"
                report_markdown += "\n"

        if delayed_tasks:
            report_markdown += "## ⚠️ 延期预警\n\n"
            for t in delayed_tasks:
                report_markdown += f"- {t['task_name']}（{t['project_name']}）延期{t['delay_days']}天\n"
            report_markdown += "\n"

        if goals:
            report_markdown += "## 月度目标进度\n\n"
            for g in goals:
                status = "🟢" if g['progress_rate'] >= 80 else "🟡" if g['progress_rate'] >= 50 else "🔴"
                report_markdown += f"- {status} {g['title']}：{g['progress_rate']}%\n"

        report_markdown += "\n---\n*本报告由项目管家智能生成*"

        return {
            "success": True,
            "employee_name": employee_name,
            "week_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "week_number": week_number
            },
            "statistics": {
                "report_count": report_count,
                "total_hours": total_hours,
                "project_count": project_count,
                "task_count": len(tasks),
                "completed_count": completed_count,
                "delayed_count": len(delayed_tasks)
            },
            "project_hours": project_hours,
            "work_summary": work_summary,
            "tasks": tasks,
            "delayed_tasks": delayed_tasks,
            "goals": goals,
            "report_markdown": report_markdown
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": str(e)
        }


# ============== 系统通知 API ==============

@app.get("/api/agent/notifications")
async def get_my_notifications(
    unread_only: bool = False,
    limit: int = 20,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取我的通知列表

    Args:
        unread_only: 仅未读
        limit: 返回数量
    """
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            sql = """
                SELECT id, notification_type, priority_level, title, content,
                       is_read, create_time, related_task_id
                FROM tracking_notifications
                WHERE recipient_id = :emp_id AND is_deleted = false
            """
            params = {"emp_id": employee_id}

            if unread_only:
                sql += " AND is_read = false"

            sql += " ORDER BY create_time DESC LIMIT :limit"
            params["limit"] = limit

            result = conn.execute(text(sql), params)
            notifications = []
            for row in result:
                notifications.append({
                    "id": row[0],
                    "type": row[1],
                    "priority": row[2],
                    "title": row[3],
                    "content": row[4],
                    "is_read": row[5],
                    "create_time": row[6].isoformat() if row[6] else None,
                    "related_task_id": row[7]
                })

            # 获取未读数量
            count_result = conn.execute(text("""
                SELECT COUNT(*) FROM tracking_notifications
                WHERE recipient_id = :emp_id AND is_deleted = false AND is_read = false
            """), {"emp_id": employee_id})
            unread_count = count_result.fetchone()[0]

            return {
                "notifications": notifications,
                "unread_count": unread_count
            }

    except Exception as e:
        logger.error(f" {e}")
        return {"notifications": [], "unread_count": 0}


@app.post("/api/agent/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """标记通知为已读"""
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE tracking_notifications
                SET is_read = true, read_time = CURRENT_TIMESTAMP
                WHERE id = :id
            """), {"id": notification_id})
            conn.commit()

        return {"success": True, "message": "已标记为已读"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@app.post("/api/agent/notifications/read-all")
async def mark_all_notifications_read(
    current_user: Dict = Depends(get_current_user)
):
    """标记所有通知为已读"""
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE tracking_notifications
                SET is_read = true, read_time = CURRENT_TIMESTAMP
                WHERE recipient_id = :emp_id AND is_read = false AND is_deleted = false
            """), {"emp_id": employee_id})
            conn.commit()

        return {"success": True, "message": "已全部标记为已读"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@app.post("/api/agent/notifications/generate")
async def generate_smart_notifications(
    current_user: Dict = Depends(get_current_user)
):
    """
    生成智能通知

    - 今日待办提醒
    - 延期任务预警
    - 日报填报提醒
    """
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username
    employee_name = user_info.get("name") if user_info else username

    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        today = datetime.now().date()
        notifications_created = []

        with get_connection() as conn:
            # 1. 今日待办提醒
            result = conn.execute(text("""
                SELECT pt.task_name, p.name as project_name
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.assignee_id = :emp_id
                  AND pt.is_deleted = false
                  AND pt.end_date = :today
                  AND pt.actual_end_date IS NULL
            """), {"emp_id": employee_id, "today": today})

            today_tasks = list(result)
            if today_tasks:
                content = "今日待办任务：\n" + "\n".join([f"• {t[0]}（{t[1]}）" for t in today_tasks[:5]])
                conn.execute(text("""
                    INSERT INTO tracking_notifications
                    (tracking_id, notification_type, priority_level, title, content,
                     recipient_id, recipient_name, is_sent, create_time)
                    VALUES (0, 'task_reminder', '高', '📋 今日待办提醒', :content,
                            :emp_id, :emp_name, true, CURRENT_TIMESTAMP)
                """), {"content": content, "emp_id": employee_id, "emp_name": employee_name})
                notifications_created.append("今日待办提醒")

            # 2. 延期任务预警
            result = conn.execute(text("""
                SELECT pt.task_name, p.name as project_name,
                       CURRENT_DATE - pt.end_date as delay_days
                FROM project_tasks pt
                JOIN projects p ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.assignee_id = :emp_id
                  AND pt.is_deleted = false
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                ORDER BY delay_days DESC
                LIMIT 5
            """), {"emp_id": employee_id})

            delayed_tasks = list(result)
            if delayed_tasks:
                content = "延期任务预警：\n" + "\n".join([f"• {t[0]}（{t[1]}）延期{t[2]}天" for t in delayed_tasks])
                conn.execute(text("""
                    INSERT INTO tracking_notifications
                    (tracking_id, notification_type, priority_level, title, content,
                     recipient_id, recipient_name, is_sent, create_time)
                    VALUES (0, 'delay_warning', '紧急', '⚠️ 延期任务预警', :content,
                            :emp_id, :emp_name, true, CURRENT_TIMESTAMP)
                """), {"content": content, "emp_id": employee_id, "emp_name": employee_name})
                notifications_created.append("延期任务预警")

            # 3. 日报填报提醒（检查今日是否已提交）
            result = conn.execute(text("""
                SELECT id FROM daily_reports
                WHERE employee_id = :emp_id AND report_date = :today AND is_deleted = false
            """), {"emp_id": employee_id, "today": today})

            if not result.fetchone():
                conn.execute(text("""
                    INSERT INTO tracking_notifications
                    (tracking_id, notification_type, priority_level, title, content,
                     recipient_id, recipient_name, is_sent, create_time)
                    VALUES (0, 'daily_reminder', '中', '📝 日报填报提醒',
                            '今日日报尚未提交，请及时填报。',
                            :emp_id, :emp_name, true, CURRENT_TIMESTAMP)
                """), {"emp_id": employee_id, "emp_name": employee_name})
                notifications_created.append("日报填报提醒")

            conn.commit()

        return {
            "success": True,
            "notifications_created": notifications_created,
            "count": len(notifications_created)
        }

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


# ============== RAG文档问答（简化版 - 使用全文搜索） ==============

import re
from typing import List, Optional, Tuple

def chunk_text_smart(text: str, max_length: int = 500, min_length: int = 100) -> List[Tuple[str, dict]]:
    """
    智能文本切分 - 按标题和段落切分

    返回: [(chunk_text, metadata), ...]
    """
    chunks = []

    # 识别标题模式
    title_patterns = [
        r'^第[一二三四五六七八九十]+[章节]',  # 第一章、第二节
        r'^[一二三四五六七八九十]+[、.]',     # 一、二、
        r'^\d+\.[\d\s]',                     # 1.1、1.2
        r'^#{1,3}\s',                        # # ## ###
        r'^【[^】]+】',                       # 【标题】
    ]

    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text)

    current_chunk = ""
    current_title = ""
    chunk_start = 0

    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue

        # 检测是否为标题
        is_title = any(re.match(p, para) for p in title_patterns)

        if is_title:
            # 如果当前块有内容，先保存
            if current_chunk and len(current_chunk) >= min_length:
                chunks.append((
                    current_chunk.strip(),
                    {"title": current_title, "para_start": chunk_start}
                ))
            current_chunk = para + "\n\n"
            current_title = para[:50]  # 记录标题
            chunk_start = i
        else:
            # 检查是否需要切分
            if len(current_chunk) + len(para) > max_length and len(current_chunk) >= min_length:
                chunks.append((
                    current_chunk.strip(),
                    {"title": current_title, "para_start": chunk_start}
                ))
                current_chunk = para + "\n\n"
                chunk_start = i
            else:
                current_chunk += para + "\n\n"

    # 保存最后一块
    if current_chunk and len(current_chunk) >= min_length:
        chunks.append((
            current_chunk.strip(),
            {"title": current_title, "para_start": chunk_start}
        ))

    # 如果没有切分出任何块，返回整个文本
    if not chunks:
        chunks.append((text.strip(), {"title": "全文", "para_start": 0}))

    return chunks


# 嵌入模型（懒加载）
_embedding_model = None

def get_embedding_model():
    """获取嵌入模型（单例）- 使用 BGE-base-zh 中文向量模型"""
    global _embedding_model
    if _embedding_model is None:
        # 配置 HuggingFace 镜像（解决国内网络问题）
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

        from sentence_transformers import SentenceTransformer
        # BGE-base-zh: 中文语义向量模型，768维
        _embedding_model = SentenceTransformer('BAAI/bge-base-zh-v1.5')
        logger.info(" 已加载 BAAI/bge-base-zh-v1.5")
    return _embedding_model


def generate_embedding(text: str) -> Optional[List[float]]:
    """生成文本嵌入向量（使用 BGE-base-zh）"""
    try:
        model = get_embedding_model()
        # 截断过长文本（BGE 最大 512 tokens）
        if len(text) > 2000:
            text = text[:2000]
        # BGE 推荐添加指令前缀（但用于检索时不需要）
        embedding = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        return None

@app.post("/api/agent/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """上传文档（支持智能切分和向量嵌入）"""
    username = current_user.get("username")

    try:
        content = await file.read()
        filename = file.filename
        file_type = filename.split('.')[-1].lower()

        text_content = ""
        if file_type == 'txt':
            text_content = content.decode('utf-8')
        elif file_type == 'pdf':
            import PyPDF2
            import io
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
        elif file_type in ['doc', 'docx']:
            import docx
            import io
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                text_content += para.text + "\n"
        else:
            return {"success": False, "message": f"不支持的文件类型: {file_type}"}

        if not text_content.strip():
            return {"success": False, "message": "文档内容为空"}

        engine = get_db_engine()

        with get_connection() as conn:
            result = conn.execute(text("""
                INSERT INTO documents (filename, file_type, file_size, project_id, uploaded_by)
                VALUES (:filename, :file_type, :file_size, :project_id, :uploaded_by)
                RETURNING id
            """), {
                "filename": filename,
                "file_type": file_type,
                "file_size": len(content),
                "project_id": project_id,
                "uploaded_by": username
            })
            doc_id = result.fetchone()[0]
            conn.commit()

        # 智能切分
        chunks_with_meta = chunk_text_smart(text_content)

        # 批量生成嵌入（提升效率）
        logger.info(f" 开始为 {len(chunks_with_meta)} 个片段生成嵌入...")
        chunk_texts = [c[0] for c in chunks_with_meta]

        try:
            model = get_embedding_model()
            embeddings = model.encode(chunk_texts, convert_to_numpy=True, show_progress_bar=False)
        except Exception as e:
            logger.info(f" 嵌入生成失败，使用空嵌入: {e}")
            embeddings = [None] * len(chunks_with_meta)

        # 插入数据库（使用原生 psycopg2 绕过 SQLAlchemy text() 的类型转换限制）
        import psycopg2
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable not set")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        for i, (chunk_text, meta) in enumerate(chunks_with_meta):
            embedding = embeddings[i].tolist() if embeddings[i] is not None else None

            if embedding:
                cursor.execute("""
                    INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding, metadata)
                    VALUES (%s, %s, %s, %s::vector, %s::jsonb)
                """, (doc_id, chunk_text, i, str(embedding), json.dumps(meta)))
            else:
                cursor.execute("""
                    INSERT INTO document_chunks (document_id, chunk_text, chunk_index, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                """, (doc_id, chunk_text, i, json.dumps(meta)))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "success": True,
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks_with_meta),
            "message": f"文档上传成功，已切分为{len(chunks_with_meta)}个片段并生成向量嵌入"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}

@app.get("/api/agent/documents")
async def list_documents(
    project_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """列出文档"""
    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            if project_id:
                result = conn.execute(text("""
                    SELECT id, filename, file_type, file_size, uploaded_by, created_at
                    FROM documents WHERE project_id = :pid ORDER BY created_at DESC
                """), {"pid": project_id})
            else:
                result = conn.execute(text("""
                    SELECT id, filename, file_type, file_size, uploaded_by, created_at
                    FROM documents ORDER BY created_at DESC LIMIT 50
                """))

            docs = [{"id": r[0], "filename": r[1], "file_type": r[2],
                     "file_size": r[3], "uploaded_by": r[4], "created_at": str(r[5])}
                    for r in result]

            return {"success": True, "documents": docs}

    except Exception as e:
        return {"success": False, "message": str(e)}

@app.delete("/api/agent/documents/{doc_id}")
async def delete_document(doc_id: int, current_user: Dict = Depends(get_current_user)):
    """删除文档"""
    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
            conn.commit()

        return {"success": True, "message": "文档已删除"}

    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/agent/documents/search")
async def search_documents(request: Dict, current_user: Dict = Depends(get_current_user)):
    """搜索文档（向量语义搜索 + 关键词匹配）"""
    query = request.get("query", "")
    top_k = request.get("top_k", 5)
    use_semantic = request.get("use_semantic", True)

    if not query:
        return {"success": False, "message": "请输入查询内容"}

    try:
        import psycopg2
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable not set")

        results = []

        # 1. 语义搜索
        if use_semantic:
            try:
                query_embedding = generate_embedding(query)
                if query_embedding:
                    conn = psycopg2.connect(db_url)
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT dc.id, dc.document_id, dc.chunk_text, d.filename,
                               dc.metadata,
                               1 - (dc.embedding <=> %s::vector) as similarity
                        FROM document_chunks dc
                        JOIN documents d ON dc.document_id = d.id
                        WHERE dc.embedding IS NOT NULL
                        ORDER BY dc.embedding <=> %s::vector
                        LIMIT %s
                    """, (str(query_embedding), str(query_embedding), top_k))

                    for r in cursor.fetchall():
                        meta = r[4] if r[4] else {}
                        results.append({
                            "chunk_id": r[0],
                            "document_id": r[1],
                            "content": r[2][:500] if r[2] else "",
                            "filename": r[3],
                            "title": meta.get("title", ""),
                            "similarity": float(r[5]) if r[5] else 0,
                            "search_type": "semantic"
                        })

                    cursor.close()
                    conn.close()
            except Exception as e:
                logger.error(f" {e}")

        # 2. 关键词搜索（补充）
        if not results or len(results) < top_k:
            from sqlalchemy import text as text
            engine = get_db_engine()

            with get_connection() as conn:
                result = conn.execute(text("""
                    SELECT dc.id, dc.document_id, dc.chunk_text, d.filename, dc.metadata
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE dc.chunk_text ILIKE :query
                    LIMIT :limit
                """), {"query": f"%{query}%", "limit": top_k - len(results)})

                for r in result:
                    if not any(res["chunk_id"] == r[0] for res in results):
                        meta = r[4] if r[4] else {}
                        results.append({
                            "chunk_id": r[0],
                            "document_id": r[1],
                            "content": r[2][:500] if r[2] else "",
                            "filename": r[3],
                            "title": meta.get("title", ""),
                            "similarity": 0.5,
                            "search_type": "keyword"
                        })

        return {
            "success": True,
            "results": results,
            "query": query,
            "search_type": "semantic" if results and results[0].get("search_type") == "semantic" else "keyword"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}
    query = request.get("query", "")
    top_k = request.get("top_k", 5)

    if not query:
        return {"success": False, "message": "请输入查询内容"}

    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT dc.id, dc.document_id, dc.chunk_text, d.filename
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.chunk_text ILIKE :query
                LIMIT :limit
            """), {"query": f"%{query}%", "limit": top_k})

            results = [{"chunk_id": r[0], "document_id": r[1],
                        "content": r[2][:500], "filename": r[3]} for r in result]

            return {"success": True, "results": results, "query": query}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============== 数据导出 API ==============

@app.get("/api/agent/export/hours-excel")
async def export_hours_excel(
    month: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """导出工时Excel"""
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username

    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        today = datetime.now().date()
        if not month:
            month = today.strftime("%Y-%m")
        month_start = datetime.strptime(month + "-01", "%Y-%m-%d").date()

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT dr.report_date, p.name as project_name, dwi.work_content,
                       dwi.hours_spent, dr.employee_name
                FROM daily_reports dr
                JOIN daily_work_items dwi ON dr.id = dwi.report_id
                LEFT JOIN projects p ON CAST(dwi.project_id AS INTEGER) = p.id
                WHERE dr.employee_id = :emp_id
                  AND dr.is_deleted = false
                  AND dr.report_date >= :start
                  AND dr.report_date <= :today
                ORDER BY dr.report_date DESC
            """), {"emp_id": employee_id, "start": month_start, "today": today})

            rows = []
            for r in result:
                rows.append({
                    "date": str(r[0]),
                    "project": r[1] or "其他",
                    "content": r[2],
                    "hours": float(r[3] or 0),
                    "employee": r[4]
                })

            return {"success": True, "data": rows, "month": month, "count": len(rows)}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============== 预测分析 API ==============

@app.get("/api/agent/predict/hours")
async def predict_month_hours(current_user: Dict = Depends(get_current_user)):
    """预测本月工时"""
    username = current_user.get("username")
    user_info = get_user_info_cache(username)
    employee_id = user_info.get("employee_id") if user_info else username

    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        today = datetime.now().date()
        month_start = today.replace(day=1)
        days_passed = today.day
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT COALESCE(SUM(dwi.hours_spent), 0)
                FROM daily_reports dr
                JOIN daily_work_items dwi ON dr.id = dwi.report_id
                WHERE dr.employee_id = :emp_id
                  AND dr.report_date >= :start
                  AND dr.report_date <= :today
            """), {"emp_id": employee_id, "start": month_start, "today": today})

            current_hours = float(result.fetchone()[0] or 0)

            # 预测：当前工时 / 已过天数 * 总天数
            predicted_hours = (current_hours / days_passed * days_in_month) if days_passed > 0 else 0
            daily_avg = current_hours / days_passed if days_passed > 0 else 0

            return {
                "success": True,
                "current_hours": round(current_hours, 1),
                "predicted_hours": round(predicted_hours, 1),
                "daily_avg": round(daily_avg, 1),
                "days_passed": days_passed,
                "days_in_month": days_in_month,
                "status": "normal" if predicted_hours < 160 else "warning"
            }

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============== 团队看板 API ==============

@app.get("/api/agent/team/hours-ranking")
async def get_team_hours_ranking(
    month: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """团队工时排名"""
    username = current_user.get("username")
    user_info = get_user_info_cache(username)

    # 仅管理员可访问
    if not user_info or user_info.get("role_id") != 11:
        raise HTTPException(status_code=403, detail="无权限访问")

    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        today = datetime.now().date()
        if not month:
            month = today.strftime("%Y-%m")
        month_start = datetime.strptime(month + "-01", "%Y-%m-%d").date()

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT dr.employee_name, p.department,
                       SUM(dwi.hours_spent) as total_hours,
                       COUNT(DISTINCT dr.id) as report_count
                FROM daily_reports dr
                JOIN daily_work_items dwi ON dr.id = dwi.report_id
                LEFT JOIN personnel p ON dr.employee_id = p.employee_id
                WHERE dr.is_deleted = false
                  AND dr.report_date >= :start
                  AND dr.report_date <= :today
                GROUP BY dr.employee_name, p.department
                ORDER BY total_hours DESC
                LIMIT 20
            """), {"start": month_start, "today": today})

            ranking = []
            for i, r in enumerate(result, 1):
                ranking.append({
                    "rank": i,
                    "name": r[0],
                    "department": r[1] or "未知",
                    "hours": float(r[2] or 0),
                    "report_count": r[3]
                })

            return {"success": True, "month": month, "ranking": ranking}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/agent/team/goals-progress")
async def get_team_goals_progress(current_user: Dict = Depends(get_current_user)):
    """团队目标进度"""
    username = current_user.get("username")
    user_info = get_user_info_cache(username)

    if not user_info or user_info.get("role_id") != 11:
        raise HTTPException(status_code=403, detail="无权限访问")

    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        month = datetime.now().strftime("%Y-%m")

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT user_name, title, progress_rate, status
                FROM monthly_goals
                WHERE is_deleted = false AND month = :month
                ORDER BY progress_rate ASC
            """), {"month": month})

            goals = []
            for r in result:
                goals.append({
                    "name": r[0],
                    "title": r[1],
                    "progress": float(r[2] or 0),
                    "status": r[3]
                })

            return {"success": True, "month": month, "goals": goals}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============== 会话存储 ==============

# 内存会话存储（生产环境用Redis）
_session_store: Dict[str, List] = {}

def get_session_history(session_id: str) -> List:
    """获取会话历史"""
    return _session_store.get(session_id, [])

def save_session_history(session_id: str, messages: List):
    """保存会话历史"""
    # 只保留最近10轮对话
    _session_store[session_id] = messages[-20:]


def generate_project_context(project_id: int, engine) -> str:
    """
    根据项目ID实时生成项目背景MD（方案C：查询时动态生成）

    Args:
        project_id: 项目ID
        engine: 数据库引擎

    Returns:
        项目背景MD字符串
    """
    from sqlalchemy import text as text

    context = ""

    with get_connection() as conn:
        # 1. 获取项目基本信息
        result = conn.execute(text("""
            SELECT id, name, leader, status, progress, start_date, end_date
            FROM projects
            WHERE id = :pid
        """), {"pid": project_id})

        project = result.fetchone()
        if not project:
            return ""

        # 2. 获取项目任务列表（只取最新版本）
        tasks_result = conn.execute(text("""
            WITH latest_version AS (
                SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
                FROM project_tasks
                WHERE project_id::integer = :pid AND is_deleted = false
            )
            SELECT task_id, task_name, assignee, status, progress, end_date, actual_end_date
            FROM project_tasks pt, latest_version lv
            WHERE pt.project_id::integer = :pid
              AND pt.is_deleted = false
              AND COALESCE(CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER), 0) = COALESCE(lv.max_ver, 0)
            ORDER BY task_id
        """), {"pid": project_id})

        tasks = []
        for row in tasks_result:
            tasks.append({
                "task_id": row[0],
                "task_name": row[1],
                "assignee": row[2],
                "status": row[3],
                "progress": row[4],
                "end_date": str(row[5]) if row[5] else None,
                "actual_end_date": str(row[6]) if row[6] else None
            })

        # 3. 统计任务状态
        completed = [t for t in tasks if t["status"] == "已完成"]
        ongoing = [t for t in tasks if t["status"] == "进行中"]
        delayed = [t for t in tasks if t["status"] == "延期"]

        # 4. 动态计算项目进度（与前端一致）
        total_tasks = len(tasks)
        completed_count = len(completed)
        avg_progress = sum(float(t["progress"] or 0) for t in tasks) / total_tasks if total_tasks > 0 else 0
        calculated_progress = round((completed_count / total_tasks * 100 + avg_progress) / 2, 1) if total_tasks > 0 else 0

        # 5. 生成MD
        context = f"""# 项目：{project[1]}

## 基本信息
- 项目ID: {project[0]}
- 项目名称: {project[1]}
- 负责人: **{project[2]}**
- 状态: {project[3]}
- 进度: {calculated_progress}%
- 开始日期: {project[5] or '未设置'}
- 结束日期: {project[6] or '未设置'}

## 任务统计
- 总任务数: {len(tasks)}
- 已完成: {len(completed)}
- 进行中: {len(ongoing)}
- 延期: {len(delayed)}

## 任务列表
"""
        for task in tasks[:10]:  # 只显示前10个任务
            context += f"- {task['task_id']}: {task['task_name']}（{task['assignee'] or '未分配'}，{task['status']}，{task['progress']}%）\n"

        if len(tasks) > 10:
            context += f"... 还有 {len(tasks) - 10} 个任务\n"

        if delayed:
            context += "\n## 延期任务\n"
            for task in delayed:
                context += f"- **{task['task_name']}**：截止日期 {task['end_date']}，当前进度 {task['progress']}%\n"

    return context


@app.post("/api/agent/chat")
@limiter.limit("10/minute")  # AI接口限流：每分钟最多10次
async def chat(
    request: Request,
    req: Dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    智能问答接口（支持多轮对话 + RAG文档检索）

    支持自然语言查询项目、任务、风险、工时、文档知识库等
    """
    message = request.get("message", "")
    session_id = request.get("session_id", "default")
    if not message:
        raise HTTPException(status_code=400, detail="请输入问题")

    try:
        # 获取用户信息
        username = current_user.get("username")
        user_info = get_user_info_cache(username)
        employee_name = user_info.get("name", username) if user_info else username

        # 获取会话历史
        session_key = f"{username}_{session_id}"
        history = get_session_history(session_key)

        # ========== 第一步：动态生成项目背景（方案C）==========
        # 根据问题关键词，实时查询相关项目信息
        project_context = ""
        project_names = []

        try:
            engine = get_db_engine()
            from sqlalchemy import text as text

            # 1. 提取项目关键词（智能提取）
            # 尝试多种关键词长度匹配
            keywords_to_try = []

            # 提取问题中可能的项目关键词（去掉常见问题词）
            question_words = ["负责人", "进度", "状态", "任务", "延期", "是谁", "是什么", "如何", "怎么样", "？", "?", "的"]
            cleaned_message = message
            for word in question_words:
                cleaned_message = cleaned_message.replace(word, "")

            # 尝试不同长度的关键词
            if len(cleaned_message) >= 10:
                keywords_to_try.append(cleaned_message[:10])  # 前10个字符
            if len(cleaned_message) >= 8:
                keywords_to_try.append(cleaned_message[:8])   # 前8个字符
            if len(cleaned_message) >= 5:
                keywords_to_try.append(cleaned_message[:5])   # 前5个字符

            # 2. 尝试匹配项目
            matched_projects = []
            with get_connection() as conn:
                for keyword in keywords_to_try:
                    result = conn.execute(text("""
                        SELECT id, name, leader, status, progress
                        FROM projects
                        WHERE is_deleted = false
                          AND name ILIKE :query
                        LIMIT 3
                    """), {"query": f"%{keyword}%"})

                    for row in result:
                        # 避免重复
                        if not any(p["id"] == row[0] for p in matched_projects):
                            matched_projects.append({
                                "id": row[0],
                                "name": row[1],
                                "leader": row[2],
                                "status": row[3],
                                "progress": row[4]
                            })
                            project_names.append(row[1])

                    if matched_projects:
                        break  # 找到匹配就停止

            # 3. 如果匹配到项目，动态生成项目背景
            for project in matched_projects:
                project_context += generate_project_context(project["id"], engine)

        except Exception as e:
            logger.error(f" {e}")

        # ========== 第二步：RAG文档检索（补充知识）==========
        rag_context = ""
        rag_sources = []

        try:
            with get_connection() as conn:
                # 从项目知识库检索上传的文档
                result = conn.execute(text("""
                    SELECT project_name, doc_name, content, summary
                    FROM project_knowledge_base
                    WHERE is_deleted = false
                      AND doc_name != '项目概况'
                      AND (content ILIKE :query OR summary ILIKE :query OR project_name ILIKE :query)
                    LIMIT 3
                """), {"query": f"%{message[:30]}%"})

                for row in result:
                    rag_context += f"\n【文档：{row[0]} - {row[1]}】\n{row[2][:500]}\n"
                    rag_sources.append(f"{row[0]} - {row[1]}")

        except Exception as e:
            logger.error(f" {e}")

        # ========== 第二步：意图识别与工具调用 ==========
        analysis_prompt = f"""你是一个项目管理助手的意图识别模块。

用户：{employee_name}
问题：{message}

{TOOL_DESCRIPTIONS}

请分析用户意图，以JSON格式返回：
{{
  "tool": "工具名称（如果问题与流程、规范、制度相关，返回'none'）",
  "params": {{参数对象}},
  "summary": "一句话说明你要查什么"
}}

只返回JSON，不要其他内容。"""

        # 构建消息列表（包含历史）
        messages = []
        for msg in history[-6:]:  # 最近3轮（6条消息）
            messages.append(msg)
        messages.append(HumanMessage(content=analysis_prompt))

        analysis_response = llm.invoke(messages)
        analysis_text = analysis_response.content.strip()

        # 解析JSON
        tool_name = "none"
        params = {}
        data = {}

        try:
            if "```json" in analysis_text:
                analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
            elif "```" in analysis_text:
                analysis_text = analysis_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(analysis_text)
            tool_name = analysis.get("tool", "none")
            params = analysis.get("params", {})
        except:
            pass

        # 执行工具（如果不是纯文档问题）
        if tool_name != "none":
            tool_result = execute_query(tool_name, params)
            data = json.loads(tool_result)

        # ========== 第三步：生成回答 ==========
        history_context = ""
        if history:
            history_context = "\n\n历史对话摘要：\n" + "\n".join([
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {m.content[:100]}..."
                for m in history[-4:]
            ])

        # 构建上下文部分（方案C：项目背景 + RAG文档 + 工具结果）
        context_parts = []

        # 1. 项目背景（动态生成）
        if project_context:
            context_parts.append(f"📊 **相关项目信息**：\n{project_context}")

        # 2. RAG文档（补充知识）
        if rag_context:
            context_parts.append(f"📚 **相关文档知识**：{rag_context}")

        # 3. 工具查询结果
        if data and isinstance(data, dict) and not data.get("error"):
            context_parts.append(f"🔎 **查询结果**：\n{json.dumps(data, ensure_ascii=False, indent=2)}")
        elif data and isinstance(data, list):
            context_parts.append(f"🔎 **查询结果**：\n{json.dumps(data, ensure_ascii=False, indent=2)}")

        context_str = "\n\n".join(context_parts) if context_parts else "（未找到相关数据）"

        answer_prompt = f"""你是项目管理助手，帮助用户解答问题。

用户：{employee_name}
问题：{message}
{history_context}

{context_str}

请用简洁的自然语言回答用户问题。要点：
1. 如果文档中有相关信息，优先基于文档回答
2. 补充数据库中的相关数据
3. 如有风险或异常，主动提示
4. 控制在3-5句话
5. 如果引用了文档，在回答末尾标注来源"""

        final_response = llm.invoke([HumanMessage(content=answer_prompt)])

        # 保存会话历史
        history.append(HumanMessage(content=message))
        history.append(final_response)
        save_session_history(session_key, history)

        return {
            "response": final_response.content,
            "session_id": session_id,
            "sources": rag_sources if rag_sources else None
        }

    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")

# ============== 定时任务调度 ==============

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

async def scheduled_morning_reminder():
    """早间提醒 - 08:00"""
    logger.info(f" 早间提醒 - {datetime.now()}")
    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            # 查询今日待办和延期任务
            result = conn.execute(text("""
                SELECT assignee_id, assignee, COUNT(*) as task_count
                FROM project_tasks
                WHERE is_deleted = false
                  AND (end_date = CURRENT_DATE OR end_date < CURRENT_DATE)
                  AND actual_end_date IS NULL
                  AND assignee_id IS NOT NULL
                GROUP BY assignee_id, assignee
            """))

            reminders = []
            for row in result:
                reminders.append({
                    "employee_id": row[0],
                    "employee_name": row[1],
                    "task_count": row[2]
                })

            logger.info(f" 需提醒{len(reminders)}人")
            return {"success": True, "count": len(reminders), "reminders": reminders}

    except Exception as e:
        logger.error(f" {e}")
        return {"success": False, "error": str(e)}

async def scheduled_evening_reminder():
    """晚间提醒 - 18:00"""
    logger.info(f" 晚间提醒 - {datetime.now()}")
    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            # 查询今日未填日报的人员
            result = conn.execute(text("""
                SELECT employee_id, name
                FROM personnel
                WHERE employee_id NOT IN (
                    SELECT employee_id FROM daily_reports
                    WHERE report_date = CURRENT_DATE AND is_deleted = false
                )
                AND is_deleted = false
            """))

            unreported = []
            for row in result:
                unreported.append({
                    "employee_id": row[0],
                    "name": row[1]
                })

            logger.info(f" {len(unreported)}人未填日报")
            return {"success": True, "count": len(unreported), "unreported": unreported}

    except Exception as e:
        logger.error(f" {e}")
        return {"success": False, "error": str(e)}

async def scheduled_risk_alert():
    """风险预警 - 09:00"""
    logger.info(f" 风险预警 - {datetime.now()}")
    try:
        # text 已从 database 模块导入
        engine = get_db_engine()

        with get_connection() as conn:
            # 查询高风险项目
            result = conn.execute(text("""
                SELECT p.id, p.name, p.leader,
                       COUNT(pt.task_id) as delayed_count
                FROM projects p
                JOIN project_tasks pt ON CAST(pt.project_id AS INTEGER) = p.id
                WHERE pt.is_deleted = false
                  AND pt.end_date < CURRENT_DATE
                  AND pt.actual_end_date IS NULL
                GROUP BY p.id, p.name, p.leader
                HAVING COUNT(pt.task_id) >= 3
                ORDER BY delayed_count DESC
            """))

            risks = []
            for row in result:
                risks.append({
                    "project_id": row[0],
                    "project_name": row[1],
                    "leader": row[2],
                    "delayed_count": row[3]
                })

            logger.info(f"[风险预警] {len(risks)}个项目高风险")
            return {"success": True, "count": len(risks), "risks": risks}

    except Exception as e:
        logger.error(f" {e}")
        return {"success": False, "error": str(e)}

# 手动触发API（测试用）
@app.post("/api/agent/scheduler/trigger/{task_name}")
async def trigger_scheduled_task(
    task_name: str,
    current_user: Dict = Depends(get_current_user)
):
    """手动触发定时任务（测试用）"""
    tasks = {
        "morning": scheduled_morning_reminder,
        "evening": scheduled_evening_reminder,
        "risk": scheduled_risk_alert
    }

    if task_name not in tasks:
        raise HTTPException(status_code=400, detail=f"未知任务: {task_name}")

    result = await tasks[task_name]()
    return result

@app.get("/api/agent/scheduler/jobs")
async def list_scheduled_jobs(current_user: Dict = Depends(get_current_user)):
    """列出所有定时任务"""
    jobs = scheduler.get_jobs()
    return {
        "jobs": [
            {
                "id": job.id,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }


# ========== 项目智能问答API ==========
# 存储项目对话历史
_project_session_store: Dict[str, List] = {}


@app.post("/api/agent/projects/{project_id}/chat")
async def project_chat(
    project_id: int,
    request: Dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    项目智能问答接口（数据隔离）

    只能查询当前项目相关的数据，确保数据安全
    """
    message = request.get("message", "")
    session_id = request.get("session_id", "default")

    if not message:
        raise HTTPException(status_code=400, detail="请输入问题")

    try:
        # 获取用户信息
        username = current_user.get("username")
        user_info = get_user_info_cache(username)
        employee_name = user_info.get("name", username) if user_info else username

        # 获取项目对话历史
        session_key = f"project_{project_id}_{username}_{session_id}"
        history = _project_session_store.get(session_key, [])

        # ========== 第一步：动态生成项目背景 ==========
        engine = get_db_engine()
        from sqlalchemy import text as text

        project_context = generate_project_context(project_id, engine)

        if not project_context:
            raise HTTPException(status_code=404, detail="项目不存在")

        # ========== 第二步：查询项目知识库 ==========
        rag_context = ""
        rag_sources = []

        try:
            with get_connection() as conn:
                result = conn.execute(text("""
                    SELECT doc_name, content
                    FROM project_knowledge_base
                    WHERE project_id = :pid
                      AND is_deleted = false
                      AND (content ILIKE :query OR doc_name ILIKE :query)
                    LIMIT 3
                """), {"pid": project_id, "query": f"%{message[:30]}%"})

                for row in result:
                    rag_context += f"\n【文档：{row[0]}】\n{row[1][:500]}\n"
                    rag_sources.append(row[0])
        except Exception as e:
            logger.error(f" {e}")

        # ========== 第三步：意图识别（限制在项目范围内）==========
        project_tool_descriptions = f"""
可用工具（仅限当前项目，project_id={project_id}）：
1. query_project_tasks(status) - 查询项目任务
   参数：status(任务状态：进行中/已完成/延期)

2. query_project_risks() - 查询项目风险

3. query_project_hours(employee_name) - 查询项目工时
   参数：employee_name(员工姓名)

4. none - 如果问题与项目数据无关，直接回答
"""

        analysis_prompt = f"""你是项目管理助手，专门回答关于项目【ID={project_id}】的问题。

用户：{employee_name}
问题：{message}

{project_tool_descriptions}

请分析用户意图，返回JSON：
{{
  "tool": "工具名称或none",
  "params": {{}}
}}
"""

        messages = history[-4:] + [HumanMessage(content=analysis_prompt)]
        analysis_response = llm.invoke(messages)
        analysis_text = analysis_response.content.strip()

        # 解析JSON
        tool_name = "none"
        params = {}
        data = {}

        try:
            if "```json" in analysis_text:
                analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
            elif "```" in analysis_text:
                analysis_text = analysis_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(analysis_text)
            tool_name = analysis.get("tool", "none")
            params = analysis.get("params", {})
        except Exception as e:
            logger.error(f" {e}")
            tool_name = "none"

        # ========== 第四步：执行工具（项目范围限制）==========
        if tool_name == "query_project_tasks":
            # 查询项目任务
            status_filter = params.get("status", "")

            with get_connection() as conn:
                sql = f"""
                    SELECT task_id, task_name, assignee, status, progress, end_date, actual_end_date
                    FROM project_tasks
                    WHERE CAST(project_id AS INTEGER) = {project_id}
                      AND is_deleted = false
                """

                if status_filter:
                    sql += f" AND status = '{status_filter}'"

                sql += " ORDER BY task_id"

                result = conn.execute(text(sql))
                tasks = []
                for row in result:
                    tasks.append({
                        "task_id": row[0],
                        "task_name": row[1],
                        "assignee": row[2],
                        "status": row[3],
                        "progress": float(row[4] or 0),
                        "end_date": str(row[5]) if row[5] else None,
                        "actual_end_date": str(row[6]) if row[6] else None
                    })

                data = {"tasks": tasks, "total": len(tasks)}

        elif tool_name == "query_project_risks":
            # 查询项目风险
            with get_connection() as conn:
                result = conn.execute(text("""
                    SELECT task_id, task_name, assignee, end_date,
                           CURRENT_DATE - end_date as delay_days
                    FROM project_tasks
                    WHERE CAST(project_id AS INTEGER) = :project_id
                      AND is_deleted = false
                      AND end_date < CURRENT_DATE
                      AND actual_end_date IS NULL
                    ORDER BY delay_days DESC
                """), {"project_id": project_id})

                risks = []
                for row in result:
                    risks.append({
                        "task_id": row[0],
                        "task_name": row[1],
                        "assignee": row[2],
                        "end_date": str(row[3]),
                        "delay_days": row[4]
                    })

                data = {"risks": risks, "total": len(risks)}

        elif tool_name == "query_project_hours":
            # 查询项目工时
            employee_name_filter = params.get("employee_name", "")

            with get_connection() as conn:
                sql = f"""
                    SELECT dwi.assignee, SUM(dwi.hours_spent) as total_hours
                    FROM daily_work_items dwi
                    JOIN daily_reports dr ON dwi.report_id = dr.id
                    WHERE dwi.project_id = {project_id}
                      AND dr.is_deleted = false
                """

                if employee_name_filter:
                    sql += f" AND dwi.assignee LIKE '%{employee_name_filter}%'"

                sql += " GROUP BY dwi.assignee ORDER BY total_hours DESC"

                result = conn.execute(text(sql))
                hours = []
                for row in result:
                    hours.append({
                        "assignee": row[0],
                        "hours": float(row[1] or 0)
                    })

                data = {"hours": hours, "total": len(hours)}

        # ========== 第五步：生成回答 ==========
        context_parts = []

        if project_context:
            context_parts.append(f"📊 **项目背景**：\n{project_context}")

        if rag_context:
            context_parts.append(f"📚 **项目文档**：{rag_context}")

        if data:
            context_parts.append(f"🔎 **查询结果**：\n{json.dumps(data, ensure_ascii=False, indent=2)}")

        context_str = "\n\n".join(context_parts)

        answer_prompt = f"""你是项目管理助手，专门回答关于当前项目的问题。

用户：{employee_name}
问题：{message}

{context_str}

请用简洁的自然语言回答。如果涉及具体数据，请准确引用。"""

        messages = history[-4:] + [HumanMessage(content=answer_prompt)]
        final_response = llm.invoke(messages)
        answer = final_response.content

        # 保存对话历史
        history.append(HumanMessage(content=message))
        history.append(AIMessage(content=answer))
        _project_session_store[session_key] = history[-20:]  # 保留最近10轮

        return {
            "success": True,
            "answer": answer,
            "sources": rag_sources,
            "tool_used": tool_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f" {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "answer": "抱歉，查询出现问题，请稍后重试。",
            "error": str(e)
        }

# 启动时初始化调度器和HTTP客户端
@app.on_event("startup")
async def startup_event():
    global http_client
    
    # 初始化数据库连接池
    engine = get_engine()
    logger.info("[Database] 连接池已初始化")
    
    # 初始化HTTP客户端
    http_client = httpx.AsyncClient(timeout=30.0)
    
    # 导入推送函数
    from .push_service import push_morning_alerts, push_afternoon_reminder

    # 早间高风险预警汇总 08:00
    scheduler.add_job(
        push_morning_alerts,
        CronTrigger(hour=8, minute=0),
        id="morning_alerts",
        replace_existing=True
    )

    # 下午日报提醒 16:00
    scheduler.add_job(
        push_afternoon_reminder,
        CronTrigger(hour=16, minute=0),
        id="afternoon_reminder",
        replace_existing=True
    )

    # 注：已删除凌晨1点的每日摘要推送，避免打扰用户
    # 早上的高风险预警汇总（8:00）已覆盖预警功能

    scheduler.start()
    logger.info("[调度器] 定时任务已启动（含每日预警检测）")
    logger.info("[HTTP客户端] 已初始化")

@app.on_event("shutdown")
async def shutdown_event():
    # 关闭HTTP客户端
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None
        logger.info("[HTTP客户端] 已关闭")
    
    # 释放数据库连接池
    dispose_engine()
    logger.info("[Database] 连接池已释放")

    scheduler.shutdown()
    logger.info("[调度器] 定时任务已停止")


# ============== 项目知识库 API ==============

from fastapi import UploadFile, File, Form
import shutil

@app.get("/api/agent/knowledge/stats")
async def get_knowledge_stats_api(
    project_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取知识库统计信息

    参数：
    - project_id: 项目ID（可选，不传则统计所有项目）
    """
    try:
        from app.knowledge_base import get_knowledge_stats
        stats = get_knowledge_stats(project_id)
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.get("/api/agent/knowledge/list")
async def get_knowledge_list_api(
    project_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    limit: int = 20,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取知识库文档列表

    参数：
    - project_id: 项目ID（可选）
    - doc_type: 文档类型（可选）
    - limit: 返回数量（默认20）
    """
    try:
        from app.knowledge_base import get_knowledge_list
        docs = get_knowledge_list(project_id, doc_type, limit)
        return {
            "success": True,
            "data": docs,
            "total": len(docs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@app.post("/api/agent/knowledge/upload")
async def upload_document_api(
    project_id: int = Form(...),
    project_name: str = Form(...),
    doc_name: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    上传文档到知识库

    参数：
    - project_id: 项目ID
    - project_name: 项目名称
    - doc_name: 文档名称
    - doc_type: 文档类型（需求文档/设计文档/会议纪要/技术方案）
    - file: 文件（支持PDF/Word/Txt）
    """
    try:
        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in ['.pdf', '.docx', '.doc', '.txt', '.md']:
            raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 PDF/Word/Txt/Markdown")

        # 读取文件内容
        file_content = await file.read()

        # 上传者信息
        uploader_id = current_user.get("employee_id", "0001")
        uploader_name = current_user.get("name", "admin")

        # 调用上传函数
        from app.knowledge_base import upload_document
        result = await upload_document(
            project_id=project_id,
            project_name=project_name,
            doc_name=doc_name,
            doc_type=doc_type,
            file_content=file_content,
            file_ext=file_ext,
            uploader_id=uploader_id,
            uploader_name=uploader_name
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.post("/api/agent/knowledge/query")
async def query_knowledge_api(
    request: Dict[str, Any],
    current_user: Dict = Depends(get_current_user)
):
    """
    基于知识库的智能问答

    请求体：
    {
        "question": "需求调研的结论是什么？",
        "project_id": 35  // 可选，不传则查询所有项目
    }
    """
    try:
        question = request.get("question")
        project_id = request.get("project_id")

        if not question:
            raise HTTPException(status_code=400, detail="请输入问题")

        from app.knowledge_base import query_knowledge
        result = await query_knowledge(question, project_id)

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.delete("/api/agent/knowledge/{doc_id}")
async def delete_document_api(
    doc_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    删除知识库文档（软删除）

    参数：
    - doc_id: 文档ID
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE project_knowledge_base
                SET is_deleted = true
                WHERE id = :doc_id
            """), {"doc_id": doc_id})
            conn.commit()

        return {
            "success": True,
            "message": "文档已删除"
        }

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ============== 项目追踪 API（三视图）===============

@app.get("/api/agent/tracking/execution")
async def get_tracking_execution(
    current_user: Dict = Depends(get_current_user)
):
    """
    追踪-执行视图：任务驱动
    
    返回：
    - 我的任务（今日/本周/本月）
    - 进行中任务
    - 近期完成
    """
    try:
        from .tracking_service import get_execution_view
        
        user_id = current_user.get("employee_id", "")
        user_name = current_user.get("name", "")
        role_id = current_user.get("role_id", 0)
        
        data = get_execution_view(user_id, user_name, role_id)
        
        return {"code": 200, "data": data}
    except Exception as e:
        logger.exception(f"获取执行视图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/agent/tracking/health")
async def get_tracking_health(
    current_user: Dict = Depends(get_current_user)
):
    """
    追踪-健康视图：风险雷达
    
    返回：
    - 五维度风险雷达
    - 高风险项目 TOP5
    - 趋势预警
    """
    try:
        from .tracking_service import get_health_view
        
        user_id = current_user.get("employee_id", "")
        role_id = current_user.get("role_id", 0)
        
        data = get_health_view(user_id, role_id)
        
        return {"code": 200, "data": data}
    except Exception as e:
        logger.exception(f"获取健康视图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/agent/tracking/trace")
async def get_tracking_trace(
    current_user: Dict = Depends(get_current_user)
):
    """
    追踪-溯源视图：数据血缘
    
    返回：
    - 关联率统计
    - 项目关联排行
    - 不可追溯项目
    """
    try:
        from .tracking_service import get_trace_view
        
        user_id = current_user.get("employee_id", "")
        role_id = current_user.get("role_id", 0)
        
        data = get_trace_view(user_id, role_id)
        
        return {"code": 200, "data": data}
    except Exception as e:
        logger.exception(f"获取溯源视图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ============== 公共看板 API（独立模块）===============

@app.get("/api/agent/dashboard/overview")
async def get_dashboard_overview_api(
    current_user: Dict = Depends(get_current_user)
):
    """
    获取公共看板概览数据

    返回：
    - 统计数据
    - 健康度排名
    - 最近预警
    """
    try:
        from .dashboard_service import get_dashboard_overview

        role = current_user.get("role", "user")
        user_id = current_user.get("id")

        data = get_dashboard_overview(role=role, user_id=user_id)
        return data

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@app.get("/api/agent/dashboard/projects")
async def get_dashboard_projects_api(
    current_user: Dict = Depends(get_current_user)
):
    """
    获取看板项目列表（含详细信息和任务数据）
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()        
        with get_connection() as conn:
            # 获取项目基本信息
            projects = conn.execute(text("""
                SELECT 
                    p.id, p.name, p.leader, p.status, p.progress,
                    p.start_date, p.end_date,
                    p.contract_amount, p.budget_total_cost, p.actual_total_cost
                FROM projects p
                WHERE p.is_deleted = false
                ORDER BY p.id
            """)).fetchall()
            
            result = []
            for p in projects:
                project_id = p[0]
                
                # 获取项目的最新版本任务（用于计算进度）
                tasks = conn.execute(text("""
                    SELECT 
                        task_id, task_name, start_date, end_date, 
                        actual_end_date, progress, status
                    FROM project_tasks
                    WHERE project_id = :pid
                    AND is_latest = true
                    AND is_deleted = false
                    AND end_date IS NOT NULL
                    ORDER BY end_date DESC
                """), {"pid": str(project_id)}).fetchall()
                
                # 确定项目结束时间：优先用项目 end_date，否则取最后一个任务的结束时间
                project_start_date = p[5]
                project_end_date = p[6]
                
                if not project_end_date and tasks:
                    # 取最后一个任务的结束时间
                    latest_task = tasks[0]  # 已按 end_date DESC 排序
                    project_end_date = latest_task[3]  # end_date
                
                # 确定项目开始时间：优先用项目 start_date，否则取第一个任务的开始时间
                if not project_start_date and tasks:
                    # 找最早的任务开始时间
                    task_starts = [t[2] for t in tasks if t[2]]
                    if task_starts:
                        project_start_date = min(task_starts)
                
                # 计算计划进度（基于时间：已过天数/总天数）
                today = datetime.now().date()
                
                if project_start_date and project_end_date:
                    start = datetime.strptime(str(project_start_date), '%Y-%m-%d').date() if isinstance(project_start_date, str) else project_start_date
                    end = datetime.strptime(str(project_end_date), '%Y-%m-%d').date() if isinstance(project_end_date, str) else project_end_date
                    
                    if today <= start:
                        planned_progress = 0.0
                    elif today >= end:
                        planned_progress = 100.0
                    else:
                        total_days = (end - start).days
                        elapsed_days = (today - start).days
                        planned_progress = round(elapsed_days / total_days * 100, 1) if total_days > 0 else 0
                else:
                    planned_progress = 0.0
                
                # 计算实际进度（按任务工期天数计算）
                # 与计划进度保持一致的时间维度
                total_tasks = len(tasks)
                
                if total_tasks > 0:
                    total_work_days = 0
                    completed_work_days = 0
                    
                    for t in tasks:
                        task_start = t[2]  # start_date
                        task_end = t[3]    # end_date
                        task_progress = float(t[5] or 0) / 100
                        
                        # 计算任务工期（天）
                        if task_start and task_end:
                            start_dt = task_start if isinstance(task_start, type(today)) else datetime.strptime(str(task_start), '%Y-%m-%d').date()
                            end_dt = task_end if isinstance(task_end, type(today)) else datetime.strptime(str(task_end), '%Y-%m-%d').date()
                            work_days = max((end_dt - start_dt).days, 1)  # 至少1天
                        else:
                            work_days = 5  # 默认5天
                        
                        total_work_days += work_days
                        
                        if task_progress >= 1.0:
                            # 已完成：计入完整工期
                            completed_work_days += work_days
                        elif task_end and task_end < today:
                            # 延期未完成：最高计50%
                            completed_work_days += work_days * min(task_progress, 0.5)
                        else:
                            # 进行中：按进度计入
                            completed_work_days += work_days * task_progress
                    
                    actual_progress = round(completed_work_days / total_work_days * 100, 1) if total_work_days > 0 else 0
                else:
                    # 无任务时，使用项目进度字段
                    actual_progress = float(p[4] or 0)
                
                # 取前10个任务用于显示
                display_tasks = tasks[:10] if len(tasks) > 10 else tasks
                
                # 获取项目预警
                alerts = conn.execute(text("""
                    SELECT alert_type, severity, title, content
                    FROM project_alerts
                    WHERE project_id = :pid
                    AND NOT is_resolved
                    ORDER BY 
                        CASE severity 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            ELSE 3 
                        END
                    LIMIT 3
                """), {"pid": project_id}).fetchall()
                
                result.append({
                    "id": project_id,
                    "name": p[1],
                    "leader": p[2],
                    "status": p[3],
                    "progress": float(p[4] or 0),
                    "planned_progress": planned_progress,
                    "actual_progress": actual_progress,
                    "start_date": str(project_start_date) if project_start_date else None,
                    "end_date": str(project_end_date) if project_end_date else None,
                    "contract_amount": float(p[7] or 0),
                    "budget_total_cost": float(p[8] or 0),
                    "actual_total_cost": float(p[9] or 0),
                    "tasks": [{
                        "task_id": t[0],
                        "task_name": t[1],
                        "start_date": str(t[2]) if t[2] else None,
                        "end_date": str(t[3]) if t[3] else None,
                        "actual_end_date": str(t[4]) if t[4] else None,
                        "progress": float(t[5] or 0),
                        "status": t[6]
                    } for t in display_tasks],
                    "alerts": [{
                        "type": a[0],
                        "severity": a[1],
                        "title": a[2],
                        "content": a[3]
                    } for a in alerts]
                })
            
            return result
    
    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/agent/dashboard/alerts")
async def get_dashboard_alerts_api(
    severity: str = None,
    project_id: int = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取预警列表

    参数：
    - severity: 按严重程度过滤 (high/medium/low)
    - project_id: 按项目过滤
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        load_dotenv()
        sql = """
            SELECT
                a.id, a.project_id, p.name as project_name,
                a.alert_type, a.severity, a.title, a.content, a.details,
                a.created_at, a.is_resolved, a.resolved_at
            FROM project_alerts a
            JOIN projects p ON p.id = a.project_id
            WHERE NOT a.is_resolved
        """
        params = {}

        if severity:
            sql += " AND a.severity = :severity"
            params["severity"] = severity

        if project_id:
            sql += " AND a.project_id = :project_id"
            params["project_id"] = project_id

        sql += " ORDER BY CASE a.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, a.created_at DESC"

        with get_connection() as conn:
            alerts = conn.execute(text(sql), params).fetchall()

            return [{
                "id": a[0],
                "project_id": a[1],
                "project_name": a[2],
                "alert_type": a[3],
                "severity": a[4],
                "title": a[5],
                "content": a[6],
                "details": a[7],
                "created_at": str(a[8]),
                "is_resolved": a[9],
                "resolved_at": str(a[10]) if a[10] else None
            } for a in alerts]

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.post("/api/agent/dashboard/alerts/{alert_id}/resolve")
async def resolve_alert_api(
    alert_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    标记预警已处理
    """
    try:
        from .dashboard_service import resolve_alert

        user_id = current_user.get("id")
        resolve_alert(alert_id, user_id)

        return {"success": True, "message": "预警已标记为已处理"}

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.get("/api/agent/dashboard/alert-rules")
async def get_alert_rules_api(
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    获取预警规则配置（仅 admin）
    """
    try:
        from .dashboard_service import get_alert_rules
        return get_alert_rules()

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.put("/api/agent/dashboard/alert-rules/{rule_id}")
async def update_alert_rule_api(
    rule_id: int,
    enabled: bool = None,
    thresholds: Dict = None,
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    更新预警规则配置（仅 admin）
    """
    try:
        from .dashboard_service import update_alert_rule
        update_alert_rule(rule_id, enabled, thresholds)
        return {"success": True, "message": "规则已更新"}

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@app.get("/api/agent/dashboard/health/{project_id}/trend")
async def get_health_trend_api(
    project_id: int,
    days: int = 30,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取项目健康度趋势
    """
    try:
        from .dashboard_service import get_project_health_trend
        return get_project_health_trend(project_id, days)

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/agent/dashboard/insight")
async def get_ai_insight_api(
    current_user: Dict = Depends(get_current_user)
):
    """
    获取 AI 洞察（按需生成）
    """
    try:
        # text 已从 database 模块导入
        from dotenv import load_dotenv
        from datetime import date

        load_dotenv()
        # 检查今日是否已生成
        with get_connection() as conn:
            existing = conn.execute(text("""
                SELECT content FROM ai_insights
                WHERE insight_date = :today
                ORDER BY created_at DESC
                LIMIT 1
            """), {"today": date.today()}).fetchone()

            if existing:
                return {"content": existing[0], "cached": True}

        # 生成新的洞察
        insight = await generate_ai_insight()

        # 保存洞察
        with get_connection() as conn:
            conn.execute(text("""
                INSERT INTO ai_insights (insight_date, role, content)
                VALUES (:today, :role, :content)
            """), {
                "today": date.today(),
                "role": current_user.get("role", "user"),
                "content": insight
            })
            conn.commit()

        return {"content": insight, "cached": False}

    except Exception as e:
        logger.error(f" {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


async def generate_ai_insight() -> str:
    """生成 AI 洞察（从进度、风险、成本三方面分析）"""
    # text 已从 database 模块导入
    from dotenv import load_dotenv
    from datetime import date
    
    load_dotenv()    
    with get_connection() as conn:
        # 获取项目进度统计
        progress_stats = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = '进行中') as ongoing,
                COUNT(*) FILTER (WHERE status = '已完成') as completed,
                AVG(progress) FILTER (WHERE status = '进行中') as avg_progress,
                COUNT(*) FILTER (WHERE progress < 50 AND status = '进行中') as low_progress
            FROM projects WHERE is_deleted = false
        """)).fetchone()
        
        # 获取风险统计
        risk_stats = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE severity = 'high' AND NOT is_resolved) as high,
                COUNT(*) FILTER (WHERE severity = 'medium' AND NOT is_resolved) as medium,
                COUNT(*) FILTER (WHERE severity = 'low' AND NOT is_resolved) as low
            FROM project_alerts
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)).fetchone()
        
        # 获取成本统计
        cost_stats = conn.execute(text("""
            SELECT 
                SUM(budget_total_cost) as total_budget,
                SUM(actual_total_cost) as total_actual,
                COUNT(*) FILTER (WHERE actual_total_cost > budget_total_cost * 1.1) as overspent
            FROM projects WHERE is_deleted = false
        """)).fetchone()
        
        # 获取延期项目
        delayed_projects = conn.execute(text("""
            SELECT name, progress 
            FROM projects 
            WHERE is_deleted = false 
            AND status = '进行中' 
            AND progress < 100
            ORDER BY progress ASC
            LIMIT 3
        """)).fetchall()
        
        # 获取高成本超支项目
        overspent_projects = conn.execute(text("""
            SELECT name, 
                   (actual_total_cost - budget_total_cost) as overspent,
                   (actual_total_cost / NULLIF(budget_total_cost, 0) * 100) as overspent_pct
            FROM projects 
            WHERE is_deleted = false 
            AND actual_total_cost > budget_total_cost * 1.1
            ORDER BY (actual_total_cost / NULLIF(budget_total_cost, 0)) DESC
            LIMIT 3
        """)).fetchall()
        
        # 获取已开始的进行中项目数（用于成本分析）
        started_projects_count = conn.execute(text("""
            SELECT COUNT(*) FROM projects 
            WHERE is_deleted = false 
            AND status = '进行中' 
            AND start_date <= CURRENT_DATE
        """)).fetchone()
    
    # 构建分析结果
    total = progress_stats[0] or 0
    ongoing = progress_stats[1] or 0
    completed = progress_stats[2] or 0
    avg_progress = float(progress_stats[3] or 0)
    low_progress = progress_stats[4] or 0
    
    high_risk = risk_stats[0] or 0
    medium_risk = risk_stats[1] or 0
    
    total_budget = float(cost_stats[0] or 0)
    total_actual = float(cost_stats[1] or 0)
    overspent = cost_stats[2] or 0
    started_count = started_projects_count[0] if started_projects_count else 0
    
    # 生成洞察内容
    lines = []
    
    # 项目进度分析
    lines.append(f"📊 【项目进度】进行中 {ongoing} 个，平均进度 {avg_progress:.1f}%，已完成 {completed} 个")
    if low_progress > 0:
        lines.append(f"   ⚠️ {low_progress} 个项目进度低于50%，需要加快")
    if delayed_projects:
        lines.append(f"   📌 低进度项目：{', '.join([f'{p[0]}({p[1]}%)' for p in delayed_projects])}")
    
    lines.append("")
    
    # 风险预警分析
    lines.append(f"🚨 【风险预警】高风险 {high_risk} 个，中风险 {medium_risk} 个")
    if high_risk > 0:
        lines.append("   ⚠️ 存在高风险预警，建议立即处理")
    else:
        lines.append("   ✅ 暂无高风险预警")
    
    lines.append("")
    
    # 成本支出分析
    lines.append("")
    if total_budget > 0:
        cost_rate = (total_actual / total_budget * 100)
        lines.append(f"💰 【成本支出】预算 ¥{total_budget/10000:.1f}万，实际支出 ¥{total_actual/10000:.1f}万（{cost_rate:.1f}%）")
        
        # 深度分析
        if total_actual == 0:
            if started_count > 0:
                lines.append("   ⚠️ 有进行中项目但无成本记录，可能存在数据缺失或成本未及时录入")
                lines.append("   📌 建议：检查项目成本填报情况，确保数据完整")
            else:
                lines.append("   📊 暂无成本支出，项目可能处于筹备阶段")
                lines.append("   📌 建议：关注项目启动后的成本录入")
        elif overspent > 0:
            lines.append(f"   ⚠️ {overspent} 个项目超支10%以上")
            if overspent_projects:
                lines.append(f"   📌 超支项目：{', '.join([f'{p[0]}(+{(p[2] or 0)-100:.0f}%)' for p in overspent_projects])}")
            lines.append("   📌 建议：加强成本管控，防止进一步超支")
        elif cost_rate < 50:
            lines.append("   ✅ 成本支出低于预算50%，项目进展初期或预算充足")
        else:
            lines.append("   ✅ 成本控制良好，支出在预算范围内")
    else:
        lines.append(f"💰 【成本支出】总支出 ¥{total_actual/10000:.1f}万")
        if total_actual == 0:
            lines.append("   📊 暂无成本数据，可能是新项目或数据未录入")
    
    lines.append("")
    
    # 总结建议
    lines.append("💡 【建议】")
    if low_progress > 0 or high_risk > 0:
        lines.append("   1. 关注低进度项目，协调资源加快进展")
        lines.append("   2. 优先处理高风险预警，降低项目风险")
    else:
        lines.append("   1. 各项目进展正常，继续保持")
    
    if overspent > 0:
        lines.append("   3. 加强成本管控，防止进一步超支")
    
    return "\n".join(lines)


@app.post("/api/agent/dashboard/run-detection")
async def run_detection_api(
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    手动触发预警检测（仅 admin）
    """
    try:
        from .dashboard_service import run_daily_alert_detection

        count = run_daily_alert_detection()

        return {
            "success": True,
            "message": f"已完成 {count} 个项目的预警检测"
        }

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@app.post("/api/agent/dashboard/test-push")
async def test_push_api(
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    测试推送（仅 admin）
    """
    try:
        from .push_service import push_to_wechat

        result = push_to_wechat(
            title="🔔 测试推送",
            content="<h3>推送测试成功</h3><p>这是一条来自项目智能体的测试消息</p>"
        )

        return {
            "success": result,
            "message": "推送成功" if result else "推送失败"
        }

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"推送失败: {str(e)}")


@app.post("/api/agent/dashboard/test-morning-push")
async def test_morning_push_api(
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    测试早上高风险预警推送（仅 admin）
    """
    try:
        from .push_service import push_morning_alerts

        result = push_morning_alerts()

        return {
            "success": result,
            "message": "推送成功" if result else "推送失败或无高风险预警"
        }

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"推送失败: {str(e)}")


@app.post("/api/agent/dashboard/test-afternoon-push")
async def test_afternoon_push_api(
    current_user: Dict = Depends(require_role(["admin"]))
):
    """
    测试下午日报提醒推送（仅 admin）
    """
    try:
        from .push_service import push_afternoon_reminder

        result = push_afternoon_reminder()

        return {
            "success": result,
            "message": "推送成功" if result else "推送失败"
        }

    except Exception as e:
        logger.error(f" {e}")
        raise HTTPException(status_code=500, detail=f"推送失败: {str(e)}")


# ============== 成本数据智能导入 ==============

@app.post("/api/agent/cost/import/analyze")
async def analyze_cost_excel(
    file: UploadFile = File(...),
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    分析Excel文件结构
    """
    try:
        from .cost_import import analyze_excel_structure
        
        content = await file.read()
        result = analyze_excel_structure(content, file.filename)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.post("/api/agent/cost/import/identify")
async def identify_cost_columns(
    request: dict,
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    AI识别列含义
    """
    try:
        from .cost_import import ai_identify_columns
        
        columns = request.get("columns", [])
        sample_data = request.get("sample_data", [])
        
        result = ai_identify_columns(columns, sample_data)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.post("/api/agent/cost/import/preview")
async def preview_cost_import(
    request: dict,
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    预览导入结果
    """
    try:
        from .cost_import import preview_import
        
        file_content = bytes(request.get("file_content", []))
        file_name = request.get("file_name", "")
        sheet_name = request.get("sheet_name", "")
        column_mapping = request.get("column_mapping", {})
        
        with get_connection() as conn:
            result = preview_import(file_content, file_name, sheet_name, column_mapping, conn)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


@app.post("/api/agent/cost/import/execute")
async def execute_cost_import(
    request: dict,
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    执行导入
    """
    try:
        from .cost_import import import_cost_data
        
        file_content = bytes(request.get("file_content", []))
        file_name = request.get("file_name", "")
        sheet_name = request.get("sheet_name", "")
        column_mapping = request.get("column_mapping", {})
        cost_type = request.get("cost_type", "")
        cost_subtype = request.get("cost_subtype", "")
        
        with get_connection() as conn:
            result = import_cost_data(
                file_content, file_name, sheet_name, 
                column_mapping, cost_type, cost_subtype, conn
            )
        
        return {
            "success": result["success"],
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@app.get("/api/agent/cost/types")
async def get_cost_types(
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    获取成本类型列表
    """
    try:
        with get_connection() as conn:
            # 间接成本类型
            indirect_result = conn.execute(text("""
                SELECT id, type_name, description 
                FROM indirect_cost_types 
                WHERE is_deleted = false
                ORDER BY id
            """))
            indirect_types = [dict(row._mapping) for row in indirect_result]
            
            # 外包服务类型
            outsourcing_result = conn.execute(text("""
                SELECT id, type_name, description 
                FROM outsourcing_service_types 
                WHERE is_deleted = false
                ORDER BY id
            """))
            outsourcing_types = [dict(row._mapping) for row in outsourcing_result]
        
        return {
            "success": True,
            "data": {
                "indirect": indirect_types,
                "outsourcing": outsourcing_types
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ============== 智能周报生成 ==============

# 数据库连接辅助函数（已废弃，改用 database 模块）
def get_db():
    """获取数据库引擎（使用 database 模块的全局单例）"""
    return get_engine()

@app.get("/api/agent/weekly-reports")
async def get_weekly_reports(
    page: int = 1,
    size: int = 10,
    project_id: str = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取周报列表
    """
    try:
        # text 已从 database 模块导入        
        # 获取当前用户
        username = current_user.get("username") or current_user.get("sub")
        employee_id = current_user.get("employee_id") or username
        
        offset = (page - 1) * size
        
        with get_connection() as conn:
            # 构建查询条件（只查询当前用户的周报）
            where_clause = "WHERE is_deleted = false AND created_by = :created_by"
            params = {"created_by": employee_id}
            
            if project_id:
                where_clause += " AND project_id = :project_id"
                params["project_id"] = project_id
            
            # 安全构建WHERE子句（只允许预定义条件）
            safe_where = where_clause if where_clause and where_clause.startswith("WHERE") else ""
            
            # 查询总数
            count_result = conn.execute(text(f"""
                SELECT COUNT(*) FROM weekly_reports {safe_where}
            """), params)
            total = count_result.fetchone()[0]
            
            # 查询列表
            params["offset"] = offset
            params["size"] = size
            result = conn.execute(text(f"""
                SELECT id, project_id, project_name, week_start, week_end, 
                       total_hours, task_count, created_at, created_by
                FROM weekly_reports
                {safe_where}
                ORDER BY week_start DESC
                OFFSET :offset LIMIT :size
            """), params)
            
            reports = []
            for row in result:
                reports.append({
                    "id": row[0],
                    "project_id": row[1],
                    "project_name": row[2],
                    "week_start": str(row[3]),
                    "week_end": str(row[4]),
                    "total_hours": float(row[5]) if row[5] else 0,
                    "task_count": row[6],
                    "created_at": str(row[7]) if row[7] else None,
                    "created_by": row[8]
                })
        
        return {
            "success": True,
            "data": {
                "items": reports,
                "total": total,
                "page": page,
                "size": size
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取周报列表失败: {str(e)}")


@app.post("/api/agent/weekly-reports/generate")
async def generate_weekly_report(
    request: dict,
    current_user: Dict = Depends(require_role(["admin", "project_manager"]))
):
    """
    生成智能周报（个人周报，只包含当前用户的日报数据）
    
    Args:
        project_id: 项目ID（可选，不传则生成全部项目周报）
        week_start: 周开始日期（可选，默认上周一）
        week_end: 周结束日期（可选，默认上周日）
    """
    try:
        project_id = request.get("project_id")
        
        # 获取当前用户信息
        username = current_user.get("username") or current_user.get("sub")
        employee_id = current_user.get("employee_id") or username
        
        # 计算上周日期范围
        today = datetime.now()
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = last_monday + timedelta(days=6)
        
        week_start = request.get("week_start", str(last_monday.date()))
        week_end = request.get("week_end", str(last_sunday.date()))
        
        # text 已从 database 模块导入        
        with get_connection() as conn:
            # 获取当前用户的日报数据
            if project_id:
                # 单个项目
                result = conn.execute(text("""
                    SELECT dr.report_date, dr.employee_name, dwi.project_id, 
                           dwi.project_name, dwi.task_id, dwi.task_name,
                           dwi.work_content, dwi.hours_spent, dwi.progress_percentage
                    FROM daily_reports dr
                    JOIN daily_work_items dwi ON dr.id = dwi.report_id
                    WHERE dr.report_date BETWEEN :week_start AND :week_end
                    AND dr.is_deleted = false
                    AND dr.employee_id = :employee_id
                    AND dwi.project_id = :project_id
                    ORDER BY dr.report_date, dr.employee_name
                """), {"week_start": week_start, "week_end": week_end, "employee_id": employee_id, "project_id": project_id})
            else:
                # 当前用户全部项目
                result = conn.execute(text("""
                    SELECT dr.report_date, dr.employee_name, dwi.project_id, 
                           dwi.project_name, dwi.task_id, dwi.task_name,
                           dwi.work_content, dwi.hours_spent, dwi.progress_percentage
                    FROM daily_reports dr
                    JOIN daily_work_items dwi ON dr.id = dwi.report_id
                    WHERE dr.report_date BETWEEN :week_start AND :week_end
                    AND dr.is_deleted = false
                    AND dr.employee_id = :employee_id
                    ORDER BY dwi.project_name, dr.report_date
                """), {"week_start": week_start, "week_end": week_end, "employee_id": employee_id})
            
            # 整理数据
            daily_data = []
            project_stats = {}
            
            for row in result:
                daily_data.append({
                    "date": str(row[0]),
                    "employee": row[1],
                    "project_id": row[2],
                    "project_name": row[3] or "未分配项目",
                    "task_id": row[4],
                    "task_name": row[5],
                    "content": row[6],
                    "hours": float(row[7]) if row[7] else 0,
                    "progress": float(row[8]) if row[8] else 0
                })
                
                # 统计项目数据
                pid = row[2] or "unknown"
                if pid not in project_stats:
                    project_stats[pid] = {
                        "name": row[3] or "未分配项目",
                        "total_hours": 0,
                        "task_count": 0
                    }
                project_stats[pid]["total_hours"] += float(row[7]) if row[7] else 0
                project_stats[pid]["task_count"] += 1
            
            if not daily_data:
                return {
                    "success": False,
                    "message": f"该时间段({week_start} ~ {week_end})没有日报数据"
                }
            
            # 使用 DeepSeek AI 生成周报摘要
            from langchain_deepseek import ChatDeepSeek
            
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            
            llm = ChatDeepSeek(
                model="deepseek-chat",
                api_key=api_key,
                temperature=0.3
            )
            
            # 准备提示词
            prompt = f"""根据以下日报数据，生成一份简洁专业的项目周报摘要。

时间范围：{week_start} 至 {week_end}

日报数据：
{json.dumps(daily_data[:50], ensure_ascii=False, indent=2)}
...（共 {len(daily_data)} 条记录）

项目统计：
{json.dumps(project_stats, ensure_ascii=False, indent=2)}

请生成周报，包含以下内容：
1. 本周工作概述（100字以内）
2. 各项目进展摘要（每个项目50字以内）
3. 下周重点关注事项（基于未完成任务和延期风险）
4. 整体工时统计

请直接返回JSON格式：
{{
    "summary": "本周工作概述...",
    "project_progress": [
        {{"name": "项目名", "progress": "进展描述", "hours": 工时}}
    ],
    "next_week_focus": ["事项1", "事项2"],
    "total_hours": 总工时,
    "highlights": ["亮点1", "亮点2"]
}}
"""

            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # 解析 AI 返回
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            ai_result = json.loads(content)
            
            # 保存到数据库
            username = current_user.get("username", "system")
            saved_reports = []
            
            for pid, stats in project_stats.items():
                if pid == "unknown":
                    continue
                    
                # 检查是否已存在
                existing = conn.execute(text("""
                    SELECT id FROM weekly_reports
                    WHERE project_id = :project_id AND week_start = :week_start
                    AND is_deleted = false
                """), {"project_id": pid, "week_start": week_start})
                
                if existing.fetchone():
                    # 更新
                    conn.execute(text("""
                        UPDATE weekly_reports
                        SET summary = :summary, total_hours = :hours,
                            task_count = :count, updated_at = NOW()
                        WHERE project_id = :project_id AND week_start = :week_start
                    """), {
                        "summary": ai_result.get("summary", ""),
                        "hours": stats["total_hours"],
                        "count": stats["task_count"],
                        "project_id": pid,
                        "week_start": week_start
                    })
                else:
                    # 新增
                    conn.execute(text("""
                        INSERT INTO weekly_reports
                        (project_id, project_name, week_start, week_end, summary,
                         total_hours, task_count, ai_analysis, created_at, created_by, is_deleted)
                        VALUES (:project_id, :project_name, :week_start, :week_end, :summary,
                         :hours, :count, :analysis, NOW(), :created_by, false)
                    """), {
                        "project_id": pid,
                        "project_name": stats["name"],
                        "week_start": week_start,
                        "week_end": week_end,
                        "summary": ai_result.get("summary", ""),
                        "hours": stats["total_hours"],
                        "count": stats["task_count"],
                        "analysis": json.dumps(ai_result, ensure_ascii=False),
                        "created_by": username
                    })
                
                saved_reports.append({
                    "project_id": pid,
                    "project_name": stats["name"],
                    "week_start": week_start,
                    "week_end": week_end,
                    "total_hours": stats["total_hours"],
                    "task_count": stats["task_count"]
                })
            
            conn.commit()
        
        return {
            "success": True,
            "data": {
                "week_start": week_start,
                "week_end": week_end,
                "reports": saved_reports,
                "ai_analysis": ai_result,
                "daily_count": len(daily_data)
            }
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI返回格式错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成周报失败: {str(e)}")


@app.get("/api/agent/weekly-reports/{report_id}")
async def get_weekly_report_detail(
    report_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取周报详情
    """
    try:
        # text 已从 database 模块导入        
        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT id, project_id, project_name, week_start, week_end,
                       summary, total_hours, task_count, ai_analysis,
                       created_at, created_by
                FROM weekly_reports
                WHERE id = :id AND is_deleted = false
            """), {"id": report_id})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="周报不存在")
            
            # 获取该周的日报明细
            daily_result = conn.execute(text("""
                SELECT dr.report_date, dr.employee_name, dwi.work_content, 
                       dwi.hours_spent, dwi.progress_percentage
                FROM daily_reports dr
                JOIN daily_work_items dwi ON dr.id = dwi.report_id
                WHERE dr.report_date BETWEEN :week_start AND :week_end
                AND dwi.project_id = :project_id
                AND dr.is_deleted = false
                ORDER BY dr.report_date
            """), {"week_start": str(row[3]), "week_end": str(row[4]), "project_id": row[1]})
            
            daily_items = []
            for d in daily_result:
                daily_items.append({
                    "date": str(d[0]),
                    "employee": d[1],
                    "content": d[2],
                    "hours": float(d[3]) if d[3] else 0,
                    "progress": float(d[4]) if d[4] else 0
                })
        
        return {
            "success": True,
            "data": {
                "id": row[0],
                "project_id": row[1],
                "project_name": row[2],
                "week_start": str(row[3]),
                "week_end": str(row[4]),
                "summary": row[5],
                "total_hours": float(row[6]) if row[6] else 0,
                "task_count": row[7],
                "ai_analysis": row[8] if row[8] else {},
                "created_at": str(row[9]) if row[9] else None,
                "created_by": row[10],
                "daily_items": daily_items
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取周报详情失败: {str(e)}")


# ============== 启动 ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)


# ============== Excel文件下载接口 ==============

@app.get("/api/agent/plans/file/{version_id}")
async def download_plan_file(version_id: int, current_user: Dict = Depends(get_current_user)):
    """
    下载/预览计划Excel文件
    
    返回文件流供前端SheetJS解析
    """
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT file_name, file_path 
            FROM project_plan_versions 
            WHERE id = :version_id
        """), {"version_id": version_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="版本不存在")
        
        file_name = result[0]
        file_path = result[1]
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在或已删除")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
