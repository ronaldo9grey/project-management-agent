"""
Excel文件下载接口
"""
import os
from fastapi import HTTPException, Depends
from fastapi.responses import FileResponse
from typing import Dict

def register_excel_download_api(app):
    """注册Excel文件下载接口"""
    
    @app.get("/api/agent/plans/file/{version_id}")
    async def download_plan_file(
        version_id: int,
        current_user: Dict = Depends(lambda: None)  # 简化认证
    ):
        """
        下载/预览计划Excel文件
        
        返回文件流供前端SheetJS解析
        """
        from sqlalchemy import create_engine, text
        from dotenv import load_dotenv
        
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
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
            
            # 返回文件
            return FileResponse(
                path=file_path,
                filename=file_name,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
