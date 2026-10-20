# FluxAgent

参考 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 的个人 AI Agent（全栈）。

一句话概括：像 ChatGPT 一样聊天，但 AI 不只是「说」——它能自己**调用工具**（查时间、跑 Python、写 Word/Excel、上网查资料、定时提醒……）、按 **SKILL 说明书**执行任务、**记住你的偏好**，还能开**子代理**并行干活。

> 项目定位：nanobot 原仓库源码放在 `reference/`（已 gitignore，仅供对照），本项目是独立复刻。

---

## 功能特性

- **流式对话**：SSE 逐字输出，`requestAnimationFrame` + **50ms 节流**渲染，顺滑不卡顿
- **工具调用可视化**：AI 调了什么工具、传了什么参数、返回什么结果，都能点开卡片看（调试友好）
- **16 个内置工具**：时间 / 执行 Python / shell / 文件读写 / 目录与搜索 / 正则 grep / 结构化补丁 / 网页抓取 / 长期记忆 / 历史检索 / 子代理 / 定时任务
- **技能层（SKILL.md）**：`weather`（查天气）、`office`（生成 Word/Excel）、`memory`（历史回忆）
- **记忆系统**：`MEMORY.md` 长期记忆注入 + `history.jsonl` 历史检索 + 「整理记忆」（Dream，一键把对话提炼成记忆，并 git 版本化）
- **多 agent + 自动化**：`subagent` 开子代理独立完成子任务；`cron` 定时醒来干活
- **MCP 接入**：`calc`（自写计算器）、`filesystem`（文件系统），启动时自动加载
- **前端工程化**：zustand 状态管理、IndexedDB 本地持久化（刷新/切会话不丢）、markdown + 代码高亮

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19 · TypeScript · Vite · zustand · Dexie (IndexedDB) · react-markdown + rehype-highlight |
| 后端 | Python · FastAPI · OpenAI 兼容接口（DeepSeek）· SSE · MCP SDK |
| 其它 | python-docx · openpyxl |

---

## 目录结构

```
FluxAgent/
├── frontend/              # React 前端
│   └── src/
│       ├── components/    # ChatPanel / MessageBubble / Sidebar / ToolCallCard
│       ├── store/         # zustand 状态（会话 + 流式 + 工具调用）
│       ├── lib/           # api.ts（SSE 解析）/ db.ts（Dexie）
│       └── types.ts
├── backend/               # FastAPI 后端
│   ├── main.py            # 入口（加载 MCP + 启动 cron）
│   ├── chat.py            # /api/chat SSE 接口
│   ├── llm.py             # agent 循环（function calling + 流式）
│   ├── tools.py           # 16 个工具 + 注册表
│   ├── skills.py          # SKILL.md 发现/解析/注入
│   ├── memory.py          # 记忆读写 + 历史日志
│   ├── dream.py           # 「整理记忆」提炼
│   ├── gitstore.py        # 记忆的 git 版本化
│   ├── cron.py            # 定时任务
│   ├── fstools.py         # 文件/搜索/补丁工具
│   ├── webtools.py        # 网页抓取
│   ├── exec_session.py    # 持久 Python 会话
│   ├── mcp_loader.py      # MCP 接入
│   ├── mcp_servers/       # 自写的 calc_server
│   └── skills/            # weather / office / memory
├── docs/                  # 学习文档（开发流程/架构拆解/技术选型…）
└── reference/             # nanobot 原仓库（gitignore，仅供对照）
```

---

## 快速开始

### 0. 环境要求

- Python 3.10+（后端）
- Node.js 18+（前端，且 MCP 的 filesystem server 走 `npx`）

### 1. 后端

```bash
cd backend
python -m venv .venv                      # 创建虚拟环境（已存在可跳过）
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# （可选）配置真实 key，不配则跑「mock 模式」用假回答测试界面
cp .env.example .env                      # 然后编辑填入 DEEPSEEK_API_KEY

uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功后访问 `http://127.0.0.1:8000/api/health` 应返回 `{"status":"ok"}`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 `http://localhost:5173`（Vite 已配代理转发 `/api` 到后端 8000）。

---

## 怎么用

在输入框发消息即可。没有真实 key 时是 **mock 模式**（假流式回答，用来测界面），配好 `DEEPSEEK_API_KEY` 并重启后端后就是真实大模型。

可以试试这些：

- 「现在几点」 → 触发 `get_current_time` 工具
- 「帮我写一份 Word 文档」 → 走 office 技能，生成到 `backend/generated/`
- 「查一下北京天气」 → 走 weather 技能
- 「记住我喜欢用 Vue」 → 写入长期记忆
- 「整理记忆」按钮 → 把最近对话提炼进 `MEMORY.md`
- 工具卡片点开，能看到每次调用的**参数和返回结果**

---

## 技术亮点

1. **Agent 循环**：LLM + OpenAI function calling，模型自己决定「调工具还是直接答」，循环直到产出最终回答——这是 AI Agent 的核心。
2. **流式渲染优化**：SSE 逐字到达 → `requestAnimationFrame` 批处理 → **50ms 节流**（参考 nanobot，给 markdown 解析留出时间）+ `React.memo` 隔离历史消息，避免重复解析。
3. **工具调用可视化**：把 agent 内部行为透明化，每个工具调用都是可展开的调试卡片（参数 + 结果 + 状态）。
4. **技能系统（SKILL.md）**：用 Markdown 说明书扩展能力，frontmatter 摘要注入系统提示词、需要时再读全文——「提示词即功能」。
5. **记忆系统**：`MEMORY.md` 注入 + `history.jsonl` 检索 + Dream 提炼 + git 版本化，形成完整的「记住 → 回忆 → 沉淀」闭环。
6. **多 agent + 自动化**：`subagent` 开子代理隔离上下文；`cron` 让 agent 定时醒来干活。
7. **MCP 接入**：通过 stdio 连接外部工具服务器，工具名加前缀隔离命名空间。
8. **前端工程化**：zustand 集中状态、Dexie(IndexedDB) 本地持久化、markdown + 代码高亮。

---

## 文档

学习笔记都在 `docs/`，建议按顺序读：

- `01-开发流程与阶段.md` — 整个项目怎么分阶段推进
- `02-技术选型讲解.md` — 为什么选这些技术
- `06-nanobot架构拆解.md` — nanobot 四层模型 + 通用工具清单
- `07-技术设计文档.md` — 本项目架构设计
- `08-大白话-一条消息是怎么跑通的.md` — 从发消息到回复的完整链路
- `09-渲染优化-nanobot的四招.md` — 流式渲染性能优化
- `10-工具调用可视化.md` — 调试卡片的实现思路
- `11-重点问题.md` — 项目是什么 + 重点问题

---

## License

学习/作品集项目，参考 [HKUDS/nanobot](https://github.com/HKUDS/nanobot)。
