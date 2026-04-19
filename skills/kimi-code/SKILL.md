---
name: kimi-code
description: "指导 Agent 使用 Kimi Code CLI 完成编程任务，支持代码编写、调试、重构、自动化等任务，完成后输出执行结果供调用者分析。"
metadata:
  sandbox_only: true
  enforced: true
---

# Kimi Code Skill

> ⚠️ **强制约束**：此技能必须严格遵循沙箱开发流程，禁止任何绕过行为。

## 强制流程规则

### ❌ 禁止的行为

1. **禁止直接操作主机代码**
   - 不得在 `/home/xujie/workspace/` 目录执行 kimi 代码开发
   - 不得修改主机上的非沙箱文件

2. **禁止跳过代码取出步骤**
   - 不得在容器内开发完成后不取出代码就直接结束任务
   - 不得假设代码会自动同步（除非使用 bind mount）

3. **禁止绕过沙箱验证**
   - 路径检查失败时不得强行执行
   - 不得使用 sudo 或其他方式绕过权限限制

### ✅ 必须遵循的流程

```
1. 创建沙箱项目目录
   ↓
2. 配置 Dev Container（bind mount 或 docker cp）
   ↓
3. 启动容器并进入开发
   ↓
4. Kimi Code 执行代码开发
   ↓
5. 【强制】取出代码到沙箱目录
   ↓
6. 验证代码完整性
   ↓
7. 汇报结果
```

### 流程检查点

| 步骤 | 检查点 | 验证方式 |
|------|--------|---------|
| 1 | 项目目录已创建 | `ls ~/.openclaw/workspace/<project>/` |
| 2 | Dev Container 已配置 | 检查 .devcontainer/devcontainer.json |
| 3 | 容器已启动 | `docker ps` 确认容器运行中 |
| 4 | 开发完成 | 确认关键文件已生成 |
| 5 | 代码已取出 | 确认文件在沙箱目录内 |
| 6 | 代码完整 | 验证 main.py / package.json 等存在 |

### 违规处理

如果检测到违规行为：
1. 立即停止当前操作
2. 记录错误到 `.learnings/ERRORS.md`
3. 提示用户违反了安全流程
4. 提供正确路径引导用户


---

## 沙箱限制

### 允许的操作
- 在虚拟沙箱目录 (`~/.openclaw/workspace/`) 内创建/修改项目
- 使用 Dev Container 开发容器
- 读写沙箱内的文件

### 禁止的操作
- ❌ 在主机路径 (`/home/xujie/workspace/`, `~/workspace/`) 执行代码
- ❌ 在系统目录 (`/etc`, `/usr`) 进行操作
- ❌ 直接操作宿主机上的项目

### 路径规则
```
# 正确
~/.openclaw/workspace/project-name/
/home/xujie/.openclaw/workspace/

# 错误（会被 sandbox 拦截）
~/workspace/project-name/
/home/xujie/workspace/
```

### 路径验证流程
1. 检查目标路径是否在 `~/.openclaw/workspace/` 内
2. 如果是 `~/workspace/` 开头 → 转换为 `~/.openclaw/workspace/`
3. 如果路径超出沙箱 → 报错并提示修正

---

## 核心命令

```bash
# 安装
curl -LsSf https://code.kimi.com/install.sh | bash

# 验证
kimi --version
```

## 使用流程

### 1. 启动会话

```bash
cd /path/to/project
kimi
```

首次使用需 `/login` 配置（推荐 Kimi Code，自动 OAuth 授权）

### 2. 常用任务指令

| 任务类型 | 示例指令 |
|---------|---------|
| 查看项目结构 | "Show me the directory structure" |
| 实现新功能 | "帮我实现用户认证功能" |
| 修复 Bug | "修复登录页面的验证码不显示问题" |
| 重构代码 | "把这个组件重构为 Hook" |
| 理解代码 | "解释这段代码的作用" |
| 自动化任务 | "批量重命名所有 .txt 文件" |
| 运行测试 | "运行单元测试并修复失败用例" |

### 3. Shell 模式

按 `Ctrl-X` 切换到 Shell 模式，直接执行终端命令

### 4. 斜杠命令

| 命令 | 说明 |
|------|------|
| `/login` | 配置平台和模型 |
| `/init` | 分析项目生成 AGENTS.md |
| `/help` | 查看所有命令 |
| `/exit` | 退出 |

## 输出格式

任务完成后，请按以下格式输出结果：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Kimi Code 执行结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 任务状态: 成功/失败

📝 执行摘要:
[简要描述完成的工作]

📄 修改文件:
- file1.py (新增)
- file2.js (修改)
- file3.ts (删除)

🔧 执行命令:
[列出执行的命令]

📊 额外输出:
[如有命令输出或日志]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## MCP 集成（可选）

如需扩展功能，可配置 MCP 服务器：

```bash
# 添加 MCP 服务器
kimi mcp add --transport http context7 https://mcp.context7.com/mcp --header "CONTEXT7_API_KEY: xxx"

# 或配置文件方式
kimi --mcp-config-file /path/to/mcp.json
```

## 注意事项

1. **首次运行**：macOS 首次启动可能较慢，可在「系统设置 → 隐私与安全性 → 开发者工具」添加终端应用加速
2. **模型选择**：推荐使用 Kimi Code（kimi-k2.5 模型）
3. **项目初始化**：新项目可运行 `/init` 生成 AGENTS.md 帮助 AI 更好理解项目结构
4. **会话管理**：使用 `kimi web` 可查看历史会话记录

---

## 代码取出流程（Dev Container 模式）

当代码在 Docker 容器内开发完成后，按以下流程取出：

### 方式一：Bind Mount（推荐）

项目目录通过 bind mount 挂载，代码实时同步：
```json
// .devcontainer.json
{
  "mounts": [
    "source=${localEnv:HOME}/.openclaw/workspace/kimi-project,target=/workspace,type=bind"
  ]
}
```
开发完成后直接读取 `~/.openclaw/workspace/kimi-project/` 即可。

### 方式二：docker cp

容器内开发，需手动复制出来：
```bash
# 1. 确定容器名称或 ID
docker ps -a | grep kimi

# 2. 复制文件
docker cp kimi-container:/workspace/project-name ./

# 3. 验证复制结果
ls -la ./project-name/
```

### 我的职责（作为菜包）

1. **启动容器**：使用 docker-compose 或 devcontainer.json 启动开发环境
2. **监控状态**：等待开发完成，确认容器内代码已保存
3. **取出代码**：
   - Bind Mount 模式：直接读取沙箱目录
   - docker cp 模式：执行 `docker cp` 复制到目标位置
4. **验证结果**：
   - 检查文件是否存在
   - 确认关键文件（main.py, package.json 等）已生成
   - 告知用户代码已取出

### 完整工作流

```
用户: 帮我用 Kimi Code 实现 xxx 功能

↓

菜包:
1. 在沙箱内创建项目目录 (~/.openclaw/workspace/xxx/)
2. 配置 Dev Container
3. 启动容器
4. 进入容器执行 kimi 开发

↓

Kimi Code: 开发代码...

↓

菜包:
1. 等待开发完成
2. 取出代码（bind mount 或 docker cp）
3. 验证文件
4. 汇报结果给用户
```

---

## 错误处理

| 错误 | 解决方法 |
|------|---------|
| 容器启动失败 | 检查 docker daemon 运行状态 |
| docker cp 无权限 | 使用 sudo 或检查权限 |
| 代码未同步 | 确认 bind mount 配置正确 |
| 容器内 kimi 未登录 | 挂载 ~/.kimi 配置目录 |
