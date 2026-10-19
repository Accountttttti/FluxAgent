# OpenAI API 教学大纲

## 是什么
OpenAI API = 通过 HTTP 请求调用大模型的接口。发一段「消息列表」过去，模型返回一段回答。它定义的接口格式成了**事实标准**，很多别的模型（Ollama、DeepSeek、智谱 GLM）都「兼容 OpenAI 接口」，所以学一套，到处能用。

## 核心概念（大纲）
- API key：调用凭证（付费/额度）
- 模型：如 gpt-4o 等，不同模型能力/价格不同
- messages 结构：`[{role: "system"|"user"|"assistant", content: "..."}]`
  - system：给模型定的「人设/规则」
  - user：用户说的话
  - assistant：模型之前的回答
- 补全接口：chat/completions
- stream（流式）：设 true 后边生成边返回（SSE）
- 关键参数：temperature（随机性）、max_tokens（最大长度）
- OpenAI 兼容接口：Ollama / DeepSeek 等提供同样的 URL 和格式，改个 base_url 就能切换

## 学习路径
阶段 1 后端就会用到：用 Python 的 openai SDK 调一个流式补全，把 token 转成 SSE 发给前端。
