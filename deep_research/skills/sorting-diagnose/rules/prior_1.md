# 规则文件：`PRIOR_1`

判定一个 Lot 在指定时间窗内的「PRIOR_1」的理论生效值。

数据来源：`rpt6.lot_history` 中**最新一条** `eventtime` 落在窗口内的事件，取其 `priority` 与 `internalpriority` 两个栏位拼接而成。

业务逻辑可以一句话概括：**只有 `priority == 1` 时 PRIOR_1 才"真生效"**；其它情况一律返回哨兵值 `-9999`。

---

## 1. 基本信息

| 字段 | 值 |
|---|---|
| Sorting 名（registry 大写键） | `PRIOR_1` |
| rtdinfo key（case-sensitive） | TODO（首次接入时先 `SELECT rtdinfo FROM rtd6.fabrtdlog WHERE ...` 看一眼真实样本，再回 `_registry.md` 把这一列填准；可能不是裸 `PRIOR_1`） |
| 业务含义 | 把 `priority` 与 `internalpriority` 编码成一个负整数，作为派工里的 PRIOR_1 信号 |
| 取值类型 | 数值（NUMBER），始终为负 |
| 取值范围 | `priority == 1` 时落在 `-199 ~ -100` 区间（详见 §4）；其它情况固定 `-9999` |
| 负责人 | TODO（请补） |

---

## 2. 输入字段

| 字段 | 来源 | 类型 | 说明 |
|---|---|---|---|
| `lotid` | 流程入参 | VARCHAR | 待判断的 Lot 名 |
| `starttime` | Step 1 算出 | VARCHAR `YYYY-MM-DD HH:MM:SS` | 时间窗起 |
| `endtime` | Step 1 算出 | VARCHAR `YYYY-MM-DD HH:MM:SS` | 时间窗止 |
| `lotname` | `rpt6.lot_history` | VARCHAR | 等于入参 `lotid` |
| `eventtime` | `rpt6.lot_history` | DATE | 事件时间，落在 `[starttime, endtime]` 内；用于挑"最新"那一条 |
| `priority` | `rpt6.lot_history` | NUMBER | 主优先级；只有 `1` 才进入拼接逻辑 |
| `internalpriority` | `rpt6.lot_history` | NUMBER | 内部优先级；与 `priority` 拼接，个位数前补 `0` |

---

## 3. 取数（脚本调用）

按 [workflow.md 的「查询机制」](../workflow.md#查询机制调脚本不要手写-sql) 调脚本，不要手写 SQL。

```bash
./skills/sorting-diagnose/scripts/prior_1_history.py \
  --lotid '{lotid}' \
  --start '{starttime}' --end '{endtime}'
```

脚本自动处理：单引号转义、`YYYY-MM-DD HH:MM:SS` 格式校验、SQL 端用 `to_date(..., 'YYYY-MM-DD HH24:MI:SS')` 与 `eventtime` DATE 列对齐（避免 NLS 隐式转换的坑，详见 §6）；并在 SQL 内用 `ORDER BY eventtime DESC` + `ROWNUM = 1` 直接挑出最新一条，避免被 `--max-rows` 截断。可加 `--print-sql` 看实际 SQL，`--max-rows N` 调大上限。

返回字段（最多 1 行）：

| 列名（大写） | 含义 |
|---|---|
| `EVENTTIME` | 事件时间，Oracle DATE，窗口内最新 |
| `PRIORITY` | 主优先级 |
| `INTERNALPRIORITY` | 内部优先级 |

解析：

```python
# 伪代码
result = json.loads(stdout)
if not result["ok"]:
    abort(f"PRIOR_1 取数失败：{result['errorType']}: {result['error']}")

if not result["rows"]:
    latest = None  # 时间窗内无事件，进入 §5 的"零行"分支
else:
    row = result["rows"][0]
    latest = {
        "eventtime":        row["EVENTTIME"],
        "priority":         row["PRIORITY"],
        "internalpriority": row["INTERNALPRIORITY"],
    }
```

---

## 4. 计算公式

输入 `latest = {priority, internalpriority}` 来自 §3 的最新一条事件。决策表：

| `latest` 状态 | `priority` | `internalpriority` | 理论值 PRIOR_1 |
|---|---|---|---|
| `None`（窗口内无事件） | — | — | `-9999`（视同未生效，与 `priority != 1` 同一分支） |
| 有 | `== 1` | 非 null 的 NUMBER | `-1 * int(str(priority) + zero_pad2(internalpriority))` |
| 有 | `== 1` | `null` | `-9999`（无法拼接，按未生效处理；详见 §5） |
| 有 | `!= 1`（含 `null`） | 任意 | `-9999` |

其中 `zero_pad2(n)` 表示「个位数前补 0 凑成 2 位」：

```
zero_pad2(n) =
    str(n).zfill(2)        if 0 <= n <= 9    → '00'..'09'
    str(n)                 if n >= 10        → 原样（业务上 internalpriority 不会出现 ≥100）
```

伪代码：

```python
SENTINEL = -9999

if latest is None or latest["priority"] != 1 or latest["internalpriority"] is None:
    prior_1 = SENTINEL
else:
    p  = int(latest["priority"])              # 必为 1
    ip = int(latest["internalpriority"])
    prior_1 = -1 * int(f"{p}{ip:02d}")        # e.g. p=1, ip=2  -> int("102") = 102 -> -102
```

举例：

| `priority` | `internalpriority` | 拼接字符串 | PRIOR_1 |
|---|---|---|---|
| `1` | `2` | `"1" + "02"` → `"102"` | `-102` |
| `1` | `9` | `"1" + "09"` → `"109"` | `-109` |
| `1` | `10` | `"1" + "10"` → `"110"` | `-110` |
| `1` | `99` | `"1" + "99"` → `"199"` | `-199` |
| `1` | `0` | `"1" + "00"` → `"100"` | `-100`（注意：业务上 `0` 是否合法请与负责人确认；当前公式按字面执行） |
| `2` | 任意 | — | `-9999` |
| `null` | 任意 | — | `-9999` |

---

## 5. 边界条件与异常分支

- **SQL 返回零行**：该 Lot 在 `[starttime, endtime]` 内无任何 `lot_history` 事件 → 理论值 = `-9999`（与 `priority != 1` 同一未生效语义）
- **`priority == 1` 但 `internalpriority` 为 `null`**：无法拼接，按 `-9999` 处理。这是与 INTERNALPRI 哨兵语义一致的保守做法；如果业务希望此时按 `priority` 单独编码（例如 `-100`），需在本节明确改写
- **`internalpriority` 出现负数或 ≥ 100**：当前公式按字面 `int(f"...{ip:02d}")` 执行，会得到非预期长度的字符串。出现这种数据时不要静默放过，先在 Step 6 提醒用户数据异常，再决定是否回退到 `-9999`
- **`priority` 类型**：取自 NUMBER 列，但运算中只关心"是否等于 1"。其它任何值（包括 `0`、`-9999`、`null`、`> 1`）一律走 `-9999` 分支
- **多行结果**：脚本内 `ORDER BY eventtime DESC` + `ROWNUM = 1` 已保证只返回最新一条；如果将来改成多行返回，仍按"取 `eventtime` 最大"那一条计算，并把变化轨迹一并回给用户
- **`lotid` 大小写**：精确匹配，不做归一化（与 KEYLOT / INTERNALPRI 一致）
- **SQL 失败/超时**：中止 Step 5，把 wrapper 返回的 `error` / `errorType` 转给用户，不要回退默认值

---

## 6. 已知坑

- **日期格式串必须用 `HH24:MI:SS`**：Oracle 里 `hh` 是 12 小时制、`mm` 是月份（非分钟）。若照搬 `'YYYY-MM-DD hh:mm:ss'`：下午的小时会被截到 1–12，且分钟段被当成月份，整段日期会解析错乱。当前 SQL 已修正
- **哨兵值 `-9999` 与"实际值"对比**：与 INTERNALPRI 同一个坑——业务上 `-9999` 是"未生效"占位符。若 Step 6 把它当成普通整数和 `rtdinfo` 中的 PRIOR_1 比对，会出现"实际 -9999 / 理论 -9999 → 一致"的假阴性。正确做法：理论值落到 `-9999` → 输出"未生效"，与 rtdinfo 中是否存在该 Sorting 段做"存在性"比对而非"数值"比对
- **拼接是字符串拼，不是算术加法**：`priority * 100 + internalpriority` 看起来等价，但只有在 `priority == 1` 且 `0 <= internalpriority <= 99` 时成立。一旦 `internalpriority` 超界，算术法会静默给出错误结果，字符串拼则容易在长度校验时被发现。统一走字符串拼 + `int()` 这条路
- **`rtdinfo` 中的键名与 SORTING 不一致**：registry SORTING 列是大写 `PRIOR_1`，但 `rtdinfo` 里真实的键大小写未必相同（INTERNALPRI 就踩过这个坑，真实键是 PascalCase 的 `InternalPri`）。第一次接入时务必先 `SELECT rtdinfo FROM rtd6.fabrtdlog WHERE ...` 看一眼真实样本，再回 `_registry.md` 把 `rtdinfo key` 列填准；如果你看到 Step 4 抓不到实际值（result 全 NULL），第一时间回 `_registry.md` 复核
- **时区**：`eventtime` 是 DATE（无时区），`starttime`/`endtime` 是字符串。若 DB 时区与业务时区不一致，时间窗判断会偏移；与 INTERNALPRI 同样需要时改用 `cast (eventtime as timestamp with local time zone)` 或预先转齐时区
- **边界闭/开**：当前是闭区间 `>=` 和 `<=`。若业务希望半开区间，调整为 `>` / `<`

---

## 7. 示例

| 输入（合成） | SQL 返回最新一行 | 理论值 | 说明 |
|---|---|---|---|
| `lotid='LOT0001'`，窗口内 | `{priority: 1, internalpriority: 2}` | `-102` | 个位数补 0 拼成 `"102"`，再取负 |
| `lotid='LOT0001'`，窗口内 | `{priority: 1, internalpriority: 25}` | `-125` | 两位数原样拼成 `"125"` |
| `lotid='LOT0002'`，窗口内 | `{priority: 2, internalpriority: 5}` | `-9999` | `priority != 1`，直接哨兵 |
| `lotid='LOT0003'`，窗口内 | `{priority: null, internalpriority: 7}` | `-9999` | `priority` 为 null，进入 `!= 1` 分支 |
| `lotid='LOT0004'`，窗口内 | `{priority: 1, internalpriority: null}` | `-9999` | 无法拼接，按未生效处理（§5） |
| `lotid='LOT0005'`，窗口内 | `[]` | `-9999` | 时间窗内无事件 |
