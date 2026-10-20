# 38-聚合数据源 DataHub（v0.21）

> 日期：2026-10-19　定位：单文件内薄聚合层，提升数据消费效率与稳健性（不改变 3s 回调节拍）

## 1. 动机
- 现状：3s 帧内快照逐只 get_snapshot(sec)（约 20 次）；缓存分散在 gear_cache/m1_surge_cache/elastic_cache/bs_cache/hist 多处，
  日切在 initialize/按日切块/盘中拉起多处手动重置。
- 目标：批量化 + 统一 TTL 缓存注册表 + 失败隔离/降级标记，降帧时间、防接口抖动。

## 2. 设计（class DataHub，模块级单例 _get_ds()）
- `cached(source, sec, ttl, fetch)`：统一缓存原语。命中(ts,ttl)直接返回；未命中调 fetch() 并缓存（含安全默认值）；
  fetch 抛异常 -> 记 degraded、不缓存、返回 None（下一帧再试）。
- `snapshot(secs)`：帧首批量快照，get_snapshot(列表) 一次回填 g.spot；批量缺标再逐只兜底（正常 0 次）。
- `reset(day)`：显式清缓存；`_maybe_reset()` 按交易日惰性自重置（cached/snapshot 自动触发，无需逐处手挂）。
- 兼容性：保持现有函数签名（_gear/_elastic_1m_surge 等对外不变），DataHub 作为内部实现逐步替换。

## 3. 已接入（v0.21 Phase 1）
- tick_data：帧首 `_get_ds().snapshot(_secs)` 一次批量，替代逐只 get_snapshot（tick 帧外部调用显著下降）。
- `_gear`（L2 十档）：走 `cached('gear', sec, gear_cache_ttl=3s)`。
- `_elastic_1m_surge`（1m 大阳线）：拆分 `_calc_1m_surge` 计算 + `cached('m1_surge', sec, 15s)`。
- initialize / 日切重置：`_get_ds()` 预热 / 日切 `_get_ds().reset()`；v0.26b 起 DataHub 为模块级单例（不入 g，规避引擎 g 持久化 pickle 报错）。

## 4. 自测
- T48 快照批量一次调用 / 回填 g.spot / 批量空逐只兜底
- T49 缓存命中复用 / reset 后重拉
- T50 失败隔离 -> None + degraded
- 全量：195 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 5. Phase 2 已落地（v0.22，2026-10-19）
- **近涨停候选批量逐笔统一入口**：`DataHub.tx_zt_batch(secs, frame_data)` -> {sec: ms}
  - 先帧推送 data[sec]['transaction']（0 调用）；缺者按 3s 帧 token 批量 `get_individual_transaction(列表)` 一次并缓存原始 rows，
    同帧多消费不重复拉；up_px 消费时从 g.spot 取，避免缓存污染。
  - 单一解析点 `_parse_tx_zt_ms(sec, rows, fields)`（批量/单标共用）；`_tx_first_zt_ms` 改为兼容入口。
  - tick_data：帧首算近涨停候选（last>=up*near_px、非一字、first_zt 未触发），一次批量得 _tx_map，per-sec 直接读。
- **板块强度并入注册表**：`_board_member_changes` 走 `cached('bs', sec, 60s)`，成员快照改 `_get_snapshot_many` 批量一次
  （替代逐只最多 20 次 get_snapshot）；`_board_strength`/`_red_ratio` 口径不变。
- **1d 打分 K 线并入注册表**：`_hist_1d` 走 `cached('hist1d', sec, 60s)`；`_ensure_ma5`/`_auction_beat_history`/`_ma5_first_5d` 不变。
- 自测：T51 批量一次/帧推送优先/同帧去重；T52 板块批量快照/缓存复用/强度口径；T53 hist1d 缓存。
- 全量：204 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 6. 后续可选（Phase 3，未做）
- 帧级拉取预算计数 + 超预算降级日志。
- 不改变硬约束：3s 节拍、无亚秒、L2 权限依赖（见 docs/37）。


## 7. v0.23 板块强度排名：打首板/弹性目标 = 强度前三板块（2026-10-19）

- **刷新频率**：板块强度（成员涨跌均值%）与排名均按 `board_rank_cache_ttl=60s` 惰性刷新——
  被查询才刷新（3s tick 帧内触发），非定时推送；板块成员快照每 60s 批量一次（get_snapshot(列表)）。
- 新函数：
  - `_board_code_of(sec)`：所属板块代码（get_stock_blocks 首层首个非空行）。
  - `_fetch_board_chgs(board_code)` / `_board_strength_by_code(board_code)`：板块成员批量快照 -> 强度%（60s 缓存 'board_chgs'）。
  - `_board_rank_top3_set(secs)` / `_compute_board_rank(boards)`：候选板块集合强度排序取前三（按候选板块集合 token 缓存 60s）。
  - `_board_rank_top3(sec, secs)`：sec 板块是否前三。
  - `_near_limit_cands(secs)`：近涨停候选（供首板 1m 兜底路径的排名候选）。
- 门控接入：
  - 首板 `_try_first_board_buy(context, sec, rank_secs=None)`：新增板块强度前三门（tick 路径传帧内近涨停候选，1m 兜底用池内近涨停候选）。
  - 弹性套利 `_try_elastic_arb_buy`：新增板块强度前三门（候选=池内 20cm 标的），与 yizi 强板块门叠加（BLS 可关）。
- 新参数：board_rank_enabled(true) / board_rank_top_n(3) / board_rank_cache_ttl(60.0)。
- 自测：T54 排名前三/缓存不重复拉；T55 首板非前三拦截/前三放行；既有首板/弹性门禁用例补 _board_rank_top3 桩。
- 全量：211 PASS / 0 FAIL；双编译 py310 + PT37 通过。


## 8. v0.24 板块刷新提速 + 生命周期窗口（2026-10-19）

- **板块强度/排名刷新周期时间分档**：`_board_refresh_ttl()` —— 开盘 30 分钟内（<10:00）用 `board_rank_ttl_fast=3.0s`
  与 tick 同频；10:00 后用 `board_rank_cache_ttl=60.0s`。板块归属 `_board_code_of` 改 3600s 缓存（日内不变，避免每帧 get_stock_blocks）。
- **生命周期窗口（买入场景统一落地）**：
  - 首板打板：开盘 10 分钟内 = 09:30-09:40 前（first_board_minute=10，原已生效）。
  - 5日低吸 ma_pullback：`ma5_buy_window_min=60` = 10:30 前（新增窗口；原 13:30 已按用户修正）。
  - 核心票 core_buy：`core_buy_window_min=30` = 10:00 前（新增窗口，其它类）。
  - 预期买入 expected：`exp_buy_window_min=30` = 10:00 前（新增窗口，其它类）。
  - 弹性套利 elastic_arb：窗口由 10 分钟改为 30 分钟 = 09:30-10:00 前（其它类）。
- 自测：T56 各窗口边界拦截/放行（低吸 10:31 拦 / 10:00 放）；T57 刷新周期 09:33=3s / 10:01=60s；既有 T26d/e、T36 补固定 now_dt 防真实时钟干扰。
- 全量：219 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 9. v0.25 帧级拉取预算（Phase 3，2026-10-19）

- **动机**：tick_data 每 3s 一帧，09:30-10:00 消费最重——get_gear_price 逐目标（~15-20）、板块强度
  每帧每板块 get_industry_stocks+get_snapshot（候选板块多时 20-60 次）、get_stock_blocks 逐候选逐帧
  （弹性路径无缓存）、get_price(1m) 逐候选（two_1m 无缓存）。最坏 ~150-300 次/帧，有丢帧/限流风险。
- **帧账本（DataHub）**：`self.frame={'token','used','over'}`，token=int(time.time()/3)，切帧自动清零；
  `spend(source)` 查 `BLS['frame_<source>_limit']`，超限记 `over` 返回 False；`frame_report()` 输出
  `[budget] snapshot=1/2 tx=1/1 gear=12/15 board=4/6 ... over:board=2`。
- **降级语义（cached 增 budget/stale_ok）**：
  - P0（tx/snapshot/gear）：超限返回空、**不用旧值**、下帧重试（保首触 ≤3s 灵敏度）。
  - P1（board/blocks/bcode）：超限回退上一帧缓存值（stale_ok=True），首板/弹性门控不整体丢。
  - P2（m1/hist1d）：超限返回 None（two_1m 判 False、surge 判 0，路径本身保守）。
- **已挂预算点**：snapshot（2 批次+兜底 cap 5）、tx（1）、gear（15）、m1（20，two_1m 3s 缓存共用）、
  hist1d（10）、board（6 组）、blocks（10，300s 缓存）、bcode（20，3600s 缓存）。
- **参数（BLS，盘中可调）**：budget_log_enabled、frame_snapshot_limit/fallback_cap、frame_tx_limit、
  frame_gear_limit、frame_m1_limit、frame_hist1d_limit、frame_board_limit、frame_blocks_limit、frame_bcode_limit。
- **自测**：T58 14 项（账本/切帧重置/超限不缓存/下帧重试/stale 回退/无旧值 None/two_1m 缓存去重/report 格式）。
  全量 233 PASS / 0 FAIL；双编译 py310 + PT37 通过。

