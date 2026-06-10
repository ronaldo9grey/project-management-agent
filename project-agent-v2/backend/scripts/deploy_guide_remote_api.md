# 远程AI服务器日报解析API部署指南

## 步骤1：部署API服务（在远程AI服务器执行）

```bash
# 复制部署脚本到远程AI服务器
# 方式1：直接创建文件
cat > ~/deploy_daily_parser_api.sh << 'EOF'
# 这里粘贴 deploy_daily_parser_api.sh 的内容
EOF

# 方式2：如果可以从宿主服务器scp
# scp ubuntu@yjypro.online:/home/ubuntu/.openclaw/workspace/project-agent-v2/backend/scripts/deploy_daily_parser_api.sh ~/

# 执行部署
chmod +x ~/deploy_daily_parser_api.sh
./deploy_daily_parser_api.sh

# 测试API
curl http://127.0.0.1:8003/health
```

预期返回：
```json
{"status":"ok","chromadb":"connected","model":"qwen3.5:35B + nomic-embed-text"}
```

## 步骤2：更新frpc配置（在远程AI服务器执行）

编辑 `/etc/frp/frpc.toml`：

```toml
# 添加新的代理
[[proxies]]
name = "daily-parser"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8003
remotePort = 8003
```

重启frpc：
```bash
sudo systemctl restart frpc
sudo systemctl status frpc
```

## 步骤3：更新frps配置（在宿主服务器执行）

编辑 `/etc/frp/frps.toml`：

```toml
# 在 allowPorts 中添加 8003
allowPorts = [
  { start = 8001, end = 8001 },
  { start = 8002, end = 8002 },
  { start = 8003, end = 8003 }
]
```

重启frps：
```bash
sudo systemctl restart frps
sudo systemctl status frps
```

## 步骤4：验证连通性（在宿主服务器执行）

```bash
# 测试frpc穿透
curl http://127.0.0.1:8003/health

# 测试完整解析
curl -X POST http://127.0.0.1:8003/api/parse_daily \
  -H 'Content-Type: application/json' \
  -d '{"text":"完成隆林铝厂空压机项目调试工作4小时","report_date":"2026-06-08"}'
```

## 预期效果

| 操作 | 之前耗时 | 优化后耗时 |
|------|----------|-----------|
| 向量检索 | 35秒（frpc穿透）| 本地（毫秒）|
| LLM生成 | 180秒超时 | 本地（30-60秒）|
| **总耗时** | **超时** | **30-60秒** |

## 注意事项

1. **端口冲突**：如果8003端口被占用，修改为其他端口（需同步修改frpc.toml和代码）
2. **ChromaDB**：确保ChromaDB服务正在运行（端口8000）
3. **Ollama**：确保qwen3.5:35B模型已加载（`ollama pull qwen3.5:35B`）

## 故障排查

```bash
# 检查服务状态
sudo systemctl status daily-parser

# 查看日志
sudo journalctl -u daily-parser -f

# 检查端口
netstat -tlnp | grep 8003
```
