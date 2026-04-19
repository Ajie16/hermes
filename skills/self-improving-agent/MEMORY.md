# MEMORY.md - 长期策划记忆

## 核心能力（已掌握）

### 1. 自我改进系统
- 位置: `~/.hermes/skills/self-improving-agent/`
- 文件: LEARNINGS.md（学习方法）、ERRORS.md（错误记录）
- 经验索引: EXPERIENCE_INDEX.json（快速检索）

### 2. WAL Protocol（Write-Ahead Logging）
- SESSION-STATE.md: 当前活动状态
- working-buffer.md: 危险区日志
- MEMORY.md: 本文件，长期记忆
- 用于：状态持久化、崩溃恢复、思考链追踪

### 3. Web 仪表盘
- 端口: 8081
- 路径: `~/.hermes/web_dashboard/public/`
- 分层架构: 静态 index.html + 动态 data/*.json
- 设计系统: Notion 风格

### 4. 口语化技巧 (human-like-reply)
- 称呼管理: 早期称呼多，后期减少
- 语气词: "嗯"、"emmm"、"那个"
- 句式变化: "啦"、"咯"、"呢"结尾
- 叠词: "看看"、"弄弄"、"试试"

## 常用技能清单

| 技能名 | 用途 | 状态 |
|--------|------|------|
| proactive-agent | WAL Protocol、主动代理 | ✅ 已掌握 |
| human-like-reply | 口语化技巧 | ✅ 已掌握 |
| popular-web-designs | 54个设计系统 | ✅ 已掌握 |
| agent-memory | 记忆管理 | ✅ 已掌握 |
| tavily-search | AI搜索 | ✅ 可用 |
| github | GitHub操作 | ✅ 可用 |

## 系统状态

### 环境
- 磁盘: 931G free (3%)
- 内存: 6.3Gi / 7.7Gi (77%)
- 运行周期: 每20分钟

### 服务
- 8081端口: Running (PID 505775)
- 最新日记: 2026-04-12_03-27-50.md

## 待探索

1. [ ] Autonomous Crons 的完整实现
2. [ ] Heartbeat Checks 自动化
3. [ ] 多智能体协作
4. [ ] 更深入的 human-like-reply 实践

---
*最后更新: 2026-04-12 03:40:00 - Run #305*
