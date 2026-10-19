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
## 2026-10-18 增补：前瞻预期需同时含「持仓 + 核心苗子」
- 复盘 review（AXquant review/position_review_<T>.jsonl）区分 holding / seedling。前瞻预期应并集两者：
  - 持仓 holding -> side=hold（pending_meet）
  - 核心苗子 seedling -> side=buy（pending_exceed），是次日「超预期确认买入」的候选池
- 契约：CSV side 现允许显式 buy（exporter 优先取记录 side；缺省按 status 建仓方向回落）。
- expected_auction_change_pct：核心苗子用 max(当日竞价涨幅, 3.0) 作为竞价超预期达标阈值（Ptrade 侧 _exp_rt_status 竞价格 a >= 阈值 判 CX -> 3s 触发买入）。
- 重建工具：research/expectation/rebuild_expect_from_review.py + from-jsonl。
- 注意：601811 属连板（三连板），AXquant 复盘曾误标 first_board_arb；以快照 consecutive_board 池为准。

## 2026-10-18 增补：收盘/盘前「构建+校验」一键脚本（并入同步流程）
- 新增 `research/expectation/run_expectation_build.py`：一条命令完成
  `from-jsonl -> validate -> 报告待上传文件夹就绪`，插在
  `sync_positions / closeout_review（生成 position_expectation_<T+1>.jsonl）` 之后、
  Ptrade「定时上传」之前。
- 用法（默认日期=下一交易日，收盘跑=次日 T+1、盘前跑=当日）：
  ```text
  py -3.10 run_expectation_build.py [--date YYYY-MM-DD] [--source 预期.jsonl] [--out-dir 目录]
  ```
- 职责边界：脚本复用 `build_expectation_bridge.cmd_from_jsonl / cmd_validate`，只保证
  `data/ptrade_bridge/expectation_<T+1>.csv` 新鲜+校验通过；不代传网络，真正上送由
  Ptrade 客户端「定时上传」绑定该文件夹触发。归档 meta / `ptrade_today.csv` 在 `archive\` 不上传。
## 2026-10-18 增补：收盘一键总入口（单文件串联 同步持仓→复盘→构建校验）
- 新增 `research/expectation/run_one_click_after_close.py`（+ `.cmd` 双击入口），一次跑完：
  `sync_positions`（同步持仓）→ `closeout_review.review`（复盘→预期 CSV）→
  `run_expectation_build`（from-jsonl+validate→待上传就绪）。
- 用法（含持仓同步需已登录连接 PTrade 客户端；用 API 自带 Python3.7）：
  ```text
  双击 research\expectation\run_one_click_after_close.cmd
  # 或：
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" ^
     research\expectation\run_one_click_after_close.py --date 2026-10-16 --next-date 2026-10-19
  ```
- 常用开关：`--skip-sync`（跳过持仓同步）、`--logs <当日日志.txt>`（采 [seal]/[l2]/[may-order]）、
  `--selfwatch`（同步自选股）、`--source/--out-dir`（透传 from-jsonl）。
- 已冒烟：py310 `--skip-sync --date 2026-10-16` → 复盘 records=2、预期行=5、from-jsonl+validate 通过。
## 2026-10-18 增补：昨日开盘涨幅自动回填（消除 validate 缺列提醒）
- 问题：`cmd_review` 重建的持仓记录 `yesterday_open_pct=null`，导出后 `validate` 报
  「昨日开盘涨幅缺失/空行数=N」，云端 `_yesterday_open_chg` 只能走 1d 历史兜底。
- 口径确认（AXquant review）：`yesterday_open_pct = open(S-1)/close(S-2)-1`（S=reviews日），
  种子(buy)记录本就 verbatim 复制该值；持仓同口径应一致。
- 实现（`build_expectation_bridge.py`）：导出前 `_backfill_yopen()` 就地回填空白列——
  优先读 review jsonl（AXquant 权威 → PT 本地）verbatim；未覆盖的再以日线 open/close 兜底
  （akshare，缓存 `data/kline_cache/`，失败不阻断）。回填含 2 条路径（`cmd_from_jsonl` 与 `cmd_review`）。
- 效果：`expectation_2026-10-19.csv` 持仓 603690=-4.16 / 601811=-2.24；validate 不再提示缺列；
  预期 jsonl 也已持久化带值，后续 from-jsonl 无需重复网络。校验点=`run_one_click_after_close` 步骤3 validate 通过。