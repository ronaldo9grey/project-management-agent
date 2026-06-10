# frpc配置更新说明（远程AI服务器）

## 更新 /etc/frp/frpc.toml

添加新的代理配置：

```toml
[[proxies]]
name = "project-matcher"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8003
remotePort = 8003
```

## 完整frpc配置示例

```toml
serverAddr = "yjypro.online"
serverPort = 7000
auth.method = "token"
auth.token = "8feb955f8fc083316147a2c0f9ac1df9"

[[proxies]]
name = "qwen35b"
type = "tcp"
localIP = "127.0.0.1"
localPort = 11434
remotePort = 8001

[[proxies]]
name = "chromadb"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8000
remotePort = 8002

[[proxies]]
name = "project-matcher"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8003
remotePort = 8003
```

## 更新步骤

```bash
# 1. 编辑配置
sudo vim /etc/frp/frpc.toml

# 2. 重启frpc
sudo systemctl restart frpc

# 3. 验证端口
sudo systemctl status frpc
netstat -tlnp | grep 8003
```

## frps服务端更新（宿主服务器）

```bash
# 在宿主服务器执行
sudo vim /etc/frp/frps.toml

# 添加端口8003到allowPorts
allowPorts = [
  { start = 8001, end = 8001 },
  { start = 8002, end = 8002 },
  { start = 8003, end = 8003 }
]

# 重启frps
sudo systemctl restart frps
```