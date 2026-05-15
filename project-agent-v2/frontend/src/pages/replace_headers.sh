#!/bin/bash
# 批量替换页面导航为 SharedHeader

cd /home/ubuntu/.openclaw/workspace/project-agent/frontend/src/pages

# 定义需要修改的文件和对应的header开始行
files=("Daily.tsx" "Projects.tsx" "Dashboard.tsx" "Tracking.tsx" "Quality.tsx" "Chat.tsx")

for file in "${files[@]}"; do
  echo "处理 $file ..."
  
  # 查找 header 开始和结束的行号
  start_line=$(grep -n "<header className=\"header" "$file" | head -1 | cut -d: -f1)
  
  if [ -n "$start_line" ]; then
    # 找到对应的 </header> 结束行
    end_line=$(awk "NR>=$start_line && /<\/header>/ {print NR; exit}" "$file")
    
    if [ -n "$end_line" ]; then
      echo "  找到 header 块: $start_line - $end_line"
      
      # 检查是否已经导入了 SharedHeader
      if ! grep -q "import SharedHeader" "$file"; then
        # 添加 SharedHeader 导入
        sed -i "1a import SharedHeader from '../components/SharedHeader'" "$file"
      fi
      
      # 删除旧的 header 块，替换为 SharedHeader
      sed -i "$start_line,${end_line}c\\      {/* 顶部导航 */}\n      <SharedHeader />" "$file"
      
      echo "  已替换"
    fi
  fi
done

echo "完成"
