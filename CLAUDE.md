
# CLAUDE.md - 项目协作规则

## 核心原则

- 优先理解现有代码，不主动重构。
- 修改前先确认目标文件和影响范围。
- 避免一次性读取大量无关文件。
- 优先使用已有代码和组件。

---

## Skill 使用规则

### superpowers

默认禁止自动调用 superpowers skills。

禁止：
- 自动进入 brainstorming
- 自动生成开发计划
- 自动调用 systematic-debugging
- 自动调用任何 superpowers skill

只有当用户明确输入：
"使用superpowers"
或
"调用xxx skill"

才允许调用。

如果认为需要使用skill：
先询问用户，不要直接执行。

---

## 修改代码规则

执行修改前：

1. 简述准备修改的文件
2. 说明修改原因
3. 等待用户确认（涉及多个文件时）

小范围明确修改可以直接执行。

---

## 文件读取规则

不要扫描整个项目。

优先：
- README.md
- CLAUDE.md
- HANDOFF.md
- 用户指定文件

只读取完成任务需要的内容。

---

## Git 提交

- **提交消息末尾不要加 `Co-Authored-By: Claude` 署名行**。提交身份始终是项目自己的 git 用户（Xin-der）。
- 只有用户明确要求时才 `git push`。

---

## 输出规则

回答保持简洁：
- 先给结论
- 再给必要步骤

不要输出无关解释。