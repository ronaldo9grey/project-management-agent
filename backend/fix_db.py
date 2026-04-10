#!/usr/bin/env python3
"""
简化版数据库连接替换脚本
"""

import re

def fix_main_py():
    file_path = 'app/main.py'
    
    print(f"读取文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_count = content.count('create_engine')
    print(f"原始 create_engine 调用次数: {original_count}")
    
    # 1. 删除 from sqlalchemy import create_engine, text
    content = re.sub(
        r'(\s+)from sqlalchemy import create_engine, text\n',
        r'\1# text 已从 database 模块导入\n',
        content
    )
    
    # 2. 删除 from sqlalchemy import create_engine (单独)
    content = re.sub(
        r'(\s+)from sqlalchemy import create_engine\n',
        '',
        content
    )
    
    # 3. 删除 db_url 和 engine 创建（单行合并）
    content = re.sub(
        r'(\s+)db_url = os\.getenv\("DATABASE_URL"[^)]*\)\n(\s+)engine = create_engine\(db_url\)\n',
        '',
        content
    )
    
    # 4. 替换 with engine.connect() as conn:
    content = re.sub(
        r'with engine\.connect\(\) as conn:',
        'with get_connection() as conn:',
        content
    )
    
    # 5. 替换 engine.connect() (单独调用)
    content = re.sub(
        r'engine\.connect\(\)',
        'get_connection()',
        content
    )
    
    # 6. 清理多余的空行
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    new_count = content.count('create_engine')
    print(f"替换后 create_engine 调用次数: {new_count}")
    print(f"成功替换: {original_count - new_count} 处")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ 文件已更新")


if __name__ == '__main__':
    import os
    os.chdir('/home/ubuntu/.openclaw/workspace/project-agent/backend')
    fix_main_py()