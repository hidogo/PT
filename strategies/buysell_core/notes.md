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

## 2026-10-16 预期买入敏捷化 v0.13（tick 3s 触发 + 实盘单门控 EXPECT_ORDER）
- 问题：预期买入只在 1m handle_data 评估，且确认用按日缓存的 _auction_change——「超预期确认」被固定在自己第一次求值时刻，盘中快速上攻(超预期)那段完全采不到，触发延迟至多~60s。
- 解法（采集/决策解耦变为「采集即决策」的精准版，仅针对预期买入路径）：
  - tick_data 3s 帧末统一调 _try_expected_buys()，竞价超预期/盘中快速上攻一道确认立买；handle_data(1m) 兜底共用同一入口。
  - 实时三态 _exp_rt_status()：超预期(竞价已达标 CX / two_1m 快速上攻 CX / below_vwap 放弃 CS)；一字板走 _exp_one_word L2 封单；miss 放弃；meet/未标注走 _eval_intraday。
  - 一次触发去重 g.exp_fired：买/放弃皆记，持久化进 buysell_core_state.pkl（跨重启不双买，日切清空）。
- 独立实盘门控：EXPECT_ORDER（默认 False）只放行预期买入发真实 order()；其余买入仍受 DO_ORDER 门控 → 可「模拟盘仅对预期路径小额真实下单」验证敏捷度与成交。
- 新参数：EXPECT_ORDER、tick_exp_enabled、exp_order_pct(0.3，可调小如 0.01)。
- 修隐患：g.pending 从未初始化（EXPECT_ORDER=True 真实下单会在 place_order 第 ~990 行崩）→ initialize 补 g.pending={}。
- 日志：预期买入发单打 [exp-order]（True/False 标注），放弃打 [exp] ... miss -> skip；log_collector 新增 exp_order 分桶。
- 编译：PT 3.7 & 本地 py310 均通过。逻辑自测 research/expectation/selftest_exp_rt.py 13/13 过（竞价/上攻触发、走弱放弃、去重、重启恢复、日切、真实发单）。
- 待重传 strategy.py；明日盘中核对 [exp-order] 在超预期确认后 3s 内出现、EXPECT_ORDER=True 时真实委托。

## 2026-10-18 前瞻预期含「持仓+核心苗子」+ 显式 side=buy（rebuild）
- 问题：原 export_expectation_csv 的 side 由 status 推导（miss->sell，否则 hold），永远产不出 buy ——「核心苗子前瞻建仓」进不了待上传 CSV，实盘单测试也没候选。
- 修复：export_expectation_csv 优先采用记录显式 side（buy/sell/hold），缺失再按 status 回落。核心苗子可标 side=buy。
- 重建：research/expectation/rebuild_expect_from_review.py 读 AXquant review/position_review_<T>.jsonl（kind=holding/seedling）→ 生成 <T+1> position_expectation jsonl（持仓->hold，苗子->buy: pending_exceed，expected_auction_change_pct=floor(竞价,3.0)）→ from-jsonl 导出待上传 CSV。
- 结果：2026-10-19 预期 5 行 = 持仓 603690/601811(hold) + 核心苗子 600825/000530/600668(buy, pending_exceed)。
- 角色纠正：601811 为连板（三连板，快照 consecutive_board 池），非首板；AXquant 复盘对 601811 误标 first_board_arb（与快照连板池不一致）→ rebuild 内置 role_fix 纠正，建议修 AXquant 角色引擎保持一致。

## 2026-10-18 预期买入改两阶段（v0.14，用户确认逻辑）
- 用户申明逻辑：前瞻预期股（side=buy，预期超预期）-> T+1 竞价终态初步确认「竞价超预期」-> 观察流程（不买）；分时确认超预期 -> 执行买入；分时转弱 -> 放弃。
- 修复 startswith 坑：CSV expected_status=pending_exceed（前缀 pending_），startswith("exceed") 匹配不上 -> 分支根本没走。改 "exceed" in exp_status / "miss" in exp_status（_confirm_expected、_exp_rt_status、_sync_pool_static 排序三处）。
- 新两阶段 _exp_rt_status（超预期分支）：
  1. 分时确认已现（_two_1m_break 且未破 VWAP）-> CX intraday_exceed -> 买入；
  2. 分时转弱（破 VWAP）-> CS below_vwap_weak -> 放弃；
  3. 竞价超预期初步确认（_confirm_expected==CX，即真实竞价>=预期阈值）-> PM observe_auction_exceed -> 观察，等分时（一次 observe_seen 日志）；
  4. 其余 -> PM await_intraday_confirm。
- 观察流程日志：首次进入观察打 [exp] <code> observe ... -> 观察中(等分时确认)。
- 自测 selftest_exp_rt.py 9/9 通过（观察不买、分时买、破VWAP放弃、去重、重启、日切、真实发单、pending_exceed匹配）。
- 待重传 strategy.py 生效；明日盘中核对：超预期苗子先 [exp] observe，随后分时上攻才 [exp-order]。

## 2026-10-18 分时确认超预期：两分钟上攻 或 一分钟冲涨停（v0.14 细化）
- 用户补充：分时确认超预期 = 两分钟上攻(_two_1m_break) **或** 一分钟冲涨停(_limit_up_within_1m)，且未破 VWAP。
- 新增 _limit_up_within_1m(sec)：当前价>=涨停价*0.998 且时段 09:30-09:32（开盘 ~1 分钟冲板）。
- _exp_rt_status 超预期分支 CX 判定改为 `(_two_1m_break or _limit_up_within_1m) and not below_vwap`。
- 自测 13/13 通过（新增 T2b 一分钟冲涨停触发、T2c helper 时段 09:31 True / 14:00 False）。

## 2026-10-18 买入定价：打板/追高/回踩 + 修 order() 限价传参
- 隐患：order(security, amount, limit_price=None) 第三参是价格；原两处 order(sec,qty,'buy'/'sell') 把方向串当 limit_price 传，真实开盘必错价/失败。已修为 order(sec,qty,limit_price=limit)（limit 为 None 时走默认最新价）。
- 定价策略 _order_limit(sec,side,mode)：price_precision=2(A股) 取整；
  - board(打板) = 涨停价 up_px；
  - chase(追高) = 现价*(1+buy_chase_pct=0.008) 后封顶涨停价（防过度追高）；
  - pullback(回踩) = 现价限价；sell = 现价限价（防急跌垃圾价，需注意走弱中可能不成交）。
- 场景决策：
  - 超预期分时确认-一分钟冲涨停 -> 打板（挂涨停价排队，前一日买入）；
  - 超预期分时确认-两分钟上攻（未触板） -> 追高（上浮0.8%封顶涨停价）；
  - 一字板封单超预期 -> 打板（同 board）；
  - ma5 回踩 -> 现价限价（pullback）。
- 现金仓位按 limit（最坏价）计 qty（打板时用涨停价算，确保可成交不超仓）。
- 自测 15/15（新增 T7 限价数值断言、T9 三场景定价、T10 打板挂涨停价）。
- 再修：一字板超预期(one_word + "+exceed") 封单 CM(未超预期) 曾会触发买入 -> 收紧为仅封单超预期(CX)才买，CM 降级等待。自测 17/17。

## 2026-10-18 对齐 AXquant 买卖逻辑核心（v0.15）
- 一字板·封单超预期**不参考排单**：新增 _sealed_at_limit(sec)（现价>=涨停价*0.998 且 L2 卖盘空=封死；无盘口判非封死，与 AXquant has_book 一致）。buy 路径统一在 _block_sealed_buy 拦截（place_expected_order + _order_limit board 双保险），返回"不买、不置 fired、可再评估"，同标的每日仅告警一次 [seal] sealed at limit。对齐 AXquant P1-3 limit_up_sealed_no_queue。
- 竞价核卖 P2E（AXquant _sell_expectation_miss）：sell_manager 在 P1 之后、P3 之前插入 P2E——预期 expected_status in {confirmed_miss, degraded}（可选加 pending_miss，exp_sell_on_pending_miss=False 默认不加）-> 清仓。优先级对齐 AUCTION 链 P1>P2E>P3。
- 弹性买入价 10% 上限（AXquant _elastic_20cm_max_buy_price）：新增 _is_elastic_20cm(300/301/688/689) 与 _max_elastic_buy_price=前收*(1+elastic_max_buy_pct=10%)。_order_limit chase 追高路径封顶 10%（board 打板豁免），对齐 300/688 非打板不超前收*1.10。
- 编译：PT3.7 + py310 均 py_compile 通过；自测 selftest_exp_rt.py 30/30 通过（新增 T12 封死不排队买 / T12b 未封死可排队 / T13 弹性10%上限+打板豁免 / T14 P2E核卖 / T14b pending_miss默认不卖）。
- 待重传 strategy.py；明日盘中核对：[seal] sealed at limit、P2E_exp_miss 日志、300/688 追高限价不超前收*1.10。

## 2026-10-18 节奏验证：9:20上传 -> 9:25竞价终态初步确认 -> 9:30+分时确认
- 验证结论（原代码有断点）：before_trading_start 约 9:10 前就跑，_load_expectation() 只在其内调用 -> 9:20 上传的预期前瞻文件全天读不到；也无 9:25 竞价终态钩子，「初步确认->观察」步骤缺失。
- 修复：新增 run_daily auction_pre_confirm time='09:25'（initialize 注册，定时任务现共 3 个 <5）：
  1) 幂等重读 _load_expectation() + selfwatch + _sync_pool_static()，命中 9:20 上传文件；
  2) 对 side=buy 候选刷 _eval_auction + _exp_rt_status，竞价超预期初步确认(CX) -> 打 [exp] <code> 09:25竞价终态初步确认超预期 -> 观察(等分时确认)（不买、不置 fired）；
  3) 不走上单路径，纯观察。
- after_open_probe(09:31) 加幂等重读兜底（应对稍晚到上传）。
- 分时确认(9:30+)沿用 _exp_rt_status 超预期分支（_two_1m_break 或 _limit_up_within_1m 且不破 VWAP -> CX 买单；tick 3s 触发）。_auction_change 用 get_trend_data，9:25 竞价终态缓存正确。
- 自测 selftest_exp_rt.py 34/34（新增 T15：09:25 重读 + observe_seen + 观察日志 + 不买）。PT3.7+py310 py_compile 通过。
- 待重传；明日盘中核对：09:25 日志 auction_pre_confirm done exp_file=N + [exp] ...观察，随后 9:30+ 才 [exp-order]。

## 2026-10-18 逻辑链路兜底盘点 + 竞价初判未达标即放弃
- 兜底盘点（已具备）：文件缺失/坏格式不崩(_load_expectation try/路径候选)；预期文件空则走 watch 打分+ma5 扫码兜底；9:25+09:31 双重重读(盘中重启 before_trading_start 也重读)；_auction_change get_trend_data→open/昨收回退；观察/分时评估 try/except；place_expected_order 失败不置 fired 下帧重试；exp_fired+每日买入计数持久化防同日二买/重启重放。
- 修复缺口：原先竞价初判未超预期(acon!=CX)只进 await，盘中两分钟上攻仍会买，违背「竞价超预期才观察」。现改为 _exp_rt_status exceed 分支：未达标 -> CS auction_not_met(放弃,置 fired)；真竞价缺失(hq/open=0 致 actual~-100)兜底 `< -90` 不误弃，保持 await。auction_pre_confirm 增加「09:25未超预期->放弃」日志。
- 已知设计取舍（未改，待定）：1) 分时确认依赖两分钟上攻/一分钟冲涨停特征，若无进攻形态将持续 observe 不触发（靠破VWAP放弃兜底）；2) place_expected_order 成功后即置 fired，若真实委托被拒/未成交当日不再回购（防重复优先）。
- 自测 37/37（新增 T16 未达标->CS 放弃、T16b 数据缺失不误弃）；PT3.7+py310 py_compile 通过。

## 2026-10-18 供方数据健壮性 v0.17（预期三态供方字段 + 云端自取兜底）
- 结论：T-1 开盘涨幅(yesterday_open_pct) 与 达标基准(expected_auction_change_pct) 属「有条件提供」——AXquant 复盘缺该字段时桥接 CSV 会缺，16/17 文件曾缺失(→0)。消费端有隐患：负基不判高开、缺失基准被当0->超预期过触发。
- **云端自取**（答：可行，get_price 1d 历史已用于 ma5）：
  - _yesterday_open_chg：T-1开盘涨幅，供方缺失用 open[-3]/close[-4]-1 折算；返回 (chg, provided)。
  - _auction_benchmark：预期达标基准，供方缺失/<=0 用 open[-2]/close[-3]-1(T日/复盘日开盘涨幅) 折算；返回 (bm, valid)。
- **A** _eval_auction：`yopen>0and chg>yopen` -> `has and chg>yopen`，负基也判高开，缺基不误判。
- **B** _confirm_expected/_exp_rt_status：基准缺失(has_bm=False)或<=0 -> 不算达标(PM,不CX)、不误弃(不CS)；修复「缺失基准被当0->恒超预期过触发」。exp_auc>0 才校验 actual>=bm。
- **C** 供方 expectation_store 导出：昨日开盘/预期基准缺失 -> 空串(非0)，consumer 用 has_yesterday_open/has_expected_auction 区分；build_expectation_bridge validate 加「缺失行数」非阻断提醒。
- 自测 43/43（T16/T16b 调整mock基准；新增 T17 缺基准不超预期不放弃、T18 负基高开+云端折算、T19 云端基准折算不达标）；PT3.7+py310 py_compile 通过。
- 注：预期前瞻文件仍需提供「当日/复盘日开盘涨幅」作为 expected_auction_change_pct 基准；云端1d折算仅为缺失兜底。
