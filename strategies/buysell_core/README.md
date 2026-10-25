# buysell_core - 版本记录

> 变更记录统一存本文件；strategy.py 文件头仅保留「当前版本 / 部署核对」。

## 当前版本
- 当前版本：v0.71（2026-10-25）

## 部署核对
- 部署核对：日志首行 `buysell_core init version=v0.71 ...`（init 打印 STRATEGY_VERSION）
- 每次更新版本号后重传 strategy.py 云端，以日志首行 `buysell_core init version=..` 核对。

## 设计依据
- buysell_core —— Ptrade 托管「高可靠买卖子集」迁移骨架（v0.4）
- 依据：docs/16 + docs/18；AXquant 真实参数取自 D:/PROJ/AXquant/axquant/strategy
- (decision/sell.py, decision/__init__.py, scorer/*, btree/builder.py ma_pullback)
- v0.4 把 score_now 做成真实版（结构等价，数据用 Ptrade 内置接口近似）：
- 分 = clamp(base40 + 静态加分 - 静态扣分 + 攻击加分 - VWAP扣分 + 外内盘, 0..92)
- 兼容国金：run_daily(context,func)+回调单参；log 先 % 拼单字符串；禁用 os。
- 只读安全：DO_ORDER=False 不发真单，仅记 [may-order]。
- v0.15 对齐 AXquant 买卖逻辑核心：1) 一字板封单超预期不参考排单（封死涨停不排队买入）；
- 2) 竞价核卖 P2E：预期已确认 miss/degraded -> 清仓；3) 弹性追高买入价 300/688 前收*1.10 上限（打板豁免）。
- v0.16 节奏：新增 09:25 auction_pre_confirm（重读9:15前上传预期文件+竞价终态初步确认超预期->观察，不买）+09:31兜底重读。
- v0.17 供方数据健壮性：A)负基昨日开盘也判高开；B)预期基准缺失/<=0不超预期不误弃(防过触发)；云端1d历史折算昨日开盘与达标基准兜底；C)供方CSV缺失字段输出空串。
- v0.28 涨停池合成过滤 ST（消费 zt_lianban 的 is_st 字段，对齐 AXquant 复盘口径）；盘前一键脚本 run_one_click_premarket.py（生成+校验+上传勾选，docs/39）。
- v0.29 情绪冰点→回暖链（docs/40）：本地生成 sentiment CSV（T 日冰点+连续冰点天数）盘前读入；红盘比恢复判回暖，冰点越久恢复阈值越低（回暖概率增加）。
- v0.30 情绪仓位上限（docs/40 闭环）：连续回暖增加分歧概率；冰点日最大总仓位 40%，回暖日 80%（连续回暖 N 日起递减，分歧保护），买入路径统一拦截。
- v0.14 预期买入两阶段（T+1，side=buy 且预期超预期）：
- 1) 竞价终态初步确认「竞价超预期」-> 观察（不买）；2) 分时确认超预期(两分钟上攻 或 一分钟冲涨停,且不破VWAP) -> 执行买入。
- tick_data 3s 事件触发 + 一次触发持久化去重(exp_fired) + 独立 EXPECT_ORDER 实盘门控。

## 版本记录（新→旧）

### v0.71（2026-10-25）预期买入方向裁判：进攻高位/切低位统一消费
- 新增 `_exp_direction_eval`：基于 `high_continue/high_diverg/rotate_low/ice_wait/watch`、动态题材龙头、新题材发酵前排与身位档，输出 `attack_high / attack_low / neutral / avoid`。
- `attack_high/attack_low` 只增加候选排序分 `0.8`；`avoid` 直接不参与。技术三态 `CX/CM/PM/CS` 和仓位比例完全不变，方向不能把 `PM/CS` 升级成买入。
- `hot` 题材只允许最强前排，后排直接跳过；`high_continue` 允许原题材唯一存活龙头或发酵前排；`rotate_low` 默认低位，但允许原题材当前唯一存活龙头例外。
- 正式预期、涨停池、自选股统一进入同一方向/评分队列，来源不再天然获得执行优先级；10:00 后继续使用 `0.5` 参与缩放，不归零。
- 新增 `[exp-dir]` 日志和 10:00 方向计数；订单注释输出 `direction/score/size_mult=1.0/reason`。旧 `_lb_senti_direction_bonus` 改为调用新裁判，避免重复计分。
- 健壮性：`g.first_zt` 的 4 处读取统一改为 `(g.first_zt or {})` 兜底（与既有口径一致），首触记录/状态未就绪时不再抛 `AttributeError`。
- 验证：`tests/test_buysell_core_exp_direction.py` 覆盖 14 个场景，包括高位/低位进攻、静态唯一龙头灵敏度、hot 后排否决、rotate_low 龙头例外、PM 不升级、统一队列、10:00 冻结/缩放和仓位不变；selftest T92o 断言对齐 v0.71 方向裁决（neutral/avoid/attack_high + 禁止重复计分），全量 741 PASS。

### v0.70（2026-10-23）5D低吸改为生命周期次低价进入动态 MA5 ±2% 带
- 背景：v0.69 只在单帧现价精确触及动态 MA5 时触发，单次插针容易误判，也容易因一分钟采样错过合理回踩。
- 生命周期：每个交易日独立维护本轮观察到的两个最低价格；`low2` 为其中较高者，即“次低价”。状态按日重置并随同日重启恢复。
- 触发：以次低价作为今日临时收盘价计算动态 MA5；当 `abs(low2-ma5)/ma5 <= 2%` 时，视为次低价触及 MA5 上下 2% 带。
- 其余口径不变：`CORE`（T-1 连板>=3）、`score>=50`、10% 仓位，L2 净大单达标仍作为 +5 分增强项。
- 首次性：次低价首次进入 MA5 带后评估一次；若评分或红盘门不达标，当日不再追补，次日重新解锁。评分数据未就绪不消耗首触。
- 回退：`ma5_second_low_enabled=False` 可回退到现价与动态 MA5 的距离判断；`ma5_touch_band` 默认 0.02。
- 日志：买入注释同时输出 `low2`、`ma5`、`ma5ref`、实际偏离 `band`、四日基准 `ma5b4` 和 L2 净大单占比，便于盘中核对。
- 验证：T26d/T26d2/T26e/T26f/T30/T56/T72 覆盖次低价形成、2% 边界、评分边界、10% 仓位、当日去重、跨日重置与重启恢复。

### v0.69（2026-10-23）5D低吸口径修正：动态 MA5 + CORE 首次触线 + score>=50 + 10%
- 问题：603278 盘中日志 `ma5=11.00` 为盘前缓存的昨日 5 日均值；今日实时价 15.96 对应动态 MA5
  `(10.90+11.99+13.19+14.51+15.96)/5=13.31`，原实现未随现价更新。
- 计算：`_ma5_base4` 取最近 4 个**已完成交易日**收盘均值；`_ensure_ma5=(base4×4+当前价)/5`。
  若行情源日线末行为今日未完成 K 线，按索引日期识别并剔除；否则按 get_price 契约默认不含今日。
- 触发：`CORE`（T-1 连板>=3）且无 BS 仍可触发；当日首次触线；现价精确触及动态 MA5（容差 1.02→1.00）；
  `ma5_buy_score_min=50`；显式 `ma5_buy_ratio=0.10`。`ma5_require_bs` 默认 False。
- 首触：按交易日去重；首个可评估触线点若评分不足则不追补，次日自动重置。`ma5_first_5d=False` 为默认，
  置 True 可回退“五日内首次回踩”的旧口径。状态随同日重启恢复。
- L2：净大单占比仍由 `score_now -> _l2_big_bonus_pts` 自动加分，不设硬门；日志同时输出动态 MA5、四日基准和 L2 占比。
- 边界：不能用收盘后抬高的 MA5 反推早盘触线；信号必须在当时刻满足 `price <= 动态MA5`。603278 于 10-23
  09:31 附近最低 13.23 时动态 MA5 约 12.76，价格高于均线，未形成首次触线信号。
- 验证：T26d/T26e/T30/T72 更新，新增“不含今日/末行为今日剔除/同帧价格变化/603278=13.31”断言；全量回归见提交说明。
- 该版本未完成云端重传，已被 v0.70 取代；部署以 `version=v0.70` 为准。

### v0.68（2026-10-23）评分/竞价/预期文件三重数据就绪加固（A 重启评分失真 / B 首帧误弃 / C 盘中文件收缩，docs/33）
> 实盘 10-23 观测：①盘中重启(10:19 v0.66)后首帧行情/板块未就绪被当 0.0 打分（三峡新材 48→70、海洋王 40→65，
> chg=0.0% board=0.0 只剩加分虚高）；②09:30:01-02 首帧缺前收致 `_auction_change` 写死 (day,0.0) 毒缓存，
> 大业/海洋王/安乃达/赛福天 4 个唯一预判 `miss=auction_not_met(0.0%) -> skip` 当天永久误弃（exp_fired 不可恢复）；
> ③`expectation_latest.csv` 盘中 15→5 全量替换丢候选。
- A 评分数据就绪门：`_spot_ready`（现价+前收齐备）+ `_board_strength_info`（板块有归属但无有效涨跌样本=不可测，
  未映射=中性放行）；未就绪 `score_now` 返回 None，买入入口（ma_pullback/core_buy）跳过、卖出 P5/P6 跳过防误卖、
  `dump_scores` 打 `data_na`；`[score-na]` 60s/票节流日志。
- B 竞价未就绪守卫：`_auction_change` 缺前收/无价时返回 0.0 且不写缓存（下帧重算，根治 (day,0.0) 毒缓存）；
  新增 `_auction_ready`（缓存命中或 前收+开盘齐备），`_exp_rt_status` 超预期路径未就绪 -> `PM await_intraday_confirm`
  （不再误判 CS 永久放弃）；首帧资金未就绪 `_avail_cash<=0` 静默跳过（不刷 WARNING，下帧自然重试）。
- C 预期文件盘中替换保护：`_load_expectation(merge=True)` 盘中重读（09:25/09:31/P2E 钩子）逐 code 合并——
  新文件胜出冲突、旧有缺失保留，防 15→5 收缩丢候选；日期守卫（date/trading_date/generated_at 列非今日拒绝重载）；
  差异日志 `expectation file merged old=.. new=.. total=.. keep_old=..`。
- 上传契约：定时上传任务需 **9:15 前完成上传**（09:25 竞价终态重读命中当日文件）。
- 验证：T120-T127 新增 8 例（评分就绪门/板块不可用/不写毒缓存/未就绪不误弃/资金静默/merge 不丢/日期拒绝/差异日志）。
  全量 728 PASS / 0 FAIL；py3.13 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.68`、重启首帧 `[score-na]`、
  09:30 不再 `miss=auction_not_met(0.0%)`、09:25 `expectation file merged`。

### v0.67（2026-10-23）L2 大单链路补齐：盘中入池补播种 + 探针节流重打 + 批量缺票兜底（docs/33）
- 实盘 10-23 观测：盘中新入池触板票（统一股份、奇精机械、登康口腔、榕基软件、天娱数科、达实智能等）不在 09:25/09:31 播种列表，
  首次进入近涨停目标集时 `[l2-big]` 首帧打印 0/0；同帧批量逐笔偶有部分票缺行/近空（兆威/华阳有数据而登康/大港近空）。
- A) 盘中入池补播种 `_l2_big_seed_onjoin`：tick_data 构建 `_near` 后对未播种票按 `l2_big_seed_onjoin_interval_sec`(60s)
  节流调 `_l2_big_seed(pages=l2_tickdir_pages_onjoin=5)` 回看历史大单；与既有水印共用，双源不重复，首帧即有累计。
- B) `[l2-big]` 探针分钟节流重打：首帧立即，之后按 `l2_big_log_sec`(300s) 间隔重复打印同票累计变化；direction 全部未识别告警仍只在首帧。
- C) 批量逐笔缺票兜底：`_tx_pull_raw` 批量拉取后统计缺行票，帧预算内（`frame_tx_limit` 1->2、`l2_tx_fallback_cap=5`）
  逐只 `get_individual_transaction([c])` 补回并合并 fields；打 `[tx-pull] req=.. got=.. missing=.. (fallback=..)`，
  兜底结果并入本帧 raw，下帧新 token 仍可重试。
- 验证：T117（入池播种历史大单进 acc + 60s 节流 + 已播种票过滤）+ T118（首帧立即/间隔内不重打/超时重打+时间戳更新）
  + T119（批量缺票单票补回、fields 合并、missing 日志）+ T51 契约更新（批量一次拉取+缺票单票兜底、同帧二次消费不重复拉）。
  全量 700 PASS / 0 FAIL；py3.13 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.67`、盘中新票 `[tickdir]` 入池播种、
  同票 `[l2-big]` 多时间点、`[tx-pull] .. missing=.. (fallback=..)` 与收盘 `[l2-big-sum]`。

### v0.66（2026-10-23）L2 大单占比分母打通（docs/33）
- 实盘 10-23 发现 `[l2-big]` 占比全天恒 `-1.00%`：`_l2_big_ratio` 分母取 `turnover`/`amount`，云端
  `get_snapshot` 无 `turnover`（仅 `turnover_ratio` 换手率）、`amount` 股票恒 0；权威字段 `business_balance`=总成交额（元）。
- 新增 `_l2_big_turnover(sec)` 统一分母：`business_balance` 优先 -> `business_amount`(总成交量股) x `wavg_px`/`last_px`
  兜底 -> `turnover`/`amount` 旧环境兼容；`_l2_big_ratio` 与首板记录 `g.first_zt['amt']` 同步改用。
- `[l2-big]` 探针补打 `分母=`；日志 `分布=` 明确为 `全局分布=`（`g.l2_dir_dist` 全市场共用）。
- 买入/卖出大单取得强化：净大单=买入大单-卖出大单，方向来自逐笔 `business_direction`（0=卖/1=买/2借入/3出借不计）；
  `l2_big` 增 `bn/sn/un_n` 大单笔数分方向计数，`[l2-big]` 带笔数，`after_trading_end` 增 `[l2-big-sum]` 按票日结买/卖/净/笔数。
- 验证：T115（分母优先级）+ T116（逐笔/播种双源 buy/sell 金额与笔数分计、净大单、日结排序）新增；
  全量 690 PASS / 0 FAIL。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.66` 与 `[l2-big] .. 占比=..% 分母=..` 不再全 -1。

### v0.65（2026-10-23）连板盘中情绪动态：竞价终态 -> 盘中确认 -> 10:00 冻结（docs/43）
- 分档：low=首板/一进二（T-1 `board_cnt<=1` 或今日新首板）；mid=中高位 2-5 板；high=高标（>=6 或权威 `unique_high`）。
- 竞价终态 `_lb_senti_auction`（09:25/09:31）：中高位高开/绿开/一字率 + 低位高开率；纯 `g.auction_c`/spot 读取，零行情 API。
- 盘中确认 `_lb_senti_mid`（docs/43）：中高位晋级率（`_today_zt` 存活/触板）、炸板率（`first_zt.break`）、封单留存、
  低位承接（`_dyn_theme_ferment` 助攻/临时题材）、红盘比 `_market_red_ratio`；10:00 前 15s 缓存、10:00 后降频 60s（不归零）。
- 状态机：`high_continue` 高位延续 / `high_diverg` 高位分歧(兑现预警) / `rotate_low` 切低位新方向首板 / `ice_wait` 冰点观望 / `watch` 样本不足；
  风险升级需同候选持续 `lb_senti_hysteresis_sec`(60s) 二次确认（滞回防单帧抖动），回暖直接切换。
- 消费落点：`_pool_exp_priority` 参与方向加权（`_lb_senti_direction_bonus` × `_lb_senti_participate_scale`）；
  `_attempt_expected_buy` 参与方向闸门 `_lb_senti_buy_gate`（切低位/冰点只放行低位首板与新方向，10:00 后缩放不归零）；
  P8 `_lb_senti_cut_hold` 中高位兑现指导（高位分歧/切低位 + 中位股晋级失败 -> 减半兑现，`cut_seen` 去重），1m `sell_manager` 与 3s `tick_sell_manager` 双链。
- 10:00 定时 `lb_senti_t100_freeze` 冻结快照并持久化（`g.lb_senti.t100`），随 `_save_state`/`load_state` 同日恢复、跨日清空。
- 验证：新增 T92n/o/p 共 12 项（竞价终态统计、分档、盘中状态机+滞回+切低位+闸门+方向加权、10:00 冻结+降频缩放+P8 兑现+P8 去重+持久化恢复）。
  全量 678 PASS / 0 FAIL；PT3.7 + veighna 双 py_compile；T94 版本三处同步通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.65` 与 `[lb-senti] ... phase=..` 日志。

### v0.64（2026-10-23）订单系统闭环 + 资金实时（F1-F5，docs/33）
- F1 `place_order`/`place_expected_order` 返回 bool：7 个买入信号点（动态扫板/低吸/core_buy/首板/回封/弹性套利/弹性top）改 `if place_order(...):` 成功才记 `daily.bought`，静默失败不再占买名额。
- F2 `on_order_response` 重写为 list[dict] 主推（兼容单对象）：PTrade 状态码映射（8已成/5已撤/6废单/7部成/V确认），buy 终态按成交额释放 `buy_commit`，REJECTED/CANCELLED 释放 `daily.bought`+`exp_fired`（buy_log 冷却保留防风暴）。
- F3 `g.pending` + `g.buy_commit` 纳入 `_save_state`/`load_state`（仅同日分支恢复，跨日清空）；`before_trading_start` 挂 `_reconcile_pending()` 重启对账（get_open_orders 重建在途委托）。
- F4 `place_expected_order` pending 补齐 status/filled/ts 三字段。
- F5 `on_trade_response` 重写为 list[dict]：sell 成交回填 filled+sold_log+daily.sold，buy 成交按成交额释放承诺，撤单主推(real_type=2)/废单跳过，成交量取绝对值。
- 资金实时（用户补充）：`_avail_cash = portfolio.cash - buy_commit`（在途买单承诺，防 6s 资金同步滞后超配），`_buy_pos_ok`/`_calc_buy_qty`/`place_order`/`place_expected_order` 统一走 `_avail_cash`。
- 验证：全量 666 PASS / 0 FAIL（649 + F1-F5 新增 17）；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.64`。

### v0.63（2026-10-23）死代码清理（未引用函数 / BLS 死键 / ATK 死键）
- 删除生产未引用函数：`_set_bs`（+ `g.bs_cache` 只写不读）、`_elastic_ask1`（已由 `_order_limit('chase')` 替代）、
  `_tx_first_zt_ms`（v0.22 起走 DataHub.tx_zt_batch 批量，兼容入口无生产消费）；同步删 selftest T42b/T46。
- 删除 BLS 死键 6 个：`auction_buy_score_min`/`expectation_base`/`market_red_enabled`/`first_board_bids_min`/`score_max`/`score_min`；
  ATK 死键 `elastic_threshold`（仅 `main_threshold` 被 `_attack_bonus` 消费）。
- 保留项：引擎入口（initialize/handle_data/tick_data/before_trading_start/after_trading_end/on_*_response）由 Ptrade 按名调用；
  `frame_*` 预算键经 `_source_limit` 动态拼接消费，非死键；BONUS/PENALTY 全键消费。
- 验证：全量 649 PASS / 0 FAIL（原 655 - 死代码测试 6）；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.63`。

### v0.62（2026-10-23）首板/回封买入门封单下限同步 20 万
- `first_board_seal_min` 50000 -> 200000（首板打板最小封单额，3461）+ `reboard_seal_min` 50000 -> 200000
  （回封封单下限，3523，与大单加持二选一）；与 v0.61 `firstzt_min_seal` 上报侧同档，三处门槛口径一致。
- 验证：全量 655 PASS / 0 FAIL；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.62`。

### v0.61（2026-10-23）首此涨停封单门槛上调（firstzt_min_seal 5万->20万）
- `firstzt_min_seal` 50000 -> 200000（元）：首此涨停上报/回封确认的最小封单额，过滤小封单假封；
  仅影响 first_zt 触板跟踪与快照兜底（5366/5383）；首板/回封买侧于 v0.62 一并上调至 20 万。
- 验证：全量 655 PASS / 0 FAIL；py3.10 编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.61`。

### v0.60（2026-10-22）板块口径统一：全链路 THS 概念文件（docs/33）
- 统一口径开关 `board_concept_unified=True`：残留 5 处 API 双轨全切文件 THS 概念（`boards_latest.csv`），关闭即回退旧 API 双轨。
- `_board_rank_top3`/`_board_rank_top3_set` 概念化：候选源统一 `_elastic_top_cand_src`（池∪T-1涨停名单）共享 `csnap_led`
  合并快照账本（首板/回封/弹性套利板块目标、tick 扩板）。
- `_board_strength` 概念化：所属概念板块强度取最强（`_board_strength_by_concept`/`_concept_strong_board`）——打分板块分、
  板块走弱扣分、持仓 P7b 板块强/弱、地位评估 board 分类全走概念口径。
- `_red_ratio` 概念化：最强概念板块成员红盘比；`_elastic_yizi_scan`/`_elastic_in_strong_board` 一字板归属切 `_concept_boards_of`。
- 灵敏度保持：10:00 前 3s 同频；`_concept_snap_for` 账本新鲜零额外 RPC、否则单板预算缓存（budget=board 同旧链节奏）；共享账本同源 key 零额外批量。
- 验证：T114 新增 11 项（最强聚合/排名门控/红盘比/elastic归属/共享账本/开关关闭/未加载回退）。全量 655 PASS / 0 FAIL；py3.10 编译通过（兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.60` 与 `[boards] loaded ... unified=True`。

### v0.59（2026-10-22）持仓卖出闭环：地位评估 + P7a/P7b/P7c（docs/33）
- 持仓地位评估 `_hold_stand`（15s 节流缓存）：role（leader/follower/mid/outside）+ active（主动/跟风/中性）+
  board（强/平/弱）；评分仅持仓消费（leader+3/follower-1/mid-3/active+3/跟风-3/板块弱-3），日志 `[hold] <股名> role=.. active=.. board=.. pts=..`（60s/股节流）。
- P7a 连板放量不封板：持仓 + T-1 `board_cnt>=2` + 今日量>=昨日量×`p7a_vol_ratio`(1.10) + 未封板 -> `P7a_vol_break`；
  唯一身位降级减半（`p7a_half_ratio`=0.5），否则清仓；现价限价非地板价；`[vol]` 探针（每日一次）核对量单位。
- P7b 跟风拉升不封板：持仓 + `role∈(follower,outside)` + 板块强（`board_strength>=p7b_board_min`=1.0 或题材存活龙头封板）
  + 1m surge>=`p7b_surge_min`(1.5) + 未封板 -> `P7b_follow_break` 减半。
- P7c 首板次日不主动冲板 -> 冲高分批清仓：T-1 `board_cnt==1` + 09:30-10:00 窗口 `active≠主动` -> 标记 `p7c_price`；
  现价>=标记价×(1+`p7c_surge_min`%) -> 每 `p7c_batch_cold_secs`(10s) 卖一批（2×50%，`cool=False` 批次自控替代 30s 通用冷却）；
  回封取消标记；破 VWAP 由 P4 兜底。
- 去重/持久化：`g.p7a_sold`/`g.p7b_sold`/`g.p7c_part`/`g.p7c_sold` 随 `_save_state`/`load_state` 跨重启持久化。
- 接入：tick 卖出链 P3 后 P4 前（3s）+ 1m `sell_manager` 同条件兜底；BLS 新增 `p7_sell_enabled`/`p7a_*`/`p7b_*`/`p7c_*`/`hold_stand_*`。
- 验证：T113 新增 19 项（P7a 清仓/唯一减半/未放量/已封板/仅连板、P7b 减半/leader/surge不足/板块弱、P7c 标记/第一批/冷却内/第二批/回封取消/主动不标/窗口外、
  地位评估 leader/mid、tick 链 P7a 触发）。全量 644 PASS / 0 FAIL；py3.10 编译通过（新增代码无 3.8+ 语法，兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.59`。

### v0.58（2026-10-22）P2E 竞价核卖（同题材中位崩塌传导 + 自身大不及；docs/33）
- 触发 A（题材传导）：持仓 `_zt_themes_of` 非空 -> 所属题材存在中位股（T-1 `board_cnt` 2-5）-> 中位股最弱竞价
  `<= p2e_theme_drop_min`（-2%，用户从 -5 修正）且 9:24:45 自身确认（基准有效：竞价<基准；基准无效：绿开<0）。
- 触发 B（自身大不及）：文件 `expected_status ∈ (confirmed_miss, degraded)`（pending_miss 默认不卖）+ 自身竞价
  `<= p2e_auction_drop_min`（-2%）。v0.33 反证守卫保留（实时 `_confirm_expected == CX` 不核卖）。
- 豁免：唯一高身位（`_unique_stand`）不核卖，交盘中监控；范围仅持仓 + `_sellable>0` + 非在途 +
  sold_log 冷却外 + 条目 `side ∈ (sell, hold)`。
- 时点：新增 `run_interval(seconds=3, interval_timer_ranges='09:15-09:25')` 钩子 `p2e_auction_core_sell`：
  09:24:45 前预热只日志不触发（避免早期撮合价污染 `g.auction_c`）；09:24:45-09:25:30 确认段评估触发
  （先 `_load_expectation()` 命中 9:20 上传当日文件 + 刷新竞价缓存）；9:30 后 `sell_manager`/`tick_sell_manager`
  同 `_p2e_core_sell_check` 兜底双保险（sold_log 冷却 + 在途守卫去重）。卖出走 `_do_sell(..., urgent=True)` 跌停地板价 -> 9:25 撮合。
- 配置：BLS `p2e_sell_enabled / p2e_theme_sell_enabled / p2e_theme_drop_min / p2e_auction_drop_min / p2e_confirm_at`。
- 验证：T14/T69/T69b 更新（幅度门控 -2%）；T112 新增 12 项（A 触发/-1.5% 不触发/基准有效/唯一豁免/预热不触发-确认段触发/B 触发/
  反证/pending_miss/side=buy 排除/冷却去重/tick 兜底）。全量 626 PASS / 0 FAIL；py3.10 编译通过（新增代码无 3.8+ 语法，兼容 PT3.7）。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `buysell_core init version=v0.58`。

### v0.57（2026-10-22）新题材发酵审查修复（docs/42）
- 修复1（阻塞）：`_dyn_theme_ferment` 不再调 `_is_first_board`（`c not in zt` 即首板），
  3s tick 决策路径零行情 API；`_new_themes_of` 在 boards 文件缺失/为空时直接返回 []，不回落 `get_stock_blocks`。
- 修复3（冷缓存竞态）：`_ferment_front_gate` 对发酵缓存缺失补齐——存量题材有存活龙头 -> 助攻不放行，
  临时题材首个成员即前排放行；仅题材完全未知才回退 None。
- 修复4（死配置）：`zt_theme_ferment_seal_min` 生效——前排在存活新成员中优先取封单达标的最早触板者；
  `first_seal<=0`（无 L2）不拦截；全低于下限不转授但输出 `seal_ok=False`。
- 修复5（碎片化）：`_merge_temp_themes` 按概念成员/今日新首板交集 union-find 合并 `THS:*` 桶并按代码去重；
  无概念映射新首板计数打 `[ferment] unmapped=N` 日志。
- 验证：新增 T92j/T92k/T92l/T92m 共 8 项全过；全量回归 ALL DONE / 0 FAIL；PT3.7 + veighna 双 py_compile；
  T94 版本三处同步通过。

### v0.56（2026-10-22）盘中新题材发酵识别/消费（docs/42）
- 识别：`_dyn_theme_ferment`（15s 缓存）以 `g.first_zt` 首触为源，筛「今日新首板（T-1 不在池）+ 仍封板」；
  `_new_themes_of` 用 THS 概念与 T-1 题材桶成员交集桥接（无交集建 `THS:` 临时桶）；
  窗内助攻家数 >= `zt_theme_ferment_assist_min` 且时间跨度 <= 窗口 -> confirmed，>= hot_assist -> hot。
- 前排：存量题材动态龙头（`_dyn_theme_status`）仍为前排；全新题材取最早触板存活者；龙头炸板可转授。
- 消费：`_ferment_front_gate` 接入 `_try_first_board_buy`（助攻非前排不抢首板）；
  `_dyn_theme_leader` / `_zt_theme_sort_bonus` 扩展（确认题材成员 + 前排加分，仅排序不放大追高）。
- 开关：BLS `zt_theme_ferment_enabled / window_min / assist_min / hot_assist / front_bonus / sort_bonus / seal_min`。
- 验证：T92i 13 项全过；全量 ALL DONE / 0 FAIL；PT3.7 + veighna 双 py_compile 通过。

### v0.55（2026-10-22）zt_lianban 盘中题材身位/跟风/强度动态消费（docs/41）
- 静态锚：`_build_zt_theme_index` 按 `themes` 全量列表建题材索引（theme -> members/max_board/count/rank），
  交叉题材不漏归；`_load_zt_lianban` 加载时同步建立。
- 动态修正：`_dyn_theme_status`（15s 缓存）以今日续板/动态身位重算每题材存活最高身位、唯一龙头、
  存活跟风与实时家数；龙头炸板后最高身位只在存活者中取，唯一性可转授。
- 决策消费：`_mid_board_avoid` 中位带（T-1 2-5 板）内，静态 `unique_high` 或盘中动态题材龙头放行；
  `_pool_exp_priority` 增加题材动态龙头 + 梯队名次排序加分（仅排序、不放大追高）。
- 开关：BLS `zt_theme_dyn_enabled / zt_theme_dyn_cache_sec / zt_theme_leader_sort_bonus / zt_theme_rank_bonus_step`。

### v0.54（2026-10-22）zt_lianban 题材/概念梯队列消费对齐（docs/33）
- 消费对齐：`_load_zt_lianban` 解析新增题材列 `theme/theme_count/theme_max_board/theme_rank/themes`
  （AXquant theme.buckets 同源），缺列容错默认值；`g.zt_theme_authoritative` 标记、加载日志输出 `themed=N`。
- 唯一身位兜底：文件缺 `unique_high` 列时，`_annotate_zt_uniqueness` 优先按 `theme` 分组
  （对齐 AXquant 题材口径），缺题材列才回退涨停原因首 token。

### v0.53（2026-10-22）持仓监控全覆盖 + exp_day 持久化（docs/33）
- 持仓监控全覆盖：P4 预期三态 / P5 评分清仓 / P6 评分半仓并入 3s tick（`tick_sell_manager`），1m `sell_manager` 保留兜底；
  帧内评分卖出持仓数上限 `frame_sellscan_limit=8`（持仓一般<=5 天然不超）；`_hist_1d` 缺失时跳过 P5/P6 防降级误触发。
- 日切统一入口 `_maybe_roll_day()`：日切逻辑提取并挂进 `handle_data` 首帧；同日重启后 `exp_day` 已持久化/恢复 ->
  首帧不再清空盘中事件状态（break_sold/seal_sold/first_zt/seal_base/one_word_open/l2_big/l2_big_wm 等，防重复卖出/播种丢失），
  跨日仍正常触发全量重置。
- `before_trading_start` 同日重启分支：09:25 后保留盘中状态（`g.exp_day = _today`），09:31 前仍走重建兜底。
- `_exp_one_word(sec, quiet=False)` 加 quiet 参数：tick 3s 路径静默预热，防刷屏。
- `_save_state` 增 `exp_day`；`load_state` 同日恢复、跨日置 None。
- 自测：T110（roundtrip 同日恢复 exp_day/break_sold/first_zt/l2_big/wm + 跨日重置 + `_maybe_roll_day` 双分支）新增 6 项、
  T111（P4 一字预期 CS / P4 普通分时 CS / P5 清仓 / P6 半仓 tick 全覆盖 + sold_log 冷却去重）新增 5 项；
  全量 585 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.53`。

### v0.52a（2026-10-22）重启补种加大页数（docs/33）
- 盘中重启补种页数拆两档：`l2_tickdir_pages=3`（09:25 竞价/09:31 兜底播种保持，竞价时段 600 分笔已全覆盖、不浪费拉取）；
  新增 `l2_tickdir_pages_restart=10`（约 2000 分笔，覆盖 9:30-10:30 活跃窗口回看至 09:25 竞价）仅重启分支使用。
- `_l2_big_seed(secs, pages=None)` 加可选页数参数（默认读 `l2_tickdir_pages`）；重启分支显式传 10 页。
- 自测：T109b 新增（10 页拉取 start_pos=0..1800/覆盖至 09:25 竞价含竞价大单/默认播种保持 3 页不含 >3 页大单/跨页重叠去重）。
  全量 PASS / 0 FAIL；双编译通过。
- 待重传：strategies/buysell_core/strategy.py，核对日志首行 `version=v0.52a`。

### v0.52（2026-10-22）已成交大单回看播种（docs/33）
- 新增 `_l2_big_seed`：用 `get_tick_direction`（分时成交行情，含竞价终态 09:25 与重启前已成交）对候选集回看播种，
  分笔 `business_balance>=100万` 计入 买/卖/un；水印 `l2_big_wm[sec]` 与 live 逐笔双源防重（live 按 business_time>水印 跳过已覆盖时段）
- 播种入口：09:25 竞价终态（auction_pre_confirm）+ 09:31 兜底（after_open_probe，覆盖重置窗口）+ 盘中重启回看补种（防重启窗口已成交大单丢失）
- 成本控制：`l2_tickdir_pages=3` 页回看（每页 data_count=200），仅对近涨停目标集播种；`[tickdir]` 探针输出 首笔/条数/大单分笔/水印（实证是否含 09:25 竞价）
- `l2_big_wm` 随 `_save_state`/`load_state` 持久化（同日恢复、跨日重置）；水印只在大单行推进（小分笔不推，留待播种补大分笔）
- 自测：T109 新增（竞价播种/水印防重/幂等/live 跳过已播种时段/重启补缺口/wm 恢复）。全量 570 PASS / 0 FAIL；双编译通过。

### v0.51（2026-10-22）大单净量方向校准 + 跨重启持久化（docs/33）
- `_tx_dir` 方向映射按 PTrade 官方字典校准：0=卖、1=买、2=借入/3=出借->不计净量（v0.50 误用 1/2，实盘 direction=0 全部归 un、净量空转）
- 方向映射提为可配置 `l2_big_dir_map`（默认 {'0':'sell','1':'buy','2':'un','3':'un'}），保留 'B'/'S'/'buy'/'sell'/买/卖 字符串兼容
- `[l2-big]` 探针新增当日 direction 取值分布计数；`after_trading_end` 打 `[l2-dir]` 日结汇总（次日核对 0/1 实盘语义）
- `l2_big`（含 seen 去重集）与 `l2_dir_dist` 进 `_save_state`/`load_state`：同日盘中重启恢复当日大单累计、跨日重置（修 13:33 重启后大单清零）
- 自测：T107 断言改 0=卖/1=买/2/3 不计净量 + T108 新增（实盘 0/1 识别+分布计数+同日恢复/跨日重置）。全量 563 PASS / 0 FAIL；双编译通过。

### v0.50（2026-10-22）大单净量口径（docs/33）
- L2 大单占比语义修正：净量 =（大单买 - 大单卖）/ 实时成交额 >= 10% 才加分/封单豁免（v0.47 全大单口径不准）
- `_tx_big_feed` 按 `business_direction` 分计 buy/sell/un（多态解析 1/2、'B'/'buy'/'买'、'S'/'sell'/'卖'），方向未知/缺失不计净量（保守不误判）
- `_l2_big_ratio` 改净量口径；`l2_big_dir_enabled=False` 可回退 v0.47 全大单
- `[l2-big]` 探针输出 买/卖/净/占比/未知；direction 全部未识别时打校准告警

### v0.49
- v0.49 炸板应对收紧 + 回封打板（docs/33）：A 炸板卖出改买N档限价(默认买3+0.95下限保护)；
- B 唯一身位连板封单容忍(seal_fail_ratio_unique) + 二次炸板减半(仅唯一身位后排助攻/人气龙头)；
- C 炸板减去早盘触涨停分(+6, 回封复位恢复)；D 回封打板(前排首板/2板 10:00前炸板回封, 大单占比>=10%)

### v0.48
- v0.48 修复 v0.47 实锤问题（docs/33）：A business_amount 单位非'元'——按 shares/lots/yuan 换算元
- (默认股x价)，探针输出最大单笔元值；B tick_board_scan 并入强度前三成员仅限首板窗口
- (_min_age<=first_board_minute) + 成员上限 20->10（午后帧预算归零）

### v0.47
- v0.47 灵敏度收紧（docs/33）：A L2 大单占比加分（逐笔 business_amount 按 trade_index 去重累计，
- >=10% 加分5分/封单豁免）；B 强度前三板块成员并入 tick 目标集 + scan_interval 4->1 + [scan] 探针；
- C 预封扫板=封单下限 或 大单加持 二者满足其一

### v0.46
- v0.46 首板封单下限 + 唯一预判身位统一（docs/33）：_try_first_board_buy 补 first_board_seal_min
- (L2 买一挂单金额, 防假封秒炸)；_dyn_unq_auction_eval 跳过中位股(与 _mid_board_avoid 统一口径)

### v0.45
- v0.45 云 LogEngine 无 .warn 兼容（_warn 封装 warning->warn->info 兜底不抛，
- 修复 qty<=0 skip 分支与 except 二次崩溃导致 tick_data 链路中断）

### v0.44
- v0.44 合成数据消费审计（docs/40）：_warm_cap 显式消费 sentiment.divergence 分歧标志，
- 与 warm_days 双保险触发分歧保护 taper，修复生成侧 divergence 列云端未被消费的脱节

### v0.43
- v0.43 买卖操作理由与灵敏度日志固化（docs/30）：_signal 结构化行补 lag=检测->下单时延 + det=检测源:首触毫秒；
- [may-order]/[exp-order]/order sent 同补 lag；after_trading_end 打 [rt-summary] 日结（按 side/mode）

### v0.42
- v0.42 一字板竞价终态精确判定（docs/29）：真一字=开=涨停价且卖1=0(total_offerqty==0)才标 one_word；
- + 竞价终态封单基准回填(seal_base，_exp_one_word 首帧即判) + 09:30 首帧补标(防 09:25 漏标)；
- 卖1>0 打 [seal] playable(非真一字, 可参与) 日志；1帧内封涨停放行（不扩大拦截）

### v0.41
- v0.41 情绪温度消费统一全市场红盘比口径（_market_red_ratio 全量分片/独立 market 预算）
- + emotion 档位接入仓位上限（冰点/偏冷40%、回暖/发酵80%、高潮/过热taper，冲突取保守）

### v0.40
- v0.40 from-jsonl 自动兜底并入 ShareData 预期源（含可用性闸门防空文件抢占）

### v0.39
- v0.39 预期文件补股票名列（CSV/JSONL 贯通）+ 预期源对接 ShareData 共享目录

### v0.38
- v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（docs/30）：A 动态唯一(首触无更高/并列身位)；
- B 跟风确认(首触300s窗口内 同板块身位更低未封板成员 1m surge>=1.5% 达2家)；
- C 排序加分/CX标注/持有提示；D 竞价唯一(同身位竞品不及预期)+开盘上攻冲板+跟风确认
- +现价<涨停价 -> 涨停价扫板(预算20%, 避免买不到)；已封板/一字不扫。

### v0.37
- v0.37 中位/主动/唯一性稳健性修复（docs/33）：a) 最快拉升判快改逐笔毫秒归一(_first_zt_ms)；
- b) 首板闸门比较宇宙切概念文件口径(_board_member_codes)；c) 板块内涨幅最高批量回填快照；
- d) zt_lianban 追加权威唯一列(unique_high/follower_count, AXquant 同源预计算)云端读列优先。

### v0.36j
- v0.36j 文件头版本号注释 + init 日志打版本（部署核对）

### v0.36i
- v0.36i 统一买卖信号结构化 [signal]（采集器按日入库/对账）

### v0.36h
- v0.36h 待上传根目录只留 *_latest（dated 全移 archive）

### v0.36g
- v0.36g 盘中重启重建涨停池/自选三态（防 expect_buy 45->12 丢失）

### v0.36e
- v0.36e 概念板块口径+灵敏度（合并快照/两段式surge/预算24）
