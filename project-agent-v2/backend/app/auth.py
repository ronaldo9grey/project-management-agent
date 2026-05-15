"""
认证模块
提供JWT验证、用户认证等功能
"""
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from .config import settings
from .database import get_connection, text

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


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=8)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    """获取当前登录用户
    
    注意：JWT 本身是自包含的，不需要依赖内存缓存。
    每次请求都从 JWT 解析用户信息，避免多 worker 缓存不同步问题。
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="认证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 直接验证 JWT（不依赖缓存，避免多 worker 不同步）
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    # 获取用户信息，补充 employee_id
    username = payload.get("sub")
    if username:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            with get_connection() as conn:
                result = conn.execute(text("""
                    SELECT employee_id, name, department, position
                    FROM personnel WHERE employee_id = :username
                """), {"username": username}).fetchone()
                
                if result:
                    payload["employee_id"] = result[0]
                    payload["name"] = result[1]
                    payload["department"] = result[2]
                    payload["position"] = result[3]
        except Exception:
            pass
    
    return payload


def require_role(allowed_roles: List[str]):
    """角色权限检查装饰器"""
    async def role_checker(current_user: Dict = Depends(get_current_user)):
        username = current_user.get("username")

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT role FROM users WHERE username = :username
            """), {"username": username}).fetchone()

            user_role = result[0] if result else "user"

        # admin 判断：role=admin 或 role_id=11
        if "admin" in allowed_roles and (user_role == "admin" or current_user.get("role_id") == 11):
            return current_user

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：需要 {allowed_roles} 角色"
            )
        return current_user
    return role_checker
