# Phase 14-15 实施方案

## Phase 14：数据可视化

### 1. 项目进度看板

**功能点**：
- 项目卡片视图（状态：进行中/延期/已完成）
- 进度条可视化
- 风险等级标签（红/黄/绿）
- 快速筛选（按负责人/状态/风险）

**技术方案**：
```typescript
// 前端组件
<ProjectBoard>
  <FilterBar />
  <ProjectCard 
    project={project}
    progress={进度百分比}
    riskLevel={风险等级}
    delayedTasks={延期任务数}
  />
</ProjectBoard>
```

**数据接口**：
- `GET /api/agent/projects/board` - 获取看板数据
- 返回：项目列表 + 进度 + 风险评分 + 延期任务

---

### 2. 工时统计图表

**功能点**：
- 本周/本月工时趋势（折线图）
- 项目工时分布（饼图）
- 团队工时排名（柱状图）
- 工时预测（虚线）

**技术方案**：
```typescript
// 使用 ECharts
<WorkHoursChart>
  <LineChart data={weeklyHours} />
  <PieChart data={projectDistribution} />
  <BarChart data={teamRanking} />
</WorkHoursChart>
```

**数据接口**：
- `GET /api/agent/stats/hours-trend?range=week|month` - 工时趋势
- `GET /api/agent/stats/project-distribution` - 项目分布
- `GET /api/agent/team/hours-ranking` - 团队排名（已有）

---

### 3. 风险热力图

**功能点**：
- 项目风险矩阵（进度风险 × 资源风险）
- 风险气泡图（大小=影响程度）
- 颜色编码（绿<40 / 黄40-70 / 红>70）

**技术方案**：
```typescript
<RiskHeatmap>
  {projects.map(p => (
    <RiskBubble
      x={p.scheduleRisk}      // 进度风险 0-100
      y={p.resourceRisk}      // 资源风险 0-100
      size={p.impactScore}    // 影响程度
      color={getRiskColor(p.overallRisk)}
    />
  ))}
</RiskHeatmap>
```

**数据接口**：
- `GET /api/agent/projects/{id}/risk-radar` - 已有
- 新增：`GET /api/agent/dashboard/risk-matrix` - 全部项目风险矩阵

---

### 4. 成本趋势图

**功能点**：
- 预算 vs 实际成本曲线
- 成本偏差预警线
- 月度成本对比（柱状图）

**数据接口**：
- `GET /api/agent/stats/cost-trend?project_id=xxx` - 成本趋势
- 返回：预算线 + 实际线 + 预测线

---

### 5. 实施优先级

| 模块 | 优先级 | 预计工时 |
|------|--------|----------|
| 项目进度看板 | P0 | 4h |
| 工时统计图表 | P0 | 3h |
| 风险热力图 | P1 | 4h |
| 成本趋势图 | P2 | 3h |

---

## Phase 15：智能推荐

### 1. 任务智能分配

**场景**：新建任务时，推荐最合适的负责人

**推荐算法**：
```python
def recommend_assignee(task, team_members):
    """
    基于多因素推荐任务负责人
    
    因素权重：
    - 技能匹配度：40%
    - 当前负荷：30%
    - 历史完成率：20%
    - 协作偏好：10%
    """
    scores = []
    for member in team_members:
        # 技能匹配
        skill_score = calc_skill_match(task.skills, member.skills)
        
        # 负荷评分（负荷越低分越高）
        workload_score = 100 - member.current_workload
        
        # 历史完成率
        history_score = member.task_completion_rate
        
        # 协作偏好（是否在项目团队中）
        collab_score = 100 if member in task.project.team else 50
        
        # 综合评分
        total = (skill_score * 0.4 + 
                 workload_score * 0.3 + 
                 history_score * 0.2 + 
                 collab_score * 0.1)
        
        scores.append((member, total))
    
    return sorted(scores, key=lambda x: -x[1])[:3]
```

**数据接口**：
- `POST /api/agent/tasks/recommend-assignee` - 推荐负责人
- 入参：任务描述、项目ID、所需技能
- 返回：推荐列表（top 3）+ 推荐理由

---

### 2. 风险预警推送

**场景**：主动发现风险并推送提醒

**预警规则**：
| 规则 | 触发条件 | 预警级别 |
|------|----------|----------|
| 任务延期 | 剩余天数<3天且进度<50% | 高 |
| 资源过载 | 人员月工时>180h | 中 |
| 成本超支 | 实际>预算80% | 中 |
| 项目停滞 | 7天无进度更新 | 低 |

**推送方式**：
- 系统通知（已有）
- 企业微信/钉钉（待集成）
- 邮件摘要

**数据接口**：
- `POST /api/agent/alerts/check` - 检查并生成预警
- `GET /api/agent/alerts/subscribe` - 订阅预警规则

---

### 3. 工时预测

**场景**：预测本月工时，提前预警

**预测算法**：
```python
def predict_monthly_hours(employee_id):
    """
    基于历史数据预测本月工时
    
    方法：加权移动平均
    """
    # 获取最近3个月工时
    history = get_recent_hours(employee_id, months=3)
    
    # 权重：最近月份权重更高
    weights = [0.5, 0.3, 0.2]
    
    # 预测
    predicted = sum(h * w for h, w in zip(history, weights))
    
    # 考虑当月剩余任务
    remaining_tasks = get_remaining_tasks(employee_id)
    estimated_hours = sum(t.estimated_hours for t in remaining_tasks)
    
    # 调整预测
    final_prediction = predicted * 0.6 + estimated_hours * 0.4
    
    return {
        "predicted_hours": final_prediction,
        "confidence": 0.8,
        "risk": "high" if final_prediction > 180 else "normal"
    }
```

**数据接口**：
- `GET /api/agent/predict/hours` - 已有（需增强）
- 新增：`GET /api/agent/predict/workload?employee_id=xxx`

---

### 4. 下一步行动建议

**场景**：每日登录时，推荐今天应该做什么

**推荐逻辑**：
```python
def get_daily_actions(employee_id):
    """生成每日行动建议"""
    actions = []
    
    # 1. 紧急任务
    urgent_tasks = get_tasks_due_today(employee_id)
    if urgent_tasks:
        actions.append({
            "type": "urgent",
            "title": f"今日到期任务 ({len(urgent_tasks)}项)",
            "items": urgent_tasks,
            "action": "立即处理"
        })
    
    # 2. 延期任务
    delayed = get_delayed_tasks(employee_id)
    if delayed:
        actions.append({
            "type": "delayed",
            "title": f"延期任务预警 ({len(delayed)}项)",
            "items": delayed[:3],
            "action": "更新进度或申请延期"
        })
    
    # 3. 日报提醒
    if not has_submitted_daily_report(employee_id):
        actions.append({
            "type": "reminder",
            "title": "日报填报提醒",
            "action": "去填报"
        })
    
    # 4. 待办事项
    todos = get_pending_todos(employee_id)
    if todos:
        actions.append({
            "type": "todo",
            "title": "待办事项",
            "items": todos[:5]
        })
    
    return actions
```

**数据接口**：
- `GET /api/agent/dashboard/daily-actions` - 每日行动建议

---

### 5. 相似项目参考

**场景**：新建项目时，推荐相似历史项目作为参考

**推荐算法**：
```python
def find_similar_projects(new_project, limit=5):
    """基于项目特征找相似项目"""
    # 项目特征向量
    features = [
        new_project.budget,           # 预算
        new_project.duration,         # 周期
        new_project.team_size,        # 团队规模
        new_project.category_vector,  # 类别（编码）
        new_project.tech_stack_vector # 技术栈（编码）
    ]
    
    # 计算相似度（可用向量搜索）
    similar = vector_search(features, historical_projects)
    
    return similar[:limit]
```

**数据接口**：
- `POST /api/agent/projects/similar` - 查找相似项目
- 返回：相似项目列表 + 相似度 + 参考价值说明

---

### 6. 实施优先级

| 模块 | 优先级 | 预计工时 |
|------|--------|----------|
| 每日行动建议 | P0 | 3h |
| 风险预警推送 | P0 | 4h |
| 任务智能分配 | P1 | 5h |
| 工时预测增强 | P1 | 2h |
| 相似项目参考 | P2 | 4h |

---

## 技术栈补充

### 前端图表库
```json
{
  "dependencies": {
    "echarts": "^5.4.0",
    "echarts-for-react": "^3.0.0",
    "@ant-design/plots": "^2.0.0"
  }
}
```

### 后端推荐引擎
```python
# requirements.txt 补充
scikit-learn>=1.3.0  # 相似度计算
numpy>=1.24.0        # 向量运算
```

---

## 实施计划

### Week 1（Phase 14）
- Day 1-2：项目进度看板
- Day 3：工时统计图表
- Day 4：风险热力图
- Day 5：集成测试

### Week 2（Phase 15）
- Day 1：每日行动建议
- Day 2：风险预警推送
- Day 3-4：任务智能分配
- Day 5：工时预测 + 相似项目

---

## 验收标准

### Phase 14
- [ ] 看板展示所有项目状态
- [ ] 图表支持周/月切换
- [ ] 风险热力图正确映射
- [ ] 数据实时更新（5分钟缓存）

### Phase 15
- [ ] 每日行动建议准确率 > 90%
- [ ] 任务推荐点击率 > 60%
- [ ] 风险预警误报率 < 10%
- [ ] 相似项目推荐合理度评分 > 4.0/5.0
