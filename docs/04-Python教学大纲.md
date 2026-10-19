# Python 教学大纲

## 是什么
Python = 解释型、动态类型的高级语言，语法简洁。AI/数据/agent 生态几乎都用它（我们要复刻的 nanobot 就是 Python 写的）。

## 为什么用
1. 语法简单、上手快
2. AI 生态最全（LLM SDK、agent 框架基本都是 Python）
3. 复刻 nanobot 用 Python 顺理成章

## 核心概念（大纲）
- 基础语法：变量、类型、列表/字典/元组、循环、函数
- 缩进即代码块（没有花括号）
- 类与面向对象（简）
- 类型注解（Python 3 的 `def f(x: int) -> str`，非强制）
- 异步 asyncio / `async def` / `await`（流式后端会用到）
- 虚拟环境（venv / uv）与包管理（pip / pyproject.toml）
- FastAPI：写 HTTP 接口的框架（我们后端用它）

## 和 TS 的对比
| | Python | TypeScript |
|---|---|---|
| 类型 | 动态（可选注解） | 静态 |
| 缩进 | 缩进定义代码块 | 花括号 |
| 运行 | 解释执行 | 编译成 JS 运行 |

## 学习路径
跟着阶段 1 写 FastAPI 后端时边写边学，重点掌握「能读懂 + 会写简单接口」即可。
