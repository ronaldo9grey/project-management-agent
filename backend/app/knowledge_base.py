"""
项目知识库模块

功能：
1. 文档上传和管理
2. 智能问答（RAG）
3. 文档向量化
"""

import os
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
import httpx
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import PyPDF2
from docx import Document

# 加载环境变量
load_dotenv()

# 数据库连接
DB_URL = os.getenv("DATABASE_URL", "os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/project_cost_tracking")")

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

# 文档上传目录
UPLOAD_DIR = "/tmp/project-agent/knowledge"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def extract_text_from_pdf(file_path: str) -> str:
    """从PDF提取文本"""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"PDF提取失败: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """从Word文档提取文本"""
    try:
        doc = Document(file_path)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text.strip()
    except Exception as e:
        print(f"Word提取失败: {e}")
        return ""


def extract_text_from_file(file_path: str, file_ext: str) -> str:
    """根据文件类型提取文本"""
    if file_ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_ext in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    elif file_ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        return ""


async def generate_embedding(text: str) -> Optional[List[float]]:
    """
    生成文本向量（使用 BGE-base-zh-v1.5）
    
    暂时返回 None，后续可以集成向量模型
    """
    # TODO: 集成 BGE-base-zh-v1.5 向量模型
    # 这里暂时返回 None，不影响基本功能
    return None


async def generate_summary(text: str) -> str:
    """使用AI生成文档摘要"""
    if not text or len(text) < 100:
        return ""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个文档摘要助手，请用简洁的语言总结文档内容（不超过200字）。"
                        },
                        {
                            "role": "user",
                            "content": f"请总结以下文档内容：\n\n{text[:2000]}"  # 限制长度
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"生成摘要失败: {e}")
    
    return ""


async def upload_document(
    project_id: int,
    project_name: str,
    doc_name: str,
    doc_type: str,
    file_content: bytes,
    file_ext: str,
    uploader_id: str,
    uploader_name: str
) -> Dict[str, Any]:
    """
    上传文档到知识库
    
    参数：
    - project_id: 项目ID
    - project_name: 项目名称
    - doc_name: 文档名称
    - doc_type: 文档类型
    - file_content: 文件内容（字节）
    - file_ext: 文件扩展名（.pdf, .docx等）
    - uploader_id: 上传者ID
    - uploader_name: 上传者名称
    
    返回：上传结果
    """
    try:
        # 1. 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{timestamp}_{doc_name}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 2. 提取文本
        text_content = extract_text_from_file(file_path, file_ext)
        
        if not text_content:
            return {
                "success": False,
                "message": "无法提取文档内容，请检查文件格式"
            }
        
        # 3. 生成摘要
        summary = await generate_summary(text_content)
        
        # 4. 生成向量
        embedding = await generate_embedding(text_content)
        
        # 5. 存入数据库
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # 如果有向量，使用带向量的插入
            if embedding:
                result = conn.execute(text("""
                    INSERT INTO project_knowledge_base 
                    (project_id, project_name, doc_name, doc_type, file_path, 
                     file_size, content, summary, vector_embedding, uploader_id, uploader_name)
                    VALUES 
                    (:pid, :pname, :dname, :dtype, :fpath, :fsize, :content, :summary, 
                     :embedding, :uid, :uname)
                    RETURNING id
                """), {
                    "pid": project_id,
                    "pname": project_name,
                    "dname": doc_name,
                    "dtype": doc_type,
                    "fpath": file_path,
                    "fsize": len(file_content),
                    "content": text_content,
                    "summary": summary,
                    "embedding": str(embedding),
                    "uid": uploader_id,
                    "uname": uploader_name
                })
            else:
                # 没有向量时，不插入向量字段
                result = conn.execute(text("""
                    INSERT INTO project_knowledge_base 
                    (project_id, project_name, doc_name, doc_type, file_path, 
                     file_size, content, summary, uploader_id, uploader_name)
                    VALUES 
                    (:pid, :pname, :dname, :dtype, :fpath, :fsize, :content, :summary,
                     :uid, :uname)
                    RETURNING id
                """), {
                    "pid": project_id,
                    "pname": project_name,
                    "dname": doc_name,
                    "dtype": doc_type,
                    "fpath": file_path,
                    "fsize": len(file_content),
                    "content": text_content,
                    "summary": summary,
                    "uid": uploader_id,
                    "uname": uploader_name
                })
            
            doc_id = result.fetchone()[0]
            conn.commit()
        
        return {
            "success": True,
            "message": "文档上传成功",
            "doc_id": doc_id,
            "doc_name": doc_name,
            "summary": summary
        }
        
    except Exception as e:
        print(f"文档上传失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"上传失败: {str(e)}"
        }


async def query_knowledge(
    question: str,
    project_id: Optional[int] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    基于知识库的智能问答
    
    参数：
    - question: 用户问题
    - project_id: 项目ID（可选，不传则查询所有项目）
    - top_k: 返回的相关文档数量
    
    返回：答案和相关文档
    """
    try:
        engine = create_engine(DB_URL)
        
        # 1. 查询相关文档（暂时返回项目所有文档，后续可改用向量搜索）
        with engine.connect() as conn:
            if project_id:
                # 查询特定项目的文档
                result = conn.execute(text("""
                    SELECT id, project_id, project_name, doc_name, doc_type, 
                           content, summary
                    FROM project_knowledge_base
                    WHERE project_id = :pid
                      AND is_deleted = false
                    ORDER BY upload_time DESC
                    LIMIT :limit
                """), {
                    "pid": project_id,
                    "limit": top_k
                })
            else:
                # 查询所有项目的文档
                result = conn.execute(text("""
                    SELECT id, project_id, project_name, doc_name, doc_type, 
                           content, summary
                    FROM project_knowledge_base
                    WHERE is_deleted = false
                    ORDER BY upload_time DESC
                    LIMIT :limit
                """), {
                    "limit": top_k
                })
            
            docs = []
            for row in result:
                docs.append({
                    "id": row[0],
                    "project_id": row[1],
                    "project_name": row[2],
                    "doc_name": row[3],
                    "doc_type": row[4],
                    "content": row[5][:500],  # 只返回前500字符
                    "summary": row[6]
                })
        
        # 2. 如果没有找到相关文档，使用通用AI回答
        if not docs:
            # 即使没有文档，也使用AI回答问题
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{DEEPSEEK_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一个项目管理助手，请尽可能回答用户的问题。如果问题涉及项目具体情况，可以提示用户上传相关文档获取更准确的答案。"
                            },
                            {
                                "role": "user",
                                "content": question
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return {
                        "answer": answer,
                        "documents": [],
                        "source": "ai_general",
                        "hint": "💡 提示：上传项目文档可获取更精准的答案"
                    }
            
            return {
                "answer": "抱歉，AI服务暂时不可用，请稍后重试。",
                "documents": [],
                "source": "error"
            }
        
        # 3. 使用AI生成答案
        context = "\n\n".join([
            f"【{doc['doc_name']}】\n{doc['content']}"
            for doc in docs[:3]  # 只使用前3个文档
        ])
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个项目知识库助手，请基于提供的文档内容回答问题。如果文档中没有相关信息，请如实说明。"
                        },
                        {
                            "role": "user",
                            "content": f"参考文档：\n{context}\n\n问题：{question}"
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                answer = "抱歉，生成答案时出现错误。"
        
        return {
            "answer": answer,
            "documents": docs,
            "source": "knowledge_base"
        }
        
    except Exception as e:
        print(f"知识库问答失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": f"查询失败: {str(e)}",
            "documents": [],
            "source": "error"
        }


def get_knowledge_list(
    project_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    获取知识库文档列表
    
    参数：
    - project_id: 项目ID（可选）
    - doc_type: 文档类型（可选）
    - limit: 返回数量
    
    返回：文档列表
    """
    try:
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # 构建查询条件
            conditions = ["is_deleted = false"]
            params = {}
            
            if project_id:
                conditions.append("project_id = :pid")
                params["pid"] = project_id
            
            if doc_type:
                conditions.append("doc_type = :dtype")
                params["dtype"] = doc_type
            
            where_clause = " AND ".join(conditions)
            
            result = conn.execute(text(f"""
                SELECT id, project_id, project_name, doc_name, doc_type,
                       file_size, summary, upload_time, uploader_name
                FROM project_knowledge_base
                WHERE {where_clause}
                ORDER BY upload_time DESC
                LIMIT :limit
            """), {**params, "limit": limit})
            
            docs = []
            for row in result:
                docs.append({
                    "id": row[0],
                    "project_id": row[1],
                    "project_name": row[2],
                    "doc_name": row[3],
                    "doc_type": row[4],
                    "file_size": row[5],
                    "summary": row[6],
                    "upload_time": str(row[7]) if row[7] else None,
                    "uploader_name": row[8]
                })
            
            return docs
            
    except Exception as e:
        print(f"获取知识库列表失败: {e}")
        return []


def get_knowledge_stats(project_id: Optional[int] = None) -> Dict[str, Any]:
    """
    获取知识库统计信息
    
    参数：
    - project_id: 项目ID（可选）
    
    返回：统计信息
    """
    try:
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            if project_id:
                # 统计特定项目
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_docs,
                        COUNT(DISTINCT doc_type) as doc_types
                    FROM project_knowledge_base
                    WHERE project_id = :pid AND is_deleted = false
                """), {"pid": project_id})
            else:
                # 统计所有项目
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_docs,
                        COUNT(DISTINCT project_id) as projects,
                        COUNT(DISTINCT doc_type) as doc_types
                    FROM project_knowledge_base
                    WHERE is_deleted = false
                """))
            
            row = result.fetchone()
            
            return {
                "total_docs": row[0] or 0,
                "projects": row[1] if len(row) > 1 else 0,
                "doc_types": row[2] if len(row) > 2 else 0
            }
            
    except Exception as e:
        print(f"获取统计信息失败: {e}")
        return {
            "total_docs": 0,
            "projects": 0,
            "doc_types": 0
        }
