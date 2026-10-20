# 33-对齐 AXquant 买卖逻辑（v0.15）

> 版本：buysell_core v0.15　目标：把 PT 托管策略的单键买卖逻辑对齐 AXquant 已实盘验证的真实口径，收敛三处关键差异：**一字板封单超预期不参考排单 / 竞价核卖 P2E / 弹性买入价 10% 上限**。上游 AXquant 依据：`axquant/runner/bt_handlers.py`（P1-3 sealed、弹性 cap）、`axquant/strategy/btree/builder.py`（AUCTION 卖出链、_is_sealed_at_limit）、`axquant/strategy/decision/sell.py`（止损分档）。

## 1. 一字板·封单超预期不参考排单
- AXquant P1-3：除 auction/add_position/elastic_arb 外，`_is_sealed_at_limit` 命中即 `limit_up_sealed_no_queue` 拦单——挂涨停价只是排队，不参考/不参与排单成交。
- PT 对齐：新增 `_sealed_at_limit(sec)` = 现价>=涨停价*0.998 且 L2 十档卖盘空（封死）。无 L2 盘口(回测)判非封死，与 AXquant `has_book` 一致。
- 拦截点统一在 `_block_sealed_buy`（place_expected_order 兜底 + _order_limit mode=board 双保险）：返回 False、不置 fired、可再评估；同标的每日仅告警一次 `[seal] sealed at limit`。
- v0.26c：`try_core_buy` 增 `_is_one_word_open` 闸门（开盘即涨停的一字板不追，对齐 first_board/elastic 排除）；`auction_pre_confirm(09:25)`/`after_open_probe(09:31)` 增 `_mark_one_word_open()` 一字板识别（开=涨停价且无卖盘 -> `g.one_word_open`，`_sealed_at_limit` 免 5s 持续门槛立即封死）。

## 2. 竞价核卖 P2E
- AXquant AUCTION 卖出链：P0 强清 > P1 核卖 > P2 熔断 > BUFF > **P2E 预期不及卖** > P3 止损。
- PT sell_manager 原缺 P2E。v0.15 在 P1 之后、P3 之前插入：持仓预期 `expected_status in {confirmed_miss, degraded}` 即清仓（`exp_sell_on_pending_miss` 可放宽到 pending_miss，默认 False）。对齐优先级 P1 > P2E > P3。
- 提醒：pending_meet/pending_exceed 不是 miss，不会误卖；P2E 在 handle_data(1m) 与 mid_probe 都跑，竞价格局后首根 bar 即核卖。

## 3. 弹性买入价 10% 上限
- AXquant `_elastic_20cm_max_buy_price` = 前收 x (1+max_buy_pct=10%)，仅 300/301/688/689；非打板场景委托价超过即拦（打板 board_buy/first_board_buy 豁免）。
- PT `_order_limit` chase(追高) 路径封顶到前收*(1+10%)，board(打板) 豁免——即弹性的"触发价不能超前收 10 个百分点"。

## 4. 差异与边界
| 项 | AXquant | PT v0.15 |
| --- | --- | --- |
| 封死涨停 | 非 auction 全拦 queue | board 买路径拦截（同） |
| P2E miss 卖 | allowed={confirmed_miss,degraded}(+pending_miss 可选) | 同，BLS.exp_sell_on_pending_miss 控制 |
| 弹性上限 | 非 exempt 全场景拦 | _order_limit chase 收敛价格（同效果，较不激进） |
- 待实盘验证：L2 `get_gear_price` 的 ask_grp 在真实一字封死时的形态（空 dict vs 缺键），决定 _sealed_at_limit 判定是否需再校准。

## 5. 自测与编译
- `research/expectation/selftest_exp_rt.py` 30/30 通过（新增 T12/T12b 封死与未封死、T13 弹性上限+打板豁免、T14/T14b P2E 核卖与 pending_miss 默认不卖）。
- PT3.7 与 py310 均 `py_compile` 通过；待重传 `strategies/buysell_core/strategy.py`。
- 明日盘中核对点：`[seal] sealed at limit`、`P2E_exp_miss expected_status`、300/688 追高限价不超前收*1.10。
## 9. 节奏验证：9:20 上传 → 9:25 竞价终态 → 9:30+ 分时确认
> 目标时间线：9:20 定时上传预期前瞻文件；云端 9:25 竞价终态「初步确认竞价超预期->观察」；9:30 后分时超预期确认才执行买入。

### 9.1 原代码断点（验证结论）
- `before_trading_start` 约 9:10 前触发（docs/03），且 `_load_expectation()` 只在其内调用 → 9:20 上传文件不会被读，`g.exp_file` 全天为空。
- 策略仅有 run_daily 09:31 / 11:00，缺 9:25 竞价终态钩子 → 「初步确认->观察」步骤缺失。

### 9.2 v0.16 修复（09:25 钩子）
- 新增 `run_daily(context, auction_pre_confirm, time='09:25')`（initialize；定时任务现 3 个 < 5 上限）。
- `auction_pre_confirm`：幂等重读 `_load_expectation()`+selfwatch+pool_static（命中 9:20 上传）；对 side=buy 候选刷竞价与 `_exp_rt_status`，竞价超预期初步确认时打 `[exp] <code> 09:25竞价终态初步确认超预期 -> 观察(等分时确认)`，只观察不买、不置 fired。
- `after_open_probe(09:31)` 加幂等重读兜底（应对稍晚到上传）。
- 9:30+ 分时确认沿用 `_exp_rt_status` 超预期分支（两分钟上攻/一分钟冲涨停且不破 VWAP -> CX 买单，tick 3s 触发）；`_auction_change` 用 get_trend_data，9:25 竞价终态缓存正确。

### 9.3 验证
- 自测 selftest_exp_rt.py 34/34（新增 T15：09:25 重读 + observe_seen + 观察日志 + 不买）；PT3.7 与 py310 py_compile 通过。
- 待重传 strategy.py；明日盘中核对日志序：09:25 `auction_pre_confirm done exp_file=N` + `[exp] ...观察` → 09:30+ 才出现 `[exp-order] ... exp_rt CX`。

## 10. 逻辑链路兜底
- **链路**：9:20 上传 → 9:25 竞价终态初判（超预期=观察 / 未超预期=放弃 CS / 数据缺失=等待）→ 9:30+ 分时确认超预期=买入，破VWAP=放弃。
- **已有兜底**：文件缺失/坏格式不崩；预期文件空走 watch 打分+ma5；9:25+09:31 双重重读+盘中重启重读；get_trend_data→open 回退；下单失败不置 fired 下帧重试；exp_fired+每日计数持久化。
- **v0.16 补**：竞价初判未超预期(acon!=CX) → CS `auction_not_met`，不再放任盘中两分钟上攻买入；真竞价缺失(actual~-100, `< -90`)不误弃、保持等待；09:25 日志区分观察/放弃。
- **设计取舍（未改）**：分时确认需进攻形态（两分钟上攻/一分钟冲涨停），无形态则持续观察靠破VWAP放弃；下单成功后置 fired，委托被拒/未成交当日不再回购。

## 11. 预期三态供方数据稳健性（v0.17）
- 供给：`yesterday_open_pct`(T-1开盘) 与 `expected_auction_change_pct`(T日/复盘日开盘基准) 为「有条件提供」；AXquant 复盘缺字段时桥接 CSV 缺列。
- 云端自取（get_price 1d 历史折算，非仅靠文件）：`_yesterday_open_chg`(open[-3]/close[-4]-1)、`_auction_benchmark`(open[-2]/close[-3]-1)。
- 消费端健壮：A 负基也判高开；B 基准缺失/<=0 不超预期不过触发、不误弃；C 供方缺失输出空串 + has_* 区分 + validate 提醒。
- 前瞻文件仍应提供当日开盘涨幅基准(expected_auction_change_pct)；云端1d 仅为兜底。

## 2026-10-18 增补：昨日开盘涨幅口径修正 + 角色容忍度迁移
### 1. yesterday_open_pct 口径修正（消除 2 天滞后）
- 问题：原记录/CSV 的 `yesterday_open_pct` 取 AXquant review 的 `yesterday_open_pct`（=open(S-1)/close(S-2)，review 日昨天），但云端 `_eval_auction` 在 T+1 比较 `chg > yesterday_open_pct` 时“昨日”应是 review 日 S，存在 2 天滞后。
- 修正：`yesterday_open_pct`(T+1) 统一 = `open(S)/close(S-1)-1`（review 日自身开盘涨幅）。
  - 本地源：review 记录 `auction_change_pct`（=S 自身开盘涨幅，优先 AXquant→PT），缺失再日线 open/close 兜底（akshare+缓存）。
  - 云端 `_yesterday_open_chg` 兜底：`opens[-1]/closes[-2]-1`（原 `opens[-3]/closes[-4]`）。`_hist_1d` 用 get_price frequency=1d（include=False，末根=review 日 S）。
  - 反算核验：603690 → 6.98%（原 -4.16）、601811 → 2.03%（原 -2.24）；种子 600825=10.01 / 000530=-4.18 / 600668=2.0。
  - 持久化：`cmd_from_jsonl` 本地源同步写回，保证 jsonl 与导出、validate 一致。
- 范围：仅改 `yesterday_open_pct` 列；`expected_auction_change_pct`（超预期基准）保持原样（配套 `_auction_benchmark` 补丁未动，T19 回归不变）。

### 2. 角色容忍度迁移（AXquant sell_policy_hint → 云端）
- 现状核查：云端此前未消费 `sell_policy_hint`/role，卖出仅 P1绿开>P3止损>P5/P6评分（按板块止损、三态、评分），无地位角色差异。
- 迁移：
  - CSV 新增 `sell_policy_hint` 列（`build_expectation_bridge` 导出 + `expectation_store.export_expectation_csv` + 云端 `_load_expectation` 解析；旧 CSV 无列则按 none）。
  - 云端 `BLS['sell_policy']` 容忍度表：`hold_higher_tolerance`(龙头/唯一高标连板) 放最宽、`fast_exit_on_weak`(首板套利/跟风) 收紧、`watch_break_sell`/`break_weak_escape`/`vwap_follow` 居中。
  - `_role_tolerance(sec)` 按 hint 返回 `{green_tol, stop_adj, score_clear_adj, score_half_adj}`，应用于 `sell_manager` 的 P1 绿开阈值、P3 止损、P5/P6 评分阈值；缺省 none=基础（行为不变）。
  - 说明：本次数据中持仓=fast_exit、种子=hold_higher_tolerance。阈值改动仅在 `DO_ORDER=True` 真实下单时生效，回测/dry-run 行为可对照 docs/24 验收。
- 自测：selftest_exp_rt T18 改为 `opens[-1]/closes[-2]`（-4.08% 负基也判高开），全量 46/46 通过；strategy 在 py310 与 PT3.7 均 `py_compile` 通过。
## 2026-10-18 增补：expected_auction_change_pct / _auction_benchmark 一致性核对（已修复并存档）
- 核对结论：`expected_auction_change_pct` 供方值 = review 日 S 自身开盘涨幅（`review.auction_change_pct`，exceed 行另保底 3.0）。
  但云端 `_auction_benchmark` 兜底原用 `opens[-2]/closes[-3]`（=open(S-1)/close(S-2)，2 天滞后），与供方值及
  修正后的 `yesterday_open_pct`（open(S)/close(S-1)）不一致——同一类 off-by-one。
- 修复：`_auction_benchmark` 兜底改为 `opens[-1]/closes[-2]-1`（S 自身开盘涨幅），与 `_yesterday_open_chg` 同口径；
  现 supply 值、yesterday、benchmark 三处一致，无 2 天滞后。
- 边界：`_auction_benchmark` 返回 `(v, v>0)`；S 自身开盘涨幅<=0 时 has=False -> PM（不超触发，保守），
  与 exceed 行"供方保底 3.0"互补——供方缺失时不凭空给 3.0 阈值、只做缺基不误判。
- 范围：仅 `_auction_benchmark` 兜底 + `_auction_beat_history`（20日均开盘涨幅）未动。
- 回归：selftest T19 改为 `open[-1]/close[-2]`（10.526%），全量 54/54、0 FAIL；strategy 在 py310 与 PT3.7 均 `py_compile` 通过。

## 2026-10-19 增补：卖出仓位百分比梳理与漏洞修复（sell_manager）
> 背景：用户批注澄清 `exp_order_pct`=「单笔买入占当前现金比例（单笔步长）」，`single_stock_cap`=「单只股票总仓上限=总资金×30%」——单笔≠单票总上限，勿混淆。
> 本增补只梳理**卖出**仓位百分比与硬编码漏洞修复。

### 1. 卖出百分比一览（对齐 AXquant 卖出链）
| 触发 | 卖出仓位 | 说明 |
| --- | --- | --- |
| P1 绿开（低开清仓） | 可卖×100% | `enable_amount` 全清 |
| P2E 竞价核卖（miss/degraded） | 可卖×100% | 与 AXquant 核卖一致 |
| P3 止损 | 可卖×100% | 分板块/角色止损阈值 |
| P4 预期三态 miss / exp_sell | 可卖×100% | 清仓离场 |
| P5 评分清仓（sc<score_sell_clear×adj） | 可卖×100% | `score_sell_clear=30` |
| P6 评分半仓（score_sell_clear≤sc<score_sell_half×adj） | 可卖×`sell_half_ratio`(0.5)，整手取整 | `score_sell_half=50` |

- 可卖口径统一走 `_sellable(sec, positions)`：优先 `enable_amount`（A股 T+1，T 日买入不可卖），缺失回退 `amount`；≤0 视为当日不可卖直接跳过。**修复原误用 `amount` 总持仓导致的 T+1 超卖**。

### 2. 修复的漏洞
1. **超卖**：原 7 处卖单用持仓 `amount` 而非可卖 `enable_amount` → 改经 `_sellable()`。
2. **零股半仓**：原 `max(amt//2,1)` 在 amt 非整手/奇数时产生 50 股零股，且硬编码 1/2 → 改 `sell_half_ratio`（默认 0.5）+ 整手取整（`int(half//100)*100`），不足一手按 `amt<100?amt:100`，并 `cap` 到 `amt`。
3. **卖出去重**：原同帧/连续帧重复触发可叠单超卖 → `_do_sell` 统一入口记录 `g.sold_log[sec]=time.time()`，`sell_manager` 顶部按 `sell_cold_secs`(30s) 冷却跳过重复挂单。`sold_log` 已纳入持久化（跨重启恢复）。

### 3. 参数（BLS，可动态调整避免硬编码）
- `sell_half_ratio=0.5`：P6 半仓卖出比例。
- `sell_cold_secs=30.0`：同一标的后冷却窗口（防未成交叠单）。
- 生效边界：以上改动在 `DO_ORDER=True` 真实下单时生效；dry-run（DO_ORDER=False）仅打 `[may-order]` 日志可对照 docs/24 验收。

### 4. 未修风险（留存核对）
- 卖出限价为现价：下跌/封死场景可能在现价不成交而留滞持仓；重复卖出依赖冷却窗口而非订单回报（`on_order_response`/`on_trade_response` 未用于持仓对账），成交回报驱动的对账可作为下一步。

### 5. 自测
- selftest_exp_rt 新增 T23：`_sellable` 优先 enable_amount（300/500）、缺位回退 amount、dict 形式、enable_amount=0 当日不可卖；P6 半仓整手 qty=100、只余一手卖 100、P5 清仓按 enable_amount=200 而非 amount=500。全量 69/69、0 FAIL；strategy 在 py310 与 PT3.7 均 `py_compile` 通过。

## 2026-10-19 增补：卖出稳健优化（核卖地板价 + 订单/成交回报驱动对账）
> 背景：承接上一条「卖出仓位百分比梳理」未修风险——①卖出限价为现价，下跌/封死场景可能不成交留滞持仓；②去重依赖冷却窗口而非订单回报。
> 本增补参照 AXquant（order_tracker.py 的 `has_pending_sell` + order_lost 重投 / sell.py 核卖 `limit_down_price`）稳健收敛。

### 1. 核卖限价用跌停地板价（保证下跌中成交）
- 新增 `_limit_down_price(sec)` = 前收 x (1 - 板块跌停幅)；主板 10%、创业板/科创板 20%、北交所 30%（BLS 参数 `limit_down_main/chinext/bse`，自动识别 300/301/688/689/8/4/92 前缀）。
- `_do_sell(..., urgent=True)` 对 **P1 绿开 / P2E 竞价核卖 / P3 止损** 传 `mode='sell_urgent'`；`_order_limit` 其为跌停地板价（卖到地板价必能成交，交易所按≥地板的最高买价成交），替代原「现价限价」。非核卖 P4/P5/P6 保持现价限价（涨停一字板卖出挂现价即按涨停价成交）。
- 开关：`BLS.sell_urgent_floor`（默认 1）。dry-run 的 `[may-order] limit=` 即显示拟成交地板价，可对照 docs/24 验收。

### 2. 订单/成交回报驱动的去重对账（替代纯时间冷却）
- `place_order` 写 `g.pending[sec] = {no, side, qty, limit, status:'SENT', filled:0, ts}`。
- `_sell_inflight(sec)`：有未终态卖出挂单在途（status∉{FILLED,CANCELLED,REJECTED}）则本次跳过，防同一标的重叠下单；`on_order_response`（拒绝/撤单）与 `on_trade_response`（全成/部分成交）回填 status/filled，成交后 `g.pending` 终态即放行下一判。
- `on_trade_response` 对卖单成交记 `daily.sold` 并刷新 `g.sold_log`（成交驱动去重叠加 min-冷却防高频重复减仓）。
- **防锁死**：`_sell_inflight` 带 `sell_pending_timeout`（默认 120s）——挂单超时无回报视为丢失放行重试（对齐 AXquant order_lost 重投），避免 P5/P6 挂单长期不成交把该股永久锁死。

### 3. 生效边界与自测
- 以上仅在 `DO_ORDER=True` 真实下单时触达（pending/回报对账）；dry-run 走 `[may-order]` 日志仍可看到核卖地板价。
- selftest 新增 T24：主板/创业板跌停地板（9.0/8.0）、普通卖出=现价、核卖=地板、在途 SENT 拦截 / FILLED·buy 放行、成交回报全成 FILLED·部分 PARTIAL·记 daily.sold、订单回报拒绝放行、挂单超时放行。全量 **81/81、0 FAIL**；strategy 在 py310 与 PT3.7 均 `py_compile` 通过。
- 待重传 `strategies/buysell_core/strategy.py`；明日盘中核对日志：P1/P2E/P3 卖出 `limit=地板价`、`on_trade_response` 后下帧不再叠加清仓、超时无回报可重试。

## 2026-10-19 盘后增补：卖出链静默空转根因（持仓键未标准化）修复
> 现象：10-19 早盘日志（DO_ORDER=False）持仓=['601811.XSHG','603690.XSHG']，601811 分数 09:49 起跌破 50（38），但全上午一条 `[may-order] sell` 都没有；无任何 ERROR。

### 1. 定位
- `sell_manager` 直接遍历 `context.portfolio.positions` 的**原始键**，而 `last_px/pre_close/g.exp/g.exp_file/get_positions()` 用的都是**规范 `.XSHG` 键**（`g.spot` 由 `refresh_spot(get_positions())` 填充）。
- 一旦实盘 `portfolio.positions` 键后缀异于规范键（如 `.SS`），`last_px(原始键)` 查 `g.spot` 落空 → `px=None` → 该持仓 `continue`。由于 `px=None`/`amt=0` 都是静默分支、无日志，整条卖出链空转却"看起来正常"。
- 说明：这是**卖出侧独有**（买入/持仓探测用 get_positions 规范键），恰好对应"分数已触发却不下卖单"。

### 2. 修复（本轮）
- `sell_manager` 顶部把持仓键统一 `_norm_sec(_raw)` 标准化后用于 spot/score/去重/exp 查找；位置对象本体（`_sellable`/`my_cost` 取数量与成本）仍按原始键 `_raw` 查，保证读写一致。
- 新增 `_audit_sell_skip(sec, why)`：`no_px`/`amt0` 静默跳过时 60s 节流打印 `[sell-skip]`，附带 `spot_keys_hint`，下一盘直接可见是哪条导致不下单（不再盲查）。
- 影响：若实盘键本就是规范键则行为不变；若不同则**修复卖出空转**（非 dry-run 时按卖线真实减仓/清仓）。

### 3. 自测
- selftest 新增 T25：持仓键 `601811.SS`、spot 键 `601811.XSHG`，score=40 → P6 半仓仍触发卖 100 整手；修复前该场景 `px=None` 静默跳过。全量 **82/82、0 FAIL**；py310 与 PT3.7 均 `py_compile` 通过。
- 待重传 strategy.py；明日盘中确认非 dry-run 下的卖出行为，或先在 dry-run 看 `[sell-skip]` 是否仍出现（若仍 `no_px` 说明实盘 spot 键也需对齐）。

## 2026-10-19 盘后增补：定时上传落 upload_file/ 目录（搜索路径纳入）
> 用户反馈：客户端「定时上传」任务在云端自建了 `upload_file/` 子目录，即本地 `data/ptrade_bridge/` 的文件实际落到云端 `/home/fly/notebook/upload_file/`，而不是研究根 `/home/fly/notebook/`。此前策略只查根和 `data/` 两个候选，导致 10-19 全天 `expectation` not found（本地已生成、云端落点在 upload_file/ 未被读到）。
- 修复：新增 `_research_roots()` = [研究根, `upload_file/`, `data/`, `data/upload_file/`]，`_expectation_paths()` 与 `_selfwatch_paths()` 都以这四层为前缀（根优先，upload_file 次之）。
- 作用：无论定时上传落在根或 `upload_file/`，预期文件与自选股都能命中；不再依赖单一目录假设。
- 自测：selftest T26（预期文件与 selfwatch 候选均含 `upload_file/` 且根优先），全量 85/85、0 FAIL；py310 与 PT3.7 均 `py_compile` 通过。
- 待重传 strategy.py；明日盘前核对日志「expectation file loaded .../upload_file/expectation_<当日>.csv -> N>0」。

## 2026-10-19 盘中续：sell-skip amt0 真根因 + 持仓来源/字段多候选修复
> 现象：重传后 `[sell-skip] 601811.XSHG amt0(lookup key=601811.SS)` —— 代码后缀问题已修(py 找到 spot)，但 `_sellable` 仍返回 0。
### 定位（docs/06 权威字段）
- 实盘 `context.portfolio.positions` 键为原始 `.SS`，其 Position 对象/字典未按我们字段名暴露 `amount/enable_amount/cost_basis`。
- docs/06 明确：`get_positions()` 返回**规范键 + `amount/enable_amount/cost_basis`**（日志 `list(get_positions())`=`.XSHG`，全策略本就以它建 spot）；原始柜台为 `current_amount/enable_amount/cost_price/hold_amount/...`，且**不同柜台字段名与类型不同**（文档留了口子）。
### 修复（本轮）
- 新增 `_sellable_source()`：卖出量/成本**优先 `get_positions()`**（规范键+文档字段），空则兜底 `context.portfolio.positions`。
- `_sellable` 多字段探测（可卖类→持仓量类）：`enable_amount/available_amount/sellable_amount/closeable_amount/real_enable_amount/current_amount/amount/hold_amount/holding_amount`；**有可卖字段即采用(含 0=当日不可卖)，不回落总量**，避免 T+1 误卖。
- `my_cost` 多字段：`cost_basis/cost_price/hold_cost_price/av_cost_price/avg_cost/cost`，容忍 str/int/float。
### 自测
- selftest T27：柜台式 `current_amount+enable_amount→取 enable_amount`；无 enable→回退 current_amount；`enable_amount=0` 不回退总量；`cost_price` 解析；`get_positions()` 作来源时 P6 触发卖 100。全量 **90/90、0 FAIL**；py310 与 PT3.7 均 `py_compile` 通过。
- 待重传 strategy.py；明日核对 `[sell-skip] amt0` 是否消失、卖出与扣减是否按真实可卖数。

## 2026-10-19 盘中：一字板 / 首次涨停 灵敏度分析（+可卖字段探测诊断）
### 数据源现状（据 11:09-11:29 日志）
- `[firstzt]` 逐只上报：`{price, vol(量), ms(毫秒), seal(封单额), bids(买一笔数), state=first}`，如 600178/600267/600148/600329/600860/601778/603197/603330/603693…
- 封单/笔数来自 L2 `get_gear_price().bid_grp[1]`（封单金额/委托笔数），工作正常；异常时打 `SEAL_LOW`（封单/首封比值 < 阈值），如 600329 ratio=0.33、此前 600686 ratio=0.14→随后 `BREAK`。
### 灵敏度结论
1. **首笔成交感知非「真·首笔」**：`vol` 是全天**累计成交量**（600178 vol=14.9M），不是该笔 business_amount。`state=first` =「本实例首次见到该股触及涨停」，非市场中真正首笔；真正首板/一字首偷需消费逐笔 business_amount/毫秒级增量判定，否则延迟=轮询间隔(≈3s)，非亚秒级。
2. **重启清 first_zt → 虚报 first**：600178 在 10:35 已报过 first，11:13 重启后又报 first（vol 换成当日累计）。即已封住的旧涨停在每次重启后被当“新首板”上报，丢失“真首板”语义。需跨重启持久化首次状态，或只对盘中新破板判 first。
3. **一字板≠首板**：真一字板（开盘即封、全天无成交）不会有 firstzt（无首笔成交），须靠「现价=涨停+卖盘空」判封死 + L2 封单额判断，`[l2] gear_bid_cnt` 探针只证 bid 侧可用；`ask_grp` 空档形态/`seal_base` 跨日基准仍未在今日触发（今日无 one_word 预期候选）→ 一字超预期→买入路径待构造数据跑通。
4. **SEAL_LOW/BREAK 灵敏度可用**：可作为「触及涨停未封住→破板」的兑现/离场信号（600329/600686）。
### 可卖字段探测（续 sell-skip）
- 日志确认 `get_positions()` 源仍是 `[sell-skip] lookup key=601811.XSHG amt0`：规范化已生效，但实盘 Position 在候选字段名下仍取不到数量。
- **本轮加 `[pos-fields]` 一次性(1h节流)探测**：`_sellable` 返回 0 时打印该持仓对象真实字段/attrs，用于下一盘直接定位真实可卖字段名，不再盲猜（docs/06 提示不同柜台字段名各异）。
- selftest 新增 T28（未知字段对象→amt0 且输出 [pos-fields]），全量 92/92、0 FAIL；py310 与 PT3.7 均 py_compile 通过。


## 2026-10-19 晚间：T-1 涨停/连板名单链路（本地导出 → 上传 → 云端读 → 连板对齐）

### 背景与取径
云端逐只批量行情调用获取 T-1 涨停/连板名单成本高（受研究目录容量 / 上传次数 / 50M 限制约束）。改为：本地 AXquant 已产出的涨停池快照（`docs/review/limit_up_boards_<date>.json`，含连板数 `continue_day_cnt`）→ 走现有 expectation 上传链路传到研究目录 → 云端直接读。省掉云端逐只批量行情调用，也绕开上传次数/容量的担忧。

### 本地导出（新增 `research/expectation/export_lianban.py`）
- 数据契约列（表头）：`date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason`
- 代码后缀映射：AXquant `.SH→.XSHG / .SZ→.XSHE / .BJ→.XBJ`（与 expectation 同名同映射）。
- 字段来源：AXquant `payload.pool.item[]` = `thscode/ticker/name/continue_day_cnt(连板数)/limit_up_time/seal_money/price_change_ratio_pct/is_st/limit_up_reason`；同报文另含 `ladder/break_pool/summary`。
- 输出到待上传文件夹 `PTRADE_BRIDGE_DIR`（`data\ptrade_bridge\`）：
  - `zt_lianban_<date>.csv`（date=涨停数据日；收盘后跑即 T-1）；
  - `zt_lianban_latest.csv` 稳定指针 = 最近一份数据，云端直接读，避免云端额外算交易日历；
  - 按 `keep_days`(默认3) 清理旧 `zt_lianban_<date>.csv`。
- 用法：`python export_lianban.py [--date 2026-10-16] [--lub <axquant json 目录>] [--out-dir <上传文件夹>]`；未找到涨停 json 时返回空（不中断收盘链）。

### 一键收盘接入
`research/expectation/run_one_click_after_close.py` 步骤4（`rb.run_build` 之后）调用 `export_lianban.run(a.date)`，随收盘复盘一并生成名单。

### 云端读 + 连板对齐（`strategies/buysell_core/strategy.py`）
- `initialize` 初始化 `g.zt_lianban = {}`。
- `_zt_lianban_paths()` 复用 `_research_roots()` 四层（研究根 / `upload_file/` / `data/` / `data/upload_file/`），优先 `zt_lianban_latest.csv`，其次 `zt_lianban_<当日>.csv`。
- `_load_zt_lianban()` 解析为 `g.zt_lianban[code] = {date, board_cnt, limit_up_time, seal_money, chg_pct, is_st}`。
- `_limit_threshold(sec)`：主板10% / 创业板·科创板20% / 北交所30%（0.098 / 0.198 / 0.298）。
- `_today_zt(sec)`：`last_px/pre_close - 1 >= 阈值` 视为今日续板。
- `_limitup_days(sec)` 对齐口径：有权威 T-1 `board_cnt` → `max(0, board_cnt + (今日续板 ? 1 : 0))`；无权威记录 → 回退原 1d 历史近似。
- 加载点：`before_trading_start`、`auction_pre_confirm`(09:25)、`after_open_probe`(09:31) 均在 `_load_expectation` 后加 `_load_zt_lianban()`。

### selftest T29（`research/expectation/selftest_exp_rt.py`）
- 断言：`_load_zt_lianban()==2`；`600825.XSHG.board_cnt==11`；`_limitup_days` 权威 11（今日不续板）与「11 + 今日续板 = 12」。
- 双 `py_compile`（py310 + PT3.7）与 selftest 全量均通过、0 FAIL。

### 部署与盘中核对
1. 收盘（本地）跑 `run_one_click_after_close.py`（含 `export_lianban`，生成 `zt_lianban_latest.csv`）。
2. 确认 `data\ptrade_bridge\zt_lianban_latest.csv` 已上传云（定时上传按文件夹，落在云端 `upload_file/` 等路径）。
3. 重传 `strategy.py`。
4. 盘中日志应见 `[zt-lianban] loaded <...>/upload_file/zt_lianban_latest.csv -> N`；`[pool]` 的连板与 tags（LB/CORE）改用权威连板。

## 2026-10-19 修复：ma5窗口 / 跨重启持久化 / 持仓审计 / firstzt 门槛（1-4 一起收紧）
### 1. ma5 计算修正（L147 / `_ensure_ma5` L197）
- 原 `df['close'].iloc[:-1].mean()`（约 119 日均）→ 改 `df['close'].iloc[-6:-1].mean()` = 最近 5 个已完成交易日收盘（剔除今天）。
- 影响：修复 `try_ma5_buy` 的 `px<=ma5*1.02` 回撤买点在连板股上永不触发/虚触发的问题，以及打分强度失真。
### 2. 跨重启持久化（`load_state` L1646 / `_save_state` L1666）
- `_save_state` 新增落盘 `auction_c`(+`ac_day`)、`first_zt`(+`first_zt_day`)；`load_state` 仅当 `state day == 当日` 才还原，跨日丢弃防脏日泄漏。
- 作用：盘中重启后保留 09:25 竞价涨幅缓存与当日已首此涨停集合，避免已首封票被误判再次 `state=first`（首此成交灵敏度）。
- `pool_static / zt_lianban / selfwatch` 本就每日重建，不落盘。
### 3. 卖出审计（`sell_manager` L1210 / `_audit_sell_skip`）
- 原 `g.spot_keys_hint = list(g.spot)[:5]`（截前 5、且为 spot 提示）→ 改 `g.holdings_keys_hint = sorted(positions.keys())`，指向真实持仓遍历集合、不截断，`[sell-skip] positions=` 审计完整。
### 4. firstzt 上报门槛（L1348 / BLS L52）
- 新增 `firstzt_min_seal=50000`（封单≥5万元）、`firstzt_min_bids=5`（买一挂单≥5手）；低于则不上报 `state=first`（过滤假封，如 002134 seal=3600 bids=3）。
- 阈值不达标时次日/后续 tick 仍在 `ft is None` 重新核验，封单长大后再补报，不丢真实首封。
### 自测
- `selftest_exp_rt.py` 新增 T30（ma5 窗口=7.0 vs 全历史5.0）、T31（同日还原 / 跨日丢弃 auction_c+first_zt）、T32（门槛字段非负）。
- 全量 **104 PASS / 0 FAIL**，py310 + PT3.7 双 `py_compile` 通过。

## 2026-10-19 对齐：5D线低吸（ma_pullback）仅对核心(CORE)标签股
- AXquant 契约：低吸场景绑定 CORE（reason="CORE+低吸 price<ma5*1.02"），另有「4板以上中位核心 + 5日内首次回踩MA5」例外。
- PT 对齐（`try_ma5_buy`，AXquant btree builder 为准）：
  - 标签门槛 `ma5_core_only=True`（仅 CORE，连板≥3）+ `ma5_require_bs=True`（对齐 AXquant 的 CORE+BS 双标签，BS=100日新高）；拦截 002167 类非核心"杂毛"。
  - `ma5_first_5d=True`：仅"5日内首次回踩 MA5"触发——此前 4 个交易日盘中最低均未触及/跌破各自 MA5（`_ma5_first_5d`，数据<9根保守 False，缺 low 用 close 近似）；防同一标的重复低吸。
  - `ma5_loose_high=1.02` 匹配 AXquant `price<ma5*1.02`；score 沿用 `buy_score_min`（≥55，严于 AXquant 的 50）；`red_gate` 默认关。
  - AXquant 另有"4板以上中位核心 + 5日首次回踩"例外（当日首次生效、买入价=MA5），云端以 CORE(≥3) 近似覆盖，暂不单独实现例外分支。
- CORE 标签口径（云端简化）：`_tags()` 输出 CORE=连板≥3（LB=≥2、BS=100日新高、CORE=≥3），源自 T-1 涨停/连板名单（docs/33）或 1d 历史近似。
- 触发日志 now 带 tags：`[may-order] <名>(code) buy ... tags=CORE,BS`，便于核对是否核心票。
- 自测：`selftest_exp_rt.py` T26d（非CORE/缺BS被拦截、CORE+BS+首回踩才触发）、T26e（非5日首次回踩被拦截）。

## 2026-10-19 夜间：买入场景补齐 v0.18（try_core_buy 落地 + 首板打板 first_board_buy）
### 1. try_core_buy（核心票买入，替代空桩 pass）
- 门禁：CORE 标签 + score>=buy_score_min + 连板<core_max_lianban(6) + 非一字/封死 + 冷却/可交易 + 日买上限
- 定价：追高 chase（封顶涨停/300/688 弹性 10% 上限）；仓位 ordinary_buy_ratio 10%
- 参数：`core_buy_enabled` / `core_max_lianban` / `core_sealed_skip`

### 2. 首板打板 first_board_buy（firstzt 采集升级为「首板确认→打板」）
- 闸门（按需求定义）：开盘 10 分钟内 + 除一字板 + 板块内涨幅最高 + 主动最快拉升（板块内首个触板）+ 仅首板（T-1 无连板）
- 主路径：tick_data 首触分支（3s 事件）→ 打板（涨停价排队，board_buy_budget_ratio 20%）
- 兜底：handle_data 1m 对池内逼近涨停的首板候选补一次闸门评估（回测/丢 tick）
- 辅助函数：`_is_one_word_open` / `_is_first_board` / `_board_member_codes` / `_board_top_gainer` / `_board_first_zt`
- 参数：`first_board_buy_enabled` / `first_board_minute(10)` / `first_board_seal_min` / `first_board_bids_min`
- `place_order` 增 `ratio` 参数：打板单笔预算 20%（对齐 AXquant board_buy_budget_ratio）

### 3. 买入预算规则（打板20%、其它10%，v0.18 确认）
| 场景 | 预算 | 来源 |
| 首板打板 first_board_buy | 总资产 20% | `board_buy_budget_ratio` |
| 预期买入-打板（触板/一字CX） | 总资产 20% | `place_expected_order` mode=board |
| 核心票 core_buy | 总资产 10% | `ordinary_buy_ratio`（place_order 默认） |
| ma5 低吸 ma_pullback | 总资产 10% | `ordinary_buy_ratio`（place_order 默认） |
| 预期买入-追高（chase） | 总资产 10% | `exp_order_pct`（默认已对齐 0.10） |
- 单支市值上限仍受 `single_stock_cap`(30%) 约束（`_calc_buy_qty`）
- selftest T40 锁定该规则（153 PASS / 0 FAIL）

### 4. 自测与编译
- selftest T36-T39：core_buy 门禁 / 首板闸门 / 首板下单 / tick 端到端（当前 148 PASS / 0 FAIL）
- 双编译：py310 + PT3.7 通过

## v0.26 tick 级卖出（2026-10-19，事件驱动 3s 响应）

- 验证结论（审查 sell_manager 全路径）：炸板卖出此前未生效（tick 只采集 first_zt.break 打日志，无消费方）；封单大减卖出仅对一字板预期标的（_exp_one_word CS）生效且只在 1m 评估。
- 落地：新增 `tick_sell_manager`（tick_data 3s 帧末）：
  - 炸板卖出：`first_zt.break` 首触发 -> 卖（现价限价，`TICK_break_sell`；break_sold 当日一次 + 持久化）。
  - 封单大减卖出：`first_zt.seal_low` 首触发（封单<=首封×seal_fail_ratio）-> 卖（`TICK_seal_low_sell`）。
  - 急卖迁移：P1 绿开 / P2E 预期 miss / P3 止损 3s 响应（核卖限价跌停地板价）；P4-P6 留 1m sell_manager。
  - 去重：_sell_inflight + sold_log 30s 冷却 + break_sold/seal_sold 跨重启持久化。
- 参数：tick_sell_enabled / break_sell_enabled / seal_low_sell_enabled（均可单独关）。
- 自测：T59 六项（炸板首触发卖/标记/不重复、封单大减卖/标记、P3 tick 止损）。全量 259 PASS / 0 FAIL；双编译通过。

## v0.32 云端持仓预期管理（2026-10-20）

> 背景：本地拉取持仓不可行（客户端 Quant API 无本地 LISTEN 端口，sync_positions 无限阻塞）→ 持仓预期管理全部改为云端策略内算法完成，不依赖本地文件。

- 新增 _hold_exp_init(sec, force=False)：对任一只持仓股建立/刷新 g.exp 预期条目：
  - 基准全部来自云端算法：竞价三态 _eval_auction（get_trend_data 真口径 + 云端 1d 历史折算）、分时三态 _eval_intraday（两分钟上攻/破 VWAP）、一字板判定 _is_one_word_open。
  - 回填预期文件字段 sell_policy_hint / expected_status / expected_auction_change_pct / seal_amount_t0（有文件则对齐 T-1 复盘，无文件则纯云端算法兜底）。
  - 幂等：已确认的 uction_status/status 不覆盖；orce=True 跨日重算（handle_data 日切）。
  - 首次初始化打 [hold] <名称>(code) 持仓预期管理初始化 entry_type=.. auction_status=.. status=.. sell_policy=.. 日志。
- 接线三处：
  - on_trade_response 成交回报：买入/任意成交即建立条目 → 补「盘中新买入持仓无预期条目」缺口（此前 g.exp 仅 09:25/09:31/日切初始化）。
  - sell_manager（1m）与 	ick_sell_manager（3s）循环开头：确保条目存在（幂等），重启后自动重建。
  - handle_data 日切：改 _hold_exp_init(sec, force=True)（原内联重算逻辑统一收敛）。
- 效果：P4 卖出链（普通预期 _eval_intraday / 一字板 _exp_one_word 封单实时化）对「当日盘中买入的持仓」也立即生效，卖出决策基准=云端实时三态。
- 自测：T66（初始化/回填/幂等/一字板继承）、T67（买入成交回调建条目）、T68（跨日 force）。全量 312 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py。

## v0.33 文件持仓预期 vs 云端实时 防冲突仲裁（2026-10-20）

> 背景：上传的复盘文件（expectation CSV）side=hold/sell 行携带 xpected_status(pending_*)、sell_policy_hint、ntry_type、seal_amount_t0。文件是 T-1 静态预期，云端是 T+1 实时算法——两者方向冲突时需仲裁，原则：**云端实时硬信号优先，文件只作方向/容忍度参考**。

- 新增 _realtime_weak(sec)（廉价版）：竞价绿开(_auction_change<0) 或 破 VWAP → 实时走弱。不调用 _eval_intraday/_two_1m_break（避免 tick 3s 帧吃 1m get_price 帧预算）；P4 仍用完整分时三态。
- 新增 _hold_arb_log(sec, msg)：[arb] <名称>(code) ... 60s/股节流防刷屏。
- 三处仲裁：
  1. _role_tolerance：文件乐观容忍（如 hold_higher_tolerance green_tol=2.5/stop_adj=1.3）在实时走弱时回落 P1 绿开/P3 止损因子到 1.0（实时硬信号优先）；评分类软阈值（score_clear_adj/score_half_adj）仍按文件缩放；激进/保守因子（<=1.0，如 fast_exit）保持（本就该更敏感）。
  2. sell_manager P2E：文件悲观（confirmed_miss/degraded）但实时竞价超预期反证（_confirm_expected==CX）→ 不核卖，交实时分时三态；未反证仍核卖（对齐 AXquant）。
  3. sell_manager P4：文件 ntry_type=one_word 但实时已开板（_is_one_word_open False）→ 回落普通分时三态评估（防封单误判/漏卖）；实时仍封板 → 走 _exp_one_word 封单逻辑。
- 自测：T69（文件 miss+实时 CX 反证不核卖）、T69b（未反证核卖）、T70（实时绿开回落乐观容忍 P1/P3）、T71/T71b（一字板实时开板回落 / 实时封板走封单）。全量 318 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py。

## v0.34 连板中位股规避（2026-10-20）

> 背景：AXquant 复盘对持仓/苗子已标注连板角色（role_detail），其中「连板中位股」（既非首板/一进二低位，也非唯一性高标）在云端此前无规避 → 新增消费与兜底。
> 参考点：低位=首板/一进二（first_board_arb / leading_first_board）；高位=唯一性展现（unique_high_board_consecutive）；中位=mid_consecutive_limit_up（规避）。

- AXquant 侧（D:/PROJ/AXquant/strategy/expectation/publish.py `derive_role_detail`）：mid_consecutive_limit_up（中位）/ unique_high_board_consecutive（高位唯一性，板块内唯一高板 + follower_count>=1）/ leading_first_board（低位领涨首板）/ first_board_arb（首板弹性套利）。
- 链路打通：AXquant 复盘 jsonl 标注 → bridge CSV 新增 `role_detail` 列（expectation_store.export_expectation_csv + build_expectation_bridge.CSV_HEADER）→ 云端 `_load_expectation` 读入 g.exp_file[code]['role_detail']。
- 新增 `_mid_board_avoid(sec)`（v0.34）：
  - role_detail=mid_consecutive_limit_up → 规避（True）。
  - role_detail=unique_high_board_consecutive / leading_first_board / first_board_arb → 放行（False）。
  - 无标注兜底：仅当权威 zt_lianban 有记录且 T-1 board_cnt∈[2,5] → 近似中位规避（role 为复盘口径，盘中是否续板不改分档；board_cnt<2 首板/一进二放行，>=6 高位候选放行）。
- 挂闸点（全部为买入侧；卖出链不挂闸，持仓卖出照常走 P1/P2E/P3/P4）：
  - `_attempt_expected_buy` / `place_expected_order` / `place_order`（buy 分支统一兜底）→ `[mid-avoid] <名称>(code) 连板中位股规避(expected_buy|exp-order|order)`。
  - `try_core_buy`（[mid-avoid] core_buy）/ `try_ma5_buy`（ma5）/ `_try_first_board_buy`（first_board）。
  - `_synth_pool_expect` 涨停池合成（云端兜底）同口径过滤中位：合成日志加 `mid_skip=N`。
- 自测：T72 系列（role_detail 分档规避/放行、无标注 zt 兜底 1/3/6 连板、place_order/place_expected_order/_attempt_expected_buy/try_core_buy/try_ma5_buy/_try_first_board_buy 拦截、涨停池合成中位过滤）。全量 333 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py；bridge CSV 需重跑（build_expectation_bridge.py / export_expectation_csv）带出 role_detail 列。

## v0.34b 连板中位股规避-唯一高度板兜底修正（2026-10-20）

> 漏洞修复：兜底按 T-1 连板数 2–5 一刀切规避，会把「高度压制到 3/4 板但展现唯一性（板块内唯一高度板+跟风低位板）」的龙头误杀。
> 对齐 AXquant 收盘地位重算的唯一身位判定（publish.py）：板块内最高身位唯一 + 板块内≥2 家（或全市场唯一高标特例）→ unique_high_board。

- 新增 `_annotate_zt_uniqueness()`（云端兜底标注）：`_load_zt_lianban` 补读 `reason` 列后预计算唯一性：
  - 板块口径 = 涨停原因首 token（云端无权威板块映射，首 token 兜底分组，与 AXquant 复盘 board_name 同源）。
  - 组内最高身位唯一 + 组内≥2 家 → `unique_high=True`，`follower_count`=组内更低身位家数（跟风低位板）。
  - 特例：全市场最高身位唯一（高度压制到 3/4 板等场景）也授唯一。
  - 并列最高（两票同板数）不授唯一。
- `_mid_board_avoid` 兜底改：`2<=board_cnt<=5` 时，若 `unique_high` → 放行（对齐 unique_high_board_consecutive）；否则规避。
- 权威优先不变：复盘 `role_detail=mid_consecutive_limit_up` 仍规避；`unique_high_board_consecutive` 仍放行（不依赖兜底）。
- 自测：T73 系列（板块唯一 3 板+跟风放行 / 并列最高规避 / 全市场唯一高标放行 / 板块有更高身位时 3 板规避 / role_detail 权威优先）。全量 346 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py；zt_lianban CSV 需含 `reason` 列（export_lianban.py 已导出）。
