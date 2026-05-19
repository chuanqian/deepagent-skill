# Sorting 规则注册表

主流程的 **Step 5** 通过本表把 Sorting 名分发到具体的规则文件。`workflow.md` Step 3 / Step 4 的脚本（`check_sorting_hit.py` / `get_actual_value.py`）会**机器解析**本表的「映射」表格，从中读取 **rtdinfo key** 列。

> ⚠️ **机器解析格式约束**：「映射」段下方的表格被 `scripts/_common.py::load_registry()` 按行解析。改格式前请同时核对解析逻辑：
> - 表头必须含 `SORTING` 和 `rtdinfo key` 字样
> - SORTING 列写大写裸字符串；`rtdinfo key` 列用反引号包裹真实键名
> - 表格第一遇到非 `|` 开头的行即终止（包括空行）；演示用的 HTML 注释例子放在表格后即可
> - 同一 SORTING 出现多次以最后一次为准（一般别这么干）

## 规则

- `SORTING` 列一律**大写**，匹配时把用户输入也转大写。它用于 Step 5 的 registry 分发
- `rtdinfo key` 列是 **case-sensitive** 的真实键名，用于 Step 3 / Step 4 在 `rtdinfo` 中 `INSTR` / `REGEXP_SUBSTR`。**可能与 SORTING 列大小写不一致**（例：`INTERNALPRI` 在 rtdinfo 里是 `InternalPri`）。第一次接入新 Sorting 时务必先 `SELECT rtdinfo FROM rtd6.fabrtdlog WHERE ...` 看一眼真实样本，再填本列
- `规则文件` 列是相对本目录的路径
- `负责人` 选填，便于追问
- 加新行 = 注册新 Sorting；删行 = 停用规则
- **没注册的 Sorting，主流程会中止并提示补 registry**

## 映射

| SORTING | rtdinfo key | 规则文件 | 负责人 | 备注 |
|---|---|---|---|---|
| KEYLOT | `KEYLOT` | ./keylot.md | TODO | 基于 MFGCIM_SYN.tb_quota_apply_info 白名单判断 |
| INTERNALPRI | `InternalPri` | ./internalpri.md | TODO | 取 rpt6.lot_history.internalpriority，哨兵值 null/0/-9999 视为未生效 |
| PRIOR_1 | `PRIOR_1` | ./prior_1.md | TODO | 取 rpt6.lot_history 最新一条 (priority, internalpriority) 拼接；priority!=1 一律 -9999。⚠️ rtdinfo key 为占位，首次接入前务必 `SELECT rtdinfo FROM rtd6.fabrtdlog ...` 复核真实大小写 |

<!-- 在上面表格中追加新行，例如：
| PRIOR_1 | ./prior_1.md | 张三 | |
| HOLD_LOT | ./hold_lot.md | 李四 | |
-->
