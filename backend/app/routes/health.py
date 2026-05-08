"""
健康检查API路由
最简单的模块，用于验证拆分可行性
"""
from fastapi import APIRouter
from datetime import datetime
import os

router = APIRouter(tags=["系统"])


@router.get("/health")
async def health_check():
    """
    健康检查接口
    验证服务是否正常运行
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "project-agent-backend",
        "version": "1.0.0"
    }


@router.get("/")
async def root():
    """根路径 - API文档入口"""
    return {
        "message": "项目智能体API服务",
        "docs": "/docs",
        "health": "/health"
    }