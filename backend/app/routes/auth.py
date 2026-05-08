"""
认证相关API路由
包括：登录、获取用户信息、刷新token、更新推送token
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict
from datetime import timedelta
import jwt

from ..config import settings
from ..database import get_connection, text
from ..logger import logger
from ..auth import (
    get_current_user,
    get_user_info,
    store_user_token,
    get_user_token,
    get_user_info_cache,
    create_access_token,
    cache_manager
)
from ..limiter import limiter

router = APIRouter(prefix="/api/agent/auth", tags=["认证"])


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    登录接口 - 代理到现有后端认证
    用户名/密码与现有管理系统一致
    """
    from ..http_client import http_client
    
    try:
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

            response_data = data.get("data", data)
            token = response_data.get("access_token") or response_data.get("token")

            if token:
                try:
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    user_key = payload.get("sub") or form_data.username
                except:
                    user_key = form_data.username

                user_info = await get_user_info(token)
                logger.debug(f"用户信息: {user_info}")

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
            raise HTTPException(status_code=401, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail="登录服务异常")


@router.get("/me")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """获取当前用户详细信息（含角色、部门、岗位）"""
    try:
        username = current_user.get("username")

        with get_connection() as conn:
            result = conn.execute(text("""
                SELECT id, username, role FROM users WHERE username = :username
            """), {"username": username}).fetchone()

            if result:
                current_user["id"] = result[0]
                current_user["role"] = result[2] or "user"

            person_result = conn.execute(text("""
                SELECT name, department, position, phone, email
                FROM personnel WHERE employee_id = :username
            """), {"username": username}).fetchone()

            if person_result:
                current_user["name"] = person_result[0] or username
                current_user["department"] = person_result[1] or ""
                current_user["position"] = person_result[2] or ""
                current_user["phone"] = person_result[3] or ""
                current_user["email"] = person_result[4] or ""

        return current_user
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        current_user["role"] = "user"
        return current_user


@router.post("/refresh")
async def refresh_token(current_user: Dict = Depends(get_current_user)):
    """
    刷新 Token - 基于当前JWT生成新token
    前端检测到 token 即将过期时自动调用
    """
    try:
        username = current_user.get("username") or current_user.get("sub")
        user_id = current_user.get("user_id") or current_user.get("employee_id")
        
        if not username:
            raise HTTPException(status_code=401, detail="无效的用户信息")
        
        access_token_expires = timedelta(hours=8)
        new_token = create_access_token(
            data={"sub": username, "user_id": user_id},
            expires_delta=access_token_expires
        )
        
        try:
            store_user_token(username, new_token)
        except:
            pass
        
        user_info = get_user_info_cache(username)
        if not user_info:
            try:
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
                        cache_manager.store_user_info(username, user_info)
            except Exception as e:
                logger.warning(f"获取用户信息失败: {e}")
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "name": user_info.get("name") if user_info else username,
                "username": username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"刷新token失败: {e}")
        raise HTTPException(status_code=401, detail="刷新token失败")


@router.put("/push-token")
async def update_push_token(
    push_token: str = None,
    current_user: Dict = Depends(get_current_user)
):
    """更新用户的微信推送Token"""
    try:
        username = current_user.get("username")
        
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE users SET push_token = :token WHERE username = :username
            """), {"token": push_token, "username": username})
            conn.commit()
        
        return {"success": True, "message": "推送Token已更新"}
    
    except Exception as e:
        logger.error(f"更新推送Token失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
