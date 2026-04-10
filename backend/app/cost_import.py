"""
成本数据智能导入模块
支持Excel上传、AI识别、自动匹配项目、写入成本表
"""

import pandas as pd
import numpy as np
from io import BytesIO
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage
import json
import os

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 成本类型关键词映射
COST_TYPE_KEYWORDS = {
    # 间接成本类型
    "indirect": {
        "差旅费": ["交通", "住宿", "机票", "火车", "出差", "差旅", "打车", "高铁"],
        "运输费": ["物流", "运输", "货运", "快递", "配送"],
        "管理费分摊": ["管理费", "分摊", "行政"],
        "中介机构费": ["中介", "咨询", "审计", "律师", "代理", "评估"],
        "车辆使用费": ["车辆", "油费", "过路费", "停车", "维修", "保养"],
        "通讯费": ["电话", "通讯", "网络", "流量", "话费"],
        "招待费": ["招待", "餐费", "宴请", "接待"],
        "办公费": ["办公", "文具", "耗材", "打印", "纸张"],
        "维修费": ["维修", "保养", "修理", "维护"]
    },
    # 外包服务类型
    "outsourcing": {
        "施工安装": ["施工", "安装", "调试", "实施", "现场", "工程"],
        "设计编程部分（外协）": ["设计", "编程", "开发", "软件", "技术", "编码"],
        "其他": ["其他", "杂项"]
    },
    # 材料成本关键词
    "material": ["材料", "设备", "配件", "零件", "原材料", "采购", "物资", "器件", "元件"]
}


def analyze_excel_structure(file_content: bytes, file_name: str) -> Dict[str, Any]:
    """
    分析Excel文件结构
    
    Args:
        file_content: 文件二进制内容
        file_name: 文件名
        
    Returns:
        {
            "sheets": [工作表名列表],
            "columns": {sheet_name: [列名列表]},
            "sample_data": {sheet_name: [前5行数据]},
            "row_count": {sheet_name: 行数}
        }
    """
    try:
        # 读取Excel
        df_dict = pd.read_excel(BytesIO(file_content), sheet_name=None)
        
        if df_dict is None or len(df_dict) == 0:
            raise Exception("Excel文件为空或无法解析，请检查文件格式")
        
        result = {
            "sheets": list(df_dict.keys()),
            "columns": {},
            "sample_data": {},
            "row_count": {}
        }
        
        for sheet_name, df in df_dict.items():
            # 处理列名，确保都是字符串
            columns = [str(c) if not pd.isna(c) else f"列{i+1}" for i, c in enumerate(df.columns)]
            result["columns"][sheet_name] = columns
            
            # 重命名 DataFrame 列
            df.columns = columns
            
            # 处理 NaN 值，替换为 None
            sample = df.head(5).to_dict(orient='records')
            cleaned_sample = []
            for row in sample:
                cleaned_row = {}
                for k, v in row.items():
                    if pd.isna(v):
                        cleaned_row[k] = None
                    elif isinstance(v, float):
                        if not np.isfinite(v):
                            cleaned_row[k] = None
                        else:
                            cleaned_row[k] = v
                    else:
                        cleaned_row[k] = v
                cleaned_sample.append(cleaned_row)
            result["sample_data"][sheet_name] = cleaned_sample
            result["row_count"][sheet_name] = len(df)
        
        return result
        
    except Exception as e:
        raise Exception(f"解析Excel失败: {str(e)}")


def ai_identify_columns(columns: List[str], sample_data: List[Dict]) -> Dict[str, Any]:
    """
    使用AI识别列含义
    
    Args:
        columns: 列名列表
        sample_data: 样例数据
        
    Returns:
        {
            "project_column": "项目名/编号所在列",
            "amount_column": "金额所在列",
            "cost_type": "material/outsourcing/indirect",
            "cost_subtype": "具体类型",
            "date_column": "日期列（可选）",
            "description_column": "描述列（可选）",
            "confidence": 0.0-1.0
        }
    """
    llm = ChatDeepSeek(
        model="deepseek-chat",
        api_key=DEEPSEEK_API_KEY,
        temperature=0.1
    )
    
    prompt = f"""分析以下Excel数据，识别各列的含义：

列名：{json.dumps(columns, ensure_ascii=False)}

样例数据（前5行）：
{json.dumps(sample_data[:5], ensure_ascii=False, indent=2)}

请识别：
1. project_column: 项目名或项目编号所在的列名（可能叫"项目名"、"项目名称"、"项目编号"、"工程名称"等）
2. amount_column: 金额所在的列名（可能叫"金额"、"费用"、"成本"、"总价"等）
3. cost_type: 成本大类，只能是以下之一：
   - "material" (材料成本：原材料、设备、配件等)
   - "outsourcing" (外包成本：施工、设计、技术服务等)
   - "indirect" (间接成本：差旅、办公、管理等费用)
4. cost_subtype: 具体成本类型（如"差旅费"、"施工安装"等，如果是材料成本则填"材料"）
5. date_column: 日期列名（如果有的话）
6. description_column: 描述/备注列名（如果有的话）
7. quantity_column: 数量列名（如果有的话）
8. unit_price_column: 单价列名（如果有的话）

请直接返回JSON格式，不要有其他内容：
{{
    "project_column": "列名",
    "amount_column": "列名",
    "cost_type": "material/outsourcing/indirect",
    "cost_subtype": "具体类型",
    "date_column": "列名或null",
    "description_column": "列名或null",
    "quantity_column": "列名或null",
    "unit_price_column": "列名或null",
    "confidence": 0.95
}}
"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # 提取JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        return result
        
    except Exception as e:
        # AI识别失败，尝试规则匹配
        return rule_based_identify(columns, sample_data)


def rule_based_identify(columns: List[str], sample_data: List[Dict]) -> Dict[str, Any]:
    """
    基于规则的列识别（AI失败的备选方案）
    """
    result = {
        "project_column": None,
        "amount_column": None,
        "cost_type": None,
        "cost_subtype": None,
        "date_column": None,
        "description_column": None,
        "quantity_column": None,
        "unit_price_column": None,
        "confidence": 0.5
    }
    
    # 项目列关键词
    project_keywords = ["项目", "工程", "合同"]
    for col in columns:
        if any(kw in str(col) for kw in project_keywords):
            result["project_column"] = col
            break
    
    # 金额列关键词
    amount_keywords = ["金额", "费用", "成本", "总价", "合计", "总额"]
    for col in columns:
        if any(kw in str(col) for kw in amount_keywords):
            result["amount_column"] = col
            break
    
    # 日期列关键词
    date_keywords = ["日期", "时间", "月份", "年月"]
    for col in columns:
        if any(kw in str(col) for kw in date_keywords):
            result["date_column"] = col
            break
    
    # 描述列关键词
    desc_keywords = ["描述", "备注", "说明", "内容", "摘要"]
    for col in columns:
        if any(kw in str(col) for kw in desc_keywords):
            result["description_column"] = col
            break
    
    # 数量和单价
    for col in columns:
        if "数量" in str(col):
            result["quantity_column"] = col
        if "单价" in str(col):
            result["unit_price_column"] = col
    
    # 根据列名判断成本类型
    col_str = " ".join(str(c) for c in columns)
    sample_str = json.dumps(sample_data, ensure_ascii=False)
    combined = col_str + " " + sample_str
    
    # 材料成本
    for kw in COST_TYPE_KEYWORDS["material"]:
        if kw in combined:
            result["cost_type"] = "material"
            result["cost_subtype"] = "材料"
            result["confidence"] = 0.7
            return result
    
    # 外包成本
    for subtype, keywords in COST_TYPE_KEYWORDS["outsourcing"].items():
        for kw in keywords:
            if kw in combined:
                result["cost_type"] = "outsourcing"
                result["cost_subtype"] = subtype
                result["confidence"] = 0.7
                return result
    
    # 间接成本
    for subtype, keywords in COST_TYPE_KEYWORDS["indirect"].items():
        for kw in keywords:
            if kw in combined:
                result["cost_type"] = "indirect"
                result["cost_subtype"] = subtype
                result["confidence"] = 0.7
                return result
    
    return result


def match_project(project_value: str, conn) -> Optional[str]:
    """
    匹配项目ID
    
    Args:
        project_value: Excel中的项目名或编号
        conn: 数据库连接
        
    Returns:
        项目ID或None
    """
    if not project_value:
        return None
    
    try:
        # 尝试匹配项目名或编号
        result = conn.execute(text("""
            SELECT id, name FROM projects 
            WHERE (name ILIKE :value OR id::text = :value)
            AND is_deleted = false
            LIMIT 1
        """), {"value": f"%{project_value}%"})
        
        row = result.fetchone()
        if row:
            return str(row[0])
        
        # 模糊匹配
        result = conn.execute(text("""
            SELECT id, name FROM projects 
            WHERE name ILIKE :value
            AND is_deleted = false
            LIMIT 1
        """), {"value": f"%{project_value[:10]}%"})
        
        row = result.fetchone()
        if row:
            return str(row[0])
        
        return None
        
    except Exception:
        return None


def get_or_create_cost_type(cost_type: str, cost_subtype: str, conn) -> Optional[int]:
    """
    获取或创建成本类型ID
    """
    try:
        if cost_type == "indirect":
            table = "indirect_cost_types"
        elif cost_type == "outsourcing":
            table = "outsourcing_service_types"
        else:
            return None
        
        # 查找已有类型
        result = conn.execute(text(f"""
            SELECT id FROM {table} 
            WHERE type_name = :name AND is_deleted = false
            LIMIT 1
        """), {"name": cost_subtype})
        
        row = result.fetchone()
        if row:
            return row[0]
        
        # 创建新类型
        result = conn.execute(text(f"""
            INSERT INTO {table} (type_name, description, created_at, updated_at, is_deleted)
            VALUES (:name, :desc, NOW(), NOW(), false)
            RETURNING id
        """), {"name": cost_subtype, "desc": f"从Excel导入创建"})
        
        conn.commit()
        return result.fetchone()[0]
        
    except Exception:
        return None


def import_cost_data(
    file_content: bytes,
    file_name: str,
    sheet_name: str,
    column_mapping: Dict[str, str],
    cost_type: str,
    cost_subtype: str,
    conn
) -> Dict[str, Any]:
    """
    导入成本数据到数据库
    
    Args:
        file_content: 文件内容
        file_name: 文件名
        sheet_name: 工作表名
        column_mapping: 列映射 {系统字段: Excel列名}
        cost_type: 成本大类
        cost_subtype: 成本子类型
        conn: 数据库连接
        
    Returns:
        {
            "success": True/False,
            "imported_count": 成功导入数量,
            "skipped_count": 跳过数量,
            "errors": [错误信息],
            "matched_projects": [匹配到的项目]
        }
    """
    result = {
        "success": False,
        "imported_count": 0,
        "skipped_count": 0,
        "errors": [],
        "matched_projects": []
    }
    
    try:
        # 读取Excel
        df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name)
        
        # 获取列映射
        project_col = column_mapping.get("project_column")
        amount_col = column_mapping.get("amount_column")
        date_col = column_mapping.get("date_column")
        desc_col = column_mapping.get("description_column")
        quantity_col = column_mapping.get("quantity_column")
        unit_price_col = column_mapping.get("unit_price_column")
        
        if not project_col or not amount_col:
            result["errors"].append("缺少必要的列映射：项目列或金额列")
            return result
        
        imported_projects = set()
        
        for idx, row in df.iterrows():
            try:
                # 获取项目
                project_value = str(row.get(project_col, "")).strip()
                if not project_value or project_value == "nan":
                    result["skipped_count"] += 1
                    continue
                
                # 匹配项目ID
                project_id = match_project(project_value, conn)
                if not project_id:
                    result["errors"].append(f"第{idx+2}行：未找到项目 '{project_value}'")
                    result["skipped_count"] += 1
                    continue
                
                # 获取金额
                amount = row.get(amount_col)
                if pd.isna(amount) or amount == 0:
                    result["skipped_count"] += 1
                    continue
                
                try:
                    amount = float(amount)
                except:
                    result["errors"].append(f"第{idx+2}行：金额格式错误 '{amount}'")
                    result["skipped_count"] += 1
                    continue
                
                # 获取其他字段
                date_val = row.get(date_col) if date_col else None
                description = str(row.get(desc_col, "")).strip() if desc_col else ""
                quantity = row.get(quantity_col) if quantity_col else None
                unit_price = row.get(unit_price_col) if unit_price_col else None
                
                # 写入数据库
                if cost_type == "material":
                    conn.execute(text("""
                        INSERT INTO material_costs 
                        (project_id, name, quantity, unit_price, total_price, cost_type, remark, create_time, update_time, is_deleted)
                        VALUES (:project_id, :name, :quantity, :unit_price, :total_price, :cost_type, :remark, NOW(), NOW(), false)
                    """), {
                        "project_id": project_id,
                        "name": description or f"材料-{cost_subtype}",
                        "quantity": float(quantity) if not pd.isna(quantity) else 1,
                        "unit_price": float(unit_price) if not pd.isna(unit_price) else amount,
                        "total_price": amount,
                        "cost_type": cost_subtype,
                        "remark": f"从Excel导入: {file_name}"
                    })
                
                elif cost_type == "outsourcing":
                    type_id = get_or_create_cost_type(cost_type, cost_subtype, conn)
                    conn.execute(text("""
                        INSERT INTO outsourcing_costs 
                        (project_id, service_type, service_type_id, quantity, unit_price, total_price, cost_type, description, remark, create_time, update_time, is_deleted)
                        VALUES (:project_id, :service_type, :service_type_id, :quantity, :unit_price, :total_price, :cost_type, :description, :remark, NOW(), NOW(), false)
                    """), {
                        "project_id": project_id,
                        "service_type": cost_subtype,
                        "service_type_id": type_id,
                        "quantity": float(quantity) if not pd.isna(quantity) else 1,
                        "unit_price": float(unit_price) if not pd.isna(unit_price) else amount,
                        "total_price": amount,
                        "cost_type": cost_subtype,
                        "description": description,
                        "remark": f"从Excel导入: {file_name}"
                    })
                
                elif cost_type == "indirect":
                    type_id = get_or_create_cost_type(cost_type, cost_subtype, conn)
                    conn.execute(text("""
                        INSERT INTO indirect_costs 
                        (project_id, cost_type, cost_type_flag, indirect_type_id, amount, total_price, description, remark, create_time, update_time, is_deleted)
                        VALUES (:project_id, :cost_type, :cost_type_flag, :indirect_type_id, :amount, :total_price, :description, :remark, NOW(), NOW(), false)
                    """), {
                        "project_id": project_id,
                        "cost_type": cost_subtype,
                        "cost_type_flag": cost_subtype,
                        "indirect_type_id": type_id,
                        "amount": amount,
                        "total_price": amount,
                        "description": description,
                        "remark": f"从Excel导入: {file_name}"
                    })
                
                result["imported_count"] += 1
                imported_projects.add(project_value)
                
            except Exception as e:
                result["errors"].append(f"第{idx+2}行：{str(e)}")
                result["skipped_count"] += 1
        
        conn.commit()
        result["success"] = result["imported_count"] > 0
        result["matched_projects"] = list(imported_projects)
        
    except Exception as e:
        result["errors"].append(f"导入失败: {str(e)}")
    
    return result


def preview_import(
    file_content: bytes,
    file_name: str,
    sheet_name: str,
    column_mapping: Dict[str, str],
    conn
) -> Dict[str, Any]:
    """
    预览导入结果（不实际写入）
    """
    result = {
        "total_rows": 0,
        "matched_projects": [],
        "unmatched_projects": [],
        "preview_data": []
    }
    
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name)
        result["total_rows"] = len(df)
        
        project_col = column_mapping.get("project_column")
        amount_col = column_mapping.get("amount_column")
        
        project_matches = {}
        
        for idx, row in df.iterrows():
            project_value = str(row.get(project_col, "")).strip()
            amount = row.get(amount_col)
            
            if project_value and project_value != "nan":
                if project_value not in project_matches:
                    project_id = match_project(project_value, conn)
                    project_matches[project_value] = project_id
                
                result["preview_data"].append({
                    "row": idx + 2,
                    "project": project_value,
                    "matched_project_id": project_matches[project_value],
                    "amount": float(amount) if not pd.isna(amount) else 0
                })
        
        for project, matched_id in project_matches.items():
            if matched_id:
                result["matched_projects"].append({
                    "name": project,
                    "project_id": matched_id
                })
            else:
                result["unmatched_projects"].append(project)
        
    except Exception as e:
        result["error"] = str(e)
    
    return result
