#!/bin/bash
# 前端部署脚本 - 构建并部署到 Nginx 静态目录
# 用法: ./deploy-frontend.sh

set -e

# 配置
FRONTEND_DIR="/home/ubuntu/.openclaw/workspace/project-agent-v2/frontend"
NGINX_DIR="/var/www/project-agent/frontend"
APP_NAME="项目智能体"

echo "=========================================="
echo "🚀 $APP_NAME 前端部署"
echo "=========================================="

# 检查前端目录
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ 前端目录不存在: $FRONTEND_DIR"
    exit 1
fi

cd "$FRONTEND_DIR"

# 1. 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

# 2. 构建
echo "🔨 构建前端..."
npm run build

# 3. 验证构建结果
if [ ! -f "dist/index.html" ]; then
    echo "❌ 构建失败：未找到 dist/index.html"
    exit 1
fi

echo "✅ 构建成功"

# 4. 创建目录结构（匹配 Nginx root 路径）
echo "📁 创建目录结构..."
sudo mkdir -p "$NGINX_DIR/agent/assets"

# 5. 复制文件
echo "📋 复制文件到 Nginx 目录..."
sudo cp -r dist/* "$NGINX_DIR/agent/"

# 6. 设置权限
echo "🔐 设置权限..."
sudo chown -R www-data:www-data "$NGINX_DIR"
sudo chmod -R 755 "$NGINX_DIR"

# 7. 清理旧版文件（保留当前版本）
echo "🧹 清理旧版文件..."
CURRENT_JS=$(grep -oP 'index-[A-Za-z0-9_-]+\.js' "$NGINX_DIR/agent/index.html" | head -1)
CURRENT_CSS=$(grep -oP 'index-[A-Za-z0-9_-]+\.css' "$NGINX_DIR/agent/index.html" | head -1)

cd "$NGINX_DIR/agent/assets"
ls *.js *.css 2>/dev/null | grep -v "$CURRENT_JS\|$CURRENT_CSS" | while read old_file; do
    echo "  删除旧文件: $old_file"
    sudo rm -f "$old_file"
done

# 8. 显示部署信息
echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📍 访问地址: https://yjypro.online/agent/"
echo ""
echo "当前版本:"
echo "  JS:  $CURRENT_JS"
echo "  CSS: $CURRENT_CSS"
echo ""
echo "💡 提示: 静态资源由 Nginx 直接服务，无需重启后端"
