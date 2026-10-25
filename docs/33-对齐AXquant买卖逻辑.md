# 33-对齐 AXquant 买卖逻辑（v0.15）

> 版本：buysell_core v0.15　目标：把 PT 托管策略的单键买卖逻辑对齐 AXquant 已实盘验证的真实口径，收敛三处关键差异：**一字板封单超预期不参考排单 / 竞价核卖 P2E / 弹性买入价 10% 上限**。上游 AXquant 依据：`axquant/runner/bt_handlers.py`（P1-3 sealed、弹性 cap）、`axquant/strategy/btree/builder.py`（AUCTION 卖出链、_is_sealed_at_limit）、`axquant/strategy/decision/sell.py`（止损分档）。

## v0.70 5D低吸：生命周期次低价进入 MA5±2% 带（2026-10-23）
- 生命周期按交易日维护观察到的两个最低价，`low2` 为次低价；至少形成两个样本后才可触发。
- 动态 MA5 以 `low2` 作为今日临时收盘价计算：`(前四日收盘均值×4 + low2)/5`。
- 次低价满足 `abs(low2-ma5)/ma5 <= 2%` 时视为触及；仍需 CORE（T-1 连板>=3）、`score>=50`，买入仓位 10%。
- 首次进入 MA5 带后评估一次；评分或红盘门不达标则当日不追补。评分未就绪不消耗首触。
- L2 净大单占比达到 10% 仍由 `score_now -> _l2_big_bonus_pts` 加 5 分，不作为硬门。
- 开关：`ma5_second_low_enabled=True`、`ma5_touch_band=0.02`；关闭次低价开关可回退为现价与动态 MA5 的距离判断。
- 验证：T26d/T26d2/T26e/T26f/T30/T56/T72，覆盖次低价形成、±2% 边界、评分 49/50、10% 仓位、当日去重、跨日重置与同日重启恢复。

## v0.69 5D低吸：动态 MA5 + CORE 首次触线 + score>=50 + 10%（2026-10-23）
> 实盘核对 603278：PT 日志 `ma5=11.00`，而今日现价 15.96 对应动态 MA5=13.31。旧实现盘前预算后全天缓存，
> 且按最近 5 个已完日计算；盘中未把当前价纳入，无法反映当日均线。
- `_ma5_base4`：取最近 4 个已完成交易日收盘均值。get_price 日线默认不含今日；若末行确为今日，则按索引日期剔除。
- `_ensure_ma5`：`(base4×4 + 当前价)/5`，每次随当前价动态变化；`dump_scores` 同时输出 `ma5` 与 `ma5b4`。
- `try_ma5_buy`：CORE（T-1 连板>=3）+ 当日首次触线 + `price<=ma5×1.00` + `score>=50` +
  显式 `ratio=0.10`。`ma5_require_bs` 默认关闭，不再要求 100 日新高；L2 净大单加分继续并入 `score_now`。
- 首触按交易日去重，`ma5_first_5d=False` 默认关闭旧“五日内首次回踩”；同日重启恢复首触状态，跨日重置。
- 口径警示：不能以收盘后抬高的 MA5 反推早盘触线。603278 在 09:31 最低 13.23 时动态 MA5 约 12.76，
  当时价格仍在均线上方，未触发；13.31 是午后涨停后随现价抬升的实时 MA5。
- 验证：T26d/T26e/T30/T72 更新，覆盖动态均线、今日 K 线剔除、精确触线、score=49/50 边界、10% 仓位与 L2 日志。

## v0.68 评分/竞价/预期文件三重数据就绪加固（2026-10-23）
> 实盘 10-23 观测三处数据就绪缺口：①盘中重启(10:19 v0.66)后首帧行情/板块未就绪被当 0.0 打分，
> 重启后评分虚高（三峡新材 48→70、海洋王 40→65，chg=0.0% board=0.0 只剩加分）；②09:30:01-02 首帧缺前收致
> `_auction_change` 写死 (day,0.0) 毒缓存，大业/海洋王/安乃达/赛福天 4 个唯一预判 `miss=auction_not_met(0.0%)`
> 当天永久误弃（exp_fired 不可恢复）；③`expectation_latest.csv` 盘中 15→5 全量替换丢候选。
- A 评分数据就绪门：`_spot_ready`（现价+前收齐备）+ `_board_strength_info`（板块有归属但无有效涨跌样本=不可测，
  未映射=中性放行）；未就绪 `score_now` 返回 None：买入入口跳过、卖出 P5/P6 跳过防误卖、`dump_scores` 打
  `data_na`，`[score-na]` 60s/票节流。
- B 竞价未就绪守卫：`_auction_change` 缺前收/无价返回 0.0 且不写缓存（下帧重算，根治毒缓存）；`_auction_ready`
  缓存命中或 前收+开盘齐备即就绪；`_exp_rt_status` 超预期路径未就绪 -> `PM await_intraday_confirm` 不再误弃；
  首帧 `_avail_cash<=0` 静默跳过（下帧自然重试）。
- C 预期文件盘中替换保护：盘中重读 `_load_expectation(merge=True)`（09:25/09:31/P2E 钩子）逐 code 合并防收缩；
  日期守卫（date/trading_date/generated_at 列非今日拒绝重载）；差异日志 `expectation file merged old=.. new=.. total=..`。
- 上传契约：定时上传任务需 **9:15 前完成上传**，09:25 竞价终态重读命中当日文件；若 08:59 首载读到前一日残留
  属正常（盘中 merge 后以 09:25 当日文件为准，不再丢候选）。
- 自测：T120-T127 新增 8 例（评分就绪门/板块不可用/不写毒缓存/未就绪不误弃/资金静默/merge 不丢/日期拒绝/差异日志），
  全量 728 PASS / 0 FAIL。
- 待重传 strategy.py，核对日志首行 `version=v0.68`、重启首帧 `[score-na]`、09:30 不再 `miss=auction_not_met(0.0%)`、
  09:25 `expectation file merged old=.. new=..`。

## v0.67 L2 大单链路补齐：盘中入池补播种 + 探针节流重打 + 批量缺票兜底（2026-10-23）
> 实盘 10-23 观测：盘中新入池触板票（统一股份、奇精机械、登康口腔、榕基软件、天娱数科、达实智能等）不在 09:25/09:31 播种列表，
> 首次进入近涨停目标集时 `[l2-big]` 首帧打印 0/0 且探针只打一次；同帧批量逐笔偶有部分票缺行/近空（兆威/华阳有数据而登康/大港近空），
> 大单净量比决策读实时累计不受影响，但首帧信号失真、盘中无法核对。
- A) 盘中入池补播种 `_l2_big_seed_onjoin`：tick_data 构建 `_near` 后对未播种票按 `l2_big_seed_onjoin_interval_sec`(60s)
   节流调 `_l2_big_seed(pages=l2_tickdir_pages_onjoin=5)` 回看历史大单；与既有 `l2_big_wm` 水印共用，双源不重复，首帧即有累计。
- B) `[l2-big]` 探针分钟节流重打：首帧立即打印，之后按 `l2_big_log_sec`(300s) 间隔重复打印同票累计变化，便于盘中核对；
   direction 全部未识别告警仍只在首帧。
- C) 批量逐笔缺票兜底：`_tx_pull_raw` 批量拉取后统计缺行票，帧预算内（`frame_tx_limit` 1->2、`l2_tx_fallback_cap=5`）
   逐只 `get_individual_transaction([c])` 补回并合并 fields（字段序不一致时按批量 fields 重排，缺列补 None）；
   打 `[tx-pull] req=.. got=.. missing=.. (fallback=..)`；兜底结果并入本帧 raw，下帧新 token 仍可重试。
- 自测：T117（入池播种历史大单进 acc 买/卖分量 + 60s 节流防重复 + 已播种票过滤）+ T118（首帧立即/间隔内不重打/超时重打+时间戳更新）
  + T119（批量缺票单票补回、fields 合并、missing 日志）+ T51 契约更新（批量一次拉取+缺票单票兜底、同帧二次消费不重复拉）。
  全量 700 PASS / 0 FAIL；py3.13 编译通过。
- 待重传 strategy.py，核对日志首行 `version=v0.67`、盘中新票 `[tickdir]` 入池播种、同票 `[l2-big]` 多时间点、
  `[tx-pull] .. missing=.. (fallback=..)` 与收盘 `[l2-big-sum]`。

## v0.66 L2 大单占比分母打通（2026-10-23）
> 实盘 10-23 发现 `[l2-big]` 占比全天恒 `-1.00%`：`_l2_big_ratio` 分母取 `turnover`/`amount`，而云端
> `get_snapshot` 无 `turnover`（只有 `turnover_ratio` 换手率），`amount` 是期货字段股票恒 0；权威字段为
> `business_balance`（总成交额，元）。分母恒 0 -> 占比恒 -1 -> 大单占比增强项（加分/封单豁免/回封门）全程静默。
- A) 新增 `_l2_big_turnover(sec)` 统一分母：`business_balance`（总成交额元）优先 ->
   `business_amount`（总成交量股）x `wavg_px`/`last_px` 兜底 -> `turnover`/`amount` 旧环境兼容。
- B) `_l2_big_ratio` 分母改用 helper；首板记录 `g.first_zt['amt']`（原 `turnover or amount` 恒 0）同步修复。
- C) `[l2-big]` 探针补打 `分母=` 便于现场核对；日志 `分布=` 明确为 `全局分布=`（`g.l2_dir_dist` 为全市场共用字典）。
- D) 买入/卖出大单取得强化（净大单=买入大单-卖出大单，两个分量才是分子关键）：方向来自逐笔
   `business_direction`（0=卖、1=买、2=借入/3=出借不计入净量，docs/10 官方字典）；`l2_big` 累计结构
   增 `bn/sn/un_n` 大单笔数分方向计数，`[l2-big]` 探针输出 `大单买=..(N笔) 卖=..(M笔)`；
   `after_trading_end` 增 `[l2-big-sum]` 按票日结 买额/卖额/净额/笔数（净额降序前 30），供次日核对买入/卖出大单均取得。
- 自测：T115 新增（business_balance 优先 17% 加分 / business_amount x wavg 兜底 / turnover 兼容）
  + T116 新增（逐笔/播种双源 buy/sell/un 金额与笔数分计、净大单=买-卖、日结按净额排序）。
- 待重传 strategy.py，核对日志首行 `version=v0.66` 与 `[l2-big] .. 占比=..% 分母=..` 不再全 -1。

## v0.64 订单系统闭环 + 资金实时（2026-10-23）
> F1-F5 修复订单系统闭环，并落地"资金实时最新"（用户补充：云端持仓拉不到本地，成交/委托主推是唯一实时的资金与持仓对账通道）。

### F1 买入量化记账只在发单成功时
- `place_order`/`place_expected_order` 改为返回 bool（True=已发单或 SIM 信号，False=跳过/异常）。
- 7 个买入信号点（动态扫板/低吸/core_buy/首板/回封/弹性套利/弹性top）改 `if place_order(...):` 成功才记 `daily.bought`——修复静默失败占 `daily_max_buy=1` 名额。
- 预期买入路径 `place_expected_order` 保持现状（2897 已 `if not place_expected_order(...)` 返回 None 不置 fired）。

### F2 委托主推释放买名额 + 终态释放资金承诺
- `on_order_response` 重写为 list[dict] 主推（PTrade 回调传 list，兼容单对象）：`_map_order_status` 状态码映射（'0'未报 '1'待报 '2'已报 '3'待撤 '4'部成待撤 '5'已撤 '6'废单 '7'部成 '8'已成 '9'部撤 'V'已确认）。
- buy 单终态（FILLED/CANCELLED/REJECTED/PARTIAL 按成交额）`_buy_commit_rel` 释放 `g.buy_commit`；REJECTED/CANCELLED 额外 `_release_buy_slot` 释放 `daily.bought`+`exp_fired`（buy_log 冷却保留防信号风暴）。

### F3 在途委托/买入承诺持久化 + 重启对账
- `g.pending` + `g.buy_commit` 纳入 `_save_state`/`load_state`（仅同日分支恢复，跨日清空）。
- `before_trading_start` 挂 `_reconcile_pending()`：`get_open_orders()`+`get_all_orders()` 重建在途委托（防重复卖/资金扣减），restart 后 `_sell_inflight` 继续生效。

### F4 预期下单 pending 字段补齐
- `place_expected_order` pending 补 `status='SENT'/'filled'=0/'ts'`，与 `place_order` 对齐，保证主推回填与重启恢复一致。

### F5 成交主推回填 + 撤单跳过
- `on_trade_response` 重写为 list[dict]（PTrade 回调传 list）：sell 成交回填 `filled`+`sold_log`+`daily.sold`；buy 成交按成交额释放买入承诺；撤单主推（`real_type='2'`）与废单跳过；成交量取绝对值（实盘撤单/卖可能为负）。

### 资金实时（_avail_cash）
- `_avail_cash = portfolio.cash - sum(buy_commit)`（在途买单承诺，现价×量），防 6s 资金同步滞后窗口超配。
- `_buy_pos_ok`/`_calc_buy_qty`/`place_order`/`place_expected_order` 统一走 `_avail_cash`；commit 由主推回报终态释放。

### 验证
- selftest 新增 F1-F5 17 条（无行情跳过 False / 实单记 pending+commit / REJECTED 释放三件套 / 状态码映射 / FILLED 释放 / 同日重启恢复 pending+commit / _avail_cash / sell 成交回填 / buy 部分成交释放 / 撤单跳过）；全量 666 PASS / 0 FAIL；py3.10 编译通过。
- 待重传 strategy.py，核对日志首行 `buysell_core init version=v0.64`；盘中核对 `[order sent]`/`[buy-slot]`/`[pending-restore]`/`on_order_response status=`/`on_trade_response`。

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
- 数据契约列（表头）：`date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes`
- 代码后缀映射：AXquant `.SH→.XSHG / .SZ→.XSHE / .BJ→.XBJ`（与 expectation 同名同映射）。
- 字段来源：AXquant `payload.pool.item[]` = `thscode/ticker/name/continue_day_cnt(连板数)/limit_up_time/seal_money/price_change_ratio_pct/is_st/limit_up_reason`；同报文另含 `ladder/break_pool/summary`。
- 题材/概念梯队列（v0.38）：`theme`=主题材（题材内最高板优先、家数次之）、`theme_count`=题材涨停家数、`theme_max_board`=题材最高连板、`theme_rank`=梯队名次（家数+最高板排序）、`themes`=全部题材（`|` 连接）；优先读 AXquant `data/tmp/review_analysis_<date>.json` 的 `theme.buckets`，缺失时按 `reason` 标签本地聚合兜底。
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
- `_load_zt_lianban()` 解析为 `g.zt_lianban[code] = {date, board_cnt, limit_up_time, seal_money, chg_pct, is_st, unique_high, follower_count, theme, theme_count, theme_max_board, theme_rank, themes}`；缺列默认 theme=""、计数/名次 0；`g.zt_theme_authoritative` 标记文件是否带题材列，加载日志输出 `themed=N`。
- 唯一身位兜底（v0.38）：文件缺 `unique_high` 列时，`_annotate_zt_uniqueness` 优先按 `theme` 分组（对齐 AXquant theme.buckets 口径），缺题材列才回退涨停原因首 token 分组。
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

## v0.46-v0.47 首板收紧与灵敏度（2026-10-22）

> v0.46：`_try_first_board_buy` 补首板封单下限（L2 买一挂单金额 >= first_board_seal_min，防假封秒炸）；
> `_dyn_unq_auction_eval` 跳过中位股（与 `_mid_board_avoid` 统一口径，`dyn_unq_mid_skip`）。
> v0.47：A) L2 大单占比加分（逐笔 business_amount 按 trade_index 去重累计，占比>=10% 加分5分/封单豁免）；
> B) 强度前三板块成员并入 tick 目标集（`tick_board_scan`）+ scan_interval 4->1 + [scan] 窗口探针；
> C) 预封扫板=封单下限 或 大单加持 二者满足其一。
- 自测：T99/T100/T101/T102/T103。全量 527 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py。

## v0.48 修复 v0.47 实锤问题（2026-10-22）

> 依据今日 11:08-11:29 日志：`business_amount` 单位非'元'（10.5 元股票单笔 200 不可能为元）→ 全下午
> `[l2-big] 累计大单=0 占比=-1%`；且每帧 `board=6/6 over:3~19 / bcode over / hist1d over` 帧预算超限。
> A) `_tx_big_feed` 按 `l2_big_amt_unit`（默认 shares）将 `business_amount x hq_px` 换算元（lots x100，
>    yuan 直用）；探针输出 `最大单笔=..元 unit=..`；累计结构增 `max` 键。阈值 `l2_big_amt_min` 仍按元。
> B) `tick_board_scan` 并入强度前三成员仅限首板窗口（`_min_age()<=first_board_minute`），
>    `tick_board_member_cap` 20->10（午后并入无交易价值，帧预算归零）。
- 自测：T101 重写（shares 换算口径）+ T103 补窗口内时间 + T104 新增（shares/lots/yuan 换算、窗口内外门控）。全量 533 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.48` 与 `[l2-big] ... 最大单笔=..元` 探针。

## v0.59 持仓卖出闭环：地位评估 + P7a/P7b/P7c（2026-10-22）

> 背景：持仓卖出核心是「标的持续超预期」，监控点为主动性（非跟风）与板块加持；此前主动性/地位只在买入侧消费，
> 持仓持有/卖出侧无显式地位评估。本次落地持仓地位评估 + 三个主动卖出闭环（P7a 连板放量不封板 / P7b 跟风拉升不封板 /
> P7c 首板次日不主动冲板分批清仓），tick（3s）与 1m 双链兜底。

### 持仓地位评估 `_hold_stand(sec)`
- 15s 节流缓存（`hold_stand_cache_sec`），输出 role / active / board 三维：
  - role：动态龙头 `_dyn_theme_leader` -> leader；T-1 `board_cnt∈[2,5]` 非唯一 -> mid；池内同题材有存活更高身位 -> follower；其它 -> outside。
  - active：个股涨幅 >= 板块强度 + `p7c_active_threshold`(0.5%) -> 主动；板块强但个股明显弱于板块 -> 跟风；其它中性。
  - board：板块强度>=`p7b_board_min`(1.0) 或所属题材存活龙头/发酵前排封板 -> 强；板块强度<=-1 -> 弱；其它平。
- 评分仅持仓消费（`_hold_stand_pts`）：leader+3 / follower-1 / mid-3 / active+3 / 跟风-3 / 板块弱-3；
  日志 `[hold] <股名> role=.. active=.. board=.. pts=..`（60s/股节流，`hold_stand_log_sec`）。

### P7a 连板放量不封板（`_p7a_check`）
- 条件：持仓 + T-1 `board_cnt>=2` + 今日量>=昨日量×`p7a_vol_ratio`(1.10) + 未封板（`_sealed_now`）。
- 量口径：今日量=`_snap_vol`（快照 volume），昨日量=hist1d `vols[-2]`（[-1]=今日 [-2]=昨日，与 `_volume_ratio` 同口径）；
  `[vol]` 探针（随 `_l2_probe` 每日一次）输出快照 volume / hist1d[-1] / hist1d[-2] 核对单位。
- 卖出：唯一身位（`_unique_stand`）降级减半（`p7a_half_ratio`=0.5），否则清仓；现价限价非地板价（非核卖）。
- 去重：`g.p7a_sold` 首触发标记，跨重启持久化。

### P7b 跟风拉升不封板（`_p7b_check`）
- 条件：持仓 + role∈(follower,outside) + 板块强（`_hold_board_strong`：板块强度>=1.0 或题材存活龙头/发酵前排封板）
  + 1m surge>=`p7b_surge_min`(1.5) + 未封板 -> `P7b_follow_break` 减半（`p7b_half_ratio`=0.5）。
- 语义：跟风股在强板块被拉起但不封板 -> 减半兑现；去重 `g.p7b_sold` 跨重启持久化。

### P7c 首板次日不主动冲板 -> 冲高分批清仓（`_p7c_check`）
- 条件：T-1 `board_cnt==1` + 09:30-10:00 窗口（`p7c_until_minute`=30）active≠主动 -> 标记 `p7c_price`（仅标记不卖）。
- 触发：现价>=标记价×(1+`p7c_surge_min`%) 且未封板 -> 每 `p7c_batch_cold_secs`(10s) 卖一批（2×50%；
  `_do_sell(..., cool=False)` 批次间隔自控，不写通用 30s 冷却，第二批 10s 即触发）。
- 回封（`_today_zt`/`_sealed_now`）取消标记；转主动取消标记；破 VWAP 由 P4 兜底。
- 状态：`g.p7c_part`（price/half/sold1_ts）+ `g.p7c_sold`（完成）跨重启持久化。

### 接入与配置
- tick 卖出链 P3 后 P4 前（3s）+ 1m `sell_manager` 同条件兜底（双保险，sold_log 冷却 + 在途守卫去重）。
- BLS：`p7_sell_enabled / p7a_vol_ratio / p7a_half_ratio / p7b_board_min / p7b_surge_min / p7b_half_ratio /
  p7c_until_minute / p7c_surge_min / p7c_batch_cold_secs / p7c_active_threshold / hold_stand_cache_sec / hold_stand_log_sec`。
- 自测：T113 新增 19 项（P7a 清仓/唯一减半/未放量/已封板/仅连板、P7b 减半/leader/surge不足/板块弱、P7c 标记/第一批/冷却内/第二批/
  回封取消/主动不标/窗口外、地位评估 leader/mid、tick 链 P7a 触发）。全量 644 PASS / 0 FAIL；py3.10 编译通过（兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.59`。

## v0.63 死代码清理（2026-10-23）

- 删除生产未引用函数：`_set_bs`/`g.bs_cache`（只写不读，板块强度缓存已由 DataHub `board_chgs` 替代）、
  `_elastic_ask1`（已被 `_order_limit('chase')` 的 `_max_elastic_buy_price` 替代）、
  `_tx_first_zt_ms`（v0.22 起 tick 主路径走 DataHub.tx_zt_batch 批量，兼容入口无生产消费）。
- 删除 BLS 死键 6 个：`auction_buy_score_min`/`expectation_base`/`market_red_enabled`/`first_board_bids_min`/`score_max`/`score_min`；
  ATK 死键 `elastic_threshold`（仅 `main_threshold` 被 `_attack_bonus` 消费）。
- 保留项：引擎入口回调（initialize/handle_data/tick_data/before_trading_start/after_trading_end/on_order_response/on_trade_response）
  由 Ptrade 按名调用；`frame_*` 预算键经 `_source_limit` 动态拼接读取，属活跃配置；BONUS/PENALTY 全键消费、无死项。
- selftest：删除对应死代码测试 T42b（_elastic_ask1）/T46（_tx_first_zt_ms）共 6 断言；`_DAY`/`_lt` 由 T47/T51 自建不受影响。
- 自测：全量 649 PASS / 0 FAIL；py3.10 编译通过（兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.63`。

## v0.62 首板/回封买入门封单下限同步（2026-10-23）

- `first_board_seal_min` 50000 -> 200000（首板打板最小封单额，3461）：预封扫板需 seal 达标或大单加持二者满足其一。
- `reboard_seal_min` 50000 -> 200000（回封封单下限，3523）：回封打板除大单占比>=10% 外封单需达标。
- 与 v0.61 `firstzt_min_seal`(200000) 上报侧同档，三处门槛口径一致；`firstzt_min_bids`(5)/大单加持规则不变。
- 自测：全量 655 PASS / 0 FAIL；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.62`。

## v0.61 首此涨停封单门槛上调（2026-10-23）

- `firstzt_min_seal` 50000 -> 200000（元）：首此涨停上报最小封单额（5366 快照兜底 / 5383 回封确认），
  过滤小封单假封；`firstzt_min_bids`(5) 不变。
- 首板/回封买侧门槛于 v0.62 一并上调至 20 万（买侧语义与上报侧对齐）。
- 自测：全量 655 PASS / 0 FAIL；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.61`。

## v0.60 板块口径统一：残留链路全切 THS 概念文件（2026-10-22）

> 背景：v0.36e 弹性套利链路已走文件 THS 概念口径（boards_latest.csv），但残留 5 处 API 双轨
> （get_stock_blocks/get_industry_stocks）：板块强度前三门控、评分板块分、板块红盘比、弹性一字归属。
> 本次按「口径统一 + 灵敏度保持」原则全部切到文件概念口径，未加载/开关关闭回退 API。

### 改动点
- 开关 `board_concept_unified=True`（默认开；False 一键回退旧 API 双轨），`[boards] loaded` 日志标注 unified 状态。
- `_board_rank_top3_set`/`_board_rank_top3`：候选板块集改 `_concept_boards_of`（全列表），强度改 `_concept_board_strength`；
  候选源统一 `_elastic_top_cand_src`（池∪T-1涨停名单）-> 与 `_new_top_board_scan` 同 key 共享 `csnap_led` 合并快照账本（零额外 RPC）。
  消费点：首板/回封/弹性套利板块目标门控、tick 扩板。
- `_board_strength`：新增 `_board_strength_by_concept`（所属概念板块强度取最强，聚合决策已确认）+ `_concept_strong_board`；
  打分 `_board_bonus`/板块走弱扣分/dump_scores/P7b 板块强/地位 board 分类全走概念。
- `_red_ratio`：最强概念板块成员 up/(up+dn)；`_elastic_yizi_scan`/`_elastic_in_strong_board` 一字板归属切 `_concept_boards_of`。
- `_concept_snap_for` 统一快照入口：共享账本（csnap_led 新鲜且覆盖该板块）零额外 RPC；否则单板批量预算缓存
  （budget=board，`_board_refresh_ttl` 与 API 旧链同节奏，防 score_now 高频触发批量）。

### 灵敏度/预算
- 10:00 前 3s 同频保持（`_board_refresh_ttl` 不动）；首板/回封门控用「账本新鲜读共享 snap、否则单板批量」双路径，
  冷启动每候选板 1 次批量（与旧 API 路径同构），账本整轮完成后同帧 0 额外 RPC。
- `frame_board_limit_fast=24` 覆盖候选板块并集分帧续算；`get_stock_blocks`/`get_industry_stocks` 主链归零（仅兜底保留），blocks 预算释放。
- 共享账本验证：T114 断言 top1 建账后 rank_top3 强度读账本、不产生单板 cbsnap 缓存。

### 自测/边界
- T114 新增 11 项（最强聚合/单板块强度/概念top3/rank门控/红盘比/elastic归属/共享账本/开关关闭回退/未加载回退）。
  全量 655 PASS / 0 FAIL；py3.10 编译通过（兼容 PT3.7）。
- 边界：概念成员 cap 20 与 API 成员数不可比，跨日对比以文件口径为准（5日均值已文件化）；boards_latest.csv 低频，
  文件 mtime 超 3 日日志告警（不自动回退，防盘中口径跳变）；未在文件内的标的（非池/涨停名单）无概念归属 -> rank 门控不通过（文件为准）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.60` 与 `[boards] loaded ... unified=True`。

## v0.58 P2E 竞价核卖（同题材中位崩塌传导 + 自身大不及）（2026-10-22）

> 背景：P2E 原逻辑只对文件 `expected_status ∈ (confirmed_miss, degraded)` 清仓（无竞价幅度、无题材传导、9:30 后才有卖出链）。
> 本次按确认方案收紧：触发时点提前到 9:24:50（9:15-9:25 钩子），新增同题材中位崩塌传导（题材层面冰点），
> 并对自身大不及加竞价幅度门槛，唯一高身位豁免交盘中监控。

### 触发条件
- A（题材传导，`p2e_theme_sell_enabled=True`）：持仓所属题材（`_zt_themes_of`）存在中位股（T-1 `board_cnt ∈ [2,5]`），
  中位股最弱竞价 `_auction_change(mid) <= p2e_theme_drop_min`（默认 -2.0），且 9:24:45 自身确认
  （基准有效：`竞价 < 基准`；基准无效：`竞价 < 0` 绿开）。
- B（自身大不及）：文件 `expected_status ∈ (confirmed_miss, degraded)`（`exp_sell_on_pending_miss=False` 时 pending_miss 不卖）
  + 自身竞价 `_auction_change <= p2e_auction_drop_min`（默认 -2.0）。
- 豁免：唯一高身位（`_unique_stand`：静态 unique_high / 动态唯一确认）不核卖，容忍度交盘中监控。
- 范围守卫：仅持仓 + `_sellable>0` + 非在途（`_sell_inflight`）+ sold_log 冷却外 + 条目 `side ∈ (sell, hold)`（排除 buy）。
- 反证守卫：文件悲观但实时 `_confirm_expected == CX`（云端竞价超预期）-> 不核卖，转实时分时三态。

### 时点与双保险
- `run_interval(seconds=3, interval_timer_ranges='09:15-09:25')` 钩子 `p2e_auction_core_sell`：
  - 09:24:45 前为预热段：只打启动日志不评估不触发（避免早期撮合价写入 `g.auction_c` 污染确认段快照）。
  - 09:24:45-09:25:30 确认段：首次进入清空 `g.auction_c` + 幂等重读 `_load_expectation()`（命中 9:20 上传当日文件），
    对持仓评估 `_p2e_core_sell_check`；命中即 `_do_sell(..., 'P2E_*', urgent=True)` 跌停地板价 -> 9:25 集合竞价按开盘价撮合。
- 9:30 后 `sell_manager`（1m）/`tick_sell_manager`（3s）共用同一 `_p2e_core_sell_check` 兜底，
  与钩子通过 sold_log 冷却 + 在途守卫双保险去重（不重复下单）。

### 统一判定
- `_p2e_core_sell_check(sec)` 返回 `(hit, note)`：三入口（钩子/1m/3s）共用，防逻辑漂移。
  卖出理由带股票名与竞价幅度，日志 `[P2E] ...` 记录触发。

### 自测
- T14/T69/T69b 更新为幅度门控（-2%）；T112 新增 12 项：A 触发、中位 -1.5% 不触发、基准有效命中、唯一高身位豁免、
  预热段不触发/确认段触发、B 触发、实时反证 CX 不核卖、pending_miss 默认不卖、side=buy 排除、卖出冷却去重、tick 兜底同条件。
- 全量 626 PASS / 0 FAIL；py3.10 编译通过（新增代码无 3.8+ 语法，兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.58`。

## v0.53 持仓监控全覆盖 + exp_day 持久化（2026-10-22）

> 背景：此前持仓卖出只 P1/P2E/P3 与炸板/封单事件走 3s tick，P4 预期三态/P5 评分清仓/P6 评分半仓仅 1m 评估，
> 快速下行期反应滞后。本次把 P4/P5/P6 并入 3s tick，并修复盘中重启后首帧误清空盘中事件状态的问题（exp_day 未持久化）。
- `tick_sell_manager` 追加全覆盖段：P4-one_word（`_exp_one_word` quiet 静默）CS/PS -> 卖、P4-normal（`_eval_intraday`）PS/CS -> 卖、
  P5 评分清仓（score<clear*adj）、P6 评分半仓（score<half*adj 卖半仓整手）；`_hist_1d` 缺失跳过防降级误触发；帧内计数
  `frame_sellscan_limit=8` 上限防帧超预算；1m `sell_manager` 保留兜底双保险。
- `_maybe_roll_day()`：日切统一入口挂 handle_data 首帧。同日重启后 `exp_day` 恢复 -> 首帧不日切（不重复卖出/不丢播种）；跨日触发全量重置。
- `before_trading_start` 同日重启分支 09:25 后 `g.exp_day=_today` 保留盘中状态；`_save_state`/`load_state` 同步 `exp_day`。
- 自测：T110 新增 6 项（roundtrip 恢复 exp_day/break_sold/first_zt/l2_big/wm、跨日重置、`_maybe_roll_day` 同日 False/跨日 True 清空）、
  T111 新增 5 项（P4 一字 CS / P4 普通 CS / P5 清仓 / P6 半仓 + sold_log 冷却去重）。全量 585 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.53`。


## v0.52a 重启补种加大页数（2026-10-22）

> 限制：v0.52 重启补种固定 `l2_tickdir_pages=3`（600 分笔≈回看约 30 分钟），盘中重启只能补回重启前约半小时，
> 上午 9:30-10:30 活跃窗口（尤其竞价至早盘）的已成交大单补不回。
- 拆两档页数：`l2_tickdir_pages=3` 保持（09:25 竞价/09:31 兜底播种，竞价时段分笔总量 <600 已全覆盖，不浪费拉取）；
  新增 `l2_tickdir_pages_restart=10`（约 2000 分笔，回看覆盖 9:30-10:30 活跃窗口至 09:25 竞价）仅盘中重启补种分支使用。
- `_l2_big_seed(secs, pages=None)`：加可选页数参数（默认读 `l2_tickdir_pages`）；重启分支显式传 `pages=int(BLS[l2_tickdir_pages_restart])`。
  分页回读仍走 `start_pos` 翻页（每页 data_count=200），`seen_ts` 集合去重防分页重叠；水印推进/双源防重逻辑不变。
- 成本：`get_tick_direction` 不走 DataHub 帧预算，每页一次批量 RPC（全部候选同时返回），重启分支一次性 10 次 RPC 可接受。
- 自测：T109b 新增（10 页拉取 start_pos=0..1800 / 覆盖至 09:25 竞价且含竞价大单 / 默认播种保持 3 页不含 >3 页大单 / 跨页重叠去重）。
  全量 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.52a`；次日盘中重启后看 `[tickdir]` 探针首笔回看至 09:25 附近。

## v0.52 已成交大单回看播种（2026-10-22）

> 背景：`_tx_big_feed` 仅累计「该股进入 tick 候选集后、每帧最新 200 笔逐笔」里 >=100万 的大单，是纯增量 live-only 口径；
> 09:30 首帧时 09:25 竞价撮合已滚出 200 笔窗口，盘中重启/中途入池前的已成交大单也拿不到。
> v0.52 用 `get_tick_direction`（分时成交行情，含竞价终态，沪深都有、交易模块可用）回看播种，补上已成交大单。
- 播种函数 `_l2_big_seed(secs)`：对候选集（涨停池+自选+持仓+预期）分页拉 `get_tick_direction`（`start_pos` 翻页、`data_count=200`、`l2_tickdir_pages=3` 封顶），
  分笔 `business_balance >= l2_big_amt_min` 且 `time_stamp > 水印` 计入 买/卖/un（方向走 `_tx_dir`，0=卖/1=买）。
- 双源防重：`g.l2_big_wm[sec]`（已覆盖到的最大 business_time，随 `_save_state`/`load_state` 持久化、跨日重置）。
  - live 逐笔：`business_time > wm` 才计入，计入时推进 wm（仅大单行推进，小分笔不推、留给播种补大分笔）；
  - 播种：只补 `time_stamp > wm` 的分笔，调用内用 `seen_ts` 集合去重（防分页重叠）；竞价终态播种后 wm≈09:25，09:30 起 live 无重叠。
- 入口：09:25 竞价终态（auction_pre_confirm）、09:31 兜底（after_open_probe，覆盖其自身 l2_big 重置窗口）、盘中重启（before_trading_start 重启分支，补重启窗口）。
- 探针 `[tickdir]`：每标的打印 首笔/条数/大单分笔/水印（阈值），用于实证分时成交源是否含 09:25 竞价（看首笔是否为 09:25:00 附近）。
- 说明：live 为「单笔逐笔>=100万」、播种为「单分笔>=100万」，两者口径略有差异但净量方向一致；重启补种仅可能在一个分笔窗口（~1s）内与 live 有界重叠，保守不重复计。
- 自测：T109 新增（竞价播种 120+150万 计入/水印=最大分笔时间/方向分布/重复播种幂等/live 跳过已播种时段且新时段计入/重启只补>水印缺口/wm 同日恢复）。
  全量 570 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.52`、09:25 出现 `[tickdir]` 探针（首笔~09:25 即含竞价）、
  盘中重启后 `[l2-big]` 保留重启前累计并补回缺口。

## v0.51 大单净量方向校准 + 跨重启持久化（2026-10-22）

> 实锤：2026-10-22 盘中日志 `[l2] tx_row=[..., 0, ...]`（business_direction=0）——官方字典
> `business_direction` 为 **0=卖、1=买、2=借入、3=出借**（docs/10 §成交方向 + hxquant-API文档一致），
> v0.50 误用 1/2 映射导致实盘 direction=0 全部归 `un`（600698 湖南天雁 `大单买=0 卖=0 净=0 未知=1131669`），
> 大单净量链路午后空转。另 13:33 盘中重启后 `[l2-big]` 全 0 —— `l2_big` 未持久化，当日大单累计清零。
- A) `_tx_dir` 按官方字典校准：0=卖、1=买、2/3=借入/出借->`un`（不计净量）；方向映射提为可配置 `l2_big_dir_map`
-  （默认 `{'0':'sell','1':'buy','2':'un','3':'un'}`，盘中可纠偏不改码）；保留 'B'/'S'/'buy'/'sell'/买/卖 字符串兼容
- B) `l2_big`（含 seen 去重集）+ `l2_dir_dist` 进 `_save_state`/`load_state`：同日盘中重启恢复当日大单累计、跨日重置
- C) `[l2-big]` 探针新增当日 direction 取值分布计数；`after_trading_end` 打 `[l2-dir]` 日结汇总（次日核对 0/1 实盘语义）
- 兜底：`l2_big_dir_enabled=False` 回退 v0.47 全大单口径（若方向核验失败先启用，保证链路不空转）
- 自测：T107 断言改 0=卖/1=买/2/3 不计净量 + T108 新增（实盘 0/1 识别/分布计数/同日恢复/跨日重置）。
  全量 563 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.51` 与 `[l2-big]` 净量不再全未知、
  重启后 `l2_big` 不归零。

## v0.50 大单净量口径（2026-10-22）

> L2 大单占比语义修正：净量 =（大单买 - 大单卖）/ 实时成交额 >= 10% 才加分/封单豁免。
> `_tx_big_feed` 按 `business_direction` 分计 buy/sell/un（多态解析：数值 1/2、'B'/'buy'/'买'、'S'/'sell'/'卖'），
> 方向未知/缺失的成交不计入净量（保守不误判）；`_l2_big_ratio` 改净量口径，net<=0 不授分；
> `l2_big_dir_enabled=False` 可回退 v0.47 全大单口径；`[l2-big]` 探针输出 买/卖/净/占比/未知，
> 单标的 direction 全部未识别时打一次校准告警。
- 自测：T101 重写净量口径 + T104 补 direction + T107 新增（卖>买负净不授分/方向未知不计/字段缺失降级/dir_enabled=False 回退/多态解析）。
  全量 556 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.50` 与 `[l2-big] 大单买=.. 卖=.. 净=..` 探针。

## v0.49 炸板应对收紧 + 回封打板（2026-10-22）

> A) 炸板卖出改买N档限价：`_order_limit` 新增 `sell_break` 模式——取 L2 `bid_grp[break_sell_bid_level(3)]` 档价，
>    缺失回退现价；`break_sell_floor_ratio(0.95)` 下限保护（防炸板瞬间买3被砸深时过度杀价）。
> B) 唯一身位连板封单容忍 + 二次炸板减半：唯一身位判定=`_unique_stand`（复盘 `unique_high` 或动态唯一+跟风确认）；
>    seal_low 阈值唯一身位用 `seal_fail_ratio_unique(0.25)`（默认 0.333）；`break_cnt` 计数——首次炸板全卖，
>    二次炸板且唯一身位（后排助攻/人气龙头）减半 `break2_half_ratio(0.5)`，非唯一维持清仓语义；
>    `break` 支持回封复位（`last>=涨停价x0.998` 且封单达标 -> break=False，break_cnt/reboard_ts 保留）。
> C) 炸板减去涨停分：`_static_bonus` 的 `touched_limit_up_early(+6)` 加 `not _broken_now(sec)` 条件，
>    炸板即取消，回封复位后恢复。
> D) 回封打板 `_try_reboard_buy`：前排（板块强度前三）首板/2板 10:00 前炸板后回封，且 L2 大单占比>=10%
>    （`reboard_l2_big_min`）-> 涨停价打板参与；封单下限 `reboard_seal_min(50000)`；每日全局 1 次
>    （`g.reboard_fired`，跨重启持久化），只打第一个回封的前排候选；非持仓/非一字/非中位股规避。
- 自测：T105（买3限价+下限/扣涨停分/唯一身位/二次炸板减半）+ T106（回封打板触发/大单不足/已fired）+ T24 mock 签名适配。
  全量 548 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.49` 与 `[firstzt] BREAK#N / 回封 / TICK_break2_half_sell` 日志。
