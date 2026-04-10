#!/usr/bin/env python3
"""
批量替换数据库连接代码

将所有函数内的 create_engine 调用替换为使用全局连接池
"""

import re
import sys

def fix_database_connections(content: str) -> str:
    """
    替换模式：
    
    旧代码：
        from sqlalchemy import create_engine, text
        from dotenv import load_dotenv
        load_dotenv()
        
        db_url = os.getenv("DATABASE_URL", "...")
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
    
    新代码：
        with get_connection() as conn:
    """
    
    # 模式 1: 完整的导入 + 创建引擎模式
    # 匹配多行模式
    pattern1 = re.compile(
        r'(\s+)(from sqlalchemy import create_engine, text\n'
        r'\s+from dotenv import load_dotenv\n'
        r'\s+load_dotenv\(\)\n'
        r'\s+\n'
        r'\s+db_url = os\.getenv\("DATABASE_URL"[^)]*\)\n'
        r'\s+engine = create_engine\(db_url\)\n'
        r'\s+\n'
        r'\s+)(with engine\.connect\(\) as conn:)',
        re.MULTILINE
    )
    
    def replace1(match):
        indent = match.group(1)
        return f'{indent}{match.group(3)}'
    
    content = pattern1.sub(replace1, content)
    
    # 模式 2: 简化的模式（没有 dotenv）
    pattern2 = re.compile(
        r'(\s+)(from sqlalchemy import create_engine, text\n'
        r'\s+\n'
        r'\s+db_url = os\.getenv\("DATABASE_URL"[^)]*\)\n'
        r'\s+engine = create_engine\(db_url\)\n'
        r'\s+\n'
        r'\s+)(with engine\.connect\(\) as conn:)',
        re.MULTILINE
    )
    
    def replace2(match):
        indent = match.group(1)
        return f'{indent}{match.group(3)}'
    
    content = pattern2.sub(replace2, content)
    
    # 模式 3: 只有 engine.connect() 没有 with
    # 替换 engine.connect() 为 get_connection()
    content = re.sub(
        r'engine\.connect\(\)',
        'get_connection()',
        content
    )
    
    # 模式 4: 删除多余的 create_engine 导入
    # 保留 text 导入（已从 database 模块导入）
    content = re.sub(
        r'from sqlalchemy import create_engine, text\n',
        '# text 已从 database 模块导入\n',
        content
    )
    
    # 模式 5: 删除单独的 create_engine 导入
    content = re.sub(
        r'from sqlalchemy import create_engine\n',
        '',
        content
    )
    
    # 模式 6: 删除 db_url 和 engine 创建
    content = re.sub(
        r'\s+db_url = os\.getenv\("DATABASE_URL"[^)]*\)\n\s+engine = create_engine\(db_url\)\n',
        '\n',
        content
    )
    
    # 模式 7: 清理多余的空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content


def main():
    file_path = 'app/main.py'
    
    print(f"读取文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 统计原始 create_engine 调用次数
    original_count = content.count('create_engine')
    print(f"原始 create_engine 调用次数: {original_count}")
    
    # 执行替换
    new_content = fix_database_connections(content)
    
    # 统计替换后的次数
    new_count = new_content.count('create_engine')
    print(f"替换后 create_engine 调用次数: {new_count}")
    print(f"成功替换: {original_count - new_count} 处")
    
    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✓ 文件已更新")


if __name__ == '__main__':
    main()
