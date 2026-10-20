# 渲染优化：nanobot 的四招（我们怎么落地）

> 流式吐字时怎么让界面不卡？这是「前端性能优化」的经典面试素材。我们参考 nanobot，四招都落地了。

## 核心问题

流式 = 一个字一个 token。每来一个 token 就让 React 画一次，一秒几十次 → 卡。

更糟的是：每次画，**整条消息都要重新解析 markdown + 代码高亮**（highlight.js 特别吃 CPU）。消息越长、聊得越久，越卡。

## 两件事：「少画几次」+「每次画得轻」

### 第一类：少画几次

**1. 50ms 节流 + rAF 批处理** ✅ 已做

- token 先攒进 buffer，**最多每 50ms 刷一次屏**（不是每 token 刷，也不是每帧 60fps 刷）。
- 为什么是 50ms？nanobot 源码里写死 `VISIBLE_STREAM_FLUSH_INTERVAL_MS = 50`，注释原话：「markdown 和布局工作要给输入留出时间」。20fps 肉眼看已经很连贯，但省下的主线程时间让 markdown 解析不至于拖垮帧率。
- 实现（`frontend/src/store/chat.ts` 的 `schedule()`）：距上次刷屏不足 50ms 就 `setTimeout` 等到点，否则下一帧 `requestAnimationFrame` 刷。
- 页面切后台时 nanobot 还降到 1 秒刷一次（我们暂没做，可补）。

### 第二类：每次画得轻

**2. React.memo 隔离历史消息** ✅ 已做

- 关键点：`flush()` 里 `messages.map` 只替换**正在流式的那条消息**的引用，其它消息引用不变。
- 给 `MessageBubble` 包 `React.memo`，浅比较 props → **历史消息不重渲染**，只有当前那条流式消息每 50ms 画一次。
- 效果：聊得越久越明显——之前每帧都在白刷几十条旧消息、重新解析它们的 markdown。

**3. 窗口化历史（虚拟滚动）** ✅ 已做

- 屏幕一次只显示十几条，但历史可能几百条，全放 DOM 里节点太多。
- 只渲染最近 **120 条**，往上滚到顶部再加载 120 条（复刻 nanobot 的 `windowMessages` + `visibleCount`）。
- 关键点：只有「在底部」时才自动跟随滚动，翻历史不会被拽回底部；加载更多后用 `scrollHeight` 差值补偿 `scrollTop`，视口内容不跳动。

**4. 懒加载代码高亮** ✅ 已做

- 代码块**进入视口**（IntersectionObserver，提前 300px）才用 highlight.js 高亮，屏幕外的是纯 `<pre>`。
- **流式期间不高亮**：代码块还没闭合，高亮了也白高亮；等消息生成完再高亮一次。
- 依赖从 `rehype-highlight` 换成 `highlight.js`（`lib/common`，只打包常用语言）。

## 一句话总结

> 能少画就少画，必须画就画轻。

- 少画 = 50ms 节流（20fps）
- 画轻 = React.memo（历史不重渲染）+ 窗口化（少渲染）+ 懒加载高亮（少计算）

## 面试怎么讲

被问「流式渲染怎么优化」就说三点：

1. token 攒 buffer，`requestAnimationFrame` + **50ms 节流**合并成一次渲染；
2. `React.memo` 让只有当前消息重渲染，历史消息跳过；
3. （可提）markdown/highlight 是重活，所以既要「少画」也要「画轻」。
