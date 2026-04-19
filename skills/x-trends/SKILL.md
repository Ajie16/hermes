---
name: X/Twitter Trends
description: 获取X/Twitter全球热点话题 via trends24.in。无需登录即可实时获取Twitter热点趋势。
read_when:
  - 获取Twitter热点
  - 获取Trending话题
  - 推送热点资讯
metadata: {"openclaw":{"emoji":"🔥","requires":{"browser":"openclaw"}}}
allowed-tools: Browser(snapshot:*),Browser(tabs:*),Browser(act:*)
---

# X/Twitter 热点获取

## 数据源

使用 [trends24.in](https://trends24.in/) 获取X/Twitter全球热点话题，无需登录。

## 使用方法

### 1. 获取当前打开的trends24页面

```bash
browser action=tabs --profile openclaw
# 找到 trends24.in 的 targetId
```

### 2. 获取快照

```bash
browser action=snapshot targetId=<trends24_tab_id>
```

### 3. 提取热点

从Timeline/Tag Cloud提取最近热点：
- 48 minutes ago
- 1 hour ago
- 2 hours ago

### 推送模板

```markdown
━━━━━━━━━━━━━━━━━━
🔥 X (Twitter) 全球热点
⏰ MM月DD日 HH:MM
━━━━━━━━━━━━━━━━━━

▌ 1. 热点话题
   └ 🔗 https://twitter.com/search?q=热点

▌ 2. 热点话题
   └ 🔗 ...

来源: trends24.in
```

## 定时推送

由于trends24.in使用JS动态渲染，需要浏览器工具：
1. 通过subagent定时获取browser snapshot
2. 解析Timeline热点
3. 格式化推送