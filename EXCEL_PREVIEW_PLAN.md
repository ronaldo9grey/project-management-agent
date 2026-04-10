# Excel 在线查看方案

## 需求背景
- 用户上传Excel计划后，希望能在线查看原始文件
- 方便核对导入结果是否正确
- 符合日常工作习惯，无需额外安装

---

## 方案对比

### 方案一：纯前端方案 - SheetJS（推荐）

**技术**：`xlsx.js` (SheetJS 库)

**优点**：
- ✅ 纯前端实现，无需后端支持
- ✅ 开源免费，社区活跃
- ✅ 支持常见Excel格式（.xlsx, .xls）
- ✅ 可渲染为HTML表格
- ✅ 部署简单，无需额外配置

**缺点**：
- ⚠️ 复杂格式（合并单元格、甘特图）支持有限
- ⚠️ 样式无法100%还原

**实现示例**：
```tsx
import * as XLSX from 'xlsx'

function ExcelPreview({ fileUrl }: { fileUrl: string }) {
  const [data, setData] = useState<any[][]>([])
  
  useEffect(() => {
    fetch(fileUrl)
      .then(res => res.arrayBuffer())
      .then(buffer => {
        const workbook = XLSX.read(buffer)
        const sheet = workbook.Sheets[workbook.SheetNames[0]]
        const html = XLSX.utils.sheet_to_html(sheet)
        setData(html)
      })
  }, [fileUrl])
  
  return <div dangerouslySetInnerHTML={{ __html: data }} />
}
```

---

### 方案二：后端渲染 - Excel 转 HTML

**技术**：Python `openpyxl` + `pandas`

**优点**：
- ✅ 格式保持较好
- ✅ 支持复杂格式
- ✅ 可自定义渲染逻辑

**缺点**：
- ⚠️ 需要后端接口
- ⚠️ 大文件可能较慢

**实现示例**：
```python
@app.get("/api/agent/plans/preview/{file_id}")
async def preview_excel(file_id: int):
    # 读取Excel
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    
    # 转换为HTML
    html = "<table>"
    for row in ws.iter_rows():
        html += "<tr>"
        for cell in row:
            html += f"<td>{cell.value or ''}</td>"
        html += "</tr>"
    html += "</table>"
    
    return {"html": html}
```

---

### 方案三：混合方案（推荐）

**结合方案一和方案二**：
- 简单Excel：前端直接渲染（SheetJS）
- 复杂Excel（甘特图）：后端解析结构化数据

**实现架构**：
```
前端上传 → 后端存储 → 返回文件ID
                ↓
        解析Excel内容
                ↓
    ┌─────────┴─────────┐
    ↓                   ↓
前端预览(SheetJS)   结构化数据(任务列表)
```

---

## 推荐方案

### 🌟 方案：前端 SheetJS + 后端解析

#### 技术栈
- **前端**：`xlsx` 库 (SheetJS)
- **后端**：`openpyxl` (已有) + 新增预览接口

#### 功能设计

1. **上传后立即预览**
   - 用户上传Excel后，前端使用 SheetJS 直接渲染预览
   - 显示原始Excel内容，用户可核对

2. **后端解析确认**
   - 用户确认解析按钮
   - 后端使用 openpyxl 深度解析
   - 返回解析结果，用户再次确认

3. **版本记录关联**
   - 保存原始Excel文件
   - 版本记录中可重新查看

#### 实现步骤

**Step 1: 前端添加 SheetJS**
```bash
cd frontend
npm install xlsx
```

**Step 2: 创建预览组件**
```tsx
// ExcelPreview.tsx
import { useState } from 'react'
import * as XLSX from 'xlsx'

export function ExcelPreview({ file }: { file: File }) {
  const [preview, setPreview] = useState<string>('')
  
  const handlePreview = async () => {
    const data = await file.arrayBuffer()
    const workbook = XLSX.read(data)
    const sheet = workbook.Sheets[workbook.SheetNames[0]]
    const html = XLSX.utils.sheet_to_html(sheet, {
      editable: false,
    })
    setPreview(html)
  }
  
  return (
    <div>
      <button onClick={handlePreview}>预览Excel</button>
      <div dangerouslySetInnerHTML={{ __html: preview }} />
    </div>
  )
}
```

**Step 3: 后端保存原始文件**
```python
@app.post("/api/agent/plans/upload/{project_id}")
async def upload_plan(
    project_id: int,
    file: UploadFile,
    ...
):
    # 保存原始文件
    file_path = f"uploads/plans/{project_id}/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # 解析任务
    tasks = parse_excel(file_path)
    
    # 创建版本记录（关联文件路径）
    version = create_version(project_id, file.filename, file_path)
    
    return {"version_id": version.id, "file_path": file_path}
```

**Step 4: 后端预览接口**
```python
@app.get("/api/agent/plans/preview/{version_id}")
async def preview_excel(version_id: int):
    # 获取版本记录
    version = get_version(version_id)
    
    # 读取文件
    wb = openpyxl.load_workbook(version.file_path)
    
    # 转换为HTML（保留格式）
    html = excel_to_html(wb)
    
    return {"html": html}
```

---

## 成本评估

| 项目 | 工时 | 说明 |
|------|------|------|
| 前端预览组件 | 2h | SheetJS集成 |
| 后端预览接口 | 1h | Excel转HTML |
| 文件存储管理 | 1h | 上传/下载/删除 |
| UI交互优化 | 1h | 确认流程 |
| **总计** | **5h** | |

---

## 依赖项

**前端**：
```json
{
  "xlsx": "^0.18.5"
}
```

**后端**（已有）：
```
openpyxl==3.1.2
pandas==2.1.4
```

---

## 示例效果

```
┌─────────────────────────────────────────┐
│  📁 上传计划 - 项目：隆林铝厂空压机项目   │
├─────────────────────────────────────────┤
│                                         │
│  [选择文件] 隆林铝厂空压站进度表.xlsx      │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  📊 Excel预览（SheetJS渲染）       │ │
│  │  ┌─────┬──────┬──────┬─────────┐  │ │
│  │  │ 序号│任务名│开始  │结束     │  │ │
│  │  ├─────┼──────┼──────┼─────────┤  │ │
│  │  │ 1.1 │调研  │3/7   │3/7      │  │ │
│  │  │ 1.2 │方案  │3/14  │3/14     │  │ │
│  │  └─────┴──────┴──────┴─────────┘  │ │
│  └───────────────────────────────────┘ │
│                                         │
│  解析结果：                             │
│  ✅ 识别到31个任务                       │
│  ✅ 日期范围：2026-03-07 ~ 2026-12-31   │
│                                         │
│  [确认导入]  [重新选择]                  │
└─────────────────────────────────────────┘
```

---

## 建议

**推荐实施方案**：混合方案（前端SheetJS + 后端解析）

**理由**：
1. 用户体验好 - 上传后立即可见
2. 实现成本低 - SheetJS成熟稳定
3. 无需额外依赖 - 纯前端渲染
4. 可扩展性强 - 后端可深度解析复杂格式

**是否需要我开始实施？**
