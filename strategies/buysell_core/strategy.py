# -*- coding: utf-8 -*-
# ============================================================
# 当前版本：v0.47（2026-10-22）（前一版 v0.43 存档 1eea218）
# 部署核对：日志首行 `buysell_core init version=v0.47 ...`（init 打印 STRATEGY_VERSION）
# 最近变更：v0.36e 概念板块口径+灵敏度（合并快照/两段式surge/预算24）
#          v0.36g 盘中重启重建涨停池/自选三态（防 expect_buy 45->12 丢失）
#          v0.36h 待上传根目录只留 *_latest（dated 全移 archive）
#          v0.36i 统一买卖信号结构化 [signal]（采集器按日入库/对账）
#          v0.36j 文件头版本号注释 + init 日志打版本（部署核对）
#          v0.37 中位/主动/唯一性稳健性修复（docs/33）：a) 最快拉升判快改逐笔毫秒归一(_first_zt_ms)；
#                b) 首板闸门比较宇宙切概念文件口径(_board_member_codes)；c) 板块内涨幅最高批量回填快照；
#                d) zt_lianban 追加权威唯一列(unique_high/follower_count, AXquant 同源预计算)云端读列优先。
#          v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（docs/30）：A 动态唯一(首触无更高/并列身位)；
#                B 跟风确认(首触300s窗口内 同板块身位更低未封板成员 1m surge>=1.5% 达2家)；
#                C 排序加分/CX标注/持有提示；D 竞价唯一(同身位竞品不及预期)+开盘上攻冲板+跟风确认
#                +现价<涨停价 -> 涨停价扫板(预算20%, 避免买不到)；已封板/一字不扫。
#          v0.39 预期文件补股票名列（CSV/JSONL 贯通）+ 预期源对接 ShareData 共享目录
#          v0.40 from-jsonl 自动兜底并入 ShareData 预期源（含可用性闸门防空文件抢占）
#          v0.41 情绪温度消费统一全市场红盘比口径（_market_red_ratio 全量分片/独立 market 预算）
#                + emotion 档位接入仓位上限（冰点/偏冷40%、回暖/发酵80%、高潮/过热taper，冲突取保守）
#          v0.42 一字板竞价终态精确判定（docs/29）：真一字=开=涨停价且卖1=0(total_offerqty==0)才标 one_word；
#                + 竞价终态封单基准回填(seal_base，_exp_one_word 首帧即判) + 09:30 首帧补标(防 09:25 漏标)；
#                卖1>0 打 [seal] playable(非真一字, 可参与) 日志；1帧内封涨停放行（不扩大拦截）
#          v0.43 买卖操作理由与灵敏度日志固化（docs/30）：_signal 结构化行补 lag=检测->下单时延 + det=检测源:首触毫秒；
#                [may-order]/[exp-order]/order sent 同补 lag；after_trading_end 打 [rt-summary] 日结（按 side/mode）
#          v0.44 合成数据消费审计（docs/40）：_warm_cap 显式消费 sentiment.divergence 分歧标志，
#                与 warm_days 双保险触发分歧保护 taper，修复生成侧 divergence 列云端未被消费的脱节
#          v0.45 云 LogEngine 无 .warn 兼容（_warn 封装 warning->warn->info 兜底不抛，
#                修复 qty<=0 skip 分支与 except 二次崩溃导致 tick_data 链路中断）
#          v0.46 首板封单下限 + 唯一预判身位统一（docs/33）：_try_first_board_buy 补 first_board_seal_min
#                (L2 买一挂单金额, 防假封秒炸)；_dyn_unq_auction_eval 跳过中位股(与 _mid_board_avoid 统一口径)
#          v0.47 灵敏度收紧（docs/33）：A L2 大单占比加分（逐笔 business_amount 按 trade_index 去重累计，
#                >=10% 加分5分/封单豁免）；B 强度前三板块成员并入 tick 目标集 + scan_interval 4->1 + [scan] 探针；
#                C 预封扫板=封单下限 或 大单加持 二者满足其一
# ============================================================
# buysell_core —— Ptrade 托管「高可靠买卖子集」迁移骨架（v0.4）
# 依据：docs/16 + docs/18；AXquant 真实参数取自 D:/PROJ/AXquant/axquant/strategy
#   (decision/sell.py, decision/__init__.py, scorer/*, btree/builder.py ma_pullback)
# v0.4 把 score_now 做成真实版（结构等价，数据用 Ptrade 内置接口近似）：
#   分 = clamp(base40 + 静态加分 - 静态扣分 + 攻击加分 - VWAP扣分 + 外内盘, 0..92)
# 兼容国金：run_daily(context,func)+回调单参；log 先 % 拼单字符串；禁用 os。
# 只读安全：DO_ORDER=False 不发真单，仅记 [may-order]。
# v0.15 对齐 AXquant 买卖逻辑核心：1) 一字板封单超预期不参考排单（封死涨停不排队买入）；
#   2) 竞价核卖 P2E：预期已确认 miss/degraded -> 清仓；3) 弹性追高买入价 300/688 前收*1.10 上限（打板豁免）。
# v0.16 节奏：新增 09:25 auction_pre_confirm（重读9:20上传预期文件+竞价终态初步确认超预期->观察，不买）+09:31兜底重读。
# v0.17 供方数据健壮性：A)负基昨日开盘也判高开；B)预期基准缺失/<=0不超预期不误弃(防过触发)；云端1d历史折算昨日开盘与达标基准兜底；C)供方CSV缺失字段输出空串。
# v0.28 涨停池合成过滤 ST（消费 zt_lianban 的 is_st 字段，对齐 AXquant 复盘口径）；盘前一键脚本 run_one_click_premarket.py（生成+校验+上传勾选，docs/39）。
# v0.29 情绪冰点→回暖链（docs/40）：本地生成 sentiment CSV（T 日冰点+连续冰点天数）盘前读入；红盘比恢复判回暖，冰点越久恢复阈值越低（回暖概率增加）。
# v0.30 情绪仓位上限（docs/40 闭环）：连续回暖增加分歧概率；冰点日最大总仓位 40%，回暖日 80%（连续回暖 N 日起递减，分歧保护），买入路径统一拦截。
# v0.14 预期买入两阶段（T+1，side=buy 且预期超预期）：
#   1) 竞价终态初步确认「竞价超预期」-> 观察（不买）；2) 分时确认超预期(两分钟上攻 或 一分钟冲涨停,且不破VWAP) -> 执行买入。
#   tick_data 3s 事件触发 + 一次触发持久化去重(exp_fired) + 独立 EXPECT_ORDER 实盘门控。
import time, pickle, csv
from datetime import timedelta

STRATEGY_VERSION = "v0.47"   # 部署核对：日志首行 buysell_core init version=.. （2026-10-22）


def _warn(msg):
    # 云 LogEngine 无 .warn：有 warning 用 warning，否则退 info，绝不抛（防链路中断）
    _lb = getattr(log, "warning", None) or getattr(log, "warn", None)
    try:
        if _lb is not None:
            _lb(msg)
        else:
            log.info("[WARN] " + str(msg))
    except Exception:
        try:
            log.info("[WARN] " + str(msg))
        except Exception:
            pass


# ---------- 参数 ----------
BLS = {
    'DO_ORDER': False,
    'universe': ['600570.XSHG', '603528.XSHG', '601188.XSHG'],   # 占位自选池，待接全市场扫描
    'buy_score_min': 55.0, 'auction_buy_score_min': 50.0,
    'ma5_pullback': True, 'ma5_loose_high': 1.02, 'ma5_core_only': True,   # 5D线低吸仅对核心(CORE)标签股（对齐 AXquant CORE+低吸） 'ma5_require_bs': True,     # 对齐 AXquant：低吸还要 BS(100日新高)标签 'ma5_first_5d': True,       # 仅 5日内首次回踩 MA5（防重复低吸）
    'cold_secs': 60, 'daily_max_buy': 1,
    # 实盘单门控（v0.13）：仅放行「预期买入」路径；其余买入仍受 DO_ORDER 门控
    'EXPECT_ORDER': False,          # True = 预期买入发真实 order()（模拟盘小额测试）
    'tick_exp_enabled': True,       # 预期买入走 tick_data 3s 事件触发（敏捷）
    'exp_order_pct': 0.10,          # 预期买入单笔仓位比例（预算规则「打板20%、其它10%」；实盘测试可调小，如 0.01）
    'buy_chase_pct': 0.008,         # 追高分时确认买入：限价较现价上浮比例（防过度追高）
    'price_precision': 2,           # A股限价单价格精度（取整 2 位小数）
    'green_open_drop': -5.0,          # P1 绿开核卖：竞价跌幅 % <= -5
    'debug_score': True,            # 回测/交易观察：定时 dump 评分明细
    'debug_interval': 4,            # 每 N 根 bar dump 一次评分
    # 全市场入池扫描（候选 B；失败回退 universe）
    'scan_enabled': True,
    'max_watch': 50,                # 入池上限标的数
    'scan_batch': 300,              # 一次 get_snapshot(列表) 的批规模（单向）
    'per_stock_cap': 60,            # 若列表不可用，逐只扫描上限
    'scan_min_chg': 3.0,            # 入池最小涨幅 %
    # 预期三态（候选 D，docs/17）
    'fast_up_ratio': 0.01,          # two_1m 快速上攻：价站上 open*(1+r)
    'seal_exceed_ratio': 1.2,       # 一字板封单 >= 基准*1.2 -> 超预期
    'sell_half_ratio': 0.5,        # P6 评分半仓：卖 可卖数量×比例（整手取整）
    'sell_cold_secs': 30.0,        # 卖出冷却：成交回报驱动的去重备用（未成交防叠单）
    'sell_urgent_floor': 1,        # 核卖(P1/P2E/P3)限价用跌停地板价, 保证下跌中成交(对齐AXquant核卖limit_down_price)
    'limit_down_main': 0.10,       # 主板跌停幅
    'limit_down_chinext': 0.20,    # 创业板/科创板 20cm
    'limit_down_bse': 0.30,        # 北交所 30cm
    'sell_pending_timeout': 120.0, # 卖单挂起超时无回报 -> 视为丢失, 放行重试(对齐AXquant order_lost)
    'seal_fail_ratio': 0.333,       # 封单衰退：<= 基准*(1/3) -> 破
    'firstzt_min_seal': 50000.0,      # 首此涨停上报最小封单额(元)，过滤假封
    'firstzt_min_bids': 5,            # 首此涨停上报最小买一挂单量(手)
    # 预期文件：AXquant 预期三态 csv（docs/25）
    'expectation_base': 'data/expectation_',
    'expectation_suffix': '.csv',
    'scan_interval': 1,             # 每 N 根 bar 触发一次全市场扫描（v0.47 收紧 4->1）
    'score_sell_clear': 30, 'score_sell_half': 50,
    # 止损按板块
    'stop_loss_pct': 0.05, 'stop_loss_chinext': 0.07, 'stop_loss_star': 0.08, 'stop_loss_bse': 0.10,
    'elastic_max_buy_pct': 0.10,      # 弹性追高 300/688 买入价前收*1.10 上限（打板豁免）
    'exp_sell_on_pending_miss': False, # P2E 竞价核卖：pending_miss 默认只记录暂缓，confirmed_miss/degraded 才卖
    'single_stock_cap': 0.30,          # 单支市值上限：买入后该股市值 <= 总资产×30%（AXquant single_stock_cap）
    'ordinary_buy_ratio': 0.10,        # 普通买入单笔=总资产×10%（AXquant ordinary_buy_ratio=1/10，替代硬编码0.3）
    'board_buy_budget_ratio': 0.20,    # 打板买入单笔=总资产×20%（AXquant board_buy_budget_ratio）
    'red_gate_enabled': False,         # 红盘比买入门（默认关；开启才要求板块红盘比>=red_ratio_buy_min 且情绪回暖，v0.29）
    'sentiment_enabled': False,        # v0.29 情绪回暖闸门（T-1 冰点基线存在时，红盘比恢复才放行）
    'sentiment_warm_base': 0.55,       # 回暖恢复阈值基准（对齐 red_ratio_buy_min）
    'sentiment_warm_decay': 0.02,      # 每多 1 天冰点，恢复阈值降低（回暖概率增加）
    'sentiment_warm_min': 0.45,        # 恢复阈值下限
    'sentiment_ice_ratio': 0.40,       # 盘中实时红盘比 < 此值 = 今日继续冰点
    'sentiment_pos_cap_enabled': True,   # v0.31 情绪仓位上限（总仓位：冰点40%/回暖80%，已默认启用，盘前/盘中均有 [pos-cap] 日志）
    'ice_pos_pct': 0.40,              # 冰点日最大总仓位
    'warm_pos_pct': 0.80,             # 回暖日最大总仓位
    'warm_taper_start': 3,            # 连续回暖/延续 >= N 日开始递减（分歧概率上升）
    'warm_taper_step': 0.10,          # 每多 1 个连续回暖日递减幅度
    'warm_taper_min': 0.50,           # 递减下限（分歧保护）
    'red_ratio_buy_min': 0.55,         # 红盘比下限（对齐 AXquant first_board_buy 回暖下限）
    # v0.41 全市场红盘比（情绪温度消费口径统一：冰点/回暖判定用全市场，替代个股板块近似；docs/16）
    'market_red_enabled': True,        # 全市场红盘比总开关
    'market_batch': 300,               # 全量分片 get_snapshot 批规模（与 scan_batch 一致）
    'market_red_ttl': 60.0,            # 全市场红盘比缓存 s（10:00 后）
    'market_red_ttl_fast': 30.0,       # 10:00 前快速刷新缓存 s（受单轮全量耗时下限约束，盘中探针校准）
    'frame_market_limit': 2,           # 帧内全市场红盘比 fetch 次数（独立预算源，不挤占实时快照）
    'frame_market_limit_fast': 4,      # 10:00 前
    # v0.41 emotion 档位 -> 总仓位硬上限（与规则 ice/phase 冲突时取保守值 + WARN）
    'emotion_cap_ice': 0.40,           # 冰点/偏冷
    'emotion_cap_warm': 0.80,          # 回暖/发酵
    'emotion_cap_taper': 0.50,         # 高潮/过热（分歧保护下限档）
    # v0.18 买入场景补齐：核心票买入 + 首板打板（AXquant first_board_buy / CORE 门禁）
    'core_buy_enabled': True,          # 核心票买入总开关
    'core_max_lianban': 6,             # 核心票连板上限：>=6 不追（高标不接）
    'core_sealed_skip': True,          # 核心票一字/封死涨停不排队买入
    'core_buy_window_min': 30,         # 核心票买入窗口：开盘 N 分钟内（10:00 前，其它类）
    'ma5_buy_window_min': 60,          # 5日低吸窗口：开盘 N 分钟内（10:30 前 = 60 分钟）
    'exp_buy_window_min': 30,          # 预期买入窗口：开盘 N 分钟内（10:00 前，其它类）
    'pool_expect_enabled': True,         # v0.27 涨停池预期三态初步确认（竞价超预期->观察，窗口内分最高/最主动优先）
    'pool_expect_skip_st': True,         # v0.28 涨停池合成过滤 ST（is_st 字段消费）
    'first_board_buy_enabled': True,   # 首板打板总开关（tick 首触主路径 + 1m 兜底）
    'first_board_minute': 10,          # 首板闸门：开盘 N 分钟内（09:30-09:40）
    'first_board_seal_min': 50000.0,   # 首板打板最小封单额(元)（与 firstzt 门槛一致）
    'dyn_unq_mid_skip': True,          # v0.46 竞价唯一预判跳过中位股（与 _mid_board_avoid 统一口径）
    'l2_big_enabled': True,            # v0.47 L2 大单占比（近涨停候选逐笔累计）
    'l2_big_amt_min': 1000000.0,       # 单笔大单阈值(元)
    'l2_big_ratio_min': 0.10,          # 大单占比>=10% 加分/封单豁免
    'l2_big_bonus': 5.0,               # 大单占比达标加分(分)
    'l2_big_seen_cap': 20000,          # 去重序号上限（防累计无限膨胀）
    'tick_board_scan': True,           # v0.47 B1: tick 目标并入强度前三板块成员
    'tick_board_member_cap': 20,       # 每板块并入成员上限
    'first_board_bids_min': 5,         # 首板打板最小买一挂单量(手)
    # v0.19 弹性套利 elastic_arb（AXquant Phase 1）
    'elastic_arb_enabled': True,       # 弹性套利总开关
    'elastic_arb_window_minute': 30,   # 仅开盘后 N 分钟内（09:30-10:00，其它类 10:00 前）
    'elastic_arb_min_yizi': 2,         # 板块一字板>=N 情绪爆发（对齐 elastic_arb_min_yizi）
    'elastic_arb_min_1m_surge': 3.0,   # 最新 1m 柱 (close-open)/open >= N% 大阳线
    'elastic_arb_min_change': 6.0,     # 当前涨幅下限 %
    'elastic_arb_max_change': 10.0,    # 当前涨幅上限 %（防炸板）
    'elastic_arb_max_open_change': 12.0, # 开盘涨幅上限 %（防大幅高开兑现）
    'elastic_arb_cache_ttl': 60.0,     # 板块一字板统计缓存 s（按日重置）
    'gear_cache_ttl': 3.0,           # L2 十档盘口帧级缓存 s（打板/弹性共用，避免同帧多次 get_gear_price）
    'm1_surge_cache_ttl': 30.0,      # 弹性 1m 大阳线缓存 s（v0.36e 30s： surge 只算前N后窗口内避免重复拉取）
    # v0.20 L2 逐笔首笔成交感知（打板首触灵敏度 <=3s）
    'firsttx_enabled': True,          # L2 逐笔涨停价成交 -> 首触确认 总开关
    'firsttx_near_px': 0.98,          # 现价>=涨停价*该比例 才拉逐笔（控 API 负担，避免全池逐笔轮询）
    'firsttx_data_count': 200,        # 每次拉取逐笔成交条数（最大200）
    # v0.23/v0.24 板块强度排名：打首板/弹性套利的目标 = 强度前三板块
    'board_rank_enabled': True,       # 强度前三板块门控总开关
    'board_rank_top_n': 3,            # 取强度前 N 名板块
    'board_rank_cache_ttl': 60.0,     # 板块强度/排名刷新周期 s（10:00 后）
    'board_rank_ttl_fast': 3.0,       # 10:00 前板块强度/排名刷新周期 s（与 tick 同频）
    'board_rank_fast_until_minute': 30,  # 快速刷新截止：开盘 N 分钟内（09:30+N，10:00）
    # v0.25 Phase 3 帧级拉取预算（tick_data 每 3s 一帧，超限按优先级降级）
    'budget_log_enabled': True,       # 帧末输出 [budget] 统计
    'frame_snapshot_limit': 2,        # 帧内批量快照批次（1 批量+1 兜底）
    'frame_snapshot_fallback_cap': 5, # 批量缺标逐只兜底上限
    'frame_tx_limit': 1,              # 帧内逐笔批量拉取（3s token 已限 1）
    'frame_gear_limit': 15,           # 帧内 get_gear_price 总次数
    'frame_m1_limit': 20,             # 帧内 1m K线 get_price 总次数（two_1m/弹性 surge 共用）
    'frame_hist1d_limit': 10,         # 帧内 1d 历史 get_price 总次数
    'frame_board_limit': 6,           # 帧内板块强度组（get_industry_stocks+get_snapshot 各 1 次/组）
    'frame_blocks_limit': 10,         # 帧内 get_stock_blocks 总次数（300s 缓存后≈0）
    'frame_bcode_limit': 20,          # 帧内板块归属（3600s 缓存后≈0）
    # v0.36 帧预算快速期放大 + 高优先级独立配额（docs/24 §25）：10:00 前与 3s 帧同频，防候选多时排名/确认滞后
    'frame_board_limit_fast': 24,     # 10:00 前板块强度组限额（平时 6；v0.36e 合并快照每帧一批=1次 RPC，放大供多板块并集续算）
    'frame_m1_limit_fast': 30,        # 10:00 前 1m K线限额（平时 20）
    'frame_m1_prio_limit': 15,        # 预期分时确认 two_1m 独立配额（高优先级，不挤占弹性 surge）
    'frame_blocks_limit_fast': 20,    # 10:00 前板块全列表归属预算（_boards_of 新最强板块用）
    'frame_day_limit': 8,             # 帧内 1d 日线 get_price 次数（板块5日强度续算）
    'frame_day_limit_fast': 12,       # 10:00 前日线预算放大
    # v0.36 弹性套利：当日新最强板块第一时间跟踪（最主动弹性标的，10% 前买入）
    'elastic_top_enabled': True,
    'elastic_top_window_minute': 30,  # 新最强板块弹性跟踪窗口：10:00 前
    'elastic_top_min_strength': 2.0,  # 新最强板块强度阈值 %（候选池内第一，>=2%）
    'elastic_top_min_1m_surge': 2.0,  # 最主动弹性标的 1m 大阳线下限 %
    'elastic_top_buy_before_pct': 10.0,  # 10% 涨幅前买入
    'elastic_top_cache_ttl': 30.0,    # 板块内弹性候选排序缓存 s
    'elastic_top_surge_top_n': 5,     # v0.36e 弹性候选 surge 只算前 N（批量快照按涨幅粗排后）
    'elastic_top_member_cap': 20,     # v0.36e 概念板块强度/开盘涨幅成员样本上限（对齐旧 [:20]）
    'frame_snap_batch': 100,          # v0.36e 帧内合并快照成员批上限（概念板块并集分帧续算）
    # v0.36b 新爆发板块确认因子：T日开盘板块涨幅 明显强于 自身平均5日强度（docs/36 §9）
    'elastic_top_breakout_min_open': 1.0,   # 开盘板块涨幅自身下限 %
    'elastic_top_breakout_min_boost': 2.0,  # 开盘涨幅 - 5日均强度 的最小增强 %
    'elastic_top_max_trigger_per_day': 2,   # 当日「新最强板块」触发（易主）上限
    # v0.36c 稳定性：连续 N 帧保持第一才触发/易主；top1-top2 领先幅度门槛（防并列/紧咬）
    'elastic_top_stable_frames': 3,     # top1 需连续 N 帧保持第一（3s 帧 ≈9s）
    'elastic_top_lead_min': 0.5,        # top1 强度 - top2 强度 最小领先 %（防并列/紧咬误判）
    'board_probe_enabled': True,        # 盘中探针：get_stock_blocks 全类别 + get_industry_stocks HY/GN 返回量
    # v0.26 tick 级卖出（事件驱动：3s 帧末响应炸板/封单大减/急卖；docs/33）
    'tick_sell_enabled': True,       # tick 级卖出总开关
    'break_sell_enabled': True,      # 炸板卖出：first_zt.break 首触发 -> 卖
    'seal_low_sell_enabled': True,   # 封单大减卖出：first_zt.seal_low 首触发 -> 卖
    'sealed_fresh_secs': 5.0,        # 封死判定持续 N 秒才生效（防瞬时零卖盘误判不排单）
    'sealed_offerqty_enabled': True, # 用 total_offerqty==0 判封死（快照总委卖量；缺失回退 ask_grp 空判）
    # 打分引擎（AXquant 默认）
    'score_base': 40, 'score_max': 92, 'score_min': 0,
    'vwap_penalty_per_30s': 1.0, 'vwap_daily_limit': 12,
    # 预期角色容忍度（AXquant sell_policy_hint 迁移，docs/17）：绿开/止损/评分阈值缩放系数
    'sell_policy': {
        'hold_higher_tolerance': {'green_tol': 2.5, 'stop_adj': 1.3, 'score_clear_adj': 0.6, 'score_half_adj': 0.8},
        'fast_exit_on_weak':     {'green_tol': 0.5, 'stop_adj': 0.8, 'score_clear_adj': 1.05, 'score_half_adj': 1.0},
        'watch_break_sell':      {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 0.9, 'score_half_adj': 1.0},
        'break_weak_escape':     {'green_tol': 0.6, 'stop_adj': 0.7, 'score_clear_adj': 1.1, 'score_half_adj': 1.0},
        'vwap_follow':           {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
        'none':                  {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
    },
    # v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（P2，docs/30）
    'dyn_unq_enabled': True,            # 盘中动态唯一+跟风确认 总开关
    'dyn_unq_window_minute': 30,        # A/B/C 生命周期：09:30-10:00
    'dyn_unq_follow_win_sec': 300,      # 跟风确认窗口：龙头首触后 300s
    'dyn_unq_member_cap': 15,           # 同板块成员批量快照上限
    'dyn_unq_surge_top_n': 5,           # 涨幅前 N 算 1m surge
    'dyn_unq_follower_min': 2,          # 跟风确认最少家数
    'dyn_unq_surge_pct': 1.5,           # 跟风 1m 拉升阈值 %
    'dyn_unq_sort_bonus': 2.0,          # 确认龙头排序加分（_pool_exp_priority）
    'dyn_sweep_enabled': True,          # 竞价唯一扫板 开关
    'dyn_sweep_window_minute': 15,      # 扫板窗口 09:30-09:45
    'dyn_sweep_budget_ratio': 0.20,     # 扫板单笔预算（=打板 20%）
}
# 打分加减分配置（scoring.bonus.* / scoring.penalty.* 默认）
BONUS = {
    'auction_beat_history': 5, 'touched_limit_up_early': 6, 'volume_ratio_shrink': 2,
    'is_100day_high': 10, 'tag_bs': 5, 'tag_core': 5, 'tag_lb': 5,
}
PENALTY = {
    'open_low_5': 15, 'open_low_2': 8, 'open_low_0': 3, 'board_weak': 8,
}
ATK = {'a1': 6.0, 'a2': 3.0, 'a3': 2.0, 'main_threshold': 0.08, 'elastic_threshold': 0.15}


def _sn(sec):
    # 日志补全：证券代码后追加股票名称（get_stock_name），失败回退原代码。带 g._name_map 缓存。
    sec = str(sec or '')
    if not sec:
        return sec
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    if sec not in nm:
        try:
            _got = get_stock_name(sec)
            nm[sec] = str(_got or '').strip()
        except Exception:
            nm[sec] = ''
    return ('%s(%s)' % (nm[sec], sec)) if nm[sec] else sec

def _snl(codes):
    # 代码列表 -> [code|名称]（init universe / restore / end bought=sold 等登记日志补全名称）
    return [_sn(c) for c in (codes or [])]

class DataHub(object):
    # 聚合数据源薄层（v0.21）：帧首批量快照 + 统一 TTL 缓存注册表 + 失败隔离/降级标记。
    # Module-level singleton (NOT attached to g): engine pickles g on save, classes in g break pickle
    # 避免在 initialize/日切/盘中拉起多处手动清缓存。保持现有过程式函数签名兼容。
    def __init__(self):
        self.cache = {}        # (source, sec) -> (ts, value)
        self.degraded = set()  # 已降级数据源（失败隔离标记）
        self._day = ''
        self.frame = {'token': -1, 'used': {}, 'over': {}}   # v0.25 帧账本：3s 帧内各源调用计数/超限数

    def reset(self, day=None):
        self.cache.clear(); self.degraded.clear()
        self.frame = {'token': -1, 'used': {}, 'over': {}}
        if day is not None:
            self._day = day

    def _maybe_reset(self):
        try:
            day = str(get_trading_day())
        except Exception:
            day = ''
        if day and day != self._day:
            self.cache.clear(); self.degraded.clear(); self._day = day
        token = int(time.time() / 3.0)
        if token != self.frame['token']:
            self.frame['token'] = token
            self.frame['used'] = {}
            self.frame['over'] = {}

    def spend(self, source, n=1, prio=0):
        # 帧预算记账：超限返回 False（不阻塞，调用方按优先级降级）；配额内返回 True。
        # prio=1 走独立高优先级配额（frame_<source>_prio_limit），高优先级消费不挤占普通配额
        self._maybe_reset()
        key = '%s_p' % source if prio else source
        limit = _source_limit(source, prio)
        used = self.frame['used'].get(key, 0) + n
        if used > limit:
            self.frame['over'][key] = self.frame['over'].get(key, 0) + 1
            return False
        self.frame['used'][key] = used
        return True

    def frame_report(self):
        # 帧末统计：[budget] snapshot=1/2 tx=1/1 ... over:xxx=n
        parts = []
        for src, used in sorted(self.frame['used'].items()):
            base = src[:-2] if src.endswith('_p') else src
            if src.endswith('_p'):
                lim = BLS.get('frame_%s_prio_limit' % base, BLS.get('frame_%s_limit' % base, 'inf'))
            else:
                lim = BLS.get('frame_%s_limit' % base, 'inf')
            parts.append('%s=%d/%s' % (src, used, lim))
        over = self.frame.get('over') or {}
        if over:
            parts.append('over:%s' % ','.join('%s=%d' % (k, v) for k, v in sorted(over.items())))
        return ' '.join(parts)

    def cached(self, source, sec, ttl, fetch, budget=None, stale_ok=False, prio=0, single=False):
        # 统一缓存原语：命中直接返回；未命中调 fetch() 并缓存（含安全默认值）；
        # fetch 抛异常 -> 记 degraded、不缓存、返回 None（下一帧再试）；budget 超限按优先级降级：
        #   stale_ok=True（P1）回退旧值；P0 不缓存下帧重试。
        # prio=1 走高优先级独立配额；single=True 同源只保留最新一条（防 token 碎片累积）
        self._maybe_reset()
        if single and isinstance(source, tuple):
            prefix = source[0]
            for k in [k for k in self.cache
                      if isinstance(k[0], tuple) and k[0][0] == prefix and k != (source, sec)]:
                del self.cache[k]
        key = (source, sec)
        hit = self.cache.get(key)
        if hit is not None and (time.time() - hit[0]) < ttl:
            return hit[1]
        if budget and not self.spend(budget, prio=prio):
            if stale_ok and hit is not None:
                return hit[1]
            return None
        try:
            v = fetch()
            self.cache[key] = (time.time(), v)
            return v
        except Exception:
            self.degraded.add(source)
            return None

    def tx_zt_batch(self, secs, frame_data):
        # 近涨停候选逐笔涨停价成交统一入口：先帧推送（0 调用），缺者按 3s 帧 token 批量拉取一次；
        # 返回 {sec: 最早涨停价成交 ms}；up_px 消费时从 g.spot 取，避免缓存污染
        self._maybe_reset()
        secs = [s for s in (secs or []) if s]
        if not secs:
            return {}
        out = {}
        miss = []
        for sec in secs:
            ms = _tx_frame_zt_ms(sec, frame_data)
            if ms is not None:
                out[sec] = ms
            else:
                miss.append(sec)
        raw = self._tx_pull_raw(secs) or {}   # v0.47 全量拉（含帧推送命中, 供大单累计; 帧内缓存 0 额外 RPC）
        fields = raw.get('fields') or []
        for sec in miss:
            ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
            if ms is not None:
                out[sec] = ms
        try:
            _tx_big_feed(secs, fields, raw)   # v0.47 L2 大单累计（同帧 raw）
        except Exception:
            pass
        return out

    def _tx_pull_raw(self, secs):
        # 按 3s 帧缓存原始逐笔（同一帧多消费不重复拉）；异常 -> {}（不缓存，下一帧再试）
        token = int(time.time() / 3.0)
        return self.cached(('tx_pull', token), '_frame_', 3.0,
                           lambda: get_individual_transaction(secs,
                                                              data_count=int(BLS.get('firsttx_data_count', 200)),
                                                              is_dict=True) or {}, budget='tx') or {}

    def snapshot(self, secs):
        # 帧首批量快照：get_snapshot(列表) 一次回填 g.spot；批量缺标再逐只兜底（正常 0 次）
        self._maybe_reset()
        secs = [s for s in (secs or []) if s]
        if not secs:
            return {}
        got = {}
        if self.spend('snapshot'):
            try:
                sn = get_snapshot(secs)
                if isinstance(sn, dict):
                    got = sn
            except Exception:
                self.degraded.add('snapshot')
        fb_cap = int(BLS.get('frame_snapshot_fallback_cap', 5))
        _fb = 0
        for c in secs:
            d = got.get(c)
            if isinstance(d, dict):
                g.spot[c] = d
            else:
                if _fb >= fb_cap or not self.spend('snapshot'):
                    g.spot[c] = {}           # 兜底预算耗尽 -> 置空，与缺失一致
                    continue
                _fb += 1
                try:
                    one = get_snapshot(c) or {}
                    if isinstance(one, dict) and one:
                        g.spot.update(one)
                    else:
                        g.spot[c] = {}       # 批量/兜底均无 -> 置空，与原逐只行为一致
                except Exception:
                    g.spot[c] = {}
                    self.degraded.add('snapshot')
        return g.spot


def _source_limit(source, prio=0):
    # 帧预算限额解析（v0.36）：10:00 前走 _fast 档（对齐 _board_refresh_ttl 快速期）；prio=1 走独立高优先级配额。
    # gear 快速期无 _fast 键时动态按 tick 目标集数量（min(len(_tick_targets), 25)），防 watch 池大时 L2 封单采集缺。
    if prio:
        return float(BLS.get('frame_%s_prio_limit' % source,
                             BLS.get('frame_%s_limit' % source, 1e9)))
    fast = False
    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            fast = True
    except Exception:
        pass
    if fast:
        k = 'frame_%s_limit_fast' % source
        if k in BLS and BLS[k]:
            return float(BLS[k])
        if source == 'gear':
            try:
                return float(min(len(_tick_targets()), 25))
            except Exception:
                pass
    return float(BLS.get('frame_%s_limit' % source, 1e9))


_DS = None  # DataHub module-level singleton (not stored in g; avoids engine g-pickle save errors)

def _get_ds():
    global _DS
    if _DS is None:
        _DS = DataHub()
    return _DS

def initialize(context):
    set_universe(BLS['universe'])
    g.buy_log = {}; g.sold_log = {}
    g.daily = {'bought': [], 'sold': []}
    g.state_day = None   # 持久化的“交易日”戳（跨重启每日买入计数恢复）
    g.spot = {}; g.last_ma5 = {}
    _get_ds()  # DataHub singleton warmup (kept out of g)
    g.one_word_open = set()   # 09:25/开盘识别的一字板（买入不排队）
    g.one_word_marked_open = False   # v0.42 09:30 首帧补标去重（按日重置）
    g.rt_stats = {}   # v0.43 灵敏度日结采样（检测->下单时延，after_trading_end 打 [rt-summary]）
    g.l2_big = {}; g.l2_big_probed = set()   # v0.47 L2 大单累计（按日重置）
    g.hist = {}         # sec -> (ts, df)  1d 历史缓存
    g.bs_cache = {}     # sec -> (ts, board_strength)
    g.bs_codes = {}     # sec -> (ts, 板块成分代码)（首板闸门：板块内涨幅最高）
    g.first_board_fired = set()  # 首板打板当日去重（tick 首触 / 1m 兜底共用）
    g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}   # 弹性套利：板块一字板统计缓存（60s，按日重置）
    g.elastic_top = {'day': '', 'top': '', 'ts': 0.0, 'tracked': set()}  # v0.36 新最强板块弹性跟踪状态
    g.gear_cache = {}     # sec -> (ts, get_gear_price)  L2 十档帧级缓存
    g.m1_surge_cache = {} # sec -> (ts, 1m大阳线%)        弹性窗口缓存
    g.now_dt = None     # 当前 bar 时间（context.blotter.current_dt，回测/交易均可用）
    g.bar_counter = 0
    g.vwap_below_since = {}  # sec -> 连续低于VWAP计时起点(_sec_age值)；高于VWAP即移除(恢复归零)

    g.pool_all = []     # 全市场 A 股代码（按交易日刷新）
    g.pool_day = None
    g.watch = []        # 入池候选（动态，买入/打分迭代目标）
    g.selfwatch = []   # 手动/文件同步 自选股（实时同步 selfwatch.csv）
    g.pool_static = [] # 固定股池 = 自选股 ∪ 超预期确认推荐池(side=buy)
    g.last_scan = 0
    g.scan_offset = 0   # 全市场滑动窗口游标
    g.auction_c = {}    # sec -> (day, 竞价涨幅%)  候选 C 缓存
    g.exp = {}          # sec -> 预期三态状态（候选 D）
    g.exp_day = None
    g.seal_base = {}    # sec -> 当日首次封单量基准
    g.seal_bid_base = {}  # sec -> 当日首次封单委托笔数基准（L2）
    g.first_zt = {}     # sec -> 涨停首笔成交感知状态（tick_data，仅交易）
    g.dyn_unq = None    # v0.38 盘中动态唯一+跟风+扫板状态（按日重置，随 g 持久化）
    g.break_sold = set()  # sec -> 炸板事件卖出首触发标记（v0.26，跨重启持久化）
    g.seal_sold = set()   # sec -> 封单大减事件卖出首触发标记（v0.26）
    g.sealed_since = {}   # sec -> 封死状态持续计时起点（v0.26b，5s 新鲜度确认）
    g.zt_lianban = {}   # sec -> T-1 涨停/连板名单（AXquant limit_up_boards 导出, upload_file）
    g.exp_file = {}     # sec -> 预期文件条目（AXquant 竞价终态）
    g.exp_fired = set() # sec -> 本日已触发(买/放弃)的预期买入（一次触发+跨重启去重）
    g.pending = {}      # sec -> 已发送委托（成交确认前的去重/回执）
    run_daily(context, auction_pre_confirm, time='09:25')
    run_daily(context, after_open_probe, time='09:31')
    run_daily(context, mid_probe, time='11:00')
    log.info('buysell_core init version=%s universe=%s DO_ORDER=%s EXPECT_ORDER=%s' % (STRATEGY_VERSION, _snl(BLS['universe']), BLS['DO_ORDER'], BLS.get('EXPECT_ORDER', False)))


def before_trading_start(context, data):
    _set_now(context)
    load_state()
    _today = str(get_trading_day())
    _restart_same_day = False
    if getattr(g, 'state_day', None) == _today:
        _restart_same_day = True
        # 同日盘中重启：保留当日已买计数（跨重启恢复），sold 本就每日清
        g.daily = {'bought': [x for x in (g.daily.get('bought') or [])], 'sold': []}
        log.info('before_trading_start restore same-day daily=%s (restart)' % (_snl(g.daily.get('bought')),))
    else:
        g.daily = {'bought': [], 'sold': []}
        g.exp_fired = set()   # 跨日清空预期买入触发
    g.sealed_warn = set()
    g.state_day = _today
    _save_state()
    _load_expectation()
    _load_zt_lianban()
    _load_sentiment()
    try:
        _load_boards()   # v0.36d 板块映射文件（Step1 仅加载验证, docs/24 §26）
    except Exception:
        pass
    if BLS.get('sentiment_pos_cap_enabled', False):
        _s = getattr(g, 'sentiment', None)
        _sm = '无'
        if _s:
            _sm = 'ice=%d warm_days=%d phase=%s' % (int(_s.get('ice') or 0), int(_s.get('warm_days') or 0), _s.get('phase') or '-')
        log.info('[pos-cap] 已启用：冰点上限=%.2f 回暖上限=%.2f 连续回暖>=%d 起递减%.2f/日 下限=%.2f；当前情绪基线：%s'
                 % (float(BLS.get('ice_pos_pct', 0.40)), float(BLS.get('warm_pos_pct', 0.80)),
                    int(BLS.get('warm_taper_start', 3)), float(BLS.get('warm_taper_step', 0.10)),
                    float(BLS.get('warm_taper_min', 0.50)), _sm))
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    try:
        _board_probe()   # v0.36c 板块口径探针（每日一次，验证 HY/GN 被 get_industry_stocks 消费）
    except Exception:
        pass
    if _restart_same_day:
        try:
            _synth_pool_expect()        # v0.36g 盘中重启：重建涨停池三态（防 expect_buy 45->12 丢失）
            _synth_selfwatch_expect()   # v0.36g 盘中重启：重建自选股三态
            _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
        except Exception:
            pass
        try:
            _mark_one_word_open()   # v0.31c 盘中重启：重标一字板（免5s门槛不丢）
        except Exception:
            pass
    for sec in list(dict.fromkeys(BLS['universe'] + list(get_positions()))):
        df = _hist_1d(sec)
        if df is not None and len(df) >= 6:
            g.last_ma5[sec] = float(df['close'].iloc[-6:-1].mean())
    log.info('before_trading_start done positions=%s' % list(get_positions()))


def handle_data(context, data):
    _set_now(context)
    g.bar_counter += 1
    refresh_spot(context)
    if not getattr(g, 'one_word_marked_open', False):
        g.one_word_marked_open = True
        try:
            _mark_one_word_open()   # v0.42 09:30 首帧补标真一字（防 09:25 快照缺失漏标，开盘即拦截；不重置只累加）
        except Exception:
            pass
    if not getattr(g, 'l2_probed', False):
        try:
            _l2_probe(context)   # L2 探针兜底：盘中重启/开盘后拉起也会跑一次
        except Exception:
            pass
    if BLS.get('debug_score') and (g.bar_counter % BLS.get('debug_interval', 4)) == 0:
        dump_scores(context)
    if BLS.get('scan_enabled') and (g.bar_counter % BLS.get('scan_interval', 4)) == 0:
        _sync_watch(context)
    if BLS.get('selfwatch_enabled', True) and (g.bar_counter % BLS.get('selfwatch_sync_interval', 8)) == 0:
        _load_selfwatch(); _sync_pool_static()
    if g.exp_day != str(get_trading_day()):
        g.exp_day = str(get_trading_day())
        g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.sealed_since = {}; g.gear_cache = {}; g.m1_surge_cache = {}; _get_ds().reset(); g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set()
        for sec in list(get_positions()):
            _hold_exp_init(sec, force=True)   # v0.32 跨日重算持仓预期条目
    sell_manager(context)
    _try_expected_buys(context)
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if BLS['ma5_pullback']:
        try_ma5_buy(context)
    try_core_buy(context)
    _try_first_board_buy_1m(context)
    _try_elastic_arb_buy(context)
    try:
        _try_elastic_top_buy(context)   # v0.36 新最强板块弹性套利（1m 兜底）
    except Exception as e:
        _warn('elastic_top buy fail: %r' % e)
    try:
        _try_dyn_unq(context)            # v0.38 盘中动态唯一+跟风+扫板（1m 兜底，状态幂等）
    except Exception as e:
        _warn('dyn_unq(1m) fail: %r' % e)


# ================= 行情/工具 =================
def _hist_1d(sec):
    # 1d OHLCV 缓存（约 60s 有效，统一 DataHub 注册表）
    try:
        dh = _get_ds()
        return dh.cached('hist1d', sec, 60.0,
                         lambda: get_price(sec, start_date=None, end_date=None, count=120, frequency='1d'), budget='hist1d')
    except Exception:
        return None


def _ensure_ma5(sec):
    # 惰性算 MA5（watch/盘中入池才需要；1d 历史缓存，60s 内复用）
    if sec in g.last_ma5:
        return g.last_ma5[sec]
    df = _hist_1d(sec)
    if df is not None and len(df) >= 6:
        v = float(df['close'].iloc[-6:-1].mean())
        g.last_ma5[sec] = v
        return v
    return None


def refresh_spot(context):
    # 刷新 _pool()（watch 候选 or universe）+ 持仓快照；批量取，失败回退逐只
    secs = list(dict.fromkeys([x for x in (_pool() + list(get_positions())) if x]))
    if not secs:
        return
    try:
        snap_all = _get_snapshot_many(secs, len(secs))
    except Exception:
        snap_all = {}
    for c in snap_all:
        d = snap_all[c]
        if d:
            g.spot[c] = d


def last_px(sec):
    s = g.spot.get(sec)
    return float(s['last_px']) if s and s.get('last_px') else None


def pre_close(sec):
    s = g.spot.get(sec)
    return float(s['preclose_px']) if s and s.get('preclose_px') else None


def trade_open(sec):
    s = g.spot.get(sec)
    return not (s and s.get('trade_status') == 'ENDTR')


def my_cost(sec, positions):
    # 持仓成本：成本字段因柜台而异（docs/06），逐键探测容忍 str/int/float
    p = positions.get(sec)
    for key in ('cost_basis', 'cost_price', 'hold_cost_price', 'av_cost_price', 'avg_cost', 'cost'):
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is not None and str(v).strip() not in ('', 'None'):
                return float(v)
        except Exception:
            continue
    return 0.0


def get_stop_loss_pct(sec):
    if sec.startswith('300') or sec.startswith('301'):
        return BLS['stop_loss_chinext']
    if sec.startswith('688'):
        return BLS['stop_loss_star']
    if sec[:2] in ('43', '83', '87', '92'):
        return BLS['stop_loss_bse']
    return BLS['stop_loss_pct']


# ================= 实时打分（真实版，docs/16 三维标签 + 多维打分） =================
def score_now(sec):
    base = float(BLS['score_base'])
    bonus = _static_bonus(sec)
    penalty = _static_penalty(sec)
    atk = _attack_bonus(sec)
    vp = _vwap_penalty(sec)
    ei = _external_internal(sec)
    raw = base + bonus - penalty + atk - vp + ei
    raw += _l2_big_bonus_pts(sec)   # v0.47 L2 大单占比>=10% 加分
    raw = max(0.0, min(92.0, raw))
    if _is_debug(sec):
        log.info('score %s base=%.0f bonus=%.0f penalty=%.0f atk=%.0f vp=%.0f ei=%.0f -> %.1f' % (
            _sn(sec), base, bonus, penalty, atk, vp, ei, raw))
    return raw


def _is_debug(sec):
    return bool(getattr(g, 'debug_sec', None) == sec)


def _static_bonus(sec):
    # 开盘优于历史 +5、早盘触涨停 +6、缩量<0.6 +2、100日新高 +10、板块分档、标签 BS/CORE/LB +5
    b = 0.0
    if _auction_beat_history(sec):
        b += BONUS['auction_beat_history']
    if _touched_limit_early(sec):
        b += BONUS['touched_limit_up_early']
    if _volume_ratio(sec) < 0.6:
        b += BONUS['volume_ratio_shrink']
    if _is_100day_high(sec):
        b += BONUS['is_100day_high']
    b += _board_bonus(sec)
    tags = _tags(sec)
    if 'BS' in tags: b += BONUS['tag_bs']
    if 'CORE' in tags: b += BONUS['tag_core']
    if 'LB' in tags: b += BONUS['tag_lb']
    return b


def _static_penalty(sec):
    p = 0.0
    chg = _auction_change(sec)              # 低开梯形扣分（用开盘近似竞价）
    if chg < -5.0: p += PENALTY['open_low_5']
    elif chg < -2.0: p += PENALTY['open_low_2']
    elif chg < 0.0: p += PENALTY['open_low_0']
    if _board_strength(sec) < -2.0:          # 板块走弱
        p += PENALTY['board_weak']
    return p


def _attack_bonus(sec):
    # 9:30-9:35 +6 / 9:35-9:45 +3 / 9:45-10:00 +2，主板涨停逼近（涨幅>=8%）
    px = last_px(sec); pre = pre_close(sec)
    if not px or not pre or pre <= 0:
        return 0.0
    chg = px / pre - 1.0
    if chg < ATK['main_threshold']:
        return 0.0
    hm = _hhmm()
    if hm < '09:35': return ATK['a1']
    if hm < '09:45': return ATK['a2']
    if hm < '10:00': return ATK['a3']
    return 0.0


def _vwap_penalty(sec):
    # 低于 VWAP 每 30 秒扣 1 分，日上限 12（用快照 wavg_px 近似 VWAP）。
    # 时钟=「连续低于 VWAP」时长：高于 VWAP 立即恢复（归零移除），下次再破重新计时。
    px = last_px(sec); s = g.spot.get(sec)
    vwap = float(s.get('wavg_px') or 0.0) if s else 0.0
    if not px or not vwap:
        return 0.0
    if px >= vwap:
        getattr(g, 'vwap_below_since', {}).pop(sec, None)   # 高于 VWAP -> 恢复归零
        return 0.0
    now = _sec_age()
    below = getattr(g, 'vwap_below_since', {})
    start = below.get(sec)
    if start is None:
        start = now
        below[sec] = start
    return min(BLS['vwap_daily_limit'], max(0, (now - start) // 30) * BLS['vwap_penalty_per_30s'])


def _external_internal(sec):
    return 0.0    # 外盘/内盘动态分——Ptrade 无标准字段，留 0，口径待定


def _tags(sec):
    # 三维标签（简化）：LB=连板>=2、BS=100日新高、CORE=连板>=3（热门版块命中待接）
    lb = _limitup_days(sec)
    tags = []
    if lb >= 2:
        tags.append('LB')
    if _is_100day_high(sec):
        tags.append('BS')
    if lb >= 3:
        tags.append('CORE')
    return tags


def _limit_threshold(sec):
    # 涨停幅度阈值：主板10%/创·科20%/北交30%（ST5%未单列）
    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        return 0.198
    if num.startswith(('8', '4', '92')):
        return 0.298
    return 0.098

def _today_zt(sec):
    # 现价是否达涨停（今日续板判断）
    px = last_px(sec); pre = pre_close(sec)
    return bool(px and pre and (px / pre - 1.0) >= _limit_threshold(sec))

def _limitup_days(sec):
    # 连板天数：优先权威 T-1 涨停池 board_cnt（云端对齐 AXquant 涨停/连板名单）+ 今日是否续板;
    # 无权威记录回退 1d 历史近似（收盘较前收>=阈值）。
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        return max(0, int(zt.get('board_cnt') or 0) + (1 if _today_zt(sec) else 0))
    df = _hist_1d(sec)
    if df is None or len(df) < 2:
        return 0
    closes = list(df['close'])
    cnt = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i - 1] >= closes[i - 2] and closes[i] >= closes[i - 1] * 1.098:
            cnt += 1
        else:
            break
    return cnt


def _mid_board_avoid(sec):
    # 连板中位股规避（v0.34，docs/33）：复盘标注 role_detail=mid_consecutive_limit_up（既非首板/一进二低位，
    # 也非 unique_high_board 唯一性高位）-> 规避（不进买入/预期/弹性候选）。消费 AXquant 复盘 role_detail 标注。
    # 参考点：低位=首板/一进二（first_board_arb/leading_first_board），高位=唯一性展现（unique_high_board_consecutive）。
    en = g.exp_file.get(sec) or {}
    rd = str(en.get('role_detail') or '')
    if rd == 'mid_consecutive_limit_up':
        return True
    if rd in ('unique_high_board_consecutive', 'leading_first_board', 'first_board_arb'):
        return False
    # 无复盘 role_detail 兜底：按 T-1 连板数近似中位（role 为复盘口径，盘中是否续板不改分档）。
    # 2<=board_cnt<=5 中位带规避；board_cnt<2=首板/一进二放行；>=6=高位唯一性候选放行。
    # v0.34b 中位带内若为唯一高度板（板块内最高身位唯一+跟风低位板，如高度压制到 3/4 板）则放行。
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        cnt = int(zt.get('board_cnt') or 0)
        if 2 <= cnt <= 5:
            if zt.get('unique_high'):
                return False
            return True
    return False


def _is_100day_high(sec):
    df = _hist_1d(sec)
    if df is None or len(df) < 2:
        return False
    closes = list(df['close'])
    now = closes[-1]
    return now >= max(closes[:-1]) * 0.9999


def _volume_ratio(sec):
    # 量比：优先 get_snapshot 的 vol_ratio（PTrade 标准量比）；缺失回退 今日量/前5日均量
    try:
        s = g.spot.get(sec) or {}
        vr = float((s or {}).get('vol_ratio') or 0.0)
        if vr and vr > 0:
            return vr
    except Exception:
        pass
    df = _hist_1d(sec)
    if df is None or len(df) < 6:
        return 1.0
    vols = list(df['volume'])
    today = vols[-1] or 0.0
    avg5 = sum(vols[-6:-1]) / 5.0
    return (today / avg5) if avg5 > 0 else 1.0


# ================= 候选 C：竞价真口径 + 候选 D：预期三态 =================
AW="awaiting_auction"; PX="pending_exceed"; PM="pending_meet"; PS="pending_miss"
CX="confirmed_exceed"; CM="confirmed_meet"; CS="confirmed_miss"

def _overwrite_auction_c(secs):
    # v0.36 竞价终态覆盖兜底：09:25/09:31 用批量快照 open 口径统一覆盖 auction_c，
    # 消除早盘 get_trend_data 未开盘值污染（涨停池/自选合成已覆盖，普通 watch/持仓补上）
    day = str(get_trading_day())
    for code in secs:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            if pre > 0 and op > 0:
                g.auction_c[code] = (day, (op / pre - 1.0) * 100.0)
        except Exception:
            continue


def _auction_change(sec):
    # 竞价涨幅%（真口径）：get_trend_data 的 hq_px/昨收；失败回退 开盘_昨收（按交易日缓存）
    day = str(get_trading_day())
    c = g.auction_c.get(sec)
    if c and c[0] == day:
        return c[1]
    pre = pre_close(sec)
    chg = 0.0
    if pre and pre > 0:
        try:
            td = get_trend_data(stocks=sec) or {}
            d = td.get(sec) or {}
            hq = float(d.get("hq_px") or 0.0)
            if hq > 0:
                chg = (hq / pre - 1.0) * 100.0
            else:
                s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
                chg = (op / pre - 1.0) * 100.0 if op else 0.0
        except Exception:
            s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
            chg = (op / pre - 1.0) * 100.0 if op else 0.0
    g.auction_c[sec] = (day, chg)
    return chg

def _hist_window(sec):
    # 供云端自取开盘基准：1d 历史 open/close（缺失返回 None,None）
    df = _hist_1d(sec)
    if df is None:
        return None, None
    try:
        return list(df["open"]), list(df["close"])
    except Exception:
        return None, None

def _yesterday_open_chg(sec):
    # T-1 开盘涨幅 %（「昨日开盘基准」）：优先供方文件(+has)；缺失用云端 1d 历史折算
    e = g.exp.setdefault(sec, {})
    has = e.get("has_yesterday_open"); val = e.get("yesterday_open_pct")
    if not has:
        en = g.exp_file.get(sec) or {}
        if en.get("has_yesterday_open"):
            has, val = True, en.get("yesterday_open_pct")
    if has:
        return float(val or 0.0), True
    opens, closes = _hist_window(sec)
    if opens and closes and len(opens) >= 2 and len(closes) >= 2 and opens[-1] and closes[-2]:
        return (opens[-1] / closes[-2] - 1.0) * 100.0, True
    return 0.0, False

def _auction_benchmark(sec):
    # 预期达标基准（expected_auction_change_pct=T日开盘涨幅）：优先供方；缺失/<=0 用云端 1d 历史折算，再无基准=not提供
    e = g.exp.setdefault(sec, {})
    if e.get("has_expected_auction"):
        v = float(e.get("expected_auction_change_pct") or 0.0)
        return v, (v > 0.0)
    en = g.exp_file.get(sec) or {}
    if en.get("has_expected_auction"):
        v = float(en.get("expected_auction_change_pct") or 0.0)
        return v, (v > 0.0)
    opens, closes = _hist_window(sec)
    if opens and closes and len(opens) >= 2 and len(closes) >= 2 and opens[-1] and closes[-2]:
        v = (opens[-1] / closes[-2] - 1.0) * 100.0
        return v, (v > 0.0)
    return 0.0, False

def _gear(sec):
    # L2 十档盘口帧级缓存（统一 DataHub 注册表，TTL gear_cache_ttl）；
    # 缺失/异常也短缓存，防止回测/接口抖动时同帧反复打盘口
    try:
        dh = _get_ds()
        v = dh.cached('gear', sec, float(BLS.get('gear_cache_ttl', 3.0)),
                      lambda: get_gear_price(sec) or {})
        return v if v is not None else {}
    except Exception:
        return {}

def _seal_metrics(sec):
    # 实时封单（L2）：十档买一挂单金额 + 买一委托笔数（仅交易；回测返回 (0.0, 0)）
    try:
        gp = _gear(sec)
        b = (gp.get("bid_grp") or {}).get(1) or [0, 0, 0]
        amt = float(b[1] or 0.0)
        cnt = int(b[2] or 0)
        return amt, cnt
    except Exception:
        return 0.0, 0

def _is_elastic_20cm(sec):
    # 创业板(300/301)/科创板(688/689) 20cm 弹性标的（对齐 AXquant _is_elastic_20cm）
    return str(sec).split('.')[0].startswith(('300', '301', '688', '689'))

def _max_elastic_buy_price(sec):
    # 弹性追高买入价上限 = 前收 x (1 + elastic_max_buy_pct)（对齐 AXquant _elastic_20cm_max_buy_price）
    if not _is_elastic_20cm(sec):
        return 0.0
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return 0.0
    return _round_price(pre * (1 + float(BLS.get('elastic_max_buy_pct', 0.10))))

def _sealed_now(sec):
    # 即时封死判定（无 5s 持续门槛）：供 09:25/开盘一字板识别用
    s = g.spot.get(sec) or {}
    try:
        gp = _gear(sec)
        ask = gp.get('ask_grp')
        has_book = isinstance(ask, dict)
        _tq = s.get('total_offerqty')
        has_tq = _tq is not None and str(_tq).strip() not in ('', 'None')
        if BLS.get('sealed_offerqty_enabled', True) and has_tq:
            return float(_tq) <= 0.0
        if has_book:
            if not ask:
                return True
            for row in ask.values():
                if isinstance(row, (list, tuple)) and len(row) >= 2 and float(row[1] or 0) > 0:
                    return False
            return True
        return False
    except Exception:
        return False

def _sealed_at_limit(sec):
    # 封死涨停（一字/排满）：现价=涨停价 且 卖方无挂单 -> 挂单只能排队，AXquant 不参考排单（P1-3 limit_up_sealed_no_queue）
    # v0.26b：卖方无挂单判据优先 total_offerqty==0（快照总委卖量单位手），缺失回退 ask_grp 显式空判；
    # 封死判定需持续 sealed_fresh_secs(5s) 才生效（防瞬时零卖盘误判不排单）。
    # 无 L2 盘口(回测)时不判定封死，走保守可买路径，与 AXquant _is_sealed_at_limit has_book 一致。
    s = g.spot.get(sec) or {}
    px = last_px(sec); up = float(s.get('up_px') or 0.0)
    if not px or px <= 0 or up <= 0 or px < up * 0.998:
        return False
    if sec in getattr(g, 'one_word_open', set()):
        return True   # 09:25/开盘识别的一字板：直接视为封死不排队（免 5s 持续门槛；炸板后 px<涨停价 走上方返回 False）
    try:
        gp = _gear(sec)
        ask = gp.get('ask_grp')
        has_book = isinstance(ask, dict)
        _tq = s.get('total_offerqty')
        has_tq = _tq is not None and str(_tq).strip() not in ('', 'None')
        sealed_now = False
        if BLS.get('sealed_offerqty_enabled', True) and has_tq:
            sealed_now = (float(_tq) <= 0.0)             # 总委卖量==0 -> 卖方无挂单
        elif has_book:
            if not ask:
                sealed_now = True                         # 显式空卖盘 -> 封死
            else:
                for row in ask.values():
                    if isinstance(row, (list, tuple)) and len(row) >= 2 and float(row[1] or 0) > 0:
                        sealed_now = False; break
                else:
                    sealed_now = True
        else:
            return False                                 # 无快照总量亦无盘口 -> 保守判非封死
        if not sealed_now:
            if hasattr(g, 'sealed_since'):
                g.sealed_since.pop(sec, None)
            return False
        since = getattr(g, 'sealed_since', None)
        if since is None:
            since = {}; g.sealed_since = since
        if sec not in since:
            since[sec] = time.time()
            return False                                 # 第一帧只记录起点
        return (time.time() - since[sec]) >= float(BLS.get('sealed_fresh_secs', 5.0))
    except Exception:
        return False

def _block_sealed_buy(sec):
    # 封死涨停不排队买入（一字板·封单超预期也不参考排单）；同一标的每日仅告警一次
    if not _sealed_at_limit(sec):
        return False
    warned = getattr(g, 'sealed_warn', None)
    if warned is None:
        g.sealed_warn = set()
    if sec not in g.sealed_warn:
        g.sealed_warn.add(sec)
        log.info('[seal] %s sealed at limit -> no queue buy' % _sn(sec))
    return True

def _mark_one_word_open():
    # 一字板识别（09:25 竞价终态 / 09:31 开盘兜底）：竞价/开盘价=涨停价 且 卖方无挂单 -> 买入不排队
    if not getattr(g, 'one_word_open', None):
        g.one_word_open = set()
    cands = list(dict.fromkeys(
        list(g.watch or []) + list(g.pool_static or []) + list(g.selfwatch or []) +
        list((getattr(g, 'zt_lianban', None) or {}).keys()) + list((g.exp_file or {}).keys())))
    if not cands:
        return
    sn = None
    for sec in cands:
        try:
            if sec in g.one_word_open:
                continue
            s = g.spot.get(sec) or {}
            up = float(s.get('up_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            d = None
            if op <= 0 or up <= 0:   # 快照未回填(09:25)：批量补一次快照
                if sn is None:
                    sn = _get_snapshot_many(cands, 300)
                d = (sn or {}).get(sec) or {}
                if op <= 0:
                    op = float(d.get('open_px') or 0.0)
                if up <= 0:
                    up = float(d.get('up_px') or 0.0)
            if up <= 0 or op < up * 0.998:
                continue
            # v0.42 竞价终态盘口：涨停股买单全在涨停价(买1)，total_bidqty(手)≈封单量；
            #   total_offerqty==0 等价卖1=0（真一字，不排单）；卖1>0 非真一字 -> playable 可参与。
            if d is not None:
                s2 = g.spot.setdefault(sec, {})
                if s2.get('total_offerqty') is None and d.get('total_offerqty') is not None:
                    s2['total_offerqty'] = d['total_offerqty']
                if s2.get('total_bidqty') is None and d.get('total_bidqty') is not None:
                    s2['total_bidqty'] = d['total_bidqty']
                s = s2
            _tq = s.get('total_offerqty')
            _tb = s.get('total_bidqty')
            if _sealed_now(sec):
                g.one_word_open.add(sec)
                # 竞价终态封单基准回填（买1=涨停价封单≈total_bidqty 手；金额口径对齐 _seal_metrics）：
                # _exp_one_word 首帧即可判 CX/CS，不必空等 L2 base_init
                if float(g.seal_base.get(sec, 0.0) or 0.0) <= 0 and _tb is not None:
                    try:
                        g.seal_base[sec] = float(_tb) * 100.0 * up
                    except Exception:
                        pass
                log.info('[seal] %s 一字板(开=涨停价且无卖盘) sell1=%s buy1=%s -> 买入不排队' % (_sn(sec), _tq, _tb))
            else:
                log.info('[seal] %s 开=涨停价 sell1=%s buy1=%s -> playable(非真一字, 可参与)' % (_sn(sec), _tq, _tb))
        except Exception:
            continue

def _two_1m_break(sec):
    # 两根 1m 站上 open*(1+fast_up_ratio)，且当前根仍站上（v0.25：3s 缓存 + 帧预算 m1）
    try:
        dh = _get_ds()
        v = dh.cached('m1_break', sec, 3.0, lambda: _calc_two_1m_break(sec), budget='m1', prio=1)   # v0.36 高优先级独立配额
        return bool(v)
    except Exception:
        return False


def _calc_two_1m_break(sec):
    # 两分钟上攻实际拉取（帧预算/缓存内执行；超预算返回 False 保守）
    try:
        df = get_price(sec, start_date=None, end_date=None, count=8, frequency="1m")
        if df is None or len(df) < 2:
            return False
        open_px = float(df["open"].iloc[0] or 0.0)
        if open_px <= 0:
            return False
        thr = open_px * (1 + float(BLS.get("fast_up_ratio", 0.01)))
        mid = (df["close"] + df["high"]) / 2.0
        q = [bool(x) for x in (mid >= thr)]
        return q.count(True) >= 2 and bool(q) and q[-1]
    except Exception:
        return False

def _limit_up_within_1m(sec):
    # 分时确认超预期之一：开盘后 ~1 分钟内冲涨停（当前价>=涨停价*0.998，时段 09:30-09:32）
    s = g.spot.get(sec)
    px = last_px(sec); up = float(s.get("up_px") or 0.0) if s else 0.0
    if not px or px <= 0 or up <= 0 or px < up * 0.998:
        return False
    hm = _hhmm()
    return hm in ("09:30", "09:31", "09:32")


def _below_vwap(sec):
    s = g.spot.get(sec)
    vwap = float(s.get("wavg_px") or 0.0) if s else 0.0
    px = last_px(sec)
    return bool(px and vwap and px < vwap)

def _eval_auction(sec):
    e = g.exp.setdefault(sec, {})
    if e.get("entry_type") == "one_word":
        return AW, ["one_word_requires_seal"]
    chg = _auction_change(sec)
    if chg < 0:
        return PS, ["auction_green_open"]
    yopen, has = _yesterday_open_chg(sec)
    if has and chg > yopen:
        return PX, ["auction_higher_than_yesterday"]   # 负基也判高开（v0.17）
    return PM, ["auction_small_open"]

def _eval_intraday(sec, auction_status):
    if auction_status in (PS, CS):
        return CS, ["from_auction"]
    if _two_1m_break(sec) and auction_status in (PX, CX):
        return CX, ["two_1m_break"]
    if _below_vwap(sec):
        return CS, ["break_vwap"]
    return CM, ["held_vwap"]

def _hold_exp_init(sec, force=False):
    # 云端持仓预期管理（v0.32）：对任一只持仓股建立/刷新 g.exp 预期条目。
    # 基准全部来自云端算法（竞价三态 _eval_auction + 分时三态 _eval_intraday + 一字板判定），
    # 回填预期文件字段（sell_policy_hint/expected_status 等）；幂等（不覆盖已确认状态，force 跨日重算）。
    sec = _norm_sec(sec) or sec
    e = g.exp.setdefault(sec, {})
    _en = g.exp_file.get(sec) or {}
    for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct',
               'seal_amount_t0', 'sell_policy_hint'):
        if _en.get(_k) is not None:
            e[_k] = _en[_k]
    if not e.get('entry_type'):
        e['entry_type'] = 'one_word' if _is_one_word_open(sec) else 'normal'
    if not e.get('side'):
        e['side'] = 'hold'
    if force or e.get('auction_status') is None:
        try:
            e['auction_status'] = _eval_auction(sec)[0]
        except Exception:
            e['auction_status'] = PM
    if force or e.get('status') is None:
        try:
            e['status'] = _eval_intraday(sec, e.get('auction_status') or PM)[0]
        except Exception:
            e['status'] = CM
    if force or not e.get('_hold_inited'):
        e['_hold_inited'] = True
        e['_hold_ts'] = time.time()
        log.info('[hold] %s 持仓预期管理初始化 entry_type=%s auction_status=%s status=%s sell_policy=%s' % (
            _sn(sec), e.get('entry_type'), e.get('auction_status'), e.get('status'),
            e.get('sell_policy_hint') or 'none'))
    return e


def _exp_one_word(sec):
    # 一字板封单（L2 实时化）：金额比基准判超预期/衰竭；买一委托笔数骤降视为撤单松动，加速判 miss
    seal, bids = _seal_metrics(sec)
    base = g.seal_base.get(sec, 0.0)
    bbase = g.seal_bid_base.get(sec, 0)
    if base <= 0:
        g.seal_base[sec] = seal
        g.seal_bid_base[sec] = bids
        return AW, ["seal_base_init"]
    ratio = seal / base if base > 0 else 0.0
    bid_fail = False
    if BLS.get("seal_bid_enabled", True) and bbase > 0 and bids < bbase * float(BLS.get("seal_bid_fail_ratio", 0.5)):
        bid_fail = True
    if ratio <= float(BLS["seal_fail_ratio"]) or bid_fail:
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d bid_fail=%s -> CS" % (_sn(sec), seal, base, ratio, bids, bbase, bid_fail))
        return CS, ["seal_fail"]
    if ratio >= float(BLS["seal_exceed_ratio"]):
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CX" % (_sn(sec), seal, base, ratio, bids))
        return CX, ["seal_increase"]
    log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CM" % (_sn(sec), seal, base, ratio, bids))
    return CM, ["seal_within"]



def _auction_beat_history(sec):
    # 开盘涨幅优于近 20 日平均开盘涨幅（近似，真实为竞价后对比历史同期）
    df = _hist_1d(sec)
    if df is None or len(df) < 21:
        return False
    opens = list(df['open']); closes = list(df['close'])
    opens = opens[-(21):]
    hist_open_chg = sum((opens[i] / opens[i - 1] - 1.0) for i in range(1, len(opens))) / (len(opens) - 1)
    return _auction_change(sec) > hist_open_chg * 100.0 + 0.5


def _touched_limit_early(sec):
    # 早盘触涨停：当前价>=涨停价*0.998 且 10:00 前
    s = g.spot.get(sec)
    px = last_px(sec); up = float(s.get('up_px') or 0.0) if s else 0.0
    return bool(px and up and px >= up * 0.998 and _hhmm() < '10:00')


def _board_bonus(sec):
    # 板块分档 -15~+15（用板块强度幅度制回退，AXquant _board_strength_to_bonus）
    st = _board_strength(sec)
    if st > 3.0: return 15.0
    if st > 1.0: return 10.0
    if st > 0.0: return 5.0
    if st == 0.0: return 0.0
    if st > -1.0: return -5.0
    if st > -3.0: return -10.0
    return -15.0


def _board_refresh_ttl():
    # 板块强度/排名刷新周期：开盘 30 分钟内（<10:00）3s 与 tick 同频，之后 60s
    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            return float(BLS.get('board_rank_ttl_fast', 3.0))
    except Exception:
        pass
    return float(BLS.get('board_rank_cache_ttl', 60.0))


def _fetch_board_code(sec):
    # 所属板块代码（get_stock_blocks 首层首个非空行）；无则 None
    try:
        blocks = get_stock_blocks(sec) or {}
        for lst in blocks.values():
            if isinstance(lst, list):
                for row in lst:
                    if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                        return str(row[0]).strip()
    except Exception:
        pass
    return None


def _board_code_of(sec):
    # 所属板块代码（板块归属日内不变，3600s 缓存，日切随 DataHub 清空）
    try:
        dh = _get_ds()
        return dh.cached('bcode', sec, 3600.0, lambda: _fetch_board_code(sec), budget='bcode')
    except Exception:
        return None


def _fetch_board_chgs(board_code):
    # 板块代码 -> 成员批量快照涨跌（一次 get_snapshot(列表)，最多20只）；异常/无成员返回 ()
    chgs = []
    try:
        mem = [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board_code)) or [])[:20]) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        for m in mem:
            try:
                d = sn.get(m) or {}
                pre = float(d.get('preclose_px') or 0.0)
                px = float(d.get('last_px') or 0.0)
                if pre > 0:
                    chgs.append(px / pre - 1.0)
            except Exception:
                continue
    except Exception:
        chgs = []
    return tuple(chgs)


def _board_strength_by_code(board_code):
    # 板块强度（成员涨跌均值%，board_rank_cache_ttl=60s 缓存，DataHub 注册表）
    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', str(board_code), _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(board_code), budget='board', stale_ok=True)
        chgs = list(v) if v is not None else []
        return (sum(chgs) / len(chgs)) * 100.0 if chgs else 0.0
    except Exception:
        return 0.0


def _board_member_changes(sec):
    # 板块成员实时涨跌列表(缓存60s)：所属板块代码->成员批量快照涨跌。
    # 注：不做 get_sort_msg(该券商签名不适配会刷 ERROR)，统一走板块代码取成员。
    b = _board_code_of(sec)
    if not b:
        return []
    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', b, _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(b), budget='board', stale_ok=True)
        return list(v) if v is not None else []
    except Exception:
        return []


def _board_strength(sec):
    # 板块强度：所属板块成员实时涨跌均值（缓存60s）
    b = _board_code_of(sec)
    return _board_strength_by_code(b) if b else 0.0


def _compute_board_rank(boards):
    # 各板块强度排序，取强度前 N（v0.23 打首板/弹性套利板块目标）
    sts = []
    for b in boards:
        try:
            sts.append((_board_strength_by_code(b), b))
        except Exception:
            continue
    sts.sort(key=lambda kv: kv[0], reverse=True)
    return {b for _, b in sts[:int(BLS.get('board_rank_top_n', 3))]}


def _board_rank_top3_set(secs):
    # 候选所属板块集合 -> 强度前三板块代码集合；按候选板块集合缓存（60s，随板块强度刷新）
    secs = [s for s in (secs or []) if s]
    if not secs:
        return set()
    boards = sorted({b for b in (_board_code_of(s) for s in secs) if b})
    if not boards:
        return set()
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('board_rank', token), '_', _board_refresh_ttl(),
                      lambda: _compute_board_rank(boards), single=True)   # v0.36 同源只留最新一条
        return v if v is not None else set()
    except Exception:
        return set()


def _compute_board_top1_lead(boards):
    # 候选板块中强度第一 及 对第二的领先幅度%（v0.36c：防并列/紧咬误判）
    best = None; best_st = None; second_st = None
    for b in boards:
        try:
            st = _board_strength_by_code(b)
        except Exception:
            continue
        if best is None or st > best_st:
            second_st = best_st
            best, best_st = b, st
        elif second_st is None or st > second_st:
            second_st = st
    if best_st is None:
        return (None, 0.0)
    return (best, best_st - (second_st if second_st is not None else 0.0))


def _board_rank_top1(secs):
    # 候选所属板块集合 -> (强度第一板块代码, 对第二的领先幅度%)；single 缓存防 token 碎片
    # v0.36b：归属扩为全板块列表（_boards_of，300s 缓存）；v0.36c：返回领先幅度
    secs = [s for s in (secs or []) if s]
    if not secs:
        return (None, 0.0)
    boards = sorted({b for s in secs for b in _boards_of(s) if b})
    if not boards:
        return (None, 0.0)
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('board_top1', token), '_', _board_refresh_ttl(),
                      lambda: _compute_board_top1_lead(boards), single=True)
        if isinstance(v, tuple) and len(v) == 2:
            return v
        return (v, 0.0)
    except Exception:
        return (None, 0.0)


def _board_rank_top3(sec, secs):
    # sec 所属板块是否在候选板块强度前三（打首板/弹性套利板块目标门控）
    try:
        b = _board_code_of(sec)
        if not b:
            return False
        return b in _board_rank_top3_set(secs)
    except Exception:
        return False


def _near_limit_cands(secs):
    # 近涨停候选（last>=up*firsttx_near_px 且 非一字）；供首板 1m 兜底路径的板块排名候选
    near_px = float(BLS.get('firsttx_near_px', 0.98))
    out = []
    for s in secs:
        try:
            d = g.spot.get(s) or {}
            last = float(d.get('last_px') or 0.0); up = float(d.get('up_px') or 0.0)
            if last > 0 and up > 0 and last >= up * near_px and not _is_one_word_open(s):
                out.append(s)
        except Exception:
            continue
    return out

def _red_ratio(sec):
    # 板块红盘比：所属板块成员中上涨占比 up/(up+dn)，缓存60s；无成员返回0.5(中性)
    chgs = _board_member_changes(sec)
    up = sum(1 for x in chgs if x > 0)
    dn = sum(1 for x in chgs if x < 0)
    denom = up + dn
    return float(up) / denom if denom else 0.5


def _market_red_ttl():
    # 全市场红盘比缓存 TTL：10:00 前快速刷新（对齐 board_rank_fast_until_minute）
    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            return float(BLS.get('market_red_ttl_fast', 30.0))
    except Exception:
        pass
    return float(BLS.get('market_red_ttl', 60.0))


def _fetch_market_red(pool):
    # 全量分片 get_snapshot 统计 涨/(涨+跌)（与 AXquant 生成侧口径一致，不含平盘）；无有效样本 -> None
    batch = max(int(BLS.get('market_batch', 300)), 1)
    up = dn = 0
    t0 = time.time()
    n_batch = 0
    for i in range(0, len(pool), batch):
        chunk = pool[i:i + batch]
        n_batch += 1
        try:
            sn = get_snapshot(chunk)
            if not isinstance(sn, dict):
                continue
        except Exception:
            continue
        for code, d in sn.items():
            try:
                pre = float(d.get('preclose_px') or 0.0)
                px = float(d.get('last_px') or 0.0)
                if pre <= 0 or px <= 0:
                    continue
                if px > pre:
                    up += 1
                elif px < pre:
                    dn += 1
            except Exception:
                continue
    denom = up + dn
    if denom <= 0:
        log.info('[market-red] 无有效样本（全量分片 %d 批）-> None' % n_batch)
        return None
    ratio = float(up) / denom
    log.info('[market-red] 全市场红盘比=%.2f%% up=%d dn=%d 批=%d 样本=%d 耗时=%.1fs'
             % (ratio * 100.0, up, dn, n_batch, denom, time.time() - t0))
    return ratio


def _market_red_ratio():
    # 全市场红盘比（v0.41）：get_Ashares 全量分片 get_snapshot 统计，独立预算源 market；
    # 失败/无池 -> None（上层降级基线驱动保守上限）。日切随 DataHub 缓存 key(day) 失效。
    try:
        day = str(get_trading_day())
        if getattr(g, 'pool_day', '') != day:
            try:
                g.pool_all = [x for x in (_norm_sec(c) for c in (get_Ashares() or [])) if x]
                g.pool_day = day
            except Exception as e:
                _warn('market-red get_Ashares fail: %r' % e)
                g.pool_all = []
        pool = list(g.pool_all or [])
        if not pool:
            return None
        dh = _get_ds()
        return dh.cached(('mkt_red', day), '_mkt_', _market_red_ttl(),
                         lambda: _fetch_market_red(pool), budget='market', stale_ok=True)
    except Exception as e:
        _warn('market-red fail: %r' % e)
        return None


def _sentiment_warm(sec):
    # v0.41 情绪回暖判定：T 日冰点基线 + 今日全市场红盘比恢复（>= 恢复阈值，冰点越久阈值越低=回暖概率增加）。
    # 未启用 / 无冰点基线 -> None（不参与闸门）；全市场红盘比缺失 -> False（保守不放行）；
    # 今日继续冰点（全市场红盘比<ice_ratio）-> False。
    if not BLS.get('sentiment_enabled', False):
        return None
    s = getattr(g, 'sentiment', None)
    if not s or not s.get('ice'):
        return None
    red = _market_red_ratio()
    if red is None:
        log.info('[sentiment] %s 全市场红盘比缺失 -> 保守不放行' % _sn(sec))
        return False
    ice_ratio = float(BLS.get('sentiment_ice_ratio', 0.40))
    if red < ice_ratio:
        log.info('[sentiment] %s 继续冰点 red=%.2f (<%.2f) 等下一交易日再验证回暖' % (_sn(sec), red, ice_ratio))
        return False
    streak = max(int(s.get('ice_streak') or 1), 1)
    th = max(float(BLS.get('sentiment_warm_min', 0.45)),
             float(BLS.get('sentiment_warm_base', 0.55)) - streak * float(BLS.get('sentiment_warm_decay', 0.02)))
    warm = red >= th
    log.info('[sentiment] %s streak=%d red=%.2f th=%.2f -> %s' % (_sn(sec), streak, red, th, '回暖' if warm else '未回暖'))
    return warm

def _buy_red_ok(sec):
    # 红盘比买入门（v0.18）：red_gate_enabled 开启时要求板块红盘比>=red_ratio_buy_min；
    # v0.29 情绪回暖闸门：T-1 冰点基线存在时，还要求「今日红盘比恢复」才放行（回暖博弈）。
    if not BLS.get('red_gate_enabled', False):
        return True
    if _red_ratio(sec) < BLS.get('red_ratio_buy_min', 0.55):
        return False
    w = _sentiment_warm(sec)
    return True if w is None else w


def _pos_value(p, sec):
    # 单只持仓市值（market_value -> amount*last 兜底）；str/int/float 容忍
    try:
        v = p.get('market_value') if isinstance(p, dict) else getattr(p, 'market_value', None)
        if v:
            return float(v)
        amt = float(p.get('amount') if isinstance(p, dict) else getattr(p, 'amount', 0) or 0)
        last = float(p.get('last_sale_price') if isinstance(p, dict) else getattr(p, 'last_sale_price', 0) or 0)
        if amt and last:
            return amt * last
        px = last_px(sec) or 0.0
        return amt * px
    except Exception:
        return 0.0


def _warm_cap(s):
    # 回暖/延续日仓位上限 = warm_pos_pct - 连续回暖天数递减（分歧保护，docs/40 闭环）
    warm_days = int(s.get('warm_days') or 0)
    divergence = int(s.get('divergence') or 0)   # v0.44 显式消费 CSV 分歧标志（与 warm_days 双保险）
    taper_start = int(BLS.get('warm_taper_start', 3))
    step = float(BLS.get('warm_taper_step', 0.10))
    cap = float(BLS.get('warm_pos_pct', 0.80)) - max(0, warm_days - taper_start + 1) * step
    cap = max(cap, float(BLS.get('warm_taper_min', 0.50)))
    if warm_days >= taper_start:
        n_taper = max(0, warm_days - taper_start + 1)
    elif divergence:
        n_taper = 1                              # CSV 显式分歧：至少一档递减
    else:
        n_taper = 0
    cap = float(BLS.get('warm_pos_pct', 0.80)) - n_taper * step
    cap = max(cap, float(BLS.get('warm_taper_min', 0.50)))
    if n_taper > 0:
        log.info('[pos-cap] 分歧保护：divergence=%d warm_days=%d -> cap=%.2f' % (divergence, warm_days, cap))
    return cap


def _emotion_cap(s):
    # v0.41 emotion 档位 -> 总仓位硬上限（None=不干预）；与规则 ice/phase 冲突取保守值并 WARN。
    emo = str(s.get('emotion') or '').strip()
    if not emo:
        return None
    ice = bool(s.get('ice'))
    cap_ice = float(BLS.get('emotion_cap_ice', 0.40))
    cap_warm = float(BLS.get('emotion_cap_warm', 0.80))
    cap_tap = float(BLS.get('emotion_cap_taper', 0.50))
    if emo in ('冰点', '偏冷'):
        return cap_ice
    if emo in ('回暖', '发酵'):
        if ice:
            log.info('[sentiment] 冲突: emotion=%s 但 ice=%d -> 规则冰点优先(保守)' % (emo, int(ice)))
            return cap_ice
        return cap_warm
    if emo in ('高潮', '过热'):
        return cap_tap
    return None


def _sentiment_pos_cap(context, sec):
    # v0.41 情绪总仓位上限（None=不限）：
    #   冰点基线存在 -> 按今日全市场红盘比判定冰点/回暖（全市场缺失降级冰点 40%）；
    #   已回暖/无冰点基线(回暖延续) -> warm_cap(80%-taper)；emotion 档位再收窄（冲突保守+WARN）。
    if not BLS.get('sentiment_pos_cap_enabled', False):
        return None
    s = getattr(g, 'sentiment', None)
    if not s:
        return None
    if s.get('ice'):
        red = _market_red_ratio()
        streak = max(int(s.get('ice_streak') or 1), 1)
        th = max(float(BLS.get('sentiment_warm_min', 0.45)),
                 float(BLS.get('sentiment_warm_base', 0.55)) - streak * float(BLS.get('sentiment_warm_decay', 0.02)))
        if red is None:
            cap = float(BLS.get('ice_pos_pct', 0.40))          # 全市场红盘比缺失 -> 降级冰点上限
            note = 'mkt-red=None(降级冰点)'
        else:
            cap = float(BLS.get('ice_pos_pct', 0.40)) if red < th else _warm_cap(s)
            note = 'mkt-red=%.2f th=%.2f' % (red, th)
    else:
        cap = _warm_cap(s)                                     # 无冰点基线：回暖/延续日
        note = '无冰点基线'
    ec = _emotion_cap(s)                                       # emotion 档位硬上限（保守合并）
    if ec is not None and cap > ec:
        log.info('[pos-cap] %s emotion 档位收窄 %s -> %.2f（原 %.2f）' % (_sn(sec), s.get('emotion') or '-', ec, cap))
        cap = ec
    log.info('[pos-cap] %s 情绪仓位上限 cap=%.2f (ice=%d warm_days=%d phase=%s emotion=%s %s)'
             % (_sn(sec), cap, int(s.get('ice') or 0), int(s.get('warm_days') or 0),
                s.get('phase') or '-', s.get('emotion') or '-', note))
    return cap


def _buy_pos_ok(context, sec, qty, limit):
    # 总仓位上限闸门：买入后总持仓市值/总资产 <= 情绪仓位上限，超限 skip（读只/实盘一致可观察）
    cap = _sentiment_pos_cap(context, sec)
    if cap is None:
        return True
    pos = getattr(getattr(context, 'portfolio', None), 'positions', {}) or {}
    pv = sum(_pos_value(p, sec) for p in pos.values())
    cash = float(getattr(getattr(context, 'portfolio', None), 'cash', 0) or 0)
    total = cash + pv
    if total <= 0:
        return True
    add = qty * (limit or last_px(sec) or 0.0)
    ratio = (pv + add) / total
    if ratio > cap:
        log.info('[pos-cap] %s qty=%d add=%.0f pos_ratio=%.2f > cap=%.2f -> skip' % (_sn(sec), qty, add, ratio, cap))
        return False
    return True
def _set_bs(sec, v):
    g.bs_cache[sec] = (time.time(), v)
    return v


def _set_now(context):
    g.now_dt = getattr(getattr(context, 'blotter', None), 'current_dt', None) or None


def _hhmm():
    if g.now_dt is not None:
        try:
            return g.now_dt.strftime('%H:%M')
        except Exception:
            pass
    return time.strftime('%H:%M')


def _min_age():
    # 距 09:30 已过分钟数（用于 VWAP 扣分，基于当前 bar 时间）
    hm = _hhmm()
    try:
        h1, m1 = int(hm[:2]), int(hm[3:5])
    except Exception:
        return 0
    return max(0, (h1 * 60 + m1) - (9 * 60 + 30))


def _sec_age():
    # 距 09:30 已过秒数（30 秒粒度 VWAP 扣分；now_dt 缺失回退 分钟*60）
    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            secs = (nd.hour * 3600 + nd.minute * 60 + nd.second) - (9 * 3600 + 30 * 60)
            return max(0, secs)
        except Exception:
            pass
    return _min_age() * 60


def dump_scores(context):
    # 观察输出：把入池/持仓各标的本 bar 评分明细打出来，便于回测/交易核对打分触发
    if not BLS.get('debug_score'):
        return
    for sec in _pool() + list(get_positions()):
        try:
            px = last_px(sec); ma5 = _ensure_ma5(sec) or 0.0
            chg = _auction_change(sec)
            tags = ','.join(_tags(sec)) or '-'
            st = _board_strength(sec)
            sc = score_now(sec)
            log.info('score %s bar=%s px=%.2f ma5=%.2f chg=%.1f%% board=%.1f tags=%s score=%.1f' % (
                _sn(sec), _hhmm(), px if px else 0.0, ma5, chg, st, tags, sc))
        except Exception as e:
            _warn('dump_scores fail %s: %r' % (_sn(sec), e))


def _norm_sec(code):
    # 代码后缀统一为 .XSHG/.XSHE/.XBJ（get_Ashares 可能回 .SS/.SH/.SZ/裸代码，行情取不到）
    s = str(code or '').strip()
    if not s:
        return ''
    num = s.split('.')[0]
    if not num:
        return ''
    low = s.lower()
    suf = low.split('.')[-1] if '.' in low else ''
    if suf in ('xshg', 'sh', 'ss'):
        return num + '.XSHG'
    if suf in ('xshe', 'sz'):
        return num + '.XSHE'
    if suf in ('xbj', 'bj'):
        return num + '.XBJ'
    head = num[:1]
    if head in ('6', '9', '5'):
        return num + '.XSHG'
    if head in ('0', '1', '2', '3'):
        return num + '.XSHE'
    if head in ('4', '8'):
        return num + '.XBJ'
    return num

def _research_roots():
    # 云端研究根 + 定时上传自建 upload_file/ + data/ 兜底（见 docs-02/33；upload_file 为定时上传任务自建目录）
    base = get_research_path()
    return [base, base + 'upload_file/', base + 'data/', base + 'data/upload_file/']

def _selfwatch_paths():
    return [r + 'selfwatch.csv' for r in _research_roots()]


def _load_selfwatch():
    # 读取手动/实时同步的自选股（每行一代码 或 code CSV；可盘中更新，N bar 重读）
    g.selfwatch = []
    for cand in _selfwatch_paths():
        try:
            with open(cand, 'rt', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
            codes = []
            for ln in lines:
                tok = ln.split(',')[0].strip()
                if tok.lower() in ('code', 'security', 'codes'):
                    continue
                codes.append(tok)
            g.selfwatch = [x for x in (_norm_sec(c) for c in codes) if x]
            log.info('[pool] selfwatch loaded %s -> %d' % (cand, len(g.selfwatch)))
            return len(g.selfwatch)
        except Exception:
            continue
    return 0


def _sync_pool_static():
    # 固定池 = 自选股 + 预期文件 side=buy 的推荐（超预期优先在前）
    sw = list(getattr(g, 'selfwatch', []) or [])
    buy_codes = []
    for code, en in (getattr(g, 'exp_file', {}) or {}).items():
        if str(en.get('side') or '') == 'buy':
            buy_codes.append(code)
    buy_codes.sort(key=lambda c: 0 if 'exceed' in str((getattr(g, 'exp_file', {}).get(c) or {}).get('expected_status') or '') else 1)
    pool = list(dict.fromkeys([x for x in (_norm_sec(c) for c in (sw + buy_codes)) if x]))
    g.pool_static = pool
    log.info('[pool] selfwatch=%d expect_buy=%d pool_static=%d' % (len(sw), len(buy_codes), len(pool)))


def _pool():
    # 当前买入/打分迭代目标：动态 watch ∪ 固定池(自选股+预期推荐)；空回落 universe
    out = [x for x in (_norm_sec(s) for s in (list(g.watch or []) + list(g.pool_static or []))) if x]
    out = list(dict.fromkeys(out))
    return out or BLS['universe']


def _get_snapshot_many(codes, cap):
    # 批量快照：优先 get_snapshot(列表)；不可用时回退逐只（仅前 per_stock_cap 只）
    try:
        sn = get_snapshot(codes[:cap])
        if isinstance(sn, dict):
            return sn
    except Exception:
        pass
    out = {}
    pc = int(BLS.get('per_stock_cap', 60))
    for c in codes[:pc]:
        try:
            one = get_snapshot(c) or {}
            out.update(one)
        except Exception:
            continue
    return out


def _scan_market():
    # 全市场扫描：按涨幅/接近涨停过滤，取 top max_watch 入池（缓存按交易日）
    day = str(get_trading_day())
    if g.pool_day != day:
        try:
            g.pool_all = [x for x in (_norm_sec(c) for c in (get_Ashares() or [])) if x]
            g.pool_day = day
        except Exception as e:
            _warn('get_Ashares fail: %r' % e)
            g.pool_all = []
    if not g.pool_all:
        return BLS['universe']
    cap = int(BLS['scan_batch'])
    total = len(g.pool_all)
    if cap > total:
        cap = total
    offset = g.scan_offset % max(total, 1)
    window = g.pool_all[offset:offset + cap]
    if len(window) < cap and total:
        window = window + (g.pool_all + g.pool_all)[offset + cap:offset + cap + (cap - len(window))]
    g.scan_offset = (offset + cap) % max(total, 1)
    sn = {}
    try:
        sn = _get_snapshot_many(window, cap)
    except Exception:
        sn = {}
    rows = []
    for code, d in sn.items():
        pre = float(d.get('preclose_px') or 0.0); px = float(d.get('last_px') or 0.0)
        if pre <= 0 or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg < float(BLS['scan_min_chg']):
            continue
        up = float(d.get('up_px') or 0.0)
        near_limit = 1.0 if (up > 0 and px >= up * 0.998) else 0.0
        rows.append({'code': code, 'chg': chg, 'limit': near_limit,
                     'proxy': chg + 20.0 * near_limit})
    rows.sort(key=lambda r: r['proxy'], reverse=True)
    watch = [x for x in (_norm_sec(r['code']) for r in rows[:int(BLS['max_watch'])]) if x]
    if watch:
        g.watch = watch
    return (watch or BLS['universe'])


def _sync_watch(context):
    try:
        watch = _scan_market()
        if watch:
            g.watch = list(dict.fromkeys(watch))
        log.info('market_scan bar=%s pool=%d watch=%d off=%d cap=%d' % (
            _hhmm(), len(g.pool_all or []), len(g.watch),
            getattr(g, 'scan_offset', 0), int(BLS.get('scan_batch', 300))))
    except Exception as e:
        _warn('market_scan fail: %r' % e)



def _prev_trade_day():
    # 上一交易日（跳过周末；节假日按工作日放宽，权威日历见 docs/28 bridge/calendar.py）
    try:
        d = get_trading_day()
        for _ in range(10):
            d = d - timedelta(days=1)
            if d.weekday() < 5:
                return d
    except Exception:
        pass
    return None


def _expectation_paths():
    # 候选：研究根目录优先，upload_file/（定时上传自建）、data/、data/upload_file/ 兜底
    # 日期对齐（docs/25）：文件以「生成日期」命名（T-1 复盘文件，T 日验证）；latest 稳定指针 > 验证日 > 生成日
    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    suf = BLS.get("expectation_suffix", ".csv")
    latest = [r + "expectation_latest" + suf for r in _research_roots()]   # 稳定指针（生成日期命名，见 docs/25），云端优先读
    today = [r + "expectation_" + day + suf for r in _research_roots()]     # 验证日命名（T 日）
    prevs = ([r + "expectation_" + prev + suf for r in _research_roots()] if prev and prev != day else [])  # 生成日命名（T-1 复盘，今日验证）
    return latest + today + prevs

def _load_expectation():
    # 读 AXquant 竞价终态文件（docs/25 契约）；缺失/坏文件自动跳过（扫描兜底）
    g.exp_file = {}
    fp = None
    rows = None
    for cand in _expectation_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        log.info("expectation file not found (tried %s)" % _expectation_paths())
        return 0
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            _ry = (rec.get("yesterday_open_pct") or "").strip()
            _ra = (rec.get("expected_auction_change_pct") or "").strip()
            g.exp_file[code] = {
                "side": (rec.get("side") or "hold").strip(),
                "entry_type": (rec.get("entry_type") or "normal").strip(),
                "expected_status": (rec.get("expected_status") or "").strip(),
                "yesterday_open_pct": _fnum(_ry),
                "has_yesterday_open": bool(_ry),
                "expected_auction_change_pct": _fnum(_ra),
                "has_expected_auction": bool(_ra),
                "seal_amount_t0": _fnum(rec.get("seal_amount_t0")),
                "sell_policy_hint": (rec.get("sell_policy_hint") or "").strip(),
                "role_detail": (rec.get("role_detail") or "").strip(),
            }
        log.info("expectation file loaded %s -> %d" % (fp, len(g.exp_file)))
        return len(g.exp_file)
    except Exception as e:
        log.info("expectation file skip (none/invalid) %s: %r" % (fp, e))
        return 0

def _fnum(v):
    try:
        return float(str(v).replace(chr(44), "").strip())
    except Exception:
        return 0.0

def _zt_lianban_paths():
    # 复用研究四层根：稳定指针 zt_lianban_latest.csv 优先, 再按当日/上一交易日日期(兼容 upload_file/ 生成日期命名)。
    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    cands = [r + "zt_lianban_latest.csv" for r in _research_roots()]
    for r in _research_roots():
        cands.append(r + "zt_lianban_" + day + ".csv")
    if prev and prev != day:
        for r in _research_roots():
            cands.append(r + "zt_lianban_" + prev + ".csv")
    return cands

def _load_zt_lianban():
    # 读 T-1 涨停/连板名单（docs/33 导出契约）：zt_lianban_latest.csv / zt_lianban_<date>.csv；缺失不崩。
    g.zt_lianban = {}
    fp = None; rows = None
    for cand in _zt_lianban_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        return 0
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        has_unq = 'unique_high' in hdr
        has_flw = 'follower_count' in hdr
        g.zt_unq_authoritative = has_unq    # v0.37 文件带权威唯一列（AXquant 同源预计算）-> 优先读列
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            g.zt_lianban[code] = {
                "date": (rec.get("date") or "").strip(),
                "board_cnt": int(_fnum(rec.get("board_cnt"))),
                "limit_up_time": (rec.get("limit_up_time") or "").strip(),
                "seal_money": _fnum(rec.get("seal_money")),
                "chg_pct": _fnum(rec.get("chg_pct")),
                "is_st": bool(int(_fnum(rec.get("is_st"))) or 0),
                "reason": (rec.get("reason") or "").strip(),
                "unique_high": bool(int(_fnum(rec.get("unique_high"))) or 0) if has_unq else False,
                "follower_count": int(_fnum(rec.get("follower_count"))) if has_flw else 0,
            }
        n_unq = _annotate_zt_uniqueness()   # v0.34b 兜底标注；v0.37 文件权威列优先
        log.info("[zt-lianban] loaded %s -> %d unique_high=%d" % (fp, len(g.zt_lianban), n_unq))
        return len(g.zt_lianban)
    except Exception as e:
        log.info("[zt-lianban] skip(invalid) %s: %r" % (fp, e))
        return 0

def _annotate_zt_uniqueness():
    # v0.34b 云端唯一高度板兜底标注（对齐 AXquant 收盘地位重算的唯一身位判定）：
    #   板块口径 = 涨停原因首 token（云端无权威板块映射，用首 token 兜底分组，与 AXquant 复盘 board_name 同源）；
    #   组内>=2家 且 最高身位唯一 -> unique_high=True（组内其余更低身位即跟风低位板）；
    #   特例：全市场最高身位唯一（高度压制到 3/4 板等场景）也授 unique_high。
    # v0.37：zt_lianban 文件带权威唯一列（AXquant 同源预计算 unique_high/follower_count）时直接读列，
    #   消除首 token 拆组漂移（如 大业股份/京城股份 同题材并列 3 板被误授唯一穿透中位规避）；
    #   仅文件缺列时才按首 token 兜底重算。
    # 复盘 role_detail 权威标注优先（mid 规避 / unique 放行），本函数仅供无标注时兜底。
    zt = getattr(g, 'zt_lianban', {}) or {}
    if not zt:
        return 0
    if getattr(g, 'zt_unq_authoritative', False):
        return sum(1 for rec in zt.values() if rec.get('unique_high'))
    groups = {}
    for code, rec in zt.items():
        reason = str(rec.get('reason') or '')
        toks = [t.strip() for t in reason.replace('+', ' ').replace('、', ' ').replace(',', ' ').replace('，', ' ').replace('/', ' ').replace('；', ' ').split() if t.strip()]
        key = toks[0] if toks else ('__noboard__' + str(code))
        groups.setdefault(key, []).append(code)
    heights = {c: max(1, int((zt[c] or {}).get('board_cnt') or 1)) for c in zt}
    gmax = max(heights.values(), default=1)
    gtop = {c for c, h in heights.items() if h == gmax}
    n_unq = 0
    for codes in groups.values():
        hs = [heights[c] for c in codes]
        mx = max(hs)
        top = [c for c, h in zip(codes, hs) if h == mx]
        for c in codes:
            rec = zt[c]
            is_leader = (len(top) == 1 and top[0] == c and (
                len(codes) >= 2 or (mx == gmax and len(gtop) == 1 and c in gtop)
            ))
            rec['unique_high'] = bool(is_leader)
            rec['follower_count'] = sum(1 for o, oh in zip(codes, hs) if o != c and oh < mx) if is_leader else 0
            if is_leader:
                n_unq += 1
    return n_unq


def _sentiment_paths():
    # 情绪基线 CSV（本地生成，与 zt_lianban 同链，docs/40）：sentiment_latest.csv 优先, 再按上一交易日
    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    cands = [r + "sentiment_latest.csv" for r in _research_roots()]
    if prev and prev != day:
        for r in _research_roots():
            cands.append(r + "sentiment_" + prev + ".csv")
    return cands


def _board_file_paths():
    # 板块映射文件（本地生成, THS 口径, docs/24 §26）：稳定指针 boards_latest.csv 优先, 四层研究根
    return [r + "boards_latest.csv" for r in _research_roots()]


def _load_boards():
    # v0.36d 板块映射文件加载（Step1：仅加载+日志 [boards] loaded，不改消费逻辑）。
    # 契约：board_name,board_type,member_code（长格式）-> g.boards{板块:[成员]} +
    # g.stock_boards{股票:[板块]} + g.board_type{板块:类型}；缺失不崩。
    g.boards = {}
    g.stock_boards = {}
    g.board_type = {}
    for cand in _board_file_paths():
        try:
            with open(cand, 'rt', encoding='utf-8') as f:
                rows = list(csv.reader(f))
        except Exception:
            continue
        if len(rows) < 2:
            continue
        hdr = [x.strip().lower() for x in rows[0]]
        try:
            ni, nt, nc = hdr.index('board_name'), hdr.index('board_type'), hdr.index('member_code')
        except ValueError:
            continue
        for r in rows[1:]:
            if len(r) <= max(ni, nt, nc):
                continue
            nm = r[ni].strip(); typ = r[nt].strip(); code = (r[nc] or '').strip()
            if not nm or not code:
                continue
            g.boards.setdefault(nm, []).append(code)
            g.board_type[nm] = typ
            g.stock_boards.setdefault(code, []).append(nm)
        for nm in g.boards:
            g.boards[nm] = list(dict.fromkeys(g.boards[nm]))
        for code in g.stock_boards:
            g.stock_boards[code] = list(dict.fromkeys(g.stock_boards[code]))
        log.info('[boards] loaded %s -> boards=%d stocks=%d' % (cand, len(g.boards), len(g.stock_boards)))
        return len(g.boards)
    return 0


def _load_sentiment():
    # 读 T 日情绪冰点基线（docs/40 契约）：date,...,divergence,emotion,emotion_basis
    # emotion/emotion_basis 为复盘 marker 机器判定的情绪温度档位+依据（旧表头缺失时为空串）
    g.sentiment = None
    fp = None; rows = None
    for cand in _sentiment_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        log.info("[sentiment] file not found (tried %s)" % _sentiment_paths())
        return None
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        rec = dict(zip(hdr, rows[1][:len(hdr)])) if len(rows) > 1 else {}
        g.sentiment = {
            "date": (rec.get("date") or "").strip(),
            "limit_up": int(_fnum(rec.get("limit_up"))),
            "break_count": int(_fnum(rec.get("break_count"))),
            "seal_rate": _fnum(rec.get("seal_rate")),
            "advance_rate": _fnum(rec.get("advance_rate")),
            "max_board": int(_fnum(rec.get("max_board"))),
            "lianban_count": int(_fnum(rec.get("lianban_count"))),
            "ice": bool(int(_fnum(rec.get("ice"))) or 0),
            "ice_streak": int(_fnum(rec.get("ice_streak"))),
            "warm_days": int(_fnum(rec.get("warm_days"))),
            "phase": (rec.get("phase") or "").strip(),
            "divergence": bool(int(_fnum(rec.get("divergence"))) or 0),
            "emotion": (rec.get("emotion") or "").strip(),
            "emotion_basis": (rec.get("emotion_basis") or "").strip(),
        }
        log.info("[sentiment] loaded %s -> ice=%s streak=%d adv=%.1f%% seal=%.0f%% emotion=%s (date=%s)" % (
            fp, g.sentiment["ice"], g.sentiment["ice_streak"], g.sentiment["advance_rate"],
            g.sentiment["seal_rate"] * 100.0, g.sentiment["emotion"] or "-", g.sentiment["date"]))
        return g.sentiment
    except Exception as e:
        log.info("[sentiment] skip(invalid) %s: %r" % (fp, e))
        return None


def _synth_pool_expect():
    # v0.27 涨停池预期三态：T-1 涨停池标的在竞价后也做三态初步确认——
    #   竞价涨幅>昨日开盘涨幅 = 竞价超预期(pending_exceed,观察)；绿开 = pending_miss(放弃)；其余 pending_meet(等盘中)。
    # 供方文件条目优先不覆盖；批量快照预置 g.auction_c（开盘口径=09:25 竞价价），避免 09:25 逐只 get_trend_data。
    if not BLS.get('pool_expect_enabled', True) or not g.zt_lianban:
        return 0
    codes = [c for c in g.zt_lianban if c not in g.exp_file]
    n_st = 0
    if BLS.get('pool_expect_skip_st', True):
        # v0.28 过滤 ST（供方 zt_lianban is_st 字段），对齐 AXquant 复盘口径
        n_st = sum(1 for c in codes if (g.zt_lianban[c] or {}).get('is_st'))
        codes = [c for c in codes if not (g.zt_lianban[c] or {}).get('is_st')]
    # v0.34 连板中位股规避：涨停池合成（云端兜底）同口径过滤中位（role_detail 缺失时按连板数近似）
    n_mid = sum(1 for c in codes if _mid_board_avoid(c))
    codes = [c for c in codes if not _mid_board_avoid(c)]
    if not codes:
        log.info('[exp] 涨停池竞价三态合成 -> exceed=0 meet=0 miss=0 st_skip=%d mid_skip=%d (全过滤)' % (n_st, n_mid))
        return 0
    day = str(get_trading_day())
    try:
        sn = _get_snapshot_many(codes, 400)
        for c, d in sn.items():
            if d and c not in g.spot:
                g.spot[c] = d
    except Exception:
        sn = {}
    n_ex = n_mt = n_ms = 0
    for code in codes:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            chg = (op / pre - 1.0) * 100.0 if (pre > 0 and op > 0) else None
            if chg is None:
                chg = _auction_change(code)          # 慢路径兜底（趋势接口）
            else:
                g.auction_c[code] = (day, chg)       # 预置竞价涨幅缓存（批量快照口径）
            chg = round(float(chg or 0.0), 2)        # 涨幅取 2 位小数，防浮点边界误判
            yopen, has = _yesterday_open_chg(code)
            if chg < 0:
                st = 'pending_miss'; n_ms += 1
            elif has and chg > yopen:
                st = 'pending_exceed'; n_ex += 1
            else:
                st = 'pending_meet'; n_mt += 1
            g.exp_file[code] = {
                'side': 'buy', 'entry_type': 'normal', 'expected_status': st,
                'yesterday_open_pct': yopen, 'has_yesterday_open': has,
                'expected_auction_change_pct': yopen if has else 0.0,
                'has_expected_auction': has, 'seal_amount_t0': 0.0, 'sell_policy_hint': '',
                '_src': 'zt_pool',
            }
        except Exception:
            continue
    log.info('[exp] 涨停池竞价三态合成 -> exceed=%d meet=%d miss=%d st_skip=%d mid_skip=%d' % (n_ex, n_mt, n_ms, n_st, n_mid))
    return n_ex + n_mt + n_ms

def _synth_selfwatch_expect():
    # v0.35e 自选股预期三态：对自选股（未在供方/涨停池条目中）在竞价后做三态初步确认，
    # 复用涨停池合成口径——竞价涨幅>昨日开盘涨幅=竞价超预期(观察)、绿开=miss(放弃)、其余=meet(等盘中)。
    # 数据（T 日开盘涨幅 _auction_change / 昨日开盘基准 _yesterday_open_chg）全部云端算法供给，
    # 与持仓股 _hold_exp_init 同源，不依赖供方文件；供方/涨停池条目优先不覆盖。
    if not BLS.get('pool_expect_enabled', True):
        return 0
    sw = [c for c in (getattr(g, 'selfwatch', []) or []) if c not in g.exp_file]
    n_mid = sum(1 for c in sw if _mid_board_avoid(c))
    sw = [c for c in sw if not _mid_board_avoid(c)]
    if not sw:
        log.info('[exp] 自选股竞价三态合成 -> exceed=0 meet=0 miss=0 mid_skip=%d' % n_mid)
        return 0
    day = str(get_trading_day())
    try:
        sn = _get_snapshot_many(sw, 200)
        for c, d in sn.items():
            if d and c not in g.spot:
                g.spot[c] = d
    except Exception:
        sn = {}
    n_ex = n_mt = n_ms = 0
    for code in sw:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            chg = (op / pre - 1.0) * 100.0 if (pre > 0 and op > 0) else None
            if chg is None:
                chg = _auction_change(code)
            else:
                g.auction_c[code] = (day, chg)
            chg = round(float(chg or 0.0), 2)
            yopen, has = _yesterday_open_chg(code)
            if chg < 0:
                st = 'pending_miss'; n_ms += 1
            elif has and chg > yopen:
                st = 'pending_exceed'; n_ex += 1
            else:
                st = 'pending_meet'; n_mt += 1
            g.exp_file[code] = {
                'side': 'buy', 'entry_type': 'normal', 'expected_status': st,
                'yesterday_open_pct': yopen, 'has_yesterday_open': has,
                'expected_auction_change_pct': yopen if has else 0.0,
                'has_expected_auction': has, 'seal_amount_t0': 0.0, 'sell_policy_hint': '',
                '_src': 'selfwatch',
            }
        except Exception:
            continue
    log.info('[exp] 自选股竞价三态合成 -> exceed=%d meet=%d miss=%d mid_skip=%d' % (n_ex, n_mt, n_ms, n_mid))
    return n_ex + n_mt + n_ms


def _confirm_expected(code):
    # 用真实竞价(get_trend_data)确认预期命中：exceed/meet/miss
    en = g.exp_file.get(code) or {}
    actual = _auction_change(code)   # 真实竞价涨幅%（标准函数）
    exp_status = en.get("expected_status") or ""
    if "exceed" in exp_status:
        bm, has_bm = _auction_benchmark(code)   # 基准缺失/<=0 不算达标（防过触发，v0.17）
        if not has_bm:
            return PM, actual
        return (CX if actual >= bm else PM), actual
    if "miss" in exp_status:
        return (CS if actual < 0 else PM), actual
    return PM, actual   # meet/未标注 -> 等盘中确认

def _exp_rt_status(code):
    # 预期买入实时三态（v0.14 两阶段）：tick/bar 均可调，返回 (state, reason)
    #   超预期：竞价达标 -> PM(observe 观察)；分时确认(两分钟上攻 或 一分钟冲涨停,且不破VWAP) -> CX(买入)；破VWAP -> CS 放弃
    #   一字板：L2 封单实时（>=超预期比率 CX / <=衰竭比率 CS）
    #   meet/未标注：走标准 _eval_intraday 三态
    en = g.exp_file.get(code) or {}
    e = g.exp.setdefault(code, {})
    for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct', 'seal_amount_t0', 'sell_policy_hint'):
        if en.get(_k) is not None:
            e[_k] = en[_k]
    entry = str(e.get("entry_type") or en.get("entry_type") or "normal")
    exp_status = str(e.get("expected_status") or en.get("expected_status") or "")
    au, _ra = _eval_auction(code)
    e["auction_status"] = au
    if entry == "one_word":
        st, _r = _exp_one_word(code)
        if "exceed" in exp_status and st == CM:
            return PM, "seal_wait"      # 一字超预期：封单未超预期(CM)不下单，等封单超预期(CX)才买
        return st, "seal"
    if "exceed" in exp_status:
        # 用户确认逻辑（T+1）：先竞价终态「初判」——竞价超预期才观察；未超预期则放弃（兜底，不再放任盘中买入）
        acon, actual = _confirm_expected(code)
        if acon != CX:
            # 兜底：基准缺失 / 真竞价缺失(actual~-100) / 竞价数据未就绪(actual=0且open未回填) 均不误弃，保持等待；确未达标 -> 放弃
            _bm, _has_bm = _auction_benchmark(code)
            _s0 = g.spot.get(code) or {}
            _op0 = float(_s0.get('open_px') or 0.0)
            if not _has_bm or actual < -90.0 or (actual == 0.0 and _op0 <= 0):
                return PM, "await_intraday_confirm"
            return CS, "auction_not_met(%.1f%%)" % actual    # 竞价初判未超预期 -> 放弃
        if (_two_1m_break(code) or _limit_up_within_1m(code)) and not _below_vwap(code):
            return CX, "intraday_exceed(%.1f%%)" % actual   # 分时确认超预期(两分钟上攻/一分钟冲涨停) -> 买
        if _below_vwap(code):
            return CS, "below_vwap_weak"                    # 分时转弱 -> 放弃
        return PM, "observe_auction_exceed %.1f%%" % actual   # 竞价超预期初步确认 -> 观察，等分时
    if "miss" in exp_status:
        return CS, "expect_miss"
    st = _eval_intraday(code, au)[0]
    return st, "intraday"

def _attempt_expected_buy(context, code):
    # 统一入口（tick/bar 共用）：超预期确认 -> 发单；确认 miss -> 放弃；否则等待
    if _mid_board_avoid(code):
        log.info('[mid-avoid] %s 连板中位股规避(expected_buy)' % _sn(code)); return None
    if code in (context.portfolio.positions or {}):
        return None
    if code in (g.exp_fired or set()):
        return None
    now = time.time()
    if now - g.buy_log.get(code, 0) < BLS["cold_secs"]:
        return None
    if not trade_open(code):
        return None
    st, reason = _exp_rt_status(code)
    if st == PM and str(reason).startswith("observe"):
        eo = g.exp.setdefault(code, {})
        if not eo.get("observe_seen"):
            eo["observe_seen"] = True
            log.info("[exp] %s observe %s -> 观察中(等分时确认)" % (_sn(code), reason))
    if st == CS:
        g.exp_fired.add(code)
        _save_state()
        log.info("[exp] %s miss=%s -> skip" % (_sn(code), reason))
        return True
    if st in (CX, CM):
        if not place_expected_order(context, code, note="exp_rt %s %s" % (st, reason)):
            return None   # 发单失败 -> 下次重试，不置 fired
        if st == CX and _dyn_unq_confirmed(code):
            log.info('[dyn-unq] %s CX 动态唯一龙头确认 -> 预期买入' % _sn(code))
        g.daily["bought"].append(code)
        g.exp_fired.add(code)
        g.buy_log[code] = now
        _save_state()
        return True
    return None   # 仍在等待，不爆

# ================= v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（P2，docs/30） =================
def _dyn_unq_state():
    # 状态容器（按日重置：auction 竞价唯一预判 / uniq 动态唯一龙头+跟风确认 / swept 已扫板）
    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    st = getattr(g, 'dyn_unq', None)
    if not st or st.get('day') != day:
        st = {'day': day, 'auction': {}, 'uniq': {}, 'swept': {}}
        g.dyn_unq = st
    return st


def _auction_level(sec):
    # 竞价身位（v0.38）：T-1 权威连板数（竞价未开盘，今日续板未知 -> 不加）；名单缺失回退 0
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        return int(zt.get('board_cnt') or 0)
    except Exception:
        return 0


def _dyn_level_of(sec, snap=None):
    # 盘中身位（v0.38）：权威 T-1 board_cnt + 今日是否触板（快照 last_px>=up*0.998，对齐 _limitup_days 续板口径）
    d = snap.get(sec) if snap else (g.spot.get(sec) or {})
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        base = int(zt.get('board_cnt') or 0)
    except Exception:
        base = 0
    try:
        up = float(d.get('up_px') or 0.0); px = float(d.get('last_px') or 0.0)
        if up > 0 and px and px >= up * 0.998:
            base += 1
    except Exception:
        pass
    return base


def _dyn_unq_confirmed(sec):
    # 动态唯一龙头已跟风确认（排序加分/CX标注/扫板前提）
    st = getattr(g, 'dyn_unq', None)
    if not st:
        return False
    u = (st.get('uniq') or {}).get(sec) or {}
    return bool(u.get('uniq') and u.get('confirm'))


def _dyn_unq_auction_unique(sec):
    # 竞价唯一（同身位竞品均不及预期）——扫板前提之一
    st = getattr(g, 'dyn_unq', None)
    if not st:
        return False
    a = (st.get('auction') or {}).get(sec) or {}
    return bool(a.get('unique'))
def _dyn_unq_auction_eval():
    # 竞价唯一预判（09:25/09:31 各算一次，0 盘中 RPC）：对 side=buy 预期条目统计
    # 同板块同身位（board_cnt）竞品中竞价超预期(pending_exceed)家数 -> 0 则本票竞价唯一。
    if not BLS.get('dyn_unq_enabled', True):
        return
    st = _dyn_unq_state()
    if st.get('auction_done'):
        return
    entries = {c: en for c, en in (g.exp_file or {}).items() if str(en.get('side') or '') == 'buy'}
    if not entries:
        return                                  # 无候选：不置 done（09:31 文件迟到可重算）
    cboard = {}
    board_of = {}
    for c in entries:
        for b in _concept_boards_of(c):
            if _board_members_file(b, 1):
                cboard[c] = b
                board_of.setdefault(b, []).append(c)
                break
    for c, en in entries.items():
        st_ = str(en.get('expected_status') or '')
        exceed = 'exceed' in st_
        if BLS.get('dyn_unq_mid_skip', True) and _mid_board_avoid(c):
            log.info('[dyn-unq] %s 中位股不参与唯一预判 -> skip' % _sn(c))
            continue
        b = cboard.get(c)
        lvl = _auction_level(c)
        peer_n = 0; peer_ex = 0
        for p in (board_of.get(b) or []) if b else []:
            if p == c:
                continue
            if _auction_level(p) != lvl:
                continue
            peer_n += 1
            if 'exceed' in str((g.exp_file.get(p) or {}).get('expected_status') or ''):
                peer_ex += 1
        st['auction'][c] = {'exceed': exceed, 'level': lvl, 'peer_cnt': peer_n,
                            'peer_exceed': peer_ex, 'unique': (exceed and peer_ex == 0)}
        if exceed:
            log.info('[dyn-unq] 竞价唯一预判 %s 身位=%s 竞品=%d/超预期=%d -> %s' % (
                _sn(c), lvl, peer_n, peer_ex, '唯一' if peer_ex == 0 else '并列'))
    st['auction_done'] = True
    return len(st['auction'])


def _dyn_unq_eval_uniq(sec, st, now):
    # A 动态唯一首评：取首概念板块成员批量回填快照，身位无更高/并列 -> 唯一龙头
    boards = [b for b in _concept_boards_of(sec) if _board_members_file(b, 1)]
    if not boards:
        return
    board = boards[0]
    members = [m for m in _board_members_file(board, int(BLS.get('dyn_unq_member_cap', 15))) if m]
    if not members:
        return
    _need = [m for m in members if not (g.spot.get(m) or {}).get('last_px')]
    if _need:
        try:
            _snap = _get_snapshot_many(_need, len(_need)) or {}
            for _m, _d in _snap.items():
                if _d:
                    g.spot[_m] = _d
        except Exception:
            pass
    my_lvl = _dyn_level_of(sec, {sec: g.spot.get(sec) or {}})
    higher = same = False
    for m in members:
        if m == sec:
            continue
        ml = _dyn_level_of(m, {m: g.spot.get(m) or {}})
        if ml > my_lvl:
            higher = True
        elif ml == my_lvl:
            same = True
    if higher or same:
        st['uniq'][sec] = {'board': board, 'uniq': False, 'ts': now, 'level': my_lvl, 'members': members}
        return
    st['uniq'][sec] = {'board': board, 'uniq': True, 'ts': now, 'level': my_lvl,
                       'members': members, 'confirm': False, 'confirm_ts': 0,
                       'follow_ev': False, 'last_follow': 0.0, 'surge_cnt': 0}
    log.info('[dyn-unq] %s 板块=%s 身位=%d -> 动态唯一龙头(首触)' % (_sn(sec), board, my_lvl))
def _dyn_unq_eval_follow(sec, st, u):
    # B 跟风确认：首触后窗口内，同板块身位更低且未封板成员涨幅前5算 1m surge，
    # 达标家数 >= dyn_unq_follower_min -> confirm（15s 节流重评，窗口内批量快照一次）。
    now = time.time()
    if u.get('confirm'):
        return
    if now - float(u.get('last_follow') or 0) < 15.0:
        return
    u['last_follow'] = now
    first_ts = ((g.first_zt or {}).get(sec) or {}).get('ts') or u.get('ts') or now
    if now - float(first_ts) > float(BLS.get('dyn_unq_follow_win_sec', 300.0)):
        return
    members = u.get('members') or []
    if not u.get('follow_ev'):
        _need = [m for m in members if m != sec and not (g.spot.get(m) or {}).get('last_px')]
        if _need:
            try:
                _snap = _get_snapshot_many(_need, len(_need)) or {}
                for _m, _d in _snap.items():
                    if _d:
                        g.spot[_m] = _d
            except Exception:
                pass
        u['follow_ev'] = True
    my_lvl = u.get('level') or _dyn_level_of(sec, {sec: g.spot.get(sec) or {}})
    followers = []
    for m in members:
        if m == sec:
            continue
        d = g.spot.get(m) or {}
        try:
            up = float(d.get('up_px') or 0.0); px = float(d.get('last_px') or 0.0)
            pre = float(d.get('preclose_px') or 0.0)
        except Exception:
            continue
        if up > 0 and px and px >= up * 0.998:
            continue                           # 已封板：非跟风（并列冲板）
        if _dyn_level_of(m, {m: d}) >= my_lvl:
            continue                           # 身位不低于龙头：不算跟风
        chg = (px / pre - 1.0) * 100.0 if (pre > 0 and px > 0) else -1.0
        if chg > 0:
            followers.append((chg, m))
    followers.sort(reverse=True)
    surge_cnt = 0
    for _chg, m in followers[:int(BLS.get('dyn_unq_surge_top_n', 5))]:
        try:
            if _elastic_1m_surge(m) >= float(BLS.get('dyn_unq_surge_pct', 1.5)):
                surge_cnt += 1
        except Exception:
            continue
    u['surge_cnt'] = surge_cnt
    if surge_cnt >= int(BLS.get('dyn_unq_follower_min', 2)):
        u['confirm'] = True; u['confirm_ts'] = now
        log.info('[dyn-unq] %s 跟风确认 %d家(1m>=%.1f%%) -> 确认' % (
            _sn(sec), surge_cnt, float(BLS.get('dyn_unq_surge_pct', 1.5))))
def _try_dyn_sweep(context, st=None):
    # D 竞价唯一扫板：竞价终态超预期+同身位竞品不及预期(竞价唯一)+开盘上攻冲板(_two_1m_break/
    # _limit_up_within_1m)+跟风确认+现价<涨停价(未封板) -> 涨停价扫板(预算20%)，避免买不到；已封板不扫。
    if not BLS.get('dyn_sweep_enabled', True):
        return
    if _min_age() > int(BLS.get('dyn_sweep_window_minute', 15)):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    st = st or _dyn_unq_state()
    positions = context.portfolio.positions
    now = time.time()
    for sec, en in (g.exp_file or {}).items():
        if str(en.get('side') or '') != 'buy':
            continue
        if sec in positions or sec in g.daily['bought'] or sec in st.get('swept', {}):
            continue
        if not _dyn_unq_auction_unique(sec) or not _dyn_unq_confirmed(sec):
            continue
        if not trade_open(sec):
            continue
        if _is_one_word_open(sec) or _block_sealed_buy(sec):
            continue
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or px <= 0 or up <= 0 or px >= up * 0.998:
            continue                           # 已触板/现价=涨停价：不扫板（限价=涨停价只在前排队）
        if not (_two_1m_break(sec) or _limit_up_within_1m(sec)):
            continue                           # 开盘上攻冲板（两分钟上攻 或 一分钟冲涨停）
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            continue
        limit = _order_limit(sec, 'buy', 'board')
        if not limit:
            log.info('[dyn-sweep] %s sealed -> no sweep' % _sn(sec))
            continue
        place_order(context, sec, 'buy',
                    note='dyn_sweep px=%.2f limit=%.2f 跟风%d家' % (
                        px, limit, (st.get('uniq', {}).get(sec) or {}).get('surge_cnt', 0)),
                    mode='board', ratio=float(BLS.get('dyn_sweep_budget_ratio', 0.20)))
        g.daily['bought'].append(sec); g.buy_log[sec] = now
        st['swept'][sec] = {'ts': now}
        _save_state()
        return                                   # 一帧一单
def _try_dyn_unq(context):
    # v0.38 盘中动态唯一+跟风确认（P2-A/B/C）：09:30-10:00 帧末；10:00 后停止新评估、保留 confirm。
    if not BLS.get('dyn_unq_enabled', True):
        return
    if _min_age() > int(BLS.get('dyn_unq_window_minute', 30)):
        return
    positions = context.portfolio.positions
    st = _dyn_unq_state()
    now = time.time()
    try:
        for sec in list(positions):               # C-持有侧：确认龙头持仓提示（不改卖出阈值）
            if _dyn_unq_confirmed(sec) and (g.first_zt or {}).get(sec):
                _hold_arb_log(sec, '盘中动态唯一龙头确认 -> 持有提示(不改卖出阈值)')
    except Exception:
        pass
    cands = [c for c, en in (g.exp_file or {}).items()
             if str(en.get('side') or '') == 'buy' and (g.first_zt or {}).get(c) and c not in positions]
    for sec in cands:
        try:
            u = st['uniq'].get(sec)
            if u is not None and u.get('uniq') is False:
                if now - float(u.get('ts') or 0) < 60.0:
                    continue                       # 非唯一重评节流（竞品炸板身位回落可转唯一）
                u['ts'] = now
            if u is None or u.get('uniq') is False:
                _dyn_unq_eval_uniq(sec, st, now)   # A 动态唯一（首评/重评）
                u = st['uniq'].get(sec)
            if not u or not u.get('uniq'):
                continue
            _dyn_unq_eval_follow(sec, st, u)       # B 跟风确认
        except Exception as e:
            _warn('dyn_unq %s fail %r' % (_sn(sec), e))
    _try_dyn_sweep(context, st)                    # D 竞价唯一扫板


def _pool_exp_priority(code):
    # v0.27 涨停池观察候选排序：分最高优先，其次「最主动」（最早触板/最快拉升）
    try:
        sc = float(score_now(code) or 0.0)
    except Exception:
        sc = 0.0
    if _dyn_unq_confirmed(code):
        sc += float(BLS.get('dyn_unq_sort_bonus', 2.0))   # v0.38 动态唯一龙头确认排序加分
    act = _first_zt_ms(code) or 1e18   # v0.37 毫秒归一（逐笔 ms 优先, 帧 ts 归一）
    return (-sc, act)

def _try_expected_buys(context):
    # 预期买入：tick(3s) 与 handle_data(1m) 共用同一判定/去重，避免双触发
    if _min_age() > int(BLS.get('exp_buy_window_min', 30)):
        return                       # 预期买入窗口：10:00 前（其它类）
    if not g.exp_file or len(g.daily["bought"]) >= BLS["daily_max_buy"]:
        return
    provider = []
    pool = []
    for code, en in g.exp_file.items():
        if str(en.get("side") or "") != "buy":
            continue
        (pool if str(en.get("_src") or "") in ("zt_pool", "selfwatch") else provider).append(code)
    pool.sort(key=_pool_exp_priority)   # v0.27 涨停池合成：分最高/最主动优先
    for code in provider + pool:
        _attempt_expected_buy(context, code)
        if len(g.daily["bought"]) >= BLS["daily_max_buy"]:
            return

# ================= 买入 =================
def _ma5_first_5d(sec):
    # 对齐 AXquant：5日内首次回踩 MA5 = 此前 4 个交易日盘中最低均未触及/跌破各自 MA5。
    # 数据不足(少于9根)保守返回 False（与 AXquant 一致）；缺 low 列时用 close 近似。
    df = _hist_1d(sec)
    if df is None or len(df) < 9:
        return False
    try:
        closes = list(df['close'])
        lows = list(df['low']) if 'low' in df else closes
    except Exception:
        return False
    n = len(closes)
    # 只看此前 4 个交易日（今日为第 n-1 根）；各日 MA5 = 该日向前 5 根收盘均值（对齐 AXquant desc向前取样）
    for i in range(n - 2, max(n - 6, 0), -1):
        lo = i - 4
        if lo < 0:
            continue
        ma5 = sum(closes[lo:i+1]) / 5.0
        if ma5 <= 0:
            return False
        if lows[i] > 0 and lows[i] <= ma5 + 0.001:
            return False
    return True
def try_ma5_buy(context):
    if _min_age() > int(BLS.get('ma5_buy_window_min', 240)):
        return                       # 5日低吸窗口：10:30 前
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        tags = _tags(sec)
        if BLS.get('ma5_core_only', True) and 'CORE' not in tags:
            continue   # 低吸仅对核心(CORE)标签股（对齐 AXquant）
        if _mid_board_avoid(sec):
            log.info('[mid-avoid] %s 连板中位股规避(ma5)' % _sn(sec)); continue
        if BLS.get('ma5_require_bs', True) and 'BS' not in tags:
            continue   # 对齐 AXquant CORE+BS：低吸还要 100日新高标签
        if BLS.get('ma5_first_5d', True) and not _ma5_first_5d(sec):
            continue   # 对齐 AXquant：只有 5日内首次回踩 MA5 才触发，防重复低吸
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        px = last_px(sec); ma5 = _ensure_ma5(sec)
        if not px or px <= 0 or not ma5:
            continue
        if px <= ma5 * BLS['ma5_loose_high']:
            score = score_now(sec)
            if score >= BLS['buy_score_min'] and _buy_red_ok(sec):
                place_order(context, sec, 'buy', note='ma_pullback px=%.2f ma5=%.2f score=%.1f red=%.2f tags=%s' % (px, ma5, score, _red_ratio(sec), ','.join(_tags(sec))), mode='pullback')
                g.daily['bought'].append(sec); g.buy_log[sec] = now
                _save_state()
            if len(g.daily['bought']) >= BLS['daily_max_buy']:
                break


def try_core_buy(context):
    # 核心票买入（v0.18，对齐 AXquant CORE 门禁）：score>=buy_score_min 且 连板<core_max_lianban；
    # 一字/封死涨停不排队；追高定价（封顶涨停/弹性10%上限）。tag CORE 已并入打分，本入口补门禁与执行。
    if not BLS.get('core_buy_enabled', True):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if _min_age() > int(BLS.get('core_buy_window_min', 30)):
        return                       # 核心票买入窗口：10:00 前（其它类）
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        if 'CORE' not in _tags(sec):
            continue
        if _mid_board_avoid(sec):
            log.info('[mid-avoid] %s 连板中位股规避(core_buy)' % _sn(sec)); continue
        if _is_one_word_open(sec):
            continue                       # 一字板（开盘即涨停）不追（对齐 first_board/elastic 排除）
        if _limitup_days(sec) >= int(BLS.get('core_max_lianban', 6)):
            continue
        if BLS.get('core_sealed_skip', True) and _block_sealed_buy(sec):
            continue
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        score = score_now(sec)
        if score >= BLS['buy_score_min'] and _buy_red_ok(sec):
            place_order(context, sec, 'buy', note='core_buy px=%.2f score=%.1f tags=%s' % (px, score, ','.join(_tags(sec))), mode='chase')
            g.daily['bought'].append(sec); g.buy_log[sec] = now
            _save_state()
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            break


# ================= 首板打板（AXquant first_board_buy，v0.18） =================
def _sector_chg(sec):
    # 现价涨幅（小数）
    px = last_px(sec); pre = pre_close(sec)
    if not px or not pre or pre <= 0:
        return 0.0
    return px / pre - 1.0


def _is_one_word_open(sec):
    # 一字板：开盘价>=涨停价*0.998（开盘即涨停）；打首板闸门排除
    s = g.spot.get(sec) or {}
    op = float(s.get('open_px') or 0.0)
    up = float(s.get('up_px') or 0.0)
    return bool(op and up and op >= up * 0.998)


def _is_first_board(sec):
    # 首板：T-1 权威连板名单 board_cnt<1；名单缺失回退 连板天数<=1（今日首触）
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        return int(zt.get('board_cnt') or 0) < 1
    return _limitup_days(sec) <= 1


def _board_member_codes(sec):
    # 所属板块成分代码（与 _board_member_changes 同口径，缓存60s）
    if not getattr(g, 'bs_codes', None):
        g.bs_codes = {}
    c = g.bs_codes.get(sec)
    if c and (time.time() - c[0]) < 60:
        return list(c[1])
    codes = []
    cap = int(BLS.get('board_member_cap', 20))
    try:
        # v0.37 首板闸门比较宇宙优先概念文件口径（THS 概念, 与弹性套利一致）；文件未加载回退 API 首板块前 N
        if getattr(g, 'boards', None):
            for b in _concept_boards_of(sec):
                codes = _board_members_file(b, cap)
                if codes:
                    break
        if not codes:
            blocks = get_stock_blocks(sec) or {}
            board_code = None
            for lst in blocks.values():
                if isinstance(lst, list):
                    for row in lst:
                        if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                            board_code = row[0]
                            break
                if board_code:
                    break
            if board_code:
                codes = [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board_code)) or [])[:cap]) if x]
    except Exception:
        codes = []
    g.bs_codes[sec] = (time.time(), tuple(codes))
    return codes


def _board_top_gainer(sec):
    # 板块内涨幅最高（且为正）：sec 现价涨幅 >= 同板块全部成员（首板闸门之一）
    my = _sector_chg(sec)
    if my <= 0:
        return False
    mem = [m for m in _board_member_codes(sec) if m != sec]
    _need = [m for m in mem if not (g.spot.get(m) or {}).get('last_px') or not (g.spot.get(m) or {}).get('preclose_px')]
    if _need:
        try:
            _sn = _get_snapshot_many(_need, len(_need)) or {}
            for _m, _d in _sn.items():
                if _d:
                    g.spot[_m] = _d
        except Exception:
            pass
    for m in mem:
        try:
            d = g.spot.get(m) or {}
            mp = float(d.get('preclose_px') or 0.0); mpx = float(d.get('last_px') or 0.0)
        except Exception:
            continue
        if mp > 0 and mpx > 0 and (mpx / mp - 1.0) > my + 1e-9:
            return False
    return True


def _first_zt_ms(sec):
    # 首触时刻归一（YYYYMMDDHHMMSSmmm 毫秒整数, 与逐笔 business_time / 快照 hsTimeStamp 同格式）：
    # 逐笔/快照 ms 优先；缺省把帧 ts（epoch 秒）归一到同格式, 避免 17 位与 13 位 epoch 混比错序。
    f = g.first_zt.get(sec) or {}
    ms = f.get('ms')
    if ms:
        try:
            return int(ms)
        except Exception:
            pass
    ts = f.get('ts') or 0.0
    if not ts:
        return 0
    lt = time.localtime(float(ts))
    return int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int(float(ts) % 1 * 1000)


def _board_first_zt(sec):
    # 主动（最快拉升）：同板块成员中首个触板（无更早触板成员则本票为最快）；缺成员对比时放行
    # v0.37 比较用逐笔毫秒归一（同帧 ts 并列 -> 精确到那一笔）；本票未记录触板时刻时保守非最快
    my = _first_zt_ms(sec) or None
    for m in _board_member_codes(sec):
        if m == sec:
            continue
        if _is_one_word_open(m):
            continue                      # 一字板成员不参与"主动最快"竞争（竞价一字非主动拉升）
        t = _first_zt_ms(m)
        if t and (my is None or t < my - 1e-6):
            return False
    return True


def _try_first_board_buy(context, sec, rank_secs=None):
    # 首板确认->打板（tick 首触 / 1m 兜底共用）：开盘10分钟内 + 非一字板 + 板块内涨幅最高 + 主动最快拉升
    # + 板块强度前三（v0.23 板块目标）
    if not BLS.get('first_board_buy_enabled', True):
        return
    if _min_age() > int(BLS.get('first_board_minute', 10)):
        return                       # 开盘10分钟内
    if sec in getattr(context, 'portfolio', None).positions:
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if _is_one_word_open(sec):
        return                       # 除一字板
    if not _is_first_board(sec):
        return                       # 仅首板（T-1 无连板）
    if _mid_board_avoid(sec):
        log.info('[mid-avoid] %s 连板中位股规避(first_board)' % _sn(sec)); return
    now = time.time()
    if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
        return
    if BLS.get('board_rank_enabled', True):
        rs = rank_secs if rank_secs is not None else _near_limit_cands(_pool())
        if not _board_rank_top3(sec, rs or [sec]):
            return                       # 板块目标：强度前三（v0.23）
    if not _board_top_gainer(sec):
        return                       # 板块内涨幅最高
    if not _board_first_zt(sec):
        return                       # 主动：板块内首个触板
    if _block_sealed_buy(sec):
        return                       # 一字/封死涨停不排队（防御）
    amt, _cnt = _seal_metrics(sec)   # v0.46 首板封单下限（L2 买一挂单金额, 防假封秒炸）
    seal_min = float(BLS.get('first_board_seal_min', 50000.0))
    _big_r = _l2_big_ratio(sec)   # v0.47 大单加持：占比>=10% 豁免封单下限（预封扫板）
    if seal_min > 0 and amt > 0 and amt < seal_min and not _l2_big_ok(sec):
        log.info('[firstboard] %s 封单不足 seal=%.0f<%.0f 且无大单加持(big=%.2f%%) -> skip' % (
            _sn(sec), amt, seal_min, _big_r * 100.0 if _big_r >= 0 else 0.0))
        return
    s = g.spot.get(sec) or {}
    up = float(s.get('up_px') or 0.0)
    if not up or up <= 0:
        return
    limit = _order_limit(sec, 'buy', 'board')
    if not limit:
        log.info('[firstboard] %s sealed -> skip board queue' % _sn(sec))
        return
    place_order(context, sec, 'buy', note='first_board_buy px=%.2f limit=%.2f chg=%.1f%% tags=%s' % (
        last_px(sec) or 0.0, limit, _sector_chg(sec) * 100.0, ','.join(_tags(sec))), mode='board',
        ratio=BLS.get('board_buy_budget_ratio', 0.20))
    g.daily['bought'].append(sec); g.buy_log[sec] = now
    if not getattr(g, 'first_board_fired', None):
        g.first_board_fired = set()
    g.first_board_fired.add(sec)
    _save_state()


def _try_first_board_buy_1m(context):
    # 1m 兜底（回测/丢 tick）：对池内逼近涨停的首板候选补一次首板闸门评估
    if not BLS.get('first_board_buy_enabled', True):
        return
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if sec in (getattr(g, 'first_board_fired', None) or set()):
            continue
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or not up or px < up * 0.998:
            continue
        if not g.first_zt.get(sec):
            g.first_zt[sec] = {'first_seal': 0.0, 'first_bids': 0, 'ts': time.time(), 'break': False}
        try:
            _try_first_board_buy(context, sec)
        except Exception as e:
            _warn('first_board_buy(1m) fail %r' % e)


# ================= 弹性套利 elastic_arb（AXquant，v0.19 Phase 1） =================
def _elastic_yizi_pool():
    # 一字板统计候选：池(自选+预期+watch) + T-1 涨停名单（今日续板/一字近似；全市场实时名单 PT 无）
    out = list(_pool()) + list((getattr(g, 'zt_lianban', {}) or {}).keys())
    return [x for x in (_norm_sec(c) for c in out) if x]


def _boards_of(sec):
    # 所属板块代码列表（get_stock_blocks 首层；与 _board_member_codes 同口径）
    # v0.25：300s 缓存 + 帧预算 blocks（弹性强板块判定从每帧逐只 -> 缓存/预算内）
    try:
        dh = _get_ds()
        v = dh.cached('blocks', sec, 300.0, lambda: _fetch_boards_of(sec), budget='blocks', stale_ok=True)
        return list(v) if v else []
    except Exception:
        return []


def _fetch_boards_of(sec):
    try:
        blocks = get_stock_blocks(sec) or {}
        names = []
        for lst in blocks.values():
            if isinstance(lst, list):
                for row in lst:
                    if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                        names.append(str(row[0]).strip())
        return tuple(names)
    except Exception:
        return ()


def _elastic_yizi_scan():
    # 板块一字板统计（60s 缓存，按日重置）：开盘一字（open>=前收×(1+限幅)×0.995 且 L2 封单>0）
    # -> 板块计数>=min_yizi 的强板块（对齐 AXquant A 段）
    if not getattr(g, 'elastic_cache', None):
        g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
    c = g.elastic_cache
    day = str(get_trading_day())
    now = time.time()
    if c.get('day') == day and now - c.get('ts', 0.0) < float(BLS.get('elastic_arb_cache_ttl', 60.0)):
        return c.get('strong', {})
    # 批量补快照（仅缺）：zt_lianban 等非池代码一次 get_snapshot(列表) 回填 g.spot，避免逐只串行拉取
    _need = [sec for sec in _elastic_yizi_pool() if sec not in g.spot]
    if _need:
        try:
            for _cc, _dd in (_get_snapshot_many(_need, len(_need)) or {}).items():
                if _dd:
                    g.spot[_cc] = _dd
        except Exception:
            pass
    yizi = []
    for sec in _elastic_yizi_pool():
        try:
            s = g.spot.get(sec) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            if pre <= 0 or op <= 0 or op < pre * (1.0 + _limit_threshold(sec)) * 0.995:
                continue
            seal, _b = _seal_metrics(sec)
            if seal > 0:
                yizi.append(sec)
        except Exception:
            continue
    from collections import Counter
    cnt = Counter()
    for sec in yizi:
        for b in _boards_of(sec):
            cnt[b] += 1
    strong = {b: n for b, n in cnt.items() if n >= int(BLS.get('elastic_arb_min_yizi', 2))}
    c.update(day=day, ts=now, strong=strong)
    log.info('[elastic] yizi=%d strong_boards=%d' % (len(yizi), len(strong)))
    return strong


def _elastic_in_strong_board(sec, strong):
    # 候选属于任一强板块
    for b in _boards_of(sec):
        if b in strong:
            return True
    return False


def _calc_1m_surge(sec):
    # 最新 1m 柱 (close-open)/open 涨幅 %；无数据返回 0（对齐 AXquant min_1m_surge）
    df = get_price(sec, start_date=None, end_date=None, count=2, frequency='1m')
    if df is None or len(df) < 1:
        return 0.0
    o = float(df['open'].iloc[-1] or 0.0); close_px = float(df['close'].iloc[-1] or 0.0)
    return (close_px / o - 1.0) * 100.0 if o > 0 else 0.0


def _elastic_1m_surge(sec):
    # 1m 大阳线 15s 缓存（统一 DataHub 注册表），避免窗口内重复拉取
    try:
        dh = _get_ds()
        v = dh.cached('m1_surge', sec, float(BLS.get('m1_surge_cache_ttl', 15.0)),
                      lambda: _calc_1m_surge(sec), budget='m1')
        return v if v is not None else 0.0
    except Exception:
        return 0.0


def _elastic_ask1(sec):
    # 卖一价（L2 十档，成交确性好）；缺省回退最新价（对齐 AXquant ask_price_1）
    try:
        gp = _gear(sec)
        a = (gp.get('ask_grp') or {}).get(1) or []
        if isinstance(a, (list, tuple)) and len(a) >= 1:
            v = float(a[0] or 0.0)
            if v > 0:
                return v
    except Exception:
        pass
    return last_px(sec) or 0.0


def _try_elastic_arb_buy(context):
    # 弹性套利（v0.19 Phase 1，AXquant elastic_arb）：板块一字>=2 情绪爆发 -> 抓同板块 20cm 弹性标的
    if not BLS.get('elastic_arb_enabled', True):
        return
    if _min_age() > int(BLS.get('elastic_arb_window_minute', 10)):
        return                       # 仅开盘后 10 分钟内
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    strong = _elastic_yizi_scan()
    if not strong:
        return
    positions = context.portfolio.positions
    rank_secs = [c for c in _pool() if _is_elastic_20cm(c)]   # v0.23 板块目标：池内 20cm 所属板块
    for sec in _pool():
        if sec in positions:
            continue
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if not _is_elastic_20cm(sec):
            continue                 # 仅 300/301/688/689 20cm
        if not _elastic_in_strong_board(sec, strong):
            continue                 # 属于强板块
        if BLS.get('board_rank_enabled', True) and not _board_rank_top3(sec, rank_secs or [sec]):
            continue                 # 板块目标：强度前三（v0.23）
        if _is_one_word_open(sec):
            continue                 # 不追一字
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            continue
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > float(BLS.get('elastic_arb_max_open_change', 12.0)):
            continue                 # 大幅高开兑现
        if _elastic_1m_surge(sec) < float(BLS.get('elastic_arb_min_1m_surge', 3.0)):
            continue                 # 1m 大阳线力度不足
        px = last_px(sec)
        if not px or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg < float(BLS.get('elastic_arb_min_change', 6.0)) or chg > float(BLS.get('elastic_arb_max_change', 10.0)):
            continue                 # 当前涨幅 6~10% 区间（防炸板）
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        if _block_sealed_buy(sec):
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        place_order(context, sec, 'buy', note='elastic_arb px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%% open=%.1f%% boards=%s' % (
            px, limit or px, chg, _elastic_1m_surge(sec), open_chg, ','.join(list(strong.keys())[:2])), mode='chase')
        g.daily['bought'].append(sec); g.buy_log[sec] = now
        _save_state()


def _board_probe():
    # 板块口径探针（v0.36c，每日一次）：打印 get_stock_blocks 全类别样本，
    # 并对 HY/GN 代码各调 get_industry_stocks 打印返回成员数（验证概念板块能否被行业接口消费）。
    try:
        if not BLS.get('board_probe_enabled', True):
            return None
        day = str(get_trading_day())
        if getattr(g, 'board_probe_day', None) == day:
            return getattr(g, 'board_probe', None)
        g.board_probe_day = day
        samp = [x for x in (_norm_sec(c) for c in (list(get_positions()) + BLS['universe'] + _pool())) if x][:2]
        if not samp:
            samp = ['600570.XSHG']
        out = {}
        for sec in samp:
            try:
                blocks = get_stock_blocks(sec) or {}
            except Exception:
                blocks = {}
            rows = {}
            for cat, lst in (blocks or {}).items():
                rows[str(cat)] = [str(r[0]) if isinstance(r, list) and r else '' for r in (lst or [])[:3]]
            codes = []
            for cat in ('HY', 'GN', 'ZJHHY', 'DY'):
                for r in (blocks or {}).get(cat, []) or []:
                    if isinstance(r, list) and r and str(r[0]).strip():
                        codes.append((cat, str(r[0]).strip()))
                        break
            counts = {}
            for cat, code in codes[:2]:
                try:
                    counts['%s:%s' % (cat, code)] = len(get_industry_stocks(code) or [])
                except Exception:
                    counts['%s:%s' % (cat, code)] = -1
            out[sec] = {'cats': rows, 'members': counts}
            log.info('[probe] %s blocks=%s industry_members=%s' % (_sn(sec), rows, counts))
        g.board_probe = out
        return out
    except Exception as e:
        _warn('board probe fail: %r' % e)
        return None


def _elastic_top_cand_src():
    # 新最强板块候选范围：动态 watch ∪ 固定池 ∪ T-1 涨停名单（覆盖不在池内的新爆发板块）
    out = list(_pool()) + list((getattr(g, 'zt_lianban', {}) or {}).keys())
    return [x for x in (_norm_sec(c) for c in out) if x]


def _board_open_gain(board_code):
    # 板块成员开盘涨幅均值%（9:25 竞价终态后 open 固定 -> 按日缓存一次，预算 board）
    try:
        dh = _get_ds()
        v = dh.cached('board_open', str(board_code), 86400.0,
                      lambda: _fetch_board_open_gain(board_code), budget='board', stale_ok=True)
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0


def _fetch_board_open_gain(board_code):
    # 板块代码/名称 -> 成员批量快照开盘涨幅均值%（最多20只；v0.36e 成员走 _board_members_file，文件 THS 概念口径，未加载回退 API）
    gains = []
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(board_code, 20)) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        for m in mem:
            try:
                d = sn.get(m) or {}
                pre = float(d.get('preclose_px') or 0.0)
                op = float(d.get('open_px') or 0.0)
                if pre > 0 and op > 0:
                    gains.append(op / pre - 1.0)
            except Exception:
                continue
    except Exception:
        gains = []
    return (sum(gains) / len(gains)) * 100.0 if gains else 0.0


# ================= v0.36e 概念板块口径（仅弹性套利链路：文件 THS 概念 -> 未加载回退 API） =================
def _concept_boards_of(sec):
    # 概念板块归属（v0.36e）：优先文件 g.stock_boards（board_type=concept，THS 概念口径）；
    # 文件未加载回退 API _boards_of（best-effort）
    try:
        sb = getattr(g, 'stock_boards', None)
        if sb:
            bts = getattr(g, 'board_type', None) or {}
            return [nm for nm in (sb.get(sec) or []) if str(bts.get(nm) or '') == 'concept']
        return _boards_of(sec)
    except Exception:
        return _boards_of(sec)


def _board_members_file(board, cap):
    # 板块成员（v0.36e）：优先文件 g.boards（THS 板块名 -> 成员列表）；
    # 文件未加载回退 API get_industry_stocks（best-effort）
    try:
        gb = getattr(g, 'boards', None)
        if gb:
            mem = gb.get(str(board)) or []
            return [x for x in (_norm_sec(m) for m in mem[:cap]) if x]
        return [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board)) or [])[:cap]) if x]
    except Exception:
        try:
            return [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board)) or [])[:cap]) if x]
        except Exception:
            return []


def _concept_snap_union(boards):
    # 合并快照（v0.36e）：候选概念板块成员并集分帧批量拉取（frame_snap_batch 上限/帧，预算 board，
    # 每帧一批=1 次批量 get_snapshot）；续算账本 g.csnap_led 按日+候选集 key 保留进度（同 _calc_board_5d 模式）：
    # 首轮分帧补齐（覆盖率<0.5 前不判 top1），整轮完成后滚动刷新（不清空：旧值顶住逐批更新）。
    # 返回 (snap, covered_ratio)；整轮完成后 ratio 始终=1.0（旧值顶住）。
    dh = _get_ds()
    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    key = '|'.join(sorted(str(b) for b in boards))
    led = getattr(g, 'csnap_led', None)
    if not led or led.get('day') != day or led.get('key') != key:
        led = {'day': day, 'key': key, 'members': [], 'idx': 0, 'snap': {}, 'ts': 0.0, 'complete': False}
        g.csnap_led = led
    now = time.time()
    if now - float(led.get('ts') or 0.0) < float(BLS.get('board_rank_ttl_fast', 3.0)):
        return led['snap'], (1.0 if led.get('complete') else float(led.get('ratio') or 0.0))
    if not led['members']:
        seen = set()
        for b in boards:
            for m in _board_members_file(b, int(BLS.get('elastic_top_member_cap', 20))):
                if m not in seen:
                    seen.add(m); led['members'].append(m)
    total = len(led['members'])
    idx = int(led.get('idx') or 0)
    if idx >= total:
        idx = 0; led['idx'] = 0          # 整轮完成 -> 滚动刷新（不清空：旧值顶住，逐批更新）
        led['complete'] = True
    if dh.spend('board'):
        cap = int(BLS.get('frame_snap_batch', 100))
        batch = led['members'][idx:idx + cap]
        try:
            sn = _get_snapshot_many(batch, len(batch))
            if isinstance(sn, dict):
                led['snap'].update(sn)
                led['idx'] = idx + len(batch)
        except Exception:
            pass
        led['ts'] = now
    ratio = (int(led.get('idx') or 0) / total) if total else 1.0
    if led.get('complete'):
        ratio = 1.0
    led['ratio'] = ratio
    return led['snap'], ratio


def _concept_board_strength(board, snap=None):
    # 概念板块强度（v0.36e）：文件已加载 -> 成员=_board_members_file、快照=同帧合并 snap/单板批量；
    # 文件未加载 -> 回退 API _board_strength_by_code（预算/缓存同旧链）
    try:
        if not getattr(g, 'boards', None):
            return _board_strength_by_code(board)
    except Exception:
        return _board_strength_by_code(board)
    mem = _board_members_file(board, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return 0.0
    if not snap:
        led = getattr(g, 'csnap_led', None)
        if led and (time.time() - float(led.get('ts') or 0.0)) < float(BLS.get('board_rank_ttl_fast', 3.0)):
            snap = led.get('snap') or {}
        else:
            snap = _get_snapshot_many(mem, len(mem)) or {}
    chgs = []
    for m in mem:
        try:
            d = snap.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre > 0 and px > 0:
                chgs.append(px / pre - 1.0)
        except Exception:
            continue
    return (sum(chgs) / len(chgs)) * 100.0 if chgs else 0.0


def _compute_concept_board_top1_lead(boards):
    # 概念板块（强度第一+领先幅度）：合并快照一次批量覆盖全候选；覆盖率>=0.5 才出 top1
    if not boards:
        return (None, 0.0)
    snap, ratio = _concept_snap_union(boards)
    if ratio < 0.5:
        return (None, 0.0)
    best = None; best_st = None; second_st = None
    for b in boards:
        try:
            st = _concept_board_strength(b, snap=snap)
        except Exception:
            continue
        if best is None or st > best_st:
            second_st = best_st
            best, best_st = b, st
        elif second_st is None or st > second_st:
            second_st = st
    if best_st is None:
        return (None, 0.0)
    return (best, best_st - (second_st if second_st is not None else 0.0))


def _concept_board_rank_top1(secs):
    # 概念板块（强度第一+领先幅度）入口（v0.36e）：文件已加载 -> 概念口径合并快照；
    # 未加载 -> 回退 API _board_rank_top1（兼容旧链/无文件环境）
    try:
        if not getattr(g, 'boards', None):
            return _board_rank_top1(secs)
    except Exception:
        return _board_rank_top1(secs)
    secs = [s for s in (secs or []) if s]
    if not secs:
        return (None, 0.0)
    boards = sorted({b for s in secs for b in _concept_boards_of(s) if b})
    if not boards:
        return (None, 0.0)
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('concept_top1', token), '_', _board_refresh_ttl(),
                      lambda: _compute_concept_board_top1_lead(boards), single=True)
        if isinstance(v, tuple) and len(v) == 2:
            return v
        return (v, 0.0)
    except Exception:
        return (None, 0.0)


def _board_5d_cache():
    # 板块5日强度续算账本（按交易日重置；plain dict，可随 g 持久化）
    if not getattr(g, 'board_5d', None):
        g.board_5d = {'day': '', 'data': {}}
    c = g.board_5d
    day = str(get_trading_day())
    if c.get('day') != day:
        c['day'] = day
        c['data'] = {}
    return c


def _calc_board_5d(board_code, rec):
    # 续算板块成员近5日收盘涨跌均值：每只成员 1 次 1d get_price（帧预算 day 内，耗尽即停；
    # rec 保留进度下帧续算；样本>=50% 才可信；v0.36e 成员走 _board_members_file）
    dh = _get_ds()
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(board_code, 20)) if x]
    except Exception:
        mem = []
    rec = dict(rec or {})
    total = len(mem)
    rec['total'] = total
    idx = int(rec.get('idx') or 0)
    ssum = float(rec.get('sum') or 0.0)
    cnt = int(rec.get('cnt') or 0)
    for i in range(idx, total):
        if not dh.spend('day'):
            break
        try:
            df = get_price(mem[i], start_date=None, end_date=None, count=6, frequency='1d')
            if df is not None and len(df) >= 6:
                closes = [float(df['close'].iloc[j]) for j in range(len(df))]
                chgs = [closes[j] / closes[j - 1] - 1.0 for j in range(1, 6) if closes[j - 1] > 0]
                if chgs:
                    ssum += sum(chgs) / len(chgs)
                    cnt += 1
        except Exception:
            pass
        idx = i + 1
    rec['idx'] = idx
    rec['sum'] = ssum
    rec['cnt'] = cnt
    rec['ratio'] = (cnt / total) if total else 1.0
    rec['avg'] = (ssum / cnt) * 100.0 if cnt else 0.0
    rec['finished'] = (total == 0) or (idx >= total)
    return rec


def _board_5d_strength(board_code):
    # 板块成员近5日收盘涨跌均值%；样本>=50% 才出值（否则下帧续算返回 None 不误判）
    try:
        c = _board_5d_cache()
        rec = c['data'].get(board_code)
        if rec is None or not (rec.get('finished') or rec.get('ratio', 0.0) >= 0.5):
            rec = _calc_board_5d(board_code, rec or {})
            c['data'][board_code] = rec
        if rec.get('finished') or rec.get('ratio', 0.0) >= 0.5:
            return rec.get('avg')
        return None
    except Exception:
        return None


def _new_top_board_scan():
    # v0.36c 当日「新最强板块」检测：候选范围（池+zt_lianban）所属板块中强度第一，
    # 需连续 elastic_top_stable_frames 帧保持第一 且 领先第二 >= elastic_top_lead_min，
    # 再通过「新爆发」因子（强度>=min_strength、T日开盘板块涨幅 显著强于 自身5日均值）。
    # 触发后持续跟踪（易主/10:00/买入 为止）；易主同样需连续 N 帧确认（防单帧抖动打断）。
    if not BLS.get('elastic_top_enabled', True):
        return None
    if _min_age() > int(BLS.get('elastic_top_window_minute', 30)):
        return None
    et = getattr(g, 'elastic_top', None) or {'day': '', 'top': '', 'ts': 0.0, 'tracked': set(), 'trig': 0, 'done': False}
    g.elastic_top = et
    day = str(get_trading_day())
    if et.get('day') != day:
        et.update(day=day, top='', ts=0.0, tracked=set(), trig=0, done=False)
        et.pop('stab', None)
    top, lead = _concept_board_rank_top1(_elastic_top_cand_src())   # v0.36e 概念口径（文件未加载回退 API）
    if not top:
        return None
    n_need = int(BLS.get('elastic_top_stable_frames', 3))
    lead_min = float(BLS.get('elastic_top_lead_min', 0.5))
    if top == et.get('top'):
        return None if et.get('done') else top          # 持续跟踪（买入后结束）
    stab = et.setdefault('stab', {'code': '', 'n': 0})
    if lead < lead_min:
        stab.update(code='', n=0)                       # 无明确最强 -> 稳定性计数清零
    elif stab.get('code') != top:
        stab.update(code=top, n=1)
    else:
        stab['n'] = stab.get('n', 0) + 1
    if stab['n'] < n_need:
        if et.get('top') and not et.get('done'):
            return et['top']                            # 易主未确认：旧板块跟踪不中断
        return None
    st = _concept_board_strength(top)   # v0.36e 概念板块强度（合并快照）
    if st < float(BLS.get('elastic_top_min_strength', 2.0)):
        return None
    open_g = _board_open_gain(top)
    avg5 = _board_5d_strength(top)
    if avg5 is None:
        return None                                     # 5日样本未够，下帧续算
    if open_g < float(BLS.get('elastic_top_breakout_min_open', 1.0)):
        return None                                     # 开盘板块涨幅自身下限
    if open_g < avg5 + float(BLS.get('elastic_top_breakout_min_boost', 2.0)):
        return None                                     # 未显著强于自身5日 -> 非新爆发
    if et.get('trig', 0) >= int(BLS.get('elastic_top_max_trigger_per_day', 2)):
        return None
    et['top'] = top; et['ts'] = time.time(); et['done'] = False
    if top in (et.get('tracked') or set()):
        return None
    et['tracked'].add(top); et['trig'] = et.get('trig', 0) + 1
    log.info('[elastic] new_top_board %s strength=%.1f%% open=%.1f%% avg5=%.1f%% lead=%.1f%% -> 启动弹性跟踪(最主动20cm,10%%前买)' % (
        top, st, open_g, avg5, lead))
    return top


def _calc_elastic_top_candidates(top):
    # 最强板块内 20cm 弹性标的（v0.36e 两段）：批量快照按涨幅粗排（过滤非20cm/已过 10%/不涨），
    # 只对前 elastic_top_surge_top_n 只算 1m surge（砍掉全成员串行拉取），按最主动（surge 降序）排序
    out = []
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(top, 30)) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        pre_rank = []
        for m in mem:
            if not _is_elastic_20cm(m):
                continue
            d = sn.get(m) or g.spot.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre <= 0 or px <= 0:
                continue
            chg = (px / pre - 1.0) * 100.0
            if chg <= 0 or chg >= float(BLS.get('elastic_top_buy_before_pct', 10.0)):
                continue
            pre_rank.append((chg, m))
        pre_rank.sort(key=lambda t: -t[0])
        for chg, m in pre_rank[:int(BLS.get('elastic_top_surge_top_n', 5))]:
            surge = _elastic_1m_surge(m)
            out.append((surge, chg, m))
    except Exception:
        return []
    out.sort(key=lambda t: (-t[0], -t[1]))
    return [m for _, _, m in out]


def _elastic_top_candidates(top):
    # 最强板块弹性候选排序缓存（elastic_top_cache_ttl=30s）
    try:
        dh = _get_ds()
        v = dh.cached(('elastic_top', str(top)), '_', float(BLS.get('elastic_top_cache_ttl', 30.0)),
                      lambda: _calc_elastic_top_candidates(top))
        return list(v) if v else []
    except Exception:
        return []


def _try_elastic_top_buy(context):
    # v0.36 新最强板块弹性套利：第一时间跟踪最主动弹性标的，10% 涨幅前买入
    if not BLS.get('elastic_top_enabled', True):
        return
    if _min_age() > int(BLS.get('elastic_top_window_minute', 30)):
        return                       # 10:00 前
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    top = _new_top_board_scan()
    if not top:
        return
    positions = context.portfolio.positions
    for sec in _elastic_top_candidates(top):
        if sec in positions:
            continue
        if sec in g.daily['bought']:
            continue                 # 当日已买（含其它策略）不再评估
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if not trade_open(sec):
            continue
        if _is_one_word_open(sec):
            continue                 # 不追一字
        if _block_sealed_buy(sec):
            continue                 # 封死不排队
        if _mid_board_avoid(sec):
            continue
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg <= 0 or chg >= float(BLS.get('elastic_top_buy_before_pct', 10.0)):
            continue                 # 10% 前买入
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > float(BLS.get('elastic_arb_max_open_change', 12.0)):
            continue                 # 防大幅高开兑现
        surge = _elastic_1m_surge(sec)
        if surge < float(BLS.get('elastic_top_min_1m_surge', 2.0)):
            continue                 # 最主动要求
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        place_order(context, sec, 'buy', note='elastic_top board=%s px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%%' % (
            top, px, limit or px, chg, surge), mode='chase')
        g.daily['bought'].append(sec); g.buy_log[sec] = now
        et = getattr(g, 'elastic_top', None)
        if et:
            et['done'] = True        # 本轮跟踪结束（易主/10:00/买入 三终止条件）
        _save_state()
        return                       # 只买最主动一只（一次一单）


def _realtime_weak(sec):
    # 云端实时走弱（廉价版，v0.33）：竞价绿开(auction_change<0) 或 破 VWAP。
    # 不调用 _eval_intraday/_two_1m_break（避免 tick 3s 帧吃 1m get_price 帧预算）；P4 仍用完整分时三态。
    try:
        if _auction_change(sec) < 0:
            return True
        if sec in g.spot and _below_vwap(sec):
            return True
        return False
    except Exception:
        return False


def _hold_arb_log(sec, msg):
    # 防冲突仲裁日志（60s/股节流，防刷屏）
    try:
        gl = getattr(g, 'hold_arb_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.hold_arb_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0) < 60.0:
            return
        gl[sec] = now
        log.info('[arb] %s %s' % (_sn(sec), msg))
    except Exception:
        pass


def _role_tolerance(sec):
    # 按预期 sell_policy_hint 缩放卖出容忍度（AXquant 地位角色迁移，docs/17）；缺省 none=一律基础。
    # v0.33 防冲突：云端实时已走弱（绿开/破VWAP/分时CS）时，文件的乐观容忍不得放大 P1 绿开/P3 止损
    # 硬信号阈值 -> 回落 1.0（实时硬信号优先）；评分类软阈值仍按文件角色缩放。
    en = g.exp_file.get(sec) or {}
    e = g.exp.get(sec) or {}
    hint = str(e.get('sell_policy_hint') or en.get('sell_policy_hint') or 'none')
    tbl = BLS.get('sell_policy', {})
    rp = tbl.get(hint) or tbl.get('none') or {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    if hint not in ('', 'none') and _realtime_weak(sec):
        # 仅回落「乐观放大」因子（>1.0）：实时走弱时文件宽容不得压住 P1/P3 硬信号。
        # 激进/保守因子（<=1.0，如 fast_exit_on_weak）保持 —— 本就该更敏感。
        _gt = float(rp.get('green_tol') or 1.0)
        _sa = float(rp.get('stop_adj') or 1.0)
        _n = _gt > 1.0 or _sa > 1.0
        if _n:
            _hold_arb_log(sec, '文件 sell_policy=%s 乐观容忍 vs 云端实时走弱 -> P1/P3 阈值回落基础(实时优先)' % hint)
            return {'green_tol': 1.0 if _gt > 1.0 else _gt, 'stop_adj': 1.0 if _sa > 1.0 else _sa,
                    'score_clear_adj': float(rp.get('score_clear_adj') or 1.0),
                    'score_half_adj': float(rp.get('score_half_adj') or 1.0)}
    return rp


# ================= 卖出（P1绿开>P3止损>P5/P6分数） =================
def _sellable_source():
    # 持仓量/成本来源：优先 get_positions()（规范键 .XSHG + amount/enable_amount/cost_basis, docs/06）；
    # 兜底 context.portfolio.positions（实盘原始键 .SS 且字段名随柜台而异）。
    try:
        p = get_positions() or {}
    except Exception:
        p = {}
    return p if isinstance(p, dict) and p else {}

def _sellable(sec, positions):
    # 可卖数量：优先 enable_amount 等可卖类字段（A股T+1，T日买入不可卖=0，不回落总量），
    # 缺可卖字段才回退持仓量 amount/current_amount；字段名随柜台而异(docs/06)，容忍 str/int/float。
    p = positions.get(sec)
    for key in ('enable_amount', 'available_amount', 'sellable_amount', 'closeable_amount',
                'real_enable_amount', 'current_amount', 'amount', 'hold_amount', 'holding_amount'):
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is None:
                continue
            return max(int(float(v) or 0), 0)   # 有可卖字段即采用(含0=当日不可卖), 不回落总量
        except Exception:
            continue
    if p is not None:
        _audit_pos_fields(sec, p)
    return 0

def _limit_down_price(sec):
    # 跌停地板价 = 前收 x (1 - 板块跌停幅)，供核卖限价保证下跌成交（无前收返回 None）
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return None
    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        ratio = float(BLS.get('limit_down_chinext', 0.20))
    elif num.startswith(('8', '4', '92')):
        ratio = float(BLS.get('limit_down_bse', 0.30))
    else:
        ratio = float(BLS.get('limit_down_main', 0.10))
    return max(pre * (1.0 - ratio), 0.0)


def _sell_inflight(sec):
    # 是否有未终态卖出挂单在途（订单/成交回报驱动，替代纯时间冷却）：有则本次不叠单
    p = (getattr(g, 'pending', None) or {}).get(sec) or {}
    if str(p.get('side') or '') != 'sell':
        return False
    st = str(p.get('status') or 'SENT').upper()
    if st in ('FILLED', 'CANCELLED', 'REJECTED'):
        return False
    ts = float(p.get('ts') or 0)
    if ts > 0 and (time.time() - ts) > float(BLS.get('sell_pending_timeout', 120.0)):
        return False   # 挂单超时无回报 -> 疑似丢失, 放行重试(对齐 AXquant order_lost 重投)
    return True


def _do_sell(context, sec, qty, note, urgent=False):
    # 统一卖出入口：sold_log 冷却 + 在途挂单守卫(_sell_inflight)；urgent(核卖)限价用跌停地板价保成交
    if qty <= 0:
        return
    if not isinstance(getattr(g, 'sold_log', None), dict):
        g.sold_log = {}
    g.sold_log[sec] = time.time()
    place_order(context, sec, 'sell', qty=qty, note=note, mode=('sell_urgent' if urgent else 'sell'))

def _audit_pos_fields(sec, p):
    # 一次性(1h节流)打印该持仓可用字段，定位实盘可卖数量真实字段名（不猜字段）
    try:
        gl = getattr(g, 'pos_field_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.pos_field_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0) < 3600.0:
            return
        gl[sec] = now
        if isinstance(p, dict):
            log.info('[pos-fields] %s %s keys=%s' % (_sn(sec), type(p).__name__, sorted(str(k) for k in p.keys())))
        else:
            log.info('[pos-fields] %s %s attrs=%s' % (_sn(sec), type(p).__name__, sorted(str(a) for a in dir(p) if not a.startswith('_'))[:40]))
    except Exception:
        pass

def _audit_sell_skip(sec, why, now=None):
    # 卖出被静默跳过的原因日志（60s 节流）, 定位实盘持仓为何不下单
    try:
        now = now or time.time()
        gs = getattr(g, 'last_skip_log', None)
        if not isinstance(gs, dict):
            gs = {}; g.last_skip_log = gs
        if now - float(gs.get(sec) or 0) < 60.0:
            return
        gs[sec] = now
        log.info('[sell-skip] %s %s (positions=%s)' % (_sn(sec), why, sorted(str(x) for x in (getattr(g, 'holdings_keys_hint', None) or []))))
    except Exception:
        pass

def sell_manager(context):
    positions = _sellable_source() or context.portfolio.positions
    sl = float(BLS.get('sell_cold_secs', 30.0))
    # 持仓键统一标准化(.XSHG)：实盘 portfolio.positions 原始键后缀可能异于 g.spot/g.exp/get_positions 的规范键,
    # 直接拿原始键查 spot 会 px=None 导致整个卖出链静默空转（本轮修复点）。
    g.holdings_keys_hint = sorted(str(x) for x in positions.keys())
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        px = last_px(sec); cost = my_cost(_raw, positions)
        if not px or px <= 0:
            _audit_sell_skip(sec, 'no_px(lookup key=%s)' % _raw)
            continue
        try:
            _hold_exp_init(sec)   # v0.32 持仓预期管理：确保条目存在（幂等）
        except Exception:
            pass
        amt = _sellable(_raw, positions)
        if amt <= 0:
            _audit_sell_skip(sec, 'amt0(lookup key=%s)' % _raw)
            continue
        now = time.time()
        if _sell_inflight(sec):            # 订单/成交回报驱动的去重：有未终态卖单在途则跳过(防叠单)
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (now - g.sold_log.get(sec, 0)) < sl:
            continue
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open drop=%.1f%%' % _auction_change(sec), urgent=True); continue
        # P2E 竞价核卖（v0.15 对齐 AXquant _sell_expectation_miss：预期已确认 miss/degraded -> 清仓）
        _e2 = g.exp_file.get(sec) or {}
        _est = str(_e2.get('expected_status') or '')
        _ma = ('confirmed_miss', 'degraded')
        if BLS.get('exp_sell_on_pending_miss', False):
            _ma = _ma + ('pending_miss',)
        if _est and _est in _ma:
            # v0.33 防冲突：文件悲观(miss/degraded) 但云端实时竞价超预期反证 -> 不核卖，转实时分时三态
            try:
                _rev, _ra = _confirm_expected(sec)
                if _rev == CX:
                    _hold_arb_log(sec, '文件预期=%s 悲观 vs 云端实时竞价超预期(CX) -> 不核卖' % _est)
                    continue
            except Exception:
                pass
            _do_sell(context, sec, amt, 'P2E_exp_miss ' + _est, urgent=True); continue
        if cost > 0:
            pnl_pct = px / cost - 1.0
            if pnl_pct <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss pnl=%.1f%%' % (pnl_pct * 100), urgent=True); continue
        # P4 预期三态：普通标的竞价/逆势，一字板封单，docs/17
        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word' and _is_one_word_open(sec):
                st, _r = _exp_one_word(sec)
                if st == CS or st == PS:
                    _do_sell(context, sec, amt, 'P4_exp_one_word ' + st); continue
            else:
                # v0.33 防冲突：文件标 one_word 但实时已开板 -> 回落普通分时三态（防封单误判/漏卖）
                if g.exp[sec].get('entry_type') == 'one_word' and not _is_one_word_open(sec):
                    _hold_arb_log(sec, '文件 entry_type=one_word 但实时已开板 -> 回落普通分时三态')
                au = g.exp[sec].get('auction_status') or _eval_auction(sec)[0]
                st = _eval_intraday(sec, au)[0]
                if st in (PS, CS):
                    _do_sell(context, sec, amt, 'P4_exp_miss ' + st); continue
        _en = g.exp_file.get(sec) or {}
        if str(_en.get('side') or '') == 'sell':
            _eun, _ea2 = _confirm_expected(sec)
            if _eun == CS:
                _do_sell(context, sec, amt, 'P4_exp_sell ' + _eun); continue
        sc = score_now(sec)
        if sc < BLS['score_sell_clear'] * rp['score_clear_adj']:
            _do_sell(context, sec, amt, 'P5_score_clear score=%.1f' % sc)
        elif sc < BLS['score_sell_half'] * rp['score_half_adj']:
            half = int(amt * float(BLS.get('sell_half_ratio', 0.5)))
            qty = int(half // 100) * 100
            if qty < 1:
                qty = amt if amt < 100 else 100
            if qty > amt:
                qty = amt
            _do_sell(context, sec, qty, 'P6_score_half score=%.1f' % sc)



def tick_sell_manager(context):
    # v0.26 tick \u7ea7\u5356\u51fa\uff083s \u5e27\u672b\uff0c\u4e8b\u4ef6\u9a71\u52a8\uff09\uff1a\u70b8\u677f/\u5c01\u5355\u5927\u51cf/\u6025\u5356 P1/P2E/P3 3s \u54cd\u5e94\uff1b
    # \u72b6\u6001\u6765\u81ea\u672c\u5e27 tick_data \u91c7\u96c6\uff08first_zt.break/seal_low\uff09\uff1b\u9996\u89e6\u53d1\u6807\u8bb0+\u5728\u9014\u9501+\u51b7\u5374\u53bb\u91cd\u9632\u91cd\u590d\u5356\uff1b
    # P4/P5/P6 \u4ecd\u7531 1m sell_manager \u8bc4\u4f30\uff08\u8bc4\u5206\u57fa\u4e8e 1m/1d \u6570\u636e\uff09\u3002
    if not BLS.get('tick_sell_enabled', True):
        return
    positions = _sellable_source() or context.portfolio.positions
    sl = float(BLS.get('sell_cold_secs', 30.0))
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        px = last_px(sec)
        if not px or px <= 0:
            continue
        amt = _sellable(_raw, positions)
        if amt <= 0:
            continue
        try:
            _hold_exp_init(sec)   # v0.32 持仓预期管理：确保条目存在（幂等）
        except Exception:
            pass
        now = time.time()
        if _sell_inflight(sec):
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (now - g.sold_log.get(sec, 0)) < sl:
            continue
        ft = g.first_zt.get(sec) or {}
        # \u70b8\u677f\u5356\u51fa\uff1a\u6da8\u505c\u9996\u89e6\u540e\u6389\u51fa\u6da8\u505c\u4ef7\uff08break \u9996\u89e6\u53d1 -> \u5356\uff0c\u73b0\u4ef7\u9650\u4ef7\u9632\u8fc7\u5ea6\u6740\u4ef7\uff09
        if BLS.get('break_sell_enabled', True) and ft.get('break'):
            if sec not in (getattr(g, 'break_sold', None) or set()):
                _do_sell(context, sec, amt, 'TICK_break_sell held=%.0fs' % (now - float(ft.get('break_ts') or now)))
                _mark_sold_event(sec, 'break')
                continue
        # \u5c01\u5355\u5927\u51cf\u5356\u51fa\uff1a\u5c01\u5355<=\u9996\u5c01*seal_fail_ratio \u6216\u59d4\u6258\u7b14\u6570\u8870\u7aed\uff08seal_low \u9996\u89e6\u53d1\uff0c\u9632\u70b8\u677f\u63d0\u524d\u8d70\uff09
        if BLS.get('seal_low_sell_enabled', True) and ft.get('seal_low'):
            if sec not in (getattr(g, 'seal_sold', None) or set()):
                _do_sell(context, sec, amt, 'TICK_seal_low_sell ratio<=%.2f' % float(BLS.get('seal_fail_ratio', 0.333)))
                _mark_sold_event(sec, 'seal')
                continue
        # \u6025\u5356\u8fc1\u79fb\uff1aP1 \u7eff\u5f00 / P2E \u9884\u671f miss / P3 \u6b62\u635f\uff083s \u54cd\u5e94\uff1b\u6838\u5356\u9650\u4ef7\u8dcc\u505c\u5730\u677f\u4ef7\u4fdd\u6210\u4ea4\uff09
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open_tick drop=%.1f%%' % _auction_change(sec), urgent=True); continue
        _e2 = g.exp_file.get(sec) or {}
        _est = str(_e2.get('expected_status') or '')
        _ma = ('confirmed_miss', 'degraded')
        if BLS.get('exp_sell_on_pending_miss', False):
            _ma = _ma + ('pending_miss',)
        if _est and _est in _ma:
            _do_sell(context, sec, amt, 'P2E_exp_miss_tick ' + _est, urgent=True); continue
        cost = my_cost(_raw, positions)
        if cost > 0:
            pnl = px / cost - 1.0
            if pnl <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss_tick pnl=%.1f%%' % (pnl * 100), urgent=True)


def _mark_sold_event(sec, kind):
    # \u4e8b\u4ef6\u5356\u51fa\u9996\u89e6\u53d1\u6807\u8bb0\uff08\u8de8\u91cd\u542f\u6301\u4e45\u5316\uff0c\u9632\u540c\u65e5\u91cd\u542f\u540e\u5bf9\u5df2\u70b8\u677f/\u5df2\u8870\u7aed\u6807\u7684\u91cd\u590d\u5356\uff09
    try:
        key = 'break_sold' if kind == 'break' else 'seal_sold'
        st = getattr(g, key, None)
        if not isinstance(st, set):
            st = set(); setattr(g, key, st)
        st.add(sec)
        _save_state()
    except Exception:
        pass

# ================= 定时回调（单参 func(context)） =================
def _l2_probe(context):
    # 盘中每日一次 L2 可用性探针：逐笔成交/委托 + 十档委托笔数（仅交易模块有真实 L2）
    if getattr(g, 'l2_probed', False):
        return
    try:
        secs = list(get_positions()) or (_pool() or [])[:1]
        if not secs:
            return
        sec = secs[0]
        tx = get_individual_transaction([sec], data_count=10, is_dict=True) or {}
        ent = get_individual_entrust([sec], data_count=10, is_dict=True) or {}
        n_tx = len(tx.get(sec) or []) if isinstance(tx, dict) else 0
        n_ent = len(ent.get(sec) or []) if isinstance(ent, dict) else 0
        gear = get_gear_price(sec) or {}
        bid_cnt = 0
        try:
            grp = gear.get('bid_grp') if isinstance(gear, dict) else {}
            if isinstance(grp, dict):
                for row in grp.values():
                    if isinstance(row, (list, tuple)) and len(row) >= 3:
                        bid_cnt = int(row[2] or 0)
                        break
        except Exception:
            bid_cnt = 0
        if isinstance(tx, dict) and tx.get(sec):
            log.info('[l2] %s tx_row=%s' % (_sn(sec), tx[sec][-1]))
        if isinstance(tx, dict) and tx.get('fields'):
            log.info('[l2] %s tx_fields=%s' % (_sn(sec), list(tx['fields'])))
        ok = 'L2_OK' if (n_tx or n_ent or bid_cnt) else 'L2_NONE'
        log.info('[l2] code=%s tx=%d entrust=%d gear_bid_cnt=%d -> %s' % (_sn(sec), n_tx, n_ent, bid_cnt, ok))
        # v0.26b 验证：总买/总卖量（get_snapshot 标准字段，单位手）+ 委差/委比 + L2 首档委托队列（下一交易日验证）
        try:
            _s1 = get_snapshot([sec]) or {}
            _s1 = (_s1.get(sec) or {}) if isinstance(_s1, dict) else {}
            _b1 = (_s1.get('bid_grp') or {}).get(1) or []
            _l2q = bool(isinstance(_b1, (list, tuple)) and len(_b1) >= 4 and _b1[3])
            log.info('[l2] %s snap total_bidqty=%s total_offerqty=%s entrust_diff=%s entrust_rate=%s bid1_queue_l2=%s' % (
                _sn(sec), _s1.get('total_bidqty'), _s1.get('total_offerqty'),
                _s1.get('entrust_diff'), _s1.get('entrust_rate'), _l2q))
            _bs = 0.0; _as = 0.0
            for _r in (gear.get('bid_grp') or {}).values():
                if isinstance(_r, (list, tuple)) and len(_r) >= 2:
                    _bs += float(_r[1] or 0)
            for _r in (gear.get('offer_grp') or {}).values():
                if isinstance(_r, (list, tuple)) and len(_r) >= 2:
                    _as += float(_r[1] or 0)
            log.info('[l2] %s gear bid_sum=%s offer_sum=%s' % (_sn(sec), _bs, _as))
        except Exception as _e:
            _warn('l2 totals probe fail %r' % _e)
        g.l2_probed = True
    except Exception as e:
        _warn('l2 probe fail: %r' % e)

def _tick_targets():
    # tick 采集目标：持仓 + universe 恒有 + watch 前 N（控 3s 帧负担，避免丢帧）
    # v0.36 帧缓存：同一 3s 帧内多消费（snapshot/gear 限额动态化）复用，避免重复 get_positions
    tok = int(time.time() / 3.0)
    _c = getattr(g, 'tick_targets_cache', None) or {}
    if _c.get('tok') == tok:
        return _c['secs']
    pos = list(get_positions())
    uni = [x for x in BLS['universe'] if x not in pos]
    static = [x for x in (g.pool_static or []) if x not in pos and x not in uni]
    cap = int(BLS.get('tick_watch_cap', 15))
    watch = [x for x in (g.watch or []) if x not in pos and x not in uni and x not in static][:cap]
    out = pos + uni + static + watch
    if BLS.get('tick_board_scan', True):   # v0.47 B1: 强度前三板块成员并入（首板目标直连）
        try:
            top3 = _board_rank_top3_set(_pool() or out)
            if top3:
                _cap_m = int(BLS.get('tick_board_member_cap', 20))
                for _b in top3:
                    for _m in _board_members_file(_b, _cap_m):
                        if _m and _m not in out and _m not in pos:
                            out.append(_m)
        except Exception:
            pass
    try:
        g.tick_targets_cache = {'tok': tok, 'secs': out}
    except Exception:
        pass
    return out


def _snap_vol(s):
    for k in ('business_amount', 'volume', 'trd_volume', 'amount'):
        v = s.get(k)
        if v:
            try:
                return float(v)
            except Exception:
                return 0.0
    return 0.0


def _parse_tx_zt_ms(sec, rows, fields):
    # 逐笔成交解析：最早一笔"成交价>=涨停价 且 09:30 后"的毫秒时间戳（单一解析点，批量/单标共用）；
    # 字段按 fields 映射，缺省按位序兜底（business_time, hq_px, ...）
    if not rows or not isinstance(rows, list):
        return None
    def _idx(name, default):
        return fields.index(name) if name in fields else default
    i_t = _idx('business_time', 0); i_p = _idx('hq_px', 1)
    u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
    if u <= 0:
        return None
    lt = time.localtime()
    day_open = int('%04d%02d%02d093000000' % (lt.tm_year, lt.tm_mon, lt.tm_mday))
    best = None
    for row in rows:
        try:
            ms = int(row[i_t]); px = float(row[i_p])
            if ms < day_open or px < u - 1e-9:
                continue
            if best is None or ms < best:
                best = ms
        except Exception:
            continue
    return best


def _tx_big_feed(secs, fields, raw):
    # v0.47 L2 大单累计：逐笔 business_amount 按 trade_index 去重（防跨帧重复），累计当日大单金额
    if not BLS.get('l2_big_enabled', True) or not raw:
        return
    try:
        min_amt = float(BLS.get('l2_big_amt_min', 1000000.0))
    except Exception:
        return
    if min_amt <= 0:
        return
    def _idx(name, default):
        return fields.index(name) if name in fields else default
    i_a = _idx('business_amount', -1); i_t = _idx('trade_index', -1)
    if i_a < 0:
        return
    acc = getattr(g, 'l2_big', None)
    if acc is None:
        acc = {}; g.l2_big = acc
    probed = getattr(g, 'l2_big_probed', None)
    if probed is None:
        probed = set(); g.l2_big_probed = probed
    _cap = int(BLS.get('l2_big_seen_cap', 20000))
    for sec in secs:
        rows = raw.get(sec) or []
        if not rows:
            continue
        a = acc.setdefault(sec, {'amt': 0.0, 'seen': set()})
        seen = a['seen']
        if len(seen) >= _cap:
            continue
        for row in rows:
            try:
                if i_t >= 0:
                    ti = row[i_t]
                    if ti in seen:
                        continue
                    seen.add(ti)
                va = float(row[i_a])
                if va >= min_amt:
                    a['amt'] += va
            except Exception:
                continue
        if sec not in probed:
            probed.add(sec)
            r = _l2_big_ratio(sec)
            log.info('[l2-big] %s 累计大单=%.0f 占比=%.2f%% (阈值=%.0f)' % (
                _sn(sec), a['amt'], r * 100.0 if r >= 0 else -1.0, min_amt))


def _l2_big_ratio(sec):
    # v0.47 L2 大单占比 = Σ大单金额/当日成交额（快照 turnover/amount 元）；无数据/单位异常 -> -1
    try:
        acc = (getattr(g, 'l2_big', None) or {}).get(sec)
        if not acc or not acc.get('amt'):
            return -1.0
        s = g.spot.get(sec) or {}
        to = float(s.get('turnover') or s.get('amount') or 0.0)
        if to <= 0:
            return -1.0
        r = acc['amt'] / to
        if r > 1.0:
            return -1.0        # 单位异常保护（大单额>总成交额 -> 不授分）
        return r
    except Exception:
        return -1.0


def _l2_big_ok(sec):
    # v0.47 大单加持：占比 >= l2_big_ratio_min
    try:
        return _l2_big_ratio(sec) >= float(BLS.get('l2_big_ratio_min', 0.10))
    except Exception:
        return False


def _l2_big_bonus_pts(sec):
    # v0.47 大单占比达标加分（score_now 统一加成）
    try:
        return float(BLS.get('l2_big_bonus', 5.0)) if _l2_big_ok(sec) else 0.0
    except Exception:
        return 0.0


def _tx_first_zt_ms(sec):
    # 单标逐笔拉取（兼容入口；v0.22 起 tick 主路径走 DataHub.tx_zt_batch 批量）
    try:
        dh = _get_ds()
        return dh.tx_zt_batch([sec], {}).get(sec)
    except Exception:
        return None


def _tx_frame_zt_ms(sec, frame_data):
    # 帧内推送逐笔（tick_data 的 data[sec]['transaction']，0 额外 API 调用）：该帧最近一条逐笔成交
    # 若成交价>=涨停价返回其 business_time(毫秒)，否则 None；无 L2 字段/异常 -> None（由拉取兜底）
    try:
        t = (frame_data or {}).get(sec) or {}
        tx = t.get('transaction') if isinstance(t, dict) else None
        if tx is None:
            return None
        if hasattr(tx, 'iloc'):            # DataFrame/Series 形态（沙盒 data）
            row = tx.iloc[-1]
            ms = row.get('business_time'); px = row.get('hq_px')
        elif isinstance(tx, dict):
            ms = tx.get('business_time'); px = tx.get('hq_px')
        else:
            return None
        u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
        if not u or u <= 0 or not ms:
            return None
        try:
            px = float(px)
        except Exception:
            return None
        if px >= u - 1e-9:
            return int(ms)
        return None
    except Exception:
        return None


def tick_data(context, data):
    # 仅交易，9:30-14:59 每 3s 一次。L2 涨停首笔成交感知 + 封单/破板节奏。
    # 只采集状态与 [firstzt] 日志，下单仍走 1m handle_data（采集/决策解耦）。
    if not BLS.get('tick_enabled', True):
        return
    _secs = _tick_targets()
    _dh = _get_ds()
    try:
        _dh.snapshot(_secs)                     # 帧首批量快照（一次 get_snapshot(列表)）
    except Exception:
        pass
    # v0.22 近涨停候选批量逐笔（统一入口）：先帧推送，缺者一次 get_individual_transaction(列表)
    _tx_map = {}
    if BLS.get('firsttx_enabled', True):
        _near = []
        _near_px = float(BLS.get('firsttx_near_px', 0.98))
        for _sec in _secs:
            _s0 = g.spot.get(_sec) or {}
            _l0 = float(_s0.get('last_px') or 0.0); _u0 = float(_s0.get('up_px') or 0.0)
            if (_l0 > 0 and _u0 > 0 and _l0 >= _u0 * _near_px
                    and not _is_one_word_open(_sec) and g.first_zt.get(_sec) is None):
                _near.append(_sec)
        if _near:
            try:
                _tx_map = _dh.tx_zt_batch(_near, data)
            except Exception:
                _tx_map = {}
    for sec in _secs:
        try:
            s = g.spot.get(sec) or {}
            g.spot[sec] = s                     # 顺带刷新 1m 打分用的快照
            last = float(s.get('last_px') or 0.0)
            u = float(s.get('up_px') or 0.0)
            if last <= 0 or u <= 0:
                continue
            seal, bids = _seal_metrics(sec)
            ft = g.first_zt.get(sec)
            if ft is None:
                vol = _snap_vol(s)
                amt = float(s.get('turnover') or s.get('amount') or 0.0)
                ms = s.get('hsTimeStamp') or 0   # 快照毫秒时间戳，精确还原触板时刻
                # v0.20/v0.22 L2 逐笔首笔成交感知（优先，灵敏度<=3s）：涨停价逐笔成交即确认首触；
                # _tx_map 已按近涨停候选批量取好（帧推送优先 + 批量拉取兜底），此处直接读
                tx_ms = _tx_map.get(sec) if BLS.get('firsttx_enabled', True) else None
                if tx_ms is not None:
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': tx_ms, 'break': False, 'seal_low': False, 'src': 'tx'}
                    log.info('[firstzt] %s price=%.2f tx_ms=%s vol=%.0f seal=%.0f bids=%d state=first(src=tx)' % (_sn(sec), last, tx_ms, vol, seal, bids))
                    try:
                        _try_first_board_buy(context, sec, rank_secs=_near)
                    except Exception as _e:
                        _warn('first_board_buy fail %r' % _e)
                    continue
                if (last >= u - 1e-9 and seal >= float(BLS.get('firstzt_min_seal', 0.0))
                        and bids >= int(BLS.get('firstzt_min_bids', 0))):   # 快照兜底：首此涨停上报最小封单/挂单门槛,过滤假封            # 首次触板
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False, 'src': 'snap'}
                    log.info('[firstzt] %s price=%.2f vol=%.0f ms=%s seal=%.0f bids=%d state=first(src=snap)' % (_sn(sec), last, vol, ms, seal, bids))
                    # v0.18 首板确认->打板：开盘10分钟内+非一字板+板块内涨幅最高+主动最快拉升+强度前三
                    try:
                        _try_first_board_buy(context, sec, rank_secs=_near)
                    except Exception as _e:
                        _warn('first_board_buy fail %r' % _e)
                continue
            if last < u - 1e-9:                 # 破板
                if not ft.get('break'):
                    ft['break'] = True; ft['break_ts'] = time.time()
                    log.info('[firstzt] %s price=%.2f -> BREAK seal=%.0f held=%.0fs' % (_sn(sec), last, seal, time.time() - ft.get('ts', time.time())))
                continue
            fs = ft.get('first_seal') or 0.0    # 封单衰竭（相对首封）
            if fs > 0 and seal < fs * float(BLS.get('seal_fail_ratio', 0.333)):
                if not ft.get('seal_low'):
                    ft['seal_low'] = True
                    log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW' % (_sn(sec), seal, fs, seal / fs, bids))
        except Exception:
            continue
    # v0.26 tick 级卖出：3s 帧末（炸板/封单大减/急卖；first_zt 状态已在本帧采集）
    try:
        tick_sell_manager(context)
    except Exception as e:
        _warn('tick sell fail: %r' % e)

    # v0.13：3s 帧末统一评估预期买入（竞价超预期/快速上攻/封单超预期 -> 立买；走弱 -> 放弃）
    if BLS.get('tick_exp_enabled', True):
        try:
            _try_expected_buys(context)
        except Exception as e:
            _warn('tick exp buy fail: %r' % e)
    # v0.19 弹性套利：3s 帧末评估（09:30-09:40，板块一字>=2 抓 20cm）
    try:
        _try_elastic_arb_buy(context)
    except Exception as e:
        _warn('elastic_arb buy fail: %r' % e)
    # v0.36 新最强板块弹性套利：第一时间跟踪（最主动弹性标的，10% 前买入）
    try:
        _try_elastic_top_buy(context)
    except Exception as e:
        _warn('elastic_top buy fail: %r' % e)
    # v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（P2）
    try:
        _try_dyn_unq(context)
    except Exception as e:
        _warn('dyn_unq fail: %r' % e)
    # v0.25 Phase 3：帧末拉取预算统计
    if BLS.get('budget_log_enabled', True):
        try:
            log.info('[budget] %s' % _dh.frame_report())
        except Exception:
            pass


def auction_pre_confirm(context):
    # 09:25 竞价终态：重读 9:20 定时上传的预期前瞻文件，对 side=buy 做「竞价超预期初步确认 -> 观察」节奏。
    # 时机说明：before_trading_start(~9:10) 早于上传点，须在此重读当日文件才命中；观察不买，等分时(9:30+)确认。
    _set_now(context)
    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) != day:
        g.exp_day = day
    _load_expectation()          # 幂等重读：命中 9:20 上传的当日文件
    _load_zt_lianban()
    _load_boards()               # v0.36d 板块映射文件 09:25 重读（命中 9:20 上传）
    _synth_pool_expect()         # v0.27：涨停池竞价三态初步确认（超预期->观察）
    _dyn_unq_auction_eval()      # v0.38 竞价唯一预判（同身位竞品不及预期 -> 扫板前提，0 盘中 RPC）
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect()    # v0.35e：自选股竞价三态（超预期->观察）
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))  # v0.36 覆盖兜底
    _sync_pool_static()
    _mark_one_word_open()
    for code in list(get_positions()):
        g.exp.setdefault(code, {})
        g.exp[code]['auction_status'] = _eval_auction(code)[0]
    for code in (g.exp_file or {}):
        if str((g.exp_file[code] or {}).get('side') or '') != 'buy':
            continue
        try:
            st, reason = _exp_rt_status(code)
        except Exception as e:
            _warn('auction_pre_confirm %s fail %r' % (_sn(code), e)); continue
        g.exp[code]['status'] = st
        if st == PM and str(reason).startswith('observe'):
            eo = g.exp.setdefault(code, {})
            if not eo.get('observe_seen'):
                eo['observe_seen'] = True
                log.info('[exp] %s 09:25竞价终态初步确认超预期 -> 观察(等分时确认) %s' % (_sn(code), reason))
        elif st == CS and str(reason).startswith('auction_not_met'):
            log.info('[exp] %s 09:25竞价终态未超预期 -> 放弃 %s' % (_sn(code), reason))
    log.info('auction_pre_confirm 09:25 done exp_file=%d' % len(g.exp_file))

def after_open_probe(context):
    _set_now(context)
    log.info('after_open_probe 09:31')
    # 兜底重读：9:20 上传若稍晚到，09:31 再读一次（幂等）
    _load_expectation()
    _synth_pool_expect()         # v0.27：涨停池三态（09:31 兜底重合成，覆盖重读清空）
    _dyn_unq_auction_eval()      # v0.38 竞价唯一预判（09:31 兜底重算）
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect()    # v0.35e：自选股三态（09:31 兜底重合成）
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))  # v0.36 覆盖兜底
    _sync_pool_static()
    g.exp_day = str(get_trading_day()); g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.sealed_since = {}; g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set()
    _mark_one_word_open()
    for sec in list(get_positions()):
        g.exp.setdefault(sec, {})
        au, _r = _eval_auction(sec)
        g.exp[sec]['auction_status'] = au
        _en = g.exp_file.get(sec) or {}
        for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct', 'seal_amount_t0', 'sell_policy_hint'):
            if _en.get(_k) is not None:
                g.exp[sec][_k] = _en[_k]
    dump_scores(context)
    _l2_probe(context)  # L2 可用性探针（每日一次）


def mid_probe(context):
    _set_now(context)
    log.info('mid_probe 11:00')
    dump_scores(context)
    sell_manager(context)


# ================= 下单与订单闭环 =================
def _round_price(x):
    # 限价单价格取整到标的精度（A股 2 位小数；docs/00 要求）
    try:
        return float(round(float(x), int(BLS.get('price_precision', 2))))
    except Exception:
        return float(x)


def _order_limit(sec, side, mode):
    # 下单限价策略：板(涨停价) / 追高(现价上浮后封顶涨停价) / 回踩(现价) / 卖出(现价限价防急跌垃圾价)
    s = g.spot.get(sec) or {}
    px = last_px(sec)
    up = float(s.get('up_px') or 0.0) if s else 0.0
    if not px or px <= 0:
        return None
    if side == 'sell':
        if mode == 'sell_urgent' and BLS.get('sell_urgent_floor', 1):
            floor = _limit_down_price(sec)
            if floor and floor > 0:
                return _round_price(floor)
        return _round_price(px)
    if mode == 'board':
        if _sealed_at_limit(sec):
            return None                                   # 一字/封死涨停：挂单只能排队，不参考排单 -> 不买
        return _round_price(up if up and up > 0 else px)   # 打板：挂涨停价排队
    if mode == 'pullback':
        return _round_price(px)                             # 回踩：现价限价
    p = px * (1 + float(BLS.get('buy_chase_pct', 0.008)))   # 追高：现价上浮后封顶涨停价
    if up and up > 0 and p > up:
        p = up
    cap = _max_elastic_buy_price(sec)                       # 300/688 弹性追高：前收*1.10 上限（打板豁免在本模式外）
    if cap and cap > 0 and p > cap:
        p = cap
    return _round_price(p)


def _total_asset(context):
    # 总资产：优先 portfolio.total_value；缺失回退 cash+持仓市值(amount×last_px)；再无=0
    po = getattr(context, 'portfolio', None)
    if po is None:
        return 0.0
    try:
        t = getattr(po, 'total_value', 0) or 0
        if t:
            return float(t)
    except Exception:
        pass
    try:
        c = float(getattr(po, 'cash', 0) or 0)
    except Exception:
        c = 0.0
    try:
        mv = 0.0
        for p in (getattr(po, 'positions', None) or {}).values():
            amt = float(getattr(p, 'amount', 0) or 0)
            px = float(getattr(p, 'last_price', 0) or 0)
            mv += amt * px
        return c + mv
    except Exception:
        return c


def _calc_buy_qty(context, sec, price, ratio):
    # 买入量(100股整手)：期望金额=min(现金×比例, 单支上限, 现金)；单支上限=总资产×single_stock_cap-已持市值
    # AXquant _calc_buy_volume：期望金额=min(总资产×比, 现金, 仓位余量, 单支上限)；本实现替代硬编码 0.3
    if price is None or price <= 0:
        return 0
    try:
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
    except Exception:
        return 0
    if cash <= 0:
        return 0
    total = _total_asset(context) or cash
    p = (getattr(context.portfolio, 'positions', None) or {}).get(sec)
    held_mv = 0.0
    if p is not None:
        try:
            held_mv = float(getattr(p, 'amount', 0) or 0) * price
        except Exception:
            held_mv = 0.0
    cap = total * float(BLS.get('single_stock_cap', 0.30)) - held_mv
    if cap <= 0:
        return 0
    try:
        budget = min(cash * float(ratio), cap, cash)
    except Exception:
        return 0
    if budget <= 0:
        return 0
    lot = price * 100
    if lot <= 0:
        return 0
    return int(budget / lot) * 100


def _rt_lag_info(sec):
    # v0.43 灵敏度：检测参考(first_zt 首触/涨停首笔) -> 当前下单时延；返回 ('lag=..s det=src:ms', lag值或None)
    try:
        now = time.time()
        ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
        t = ft.get('ts')
        if not t:
            return '', None
        lag = max(now - float(t), 0.0)
        src = ft.get('src') or '-'
        ms = ft.get('ms') or '-'
        return ('lag=%.1fs det=%s:%s' % (lag, src, ms), lag)
    except Exception:
        return '', None


def _acc_rt(side, mode, lag):
    # v0.43 灵敏度日结采样（after_trading_end 汇总打 [rt-summary]）
    try:
        st = getattr(g, 'rt_stats', None)
        if not isinstance(st, dict):
            st = {}; g.rt_stats = st
        key = (str(side), str(mode))
        d = st.setdefault(key, {'n': 0, 'lag': 0.0, 'max': 0.0})
        d['n'] += 1; d['lag'] += lag; d['max'] = max(d['max'], lag)
    except Exception:
        pass


def _signal(sec, side, qty, limit, mode, note='', ent='', status=''):
    # v0.36i 统一买卖信号结构化行（供 log_collector 按日入库与信号->回报对账）；纯日志，PT 沙盒安全
    try:
        sc = 0.0
        try:
            sc = float(score_now(sec) or 0.0)
        except Exception:
            sc = 0.0
        _lag, _lv = _rt_lag_info(sec)
        if _lv is not None:
            _acc_rt(side, mode, _lv)   # v0.43 灵敏度采样
        log.info('[signal] %s side=%s qty=%s limit=%s mode=%s note=%s score=%.1f ent=%s status=%s %s' % (
            _sn(sec), side, qty, limit, mode, note, sc, ent, status, _lag))
    except Exception:
        pass


def place_order(context, sec, side, qty=None, note='', mode='chase', ratio=None):
    positions = context.portfolio.positions
    _lag, _lv = _rt_lag_info(sec)   # v0.43 灵敏度（检测->下单时延）
    if side == 'buy':
        if _mid_board_avoid(sec):   # v0.34 连板中位股统一兜底闸（覆盖弹性套利等入口，幂等）
            log.info('[mid-avoid] %s 连板中位股规避(order)' % _sn(sec)); return
        limit = _order_limit(sec, side, mode)
        px = limit or last_px(sec) or 0.0
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
        if px <= 0 or cash <= 0:
            _warn('place_order skip(no px/cash) %s' % _sn(sec)); return
        qty = _calc_buy_qty(context, sec, px, float(ratio) if ratio else float(BLS.get('ordinary_buy_ratio', 0.10)))
        if qty <= 0:
            _warn('place_order skip(qty<=0) %s' % _sn(sec)); return
        if not _buy_pos_ok(context, sec, qty, limit):
            return   # v0.30 情绪总仓位上限（冰点40%/回暖80%，连续回暖递减）
    else:
        limit = _order_limit(sec, side, mode)
        if qty is None:
            qty = int(getattr(positions.get(sec), 'amount', 0) or 0)
    if not qty or qty <= 0:
        _warn('place_order skip qty<=0 %s' % _sn(sec)); return
    if not BLS['DO_ORDER']:
        log.info('[may-order] %s %s qty=%s limit=%s %s %s (DO_ORDER=False)' % (_sn(sec), side, qty, limit, note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent='', status='SIM')
        return
    try:
        ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
        g.pending[sec] = {'no': ent, 'side': side, 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0, 'ts': time.time()}
        log.info('order sent %s %s qty=%s limit=%s ent=%s %s %s' % (_sn(sec), side, qty, limit, ent, note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent=ent, status='SENT')
    except Exception as e:
        log.error('order fail %s: %r' % (_sn(sec), e))


def place_expected_order(context, sec, note=''):
    _lag, _lv = _rt_lag_info(sec)   # v0.43 灵敏度（检测->下单时延）
    # 预期买入独立下单门控（EXPECT_ORDER）：仅此路径可在 DO_ORDER=False 时发真实单（模拟盘小额测试）
    if _mid_board_avoid(sec):   # v0.34 连板中位股统一兜底闸
        log.info('[mid-avoid] %s 连板中位股规避(exp-order)' % _sn(sec)); return False
    s = g.spot.get(sec) or {}
    px = last_px(sec) or 0.0
    up = float(s.get('up_px') or 0.0) if s else 0.0
    cash = float(getattr(context.portfolio, 'cash', 0) or 0)
    if px <= 0 or cash <= 0:
        _warn('exp order skip(no px/cash) %s' % _sn(sec))
        return False
    if _block_sealed_buy(sec):
        return False   # 一字/封死涨停：不排队买入（v0.15 对齐 AXquant limit_up_sealed_no_queue）
    # 定价：冲板/一字 -> 打板(涨停价排队)；两分钟上攻(非涨停) -> 追高(现价上浮封顶涨停价)
    mode = 'board' if (up and px and px >= up * 0.998) else 'chase'
    limit = _order_limit(sec, 'buy', mode)
    p_for_size = limit or px
    ratio = float(BLS.get('board_buy_budget_ratio', BLS.get('exp_order_pct', 0.3))) if mode == 'board' else float(BLS.get('exp_order_pct', 0.3))
    qty = _calc_buy_qty(context, sec, p_for_size, ratio)
    if qty <= 0:
        _warn('exp order skip(qty<=0) %s' % _sn(sec))
        return False
    if not _buy_pos_ok(context, sec, qty, limit):
        return False   # v0.30 情绪总仓位上限
    if BLS.get('EXPECT_ORDER', False):
        try:
            ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
            g.pending[sec] = {'no': ent, 'side': 'buy', 'qty': qty, 'limit': limit}
            log.info('[exp-order] %s buy qty=%s limit=%s ent=%s %s %s (EXPECT_ORDER=True)' % (_sn(sec), qty, limit, ent, note, _lag))
            _signal(sec, 'BUY', qty, limit, mode, note, ent=ent, status='SENT')
            return True
        except Exception as e:
            log.error('exp order fail %s: %r' % (_sn(sec), e))
            return False
    log.info('[exp-order] %s buy qty=%s limit=%s %s %s (EXPECT_ORDER=False)' % (_sn(sec), qty, limit, note, _lag))
    _signal(sec, 'BUY', qty, limit, mode, note, ent='', status='SIM')
    return True


def on_order_response(context, order):
    # 订单回报：回填 pending 状态；拒绝/撤单即释放在途锁, 允许下帧重试
    try:
        ent = getattr(order, 'entrust_no', None) or getattr(order, 'order_id', None)
        st = getattr(order, 'order_status', None) or getattr(order, 'status', None) or 'SENT'
        _sec_m = None; _p = {}
        if ent is not None:
            for _sec, _pp in (getattr(g, 'pending', None) or {}).items():
                if str(_pp.get('no') or '') == str(ent):
                    _sec_m = _sec; _p = _pp
                    _pp['status'] = str(st)
                    if str(st).upper() in ('FILLED', 'CANCELLED', 'REJECTED'):
                        _pp['filled'] = int(_pp.get('qty') or 0)   # 终态不再在途
                    break
        log.info('on_order_response %s status=%s' % (ent, st))
        _signal(_sec_m, 'ORD', int(_p.get('qty') or 0), float(_p.get('limit') or 0.0), 'ord', 'order_response', ent=ent, status=str(st))
    except Exception as e:
        _warn('on_order_response err %r' % e)


def on_trade_response(context, trade):
    # 成交回报：回填 pending 已成交量、按成交释放去重并记 daily.sold（成交驱动的持仓对账）
    try:
        code = (getattr(trade, 'ticker', None) or getattr(trade, 'code', None)
                or getattr(trade, 'sec', None) or getattr(trade, 'stock_code', None)
                or getattr(trade, 'symbol', None))
        code = _norm_sec(code)
        if code:
            try:
                _hold_exp_init(code)   # v0.32 持仓预期管理：成交即建立条目（幂等）
            except Exception:
                pass
        qty = getattr(trade, 'quantity', None) or getattr(trade, 'volume', None) or getattr(trade, 'amount', None) or 0
        side = getattr(trade, 'side', None) or getattr(trade, 'entrust_bs', None) or getattr(trade, 'business_bs', None)
        p = (getattr(g, 'pending', None) or {}).get(code) or {}
        if str(p.get('side') or '') == 'sell':
            p['filled'] = int(p.get('filled') or 0) + int(qty or 0)
            p['last_trade_ts'] = time.time()
            if p['filled'] >= int(p.get('qty') or p['filled']):
                p['status'] = 'FILLED'
            else:
                p['status'] = 'PARTIAL'
            if not isinstance(getattr(g, 'sold_log', None), dict):
                g.sold_log = {}
            g.sold_log[code] = time.time()
            daily = g.daily.setdefault('sold', [])
            if code not in daily:
                daily.append(code)
            _save_state()
        log.info('on_trade_response %s qty=%s side=%s' % (_sn(code), qty, side))
        _signal(code, side, qty, 0, 'fill', 'trade_response', ent='', status=str(p.get('status') or 'TRADE'))
    except Exception as e:
        _warn('on_trade_response err %r' % e)


# ================= 持久化（无 os 依赖） =================
def state_fp():
    return get_research_path() + 'buysell_core_state.pkl'


def load_state():
    try:
        with open(state_fp(), 'rb') as f:
            st = pickle.load(f)
        g.buy_log = st.get('buy_log', {}); g.sold_log = st.get('sold_log', {})
        g.daily = st.get('daily', {'bought': [], 'sold': []})
        g.exp_fired = set(st.get('exp_fired') or [])
        g.state_day = st.get('day')
        if st.get('day') == str(get_trading_day()):
            g.auction_c = dict(st.get('auction_c') or {})
            g.first_zt = dict(st.get('first_zt') or {})
            g.break_sold = set(st.get('break_sold') or [])
            g.seal_sold = set(st.get('seal_sold') or [])
            g.dyn_unq = st.get('dyn_unq')
        else:
            g.auction_c = getattr(g, 'auction_c', None) or {}
            g.first_zt = getattr(g, 'first_zt', None) or {}
            g.break_sold = set()
            g.seal_sold = set()
            g.dyn_unq = None
    except Exception:
        g.buy_log = {}; g.sold_log = {}
        g.daily = {'bought': [], 'sold': []}; g.state_day = None
        g.exp_fired = set()


def _save_state():
    # 写入 buy_log/sold_log（冷却）+ daily 每日计数 + day 戳（跨重启恢复）
    try:
        if not getattr(g, 'state_day', None):
            g.state_day = str(get_trading_day())
        _today = getattr(g, 'state_day', None) or str(get_trading_day())
        with open(state_fp(), 'wb') as f:
            pickle.dump({'buy_log': g.buy_log, 'sold_log': g.sold_log,
                         'daily': g.daily, 'day': _today,
                         'exp_fired': sorted(getattr(g, 'exp_fired', None) or []),
                         'auction_c': dict(getattr(g, 'auction_c', None) or {}),
                         'ac_day': _today,
                         'first_zt': dict(getattr(g, 'first_zt', None) or {}),
                         'first_zt_day': _today,
                         'break_sold': sorted(getattr(g, 'break_sold', None) or []),
                         'seal_sold': sorted(getattr(g, 'seal_sold', None) or []),
                         'dyn_unq': dict(getattr(g, 'dyn_unq', None) or {})}, f, protocol=2)
    except Exception as e:
        _warn('save_state fail %r' % e)


def after_trading_end(context, data):
    _save_state()
    # v0.43 灵敏度日结：检测->下单时延按 (side, mode) 汇总
    try:
        _st = getattr(g, 'rt_stats', None)
        if isinstance(_st, dict) and _st:
            for (_side, _mode), _d in sorted(_st.items()):
                if _d.get('n'):
                    log.info('[rt-summary] side=%s mode=%s n=%d avg=%.1fs max=%.1fs' % (_side, _mode, _d['n'], _d['lag'] / _d['n'], _d['max']))
            g.rt_stats = {}
    except Exception:
        pass
    log.info('buysell_core end bought=%s sold=%s' % (_snl(g.daily.get('bought')), _snl(g.daily.get('sold'))))
