# buysell_core —— 高可靠买卖子集迁移骨架（v0.4）
## 定位
docs/18「可高可靠复刻」优先迁移子集；版本迭代 v0.1(骨架)->v0.2(context/回调/日志)
->v0.3(真实买卖参数)->v0.4(真实打分 score_now)。
## 打分 score_now（v0.4，结构等价 AXquant）
分 = clamp(base40 + 静态加分 - 静态扣分 + 攻击加分 - VWAP扣分 + 外内盘, 0, 92)
静态加分（BONUS）：
- auction_beat_history +5：开盘涨幅优于近20日平均开涨（近似）
- touched_limit_early +6：10:00前现价>=涨停价*0.998
- volume_ratio<0.6 +2：今日量/前5日均量（1d 历史 volume）
- is_100day_high +10：现收>=近100日高（1d 历史 close）
- board_bonus -15~+15：板块强度幅度制分档
- tag BS/CORE/LB 各 +5（CORE=连板>=3、LB=连板>=2、BS=百日均新高）
静态扣分（PENALTY）：低开 <=-5% 扣15 / -2~-5% 扣8 / 0~-2% 扣3；板块强度<-2% 扣8。
攻击加分（ATK）：主板涨幅>=8% 时 9:30-9:35 +6 / 9:35-9:45 +3 / 9:45-10:00 +2。
VWAP 扣分：现价<快照 wavg_px 时每 1 分钟扣1，日上限 12。
外内盘：Ptrade 无标准字段，默认 0（口径待券商开接口）。
## 参数来源（AXquant 源码）
- 买分 55/竞价 50、止损按板块 5/7/8/10%、绿开 <=-5%、低吸 px<=MA5*1.02、P5<30/P6 30~50。
- 打分组件与阈值均取 axquant/strategy/scorer/*（static_bonus/penalty/attack/board）与 decision/sell.py、decision/__init__.py。
## 与 AXquant 的口径近似（需盘中/回测校准）
- auction_change 用 开盘_昨收 近似，真实为 get_trend_data 竞价字段；
- board_strength 取所属第 1 板块前 20 只实时涨跌均值（缓存60s），失败返回0；
- VWAP 用快照 wavg_px；外内盘=0；连板天数按收盘>=前收*1.098 近似；
- 真实实时打分依赖交易时段实时行情，回测分钟级可按历史 bar 近似。
## 只读安全 / 环境适配
- DO_ORDER=False 仅记 [may-order]。禁用 os；log 先 % 拼单字符串；run_daily(context,func)+单参回调。编译过 Py3.7。
## 待接 / 下一步
- try_core_buy 门禁（CORE 已并入打分，热度 heat 等价项待定义）。
- 全市场入池 get_Ashares/get_snapshot 扫描替代占位 universe。
- 竞价字段 get_trend_data 接入（绿开/低开/开盘优于历史改真竞价）。
- 预期三态 P4 与封单：按 docs/17 规则口径补。
## v0.6 新增：全市场入池（候选 B）
- get_Ashares() 拉全市场 A 股（按交易日缓存），get_snapshot(列表) 批量取快照；
- 按涨幅>=scan_min_chg 与接近涨停(pre>=up*0.998)过滤，proxy=chg+20*limit 排序，取 top max_watch 进 g.watch；
- 滑动窗口（scan_offset 推进 scan_batch 规模）逐 bar 覆盖全市场，避免只看前段；
- 批量快照不可用时回退逐只（仅 per_stock_cap）；任何失败回退占位 universe；
- 买入/打分/dump 改为迭代 g.watch+持仓。参数见 params.json。
## v0.7 新增：候选 C（竞价真口径）+ 候选 D（预期三态/封单）
- C：_auction_change 改用 get_trend_data(stocks=sec).hq_px/昨收（交易日缓存），失败回退开盘近似；绿开/低开扣分/开盘优于历史自动取真竞价。
- D：移植 AXquant expectation/rules.py —— _eval_auction(高开=超预期/小开=符合/绿开=不及) + _eval_intraday(两根1m站上open*1.01=确认超预期；破VWAP/翻绿=不及；否则符合)。
- 一字板 _exp_one_word：get_gear_price 买一档量=封单（仅交易），>=基准*1.2=超预期、<=基准*1/3=封单衰竭卖出（fast_up_ratio=0.01, seal_exceed_ratio=1.2, seal_fail_ratio=1/3）。
- 接线：每日首bar(handle_data/after_open_probe)对持仓评估；sell_manager 增 P4（P4_exp_miss / P4_exp_one_word）。
- 注意：get_gear_price 回测不可用（docs/13）→ 一字封单仅在交易验证；get_trend_data 研究/回测/交易皆可用。
## 2026-10-16 盘中修复（v0.8c）
- 移除 `_board_strength` 的 `get_sort_msg` 调用（国金签名不适配，持续刷 "入参错误:sort_type_grp" ERROR）；
  板块强度统一走 `_board_strength_by_members`（get_stock_blocks 取板块代码 -> get_industry_stocks 成员实时涨跌均值），已实测 board 有值。
- 新增 `_norm_sec`：统一代码后缀 `.XSHG/.XSHE/.XBJ`；`get_Ashares` 返回值、`_scan_market` 的 watch、`_pool()` 均规范化，
  消除 `.SS` 候选“行情取不到 px=0 ma5=0”的无效打分。
- 待社频重传：需重新把 strategy.py 内容粘贴/上传到「策略」模块，明日盘中核对两点：
  ① ERROR(sort_type_grp) 消失；② watch 不再出现 .SS 候选（px 有效）。
## 2026-10-16 加 L2 探针（v0.8d）
- 新增 _l2_probe(context)：每日一次，对持仓调 get_individual_transaction / get_individual_entrust / get_gear_price，
  解析十档 bid_grp 委托笔数，打一行 `[l2] code=.. tx=.. entrust=.. gear_bid_cnt=.. -> L2_OK/L2_NONE`。
- 挂到 after_open_probe（dump_scores 之后）。目的：明日盘中直接验证收到第三方 L2（docs/21）——交易模块是否有逐笔/委托/十档数据。
- 判定：tx/entrust/gear_bid_cnt 任一非 0 = L2_OK；全 0 = L2_NONE（无 L2 数据或权限不足）。
- 注意：get_gear_price 回测不可用（仅交易），逐笔/委托同理——L2_OK 只能盘中交易验证。
- 待重传：重新把 strategy.py 内容粘贴/上传到「策略」模块，明日盘中核对 `[l2]` 日志行。
## 2026-10-16 盘中再修复（v0.8e）
- 现象（当日实测日志）：扫描候选已规范 .XSHG，但 dump 大量 score .. px=0.00 ma5=0.00 chg=0.0%（仅 universe 与持仓有价）。
- 根因：refresh_spot 只刷 BLS['universe']+get_positions()，而打分/买入迭代 _pool()=g.watch（扫描候选）→ 候选 spot 从不刷新 → last_px/pre_close/ma5 全空。
- 修复：refresh_spot 改为刷 _pool()+持仓（含 watch 候选），用 _get_snapshot_many 批量取+逐只回退，写回 g.spot。
- L2 探针：今日因策略 10:03 重启（已过 09:31），after_open_probe 当日不再触发 → 无 [l2] 日志。已在 handle_data 加首 bar 兜底 _l2_probe(context)，盘中重启/午后拉起也会跑一次（g.l2_probed 保证每日一次）。
- 里程碑：expectation file loaded /home/fly/notebook/expectation_2026-10-16.csv -> 1 —— 上传 CSV 桥接（docs/25）首跑成功。
- 待重传：重新把 strategy.py 粘贴/上传到「策略」，明日盘中核对：① watch 候选 px 非 0（ma5 有值）；② [l2] 行（任一非 0 即 L2_OK）。
## 2026-10-16 L2 实测确认（盘中）
- 10:31 重启后 handle_data 兜底触发探针：`[l2] code=601811.XSHG tx=10 entrust=10 gear_bid_cnt=3 -> L2_OK`。
- 结论：交易模块**具备**逐笔成交（tx=10 笔）、逐笔委托（entrust=10 笔）、十档买一委托笔数（gear_bid_cnt=3）真实 L2 数据（对甲方价 601811）。
- 佐证 docs/21：get_individual_transaction / get_individual_entrust / get_gear_price 在交易模块可用；回测不可用仍成立。
## 2026-10-16 封单 L2 实时化（v0.8f）
- _seal_amount 改为 _seal_metrics(sec) -> (买一挂单金额, 买一委托笔数)（get_gear_price bid_grp，仅交易）。
- P4_exp_one_word 接 L2：
  - 金额比基准：<=fail_ratio(1/3)=CS，>=exceed_ratio(1.2)=CX，否则 CM（逻辑不变）。
  - 新增 L2 委托笔数衰减：bid_enabled 且 bids < bbase*seal_bid_fail_ratio(0.5) -> 提前判 CS（撤单松动）。
  - 每判打 `[seal] sec seal=.. base=.. ratio=.. bids=.. bbase=.. bid_fail=.. -> CS/CX/CM` 诊断日志，供盘中/后续校准。
- 新参数：seal_bid_enabled=true、seal_bid_fail_ratio=0.5（params.json）。
- 灵敏度测试 research/seal/sensitivity_test.py（本地 Python3.10 可跑）：
  - 5 情景（强封/封单炸裂/缓衰/委托笔数塌/封单增强），默认阈值判定稳定；
  - 样本下 bid on/off 会改变 3~7 个时点决策 => L2 笔数衰减补充有效信号；
  - 注意：get_gear_price 仅交易可拿，灵敏度基于合成样本，真实阈值待一字板 [seal] 实盘日志再校准。
## 2026-10-16 日志采集器（v0.8g，本地侧）
- 新增 research/expectation/log_collector.py：粘贴的交易日志 .txt -> data/logs/log_<date>.json（l2/seal/may_order/score/expect/error 分桶）+ log_<date>.seal.csv。
- 客户端无策略日志 API（docs/22），故采集走"贴文本解析"。
- 并入 closeout_review.py：--logs <日志.txt> 新增步骤0档案采集，再同步持仓+复盘。
- seal.csv 列 time,sec,seal,base,ratio,bids,bid_fail,state，可直接回填 docs/29 灵敏度脚本做真实阈值回归。
## 2026-10-16 盘中再核对（v0.9）
- px 修复确认生效（v0.8e 的 refresh_spot 纳入 watch）：watch 候选全取到价（600319 px=6.90, 600148 px=16.28 ...），不再 px=0；chg/board 正常，score 22~57 分布合理。
- 新发现并修复：watch 候选 ma5=0.00——because before_trading_start 只给 BLS['universe'] 算 last_ma5，watch 盘中才入池 → try_ma5_buy 因 ma5=None 全跳过。
- 修复：新增 _ensure_ma5(sec) 惰性算并缓存 MA5；接入 before_trading_start(预填 universe+持仓)、dump_scores、try_ma5_buy。
- 里程碑：盘中 [may-order] 603528.XSHG buy qty=500 ma_pullback px=6.51 ma5=6.68 score=55.0（universe 内 ma5 有值），买入触发生效（DO_ORDER=False）。
- [l2] 再确认 L2_OK（tx=10 entrust=10 gear_bid_cnt=5）。
- 注意：new watch 候选 ma5 需等下次盘中重传后验证（本段日志在 v0.9 落地前采集，watch ma5 仍为 0）。
## 2026-10-16 盘中确认（v0.9 复传后）
- ma5 修复确认生效：全部 watch 候选 px 与 ma5 均非 0（600148 px=16.28 ma5=16.21；600252 px=2.53 ma5=2.21；600319 px=6.90 ma5=6.67 …）。
- 扫描候选首次触发真实买入路径：`[may-order] 600148.XSHG buy qty=200 ma_pullback px=16.28 ma5=16.21 score=60.0`（DO_ORDER=False）。
- 边界注意（重启）：
  - 今日两次 may-order 买入（10:46 603528 qty500、11:04 600148 qty200）分别落在两次会话（中间 10:59 重启），g.daily 随进程重置 -> daily_max_buy(1) 按会话而非自然日生效。真实下单前需确认是否跨重启持久化每日买入计数（buysell_core_state.pkl 目前含 bought/sold 但盘中重置时机待核）。
  - 重启后首个 bar(11:00) 持仓/全景瞬时 px=0，下一 bar(11:03) 正常（get_snapshot 首次订阅主推未到位），属正常，非 bug。
  - 601811 ma5=13.11 vs px≈27：高位连续涨停股 5 日均远低于现价，MA5 特性符合，非异常。
## 2026-10-16 涨停首笔采集 tick_data（v0.10，采集模式 DO_ORDER=False）
- 新增 tick_data(context,data)：仅交易 9:30-14:59 每 3s 一次。从 1m 灵敏度提到 ~3s。
- 职责（采集/决策解耦）：只采集状态 + 打 [firstzt] 日志，下单仍走 1m handle_data。
- 逻辑：
  - _tick_targets() = 持仓 + universe 恒有 + watch 前 tick_watch_cap(15)，控 3s 帧负担避免丢帧。
  - 用 get_snapshot(sec) 逐帧取 last_px/up_px/成交量，顺带刷新 g.spot；
  - 首次 last>=涨停价 -> [firstzt] state=first（记 first_seal/first_bids/ts）；
  - 已板后掉出涨停价 -> ->BREAK held=..s；封单<首封*seal_fail_ratio -> ->SEAL_LOW。
- 新参数：tick_enabled=true、tick_watch_cap=15。
- 采集器已兼容：log_collector 新增 firstzt 分桶 + summary。
- 待重传至「策略」；明日盘中看 [firstzt] 三类行的可读性与触发是否合理，再定确认窗/冷却/买入接线。
## 2026-10-16 跨重启每日买入计数持久化（v0.11）
- 现状问题：盘中重启会重跑 before_trading_start 并把 g.daily 清空 -> daily_max_buy(1) 按“会话”而非“自然日”，同日可能多笔（如 10-16 的 603528、600148 两次 may-order）。
- 修复：buysell_core_state.pkl 从 {buy_log,sold_log} 扩展为 {buy_log,sold_log,daily,day}。
  - load_state 恢复 daily 与 day 戳；before_trading_start 按 get_trading_day() 判定：同日 -> 保留已买计数（跨重启恢复）；跨日 -> 清空。
  - 新增 _save_state() 统一落盘（before_trading_start 首跑 + 每笔买入追加后 + after_trading_end）。
  - 买入两处（_try_expected_buys / try_ma5_buy）追加 daily 后即 _save_state()，盘中重启可恢复。
- 兼容性：旧 pkl 无 daily/day 键 -> st.get 默认空、day=None -> 首跑即升级重写，不崩。
- 注意：sold 每日在盘前置空（g.daily['sold'] 现有代码从不 append，仅保留接口）。
- 待重传 strategy.py；明日盘中核对“重启后不再同日下午再买第2笔”。
## 2026-10-16 统一股池「自选股 + 超预期确认推荐池」（v0.12）
- 自选股动态化/实时同步：_load_selfwatch() 读 selfwatch.csv（研究根或 data/，每行一代码，可盘中编辑重传）；before_trading_start 与 handle_data 每 selfwatch_sync_interval(8) bar 重读，实时并入。
- 固定池 g.pool_static = 自选股 ∪ 预期文件 side=buy（超预期 exceed 优先排序）。
- _pool() 改为 watch ∪ pool_static（去重重排），推荐池真正参与打分/tick/first_zt；_tick_targets 恒含 pool_static。
- 修超预期确认买入：_try_expected_buys 由 st∈{PM,CM} 改为 st!=CS —— 确认超预期 CX 也纳入买入。
- 卖/封单接通：after_open_probe 把 exp_file 的 entry_type/side/expected_status 并入持仓 g.exp（一字板 P4 封单路径可用）；sell_manager 增 side=sell 且确认 miss(P4_exp_sell) 加速卖出。
- 新参数：selfwatch_enabled=true、selfwatch_sync_interval=8。
- 采集器兼容：[pool] 日志（selfwatch/expect_buy/pool_static 计数）分桶。
- 待重传 strategy.py；明日盘中核对 [pool] selfwatch=N 计数、自选股可打分/下单、推荐池买得到。
## 2026-10-16 盘中核对（v0.12 复传后）
- [firstzt] 大量触发（20 条）：能逐只感知触板+封单量(business_amount)+买一笔数；SEAL_LOW/BREAK 节奏正常（例：601155 seal 220万→8.75万 ratio=0.04 SEAL_LOW，后 12.63 破板 held=132s）。
- 修复 vol=0：get_snapshot 单标的成交量字段是 business_amount（非 volume），_snap_vol 已补（business_amount/volume/trd_volume/amount 依次取）。
- [pool] selfwatch=0 expect_buy=0：因今日尚未上传 selfwatch.csv、且当日预期文件仅 1 条(非 buy) —— 数据缺，非逻辑 bug（逻辑已本地断言通过）。
- 午后无 may-order：符合“每日/冷启可能已达上限或无合适入场”，非异常。
- 待核：重传后可看 [firstzt] vol 非 0；上传 selfwatch.csv 后 [pool] selfwatch=N>0。

- 触板时刻 ms 增强（v0.12 内）：firstzt 记录并打快照 `hsTimeStamp`（毫秒）`ms=..`，比 3s 帧更精确还原触板时刻（“真·逐笔首笔”的中间态；完整逐笔解析留 docs/30 扩展点）。

## 2026-10-16 读取软件端自选股（客户端本地）
- 客户端「我的自选」= D:/gjzq/ptrade/Data/IndividualData.xml（QuoteCode，.MRI 指数跳过，.ESA 个股保留）。
- 新增 research/scripts/read_selfwatch.py 读取并生成 data/selfwatch.csv；沙盒读不到本地，生成后上传研究根同步。
- 实测客户端自选仅 002343.XSHE 为 A 股（另 2 只是指数）。

## 2026-10-16 自选股一键同步脚本
- 新增 research/expectation/sync_selfwatch.py：
  - --sync：客户端自选(IndividualData.xml) -> 上传暂存 data/ptrade_bridge/selfwatch.csv + 本地 data/selfwatch.csv。
  - --verify-log：用 log_collector 比 [pool] selfwatch=N 与客户端自选数（一致/不一致）。
- 并入 closeout_review.py --selfwatch（步骤0同步自选股）。
