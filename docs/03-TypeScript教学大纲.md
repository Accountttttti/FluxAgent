# TypeScript 教学大纲

## 是什么
TypeScript（TS）= JavaScript 的超集，给 JS 加了「静态类型系统」。浏览器不认识 TS，最终要**编译成 JS** 才能运行。

## 为什么用
1. 编译期就能发现错误（类型写错直接报错，不用等运行才炸）
2. 编辑器智能提示更强（补全、跳转、重构更安全）
3. 大型项目更好维护、多人协作更安全
4. 面试和公司项目的标配

## 核心概念（大纲）
- 基础类型：string / number / boolean / array / object
- 类型标注 vs 类型推断（`let x: number` 手动写 vs 自动推断）
- interface（接口）与 type（类型别名）
- 联合类型（`string | number`）与交叉类型
- 泛型（generic）：让类型可复用
- any vs unknown：绕过类型 vs 安全地未知
- 函数类型、可选属性、readonly
- React + TS：给组件 props 定义类型

## 和 JS / Vue3+TS 的关系
- TS = JS + 类型。Vue3 也支持 TS（你写 Vue 时可能见过 `<script setup lang="ts">`）。
- 你已有 Vue3 基础，React+TS 的「类型」概念是通用的，主要新学的是 React 的写法。

## 学习路径（跟项目走）
跟着阶段 1 写 React 前端时边写边学，不单独死记。
