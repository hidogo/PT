# 26. AXquant 复盘与预期逻辑的独立复刻与上传识别

> 状态：核心逻辑迁移完成、独立 CLI 全链路跑通（review 复盘重建 + from-jsonl 导出，
> 用 2026-10-15 真实数据端到端验证）。
> 已实测确认：Ptrade「定时上传」= **选取本地文件夹**，逐文件读取整夹上送（非固定单一文件名）。

## 1. 按逻辑拆分：本地运行 vs 云策略确认预期
全链路拆两段，交接只经研究目录文件（时差一天解耦，窗口内策略不交互）：

```text
[本地运行]                          [云策略(Ptrade)确认预期]
涨停池快照 + 持仓 + 复盘洞察          before_trading_start
  + 行情 → 生成复盘         读 expectation_<当日>.csv
  → 次日预期 JSONL → 导出 CSV        竞价确认 / 盘中确认（三态）
  → 上传文件夹（定时上传）→ 研究目录   命中 → 执行买卖（DO_ORDER 门控）
```

- 本地：`build_expectation_bridge.py` 的 `review`（完整复盘重建）与 `from-jsonl`（复用
  既有预期）做离线批处理；纯逻辑全在 `bridge/` 包、零 axquant 依赖。
- 云端：`buysell_core` 只按当天文件逐条“确认”三态再执行。
- 本地只出预期文件，云端只做确认+执行，职责不重叠、可单独演进。

## 2. 自动上传形态：按文件夹路径，不是固定文件名
- 「定时上传」= **选取本地文件夹，逐文件读取该文件夹上送**（实测确认）；手动上传才不支持
  文件夹（需逐个文件，docs/12）。云端按**日期文件名** `expectation_<get_trading_day()>.csv`
  消费（`_load_expectation` 研究根/data 双候选）。
- 故待上传文件夹只放**当天日期命名 CSV**；识别用的 meta 与稳定指针放 `archive\` 不上传。
- 待上传目录结构（默认 `D:\PROJ\PT\data\ptrade_bridge\`）：

```text
ptrade_bridge\
    expectation_YYYY-MM-DD.csv   待上传根：只放当天日期 CSV（from-jsonl/review 自动清理更早）
    archive\
        expectation_<日>.csv.meta.json
        ptrade_today.csv         不上传归档
```

### 自动上传文件识别（`validate`，上送前 fail-fast）
1. 根目录当天 CSV 存在；2. 表头逐列一致；3. 行数 > 0；4. 新鲜度（mtime<12h）；
5. meta（archive）的日期/行数/SHA-1 与文件一致。

## 3. 迁移产物（零 axquant 依赖）
`D:\PROJ\PT\research\expectation\bridge\`：

| 文件 | 职责 | 迁移改动 |
| --- | --- | --- |
| `model.py` | 数据模型、角色与三态常量 | 原样复制 |
| `rules.py` | 次日三态确认规则 | 仅改相对 import |
| `publish.py` | 复盘派生 + 竞价/盘中确认 | 相对 import + 两处 `board_rank` 惰性依赖降级离线桩 |
| `expectation_store.py` | JSONL 存取、进程锁、`export_expectation_csv` | 内联 `file_io/paths`，目录参数化 |
| `__init__.py` | 包导出 | 新建 |

CLI：`D:\PROJ\PT\research\expectation\build_expectation_bridge.py`
```text
py -3.10 build_expectation_bridge.py review      --date 2026-10-15 --next-date 2026-10-16
py -3.10 build_expectation_bridge.py from-jsonl  --date 2026-10-16
py -3.10 build_expectation_bridge.py validate    --date 2026-10-16
```

## 4. 本地完整复盘重建（`review` 子命令）
入口：涨停池快照 + 开仓理由 + 持仓（可选）+ 复盘洞察（可选）→ `make_review_records`
→ 复盘 JSONL → 初始化次日预期（`awaiting_auction` / 按 t1 primary 得 `pending_*`）
→ 预期 JSONL → 导出 CSV。

- 输入默认路径本地优先、AXquant 兜底：`data/buys/open_reason_<T>.jsonl`、
  `data/special_snapshots/<T>.json`；可用 `--open-reason/--snapshots/--positions/--insights` 显式指定。
- 离线降级：无行情补全，`yesterday_open_pct / opened_above_yesterday` 为空并标记
  `review_input_incomplete=true`（已实测如此）；三态仍由 `t1_expectation` 导出，CSV 可用。
- 已实测（2026-10-15）：`603258.XSHG` → `hold/pending_meet`，与 AXquant 原始复盘结论一致。

## 5. 数据契约（与 docs/25 一致）
输入 `position_expectation_<date>.jsonl`；输出 `expectation_<date>.csv` 表头：
`code,side,entry_type,expected_status,yesterday_open_pct,expected_auction_change_pct,seal_amount_t0,board_name,reason`
- 代码后缀 `.SH/.SZ/.BJ` → `.XSHG/.XSHE/.XBJ`（`_ptrade_code`）。
- `side`：`status` 以 `miss` 结尾 → `sell`，否则 `hold`。
- 编码 UTF-8（无 BOM），`csv.writer` 标准写出。

## 6. 已实测
- `bridge` 全包 Python 3.10 编译 + 导入通过，`PTRADE_BRIDGE_DIR=D:\PROJ\PT\data\ptrade_bridge`。
- `from-jsonl`（2026-10-15，4 行）+ `validate` 通过；根只留当天 CSV，meta/today 在 archive。
- `review`（2026-10-15→2026-10-16，1 记录）+ 导出 CSV + `validate` 通过。
- 待上传目录与 archive 结构符合本文件第 2 节。

## 7. 板块强度补齐（已完成，buysell_core）
`_board_strength`：改用 `get_stock_blocks` 返回的**板块代码**调用 `get_industry_stocks`
（修正原误用板块名导致板块强度恒 0）；并优先 `get_sort_msg([code], px_change_rate)` 一次取
板块快照涨跌幅，接口不可用时自动回退板块成员实时涨跌均值。`_board_bonus`（-15~+15 分档）
随强度生效；已用 PT 3.7 编译通过。

## 8. 后续（剩余项）
- 定时上传落地：把 `ptrade_bridge\` 配为该券商「定时上传」选中的本地文件夹即可；若实际
  只支持单文件，改选 `archive\ptrade_today.csv` 固定上传源、云端同名消费。