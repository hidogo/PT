# 36-弹性套利 elastic_arb 落地方案（比对 AXquant → PT 托管）

> 结论：AXquant `elastic_arb` 的核心逻辑（板块一字≥2 → 抓同板块 20cm 弹性标的，
> 1m 大阳线 + 6~10% 涨幅 + 前收×1.10 封顶）在 Ptrade 云端**可实现**，用 1m/L2 盘口近似；
> 仅 **0.2s hot_ticks 级灵敏度**与**权威全市场实时涨停名单**两处无法对齐（PT 上限 tick 3s + T-1 名单近似）。
> 预算遵循「其它=10%」（ordinary_buy_ratio），单支上限 30%。

## 1. AXquant 权威契约（btree/builder.py `_buy_elastic_arb` L6236）
### A 段·情绪前提：板块一字板统计（60s 缓存，按日重置）
- 涨停名单（首板+连板 top50）→ 实时 open/pre_close
- 一字板判定：`open >= pre*(1+limit_thr)*0.995` 且 买一封单 bidVol[0]>0，排除 ST
- 板块映射 → 每板块一字板数 `>= elastic_arb_min_yizi(2)` → 强板块 `strong={board:cnt}`
### B 段·候选筛选（全部满足才触发）
- 20cm 前缀 300/301/688/689；属于强板块（取 strong 最大者）
- 非一字板（`_is_one_word_board`）；开盘涨幅 `<= elastic_arb_max_open_change(12%)`
- 非次新（`elastic_arb_skip_new`）；最新 1m 柱 `(close-open)/open >= min_1m_surge(3%)`
- 当前涨幅 `min_change(6%) ~ max_change(10%)`
- 报价新鲜度：窗口内只认 hot_ticks（0.2s 级），quote_age<=3s
### 定价
- basis = 卖一价 ask1（成交确性好），缺省最新价
- `buy_cap = pre*(1+elastic_arb_max_buy_pct/100)` = **前收×1.10**（不是涨停价 1.20）
- `buy_price = min(basis*(1+spread_markup), buy_cap)`；spread_markup 按价位档：<10元3%/<30元2%/<100元1.5%/>=100元1%
- 钳制到 [跌停, 涨停]
### 资金/风控
- `_calc_buy_volume` 常规=总资产×ordinary_buy_ratio(10%)；仓位上限 `_at_position_cap`；每拦截步 `_diag_bump` 可审计

## 2. PT 现状与数据源映射
| AXquant 数据 | PT 云端对应 | 状态 |
| 20cm 前缀 | `_is_elastic_20cm`（已有） | 已具备 |
| 前收×1.10 封顶 | `_max_elastic_buy_price` / `_order_limit(chase)` 已封顶（已有） | 已具备 |
| 卖一价 ask1 | `get_gear_price().ask_grp[1][0]`（L2 十档，已验 L2_OK） | 可获取 |
| 板块映射 | `get_stock_blocks(sec)`+`get_industry_stocks(code)`（`_board_member_codes` 已有） | 可获取 |
| 一字板封单 | `_seal_metrics`（L2 买一金额/笔数） | 可获取 |
| 1m 大阳线 | `get_price(frequency="1m")` 末根柱 | 可近似 |
| 全市场涨停名单 | `zt_lianban_latest.csv`(T-1) + `market_scan` 分片 | **近似，覆盖有限** |
| hot_ticks 0.2s | `tick_data` 3s 事件 + get_snapshot 缓存 | **PT 上限 3s** |

## 3. 可实现性分级
- **可完整落地**：A 段板块一字统计（池/名单内）+ B 段 20cm 大阳线 6~10% 追涨 + 前收×1.10 封顶 + ask1 定价
- **近似落地**：全市场一字板统计（用「池 + zt_lianban 名单 + market_scan 命中」近似，10 分钟分片扫不全 5000+ 只，只统计当日前 20cm 活跃标的）
- **不对齐（如实标注）**：0.2s hot_ticks 灵敏度（PT tick 3s）；权威实时全市场涨停名单

## 4. 落地方案（分阶段）
### Phase 1 基础（1m + tick 帧末，先出核心）
新增 BLS 参数：
```python
'elastic_arb_enabled': True,       # 弹性套利总开关
'elastic_arb_window_minute': 10,   # 09:30+N 窗口
'elastic_arb_min_yizi': 2,         # 板块一字板>=2 情绪爆发
'elastic_arb_min_1m_surge': 3.0,   # 1m 大阳线 (close-open)/open >= 3%
'elastic_arb_min_change': 6.0,     # 当前涨幅下限 %
'elastic_arb_max_change': 10.0,    # 当前涨幅上限 %（防炸板）
'elastic_arb_max_open_change': 12.0, # 开盘涨幅上限 %（防大幅高开兑现）
'elastic_arb_max_buy_pct': 10.0,   # 买入价=前收×(1+10%)（复用 elastic_max_buy_pct）
'elastic_arb_cache_ttl': 60.0,     # 板块一字统计缓存 s
```
新增函数（策略文件内，复用现有 helper）：
- `g.elastic_cache = {'day':'','ts':0.0,'strong':{}}`：板块一字板统计缓存
- `_elastic_yizi_scan()`：遍历 池(自选+预期+watch) ∪ zt_lianban 名单，判定开盘一字
  `open_px >= pre*(1+_limit_threshold)*0.995 and _seal_metrics 买一>0` → `get_stock_blocks` 取板块 → Counter>=min_yizi
- `_elastic_1m_surge(sec)`：`get_price(1m)` 末根 `(close-open)/open*100`
- `_elastic_ask1(sec)`：`get_gear_price().ask_grp[1][0]`（缺省 last_px）
- `_try_elastic_arb_buy(context)`：窗口(09:30-N) + `_is_elastic_20cm` + 属强板块 + 非一字(`_is_one_word_open`)
  + 开盘涨幅<=12% + 1m 大阳线>=3% + 当前涨幅 6~10% + 非持仓/冷却/日买上限
  → `place_order(mode='chase', ratio=ordinary_buy_ratio 10%)`（`_order_limit` 已封顶前收×1.10）
- 挂载：`handle_data` 1m 兜底 + `tick_data` 帧末 3s 敏捷（与预期买入同模式）
- 诊断日志 `[elastic]` 逐拦截原因（对齐 `_diag_bump`）

### Phase 2 增强
- ask1 定价 + 价位档滑点（spread_markup：<10元3%/<30元2%/<100元1.5%/>1%），仍封顶前收×1.10
- 补池：强板块成员 20cm 未入池 → 并入 watch/pool_static（跨 1m 保留）
- 报价龄约束：get_snapshot 时间戳 >3s 不放行（对齐 max_quote_age_sec）

### Phase 3 不落地项
- 0.2s hot_ticks 快路径（PT 无该通道，tick 3s 为上限）
- 权威全市场实时涨停名单（用 T-1 zt_lianban + 池内近似，覆盖有限）

## 5. 验证点（selftest T41+ / 盘中日志）
- T41 一字板判定（open>=pre*1.10*0.995 且 封单>0）→ 板块 strong 计数
- T42 1m 大阳线 (c-o)/o>=3% 判定（FakeDF）
- T43 `_try_elastic_arb_buy` 全门禁：窗口/20cm/强板块/非一字/涨幅区间 → place_order(chase, 10%)
- 盘中核对：09:30-09:40 `[elastic]` 日志 + `[may-order] ... elastic_arb ...`（DO_ORDER=False 只记录）
- 双编译 py310 + PT3.7

## 6. Phase 1 已实施（v0.19，2026-10-19）
- 新增 BLS：`elastic_arb_enabled` / `elastic_arb_window_minute(10)` / `elastic_arb_min_yizi(2)` /
  `elastic_arb_min_1m_surge(3.0)` / `elastic_arb_min_change(6.0)` / `elastic_arb_max_change(10.0)` /
  `elastic_arb_max_open_change(12.0)` / `elastic_arb_cache_ttl(60.0)`（买入价封顶复用 `elastic_max_buy_pct`=前收×1.10）
- 新增函数：`_elastic_yizi_pool` / `_boards_of` / `_elastic_yizi_scan`(60s缓存按日重置) /
  `_elastic_in_strong_board` / `_elastic_1m_surge` / `_elastic_ask1` / `_try_elastic_arb_buy`
- 挂载：`handle_data` 1m 兜底 + `tick_data` 3s 帧末（09:30-09:40 窗口）
- 下单：`place_order(mode='chase')`，预算 10%（其它=10%），`_order_limit` 封顶前收×1.10
- 日志：`[elastic] yizi=N strong_boards=N` + `[may-order] ... elastic_arb ...`
- 自测：T41 一字统计 / T42 1m 大阳线+ask1 / T43 全门禁 / T44 tick 端到端（172 PASS / 0 FAIL）
- 双编译 py310 + PT3.7 通过
- 未落地（见第 3 节）：0.2s hot_ticks 灵敏度；权威全市场实时涨停名单（用 zt_lianban+池 近似）


## 7. v0.19.1 数据消费去重与缓存（2026-10-19）

目标：打板 + 弹性套利共用数据避免重复拉取，效率与稳健性优先。

- `_gear(sec)`：L2 十档盘口帧级缓存（`gear_cache_ttl=3.0s`，sec->(ts,gp)）。
  统一消费源：`_seal_metrics` / `_sealed_at_limit` / `_elastic_ask1`，同一帧不再多次 `get_gear_price`。
  缺失/异常也短缓存，防回测/接口抖动同帧反复打盘口。
- `_elastic_1m_surge(sec)`：1m 大阳线 15s 缓存（`m1_surge_cache_ttl`，sec->(ts,%)），窗口内重复判定复用。
- `_elastic_yizi_scan()`：一字板候选先批量 `_get_snapshot_many` 回填 `g.spot`（仅缺者一次列表调用），
  逐只判定直接读 `g.spot`，避免逐只串行 `get_snapshot`。
- `_board_top_gainer(sec)`：板块成员优先读 `g.spot`，缺者才回退 `get_snapshot`（首板闸门）。
- 日切/initialize：重置 `g.gear_cache` / `g.m1_surge_cache`。

修正：`_elastic_1m_surge` 缓存变量与收盘价变量同名导致的写缓存 TypeError（被吞成 0.0），已改名修复。
自测扩展：T42 缓存复用/失效重拉、T42b 盘口缓存复用、T44 yizi 批量补快照一次、T45 板块最高走 g.spot。
自测：181 PASS / 0 FAIL；双编译 py310 + PT3.7 通过。


## 8. v0.20 打板数据源升级：L2 逐笔首笔成交（联动）

- 打板首触从"快照价+封单门槛"升级为"L2 逐笔涨停价成交"（`_tx_first_zt_ms`，tick_data 3s 帧内检测，灵敏<=3s）。
- 与弹性/打板共用数据不冲突：逐笔为新增消费源（get_individual_transaction），
  近涨停(>=0.98*涨停)且未触发才拉取，帧负担可控；盘口仍走 `_gear` 帧级缓存。
- 详见 docs/30 第 6 节。
