# 企业微信机器人推送配置指南

## 一、创建企业微信机器人

### 步骤1：在企微群中添加机器人

1. 打开企业微信群聊
2. 点击群设置 → 群机器人 → 添加机器人
3. 命名机器人（如"项目管家提醒"）
4. **保存 Webhook URL**（格式：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx`）

### 步骤2：配置环境变量

在 `/home/ubuntu/.openclaw/workspace/project-agent/backend/.env` 添加：

```bash
# 企业微信机器人 Webhook
QYWX_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key

# 推送时间配置
PUSH_MORNING_TIME=08:30    # 早间推送时间
PUSH_EVENING_TIME=17:30    # 晚间推送时间
```

---

## 二、推送内容设计

### 早间推送（08:30）

```
📋 今日工作提醒

你好，张三！

【今日待办】2项
• 完成600KA槽项目图纸审查
• 参加项目进度会议

【延期任务】1项 ⚠️
• 除尘系统改造方案（延期3天）

【本月目标】
完成设计阶段工作 45% ▓▓▓▓░░░░░░

请及时填报今日日报 👉 http://175.178.40.53/agent/daily
```

### 晚间推送（17:30）

```
📊 今日工作统计

张三，今日工作情况：

✅ 日报状态：已提交 / 未提交
📝 本周日报：5份
⏱️ 本周工时：32.5h

【未填报提醒】
以下人员今日未填报日报：
何宾、何旭、冯恩浪...

请提醒相关人员及时填报。
```

---

## 三、配置定时任务

### 方案A：使用系统 Cron（推荐）

```bash
# 编辑 crontab
crontab -e

# 添加定时任务
30 8 * * 1-5  cd /home/ubuntu/.openclaw/workspace/project-agent/backend && /home/ubuntu/.openclaw/workspace/project-agent/backend/venv/bin/python -m app.push_worker morning >> /var/log/agent-push.log 2>&1
30 17 * * 1-5 cd /home/ubuntu/.openclaw/workspace/project-agent/backend && /home/ubuntu/.openclaw/workspace/project-agent/backend/venv/bin/python -m app.push_worker evening >> /var/log/agent-push.log 2>&1
```

### 方案B：使用 OpenClaw Cron

在 OpenClaw 配置中添加定时任务，调用推送接口。

---

## 四、需要提供的信息

请确认以下信息：

| 项目 | 需要提供 | 说明 |
|------|---------|------|
| 企微群 Webhook | ✅ | 创建机器人后获取 |
| 推送人员范围 | 需确认 | 全员推送 / 仅推送有任务的人 |
| 早间推送时间 | 默认08:30 | 可调整 |
| 晚间推送时间 | 默认17:30 | 可调整 |
| 推送内容样式 | 需确认 | Markdown / 文本 / 卡片 |

---

## 五、快速测试

获取 Webhook 后，可先手动测试：

```bash
curl -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "msgtype": "markdown",
    "markdown": {
      "content": "## 项目管家测试\n\n> 推送配置成功！"
    }
  }'
```

---

**下一步**：提供企微群 Webhook URL，我来完成推送功能开发。
