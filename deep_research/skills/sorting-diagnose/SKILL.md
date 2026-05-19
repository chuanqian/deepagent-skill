---
name: sorting-diagnose
description: 诊断某个 Lot 在指定时间点/时间段/stepseq、可选机台上的 Sorting 指标"为什么没生效"或"为什么是这个值"。基于 rtd6.fabrtdlog 派工日志，对比实际生效值与理论生效值。触发场景示例："lot ABC123 在 09:30 在 EQP01 的 KEYLOT 为什么没生效"、"lot XYZ 在 stepseq 1000 的 PRIOR_1 为什么是 5"。
---

# sorting-diagnose

诊断 Sorting 指标的实际生效值与理论生效值是否一致；不一致时给出原因。

---

## 何时触发

用户的问题命中以下两类模式之一：

1. **未生效类**："某 lot 在 [时间/stepseq] 在 [机台] 的 Sorting [名] 为什么没生效"
2. **取值类**："某 lot 在 [时间/stepseq] 在 [机台] 的 Sorting [名] 为什么是 [值]"

机台是可选的，其余参数必填。

---

## Step 0：参数收集

执行前先确认四个参数；任一缺失就向用户追问，**不要靠猜**：

| 参数 | 必选 | 形式 | 备注 |
|---|---|---|---|
| `lotid` | ✅ | 字符串 / 列表 | 目标 Lot |
| `time` | ✅ | 时间点 / 时间段 / stepseq | 三选一即可 |
| `sorting` | ✅ | 字符串 / 列表 | 如 `KEYLOT`、`PRIOR_1`，大小写不敏感，内部统一转大写 |
| `eqpid` | ⛔ | 字符串 / 列表 | 不给则由 Step 2 自动推断 |

---

## 执行流程

完整 Step 0 → Step 6 见 [workflow.md](./workflow.md)。**主流程不要为任何具体 Sorting 写计算逻辑**。

---

## Step 5：策略分发（核心设计）

Step 5（计算理论生效值）是 Sorting 特有的，**通过 registry 分发到独立规则文件**：

1. 读取 [rules/_registry.md](./rules/_registry.md)，按 `sorting` 名查到对应规则文件路径
2. 加载该规则文件，严格按文件内定义的「输入字段 / 取数脚本 / 计算公式 / 边界条件」算理论值
3. registry 中没有该 Sorting → 向用户输出："`<sorting>` 暂未配置计算规则，请在 `rules/` 下新增对应文件并在 `_registry.md` 注册"，然后中止

---

## 新增一个 Sorting

1. 复制 [rules/_template.md](./rules/_template.md) 为 `rules/<sorting_lowercase>.md`
2. 在 `scripts/` 下加对应取数脚本（参考 `keylot_whitelist.py` / `internalpri_history.py`），填充模板的 6 个区段（输入 / 取数脚本 / 公式 / 边界 / 示例 / 已知坑）
3. 在 [rules/_registry.md](./rules/_registry.md) 加一行映射
4. 不需要改 SKILL.md 或 workflow.md
