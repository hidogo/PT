# buysell_core - 版本记录

> 变更记录统一存本文件；strategy.py 文件头仅保留「当前版本 / 部署核对」。

## 当前版本
- 当前版本：v1.4（2026-10-28）

## 部署核对
- 部署核对：日志首行 `buysell_core init version=v1.4 ... DO_ORDER=True EXPECT_ORDER=True sim_cash=0.0`（init 打印 STRATEGY_VERSION）
- 每次更新版本号后重传 strategy.py 云端，以日志首行 `buysell_core init version=..` 核对。

### v1.4
- v1.4 预期买入纵深加固 + 竞价情绪全池就绪（2026-10-28 实盘数据链路复盘修复）：
  - `place_expected_order()` 在 px/cash 检查后、发单前增加 `_intraday_ready` 兜底，
    未就绪打印 `[exp-order] intraday_data_not_ready(兜底)` 并返回 False，防状态机间隙
    spot 失效仍误发单；`[exp-order]` 日志增加 `ready=spot/1m` 状态字段。
  - `_exp_one_word()` 封单就绪门：`seal_base<=0` 且当前 `seal<=0` 返回
    `AW(seal_data_not_ready)`，等 L2 明确后再判，不再把数据真空留给后续误弃。
  - `_eval_auction()` 就绪门：`_auction_change==0` 且 `_auction_ready=False` 返回
    `AW(auction_data_not_ready)`，`_eval_intraday()` 对 AW 保持 PM 等待，
    防负基昨日开盘把未就绪误判 PX（2026-10-28 榕基软件类根因）。
  - 竞价情绪全池就绪：新增 `_fill_zt_spot()`，`auction_pre_confirm()` 与
    `_lb_senti_auction()` 对 `zt_lianban` 全池缺 spot 批量补快照；就绪率仍不足
    再补一次重算，输出 `ready_detail(mid/low)`，防 09:25 `ready=26/41` 假未就绪。

### v1.3
- v1.3 同日重启守卫 + 开盘分时就绪门（2026-10-28 实盘复盘修复）：
  - `first_zt` 记录统一带交易日戳 `day`（tick tx/snap、首板 1m 兜底、重启重建四条创建路径）；
  - `load_state()` 恢复 `first_zt/auction_c` 增加 `first_zt_day/ac_day` 双重守卫，并按记录 `day` 过滤，
    跨日/异常分支强制清空内存旧值（防 2026-10-28 09:30 旧池票 BREAK held≈86k s、文投 det=tx:20261027094528520
    这类跨日首触污染当日灵敏度与买入）；
  - `before_trading_start()` 增加 `[restart-guard]` 防御兜底，发现跨日残留即清空并走重建队列；
  - `_eval_intraday()` 对 `pending_meet/pending_exceed` 新增 `_intraday_ready` 就绪门：spot 现价/开盘/VWAP
    齐备或 1m>=2 根才允许判 CM/CX，否则返回 `PM(intraday_data_not_ready)`，防开盘首帧数据真空误发
    `confirmed_meet` 买单（2026-10-28 09:30:04/06 海洋王、文投两笔根因）。

### v1.2
- v1.2 连板高度压制 → 唯一连板空间闸门（docs/40 §7）：sentiment CSV 新增近 10 日最高板路径与压制位
  （生成侧 `_height_path` 自算，默认 7 板异动压制，与复盘结论同源）；云端 `_lb_senti_buy_gate` 对唯一连板
  （unique_high/动态唯一/原题材唯一存活龙头）消费压制位空间闸门，`(suppress-板数)/suppress < 15%` 拦截
  （low 档豁免；参数 `unq_space_gate_enabled/unq_space_min`）。

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

### v1.4（2026-10-28）预期买入纵深加固 + 竞价情绪全池就绪
- 变更（strategy.py）：
  - `place_expected_order()` 发单前新增 `_intraday_ready` 兜底：未就绪返回 False 并打印
    `[exp-order] intraday_data_not_ready(兜底)`；`[exp-order]` 成功/模拟日志带
    `ready=spot/1m`，供现场核对 spot VWAP/开盘/现价 或 1m>=2 根的就绪链路。
  - `_exp_one_word()` 新增封单就绪门：`seal_base<=0` 且当前 `seal<=0` 返回
    `AW(seal_data_not_ready)`，L2 明确前不写 base、不判 CS；`g.seal_base/seal_bid_base`
    改为防御式读取（未初始化不崩）。
  - `_eval_auction()` 新增竞价就绪门：`_auction_change==0` 且 `_auction_ready=False`
    返回 `AW(auction_data_not_ready)`；`_eval_intraday()` 对 AW 返回
    `PM(auction_data_not_ready)`，避免负基昨日开盘把未就绪误判 PX/CM。
  - `auction_pre_confirm()` 与 `_lb_senti_auction()` 新增 `_fill_zt_spot()`：
    对 `zt_lianban` 全池缺 spot 批量补快照（复用 `_elastic_yizi_scan` 范式），
    就绪率仍不足再补一次重算；`[lb-senti] auction` 输出
    `ready_detail=mid:n/N low:n/N`，修 09:25 `ready=26/41` 假未就绪。
- 测试：selftest_exp_rt.py 新增 T138（发单兜底不买）、T139（一字封单未就绪 AW 等待）、
  T140（未就绪+负基不误判 PX）、T141（竞价情绪补快照落档）、T142（缺失矩阵不误买不误弃）；
  既有用例补齐 `open_px` 模拟真实 spot 口径。全量 PASS、pytest 50 passed、双编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v1.4`；盘中核对
  `[lb-senti] auction ... ready_detail=mid:n/N low:n/N`、`[exp-order] ... ready=spot/1m`
  以及数据真空时的 `[exp-order] intraday_data_not_ready(兜底)`。

### v1.3（2026-10-28）同日重启守卫 + 开盘分时就绪门
- 变更（strategy.py）：
  - `first_zt` 记录新增 `day` 交易日戳（`_try_first_board_buy_1m` 兜底、tick `src=tx/snap`、
    `_rebuild_first_zt_tick` 四条创建路径统一）。
  - `load_state()` 恢复 `first_zt` 的条件从「state.day==今日」收紧为「state.day==今日 且
    first_zt_day==今日 且 记录 day==今日」，`auction_c` 同步用 `ac_day` 守卫；跨日/异常分支强制
    `g.first_zt={}; g.auction_c={}`，不再沿用内存旧值；新增 `[restart-guard]` 日志。
  - `before_trading_start()` 对 `first_zt` 做防御兜底：存在非当日记录即清空，随后由
    `_rebuild_first_zt_queue()` 从 L2 回看重建。
  - `_eval_intraday()` 新增 `_intraday_ready` 就绪门：`PM/PX` 且 spot 现价/开盘/VWAP 未齐备且
    1m<2 根时返回 `PM(intraday_data_not_ready)`，不再无条件 `CM(held_vwap)`；`PS/CS` 与 `CX` 不受影响。
  - 顺手加固：`_hhmm()` 改 `getattr(g,'now_dt',None)` 防御读取；`_parse_tx_zt_ms` 的 day_open
    优先用 `get_trading_day()` 归一化（缺省才回退 `time.localtime()`），并修正日期依赖回归用例。
- 背景：2026-10-28 09:10 服务器拉起后旧池票在 09:30:00 集体 `BREAK held≈86k s`，文投 09:30:06 买入
  `det=tx:20261027094528520`（10-27 首触）；同时 09:30:01 `data_na(board)` 后 09:30:04/06 仍发
  `exp_rt confirmed_meet intraday` 两笔买单（海洋王、文投）。
- 验证：selftest_exp_rt 全量 PASS（新增 T136 同日守卫/记录日期戳/重建队列、T137 分时就绪门）；
  selftest_ops_oneclick 28 PASS；pytest 50 passed；strategy.py 与 deploy 剔除注释 py_compile 通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v1.3`；盘中核对
  `[restart-guard]` 日志与 `[firstzt] ... day=今日`、meet 候选未就绪时 `intraday_data_not_ready`。

### v1.1（2026-10-27）daily_max_buy 1->2（每日最多 2 笔真实买入）
- 变更（strategy.py）：`daily_max_buy=2`（用户确认 2026-10-27）；买入闸门（首板/回封/弹性/低吸/预期）
  按 `g.daily['bought'] >= 2` 拦截，即每日最多 2 笔真实买入。
- 验证：selftest_exp_rt 全量 PASS（daily_max_buy 用例均显式设置，默认值变更不影响）；py3.10 编译通过；deploy 剔除注释编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v1.1`；盘中核对第 2 笔买入放行。

### v1.0（2026-10-27）实盘下单开启（DO_ORDER=True + EXPECT_ORDER=True）+ 版本号里程碑
- 变更（strategy.py）：
  - `DO_ORDER=True`：买卖闭环真实委托（首板/回封/弹性/低吸/预期买入 发真实 order()；卖出通道 P1/P2E/P4/P5/P6/炸板/封单 真实卖单）。
  - `EXPECT_ORDER=True`：预期买入路径发真实 order()（此前独立门控默认关）。
  - `sim_cash_base=0.0`：关闭 SIM 虚拟资金，下单资金基准切换为真实账户现金（回切模拟时改回 200000.0）。
- 资金约束提醒（docs/24 §16 实盘就绪度）：2026-10-28 开盘前可用资金 16,000 元：
  `exp_order_pct=0.10`/低吸/普通买入 单笔预算 1600 元 → 1 手价位 ≤ ~16 元；
  打板（`board_buy_budget_ratio=0.20`）单笔预算 3200 元 → 1 手 ≤ ~32 元；
  单票市值上限（`single_stock_cap=0.30`） 4800 元、情绪仓位上限（回暖 0.8） 12800 元、`daily_max_buy=1` 每日 1 笔。
  更高价位 qty=0 自动跳过（属正常非故障）。
- 风险纪律（docs/24 §16.3）：连续 2-3 笔亏损、出现未成交/留滞/重复下单/成交回报异常 → 立即回
  `DO_ORDER=False; EXPECT_ORDER=False` 复盘后再继续。
- 验证：selftest_exp_rt 全量 PASS（新增 T133 共 6 例：生产默认 DO_ORDER/EXPECT_ORDER=True、sim_cash_base=0、
  实盘非 SIM 模式、place_order 实单发单+记 pending、预期买入实单发单）；py3.10 编译通过；deploy 剔除注释编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v1.0 universe=.. DO_ORDER=True EXPECT_ORDER=True sim_cash=0.0`。

### v0.81（2026-10-27）[budget] 日志节流（常规 60s 心跳 + over/degraded 事件行）
- 背景：`handle_data` 帧末无条件打 `[budget] <frame_report>`，3s 一条；今日窗口 1642 条占日志 36%，
  常规信息（snapshot=1/2 等）绝大多数帧无变化，属非关键信息。
- 修改（strategy.py）：
  - 新增 `_budget_log()`（模块级），`handle_data` 帧末改调它；保留 `budget_log_enabled` 总开关语义。
  - 新参数：`budget_log_heartbeat_sec=60.0`（常规摘要节流，0=常规摘要静默只打事件）、
    `budget_log_event_sec=30.0`（事件行同因去重窗口）、`budget_log_on_over=True` /
    `budget_log_on_degraded=True`（帧内预算超限/数据源降级立即打事件行）。
  - 打印规则：事件优先（over 帧只打事件行不打常规摘要）；常规摘要按 60s 心跳（首帧立即）；
    心跳附带窗口累计 `over_w60s:`（打印后清零）；事件行即心跳基准（防事件后下一帧补打）。
  - `_skip_log` 新增可选 `throttle_sec` 覆盖节流窗口（[budget] 事件行用 budget_log_event_sec，既有调用不变）。
- 补全：帧末调用点 `_budget_log()`（初版部署漏挂帧末调用，云端仍每帧打 [budget]；T132g 静态防回归）。
- 验证：selftest_exp_rt 全量 PASS（新增 T132 共 14 例：首帧心跳/60s 节流/61s 恢复/over 立即+去重/
  事件优先/degraded 新增即打/heartbeat=0 语义/总开关静默/帧末调用点）；py3.10 编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v0.81`；盘中核对 `[budget]`
  降至 ~60s 一条且 `over:`/`degraded:` 事件即时可见。

### v0.80（2026-10-27）SIM 虚拟资金基准 + 重建超时放弃 + 同因日志节流
- 背景：今日日志暴露 3 个问题——
  1) 全市场 0 信号（1831 次 `exp order skip(qty<=0)`，真实现金 ~2106，SIM 观察模式下买入量按真实现金计算导致信号缺失）；
  2) `restart-rebuild pending=4 done=0` 全天卡死（当日未触涨停的票永不重建成功，heartbeat 持续刷屏）；
  3) `[reboard] 非前排` 等低频原因每帧刷屏 ~590 条，干扰信号日志检索。
- 修改（strategy.py）：
  - SIM 虚拟资金：新增 `sim_cash_base=200000`（纯模拟 DO_ORDER=False 且 EXPECT_ORDER=False 时买入量按此计算；
    0=关闭用真实现金）与 `sim_min_lot=100`；新增 `_sim_mode()/_size_cash()/_size_total()`，`_calc_buy_qty`、
    `_buy_pos_ok`、`place_order`、`place_expected_order` 统一改走资金基准；SIM 下 qty<=0 回退最小一手 100
    并打 `[sim-min-lot]`（信号可观察，不发真单）。init 日志补 `sim_cash=`。
  - 重建超时放弃：新增 `first_zt_rebuild_timeout_min=30`；登记时记录 `g.first_zt_rebuild_ts[sec]` 入队时间戳；
    `_rebuild_first_zt_tick` 开头判定「入队超时 或 已过 10:00」（首板/回封闸门已过）-> 移出队列+日志+heartbeat，
    防 pending 全天卡死。heartbeat 增加 `left=` 剩余明细。
  - 同因日志节流：新增 `_skip_log(tag, sec, reason, msg)`（`g.skip_log_ts` 表，同因 30s 去重，原因变化立即打），
    替换 13 处低频原因刷屏点（`[mid-avoid]`×6、`score-na`、`[st-skip]`×3、`[reboard]` non_front/l2_big_low/seal_low）。
- 验证：selftest_exp_rt 全量 PASS（新增 T131 共 9 例：SIM 资金基准/最小一手兜底×2/非 SIM 拦截/重建超时/10:00 截止/同因节流）；
  py3.10 编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v0.80 ... sim_cash=200000.0`。

### v0.79（2026-10-26）zt_lianban 盘中重读防收缩（P1）+ 唯一身位口径验证（R1 前置）
- 背景：09:25 `auction_pre_confirm` 重读 `_load_zt_lianban` 为全量替换，若上传文件被误覆盖为收缩版会丢候选；
  且复盘 `unique_high` 权威列（AXquant reason 关联分组）与 PT 消费的 themes 全量归并口径不一致，
  600094（2 板，地产组最高实为 600838 4 板、AI 组 3 只 2 板并列）被误标 unique_high=1 -> 漏过中位规避。
- 修改（`_load_zt_lianban(merge=False)`）：
  - 09:25 调用改 `_load_zt_lianban(merge=True)`；merge 语义：新文件 code 字段胜出 + 旧有但新文件缺失的 code 保留
    （对齐 `_load_expectation` C 合并），首载保持全量替换。
  - 日期身份守卫：重读文件 `date` 列非空且 != 现有 date -> 拒绝重载（防旧文件回填覆盖）。
  - 防收缩护栏：新文件行数 < 现有 50% -> 视为异常覆盖，完全保留现有并打告警。
  - merge 且尚无现有（如盘中重启后首次加载）时视为全量，`g.zt_lianban` 缺属性不再抛。
- R1（AXquant 侧，待对接）：`unique_high` 判定分组口径改为 themes 全量归并（与 PT `_annotate_zt_uniqueness`
  兜底逐条一致）——同题材最高身位唯一授 1，600094 应收 0、600838 收 1。本版已用 T130a/b 锁定 PT 兜底与
  权威列消费行为，AXquant 修正后中位规避即恢复。
- 验证：selftest_exp_rt 全量 778 PASS（新增 T130 共 12 例：兜底唯一身位/权威列一致/merge 防收缩/日期守卫/收缩护栏）；
  selftest_ops_oneclick 28 PASS；pytest 50 passed；py3.10 编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v0.79`；
  盘中核对 09:25 `[zt-lianban] merged old=.. new=.. keep_old=..` 仅在重读出现。

### v0.78（2026-10-26）连板盘中情绪状态机可达性(A) + 统一方向闸(B) + 三列停产(C) + 竞价就绪校验(D)
- 背景：10-26 云端 `[lb-senti] 10:00 t100 freeze phase=watch` —— 状态机 10:00 前常被
  `min_touch_ratio=0.5` 样本门槛与 60s 滞回锁死在 watch（档位不可达）；首板/回封/弹性买入
  不消费方向闸（诊断无法区分「有意低位试错」与漏闸）；09:26 竞价首轮在数据未就绪时输出
  `open=0.0%` 假 0（依赖 09:31 兜底修正）。
- A 状态机可达性（10:00 前保证灵敏度与节奏）：
  - `_lb_senti_set_phase` 新增 `force_confirm`；`lb_senti_t100_freeze` 调用
    `_lb_senti_mid(force=True, force_confirm=True)` —— 10:00 冻结必落档（跳过滞回确认）。
  - 新参数 `lb_senti_hysteresis_sec_before=30.0`：10:00 前风险升级确认窗口 30s，
    10:00 后保持 60s（`lb_senti_hysteresis_sec`）。
  - 新参数 `lb_senti_min_touch_ratio_before=0.3` + `lb_senti_min_touch_floor=3`：
    10:00 前样本门槛放宽（mid_pool=9 -> touched>=3 即判档；池 < floor 不强制，防小池锁死）；
    10:00 后维持 0.5。
- B 统一方向闸（新总开关 `lb_senti_gate_all_buys_enabled=True`）：
  - `_try_first_board_buy`：首板 tier=low 恒放行，补 `[lb-senti] ... allow` 日志（区分有意低位试错）。
  - `_try_reboard_buy`：回封 2 板 tier=mid，rotate_low/high_diverg/ice_wait 下 `mid_high_skip` 拦截。
  - `_try_elastic_arb_buy`/`_try_elastic_top_buy`：弹性首板 low 恒放行补日志；含 2 板候选同样被闸。
  - `_lb_gate_seen` 增加 `action` 参数（expected_buy/first_board/reboard/elastic），日志区分通道。
- C 三列停产（仅记录字段，v0.78 起不参与决策）：`theme_count/theme_max_board/follower_count`
  云端保留兼容旧文件读取；AXquant 复盘侧可停产这三列（保留
  `theme/theme_rank/themes/unique_high/board_cnt/is_st/reason/seal_money/limit_up_time/chg_pct`）。
- D 竞价就绪校验：`_lb_senti_auction` 统计前用 `_auction_ready` 计算 mid/low 就绪率，
  新参数 `lb_senti_auction_ready_min=0.6`；不足时输出 `ready=False / note=auction_data_not_ready`，
  open/green/yizi 率置 None 不写（防 09:26 假 0）。
- 验证：selftest_exp_rt 全量 766 PASS（新增 T129 共 13 例 A/B/D）；selftest_ops_oneclick 28 PASS；
  pytest 50 passed；py3.10 编译通过。
- 待重传：strategy.py 云端，核对日志首行 `buysell_core init version=v0.78`；
  盘中核对 `[lb-senti] t100 freeze phase=` 已落档（非 watch 锁死）、`auction not_ready` 只在数据未就绪出现。

### v0.77（2026-10-26）ST 全链路兜底补全：tick 板块成员通道 / 首板买入 / 下单闸
- 背景：10-26 早盘 ST西王 000639 二触（09:31:39）发出首板 SIM 信号（云端 v0.71 无 ST 剔除）。
  本地 v0.75 的 `_is_st` 只在 tick 目标列表（uni/static/near/watch 四通道）生效，
  但板块成员通道（`_tick_targets` 内 `tick_board_scan` 追加）、`_try_first_board_buy`、
  `place_order`/`place_expected_order` 三处无 ST 兜底 —— 经板块通道进来的新票仍会漏。
- 修改：
  - `_tick_targets` 板块成员追加：`not (_skip_st and _is_st(_m))` 过滤（ST 不进 tick 候选）。
  - `_try_first_board_buy`：`_is_st` 早退 + `[st-skip]` 日志（首板闸门兜底）。
  - `place_order` 买入侧 / `place_expected_order`：`_is_st` 兜底（覆盖首板/回封/弹性/低吸/预期全部下单入口）。
- 验证：`selftest_exp_rt.py` T128 新增 8 例（名称兜底/zt 权威/首板拦截/下单闸拦截/板块成员通道剔除，750 PASS）；
  pytest 50 passed；py_compile 通过。

### v0.76（2026-10-26）重启重建 first_zt 修复：不阻塞 / 破板可重建 / ms 口径修正
- 背景：14:49 盘中重启日志仅出现 `[restart-rebuild] 登记待重建首触 59 家`，之后无任何
  `恢复首触`；14:50-14:59 仍大量 `state=first(src=tx)` 下午补记（大名城 `tx_ms=14:26:03` 等）。
- 根因：`_rebuild_first_zt_tick` 每帧固定取 `pending[:5]`，对 spot 缺失（`last<=0`/`up_px<=0`）
  或当前未封板的票直接 `continue`，不设重试也不推进队列；候选来自 watch+static 全部，
  tick 帧只对 `_tick_targets()` 做快照，多数候选 `g.spot` 无数据，前 5 只卡住即永久阻塞。
  同时 `first_ts`（逐笔首笔时间）被直接当作涨停首触 ms，会把盘中票的首笔成交误记为涨停首触。
- 修改：
  - 重建不要求“当前仍封板”：只要有 `up_px` 即回看最早涨停价成交，破板票也能补当日首触。
  - 缺 `up_px` 的票先批量补快照（一次 RPC），仍缺则 30s 重试，冷却票不占单帧 cap，
    队列不再被无快照票永久阻塞。
  - `ms` 只取 `_parse_tx_zt_ms` 最早涨停价成交；失败才降级快照 `hsTimeStamp`，
    记录 `src=restart_rebuild_fallback`；不再使用 tickdir `first_ts`。
  - 新增 60s heartbeat `[restart-rebuild] pending=N done=M wait=W` 与逐笔失败告警。
  - `handle_data` 1m 兜底消化重建队列（`restart_rebuild_1m_enabled=True`），tick 禁用/丢帧仍可恢复。
- 新参数：`first_zt_rebuild_heartbeat_sec=60.0`、`restart_rebuild_1m_enabled=True`。
- 验证：`tests/test_buysell_core_exp_direction.py` 新增 5 个 v0.76 用例并修订 2 个旧口径用例（50 passed）；
  py_compile 通过。重传云端后重启应见 `[restart-rebuild] 恢复首触 ... src=restart_rebuild`，
  且下午不再出现 `state=first(src=tx)` 补记。

### v0.75（2026-10-26）盘中定期保存 / 重启重建 first_zt / 全链路剔除 ST
- 背景：12:52 盘中重启后，上午已首触票（海量数据、良品铺子、和泰机电等）13:00-13:05
  被重新识别 `state=first(src=tx)`，`tx_ms` 只回看最近 200 笔窗口，拿不到上午真实首笔；
  同时 scan/watch/near 仍可能收录 ST。
- 修改：
  - A 盘中定期保存：`state_save_interval=60.0`，`handle_data` 帧末节流 `_save_state()`，
    `first_zt/l2_big/买卖标记`持续落盘，重启恢复到分钟级而非事件级。
  - B 重启重建 first_zt（首次实现，队列阻塞与 ms 口径由 v0.76 修复）：`_l2_big_seed` 累计器记录 `first_ts`；`before_trading_start`
    同日重启分支调 `_rebuild_first_zt_queue()` 登记缺失首触票（排除 ST），tick 帧按
    `first_zt_rebuild_cap=5` 分批 `_rebuild_first_zt_tick()`；ms 优先级：
    tickdir `first_ts`（>=09:30）→ `get_individual_transaction` 批量回看 → 快照
    `hsTimeStamp`；失败 30s 重试；记录 `src=restart_rebuild`，幂等不重复补录。
  - C 全链路剔除 ST：`skip_st_pool=True`，`_is_st()` 优先 `zt_lianban.is_st`、
    名单外名称前缀兜底并按交易日缓存；`_warm_name_map()` 批量预热名称（一次列表 RPC）；
    应用到 `_scan_market/_tick_targets/_tick_seed_cands/_sync_pool_static/_pool/重启重建`；
    持仓 ST 保留在 `pos` 卖出监控。
- 验证：`tests/test_buysell_core_exp_direction.py` 新增 7 个 v0.75 用例（45 passed）；
  `selftest_exp_rt.py` 全量 ALL DONE；py_compile 通过。
- 待重传：v0.73+v0.74+v0.75+v0.76+v0.77 一起打包重传 strategy.py，核对日志首行
  `buysell_core init version=v0.77`；盘中核对 `[restart-rebuild]` 只在重启后出现、
  `market_scan`/near 不含 ST、再次重启 first_zt 不重复补录。

### v0.74（2026-10-26）首笔灵敏度：near_scan 近涨停快速通道 + 帧内最早一笔
- 背景：10-26 日志 `market_scan bar=10:31 pool=5224 watch=6 off=300 cap=300`，`scan_batch=300` 每分钟只扫 300 只，
  全市场一轮约 17 分钟；新发酵票首触滞后 5-17 分钟（良品铺子 `tx_ms=10:17:58`、`[firstzt] 10:35:02`），
  主导瓶颈是候选池覆盖滞后而非帧内 ms 精度。
- 修改：
  - `scan_batch 300 -> 600` + 开盘 10 分钟热点优先（`scan_hot_first=True`）：昨日涨停/自选/预期/固定池先扫，
    开盘 10 分钟扫完全市场一轮（6000>=5224），黄金窗口不再等 17 分钟轮询。
  - `near_scan` 近涨停快速通道：`_scan_market` 命中 `chg>=scan_near_chg(7.0)` 或贴板即入补充池，
    跨轮保留 `scan_near_keep_rounds=3`，上限 `scan_near_cap=20`；已 `first_zt` 移出，`market_scan` 日志加 `near=N`。
  - `_tick_targets`：`near_scan` 未首触票排在 watch 前纳入 3s 帧目标，上限 `tick_near_cap=12`；
    新票从 7% 起被盯住，达 `up*0.98` 立即拉逐笔回看最早一笔。
  - `_tick_seed_cands`：L2 播种候选 = 逐笔 near + near_scan 未首触票（未到 0.98 也补历史大单）。
  - `_tx_frame_zt_ms`：多行 DataFrame/Series/沙盒 iloc 改为扫描最早一笔涨停价成交（原取 `iloc[-1]`）；
    `tx_zt_batch` 帧推送命中票用同帧 raw 回填更早 ms（0 额外 API）。
- 验证：`tests/test_buysell_core_exp_direction.py` 新增 6 个 v0.74 用例（38 passed）；
  `selftest_exp_rt.py` 全量 ALL DONE；T47 沙盒 DataFrame 形态同步覆盖。
- 已并入 v0.75 重传包，核对日志首行 `buysell_core init version=v0.75`。

### v0.73（2026-10-26）首帧误弃/一字重标/竞价唯一可信门/L2 逐票播种
- 背景：10-26 实盘发现四类失真——一字封死与开盘数秒票被 `below_vwap` 首帧永久误弃；一字票仍按普通超预期路径走；
  竞价板块映射未就绪时竞品=0 造成“假唯一”；核心苗子 L2 首帧无播种历史，把“无数据”误读为“无大单”。
- 修改：
  - `_below_vwap_confirm`：贴板豁免（`px>=up*0.998`）、首帧宽限 `vwap_weak_grace_sec=30`、连续弱
    `vwap_weak_confirm_sec=6` 两帧确认才弃，恢复即清 pending，允许回封恢复；`_eval_intraday` 与 `_exp_rt_status` 统一消费。
  - `_resync_buy_entry_type`：开盘按现价重标 buy 候选 `one_word/normal`，一字走封单三态分支（防 below_vwap 误弃）；
    持仓卖出侧不重标。
  - `_dyn_unq_auction_eval`：概念板块映射失败 `mapped=False` 不判唯一（防竞品=0 假唯一），
    `dyn_unq_require_board_map=True`；竞价唯一成员上限 `dyn_unq_auction_member_cap=15`。
  - `_l2_big_seed_onjoin` 改逐票节流：每票首见即种、空结果下帧重试、单帧上限
    `l2_big_seed_onjoin_max_per_frame=5`；tick 首封瞬间未播种补种；播种后补打 `[l2-big-seed]` 摘要。
- 纪律不变：技术三态 `CX/CM/PM/CS` 仍是硬条件，方向分不能升级 `PM/CS`；仓位比例与 10:00 后降频缩放不变。
- 验证：`tests/test_buysell_core_exp_direction.py` 新增 10 个 v0.73 用例（32 passed）；
  `selftest_exp_rt.py` T94 版本同步通过，T117 更新为逐票节流口径，全量 ALL DONE。
- 已并入 v0.74 重传包，核对日志首行 `buysell_core init version=v0.74`。

### v0.72（2026-10-26）watch 阶段方向分预确认：样本不足不再抹零
- 背景：v0.71 首日实盘（10-26）`lb_senti` 开盘 30 分钟停留在 `watch`（中高位触板样本不足），
  `_exp_direction_eval` 对 watch 一律输出 `neutral`，27 条 `[exp-dir]` 全部 `score=0.0`，早盘方向分失效。
- 修改：`watch` 阶段仍按「静态 unique_high / 动态唯一龙头 / 已确认发酵前排」输出 `attack_high / attack_low`
  （reason 分别记 `origin_leader_watch_preconfirm / new_theme_front_watch / theme_ferment_front_watch`），
  `watch` 不做 `hard_skip`，避免样本不足误杀早盘灵敏度。
- 纪律不变：`high_diverg / ice_wait` 明确阶段仍只放行低位；`rotate_low` 仅允许原题材唯一存活龙头例外；
  仓位 `board_buy_budget_ratio / exp_order_pct` 与 `size_mult=1.0` 不变；技术三态 `CX/CM/PM/CS` 仍独立，
  方向不能把 `PM/CS` 升级为买入。
- 验证：`tests/test_buysell_core_exp_direction.py` 新增 7 个 watch 预确认/纪律场景（静态/动态唯一龙头、
  新题材前端、存量题材前端、watch 普通中位股 neutral、ice_wait/high_diverg 中位仍 avoid），合计 21 项通过。

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
