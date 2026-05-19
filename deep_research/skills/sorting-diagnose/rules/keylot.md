# 规则文件：`KEYLOT`

判定一个 Lot 是否为「关键 Lot (Key Lot)」。来源：QA 申请表 `MFGCIM_SYN.tb_quota_apply_info` 中所有 `status='COMFIRM'` 且 `KEYLOT=1` 的记录的 `lotname` 集合。

---

## 1. 基本信息

| 字段 | 值 |
|---|---|
| Sorting 名（registry 大写键） | `KEYLOT` |
| rtdinfo key（case-sensitive） | `KEYLOT`（与 SORTING 同） |
| 业务含义 | 该 Lot 是否被 QA 申请单标记为关键 Lot |
| 取值类型 | 布尔（输出为 `Y`/`N` 字符串，对应 True/False） |
| 取值范围 | `Y` / `N` |
| 负责人 | TODO（请补） |

---

## 2. 输入字段

| 字段 | 来源 | 类型 | 说明 |
|---|---|---|---|
| `lotid` | 流程入参（用户问题） | VARCHAR | 待判断的 Lot 名 |
| `lotname` | `MFGCIM_SYN.tb_quota_apply_info` | VARCHAR | 关键 Lot 白名单中的 Lot 名 |
| `status` | `MFGCIM_SYN.tb_quota_apply_info` | 枚举 | 仅取 `'COMFIRM'`（注：业务拼写就是 `COMFIRM`，不是 `CONFIRM`） |
| `KEYLOT` | `MFGCIM_SYN.tb_quota_apply_info` | NUMBER | 是否为关键 Lot 的标记列，仅取 `1`（`0` 视为未启用） |

**本规则不需要任何时间过滤**——白名单是全历史最新视图。

---

## 3. 取数（脚本调用）

按 [workflow.md 的「查询机制」](../workflow.md#查询机制调脚本不要手写-sql) 调脚本，不要手写 SQL。

```bash
./skills/sorting-diagnose/scripts/keylot_whitelist.py
```

本规则无任何运行时入参（白名单是全历史最新视图）。`--print-sql` 可看实际 SQL，`--max-rows N` 可调大上限。

解析返回 JSON 的 `rows` 数组——**列名 Oracle 返回全大写**（这里是 `LOTNAME`）：

```python
# 伪代码
result = json.loads(stdout)
if not result["ok"]:
    abort(f"KEYLOT 取数失败：{result['errorType']}: {result['error']}")
keylotSet = {row["LOTNAME"] for row in result["rows"]}
```

`result["truncated"]` 若为 `true`，说明白名单可能不完整（超过 `--max-rows` 上限），需要：
- 重跑时加大上限：`--max-rows 100000`
- 或在最终回复里提醒用户"白名单已截断，未命中的 Lot 判定仅供参考"

---

## 4. 计算公式

```
keylotSet = { 上面 SQL 返回的所有 lotname }

理论值(lotid) = 'Y'  if lotid ∈ keylotSet
              = 'N'  otherwise
```

决策表：

| 条件 | 理论值 |
|---|---|
| `lotid` 在 `keylotSet` 中 | `Y`（True） |
| `lotid` 不在 `keylotSet` 中 | `N`（False） |

多 Lot 入参时，对每个 Lot 独立判断，输出 `{lotid → 理论值}` 映射；不要把列表"合并成一个值"。

---

## 5. 边界条件与异常分支

- **SQL 返回零行**：`keylotSet` 为空集，所有入参 Lot 的理论值都是 `N`。这是合法状态，不报错
- **入参 `lotid` 大小写**：精确匹配，**不做大小写归一化**。如业务确认 Lot 名忽略大小写，再统一在 SQL 端 `UPPER(lotname)` 和入参侧同时转大写
- **SQL 失败/超时**：中止 Step 5，向用户报错并附原始错误，不要回退成 `N`（否则会假阴性）
- **入参为 Lot 列表**：循环判断；任一 Lot 出错不影响其他 Lot 的判断

---

## 6. 已知坑

- **`status` 拼写**：业务用的字面值是 `'COMFIRM'`（少一个 N），SQL 里**不要**自作主张改成 `'CONFIRM'`，会导致零行结果误判全员为 `N`
- **`KEYLOT` 是列名，不是 `rtdinfo` 子串**：这张表里没有 `rtdinfo` 字段，`KEYLOT` 是一个数字标记列，判定条件就是 `KEYLOT = 1`。不要写成 `INSTR(rtdinfo, 'KEYLOT') > 0`——会直接 `ORA-00904: invalid identifier`
- **`KEYLOT` 的取值**：业务上以 `1` 代表"是关键 Lot"。若未来出现 `2`/`-1` 等扩展值，需要重新和业务确认是否仍按 `=1` 过滤
- **Y/N vs True/False 对照**：Step 4 从 `rtd6.fabrtdlog.rtdinfo` 抽出的实际值通常长这样 `KEYLOT=Y` 或 `KEYLOT=N`，本规则输出 `Y`/`N` 是为了在 Step 6 直接和实际值对齐。如果未来实际值变成 `True/False` 或 `1/0`，需要在 Step 6 之前显式归一化
- **白名单时效**：当前 SQL 没过滤"申请过期/失效"，如果业务上 KEYLOT 标记会到期，本规则会误判已过期的 Lot 仍为 `Y`，届时需补 `expire_time`/`valid_until` 等条件

---

## 7. 示例

| 入参 `lotid` | SQL 返回 `keylotSet`（合成） | 期望理论值 | 说明 |
|---|---|---|---|
| `'LOT0001'` | `{'LOT0001', 'LOT0005'}` | `Y` | 命中名单 |
| `'LOT0002'` | `{'LOT0001', 'LOT0005'}` | `N` | 不在名单 |
| `'LOT0003'` | `{}` | `N` | 系统无任何 KEYLOT 申请，合法的全员 `N` |
| `['LOT0001', 'LOT0002']` | `{'LOT0001'}` | `{LOT0001: Y, LOT0002: N}` | 多 Lot 输入返回映射，不返回单值 |
