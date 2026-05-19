# 规则文件：`INTERNALPRI`

判定一个 Lot 在指定时间窗内的「内部优先级 (InternalPri)」的理论生效值。

数据来源：`rpt6.lot_history` 的 `internalpriority` 字段。命中规则：值**不为 `null` / `0` / `-9999`** 视为生效，否则视为"未生效"。

---

## 1. 基本信息

| 字段 | 值 |
|---|---|
| Sorting 名（registry 大写键） | `INTERNALPRI` |
| rtdinfo key（case-sensitive） | `InternalPri` ⚠️ 与 SORTING 大小写不一致 |
| 业务含义 | 该 Lot 在时间窗内被赋予的内部优先级数值 |
| 取值类型 | 数值（NUMBER）；含三个"未生效"哨兵：`null`、`0`、`-9999` |
| 取值范围 | 生效：任意非哨兵的 NUMBER；未生效：`null` / `0` / `-9999` |
| 负责人 | TODO（请补） |

---

## 2. 输入字段

| 字段 | 来源 | 类型 | 说明 |
|---|---|---|---|
| `lotid` | 流程入参 | VARCHAR | 待判断的 Lot 名 |
| `starttime` | Step 1 算出 | VARCHAR `YYYY-MM-DD HH:MM:SS` | 时间窗起 |
| `endtime` | Step 1 算出 | VARCHAR `YYYY-MM-DD HH:MM:SS` | 时间窗止 |
| `lotname` | `rpt6.lot_history` | VARCHAR | 等于入参 `lotid` |
| `eventtime` | `rpt6.lot_history` | DATE | 事件时间，落在 `[starttime, endtime]` 内 |
| `internalpriority` | `rpt6.lot_history` | NUMBER | 理论生效值来源；命中 `null`/`0`/`-9999` 视为未生效 |

---

## 3. 取数（脚本调用）

按 [workflow.md 的「查询机制」](../workflow.md#查询机制调脚本不要手写-sql) 调脚本，不要手写 SQL。

```bash
./skills/sorting-diagnose/scripts/internalpri_history.py \
  --lotid '{lotid}' \
  --start '{starttime}' --end '{endtime}'
```

脚本自动处理：单引号转义、`YYYY-MM-DD HH:MM:SS` 格式校验、SQL 端用 `to_date(..., 'YYYY-MM-DD HH24:MI:SS')` 与 `eventtime` DATE 列对齐（避免 NLS 隐式转换的坑，详见 §6）。可加 `--print-sql` 看实际 SQL，`--max-rows N` 调大上限。

返回字段：

| 列名（大写） | 含义 |
|---|---|
| `EVENTTIME` | 事件时间，Oracle DATE |
| `INTERNALPRIORITY` | 内部优先级数值；命中 `null`/`0`/`-9999` 视为未生效 |

解析：

```python
# 伪代码
result = json.loads(stdout)
if not result["ok"]:
    abort(f"INTERNALPRI 取数失败：{result['errorType']}: {result['error']}")

events = [
    {
        "eventtime":        row["EVENTTIME"],
        "internalpriority": row["INTERNALPRIORITY"],
    }
    for row in result["rows"]
]
```

若 `result["truncated"]` 为 `true`：加大 `--max-rows` 重跑，或在输出中提示用户时间窗内事件过多、判定可能不完整。

---

## 4. 计算公式

```
SENTINELS = {None, 0, -9999}

effectiveEvents = [
    e for e in events
    if e["internalpriority"] not in SENTINELS
]
```

决策表：

| `effectiveEvents` 状态 | 理论值 | 解读 |
|---|---|---|
| 为空 | `<未生效>`（建议用 `None` 或字符串 `"NOT_EFFECTIVE"`） | 时间窗内没有产生有效的 InternalPri |
| 只有 1 条 | 该条的 `internalpriority` | 唯一生效值 |
| 多条且值全部相同 | 该统一值 | 多次生效但稳定 |
| 多条且值发生变化 | 取 `eventtime` 最大那条的值 | 后值覆盖前值；同时把变化轨迹一并回给用户，对应 workflow.md Step 4 "发生变化"分支 |

---

## 5. 边界条件与异常分支

- **SQL 返回零行**：该 Lot 在 `[starttime, endtime]` 内无任何 `lot_history` 事件 → 理论值 = 未生效
- **多行结果**：按 `eventtime` 升序排，取最后一条作为最终理论值；变化轨迹保留供 Step 6 解释差异
- **`lotid` 大小写**：精确匹配，不做归一化（与 KEYLOT 一致）
- **SQL 失败/超时**：中止 Step 5，把 wrapper 返回的 `error` / `errorType` 转给用户，不要回退默认值

---

## 6. 已知坑

- **日期格式串必须用 `HH24:MI:SS`**：Oracle 里 `hh` 是 12 小时制、`mm` 是月份（非分钟）。若照搬 `'YYYY-MM-DD hh:mm:ss'`：下午的小时会被截到 1–12，且分钟段被当成月份，整段日期会解析错乱。当前 SQL 已修正
- **哨兵值 `-9999` 不要参与比对**：业务上 `-9999` 意为"未赋值"。如果 Step 6 把它当成普通整数和 `rtdinfo` 中的实际值比对，可能出现"实际 -9999 / 理论 -9999 → 一致"的假阴性；正确做法：理论值落到哨兵 → 输出"未生效"，与 rtdinfo 中是否存在该 Sorting 段做"存在性"比对而非"数值"比对
- **`rtdinfo` 中的键名与 SORTING 不一致**：registry SORTING 列是大写 `INTERNALPRI`，但 `rtdinfo` 里真实的键是 PascalCase 的 `InternalPri`。workflow.md Step 3 / Step 4 已经改用 `{SORTING_KEY}` 占位符从 `_registry.md` 的 rtdinfo key 列读，不会再写错。但如果你看到 Step 4 抓不到实际值（result 全 NULL），第一时间回 `_registry.md` 复核 rtdinfo key 列是否仍是 `InternalPri`
- **时区**：`eventtime` 是 DATE（无时区），`starttime`/`endtime` 是字符串。若 DB 时区与业务时区不一致，时间窗判断会偏移；需要时改用 `cast (eventtime as timestamp with local time zone)` 或预先转齐时区
- **边界闭/开**：当前是闭区间 `>=` 和 `<=`。若业务希望半开区间，调整为 `>` / `<`

---

## 7. 示例

| 输入（合成） | SQL 返回 `events` | 理论值 | 说明 |
|---|---|---|---|
| `lotid='LOT0001'`，窗口内 | `[{eventtime: ..., internalpriority: 5}]` | `5` | 单条生效 |
| `lotid='LOT0001'`，窗口内 | `[{..., 0}, {..., 7}]` | `7` | `0` 是哨兵被过滤，仅剩 `7` |
| `lotid='LOT0001'`，窗口内（升序） | `[{..., 3}, {..., 8}]` | `8`，并附变化轨迹 `3 → 8` | 多次生效，取最后一条 |
| `lotid='LOT0002'`，窗口内 | `[]` | `<未生效>` | 时间窗内无事件 |
| `lotid='LOT0003'`，窗口内 | `[{..., -9999}, {..., null}, {..., 0}]` | `<未生效>` | 全是哨兵 |
