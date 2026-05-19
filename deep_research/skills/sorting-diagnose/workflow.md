# Workflow: Step 0 → Step 6

主流程。**所有具体 Sorting 的计算公式不写在这里**，Step 5 仅做"按 registry 分发"。

所有时间参数统一格式 `YYYY-MM-DD HH:MM:SS`（24 小时制）。脚本会校验格式，写错直接报 `ArgumentError`。

---

## 查询机制：调脚本，不要手写 SQL

本 skill 不直接连数据库；所有查询都封装成 `scripts/` 下的 Python CLI，由它们生成 SQL、写临时文件、调 `scripts/query.py` 直连 MySQL、把结果原样吐到 stdout。**不要在对话里手写或拼接 SQL**——占位符替换、单引号转义、`{SORTING_KEY}` 大小写、`{eqpidList}` 的引号+逗号格式都是脚本负责的，越界手搓只会让系统变脆。

### 脚本清单

| 用途 | 脚本 | 关键参数 |
|---|---|---|
| Step 2 找机台 | `scripts/find_eqps.py` | `--lotid` `--start` `--end` `[--stepseq]` |
| Step 3 校验 rtdinfo 命中 | `scripts/check_sorting_hit.py` | `--eqpid`(可多次) `--sorting` `--start` `--end` |
| Step 4 取实际生效值 | `scripts/get_actual_value.py` | `--lotid` `--sorting` `--start` `--end` |
| KEYLOT 白名单 | `scripts/keylot_whitelist.py` | （无） |
| InternalPri 历史 | `scripts/internalpri_history.py` | `--lotid` `--start` `--end` |

每个脚本都接受：
- `--max-rows N`：覆盖默认 10000 行上限（透传给 `query.py`）
- `--print-sql`：只打印将要执行的 SQL，不连库；调试时用，不要把它当结果

### 调用前置条件

- 本地 MySQL 正在跑（默认 `localhost:3306`，库 `test`，用户 `root`）；脚本内部会用 `pymysql` 直连
- 凭据**内联在 `scripts/query.py`** 里（host/port/user/password/database），换环境改这些常量或用环境变量覆盖：`DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- 连接失败（端口未开、密码错、库不存在等）脚本会原样吐 `{"ok": false, "error": "..."}`，**不要**重试或回退默认值，先确认 MySQL 起来了
- 脚本会把生成的 SQL 落到 `tmp/sd-<tag>-<uuid>.sql`，**保留**作为审计/排查轨迹

### 解析返回 JSON

每个脚本的 stdout 都是单行 JSON，**和 `query.py` 形状一致**——成败两种：

```json
// 成功
{"ok": true, "rowCount": N, "truncated": false, "rows": [{"EQPID": "...", ...}, ...]}
// 失败（来自 query.py 的 DB 错，或来自脚本本身的参数校验）
{"ok": false, "error": "<msg>", "errorType": "<class>"}
```

- 失败：把 `error`/`errorType` 原样转给用户并中止当前 Step，**不要**重试或回退默认值
- `truncated=true`：提醒用户结果被截断，建议加 `--max-rows` 重跑（或在调用 shell 里设 `DB_MAX_ROWS` 环境变量）
- 列名一律**全大写**（`EQPID`、`LOTID`、`TXNTIME`、`RESULT` 等）；`query.py` 会把每行 dict 的 key 统一 upper，读字段时用大写键

### SORTING 名怎么传

Step 3 / Step 4 / 各 rule 脚本统一传 **`--sorting <NAME>`**（大小写都行，脚本会 `.upper()`）；脚本内部去 `rules/_registry.md` 查 `rtdinfo key` 列，把 case-sensitive 的真实键名解析出来用在 SQL 里。例：

- `--sorting INTERNALPRI` → SQL 里用 `'InternalPri'`（PascalCase）
- `--sorting keylot` → SQL 里用 `'KEYLOT'`

未注册的 Sorting，脚本会吐：
```json
{"ok": false, "error": "Sorting 'XXX' is not registered ...", "errorType": "ArgumentError"}
```
照常作为 Step 异常处理——不要尝试用 `--sorting-key` 绕过；这个 override 只是给开发期调试新 Sorting 用的临时口子，正经流程里**不应该出现**。

---

## Step 1：确定时间范围

得到一对 `(starttime, endtime)`：

| 用户给的 | starttime | endtime |
|---|---|---|
| 时间段 `[t1, t2]` | `t1` | `t2` |
| 单一时间点 `t` | `t - 30min` | `t` |
| 仅 `stepseq`（无时间） | `now() - 30min` | `now()` |

---

## Step 2：确定机台

- 用户已给 `eqpid` → 跳过本步，直接进入 Step 3
- 未给 `eqpid` → 调脚本：

```bash
./skills/sorting-diagnose/scripts/find_eqps.py \
  --lotid '{lotid}' \
  --start '{starttime}' --end '{endtime}'
# 用户给了 stepseq 时再加： --stepseq '{stepseq}'
```

解析 `rows`，取 `EQPID` 字段去重得到 `eqpidList`。

**返回为空** → **直接中止整个流程**，原样输出下面这句话（不要改写、不要补充时间段或机台信息）：
> 当前时间段内无相关派工记录，请再次确认

> ⚠️ 不要自动放宽时间窗口（例如把 30 分钟扩成 2 小时、1 天）重跑这条脚本。时间窗口由 Step 1 一次性确定，本步只在该窗口内查一次；找不到就让用户重新给参数，不要替用户做"再宽一点试试"的猜测。

**返回多条** → 后续每个 EQP 各跑一次 Step 3~6。

---

## Step 3：确认派工日志里是否真实命中该 Sorting

只看派工时 `rtdinfo` 中是否真的包含该 Sorting —— 这是唯一可信的"该 Sorting 在该 EQP 上是否参与了派工"信号。

```bash
./skills/sorting-diagnose/scripts/check_sorting_hit.py \
  --eqpid '{eqpid1}' --eqpid '{eqpid2}' ... \
  --sorting '{SORTING}' \
  --start '{starttime}' --end '{endtime}'
```

> `--sorting` 传用户问题里的 Sorting 名（大小写不敏感），脚本自动从 `_registry.md` 查 case-sensitive 的 rtdinfo 键。

判定：

- 返回为空 → 中止：
  > {starttime} ~ {endtime} 时间段内，触发派工的 EQP 有 {eqpidList}，但都未命中该 Sorting，请确认。
- 返回数量 < `eqpidList` 长度 → 记录"未命中该 Sorting 的 EQP 子集"，后续 Step 4/5 只对"命中"的子集执行；最终报告里要提示哪些 EQP 未命中。

---

## Step 4：取实际生效值

```bash
./skills/sorting-diagnose/scripts/get_actual_value.py \
  --lotid '{lotid}' \
  --sorting '{SORTING}' \
  --start '{starttime}' --end '{endtime}'
```

返回字段：`TXNTIME` / `EQPID` / `RESULT`（`RESULT` 即 rtdinfo 里 `KEY=value` 那一段子串，到下个 `;` 为止）。

> 如果 `RESULT` 全 NULL，第一反应是回 `_registry.md` 确认 rtdinfo key 列写对了大小写——脚本读什么就用什么，错的根源在 registry 而不是脚本。

输出策略：

- 多行结果但 `RESULT` 全相同 → 输出该值 + "`{starttime} ~ {endtime}` 时间段内，该 Sorting 的生效值未发生变化"
- `RESULT` 发生过变化 → 输出每次变化的 `(TXNTIME, EQPID, RESULT)` 时序列表
- 零行 → 提示"该 Lot 在该时间段内无派工记录"，跳过 Step 5、Step 6

---

## Step 5：计算理论生效值（**策略分发**）

**不要在这里写任何 Sorting 的算法**。流程是：

1. 读取 [rules/_registry.md](./rules/_registry.md)
2. 用 `UPPER(sorting)` 匹配 registry，拿到对应 `rules/<file>.md` 路径
3. 没找到 → 输出：
   > `{sorting}` 暂未配置计算规则，请在 `rules/` 下补充 `<sorting>.md` 并在 `_registry.md` 注册。

   然后中止 Step 5、Step 6。
4. 加载规则文件，按文件中定义的「输入 / 取数脚本 / 计算公式 / 边界」一步步算出理论值

---

## Step 6：对比

| 实际值 vs 理论值 | 输出 |
|---|---|
| 一致 | 返回实际生效值，并简述"理论与实际一致" |
| 不一致 | 同时返回：①实际值；②理论值；③理论计算用到的所有输入字段及其值；④规则文件路径，便于人工复核 |

---

## 多 EQP / 多 Lot / 多 Sorting 的处理

输入是列表时，**笛卡尔展开**逐一执行 Step 1~6，但要：

- 按 `(lotid, sorting)` 分组聚合输出，避免刷屏
- 每组开头标明 `lotid` + `sorting` + 涉及到的 `eqpidList`
- 中间任何一个 EQP 因数据缺失中止，不影响其他 EQP 继续
