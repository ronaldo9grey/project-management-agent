# 项目管家智能体 - 知识库功能实现记录

## 功能概述

将项目详情页的"风险雷达"替换为"项目知识库"，支持：
1. 文档上传和管理（PDF/Word/Txt/Markdown）
2. 智能问答（RAG）
3. 跨项目查询

## 已完成 ✅

### 1. 项目名称修改 ✅
- 所有前端页面标题已改为"项目管家智能体"

### 2. 数据库表创建 ✅
```sql
project_knowledge_base (
  id, project_id, project_name, doc_name, doc_type,
  file_path, file_size, content, summary, 
  vector_embedding, upload_time, uploader_id, uploader_name
)
```

### 3. 后端模块实现 ✅
- `knowledge_base.py`: 核心功能模块
  - ✅ 文档上传（支持PDF/Word/Txt/Markdown）
  - ✅ 文本提取
  - ✅ AI摘要生成（DeepSeek API）
  - ✅ 智能问答（RAG）
  - ✅ 知识库列表和统计

### 4. API端点 ✅
- `GET /api/agent/knowledge/stats` - 统计信息
- `GET /api/agent/knowledge/list` - 文档列表
- `POST /api/agent/knowledge/upload` - 文档上传
- `POST /api/agent/knowledge/query` - 智能问答
- `DELETE /api/agent/knowledge/{doc_id}` - 删除文档

### 5. 前端组件 ✅
- ✅ 知识库卡片（替换风险雷达）
- ✅ 文档分类统计
- ✅ 智能问答输入框
- ✅ 文档上传模态框
- ✅ 最近文档列表

### 6. 功能验证 ✅
```bash
# 上传测试文档
curl -X POST "http://localhost:3000/api/agent/knowledge/upload" \
  -F "project_id=35" \
  -F "project_name=Demo项目-智能计划管理系统" \
  -F "doc_name=需求调研报告" \
  -F "doc_type=需求文档" \
  -F "file=@/tmp/test_knowledge.md"
# 响应: {"success": true, "doc_id": 1}

# 智能问答
curl -X POST "http://localhost:3000/api/agent/knowledge/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "需求调研的结论是什么？", "project_id": 35}'
# 响应: AI基于文档内容回答问题

# 跨项目查询
curl -X POST "http://localhost:3000/api/agent/knowledge/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "哪个项目评估效果最好？"}'
# 响应: "Demo项目-智能计划管理系统在同类项目中评估效果最好"
```

## 技术栈

- 文档解析：PyPDF2, python-docx
- 向量模型：BGE-base-zh-v1.5（待集成）
- LLM：DeepSeek API
- 存储：PostgreSQL + pgvector

## 使用场景

### 场景1：项目详情页
用户在项目35页面提问："需求调研的结论是什么？"
→ 只查询项目35的文档
→ AI基于该项目文档回答

### 场景2：全局查询
用户在首页提问："哪个项目评估效果最好？"
→ 查询所有项目文档
→ AI分析后给出对比答案

## 配置文件

### `.env`
```bash
# 工作时间配置
WORK_TIME_MORNING_START=08:15
WORK_TIME_MORNING_END=12:00
WORK_TIME_AFTERNOON_START=13:45
WORK_TIME_AFTERNOON_END=18:00
WORK_HOURS_PER_DAY=8.0
```

### `work_time_config.py`
- 标准工作日时长计算（8小时）
- 上午：08:15-12:00（3.75h）
- 下午：13:45-18:00（4.25h）
- 自动扣除午休时间

## 下一步（可选增强）

1. **BGE向量模型集成** - 增强搜索准确性
2. **文档预览功能** - 在线查看文档内容
3. **批量上传** - 支持多文件上传
4. **权限管理** - 文档访问控制

## 访问地址

- 前端: http://175.178.40.53/agent/
- 项目详情: http://175.178.40.53/agent/projects/35
- 知识库API: http://localhost:3000/api/agent/knowledge/
