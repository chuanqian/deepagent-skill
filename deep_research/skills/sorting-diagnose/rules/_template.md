# 规则文件模板：`<SORTING_NAME>`

> 复制本文件为 `rules/<sorting_lowercase>.md`，按区段填充后到 `_registry.md` 注册一行。
> 文件名约定：小写，全大写 Sorting 名转下划线即可，例如 `KEYLOT` → `keylot.md`、`PRIOR_1` → `prior_1.md`。

---

## 1. 基本信息

| 字段 | 值 |
|---|---|
| Sorting 名（registry 大写键） | `XXX` |
| rtdinfo key（case-sensitive） | TODO（先 `SELECT rtdinfo FROM rtd6.fabrtdlog WHERE ...` 看一眼真实样本再填；可能与 SORTING 大小写不同） |
| 业务含义 | 一句话说明这个 Sorting 是干什么的 |
| 取值类型 | 枚举 / 数值 / 字符串 / 布尔 等 |
| 取值范围 | 如 `Y / N`、`0~10`、自由字符串 |
| 负责人 | 张三（便于反查业务规则） |

---

## 2. 输入字段（计算理论值需要哪些数据）

| 字段 | 来源表 / 接口 | 取值范围 | 说明 |
|---|---|---|---|
| `<字段1>` | `rtd6.xxx` | | |
| `<字段2>` | `rpt6.xxx` | | |
| ... | | | |

---

## 3. 取数（脚本调用）

按 [workflow.md 的「查询机制」](../workflow.md#查询机制调脚本不要手写-sql) 调脚本，不要在文档里写 SQL 让 Claude 替换占位符——这条路已经被废弃了。

### 3.1 写脚本

在 `scripts/` 下新增一个文件 `<sorting_lowercase>_<purpose>.py`（命名参考 `keylot_whitelist.py`、`internalpri_history.py`），结构照搬现有脚本：

- 用 `_common.py` 的 `escape_sql_string` / `validate_time` / `format_eqpid_list` / `write_sql_and_run` / `emit_error` / `resolve_sorting_key`，**不要**自己拼字符串、自己写 subprocess、自己做时间格式校验、自己解析 registry——这些已经稳定，重写就是给系统加裂缝
- `argparse` 列出本规则真正用到的参数（lotid / start / end / 其他），可选参数也走 argparse 的 `action='append'` / `type=int`
- 必须支持 `--print-sql`（调试）和 `--max-rows`（透传）
- 主流程结尾必须是 `return write_sql_and_run(sql, tag="<short-tag>", max_rows=..., print_sql=...)`

写完先跑一次 `--print-sql` 肉眼看 SQL 是否对：
```bash
./scripts/<sorting_lowercase>_<purpose>.py --print-sql ...其它参数
```

### 3.2 在本文件里登记脚本

只描述"调谁、传什么、读什么"——**不要**复制 SQL 进来。例：

```bash
./skills/sorting-diagnose/scripts/<sorting>_<purpose>.py \
  --lotid '{lotid}' \
  --start '{starttime}' --end '{endtime}'
```

返回字段表（Oracle 列名全大写）：

| 列名 | 含义 |
|---|---|
| `<FIELD_A>` | TODO |
| `<FIELD_B>` | TODO |

### 3.3 解析返回

```python
# 伪代码
result = json.loads(stdout)
if not result["ok"]:
    abort(f"<SORTING> 取数失败：{result['errorType']}: {result['error']}")

data = [
    {"<FIELD_A>": row["<FIELD_A>"], "<FIELD_B>": row["<FIELD_B>"]}
    for row in result["rows"]
]
```

若 `result["truncated"]` 为 `true`：加大 `--max-rows` 重跑，或告知用户哪些判断不受影响（例："白名单截断只影响命中判定，未命中的 Lot 仍然可靠"）。

---

## 4. 计算公式

用伪代码 / 决策表 / 步骤式描述，**不要写成只有自己能看懂的一行**。决策类首选决策表：

| 条件1 | 条件2 | ... | 理论值 |
|---|---|---|---|
| | | | |

数值类写公式：

```
理论值 = f(字段1, 字段2, ...)
```

---

## 5. 边界条件与异常分支

- 输入字段缺失：返回 `UNKNOWN` 还是中止？
- 取数 SQL 返回零行：默认值是什么？
- 多行结果冲突时如何取舍（最新 / 最早 / 最大）？

---

## 6. 已知坑（可选，但强烈建议写）

- 业务上容易踩的判断错误
- 与相邻 Sorting 的耦合
- 历史变更点（什么时候改过逻辑，旧数据是否还按旧逻辑算）

---

## 7. 示例（建议放 2~3 组）

| 输入 | 期望理论值 | 说明 |
|---|---|---|
| | | |
