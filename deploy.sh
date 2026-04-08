#!/bin/bash

# 项目管理智能体部署脚本

PROJECT_DIR="/home/ubuntu/.openclaw/workspace/project-agent"
DEPLOY_DIR="/var/www/project-agent"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}开始部署项目管理智能体...${NC}"

# 1. 构建前端
echo -e "${YELLOW}[1/4] 构建前端...${NC}"
cd $PROJECT_DIR/frontend
npm install
npm run build

# 2. 部署前端
echo -e "${YELLOW}[2/4] 部署前端...${NC}"
sudo mkdir -p $DEPLOY_DIR/frontend
sudo rm -rf $DEPLOY_DIR/frontend/*
sudo cp -r dist/* $DEPLOY_DIR/frontend/

# 3. 部署后端
echo -e "${YELLOW}[3/4] 部署后端...${NC}"
cd $PROJECT_DIR/backend
source venv/bin/activate
pip install -r requirements.txt

# 使用 pm2 启动后端
if command -v pm2 &> /dev/null; then
    pm2 restart project-agent-backend || pm2 start app/main.py --name project-agent-backend --interpreter python3 -- --port 3000
else
    echo -e "${YELLOW}提示: 未安装 pm2，建议使用 pm2 管理后端进程${NC}"
    echo "安装: npm install -g pm2"
fi

# 4. 配置 Nginx
echo -e "${YELLOW}[4/4] 检查 Nginx 配置...${NC}"
NGINX_CONF="/etc/nginx/sites-available/project-agent"

if [ ! -f "$NGINX_CONF" ]; then
    echo "创建 Nginx 配置..."
    sudo tee $NGINX_CONF > /dev/null << 'EOF'
server {
    listen 80;
    server_name 175.178.40.53;

    # 智能体前端
    location /agent {
        alias /var/www/project-agent/frontend/;
        try_files $uri $uri/ /index.html;
        index index.html;
    }

    # 智能体后端API
    location /agent-api {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF
    sudo ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
    sudo nginx -s reload
    echo -e "${GREEN}Nginx 配置已创建并生效${NC}"
fi

echo -e "${GREEN}部署完成！${NC}"
echo ""
echo "访问地址:"
echo "  前端: http://175.178.40.53/agent"
echo "  后端: http://175.178.40.53/agent-api"
echo ""
echo "环境变量配置:"
echo "  编辑: $PROJECT_DIR/backend/.env"
echo "  需设置: KIMI_API_KEY"
