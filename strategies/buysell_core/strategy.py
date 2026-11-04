# -*- coding: utf-8 -*-
# ============================================================
# 当前版本：v1.36（2026-11-04）
# 部署核对：日志首行 `buysell_core init version=v1.36 ...`（init 打印 STRATEGY_VERSION）
# 变更记录统一存 strategies/buysell_core/README.md；本文件只保留版本/部署核对。
# ============================================================
import time, pickle, csv
from datetime import datetime, timedelta

STRATEGY_VERSION = "v1.36"   # 部署核对：日志首行 buysell_core init version=.. （2026-11-04）


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


def _skip_log(tag, sec, reason, msg, throttle_sec=None):
    # v0.80 同因日志节流：同一 (tag,sec,reason) 在 skip_log_throttle_sec 内只打一次，防每帧刷屏；原因变化立即打
    # v0.81 throttle_sec 覆盖节流窗口（[budget] 事件行用 budget_log_event_sec）
    try:
        d = getattr(g, 'skip_log_ts', None)
        if not isinstance(d, dict):
            d = {}; g.skip_log_ts = d
        key = '%s|%s|%s' % (tag, sec, reason)
        now = time.time()
        _sec = float(throttle_sec if throttle_sec is not None else BLS.get('skip_log_throttle_sec', 30.0) or 30.0)
        if now - float(d.get(key, 0.0) or 0.0) < _sec:
            return False
        d[key] = now
    except Exception:
        pass
    log.info(msg)
    return True


# ---------- 参数 ----------
BLS = {
    'DO_ORDER': True,             # v1.0 实盘下单总开关：买卖闭环真实委托；False 仅 SIM 信号（回切模拟置 False）
    'universe': ['600570.XSHG', '603528.XSHG', '601188.XSHG'],   # 占位自选池，待接全市场扫描
    'buy_score_min': 55.0,
    'ma5_pullback': True, 'ma5_loose_high': 1.00, 'ma5_core_only': True,   # 5D线低吸仅对核心(CORE)标签股
    'ma5_second_low_enabled': True,    # v0.70 用生命周期内次低价确认，过滤单次插针
    'ma5_touch_band': 0.02,            # 次低价进入动态MA5上下2%即视为触及
    'ma5_require_bs': False,           # v0.69 低吸不再要求 BS(100日新高)，CORE+首次触 MA5 即可
    'ma5_first_5d': False,             # v0.69 默认按“当日首次触线”；True 可回退五日内首次回踩
    'ma5_buy_score_min': 50.0,         # 5D低吸独立评分门槛（L2 净大单加分已并入 score_now）
    'ma5_buy_ratio': 0.10,             # 5D低吸单笔仓位=总资产10%
    'cold_secs': 60, 'daily_max_buy': 3,   # v1.21 总闸门：打板2 + 其它各策略1（用户确认 2026-11-02）
    'daily_max_board_buy': 2,   # v1.14/v1.26 打板类每日上限（首板/回封/预期board/扫板A+B）；未成交终态释放不占名额
    'daily_strategy_buy_limit': {   # v1.21 其它策略各独立1个名额，不共用（用户确认 2026-11-02）
        'ma5': 1,                   # 5D 低吸
        'core': 1,                  # 核心票买入
        'elastic_arb': 1,           # 弹性套利 arb
        'elastic_top': 1,           # 新最强板块弹性 top
    },
    # 实盘单门控（v1.0）：DO_ORDER=True 放开全路径真实委托（买卖闭环）；EXPECT_ORDER 预期买入路径
    'EXPECT_ORDER': True,           # v1.0 实盘：预期买入发真实 order()
    'tick_exp_enabled': True,       # 预期买入走 tick_data 3s 事件触发（敏捷）
    'exp_order_pct': 0.10,          # 预期买入单笔仓位比例（预算规则「打板20%、其它10%」；实盘测试可调小，如 0.01）
    'buy_chase_pct': 0.008,         # 追高分时确认买入：限价较现价上浮比例（防过度追高）
    'buy_limit_use_sell2': True,    # v1.12/v1.26 追高/扫板限价取 L2 卖2价（chase/sweep，用户确认）
    'buy_limit_sell2_level': 2,     # v1.12 卖2档位（ask_grp level；缺失/异常回退 buy_chase_pct）
    'order_limit_log': True,        # v1.12 下单限价来源核对日志（[order-limit] src=sell2/pct）
    'price_precision': 2,           # A股限价单价格精度（取整 2 位小数）
    'green_open_drop': -5.0,          # P1 绿开核卖：竞价跌幅 % <= -5
    'debug_score': True,            # 回测/交易观察：定时 dump 评分明细
    'debug_interval': 4,            # 每 N 根 bar dump 一次评分
    # 全市场入池扫描（候选 B；失败回退 universe）
    'scan_enabled': True,
    'max_watch': 50,                # 入池上限标的数
    'scan_batch': 600,              # 一次 get_snapshot(列表) 的批规模（单向；v0.74 600/分钟保证开盘10分钟扫完全市场一轮）
    'per_stock_cap': 60,            # 若列表不可用，逐只扫描上限
    'scan_min_chg': 3.0,            # 入池最小涨幅 %
    'skip_st_pool': True,           # v0.75 全链路剔除 ST：scan/watch/near/pool 不含 ST；持仓 ST 保留卖出监控
    'state_save_interval': 60.0,    # v0.75 盘中定期保存状态节流秒（handle_data 帧末）
    'first_zt_rebuild_cap': 5,      # v0.75 重启重建 first_zt 单帧上限（防拖帧）
    'first_zt_rebuild_tx_count': 200,  # v0.75 重启重建逐笔回看条数（API 上限 200）
    'first_zt_rebuild_retry_sec': 30.0,  # v0.75 重建失败逐票重试节流（数据未就绪/回看失败 30s 后再试）
    'first_zt_rebuild_heartbeat_sec': 60.0,  # v0.76 [restart-rebuild] 进度 heartbeat 节流
    'first_zt_rebuild_timeout_min': 30.0,  # v0.80 保留参数（v1.5 起放弃判定改用重试轮次，不再按墙钟一刀切）
    'first_zt_rebuild_max_attempts': 8,    # v1.5 重建重试轮次上限：无涨停证据票自然放弃，有证据票首次即成功
    'hist1d_restart_warm_enabled': True,   # v1.22 同日重启日线冷缓存恢复总开关
    'hist1d_restart_warm_cap': 40,         # v1.22 重启暖缓存单次上限（受 frame_hist1d_prio_limit_fast 配额约束）
    'score_recover_dedup_enabled': True,   # v1.22 [score-recover]/[ma5-recover] 当日恢复日志去重（补拉不抑制）
    'firstzt_rebreak_log_sec': 30.0,       # v1.22 反复炸板/回封日志节流秒（同票 30s 内只打一次）
    'restart_rebuild_1m_enabled': True,      # v0.76 handle_data 1m 兜底消化重建队列（tick 禁用/丢帧）
    'sim_cash_base': 0.0,                 # v1.0 实盘：关闭 SIM 虚拟资金（真实资金基准；回切模拟时改回 200000.0）
    'sim_min_lot': 100,                   # v0.80 SIM 最小一手兜底（qty<=0 时按 1 手发 SIM 信号，仅纯模拟模式）
    'skip_log_throttle_sec': 30.0,        # v0.80 同因日志节流（同一 标的+原因 30s 内只打一次，防每帧刷屏）
    # v0.74 近涨停快速通道（docs/30）：scan 命中后跨轮保留，tick 3s 帧优先跟踪
    'scan_near_chg': 7.0,           # 近涨停快速入池涨幅阈值 %
    'scan_near_cap': 20,            # near_scan 补充池上限（按涨幅+时间淘汰）
    'scan_near_keep_rounds': 3,     # near_scan 跨轮保留轮次（约 3 分钟）
    'tick_near_cap': 12,            # 每帧 near_scan 纳入 tick 目标上限（防拖帧）
    'scan_hot_first': True,         # 开盘 10 分钟热点优先：昨日涨停/自选/预期/固定池先扫
    # 预期三态（候选 D，docs/17）
    'fast_up_ratio': 0.01,          # two_1m 快速上攻：价站上 open*(1+r)
    'seal_exceed_ratio': 1.2,       # 一字板封单 >= 基准*1.2 -> 超预期
    'sell_half_ratio': 0.5,        # P6 评分半仓：卖 可卖数量×比例（整手取整）
    'sell_cold_secs': 30.0,        # 卖出冷却：成交回报驱动的去重备用（未成交防叠单）
    'sell_urgent_floor': 1,        # v1.15 核卖跌停地板价仅作降级(现价接近跌停/无现价时使用), 默认贴近现价
    'urgent_sell_max_discount': 0.02,   # v1.15 urgent 卖出限价下限: 现价*(1-2%), 防超低价废单
    'urgent_sell_floor_near': 0.01,     # v1.15 现价 <= 跌停价*(1+1%) 时才用跌停地板价
    'limit_down_main': 0.10,       # 主板跌停幅
    'limit_down_chinext': 0.20,    # 创业板/科创板 20cm
    'limit_down_bse': 0.30,        # 北交所 30cm
    'sell_pending_timeout': 120.0, # 卖单挂起超时无回报 -> 视为丢失, 放行重试(对齐AXquant order_lost)
    'sell_retry_max': 3,           # v1.15 卖单连续 CANCELLED/REJECTED 轮数上限, 超过暂停重投
    'sell_retry_pause_sec': 600.0, # v1.15 卖单重投熔断暂停秒数(暂停到期放行一次试探)
    'sell_skip_heartbeat_sec': 60.0, # v1.12 [sell-skip] 同因心跳节流（60s 一次并带期间计数）
    'sell_skip_heartbeat_t1_sec': 300.0, # v1.18 当日买入(T+1 enable=0) [sell-skip] 心跳降频
    'sell_source_filter_sold': True,     # v1.18 _sellable_source 过滤已全部成交的卖出票，减少 [pos-stale] 噪音
    'sell_avail_backfill_enabled': True, # v1.20 桥 enable_amount 缺失/0 时按总量回填（防卖出监控空转）
    'sell_avail_t1_strict': True,        # v1.20 T+1 严格：当日买入 enable=0 不回填；False 才允许当日回填
    'sell_avail_amt0_warn_only': True,   # v1.22 总量=0 时仅审计 [pos-amt0] 不回填（防虚构可卖）
    'pos_raw_dump_enabled': True,        # v1.35 [pos-dump] 持仓原始字段当日一次性审计（enable/amount 双 0 时定位真实字段）
    't1_protect_enabled': True,          # v1.30 T+1 当日买入保护触发持久化（记录不卖单，次日首帧复核）
    't1_protect_open_drop': 0.02,        # v1.30 T+1 次日弱开复核阈值：竞价涨幅 <= -2% -> urgent sell
    't1_protect_strong_open': 3.0,       # v1.30 T+1 次日强开复核阈值：竞价涨幅 >= +3% -> 清 pending 转常规监控
    't1_protect_consume_until_minute': 10, # v1.30 T+1 pending 复核窗口：开盘后 N 分钟
    't1_pending_save_sec': 60.0,         # v1.30 [t1-protect] 状态落盘节流（3s 帧内不写盘）
    't1_pending_heartbeat_sec': 300.0,   # v1.35 [t1-protect] 完整行当日一次，后续 300s 计数心跳
    'order_no_reply_timeout': 90.0,  # v1.13 发单后无任何回报超时（_no_reply_reconcile 兜底查询）
    'order_reconcile_interval_sec': 60.0,  # v1.13 撤单失败/无回报委托兜底对账节流
    'board_cancel_warn_sec': 300.0,  # v1.15 撤单终态长时间未确认告警阈值
    'cash_baseline_window': 300.0,   # v1.13 开盘资金未就绪时基线兜底窗口（09:25 前后缓存真实现金）
    'seal_fail_ratio': 0.333,       # 封单衰退：<= 基准*(1/3) -> 破
    'board_queue_cancel_seal_ratio': 0.333,   # v1.6 打板未成交排单：封单<=基准*该比例 -> 撤单（缺省对齐 seal_fail_ratio）
    'board_queue_cancel_bid_ratio': 0.5,      # v1.6 打板未成交排单：买一委托笔数<=基准*该比例 -> 撤单（对齐一字封单 bid_fail）
    'board_queue_cancel_break_enabled': True, # v1.18 在途 break_cnt 增加且未回封 -> 撤单（排单成交保护）
    'exp_board_queue_gate': True,             # v1.18 预期打板：已有 break 历史需回封+封单达标才下板单
    'exp_board_queue_max_sec': 600.0,         # v1.18 在途 break 保护窗口（窗口内出现 break/封单衰减才撤，不硬撤稳定封单）
    'firstzt_min_seal': 50000.0,      # v1.26 快照兜底最小封单额(元)防假封；tx 首帧成交豁免
    'firstzt_min_bids': 5,            # 首此涨停上报最小买一挂单量(手)
    # v0.49 炸板应对收紧 + 回封打板（docs/33）
    'break_sell_bid_level': 3,        # 炸板卖出限价：L2 买N档价（默认买3）
    'break_sell_floor_ratio': 0.95,   # 炸板卖出限价下限（现价*0.95，防过度杀价）
    'seal_fail_ratio_unique': 0.25,   # 唯一身位连板封单衰竭容忍度（更小=更容忍）
    'break2_half_ratio': 0.5,         # 二次炸板减半（仅唯一身位+后排助攻/人气龙头）
    'reboard_buy_enabled': True,      # 回封打板总开关（前排首板/2板 10:00前炸板回封）
    'reboard_until_minute': 30,       # 回封打板生命周期：09:30-10:00
    'reboard_max_lianban': 2,         # 回封仅限首板或2板
    'reboard_seal_min': 50000.0,      # v1.26 回封封单下限(元)（20万->5万提灵敏度）
    'reboard_l2_big_min': 0.10,       # 回封要求大单占比>=10%实时成交量
    'tick_full_sell_enabled': True,      # v0.53 持仓监控全覆盖：P4/P5/P6 并入 3s tick（1m sell_manager 兜底）
    'frame_sellscan_limit': 8,           # v0.53 帧内评分卖出持仓数上限（持仓一般<=5 天然不超）
    # v0.59 持仓卖出闭环（docs/33）：持仓地位评估 + P7a 连板放量不封板 / P7b 跟风拉升不封板 / P7c 首板次日不主动冲板分批清仓
    'p7_sell_enabled': True,             # P7a/P7b/P7c 总开关
    'p7a_vol_ratio': 1.10,               # P7a 放量阈值：今日量 >= 昨日量×ratio（唯一身位降级减半）
    'p7a_half_ratio': 0.5,               # P7a 唯一身位降级：减半（非唯一清仓）
    'p7b_board_min': 1.0,                # P7b 板块强阈值（board_strength>= 或题材存活龙头封板）
    'p7b_surge_min': 1.5,                # P7b 跟风拉升 1m 涨幅阈值%
    'p7b_half_ratio': 0.5,               # P7b 减半比例
    'p7c_until_minute': 30,              # P7c 观察窗口：09:30-10:00（首板次日不主动冲板）
    'p7c_surge_min': 1.5,                # P7c 冲高触发：现价>=标记价×(1+%) 分批卖
    'p7c_batch_cold_secs': 10.0,         # P7c 批次冷却（两批 2×50%，10s 批次间隔替代 30s 通用冷却）
    'p7c_active_threshold': 0.5,         # 主动判定：个股涨幅 >= 板块强度 + 阈值（%）
    'p7d_sell_enabled': True,            # P7d 核心冲高偏离总开关：非唯一核心持仓 冲高未封板+偏离分时均价 -> 减半
    'p7d_limit_gap': 0.04,               # P7d 冲高判定：现价距涨停价 <= 4%（未封板视为冲高）
    'p7d_vwap_dev_min': 3.0,             # P7d 偏离分时均价阈值 %（现价 >= VWAP×(1+%)）
    'p7d_half_ratio': 0.5,               # P7d 减半比例
    'p6_two_frame_enabled': True,        # v1.20 P6 两帧确认：连续弱分才减半（防单帧抖动误卖）
    'p6_confirm_frames': 2,              # v1.20 连续弱分帧数
    'p6_confirm_win_sec': 30.0,          # v1.20 两帧间隔窗口（超时重新计数）
    'hold_stand_cache_sec': 15.0,        # _hold_stand 节流缓存
    'hold_stand_log_sec': 60.0,          # [hold] 地位日志节流（/股）
    # 预期文件：AXquant 预期三态 csv（docs/25）
    'expectation_suffix': '.csv',
    'scan_interval': 1,             # 每 N 根 bar 触发一次全市场扫描（v0.47 收紧 4->1）
    'score_sell_clear': 30, 'score_sell_half': 50,
    # 止损按板块
    'stop_loss_pct': 0.05, 'stop_loss_chinext': 0.07, 'stop_loss_star': 0.08, 'stop_loss_bse': 0.10,
    'elastic_max_buy_pct': 0.10,      # 弹性追高 300/688 买入价前收*1.10 上限（打板豁免）
    'elastic_max_buy_pct_bse': 0.15,  # v1.6 北交所弹性追高买入价前收*1.15 上限（30cm 减半）
    'exp_sell_on_pending_miss': False, # P2E 竞价核卖：pending_miss 默认只记录暂缓，confirmed_miss/degraded 才卖
    # v0.58 P2E 竞价核卖（docs/33）：同题材中位崩塌传导 + 自身大不及（9:24:45 确认段评估触发）
    'p2e_sell_enabled': True,          # v0.58 P2E 竞价核卖总开关（钩子 + 卖出链统一判定 _p2e_core_sell_check）
    'p2e_theme_sell_enabled': True,    # 同题材中位崩塌传导子开关（A 路径）
    'p2e_theme_drop_min': -2.0,        # 中位股最弱竞价涨幅阈值 %（昨日涨停中位，今日默认 -2%）
    'p2e_auction_drop_min': -2.0,      # 自身大不及竞价涨幅阈值 %（文件 miss + 今日竞价绿开幅度）
    'p2e_confirm_at': '09:24:45',      # 9:15-9:25 钩子确认段起点（此前预热只日志不触发）
    'p2e_reverse_guard_enabled': True, # v1.28 触发A持仓自身反证：竞价超预期/一字封死不核卖
    'p2e_audit_heartbeat_sec': 60.0,   # v1.28 [P2E-reverse]/[P2E-skip] 审计节流秒数
    'single_stock_cap': 0.30,          # 单支市值上限：买入后该股市值 <= 总资产×30%（AXquant single_stock_cap）
    'buy_lot_step': 100,               # v1.17 买入整手步长（A股最小申报单位，取整/仓位缩量共用）
    'ordinary_buy_ratio': 0.10,        # 普通买入单笔=总资产×10%（AXquant ordinary_buy_ratio=1/10，替代硬编码0.3）
    'board_buy_budget_ratio': 0.20,    # 打板买入单笔=总资产×20%（AXquant board_buy_budget_ratio）
    'red_gate_enabled': False,         # 红盘比买入门（默认关；开启才要求板块红盘比>=red_ratio_buy_min 且情绪回暖，v0.29）
    'sentiment_enabled': False,        # v0.29 情绪回暖闸门（T-1 冰点基线存在时，红盘比恢复才放行）
    'sentiment_warm_base': 0.55,       # 回暖恢复阈值基准（对齐 red_ratio_buy_min）
    'sentiment_warm_decay': 0.02,      # 每多 1 天冰点，恢复阈值降低（回暖概率增加）
    'sentiment_warm_min': 0.45,        # 恢复阈值下限
    'sentiment_ice_ratio': 0.40,       # 盘中实时红盘比 < 此值 = 今日继续冰点
    'sentiment_pos_cap_enabled': True,   # v0.31 情绪仓位上限（总仓位：冰点40%/回暖80%，已默认启用，盘前/盘中均有 [pos-cap] 日志）
    'pos_cap_over_behavior': 'shrink',   # v1.17 情绪仓位闸门超限处理：shrink=缩量至剩余额度 / skip=整单拒绝
    'ice_pos_pct': 0.40,              # 冰点日最大总仓位
    'warm_pos_pct': 0.80,             # 回暖日最大总仓位
    'warm_taper_start': 3,            # 连续回暖/延续 >= N 日开始递减（分歧概率上升）
    'warm_taper_step': 0.10,          # 每多 1 个连续回暖日递减幅度
    'warm_taper_min': 0.50,           # 递减下限（分歧保护）
    'red_ratio_buy_min': 0.55,         # 红盘比下限（对齐 AXquant first_board_buy 回暖下限）
    # v0.41 全市场红盘比（情绪温度消费口径统一：冰点/回暖判定用全市场，替代个股板块近似；docs/16）
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
    'vwap_weak_grace_sec': 30,           # v0.73 分时 VWAP 弱化首帧宽限（09:30-09:30:30 不判 CS）
    'vwap_weak_confirm_sec': 6,          # v0.73 VWAP 弱化两帧确认（连续弱 N 秒才弃，允许回封恢复）
    'vwap_weak_at_limit_exempt': True,   # v0.73 贴板/封死豁免 VWAP 弱化（px>=up*0.998）
    'exp_entry_type_resync': True,       # v0.73 开盘重标 buy 候选 one_word/normal（防一字走普通超预期路径）
    'exp_meet_score_ready': True,        # v1.8 pending_meet 评分就绪兜底（1m<2 根时 board 就绪也放行）
    'exp_meet_require_intraday_confirm': True,  # v1.11 meet/未标注买入强制分时确认（两1m强势或1分钟内触板，且不破VWAP）
    'exp_bad_seal_red_exceed': 0.0,             # v1.27 放量烂板/炸板不回封：红开>该值=竞价超预期
    'exp_bad_seal_big_green_miss': -2.0,        # v1.27 放量烂板/炸板不回封：绿开<=该值或跌停开=低于预期
    'one_word_open_meet_ratio': 0.8,            # v1.27 一字/近一字开盘符合下限=涨停幅*该比例（主板+8%/20cm+16%/30cm+24%）
    'first_board_buy_enabled': True,   # 首板打板总开关（tick 首触主路径 + 1m 兜底）
    'first_board_minute': 10,          # 首板闸门：开盘 N 分钟内（09:30-09:40）
    'first_board_seal_min': 50000.0,   # v1.26 首板打板最小封单额(元)：tx 首帧成交豁免，仅 snap 兜底
    'new_theme_sweep_enabled': True,   # v1.26 A 新题材首板提前扫板总开关
    'new_theme_sweep_window_min': 10,  # v1.26 A 扫板窗口：开盘 10 分钟（09:30-09:40）
    'elastic_from_sweep_enabled': True,       # v1.32 A分流：20cm/北交票扫板前置分流开关
    'elastic_from_sweep_limit_ratio': 0.99,   # v1.32 低于涨停价×此比例走弹性语义；>=此值保留临板扫板
    'elastic_from_sweep_ratio': 0.10,         # v1.32 弹性语义单笔=总资产10%（对齐 ordinary_buy_ratio）
    'vwap_follow_frames': 2,           # v1.26 分时均价跟随拉高：连续 N 帧均价走高
    'vwap_follow_min_rise': 0.0005,    # v1.26 均价走高容忍（相对涨幅，防同值抖动）
    'board_first_frame_fresh_sec': 6.0, # v1.26 涨停价首帧新鲜窗口（首帧成交后 6s 内打板）
    'firstzt_buy_event_enabled': True,  # v1.34 首触/回封/near 同帧事件统一派发（预期/核心/首板/回封/扫板/弹性）
    'board_first_frame_baseline': 'ts', # v1.34 首帧动作基准：ts=检测帧(灵敏), tx=真实首笔(严格)
    'tx_lag_warn_sec': 10.0,            # v1.34 firstzt feed_lag 告警阈值（provider/批处理延迟区分）
    'tick_event_sweep_one_per_frame': True, # v1.34 同帧事件 sweep A 一帧一单
    'pm_theme_buy_enabled': True,         # v1.36 午后新题材爆发前排试点总开关（13:00-13:30）
    'pm_theme_buy_after_hhmm': '13:00',   # v1.36 午后通道开始
    'pm_theme_buy_until_hhmm': '13:30',   # v1.36 午后通道硬截止
    'pm_theme_buy_ratio': 0.10,           # v1.36 打板名额耗尽后切前排弹性套利单笔=总资产10%
    'pm_theme_buy_board_ratio': 0.20,     # v1.36 打板名额可用时单笔=总资产20%
    'dyn_unq_mid_skip': True,          # v0.46 竞价唯一预判跳过中位股（与 _mid_board_avoid 统一口径）
    'dyn_unq_require_board_map': True, # v0.73 竞价唯一需板块成员映射成功（防竞品=0 假唯一）
    'dyn_unq_auction_member_cap': 15,   # v0.73 竞价唯一板块成员参与上限（兜底口径）
    'l2_big_enabled': True,            # v0.47 L2 大单占比（近涨停候选逐笔累计）
    'l2_big_amt_min': 1000000.0,       # 单笔大单阈值(元)
    'l2_big_amt_unit': 'shares',         # v0.48 business_amount 单位: shares(股)/lots(手)/yuan(元)
    'l2_big_dir_enabled': True,         # v0.50 大单净量口径: 买-卖 方向分计（False 回退 v0.47 全大单）
    'l2_big_dir_map': {'0': 'sell', '1': 'buy', '2': 'un', '3': 'un'},  # v0.51 方向映射按官方字典校准(0=卖/1=买/2=借入/3=出借->不计净量)，可配置纠偏
    'l2_tickdir_enabled': True,      # v0.52 已成交大单回看播种（get_tick_direction 分时成交, 含竞价终态）
    'l2_tickdir_pages': 3,           # 播种回看页数上限（每页 data_count<=200, start_pos 翻页）
    'l2_tickdir_pages_restart': 10,  # v0.52a 盘中重启补种页数（约2000分笔覆盖9:30-10:30活跃窗口至09:25竞价；09:25/09:31播种保持3页）
    'l2_big_seed_onjoin_enabled': True,   # v0.67 盘中新入池触板票补播种（_near 首见 60s 节流回看）
    'l2_tickdir_pages_onjoin': 5,      # v0.67 盘中入池播种页数（约1000分笔，覆盖入池前成交窗口）
    'l2_big_seed_onjoin_interval_sec': 60,  # v0.67 盘中入池播种节流秒（防同帧/频繁重种）
    'l2_big_seed_onjoin_px_sec': 0,     # v0.73 逐票入池播种节流（0=每票当日首见即种，不被全局节流阻塞）
    'l2_big_seed_onjoin_max_per_frame': 5,  # v0.73 单帧逐票播种上限（防拖帧）
    'l2_big_seed_on_firstzt': True,     # v0.73 首封瞬间未播种补种（覆盖直接跳进首封的票）
    'l2_big_seed_log': True,            # v0.73 播种后补打 [l2-big-seed] 摘要（盘中核对）
    'l2_big_log_sec': 300,             # v0.67 [l2-big] 探针重复打印间隔秒（首帧立即，之后按间隔重打）
    'l2_big_ratio_min': 0.10,          # 大单占比>=10% 加分/封单豁免
    'l2_big_bonus': 5.0,               # 大单占比达标加分(分)
    'l2_big_seen_cap': 20000,          # 去重序号上限（防累计无限膨胀）
    'tick_board_scan': True,           # v0.47 B1: tick 目标并入强度前三板块成员
    'tick_board_member_cap': 10,       # 每板块并入成员上限（v0.48 收紧, 仅首板窗口）
    # v0.19 弹性套利 elastic_arb（AXquant Phase 1）
    'elastic_arb_enabled': True,       # 弹性套利总开关
    'elastic_arb_window_minute': 20,   # v1.6 弹性套利生命周期：开盘后 20 分钟内（09:30-09:50）
    'elastic_arb_min_yizi': 2,         # 板块一字板>=N 情绪爆发（对齐 elastic_arb_min_yizi）
    'elastic_arb_min_1m_surge': 3.0,   # 最新 1m 柱 (close-open)/open >= N% 大阳线
    'elastic_arb_min_change': 6.0,     # 20cm 当前涨幅下限 %
    'elastic_arb_max_change': 10.0,    # 20cm 当前涨幅上限 %（防炸板）
    'elastic_arb_min_change_bse': 8.0, # v1.6 北交所当前涨幅下限 %
    'elastic_arb_max_change_bse': 15.0,# v1.6 北交所当前涨幅上限 %
    'elastic_arb_max_open_change': 12.0, # 20cm 开盘涨幅上限 %（防大幅高开兑现）
    'elastic_arb_max_open_change_bse': 15.0, # v1.6 北交所开盘涨幅上限 %
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
    'pm_fast_after_hhmm': '13:00',       # v1.36 午后快速刷新窗口开始（13:00-13:30 高灵敏度）
    'pm_fast_until_hhmm': '13:30',       # v1.36 午后快速刷新窗口截止
    # v0.25 Phase 3 帧级拉取预算（tick_data 每 3s 一帧，超限按优先级降级）
    'budget_log_enabled': True,       # 帧末输出 [budget] 统计
    'budget_log_heartbeat_sec': 60.0,  # v0.81 常规 [budget] 摘要节流（0=常规摘要静默，只打事件）
    'budget_log_event_sec': 30.0,      # v0.81 over/degraded 事件行同因去重窗口（覆盖 _skip_log 节流）
    'budget_log_on_over': True,        # v0.81 帧内预算超限立即打事件行
    'budget_log_on_degraded': True,    # v0.81 帧内数据源降级（新增）立即打事件行
    'budget_tail_idle_after_hhmm': '14:45', # v1.35 尾盘后非核心 board/hist1d 暂停刷新
    'frame_snapshot_limit': 2,        # 帧内批量快照批次（1 批量+1 兜底）
    'frame_snapshot_fallback_cap': 5, # 批量缺标逐只兜底上限
    'frame_tx_limit': 2,              # 帧内逐笔批量拉取+缺票逐只兜底（批量1 + 兜底预算1）
    'l2_tx_fallback_enabled': True,   # v0.67 批量逐笔缺票逐只兜底总开关
    'l2_tx_fallback_cap': 5,          # v0.67 批量缺票逐只兜底上限（帧预算内逐只补回）
    'frame_gear_limit': 15,           # 帧内 get_gear_price 总次数
    'frame_m1_limit': 20,             # 帧内 1m K线 get_price 总次数（two_1m/弹性 surge 共用）
    'frame_hist1d_limit': 10,         # 帧内 1d 历史 get_price 总次数
    'frame_hist1d_limit_fast': 24,    # v1.16 10:00 前日线预算放大（原 frame_day_limit_fast 未接入 hist1d 消费链）
    'frame_hist1d_prio_limit': 12,    # v1.16 核心/预期票日线独立配额，不挤占普通预算
    'frame_hist1d_prio_limit_fast': 40,  # v1.20 10:00 前核心/预期票日线独立配额放大
    'frame_hist1d_limit_afternoon': 4,     # v1.35 10:00 后日线限额（午盘降频，灵敏度留给首触/封单）
    'frame_hist1d_prio_limit_afternoon': 6, # v1.35 10:00 后核心/预期日线独立配额
    'frame_board_limit': 6,           # 帧内板块强度组（get_industry_stocks+get_snapshot 各 1 次/组）
    'frame_board_limit_afternoon': 3, # v1.35 10:00 后板块强度组限额（降频，核心/持仓优先）
    'frame_blocks_limit': 10,         # 帧内 get_stock_blocks 总次数（300s 缓存后≈0）
    'frame_bcode_limit': 20,          # 帧内板块归属（3600s 缓存后≈0）
    # v0.36 帧预算快速期放大 + 高优先级独立配额（docs/24 §25）：10:00 前与 3s 帧同频，防候选多时排名/确认滞后
    'frame_board_limit_fast': 24,     # 10:00 前板块强度组限额（平时 6；v0.36e 合并快照每帧一批=1次 RPC，放大供多板块并集续算）
    'frame_m1_limit_fast': 30,        # 10:00 前 1m K线限额（平时 20）
    'frame_m1_prio_limit': 15,        # 预期分时确认 two_1m 独立配额（高优先级，不挤占弹性 surge）
    'frame_blocks_limit_fast': 20,    # 10:00 前板块全列表归属预算（_boards_of 新最强板块用）
    'frame_day_limit': 8,             # 帧内 1d 日线 get_price 次数（板块5日强度续算）
    'frame_day_limit_fast': 16,       # 10:00 前日线预算放大（v0.53 持仓评分 P5/P6 并入 tick 共用 hist1d）
    # v0.36 弹性套利：当日新最强板块第一时间跟踪（最主动弹性标的，10% 前买入）
    'elastic_top_enabled': True,
    'elastic_top_window_minute': 20,  # v1.6 新最强板块弹性跟踪窗口：09:50 前
    'elastic_top_min_strength': 2.0,  # 新最强板块强度阈值 %（候选池内第一，>=2%）
    'elastic_top_min_1m_surge': 2.0,  # 最主动弹性标的 1m 大阳线下限 %
    'elastic_top_buy_before_pct': 10.0,  # 20cm 10% 涨幅前买入
    'elastic_top_buy_before_pct_bse': 15.0,  # v1.6 北交所 15% 涨幅前买入
    'elastic_top_cache_ttl': 15.0,    # v1.11 板块内弹性候选排序缓存 s（30->15 提升灵敏度）
    'elastic_top_surge_top_n': 5,     # v0.36e 弹性候选 surge 只算前 N（批量快照按涨幅粗排后）
    'elastic_top_member_cap': 20,     # v0.36e 概念板块强度/开盘涨幅成员样本上限（对齐旧 [:20]）
    'frame_snap_batch': 100,          # v0.36e 帧内合并快照成员批上限（概念板块并集分帧续算）
    'board_concept_unified': True,    # v0.60 板块口径统一开关：True=全链路 THS 概念口径；False=回退 API 双轨
    # v0.36b 新爆发板块确认因子：T日开盘板块涨幅 明显强于 自身平均5日强度（docs/36 §9）
    'elastic_top_breakout_min_open': 1.0,   # 开盘板块涨幅自身下限 %
    'elastic_top_breakout_min_boost': 2.0,  # 开盘涨幅 - 5日均强度 的最小增强 %
    'elastic_top_avg5_grace_min': 5.0,      # v1.11 5日均值样本未就绪宽限分钟（09:35 前降级触发，之后仍等 avg5）
    'elastic_top_max_trigger_per_day': 2,   # 当日「新最强板块」触发（易主）上限
    # v0.36c 稳定性：连续 N 帧保持第一才触发/易主；top1-top2 领先幅度门槛（防并列/紧咬）
    'elastic_top_stable_frames': 2,     # v1.11 top1 需连续 N 帧保持第一（3s 帧 ≈6s，3->2 收敛节奏）
    'elastic_top_lead_min': 0.5,        # top1 强度 - top2 强度 最小领先 %（防并列/紧咬误判）
    'board_probe_enabled': True,        # 盘中探针：get_stock_blocks 全类别 + get_industry_stocks HY/GN 返回量
    # v0.26 tick 级卖出（事件驱动：3s 帧末响应炸板/封单大减/急卖；docs/33）
    'tick_sell_enabled': True,       # tick 级卖出总开关
    'break_sell_enabled': True,      # 炸板卖出：first_zt.break 首触发 -> 卖
    'seal_low_sell_enabled': True,   # 封单大减卖出：first_zt.seal_low 首触发 -> 卖
    'seal_low_confirm_sec': 6.0,     # v1.23 封单大减两帧确认（3s tick 约 2 帧），尾盘竞价段同样生效
    'seal_low_fast_ratio': 0.15,     # v1.23 封单骤减快确认：seal <= 首封*该比例（含0）时 1 帧即卖，保灵敏度
    'seal_low_tail_auction_start': '14:57',   # v1.29 收盘集合竞价开始：SEAL_LOW_FAST 降级两帧确认
    'seal_low_tail_auction_end': '15:00',     # v1.29 收盘集合竞价结束
    'seal_low_tail_log_sec': 15.0,            # v1.35 尾盘 SEAL_LOW_FAST 同票日志节流秒（状态机仍每帧评估）
    'seal_low_batch_invalid_ratio': 0.3,  # v1.23 同帧 L2 十档缺失占比超阈值 -> 整批不健康，跳过 SEAL_LOW 卖出
    'seal_low_batch_invalid_min': 5,      # v1.23 整批不健康的缺失家数下限（与占比同时满足才熔断）
    # v1.24 竞价-开盘-10:00 跌停题材因子（docs/43 扩展）：全市场跌停归集到题材/概念，
    # 作用方向分减分与题材级回避；昨日涨停池成员今日跌停视为强负反馈
    'ld_senti_enabled': True,          # 跌停题材因子总开关
    'ld_theme_soft_min': 1,            # 所属概念/题材跌停 >= N -> 方向分减分
    'ld_theme_hard_min': 2,            # 所属概念跌停 >= N -> avoid 直接不参与
    'ld_theme_penalty': 0.8,           # 题材跌停减分幅度（默认抵消 attack bonus）
    'ld_zt_ld_hard_enabled': True,     # 昨日涨停池成员今日跌停 >=1 -> 所属题材 hard 回避
    'ld_market_soft_n': 20,            # 全市场跌停家数 >= N -> 全局方向分减分
    'ld_market_penalty': 0.3,          # 全市场跌停扩散减分幅度
    'ld_sort_penalty': 1.5,            # 有跌停题材的排序加分扣减（硬回避时归零）
    'ld_ttl_before': 15.0,             # v1.25 10:00 前跌停因子刷新 TTL（灵敏度优先，受 market budget 约束）
    'ld_ttl_after': 120.0,             # v1.25 10:00 后跌停因子刷新 TTL（降频，避免无谓全量拉取）
    'sealed_fresh_secs': 5.0,        # 封死判定持续 N 秒才生效（防瞬时零卖盘误判不排单）
    'sealed_offerqty_enabled': True, # 用 total_offerqty==0 判封死（快照总委卖量；缺失回退 ask_grp 空判）
    # 打分引擎（AXquant 默认）
    'score_base': 40,
    'score_recover_probe_cap': 20,  # v1.12 [score-na] 恢复探针每帧最多补评票数（防 board 预算打满）
    'score_recover_probe_cap_fast': 60,  # v1.32 10:00 前恢复探针扩容 40->60（核心/预期优先，灵敏度优先）
    'hist1d_prewarm_enabled': True,  # v1.16 09:25/09:31 核心/预期票日线预暖
    'hist1d_core_ttl': 180.0,        # v1.20 核心/预期票日线缓存 TTL 放大（覆盖 09:25->09:31 窗口）
    'hist1d_prewarm_ttl': 600.0,     # v1.32 预温结果 TTL 放大（09:25/09:31 拉到 10:05 不中途失效）
    'hist1d_prewarm_ttl_enabled': True,  # v1.32 10:05 前核心/预期票日线缓存放大开关
    'hist1d_prewarm_until_hhmm': '10:05', # v1.32 预温保活截止（10:05 后回落常规 TTL）
    'lb_senti_auction_retry_enabled': True,  # v1.16 09:26 竞价情绪未就绪补拉
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
    'dyn_unq_theme_mode': True,         # v1.30 盘中唯一以题材桶+连板梯队为口径（替代概念前15假唯一）
    'dyn_unq_min_level': 2,             # v1.30 唯一只授主题内最高存活身位且 >=2
    'dyn_unq_min_members': 3,           # v1.30 主题比较集最少成员数（不足不判唯一）
    'dyn_unq_min_covered': 0.8,         # v1.30 主题比较集行情覆盖最低比例（不足不判唯一）
    'dyn_unq_sep_chg_gap': 2.0,         # v1.30 同身位竞品分离涨幅落后阈值 %
    'dyn_unq_max_active': 3,            # v1.30 并发盘中唯一上限（按身位+首触时间淘汰）
    'dyn_unq_pool_cache_sec': 15,       # v1.30 主题比较池缓存 s（与题材动态状态同频）
    'dyn_unq_sep_recheck_sec': 15,      # v1.30 未分离/分离后唯一性重评节流 s
    'dyn_unq_surge_na_max': 0.5,        # v1.30 跟风 surge 缺失占比上限（超过不确认）
    'dyn_unq_theme_rank_max': 3,        # v1.30 扫板 B 题材强度门：主题梯队名次上限
    'dyn_sweep_enabled': True,          # 竞价唯一扫板 开关
    'dyn_sweep_window_minute': 30,      # v1.11 扫板窗口 09:30-10:00（15->30 与动态唯一/预期买入对齐）
    'dyn_sweep_budget_ratio': 0.20,     # 扫板单笔预算（=打板 20%）
    # v0.55 盘中题材身位/跟风/强度动态修正（docs/41）：zt_lianban 题材梯队列静态锚 + 盘中重算
    'zt_theme_dyn_enabled': True,       # 盘中动态题材状态总开关
    'zt_theme_dyn_cache_sec': 15,       # 动态题材状态缓存刷新秒数
    'zt_theme_leader_sort_bonus': 1.5,  # 题材动态龙头排序加分（_pool_exp_priority）
    'zt_theme_rank_bonus_step': 0.3,    # 题材梯队名次排序加分步长（rank 越小加分越多）
    # v0.56 盘中新题材发酵识别/消费（docs/42）：新首板助攻 -> 题材桶桥接 + 发酵状态机 + 前排闸门
    'zt_theme_ferment_enabled': True,   # 盘中新题材发酵总开关
    'zt_theme_ferment_window_min': 25,  # 发酵确认时间窗（分钟）
    'zt_theme_ferment_assist_min': 2,   # 窗内新增首板助攻最少家数
    'zt_theme_ferment_hot_assist': 5,   # 高潮阈值：助攻家数 >= 此值
    'zt_theme_ferment_front_bonus': 0.8,  # 确认题材前排排序加分
    'zt_theme_ferment_sort_bonus': 0.5,   # 确认题材成员排序加分
    'zt_theme_ferment_seal_min': 50000.0, # 前排封单下限（0=关闭；无 L2 数据不拦截）
    # v0.65 连板盘中情绪动态（docs/43）：竞价终态 -> 盘中确认 -> 10:00 状态；中高位赚钱效应 vs 低位/新方向切换
    'lb_senti_enabled': True,             # 连板盘中情绪动态总开关
    'lb_senti_cache_sec': 15.0,           # 盘中确认滚动缓存（10:00 前）
    'lb_senti_cache_sec_after': 60.0,     # 10:00 后降频缓存
    'lb_senti_heartbeat_sec': 60.0,       # v1.12 分钟级 heartbeat（phase 变化立即打，之后每 60s 补打）
    'lb_senti_high_min': 2,               # 中高位分档下限（T-1 board_cnt>=2 计入中高位）
    'lb_senti_high_max': 5,               # 中高位分档上限（>5 或 unique_high 为高标）
    'lb_senti_promo_min': 0.60,           # 高位延续：中高位晋级率下限
    'lb_senti_break_max': 0.20,           # 高位延续：炸板率上限
    'lb_senti_rotation_promo': 0.40,      # 切低位：中高位晋级率上限
    'lb_senti_rotation_break': 0.30,      # 切低位：炸板率下限（参与判定）
    'lb_senti_new_dir_min': 2,            # 新方向承接最少家数（确认临时题材/助攻数）
    'lb_senti_red_cold': 0.40,            # 红盘比冰点阈值（< 此值且低位无承接 -> 冰点观望）
    'lb_senti_t100_freeze': True,         # 10:00 冻结快照（参与降频不归零）
    'lb_senti_participate_scale': 0.5,    # 10:00 后参与优先级缩放（降频不归零）
    'lb_senti_cut_enabled': True,         # P8 中高位兑现指导开关
    'lb_senti_cut_half_ratio': 0.5,       # P8 中高位兑现减半比例
    'lb_senti_min_touch_ratio': 0.5,      # 状态机样本门槛：中高位已触板占比 >= 此值才判 phase（早盘不足 -> watch）
    'lb_senti_hysteresis_sec': 60.0,      # 状态机风险升级滞回：同候选持续 N 秒才切换（防单帧抖动）
    # v0.78 A 状态机可达性（10:00 前保证灵敏度与节奏）：早盘放宽样本门槛/缩短滞回，10:00 冻结必落档
    'lb_senti_min_touch_ratio_before': 0.3,  # 10:00 前样本门槛比例（10:00 后仍用 lb_senti_min_touch_ratio=0.5）
    'lb_senti_min_touch_floor': 3,           # 10:00 前样本门槛绝对下限（mid_pool=9 -> touched>=3 即判档）
    'lb_senti_hysteresis_sec_before': 30.0,  # 10:00 前风险升级滞回（10:00 后仍用 lb_senti_hysteresis_sec=60）
    'lb_senti_auction_ready_min': 0.6,       # v0.78 D 竞价就绪率下限（不足 -> ready=False 不写 open/green/yizi 率）
    'lb_senti_gate_all_buys_enabled': True,  # v0.78 B 统一方向闸总开关（首板/回封/弹性并入，low 恒放行）
    # v1.2 连板高度压制 -> 唯一连板空间闸门（docs/40）：唯一连板距压制位空间不足不参与
    'unq_space_gate_enabled': True,     # 唯一连板空间闸门总开关（_lb_senti_buy_gate 消费）
    'unq_space_min': 0.15,              # 距压制位最小比例空间：(height_suppress-板数)/height_suppress >= 0.15 才博弈
    'lb_senti_rotate_low_bonus': 1.2,     # 切低位：低位/新方向首板参与排序加分
    'lb_senti_rotate_mid_pen': -0.8,      # 切低位：中位股参与排序减分（兑现侧）
    'lb_senti_rotate_high_pen': -0.6,     # 切低位：高标参与排序减分
    'lb_senti_ice_low_bonus': 0.3,        # 冰点观望：仅低位首板试错加分（其余不参与）
    'lb_senti_high_bonus': 0.6,           # 高位延续：中高位/高标参与排序加分
    # v0.71 预期买入方向裁判：只做硬跳过和排序奖励，不改技术确认与仓位比例
    'exp_direction_enabled': True,        # 预期方向裁判总开关
    'exp_direction_attack_bonus': 0.8,    # attack_high/attack_low 排序加分
    'exp_direction_avoid_hard_skip': True,  # avoid 直接不参与
    'exp_direction_hot_front_only': True,   # 发酵高潮只允许最强前排
    'exp_direction_rotate_leader_exception': True,  # rotate_low 允许原题材唯一存活龙头
    'exp_direction_log': True,             # 输出方向裁决日志
    # v1.31 云端近期情绪温度历史（sentiment_hist.pkl，docs/40 扩展）：CSV 为 T-1 基线，云端盘中确认当日状态
    'senti_hist_enabled': True,            # 云端近期情绪温度历史总开关
    'senti_hist_keep_days': 10,            # 历史保留最近交易日数（用户确认 10 日）
    'cold_streak_min': 3,                  # 连续冰点 >= 3 日为连冰（用户确认阈值）
    'theme_overheat_zt_min': 20,           # 题材内涨停家数再次 > 20 = 过热（首次只记 first_burst，用户确认）
    'warm_confirm_front_bonus': 0.4,       # 回暖确认日已确认前排额外排序加分（不放开技术硬条件/仓位）
    'stage_rear_round_enabled': True,      # 过热/分歧日后排/杂毛按轮次逐步减半清仓（沿用 P8 触发条件）
    'stage_rear_cut_ratio': 0.5,           # 阶段后排逐步清仓每轮比例
    'stage_rear_max_rounds': 3,            # 阶段后排逐步清仓最大轮次（保留尾仓交 P5/P6）
    'stage_rear_round_gap_sec': 60.0,      # 阶段后排相邻轮次最小间隔（防 3s tick 连续砍仓）
    'senti_stage_cache_sec': 15.0,         # 阶段判定缓存（避免 3s tick 重复计算）
}
# 打分加减分配置（scoring.bonus.* / scoring.penalty.* 默认）
BONUS = {
    'auction_beat_history': 5, 'touched_limit_up_early': 6, 'volume_ratio_shrink': 2,
    'is_100day_high': 10, 'tag_bs': 5, 'tag_core': 5, 'tag_lb': 5,
}
PENALTY = {
    'open_low_5': 15, 'open_low_2': 8, 'open_low_0': 3, 'board_weak': 8,
}
ATK = {'a1': 6.0, 'a2': 3.0, 'a3': 2.0, 'main_threshold': 0.08}


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
        # v0.74 帧推送命中票也用同帧 raw 回填更早首笔（0 额外 API），ms 尽量贴近真实首笔
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
        for sec in [s for s in out if raw.get(s)]:
            raw_ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
            if raw_ms is not None and raw_ms < out[sec]:
                out[sec] = raw_ms
        try:
            _tx_big_feed(secs, fields, raw)   # v0.47 L2 大单累计（同帧 raw）
        except Exception:
            pass
        return out

    def _tx_pull_raw(self, secs):
        # v0.67 按 3s 帧缓存原始逐笔（同一帧多消费不重复拉）；批量缺票在帧预算内逐只兜底，
        # 兜底结果并入本帧 raw（下帧新 token 仍会重试）；异常 -> {}（不缓存，下一帧再试）
        token = int(time.time() / 3.0)
        raw = self.cached(('tx_pull', token), '_frame_', 3.0,
                          lambda: get_individual_transaction(secs,
                                                             data_count=int(BLS.get('firsttx_data_count', 200)),
                                                             is_dict=True) or {}, budget='tx') or {}
        if not raw or not raw.get('fields'):
            return raw
        if not BLS.get('l2_tx_fallback_enabled', True):
            return raw
        try:
            miss = [s for s in secs if not raw.get(s)]
            if not miss:
                return raw
            cap = int(BLS.get('l2_tx_fallback_cap', 5))
            fields = list(raw.get('fields') or [])
            _fb = 0
            for c in miss:
                if _fb >= cap or not self.spend('tx'):
                    break
                _fb += 1
                try:
                    one = get_individual_transaction([c],
                                                     data_count=int(BLS.get('firsttx_data_count', 200)),
                                                     is_dict=True) or {}
                    rows = one.get(c) if isinstance(one, dict) else one
                    if not rows:
                        continue
                    f2 = one.get('fields') if isinstance(one, dict) else None
                    if f2 and fields and list(f2) != fields:
                        _i2 = {n: i for i, n in enumerate(f2)}
                        rows = [[row[_i2[n]] if n in _i2 and _i2[n] < len(row) else None
                                 for n in fields] for row in rows if isinstance(row, (list, tuple))]
                    elif f2 and not fields:
                        fields = list(f2)
                        raw['fields'] = fields
                    raw[c] = rows
                except Exception:
                    self.degraded.add('tx')
            if _fb:
                log.info('[tx-pull] req=%d got=%d missing=%d (fallback=%d)' % (len(secs), len(secs) - len(miss), len(miss), _fb))
        except Exception as e:
            _warn('tx_pull fallback fail %r' % e)
        return raw

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


def _fast_window():
    # v1.36 快速刷新窗口：开盘 30 分钟（09:30-10:00）+ 下午开盘 30 分钟（13:00-13:30）。
    # 消费端：帧预算 fast 档、板块强度 TTL、全市场红盘 TTL、跌停题材 TTL、午后 scan/首板成员采集。
    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            return True
    except Exception:
        pass
    try:
        hm = _hhmm()
        a = str(BLS.get('pm_fast_after_hhmm', '13:00') or '13:00')
        u = str(BLS.get('pm_fast_until_hhmm', '13:30') or '13:30')
        return bool(a <= u and a <= hm < u)
    except Exception:
        return False


def _source_limit(source, prio=0):
    # 帧预算限额解析（v0.36）：10:00 前走 _fast 档（对齐 _board_refresh_ttl 快速期）；prio=1 走独立高优先级配额。
    # gear 快速期无 _fast 键时动态按 tick 目标集数量（min(len(_tick_targets), 25)），防 watch 池大时 L2 封单采集缺。
    fast = _fast_window()
    # v1.35 尾盘（14:45 后）非核心 board/hist1d 暂停刷新：预算留给首触/封单/snapshot/tx
    try:
        if not prio and source in ('board', 'hist1d') \
                and _hhmm() >= str(BLS.get('budget_tail_idle_after_hhmm', '14:45') or '14:45'):
            return 0.0
    except Exception:
        pass
    if prio:
        k = 'frame_%s_prio_limit_fast' % source
        if fast and k in BLS and BLS[k]:
            return float(BLS[k])   # v1.20 10:00 前高优先级独立配额放大（核心/预期票日线）
        if not fast:
            ka = 'frame_%s_prio_limit_afternoon' % source   # v1.35 10:00 后高优先级午盘降频
            if ka in BLS and BLS[ka]:
                return float(BLS[ka])
        return float(BLS.get('frame_%s_prio_limit' % source,
                             BLS.get('frame_%s_limit' % source, 1e9)))
    if fast:
        k = 'frame_%s_limit_fast' % source
        if k in BLS and BLS[k]:
            return float(BLS[k])
        if source == 'gear':
            try:
                return float(min(len(_tick_targets()), 25))
            except Exception:
                pass
    if not fast:
        ka = 'frame_%s_limit_afternoon' % source   # v1.35 10:00 后普通配额午盘降频
        if ka in BLS and BLS[ka]:
            return float(BLS[ka])
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
    g.daily = _new_daily()
    g.state_day = None   # 持久化的“交易日”戳（跨重启每日买入计数恢复）
    g.spot = {}; g.last_ma5 = {}
    g.ma5_touch_day = None; g.ma5_touched = set()   # v0.69 当日首次触 MA5 去重
    g.ma5_lifecycle_day = None; g.ma5_lows = {}     # v0.70 当日生命周期最低两价
    g.ma5_pending = set()                            # v1.21 MA5 日线未就绪待补评
    _get_ds()  # DataHub singleton warmup (kept out of g)
    g.one_word_open = set()   # 09:25/开盘识别的一字板（买入不排队）
    g.one_word_marked_open = False   # v0.42 09:30 首帧补标去重（按日重置）
    g.rt_stats = {}   # v0.43 灵敏度日结采样（检测->下单时延，after_trading_end 打 [rt-summary]）
    g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}   # v0.47 L2 大单累计 / v0.51 方向分布 / v0.52 播种水印 / v0.67 入池播种+探针节流 / v0.73 VWAP 弱化确认（均按日重置）
    g.hist = {}         # sec -> (ts, df)  1d 历史缓存
    g.bs_codes = {}     # sec -> (ts, 板块成分代码)（首板闸门：板块内涨幅最高）
    g.first_board_fired = set()  # 首板打板当日去重（tick 首触 / 1m 兜底共用）
    g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}   # 弹性套利：板块一字板统计缓存（60s，按日重置）
    g.elastic_top = {'day': '', 'top': '', 'ts': 0.0, 'tracked': set()}  # v0.36 新最强板块弹性跟踪状态
    g.gear_cache = {}     # sec -> (ts, get_gear_price)  L2 十档帧级缓存
    g.m1_surge_cache = {} # sec -> (ts, 1m大阳线%)        弹性窗口缓存
    g.now_dt = None     # 当前 bar 时间（context.blotter.current_dt，回测/交易均可用）
    g.bar_counter = 0
    g.vwap_below_since = {}  # sec -> 连续低于VWAP计时起点(_sec_age值)；高于VWAP即移除(恢复归零)
    g.vwap_track = {}     # v1.26 A 扫板分时均价跟随帧跟踪（sec -> {vwap,cnt,ts}）

    g.pool_all = []     # 全市场 A 股代码（按交易日刷新）
    g.pool_day = None
    g.watch = []        # 入池候选（动态，买入/打分迭代目标）
    g.near_scan = {}    # v0.74 sec -> {'ts','round','chg'} 近涨停快速通道（scan 命中后跨轮保留）
    g.scan_order = []   # v0.74 每日扫描顺序（开盘 10 分钟热点优先）
    g.scan_order_day = None
    g.scan_round = 0    # v0.74 扫描轮次计数（near_scan 清理用）
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
    g.first_zt_rebuild_pending = []   # v0.75 同日重启待重建首触队列（tick 帧分批消化）
    g.first_zt_rebuild_retry_ts = {}  # v0.75 重建失败逐票重试节流（防每帧重复拉 API）
    g.first_zt_rebuild_ts = {}        # v0.80 重建入队时间戳（v1.5 起仅留痕，不参与放弃判定）
    g.first_zt_rebuild_attempts = {}  # v1.5 重建实际尝试轮次（放弃判定基准）
    g.first_zt_rebuild_zt_seen = {}   # v1.12 重建尝试中是否见过涨停价成交（区分未涨停/回看失败）
    g.restart_rebuild_hb_ts = 0.0     # v0.76 重建进度 heartbeat 节流时间戳
    g.skip_log_ts = {}                # v0.80 同因日志节流表 (tag|sec|reason)->ts
    g.score_na_pending = {}           # v1.12 评分未就绪待恢复票（数据就绪后补评并打 [score-recover]）
    g.hist_recover_once = {}          # v1.22 (tag|day|sec) -> ts 恢复日志当日去重（补拉不刷重复行）
    g.firstzt_log_ts = {}             # v1.22 反复炸板/回封日志节流表 sec->ts
    g.bought_qty = {}                 # v1.22 当日买入成交累计 sec->qty（桥 enable 未回填审计基准）
    g.t1_pending_sell = {}            # v1.30 T+1 当日买入保护触发持久化（记录不卖单，次日复核）
    g.t1_pending_log_ts = {}          # v1.30 [t1-protect] 落盘/日志节流 sec->ts
    g.t1_pending_save_ts = 0.0        # v1.30 [t1-protect] 落盘全局节流时间戳
    g.t1_pending_cnt = {}             # v1.35 [t1-protect] 心跳计数（完整行后累计）
    g.seal_low_tail_log_ts = {}       # v1.35 尾盘 SEAL_LOW_FAST 同票日志节流 sec->ts
    g.pos_raw_dump_log = {}           # v1.35 [pos-dump] 持仓原始字段当日去重 sec->set(day)
    g.tx_lag_stats = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}   # v1.35 逐笔延迟日终汇总
    g.budget_over_peak = {}           # v1.35 预算超限峰值 source->max over（日终 [budget-over-summary]）
    g.first_zt_rebuild_zt_hit = {}    # v1.35 重建回看涨停价成交累计 sec->count
    g.first_zt_rebuild_gave_up = set()  # v1.35 重建放弃名单（后续 tick 补建时打 rebuilt_later）
    g.auction_confirm_log = {}        # v1.32 三态逐票 [auction-confirm] 幂等去重 (day|sec|status|src)->ts
    g.sweep_a_ld_buy = {}             # v1.32 扫板A买入时题材跌停快照（T+1 次日复核优先标记）
    g.dyn_unq_pool_cache = {}         # v1.30 动态唯一主题比较池缓存（15s）
    g.pos_cap_skips = 0               # v1.12 情绪仓位闸门当日拦截次数（skip 日志带 total）
    g.pos_cap_shrinks = 0             # v1.17 情绪仓位闸门当日缩量次数（shrink 日志带 total）
    g.sell_skip_cnt = {}              # v1.12 [sell-skip] 60s 窗口内重复计数
    g.order_limit_src = ''            # v1.12 最近一次 _order_limit 限价来源（sell2/pct/board/px/sell）
    g.last_save_ts = 0.0              # v0.75 盘中定期保存节流时间戳
    g.cash_baseline = 0.0             # v1.13 开盘资金基线（09:25 前后真实正现金，未就绪窗口兜底）
    g.cash_baseline_ts = 0.0          # v1.13 资金基线缓存时间戳
    g.cash_src = 'real'               # v1.13 当前资金来源（real/baseline）
    g.cash_src_logged = 'real'        # v1.13 [cash-src] 切换日志节流
    g.last_board_cancel_reconcile_ts = 0.0  # v1.13 撤单失败兜底对账节流
    g.last_no_reply_reconcile_ts = 0.0      # v1.13 无回报兜底对账节流
    g.pos_stale_log = set()           # v1.13 [pos-stale] 桥持仓残留一次性日志
    g.st_set = set(); g.st_day = None # v0.75 ST 名单按交易日缓存（名称兜底）
    g.st_skip_log_ts = 0.0            # v0.75 [st-skip] 日志节流
    g.dyn_unq = None    # v0.38 盘中动态唯一+跟风+扫板状态（按日重置，随 g 持久化）
    g.break_sold = set()  # sec -> 炸板事件卖出首触发标记（v0.26，跨重启持久化）
    g.seal_sold = set()   # sec -> 封单大减事件卖出首触发标记（v0.26）
    g.break2_sold = set() # sec -> 二次炸板减半卖出标记（v0.49，跨重启持久化）
    g.board_cancel_log = set()  # v1.6 打板排单封单衰减撤单去重（按日）
    g.reboard_fired = False  # 回封打板每日全局 1 次标记（v0.49）
    g.sealed_since = {}   # sec -> 封死状态持续计时起点（v0.26b，5s 新鲜度确认）
    g.zt_lianban = {}   # sec -> T-1 涨停/连板名单（AXquant limit_up_boards 导出, upload_file）
    g.zt_theme_authoritative = False  # v0.38 文件带权威题材列（theme.buckets 同源）-> 兜底分组用题材
    g.zt_theme = {}        # v0.55 静态锚：theme -> {members,max_board,count,rank}（themes 全量建组）
    g.zt_themes_of = {}    # v0.55 code -> [theme names]（themes 全量，交叉题材不漏归）
    g.zt_dyn_cache = {}    # v0.55 盘中动态题材状态缓存 {'ts','data'}
    g.zt_new_cache = {}    # v0.56 新首板题材归属缓存 {'ts','data'}（THS 概念 -> 题材桶桥接）
    g.zt_ferment_cache = {}  # v0.56 盘中新题材发酵状态缓存 {'ts','data'}
    g.zt_ferment_stage = {}  # v0.56 发酵档位上一值（stage 变化才打日志）
    g.zt_unmapped_n = 0    # v0.57 无概念映射新首板计数（变化才打日志）
    g.lb_senti = {}        # v0.65 连板盘中情绪动态 {auction, mid, t100}
    g.lb_senti_cache = {}  # v0.65 盘中确认滚动缓存 {'ts','data'}
    g.senti_hist = None    # v1.31 云端近期情绪温度历史（独立 sentiment_hist.pkl，10 个交易日）
    g.senti_stage_cache = None   # v1.31 阶段判定 15s 缓存（避免 3s tick 重复计算）
    g.senti_stage_sell_log = {}  # v1.31 阶段后排卖出日志节流（按 sec+round 一次）
    g.exp_file = {}     # sec -> 预期文件条目（AXquant 竞价终态）
    g.hist_prio_cache = {}   # v1.16 核心/预期日线优先集缓存 {'tok','set'}
    g.hist_na_pending = {}   # v1.16 百日新高日线缺失待重评 {'sec': ts}
    g.exp_fired = set() # sec -> 本日已触发(买/放弃)的预期买入（一次触发+跨重启去重）
    g.pending = {}      # sec -> 已发送委托（成交确认前的去重/回执）
    g.buy_commit = {}   # v0.64 在途买单占用资金(现价×量，防6s资金同步滞后超配)；终态回报释放
    g.p7a_sold = set()    # v0.59 P7a 连板放量不封板 卖出首触发标记（跨重启持久化）
    g.p7b_sold = set()    # v0.59 P7b 跟风拉升不封板 卖出首触发标记（跨重启持久化）
    g.p7c_part = {}       # v0.59 P7c 首板次日不主动冲板 标记（price/half/sold1_ts）
    g.p7c_sold = set()    # v0.59 P7c 分批清仓完成标记（跨重启持久化）
    g.p7d_sold = set()    # v1.19 P7d 核心冲高偏离 卖出首触发标记（跨重启持久化）
    g.p6_weak = {}        # v1.20 P6 两帧确认计数 {sec: {cnt, ts, score}}（跨重启持久化，跨日清空）
    g.hold_stand_cache = {}  # v0.59 持仓地位评估缓存（15s 节流，不持久化）
    g.hold_stand_log = {}    # v0.59 持仓地位日志节流（60s/股，不持久化）
    run_daily(context, auction_pre_confirm, time='09:25')
    run_daily(context, lb_senti_auction_retry, time='09:26')   # v1.16 竞价情绪未就绪补拉
    run_daily(context, ld_senti_auction, time='09:25')   # v1.24 竞价终态跌停快照
    run_daily(context, ld_senti_open, time='09:30')      # v1.24 开盘跌停快照
    run_daily(context, after_open_probe, time='09:31')
    run_daily(context, lb_senti_t100_freeze, time='10:00')   # v0.65 10:00 情绪冻结快照（之后降频监控不归零）
    run_daily(context, mid_probe, time='11:00')
    run_interval(context, p2e_auction_core_sell, seconds=3, interval_timer_ranges='09:15-09:25')   # v0.58 P2E 竞价核卖（9:24:45 确认段）
    log.info('buysell_core init version=%s universe=%s DO_ORDER=%s EXPECT_ORDER=%s sim_cash=%s' % (STRATEGY_VERSION, _snl(BLS['universe']), BLS['DO_ORDER'], BLS.get('EXPECT_ORDER', False), BLS.get('sim_cash_base', 0.0)))


def before_trading_start(context, data):
    _set_now(context)
    load_state()
    _cache_cash_baseline(context)   # v1.13 开盘前缓存资金基线（09:25 会再刷新）
    _today = str(get_trading_day())
    _restart_same_day = False
    if getattr(g, 'state_day', None) == _today:
        _restart_same_day = True
        # 同日盘中重启：保留当日已买计数（跨重启恢复），sold 本就每日清
        _old_daily = dict(g.daily or {})
        g.daily = _new_daily()
        for _k in ('bought', 'bought_board', 'bought_exp_chase', 'bought_ma5',
                   'bought_core', 'bought_elastic_arb', 'bought_elastic_top',
                   'bought_other', 'legacy_other'):
            g.daily[_k] = [x for x in (_old_daily.get(_k) or [])]
        g.daily['bought_kind'] = dict(_old_daily.get('bought_kind') or {})
        g.daily['sold'] = []
        log.info('before_trading_start restore same-day daily=%s (restart)' % (_snl(g.daily.get('bought')),))
    else:
        g.daily = _new_daily()
        g.exp_fired = set()   # 跨日清空预期买入触发
        g.buy_commit = {}     # 跨日清空在途买单承诺
    # v1.3 防御兜底：load_state 已按 first_zt_day/记录 day 清跨日残留，这里再兜一次，
    # 防状态文件异常路径把昨日首触带进当日（2026-10-28 09:30 旧池票 BREAK held≈86k s 根因）。
    _fz_now = getattr(g, 'first_zt', None) or {}
    _stale_fz = [c for c, r in _fz_now.items() if str((r or {}).get('day') or '') != _today]
    if _stale_fz:
        log.info('[restart-guard] before_trading_start 发现跨日 first_zt %d 家 -> 清空重建' % len(_stale_fz))
        g.first_zt = {}
        g.auction_c = {}
    elif not _restart_same_day and _fz_now:
        log.info('[restart-guard] 跨日分支内存残留 first_zt %d 家 -> 清空' % len(_fz_now))
        g.first_zt = {}
        g.auction_c = {}
    g.sealed_warn = set()
    g.state_day = _today
    try:
        _reconcile_pending()   # v0.64 重启对账：get_open_orders 补齐在途委托（防重复卖/资金扣减）
    except Exception:
        pass
    if _restart_same_day:
        try:
            _reconcile_daily_bought_slots()   # v1.5 同日重启：交叉核对释放未成交占坑（海洋王类挂单）
        except Exception:
            pass
    _save_state()
    _load_expectation(merge=_restart_same_day)   # v1.5 同日重启 merge，配合 exp_file 持久化防 34->5 收缩
    _load_zt_lianban()
    _load_sentiment()
    _senti_hist_load()   # v1.31 加载云端近期情绪温度历史（独立文件，损坏降级不阻塞）
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
        if _hhmm() >= '09:25':
            g.exp_day = _today   # v0.53 同日重启(09:25后)：保留盘中状态，首帧日切不再清空（09:31 前仍走 09:25/09:31 重建兜底）
        try:
            _synth_pool_expect(src='restart_rebuild')        # v0.36g 盘中重启：重建涨停池三态（防 expect_buy 45->12 丢失）
            _synth_selfwatch_expect(src='restart_rebuild')   # v0.36g 盘中重启：重建自选股三态
            _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
        except Exception:
            pass
        try:
            _mark_one_word_open()   # v0.31c 盘中重启：重标一字板（免5s门槛不丢）
            _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])), pages=int(BLS.get('l2_tickdir_pages_restart', 10)))   # v0.52a 重启补种加大页数（覆盖9:30-10:30活跃窗口至09:25竞价）
            _rebuild_first_zt_queue()   # v0.75 重启登记缺失 first_zt（tick 帧分批重建，防下午补 first/tx_ms 失真）
            _hist1d_restart_warm('restart')   # v1.22 同日重启日线冷缓存恢复（positions/exp buy/CORE 优先）
        except Exception:
            pass
    for sec in list(dict.fromkeys(BLS['universe'] + list(get_positions()))):
        _ma5_base4(sec)
    log.info('before_trading_start done positions=%s' % list(get_positions()))


def _maybe_roll_day():
    # v0.53 日切统一入口：返回是否发生日切。同日重启后 exp_day 已持久化/恢复 -> 首帧不再清空盘中事件状态
    # （break_sold/seal_sold/first_zt/seal_base/one_word_open/l2_big/l2_big_wm 等，防重复卖出/播种丢失）。
    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) == day:
        return False
    g.exp_day = day
    g.ma5_touch_day = day; g.ma5_touched = set()
    g.ma5_lifecycle_day = day; g.ma5_lows = {}; g.ma5_pending = set()
    g.hist_prio_cache = {}; g.hist_na_pending = {}
    g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.break2_sold = set(); g.board_cancel_log = set(); g.reboard_fired = False; g.sealed_since = {}; g.gear_cache = {}; g.m1_surge_cache = {}; _get_ds().reset(); g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}; g.zt_ferment_stage = {}; g.zt_unmapped_n = 0; g.lb_senti = {}; g.lb_senti_cache = {}
    g.near_scan = {}; g.scan_order = []; g.scan_order_day = None; g.scan_round = 0; g.scan_offset = 0; g.vwap_track = {}   # v0.74/v1.26 跨日重置近涨停通道与扫板均价跟踪
    g.tick_near_evt = {}; g.tick_buy_event_seen = {}   # v1.34 同帧事件去重跨日重置
    g.first_zt_rebuild_pending = []; g.first_zt_rebuild_retry_ts = {}; g.first_zt_rebuild_ts = {}; g.first_zt_rebuild_attempts = {}; g.first_zt_rebuild_zt_seen = {}; g.first_zt_rebuild_zt_hit = {}; g.first_zt_rebuild_gave_up = set(); g.restart_rebuild_hb_ts = 0.0; g.last_save_ts = 0.0; g.st_skip_log_ts = 0.0; g.skip_log_ts = {}; g.budget_log_ts = 0.0; g.budget_over_acc = {}; g.budget_over_peak = {}; g.budget_deg_logged = set(); g.score_na_pending = {}; g.pos_cap_skips = 0; g.pos_cap_shrinks = 0; g.sell_skip_cnt = {}; g.order_limit_src = ''; g.sell_retry_cnt = {}; g.auction_confirm_log = {}; g.sweep_a_ld_buy = {}   # v0.75/76/80/81/1.5 + v1.12/1.15 + v1.32 + v1.35 跨日重置
    g.t1_pending_cnt = {}; g.seal_low_tail_log_ts = {}; g.pos_raw_dump_log = {}; g.tx_lag_stats = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}   # v1.35 跨日重置
    g.hist_recover_once = {}; g.firstzt_log_ts = {}; g.bought_qty = {}   # v1.22 跨日重置恢复日志去重/炸板日志节流/买入成交累计
    return True


def _budget_log():
    # v0.81 [budget] 日志节流：常规摘要 60s 心跳（首帧立即）；帧内 over/degraded 事件行优先（同因按
    # budget_log_event_sec 去重）；心跳附带窗口累计 over_w<window>s（打印后清零）；总开关 budget_log_enabled。
    try:
        if not BLS.get('budget_log_enabled', True):
            return
        _dh = _get_ds()
        rep = _dh.frame_report()
        over = _dh.frame.get('over') or {}
        deg = list(_dh.degraded)
        acc = getattr(g, 'budget_over_acc', None)
        if not isinstance(acc, dict):
            acc = {}; g.budget_over_acc = acc
        pk = getattr(g, 'budget_over_peak', None)   # v1.35 日终峰值汇总
        if not isinstance(pk, dict):
            pk = {}; g.budget_over_peak = pk
        for _k, _n in over.items():
            acc[_k] = float(acc.get(_k, 0.0) or 0.0) + float(_n or 0)
            pk[_k] = max(float(pk.get(_k, 0.0) or 0.0), float(_n or 0))
        ev = False
        if BLS.get('budget_log_on_over', True) and over:
            ev = True
            _skip_log('budget', 'over', 'frame', '[budget] %s' % rep, throttle_sec=BLS.get('budget_log_event_sec', 30.0))
        if BLS.get('budget_log_on_degraded', True) and deg:
            logged = getattr(g, 'budget_deg_logged', None)
            if logged is None:
                logged = set(); g.budget_deg_logged = logged
            new_deg = [x for x in deg if x not in logged]
            if new_deg:
                logged.update(new_deg)
                ev = True
                _skip_log('budget', 'degraded', 'frame', '[budget] %s degraded:%s' % (rep, ','.join(str(x) for x in new_deg[:5])), throttle_sec=BLS.get('budget_log_event_sec', 30.0))
        if ev:
            g.budget_log_ts = time.time()   # v0.81 事件行即心跳基准（防事件后下一帧立即补打常规摘要）
            return
        hb = float(BLS.get('budget_log_heartbeat_sec', 60.0) or 0.0)
        if hb <= 0:
            return
        now = time.time()
        if now - float(getattr(g, 'budget_log_ts', 0.0) or 0.0) < hb:
            return
        g.budget_log_ts = now
        extra = ''
        if acc:
            extra = ' over_w%.0fs:%s' % (hb, ','.join('%s=%d' % (k, int(v)) for k, v in sorted(acc.items())))
            acc.clear()
        log.info('[budget] %s%s' % (rep, extra))
    except Exception:
        pass


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
    if _maybe_roll_day():
        for sec in list(get_positions()):
            _hold_exp_init(sec, force=True)   # v0.32 跨日重算持仓预期条目
    try:
        if BLS.get('restart_rebuild_1m_enabled', True):
            _rebuild_first_zt_tick()   # v0.76 1m 兜底：tick 禁用/丢帧仍消化重启重建队列
    except Exception as _e:
        _warn('restart-rebuild(1m) fail: %r' % _e)
    try:
        _score_recover_probe()   # v1.12 评分未就绪恢复探针（1m 帧末）
    except Exception:
        pass
    try:
        _t1_protect_consume(context)   # v1.30 T+1 次日复核（1m 兜底）
    except Exception as _e:
        _warn('t1 protect consume fail %r' % _e)
    sell_manager(context)
    try:
        _board_queue_cancel_scan()   # v1.6 打板排单封单衰减撤单（1m 兜底；tick 帧内另有逐票检查）
    except Exception as _e:
        _warn('board queue cancel(1m) fail: %r' % _e)
    try:
        _board_cancel_reconcile()   # v1.13 撤单失败兜底对账（60s 节流）
        _no_reply_reconcile()       # v1.13 无回报兜底对账（60s 节流）
    except Exception as _e:
        _warn('order reconcile(1m) fail: %r' % _e)
    _try_expected_buys(context)
    _now = time.time()
    if _now - float(getattr(g, 'last_save_ts', 0.0) or 0.0) >= float(BLS.get('state_save_interval', 60.0)):
        g.last_save_ts = _now
        _save_state()   # v0.75 盘中定期保存：重启恢复到分钟级而非事件级
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
    try:
        _try_new_theme_sweep(context)    # v1.26 A 新题材首板扫板（1m 兜底）
    except Exception as e:
        _warn('new_theme_sweep(1m) fail: %r' % e)
    try:
        _try_pm_theme_buy(context)       # v1.36 午后新题材前排试点（1m 兜底）
    except Exception as e:
        _warn('pm_theme buy(1m) fail: %r' % e)
    try:
        _lb_senti_mid()                  # v0.65 连板盘中情绪状态机（1m 兜底，15s/60s 缓存节流）
    except Exception as e:
        _warn('lb_senti(1m) fail: %r' % e)


# ================= 行情/工具 =================
def _hist1d_ttl(prio):
    # v1.32 预温保活：10:05 前核心/预期票日线 TTL 放大到 600s，
    # 09:25/09:31 预温结果续期不中途失效（10:05 后回落常规 TTL）
    try:
        ttl = float(BLS.get('hist1d_core_ttl', 180.0) or 180.0) if prio == 1 else 60.0
        if prio == 1 and BLS.get('hist1d_prewarm_ttl_enabled', True) \
                and _hhmm() < str(BLS.get('hist1d_prewarm_until_hhmm', '10:05')):
            ttl = max(ttl, float(BLS.get('hist1d_prewarm_ttl', 600.0) or 600.0))
        return ttl
    except Exception:
        return float(BLS.get('hist1d_core_ttl', 180.0) or 180.0) if prio == 1 else 60.0


def _hist_1d(sec, prio=0, ttl=None):
    # 1d OHLCV 缓存（统一 DataHub 注册表；ttl 覆盖时按调用方口径，默认走 _hist1d_ttl）
    try:
        dh = _get_ds()
        ttl = ttl if ttl is not None else _hist1d_ttl(prio)
        return dh.cached('hist1d', sec, ttl,
                         lambda: get_price(sec, start_date=None, end_date=None, count=120, frequency='1d'),
                         budget='hist1d', prio=prio)
    except Exception:
        return None


def _hist_prio_set():
    # v1.16 核心/预期票日线优先集：5s token 缓存，避免每票高频 get_positions
    try:
        tok = int(time.time() / 5.0)
        c = getattr(g, 'hist_prio_cache', None)
        if isinstance(c, dict) and c.get('tok') == tok:
            return c.get('set') or set()
        pos = set(get_positions())
        buy = set(c for c, en in (getattr(g, 'exp_file', {}) or {}).items()
                  if str((en or {}).get('side') or '') == 'buy')
        core = set(c for c, rec in (getattr(g, 'zt_lianban', {}) or {}).items()
                   if int((rec or {}).get('board_cnt') or 0) >= 3)
        s = pos | buy | core
        g.hist_prio_cache = {'tok': tok, 'set': s}
        return s
    except Exception:
        return set()


def _is_hist_priority(sec):
    # v1.16 exp buy/持仓/CORE 优先拉取日线，保证 09:30 首帧 BS/MA5 不缺基准
    try:
        return str(sec or '') in _hist_prio_set()
    except Exception:
        return False


def _hist_na_pending_add(sec):
    # v1.16 百日新高日线缺失记录，供恢复探针重评，不静默当“非新高”
    try:
        hp = getattr(g, 'hist_na_pending', None)
        if not isinstance(hp, dict):
            hp = {}; g.hist_na_pending = hp
        hp[sec] = time.time()
        _skip_log('hist_na', sec, 'hist1d_na',
                  '[hist-na] %s hist1d 缺失 prio=%d -> 待重评' % (_sn(sec), 1 if _is_hist_priority(sec) else 0))
    except Exception:
        pass


def _hist1d_prewarm(tag='09:25'):
    # v1.16 09:25/09:31 核心日线预暖：只用高优先级独立配额，不阻塞主流程
    # v1.18 记录前轮 ok 名单，输出“前轮 ok 本轮 miss”的回归票数/样本，缓解 46/46 -> 15/46 掉链审计缺口
    try:
        if not BLS.get('hist1d_prewarm_enabled', True):
            return 0
        codes = list(dict.fromkeys([x for x in (_pool() + list(get_positions())
                                                + list((getattr(g, 'exp_file', {}) or {}).keys())
                                                + list((getattr(g, 'zt_lianban', {}) or {}).keys()))
                                    if x and _is_hist_priority(x)]))
        ok = 0
        ok_codes = []
        miss = []
        for sec in codes:
            # v1.32 预温直接用 600s TTL 拉取，09:25/09:31 结果保留到 10:05
            if _hist_1d(sec, prio=1, ttl=float(BLS.get('hist1d_prewarm_ttl', 600.0) or 600.0)) is not None:
                ok += 1
                ok_codes.append(sec)
                _ma5_base4(sec)   # v1.21 预温一并缓存 MA5 base4，09:25 起即可动态 MA5
            else:
                miss.append(sec)
        prev_ok = set(getattr(g, 'hist1d_prewarm_prev_ok', None) or [])
        regressed = sorted(set(miss) & prev_ok)
        for sec in miss:
            _hist_na_pending_add(sec)   # v1.20 预暖 miss 交给恢复探针按 prio=1 续拉，不再只打日志
        g.hist1d_prewarm_prev_ok = set(ok_codes)
        log.info('[hist1d-prewarm] %s core=%d ok=%d miss=%d regress_from_prev=%d miss_sample=%s' % (
            tag, len(codes), ok, len(miss), len(regressed), _snl(miss[:10])))
        return ok
    except Exception:
        return 0


def _hist1d_restart_warm(tag='restart'):
    # v1.22 同日重启冷缓存恢复：优先 positions + exp buy + CORE，受高优先级日线配额
    # frame_hist1d_prio_limit_fast 控制（超配额返回 None，转 hist_na_pending 由恢复探针续拉）。
    try:
        if not BLS.get('hist1d_restart_warm_enabled', True):
            return 0
        codes = list(dict.fromkeys([x for x in (
            list(get_positions())
            + [c for c, en in (getattr(g, 'exp_file', {}) or {}).items()
               if str((en or {}).get('side') or '') == 'buy']
            + [c for c, rec in (getattr(g, 'zt_lianban', {}) or {}).items()
               if int((rec or {}).get('board_cnt') or 0) >= 3])
            if x]))
        cap = max(1, int(BLS.get('hist1d_restart_warm_cap', 40) or 40))
        ok = 0
        miss = []
        for sec in codes[:cap]:
            if _hist_1d(sec, prio=1) is not None:
                ok += 1
                _ma5_base4(sec)
            else:
                miss.append(sec)
        overflow = codes[cap:]
        for sec in miss + overflow:
            _hist_na_pending_add(sec)
        log.info('[hist1d-restart-warm] %s core=%d ok=%d miss=%d overflow=%d miss_sample=%s' % (
            tag, len(codes), ok, len(miss), len(overflow), _snl((miss + overflow)[:10])))
        return ok
    except Exception:
        return 0


def _date_key(v):
    # 日线索引兼容 Timestamp/date/'YYYY-MM-DD'/'YYYYMMDD'
    try:
        fn = getattr(v, 'date', None)
        if callable(fn):
            v = fn()
        s = str(v)
        if len(s) >= 10 and s[4:5] == '-' and s[7:8] == '-':
            return s[:10]
        if len(s) >= 8 and s[:8].isdigit():
            return '%s-%s-%s' % (s[:4], s[4:6], s[6:8])
    except Exception:
        pass
    return ''


def _ma5_base4(sec):
    # v0.69 盘中 MA5=最近4个已完成日收盘均值×4/5 + 当前价/5。
    # get_price 日线通常不含当日；若数据源把未完成日线放在末行，则按索引日期剔除。
    day = str(get_trading_day())
    cache = getattr(g, 'last_ma5', None)
    if not isinstance(cache, dict):
        cache = {}; g.last_ma5 = cache
    rec = cache.get(sec)
    if isinstance(rec, dict) and rec.get('day') == day:
        return float(rec.get('base4') or 0.0)
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
    if df is None:
        return None
    try:
        closes = [float(x) for x in list(df['close'])]
    except Exception:
        return None
    if len(closes) < 5:
        return None
    last_is_today = False
    try:
        last_is_today = (_date_key(df.index[-1]) == day)
    except Exception:
        pass
    vals = closes[-5:-1] if last_is_today else closes[-4:]
    if len(vals) < 4 or any(v <= 0 for v in vals):
        return None
    base4 = sum(vals) / 4.0
    cache[sec] = {'day': day, 'base4': base4}
    return base4


def _ensure_ma5(sec):
    # 动态 MA5 必须含当前价；避免盘前静态值在盘中一路不变。
    base4 = _ma5_base4(sec)
    px = last_px(sec)
    if not base4 or not px or px <= 0:
        return None
    return (base4 * 4.0 + float(px)) / 5.0


def _ma5_at_price(sec, px):
    # 给定价格作为今日临时收盘价，计算该时点动态 MA5。
    base4 = _ma5_base4(sec)
    try:
        px = float(px)
    except Exception:
        return None
    if not base4 or px <= 0:
        return None
    return (float(base4) * 4.0 + px) / 5.0


def _ma5_second_low(sec, px):
    # v0.70 记录当日生命周期内最低两个价格；次低价=两者中较高者。
    # 至少两个样本后才返回；状态按交易日重置并随同日重启恢复。
    cache = getattr(g, 'ma5_lows', None)
    if not isinstance(cache, dict):
        cache = {}; g.ma5_lows = cache
    try:
        px = float(px)
    except Exception:
        return None
    if px <= 0:
        return None
    vals = []
    for v in (cache.get(sec) or []):
        try:
            v = float(v)
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    vals.append(px)
    vals.sort()
    vals = vals[:2]
    cache[sec] = vals
    return vals[1] if len(vals) >= 2 else None


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
def _spot_ready(sec):
    # v0.68 评分就绪门：现价与前收齐备（盘中重启首帧常缺 preclose -> 不评估，防虚高打分）
    s = g.spot.get(sec) or {}
    px = float(s.get('last_px') or 0.0)
    pre = float(s.get('preclose_px') or 0.0)
    return px > 0 and pre > 0


def _score_na_log(sec, why):
    # v0.68 评分未就绪节流日志（60s/票）：重启首帧缺数据不静默也不刷屏
    try:
        gl = getattr(g, 'score_na_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.score_na_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0.0) < 60.0:
            return
        gl[sec] = now
        log.info('[score-na] %s data_na(%s) -> 评分未就绪(不评估买入)' % (_sn(sec), why))
    except Exception:
        pass


def _score_na_pending_add(sec):
    # v1.12 记录评分未就绪待恢复票；v1.16 核心/预期票带 prio 先恢复
    try:
        sp = getattr(g, 'score_na_pending', None)
        if not isinstance(sp, dict):
            sp = {}; g.score_na_pending = sp
        sp[sec] = {'ts': time.time(), 'prio': 1 if _is_hist_priority(sec) else 0}
    except Exception:
        pass


def _hist_recover_logged(tag, sec):
    # v1.22 恢复日志当日去重：同一 (tag, day, sec) 当日只打一次；TTL 失效补拉仍执行，只抑制重复日志
    try:
        if not BLS.get('score_recover_dedup_enabled', True):
            return False
        d = getattr(g, 'hist_recover_once', None)
        if not isinstance(d, dict):
            d = {}; g.hist_recover_once = d
        key = '%s|%s|%s' % (tag, str(get_trading_day()), sec)
        if key in d:
            return True
        d[key] = time.time()
        return False
    except Exception:
        return False


def _ma5_pending_probe():
    # v1.21 MA5 日线未就绪待补评：hist 恢复后补算 base4 并清除待办，区分“无数据”与“未触线”
    try:
        pending = getattr(g, 'ma5_pending', None)
        if not isinstance(pending, set):
            pending = set(pending or []); g.ma5_pending = pending
        if not pending:
            return
        cap = max(1, int(BLS.get('score_recover_probe_cap', 20) or 20))
        jobs = sorted(pending, key=lambda x: (0 if _is_hist_priority(x) else 1, x))
        for sec in jobs[:cap]:
            base4 = _ma5_base4(sec)
            if base4 is None:
                continue
            pending.discard(sec)
            if not _hist_recover_logged('ma5', sec):
                log.info('[ma5-recover] %s MA5 日线恢复 base4=%.2f' % (_sn(sec), base4))
    except Exception:
        pass


def _score_recover_probe():
    # v1.12/v1.16 [score-na]/[hist-na] 恢复探针：数据就绪后补评，核心优先、10:00 前扩容
    try:
        now = time.time()
        if not _lb_senti_t100_passed():
            cap = max(1, int(BLS.get('score_recover_probe_cap_fast', 40) or 40))
        else:
            cap = max(1, int(BLS.get('score_recover_probe_cap', 20) or 20))
        pending = getattr(g, 'score_na_pending', None)
        if not isinstance(pending, dict):
            pending = {}; g.score_na_pending = pending
        hist_pending = getattr(g, 'hist_na_pending', None)
        if not isinstance(hist_pending, dict):
            hist_pending = {}; g.hist_na_pending = hist_pending
        jobs = []
        for sec, v in list(pending.items()):
            if isinstance(v, dict):
                ts = float(v.get('ts') or 0.0)
                prio = int(v.get('prio') or 0)
            else:
                ts = float(v or 0.0); prio = 0
            jobs.append((sec, ts, prio, 'board'))
        for sec, ts in list(hist_pending.items()):
            jobs.append((sec, float(ts or 0.0), 1 if _is_hist_priority(sec) else 0, 'hist'))
        jobs.sort(key=lambda x: (-x[2], x[1]))
        for sec, ts, prio, why in jobs[:cap]:
            if now - ts < 30.0:
                continue
            if why == 'hist':
                if _hist_1d(sec, prio=1) is None:   # v1.20 待重评票统一高优先级配额，防被旁路票挤占
                    continue
                if _is_100day_high(sec) is None:
                    continue
                hist_pending.pop(sec, None)
            else:
                if not _spot_ready(sec):
                    continue
                try:
                    _b_ready = _board_strength_info(sec)[1]
                except Exception:
                    _b_ready = False
                if not _b_ready:
                    continue
            sc = score_now(sec)
            if sc is None:
                continue
            if why == 'board':
                pending.pop(sec, None)
            _why = 'hist1d 恢复' if why == 'hist' else 'data_na 曾跳过'
            if not _hist_recover_logged('score', sec):
                log.info('[score-recover] %s 评分恢复 score=%.1f prio=%d (%s)' % (_sn(sec), sc, prio, _why))
        _ma5_pending_probe()   # v1.21 MA5 待补评随恢复探针一并续算
    except Exception:
        pass


def score_now(sec):
    # v0.68 数据就绪门：行情(现价/前收)或板块未就绪 -> 返回 None（买入入口跳过；卖出 P5/P6 亦跳过防误卖）
    if not _spot_ready(sec):
        _score_na_log(sec, 'spot')
        _score_na_pending_add(sec)
        return None
    _b_ready = _board_strength_info(sec)[1]
    if not _b_ready:
        _score_na_log(sec, 'board')
        _score_na_pending_add(sec)
        return None
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
    if _touched_limit_early(sec) and not _broken_now(sec):   # v0.49 炸板减去涨停分(+6), 回封复位后恢复
        b += BONUS['touched_limit_up_early']
    if _volume_ratio(sec) < 0.6:
        b += BONUS['volume_ratio_shrink']
    if _is_100day_high(sec) is True:
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
    if _is_100day_high(sec) is True:
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
                _mid_allow_log(sec, 'unique_high')
                return False
            if _dyn_theme_leader(sec):
                _mid_allow_log(sec, 'dyn_leader')
                return False
            return True
    return False


def _mid_allow_log(sec, why):
    # v1.18 中位带放行审计：复现澳洋健康 09:30:07 拦截 -> 09:31:01 放行的依据（role/身位/动态龙头/新题材前排）
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        en = g.exp_file.get(sec) or {}
        dl = _dyn_theme_leader(sec)
        fm = _dyn_theme_ferment()
        front = ''
        for nm in _new_themes_of(sec):
            d = fm.get(nm) or {}
            if d.get('front') == sec:
                front = nm
                break
        _skip_log('mid_allow', sec, why,
                  '[mid-allow] %s role=%s board=%d unique_high=%s dyn_leader=%s new_front=%s' % (
                      _sn(sec), en.get('role_detail') or '-', int(zt.get('board_cnt') or 0),
                      zt.get('unique_high') or '-', dl, front or '-'),
                  throttle_sec=300.0)
    except Exception:
        pass


def _is_100day_high(sec):
    # v1.16 三态：True/False/None（缺失可重评，不静默当非新高）
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
    if df is None or len(df) < 2:
        _hist_na_pending_add(sec)
        return None
    try:
        closes = [float(x) for x in list(df['close'])]
    except Exception:
        _hist_na_pending_add(sec)
        return None
    day = str(get_trading_day())
    last_is_today = False
    try:
        last_is_today = (_date_key(df.index[-1]) == day)
    except Exception:
        pass
    completed = closes[:-1] if last_is_today else closes
    if not completed:
        _hist_na_pending_add(sec)
        return None
    now = last_px(sec)
    if not now or now <= 0:
        return None
    try:
        return float(now) >= max(completed) * 0.9999
    except Exception:
        _hist_na_pending_add(sec)
        return None


def _volume_ratio(sec):
    # 量比：优先 get_snapshot 的 vol_ratio（PTrade 标准量比）；缺失回退 今日量/前5日均量
    try:
        s = g.spot.get(sec) or {}
        vr = float((s or {}).get('vol_ratio') or 0.0)
        if vr and vr > 0:
            return vr
    except Exception:
        pass
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
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
    # 竞价涨幅%（真口径）：get_trend_data 的 hq_px/昨收；失败回退 开盘_昨收（按交易日缓存）。
    # v0.68 B1：行情未就绪（缺前收 或 价/开盘均无）返回 0.0 且不写缓存，下帧重算——
    # 防 (day,0.0) 毒缓存导致首帧误判 miss（今日 09:30:01 大业/海洋王/安乃达/赛福天 误弃根因）。
    day = str(get_trading_day())
    c = g.auction_c.get(sec)
    if c and c[0] == day:
        return c[1]
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return 0.0
    chg = 0.0
    try:
        td = get_trend_data(stocks=sec) or {}
        d = td.get(sec) or {}
        hq = float(d.get("hq_px") or 0.0)
        if hq > 0:
            chg = (hq / pre - 1.0) * 100.0
        else:
            s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
            if op <= 0:
                return 0.0
            chg = (op / pre - 1.0) * 100.0
    except Exception:
        s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
        if op <= 0:
            return 0.0
        chg = (op / pre - 1.0) * 100.0
    g.auction_c[sec] = (day, chg)
    return chg


def _auction_ready(sec):
    # v0.68 竞价涨幅可用性（零额外行情 RPC）：缓存命中即已就绪；未缓存时 前收>0 且 开盘价>0 视为就绪
    # （与 _auction_change 就绪口径一致；供 _exp_rt_status 防首帧误弃）
    day = str(get_trading_day())
    c = g.auction_c.get(sec)
    if c and c[0] == day:
        return True
    pre = pre_close(sec)
    s = g.spot.get(sec) or {}
    op = float(s.get('open_px') or 0.0)
    return bool(pre and pre > 0 and op > 0)

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
    # 预期达标基准（expected_auction_change_pct=T日开盘涨幅）：优先供方；缺失用云端 1d 历史折算，再无基准=not提供
    # v1.27 基准只看“是否提供”：0.0 平开与负基都是合法基准，不再用 >0 过滤（S-1 平开/低开同样可比）
    e = g.exp.setdefault(sec, {})
    if e.get("has_expected_auction"):
        v = float(e.get("expected_auction_change_pct") or 0.0)
        return v, True
    en = g.exp_file.get(sec) or {}
    if en.get("has_expected_auction"):
        v = float(en.get("expected_auction_change_pct") or 0.0)
        return v, True
    opens, closes = _hist_window(sec)
    if opens and closes and len(opens) >= 2 and len(closes) >= 2 and opens[-1] and closes[-2]:
        v = (opens[-1] / closes[-2] - 1.0) * 100.0
        return v, True
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


def _seal_book_ok(sec):
    # v1.23: L2 gear validity gate. Empty batch book is unknown, not seal=0.
    gp = _gear(sec)
    if not isinstance(gp, dict):
        return False
    bg = gp.get('bid_grp')
    if not isinstance(bg, dict) or not bg:
        return False
    return True


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


def _update_seal_low_state(ft, sec, last, u, seal, bids, book_ok, fs, sfr, fast_ratio=0.15):
    # v1.23 封单大减两帧确认：数据有效才置位；封单恢复/仍封死涨停立即撤销，
    # 防止 L2 整批空档或单帧抖动被当成真实封单清零（2026-11-02 红太阳误卖根因）。
    if fs > 0 and book_ok and seal < fs * sfr:
        _tail = _is_tail_auction()
        fast = float(fast_ratio or 0.0) > 0.0 and seal < fs * float(fast_ratio)
        if fast and not _tail:
            if not ft.get('seal_low_fast'):
                ft['seal_low_fast'] = True
                ft['seal_low_fast_ts'] = time.time()
                log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW_FAST(1帧确认)' % (_sn(sec), seal, fs, seal / fs, bids))
            if not ft.get('seal_low'):
                ft['seal_low'] = True
                ft['seal_low_confirm_ts'] = time.time()
        elif fast and _tail:
            # v1.29 收盘集合竞价（14:57-15:00）封单归零属正常撤单/撮合，
            # FAST 一帧卖出降级两帧确认，防尾盘竞价误卖（2026-11-03 14:59 六票 SEAL_LOW_FAST 根因）。
            # v1.35 状态位不设 seal_low_fast（保持两帧降级语义），只对重复日志节流。
            ft['tail_auction'] = True
            if not ft.get('seal_low'):
                ft['seal_low'] = True
                ft['seal_low_confirm_ts'] = time.time()
            if not ft.get('seal_low_fast'):
                _gtl = getattr(g, 'seal_low_tail_log_ts', None)
                if not isinstance(_gtl, dict):
                    _gtl = {}; g.seal_low_tail_log_ts = _gtl
                if time.time() - float(_gtl.get(sec) or 0.0) >= float(BLS.get('seal_low_tail_log_sec', 15.0) or 15.0):
                    _gtl[sec] = time.time()
                    log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW_FAST(尾盘竞价降级两帧确认 tail_auction=1)' % (_sn(sec), seal, fs, seal / fs, bids))
        elif not ft.get('seal_low'):
            ft['seal_low'] = True
            ft['seal_low_confirm_ts'] = time.time()
            log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW(待确认)' % (_sn(sec), seal, fs, seal / fs, bids))
    elif ft.get('seal_low'):
        if (book_ok and seal >= fs * sfr) or (last >= u - 1e-9 and not ft.get('break')):
            ft['seal_low'] = False
            ft['seal_low_fast'] = False
            ft['tail_auction'] = False
            ft.pop('seal_low_fast_ts', None)
            ft.pop('seal_low_confirm_ts', None)
            log.info('[seal-low-guard] %s 封单恢复(seal=%.0f ratio=%.2f)或仍封死 -> 撤销 SEAL_LOW' % (_sn(sec), seal, (seal / fs if fs else 0.0)))


def _is_tail_auction():
    # v1.29 收盘集合竞价段判定（默认 14:57-15:00，参数化窗口）
    s = _hhmmss()
    try:
        h, m, sec = int(s[:2]), int(s[3:5]), int(s[6:8])
        cur = h * 3600 + m * 60 + sec
        def _to_sec(v):
            a, b = v.split(':')
            return int(a) * 3600 + int(b) * 60
        start = _to_sec(str(BLS.get('seal_low_tail_auction_start', '14:57') or '14:57'))
        end = _to_sec(str(BLS.get('seal_low_tail_auction_end', '15:00') or '15:00'))
        return start <= cur < end
    except Exception:
        return False


def _gear_batch_health():
    # v1.23 同帧 L2 十档缺失占比：达标返回 (unhealthy, total, invalid, ratio)
    try:
        _tot = int(getattr(g, 'gear_total_cnt', 0) or 0)
        _inv = int(getattr(g, 'gear_invalid_cnt', 0) or 0)
        _ratio = (float(_inv) / float(_tot)) if _tot > 0 else 0.0
        _min_n = int(BLS.get('seal_low_batch_invalid_min', 5) or 0)
        _min_r = float(BLS.get('seal_low_batch_invalid_ratio', 0.3) or 0.0)
        _bad = bool(_inv >= _min_n and _ratio >= _min_r)
        return _bad, _tot, _inv, _ratio
    except Exception:
        return False, 0, 0, 0.0


def _reset_seal_low_confirm_on_batch_bad():
    # v1.23 整批不健康时重置在途确认时间戳，批次恢复后需重新两帧确认
    try:
        for _sec0, _ft0 in (getattr(g, 'first_zt', None) or {}).items():
            if _ft0.get('seal_low'):
                _ft0['seal_low_confirm_ts'] = time.time()
                _ft0.pop('seal_low_fast_ts', None)
    except Exception:
        pass


def _exp_board_gate(sec):
    # v1.18 预期打板排单保护：已有 break 历史时，要求当前已回封且封单达标才允许下板单/保留在途；
    # 返回 (ok, reason)。break_cnt<=0 视为无 break 历史，直接放行。
    try:
        ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
        bc = int(ft.get('break_cnt') or 0)
        if bc <= 0:
            return True, ''
        if ft.get('break'):
            return False, 'break_open'
        s0 = g.spot.get(sec) or {}
        px = float(s0.get('last_px') or 0.0)
        up = float(s0.get('up_px') or 0.0)
        if px <= 0 or up <= 0 or px < up * 0.998:
            return False, 'not_at_limit'
        seal, _bids = _seal_metrics(sec)
        seal_min = float(BLS.get('reboard_seal_min', 200000.0) or 0.0)
        if seal_min > 0 and seal > 0 and seal < seal_min:
            return False, 'seal_low'
        return True, ''
    except Exception:
        return False, 'gate_error'


def _board_queue_cancel(sec, seal, bids):
    # v1.6 打板未成交转排单：封单衰减即撤单（防排队等到破板才以涨停价成交）。
    # 基准取排单挂出时的封单（place_order 落 pending 时记录）；旧单缺省回退 first_zt 首封。
    # 封单阈值对齐卖出链 seal_fail_ratio（唯一身位用更容忍的 unique 阈值）；委托笔数骤降视为撤单松动。
    # v1.8 云端 PTrade cancel_order 仅收 1 个位置参数（2026-10-29 富佳/中重 IQTypeError 根因）。
    # v1.18 在途 break 保护：break_cnt_at_send 之后再次炸板且当前未回封 -> 撤单（复用 cancel_pending 终态闭环）。
    try:
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        if str(pp.get('side') or '') != 'buy' or int(pp.get('filled') or 0) > 0:
            return False
        if str(pp.get('status') or '') in ('CANCELLED', 'REJECTED', 'FILLED'):
            return False
        break_fail = False
        _cancel_reason = 'seal_decay'
        if BLS.get('board_queue_cancel_break_enabled', True):
            bc_send = int(pp.get('break_cnt_at_send') or 0)
            bc_now = int((getattr(g, 'first_zt', None) or {}).get(sec, {}).get('break_cnt') or 0)
            age = time.time() - float(pp.get('ts') or 0)
            max_sec = float(BLS.get('exp_board_queue_max_sec', 600.0) or 600.0)
            if bc_now > bc_send and (max_sec <= 0 or age <= max_sec):
                _ok, _r = _exp_board_gate(sec)
                if not _ok:
                    break_fail = True
                    _cancel_reason = 'break(%s)' % _r
        base = float(pp.get('seal_base') or 0.0) or 0.0
        if base <= 0:
            ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
            base = float(ft.get('first_seal') or 0.0) or 0.0
        if base <= 0 and not break_fail:
            return False   # 无封单基准：不撤（数据未就绪保守等待）
        ratio = float(BLS.get('board_queue_cancel_seal_ratio', 0.333) or 0.333)
        try:
            if _unique_stand(sec):
                ratio = float(BLS.get('seal_fail_ratio_unique', 0.25) or 0.25)
        except Exception:
            pass
        bbase = int(pp.get('seal_bid_base') or 0)
        bid_fail = bbase > 0 and bids < bbase * float(BLS.get('board_queue_cancel_bid_ratio', 0.5) or 0.5)
        if not break_fail and seal > 0 and not bid_fail and seal / base > ratio:
            return False
        ent = str(pp.get('no') or '')
        if not ent:
            return False
        _cc = getattr(g, 'board_cancel_log', None)
        if _cc is None:
            _cc = set(); g.board_cancel_log = _cc
        if sec in _cc:
            return False   # 已撤（防同帧/重试重复撤）
        _cc.add(sec)
        # v1.15 撤单成败不以返回值判断（PTrade cancel_order 恒返回 None，失败仅打印日志）：
        # 先标记 cancel_pending，调用后立即查询终态确认，只有确认 CANCELLED/REJECTED 才释放名额/承诺。
        pp['cancel_pending'] = True
        pp['cancel_pending_ts'] = time.time()
        try:
            cancel_order(ent)
        except Exception as _e:
            # v1.13 撤单失败不释放名额/承诺：标记 cancel_pending，等回报或 _board_cancel_reconcile 兜底
            _warn('board queue cancel fail %s: %r -> cancel_pending(等回报/兜底对账)' % (_sn(sec), _e))
            return True
        st = _query_open_order_status(ent, sec=sec, side='buy', qty=pp.get('qty'), backfill=True)
        if st in ('CANCELLED', 'REJECTED'):
            pp['status'] = st
            pp['cancel_ts'] = time.time()
            _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
            log.info('[board-cancel-ok] %s 撤单确认终态=%s reason=%s seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d -> 释放名额/承诺' % (
                _sn(sec), st, _cancel_reason, seal, base, (seal / base if base > 0 else 0.0), bids, bbase))
            _release_buy_slot(sec)
            pp.pop('cancel_pending', None)
            return True
        if st == 'FILLED':
            pp['status'] = 'FILLED'
            pp['filled'] = int(pp.get('qty') or 0)
            _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
            log.info('[board-cancel-filled] %s 撤单查询已成交 -> 保留名额释放承诺' % _sn(sec))
            pp.pop('cancel_pending', None)
            return True
        # st in (None, '', 'SENT', 'PARTIAL')：保持 cancel_pending，等 _board_cancel_reconcile 兜底
        log.info('[board-cancel-pending] %s 撤单请求已发 查询=%s -> cancel_pending(不释放)' % (
            _sn(sec), st if st is not None else 'fail'))
        return True
    except Exception:
        return False


def _board_queue_cancel_scan():
    # v1.6 打板排单封单衰减撤单统一扫描（tick/1m 共用）：遍历在途买单，封单数据齐备才评估
    try:
        for sec, pp in list((getattr(g, 'pending', None) or {}).items()):
            if str(pp.get('side') or '') != 'buy' or int(pp.get('filled') or 0) > 0:
                continue
            if str(pp.get('status') or '') in ('CANCELLED', 'REJECTED', 'FILLED'):
                continue
            if str(pp.get('cancel_pending')) == 'True':   # v1.13 撤单失败等回报/兜底对账，不重复撤
                continue
            seal, bids = _seal_metrics(sec)
            try:
                _board_queue_cancel(sec, seal, bids)
            except Exception:
                continue
    except Exception:
        pass


def _is_elastic_20cm(sec):
    # 创业板(300/301)/科创板(688/689) 20cm 弹性标的（对齐 AXquant _is_elastic_20cm）
    return str(sec).split('.')[0].startswith(('300', '301', '688', '689'))


def _is_bse(sec):
    # 北交所标的（8/4/920 前缀，30cm；与 _limit_threshold/_limit_down_price 同口径）
    num = str(sec).split('.')[0]
    return num.startswith(('8', '4', '92'))


def _is_elastic_eligible(sec):
    # v1.6 弹性套利标的域：20cm（300/301/688/689）+ 北交所（8/4/92）
    return _is_elastic_20cm(sec) or _is_bse(sec)


def _elastic_min_change(sec):
    # v1.6 弹性当前涨幅下限：北交所 8%，20cm 6%
    return float(BLS.get('elastic_arb_min_change_bse', 8.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_min_change', 6.0))


def _elastic_max_change(sec):
    # v1.6 弹性当前涨幅上限：北交所 15%，20cm 10%
    return float(BLS.get('elastic_arb_max_change_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_max_change', 10.0))


def _elastic_max_open_change(sec):
    # v1.6 开盘涨幅上限：北交所 15%，20cm 12%
    return float(BLS.get('elastic_arb_max_open_change_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_max_open_change', 12.0))


def _elastic_top_buy_before(sec):
    # v1.6 弹性 top 买入前涨幅上限：北交所 15%，20cm 10%
    return float(BLS.get('elastic_top_buy_before_pct_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_top_buy_before_pct', 10.0))


def _elastic_big_bonus_pts(sec):
    # v1.6 L2 大单净量占比>=10% 作为弹性通道进攻加分（与 score_now 同阈值/同分值）
    try:
        return _l2_big_bonus_pts(sec)
    except Exception:
        return 0.0


def _fmt_big_ratio(big):
    # 订单 note 用：无/异常大单数据显示 NA，避免 -100.0% 误读
    return ('%.1f%%' % (big * 100.0)) if big >= 0.0 else 'NA'


def _max_elastic_buy_price(sec):
    # 弹性追高买入价上限：20cm 前收*1.10；北交所前收*1.15（v1.6，30cm 减半；对齐 AXquant 弹性上限）
    if not _is_elastic_eligible(sec):
        return 0.0
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return 0.0
    pct = float(BLS.get('elastic_max_buy_pct_bse', 0.15)) if _is_bse(sec) else float(BLS.get('elastic_max_buy_pct', 0.10))
    return _round_price(pre * (1 + pct))

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
                # 竞价终态封单基准回填（金额口径对齐 _seal_metrics）。
                # v1.8 total_bidqty 实测已是金额元（快照 total_offerqty 与 L2 offer_sum 等值验证），
                # 不再乘 100*up（2026-10-29 豪恩/实丰/山东矿机 base 放大 100*up 倍误判 CS 根因）；
                # 与 L2 封单金额量级差异过大时保守等待 _exp_one_word 的 L2 base_init。
                if float(g.seal_base.get(sec, 0.0) or 0.0) <= 0 and _tb is not None:
                    try:
                        _amt = float(_tb or 0.0)
                        if _amt > 0:
                            _seal0, _bids0 = _seal_metrics(sec)
                            if _seal0 > 0 and (_amt > _seal0 * 5.0 or _amt < _seal0 * 0.2):
                                log.info('[seal] %s 快照封单口径待核对 tb=%.0f seal=%.0f -> 等 L2 base_init' % (
                                    _sn(sec), _amt, _seal0))
                            else:
                                g.seal_base[sec] = _amt
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


def _vwap_follow_up(sec):
    # v1.26 A 新题材首板扫板：现价 >= 分时均价，且均价连续 N 帧走高（分时拉升均价跟随拉高）。
    try:
        s = g.spot.get(sec) or {}
        px = last_px(sec)
        vwap = float(s.get('wavg_px') or 0.0)
        if not px or not vwap or px < vwap:
            return False
        now = time.time()
        track = getattr(g, 'vwap_track', None)
        if track is None:
            track = {}; g.vwap_track = track
        prev = track.get(sec) or {}
        frames = int(BLS.get('vwap_follow_frames', 2) or 2)
        min_rise = float(BLS.get('vwap_follow_min_rise', 0.0005) or 0.0005)
        rising = bool(prev.get('vwap') is not None
                      and vwap >= float(prev['vwap']) * (1.0 - min_rise)
                      and now - float(prev.get('ts') or 0.0) <= 15.0)
        cnt = int(prev.get('cnt') or 0) + 1 if rising else 1
        track[sec] = {'vwap': vwap, 'cnt': cnt, 'ts': now}
        return cnt >= frames
    except Exception:
        return False


def _below_vwap_confirm(sec):
    # v0.73 分时 VWAP 弱化确认：首帧宽限 + 贴板豁免 + 两帧确认，防 09:30 数据未稳定永久误弃；
    # 连续弱 N 秒才判 CS；期间回封/回站 VWAP 即取消 pending。
    try:
        s = g.spot.get(sec)
        vwap = float(s.get("wavg_px") or 0.0) if s else 0.0
        up = float(s.get("up_px") or 0.0) if s else 0.0
        px = last_px(sec)
        if not (px and vwap and px < vwap):
            p = getattr(g, 'below_vwap_pending', None)
            if p:
                p.pop(sec, None)
            return False
        pending = getattr(g, 'below_vwap_pending', None)
        if pending is None:
            pending = {}; g.below_vwap_pending = pending
        if BLS.get('vwap_weak_at_limit_exempt', True) and up > 0 and px >= up * 0.998:
            pending.pop(sec, None)
            return False
        age = _sec_age()
        grace = float(BLS.get('vwap_weak_grace_sec', 30))
        confirm = float(BLS.get('vwap_weak_confirm_sec', 6))
        if age <= grace:
            if sec not in pending:
                pending[sec] = age
                log.info('[exp-rt] %s below_vwap 首帧待确认 vwap=%.3f px=%.3f age=%.0fs (不判弱)' % (_sn(sec), vwap, px, age))
            return False
        first_age = float(pending.get(sec) or 0.0)
        if not first_age or age - first_age < confirm:
            return False
        pending.pop(sec, None)
        log.info('[exp-rt] %s below_vwap 连续弱确认 vwap=%.3f px=%.3f age=%.0fs -> 放弃' % (_sn(sec), vwap, px, age))
        return True
    except Exception:
        return False

def _eval_auction(sec):
    e = g.exp.setdefault(sec, {})
    if e.get("entry_type") == "one_word":
        return AW, ["one_word_requires_seal"]
    chg = _auction_change(sec)
    # v1.4 A3：竞价数据未就绪（涨幅 0 且前收/开盘未齐）不误判，返回 AW 等待；
    # 防负基昨日开盘把未就绪误判 PX（2026-10-28 榕基软件类场景）。
    if chg == 0.0 and not _auction_ready(sec):
        return AW, ["auction_data_not_ready"]
    # v1.27 放量烂板/炸板不回封独立三态：红开=超预期；-2%<小绿开<=0=符合；<=-2% 或跌停开=低于
    if _bad_seal_role(sec):
        if chg > float(BLS.get('exp_bad_seal_red_exceed', 0.0) or 0.0):
            return PX, ["bad_seal_red_open_exceed"]
        if chg <= float(BLS.get('exp_bad_seal_big_green_miss', -2.0) or -2.0):
            return PS, ["bad_seal_big_green_miss"]
        return PM, ["bad_seal_small_green_meet"]
    if chg < 0:
        return PS, ["auction_green_open"]
    yopen, has = _yesterday_open_chg(sec)
    if has and chg > yopen:
        return PX, ["auction_higher_than_yesterday"]   # 负基也判高开（v0.17）
    if not has:
        return AW, ["missing_yesterday_open"]   # v1.27 基准缺失保持等待，不误判 PM
    return PM, ["auction_small_open"]


def _bad_seal_role(sec):
    # v1.27 放量烂板/炸板不回封：权威 role_detail 或云端动态标注
    en = g.exp_file.get(sec) or {}
    e = g.exp.setdefault(sec, {})
    rd = str(en.get('role_detail') or e.get('role_detail') or '')
    return rd in ('bad_seal_board', 'broken_consecutive_limit_up')


def _limit_pct_by_sec(sec):
    # v1.27 名义涨停幅 %：主板10/20cm20/30cm30（供一字开盘符合下限折算）
    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        return 20.0
    if num.startswith(('8', '4', '92')):
        return 30.0
    return 10.0

def _calc_intraday_bars_ready(sec):
    # v1.3 分时数据兜底：1m 已有 >=2 根（spot VWAP 缺失时证明分时已就绪）
    try:
        df = get_price(sec, start_date=None, end_date=None, count=8, frequency="1m")
        return bool(df is not None and len(df) >= 2)
    except Exception:
        return False

def _intraday_ready(sec):
    # v1.3 分时就绪门：spot 现价/开盘/VWAP 齐备即就绪；否则用 m1 预算缓存回看（0 新增帧 RPC）。
    # 防 09:30 首帧数据未就绪时 meet 候选被 `_eval_intraday` 默认 CM(held_vwap) 误判买入。
    return bool(_intraday_ready_detail(sec))

def _intraday_ready_detail(sec):
    # v1.4 A4：返回就绪源（spot / 1m / ''），供 [exp-order] 日志核对数据链路
    try:
        s = g.spot.get(sec) or {}
        if (float(s.get('last_px') or 0.0) > 0 and float(s.get('open_px') or 0.0) > 0
                and float(s.get('wavg_px') or 0.0) > 0):
            return 'spot'
        dh = _get_ds()
        if dh.cached('m1_ready', sec, 3.0, lambda: _calc_intraday_bars_ready(sec), budget='m1', prio=1):
            return '1m'
        return ''
    except Exception:
        return ''

def _intraday_confirmed_ready(sec):
    # v1.8 pending_meet 硬就绪：1m 已出 >=2 根，或评分链路（board）就绪；
    # 防 09:30 首帧 spot 三字段就绪但 1m/评分 data_na 时 CM 误发单（2026-10-29 中重/富佳/徕木）。
    try:
        dh = _get_ds()
        if dh.cached('m1_ready2', sec, 3.0, lambda: _calc_intraday_bars_ready(sec), budget='m1', prio=1):
            return True
        if _spot_ready(sec) and BLS.get('exp_meet_score_ready', True):
            try:
                return bool(dh.cached('board_ready2', sec, 5.0,
                                      lambda: _board_strength_info(sec)[1], budget='m1', prio=1))
            except Exception:
                return False
        return False
    except Exception:
        return False

def _eval_intraday(sec, auction_status):
    if auction_status in (PS, CS):
        return CS, ["from_auction"]
    if auction_status == AW:
        return PM, ["auction_data_not_ready"]
    if auction_status in (PM, PX) and not _intraday_ready(sec):
        return PM, ["intraday_data_not_ready"]
    if _two_1m_break(sec) and auction_status in (PX, CX):
        return CX, ["two_1m_break"]
    if _below_vwap_confirm(sec):
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


def _exp_one_word(sec, quiet=False):
    # 一字板封单（L2 实时化）：金额比基准判超预期/衰竭；买一委托笔数骤降视为撤单松动，加速判 miss
    seal, bids = _seal_metrics(sec)
    base = (g.seal_base or {}).get(sec, 0.0)
    bbase = (g.seal_bid_base or {}).get(sec, 0)
    if base <= 0:
        if seal <= 0:
            # v1.4 A2：L2 封单未就绪（seal 与基准均 0）不误判 CS，返回 AW 等 L2 明确后再判
            return AW, ["seal_data_not_ready"]
        g.seal_base[sec] = seal
        g.seal_bid_base[sec] = bids
        return AW, ["seal_base_init"]
    ratio = seal / base if base > 0 else 0.0
    bid_fail = False
    if BLS.get("seal_bid_enabled", True) and bbase > 0 and bids < bbase * float(BLS.get("seal_bid_fail_ratio", 0.5)):
        bid_fail = True
    if ratio <= float(BLS["seal_fail_ratio"]) or bid_fail:
        if not quiet:
            log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d bid_fail=%s -> CS" % (_sn(sec), seal, base, ratio, bids, bbase, bid_fail))
        return CS, ["seal_fail"]
    if ratio >= float(BLS["seal_exceed_ratio"]):
        if not quiet:
            log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CX" % (_sn(sec), seal, base, ratio, bids))
        return CX, ["seal_increase"]
    if not quiet:
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CM" % (_sn(sec), seal, base, ratio, bids))
    return CM, ["seal_within"]



def _unique_stand(sec):
    # v0.49 唯一身位（人气龙头/后排助攻）：复盘 unique_high 或 动态唯一+跟风确认
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        if zt.get('unique_high'):
            return True
        return _dyn_unq_confirmed(sec)
    except Exception:
        return False


def _broken_now(sec):
    # v0.49 炸板中（break 未复位）——供打分扣涨停分
    try:
        return bool(((g.first_zt or {}).get(sec) or {}).get('break'))
    except Exception:
        return False


def _auction_beat_history(sec):
    # 开盘涨幅优于近 20 日平均开盘涨幅（近似，真实为竞价后对比历史同期）
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
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
    # 板块强度/排名刷新周期：快速窗口（开盘 30 分钟 + 13:00-13:30）3s 与 tick 同频，之后 60s
    try:
        if _fast_window():
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


def _board_member_changes_api(sec):
    # 板块成员实时涨跌列表（API 兜底，v0.60）：所属板块代码->成员批量快照涨跌。
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


def _board_member_changes(sec):
    # 板块成员实时涨跌列表（v0.60 统一 THS 概念口径）：所属概念板块中强度最强板块成员批量快照涨跌；
    # 文件未加载/开关关闭回退 API（旧链 _board_code_of/_fetch_board_chgs）
    try:
        if not _concept_active():
            return _board_member_changes_api(sec)
    except Exception:
        return _board_member_changes_api(sec)
    b = _concept_strong_board(sec)
    if b is None:
        return _board_member_changes_api(sec)
    mem = _board_members_file(b, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return []
    snap = _concept_snap_for(b, mem)
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
    return chgs


def _board_strength_api(sec):
    # 板块强度（API 兜底，v0.60）：所属板块成员实时涨跌均值（缓存随 _board_refresh_ttl）
    b = _board_code_of(sec)
    return _board_strength_by_code(b) if b else 0.0


def _concept_strong_board(sec):
    # v0.60 所属概念板块中强度最强板块（文件 THS 概念口径，聚合取最强）；未激活 -> None（调用方回退 API）
    try:
        if not _concept_active():
            return None
    except Exception:
        return None
    best_b = None; best_st = None
    for b in _concept_boards_of(sec):
        try:
            st = _concept_board_strength(b)
        except Exception:
            continue
        if best_b is None or st > best_st:
            best_b, best_st = b, st
    return best_b


def _board_strength_by_concept(sec):
    # v0.60 板块强度（统一 THS 概念口径）：所属概念板块强度取最强；未激活回退 API
    try:
        if not _concept_active():
            return _board_strength_api(sec)
    except Exception:
        return _board_strength_api(sec)
    b = _concept_strong_board(sec)
    return _concept_board_strength(b) if b else 0.0


def _board_strength(sec):
    # 板块强度（v0.60 统一 THS 概念口径；文件未加载/开关关闭回退 API）
    return _board_strength_by_concept(sec)


def _board_strength_by_code_info(board_code):
    # v0.68 板块强度可用性（API 兜底）：(strength, ready)。成员快照无有效涨跌样本 -> ready=False
    # （盘中重启首帧/快照缺前收），区别于「未映射中性 0.0」——score 据此返回 None 防虚高打分。
    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', str(board_code), _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(board_code), budget='board', stale_ok=True)
        chgs = list(v) if v is not None else []
        if not chgs:
            return 0.0, False
        return (sum(chgs) / len(chgs)) * 100.0, True
    except Exception:
        return 0.0, False


def _concept_board_strength_info(board):
    # v0.68 概念板块强度可用性：(strength, ready)。板块有归属但成员快照无可测样本 -> ready=False
    try:
        if not _concept_active():
            return _board_strength_by_code_info(board)
    except Exception:
        return _board_strength_by_code_info(board)
    mem = _board_members_file(board, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return 0.0, False
    snap = _concept_snap_for(board, mem)
    s = 0.0; n = 0
    for m in mem:
        try:
            d = snap.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre > 0 and px > 0:
                s += px / pre - 1.0; n += 1
        except Exception:
            continue
    if n == 0:
        return 0.0, False
    return (s / n) * 100.0, True


def _board_strength_info(sec):
    # v0.68 板块强度可用性门：(st, ready)。无板块归属(未映射) -> (0.0, True) 保持未知中性（不阻断无映射标的）；
    # 有归属但不可测 -> (0.0, False) -> score_now 返回 None（防重启首帧 board=0.0 虚高）。
    try:
        if _concept_active():
            b = _concept_strong_board(sec)
            if b is None:
                return (0.0, True) if not _concept_boards_of(sec) else (0.0, False)
            return _concept_board_strength_info(b)
        b = _board_code_of(sec)
        if not b:
            return 0.0, True
        return _board_strength_by_code_info(b)
    except Exception:
        return 0.0, True


def _compute_board_rank(boards):
    # 各板块强度排序，取强度前 N（API 兜底，v0.60；概念口径见 _compute_concept_board_rank）
    sts = []
    for b in boards:
        try:
            sts.append((_board_strength_by_code(b), b))
        except Exception:
            continue
    sts.sort(key=lambda kv: kv[0], reverse=True)
    return {b for _, b in sts[:int(BLS.get('board_rank_top_n', 3))]}


def _compute_concept_board_rank(boards):
    # v0.60 概念口径强度排序取前 N：文件成员 + 共享账本/单板预算缓存（_concept_board_strength）
    sts = []
    for b in boards:
        try:
            sts.append((_concept_board_strength(b), b))
        except Exception:
            continue
    sts.sort(key=lambda kv: kv[0], reverse=True)
    return {b for _, b in sts[:int(BLS.get('board_rank_top_n', 3))]}


def _board_rank_cand_src(secs):
    # v0.60 排名候选源：概念激活时统一 _elastic_top_cand_src（池∪T-1涨停名单），
    # 与 _new_top_board_scan 共用 csnap_led 合并快照账本（共享 key 零额外 RPC）
    try:
        if _concept_active():
            src = _elastic_top_cand_src()
            if src:
                return src
    except Exception:
        pass
    return [s for s in (secs or []) if s]


def _board_rank_top3_set(secs):
    # 候选所属板块 -> 强度前三板块（v0.60 统一 THS 概念口径，候选源 _elastic_top_cand_src 共享账本）；
    # 文件未加载/开关关闭回退 API（旧链 _board_code_of/_board_strength_by_code）
    secs = [s for s in (secs or []) if s]
    if not secs:
        return set()
    if not _concept_active():
        boards = sorted({b for b in (_board_code_of(s) for s in secs) if b})
        if not boards:
            return set()
        try:
            dh = _get_ds()
            token = '|'.join(boards)
            v = dh.cached(('board_rank', token), '_', _board_refresh_ttl(),
                          lambda: _compute_board_rank(boards), single=True)
            return v if v is not None else set()
        except Exception:
            return set()
    src = _board_rank_cand_src(secs)
    boards = sorted({b for s in src for b in _concept_boards_of(s) if b})
    if not boards:
        return set()
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('board_rank_c', token), '_', _board_refresh_ttl(),
                      lambda: _compute_concept_board_rank(boards), single=True)
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
    # sec 所属板块是否在候选板块强度前三（v0.60 概念口径：任一所属概念板块在强度前三；
    # 文件未加载/开关关闭回退 API 首板块判定）
    try:
        if not _concept_active():
            b = _board_code_of(sec)
            if not b:
                return False
            return b in _board_rank_top3_set(secs)
        top3 = _board_rank_top3_set(secs)
        if not top3:
            return False
        return any(b in top3 for b in _concept_boards_of(sec))
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
    # 板块红盘比（v0.60 统一 THS 概念口径）：最强概念板块成员 up/(up+dn)；
    # 未激活回退 API；无成员返回0.5(中性)
    chgs = _board_member_changes(sec)
    up = sum(1 for x in chgs if x > 0)
    dn = sum(1 for x in chgs if x < 0)
    denom = up + dn
    return float(up) / denom if denom else 0.5


def _market_red_ttl():
    # 全市场红盘比缓存 TTL：快速窗口内快速刷新（对齐 _fast_window）
    try:
        if _fast_window():
            return float(BLS.get('market_red_ttl_fast', 30.0))
    except Exception:
        pass
    return float(BLS.get('market_red_ttl', 60.0))


def _ld_ttl():
    # v1.25/v1.36 跌停题材因子刷新节奏：快速窗口灵敏度优先（15s），其余降频（120s）
    if _fast_window():
        return float(BLS.get('ld_ttl_before', 15.0))
    return float(BLS.get('ld_ttl_after', 120.0))


def _ld_ratio(sec):
    # 跌停幅（与 _limit_down_price 同口径）：主板 10%、创业板/科创板 20%、北交所 30%；ST 5% 不单独建模（策略已剔除 ST）
    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        return float(BLS.get('limit_down_chinext', 0.20))
    if num.startswith(('8', '4', '92')):
        return float(BLS.get('limit_down_bse', 0.30))
    return float(BLS.get('limit_down_main', 0.10))


def _fetch_market_red(pool):
    # 全量分片 get_snapshot 统计 涨/(涨+跌)（与 AXquant 生成侧口径一致，不含平盘）；
    # v1.24 同时统计跌停家数并按题材/概念归集（竞价-开盘-10:00 跌停因子）；无有效样本 -> None
    batch = max(int(BLS.get('market_batch', 300)), 1)
    up = dn = ld_n = zt_ld_n = 0
    ld_codes = []
    theme_ld = {}
    concept_ld = {}
    zt = getattr(g, 'zt_lianban', {}) or {}
    concept_ok = _concept_active()
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
                if px <= pre * (1.0 - _ld_ratio(code)) * 1.0001:
                    ld_n += 1
                    if len(ld_codes) < 200:
                        ld_codes.append(code)
                    for nm in _zt_themes_of(code):
                        theme_ld[nm] = int(theme_ld.get(nm) or 0) + 1
                    if concept_ok:
                        for nm in _concept_boards_of(code):
                            concept_ld[nm] = int(concept_ld.get(nm) or 0) + 1
                    if code in zt:
                        zt_ld_n += 1
            except Exception:
                continue
    denom = up + dn
    if denom <= 0:
        log.info('[market-red] 无有效样本（全量分片 %d 批）-> None' % n_batch)
        return None
    ratio = float(up) / denom
    out = {
        'red': ratio, 'up': up, 'dn': dn,
        'ld_n': ld_n, 'ld_codes': ld_codes,
        'theme_ld': theme_ld, 'concept_ld': concept_ld,
        'zt_ld_n': zt_ld_n, 'zt_ld_codes': [c for c in ld_codes if c in zt][:30],
    }
    _top_ld_theme = sorted(theme_ld.items(), key=lambda kv: -kv[1])[:3]
    log.info('[market-red] 全市场红盘比=%.2f%% up=%d dn=%d 跌停=%d 池内跌停=%d 题材=%s 批=%d 样本=%d 耗时=%.1fs'
             % (ratio * 100.0, up, dn, ld_n, zt_ld_n,
                ','.join('%s:%d' % (k, v) for k, v in _top_ld_theme),
                n_batch, denom, time.time() - t0))
    return out


def _market_pool():
    # 全市场代码池（按交易日缓存，get_Ashares 失败 -> 空池）
    try:
        day = str(get_trading_day())
        if getattr(g, 'pool_day', '') != day:
            try:
                g.pool_all = [x for x in (_norm_sec(c) for c in (get_Ashares() or [])) if x]
                g.pool_day = day
            except Exception as e:
                _warn('market-red get_Ashares fail: %r' % e)
                g.pool_all = []
    except Exception:
        pass
    return list(g.pool_all or [])


def _market_ld_senti(force_fetch=False):
    # v1.24 全市场跌停因子：复用 mkt_red 缓存（同一轮全量快照统计红盘比+跌停归集）；
    # force_fetch=True（09:25/09:30/10:00 阶段快照）ttl=0 强制刷新并写缓存。
    try:
        pool = _market_pool()
        if not pool:
            return None
        day = str(get_trading_day())
        dh = _get_ds()
        ttl = 0.0 if force_fetch else _ld_ttl()
        d = dh.cached(('mkt_red', day), '_mkt_', ttl,
                      lambda: _fetch_market_red(pool), budget='market', stale_ok=True)
        return d if isinstance(d, dict) else None
    except Exception as e:
        _warn('market-ld fail: %r' % e)
        return None


def _market_red_ratio():
    # 全市场红盘比（v0.41）：get_Ashares 全量分片 get_snapshot 统计，独立预算源 market；
    # 失败/无池 -> None（上层降级基线驱动保守上限）。日切随 DataHub 缓存 key(day) 失效。
    try:
        d = _market_ld_senti()
        return d.get('red') if isinstance(d, dict) else None
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


def _buy_pos_cap_qty(context, sec, qty, limit):
    # 情绪仓位闸门：返回允许买入股数（0=整单拒绝）。
    # v1.17 超限默认按剩余额度缩量（pos_cap_over_behavior='shrink'），可选 'skip' 整单拒绝。
    cap = _sentiment_pos_cap(context, sec)
    if cap is None:
        return qty
    pos = getattr(getattr(context, 'portfolio', None), 'positions', {}) or {}
    pv = sum(_pos_value(p, sec) for p in pos.values())
    cash = _size_cash(context)   # v0.64 资金实时最新（减在途买单承诺）; v0.80 SIM 虚拟资金基准
    total = cash + pv
    if total <= 0:
        return qty
    price = limit or last_px(sec) or 0.0
    if price <= 0:
        return qty
    lot = int(BLS.get('buy_lot_step', 100) or 100)
    add = qty * price
    ratio = (pv + add) / total
    if ratio <= cap:
        return qty
    behavior = str(BLS.get('pos_cap_over_behavior', 'shrink') or 'shrink').lower()
    if behavior == 'shrink':
        allowed = max(0.0, cap * total - pv)
        shrink_qty = int(allowed / (price * lot)) * lot
        if shrink_qty < lot:
            g.pos_cap_skips = int(getattr(g, 'pos_cap_skips', 0) or 0) + 1   # 缩量不足一手按拒绝
            log.info('[pos-cap] %s qty=%d add=%.0f pos_ratio=%.2f > cap=%.2f -> shrink<%d skip total=%d'
                     % (_sn(sec), qty, add, ratio, cap, lot, g.pos_cap_skips))
            return 0
        g.pos_cap_shrinks = int(getattr(g, 'pos_cap_shrinks', 0) or 0) + 1
        log.info('[pos-cap] %s qty=%d -> %d add=%.0f pos_ratio=%.2f > cap=%.2f -> shrink total=%d'
                 % (_sn(sec), qty, shrink_qty, add, ratio, cap, g.pos_cap_shrinks))
        return shrink_qty
    g.pos_cap_skips = int(getattr(g, 'pos_cap_skips', 0) or 0) + 1   # v1.12 拦截计数
    log.info('[pos-cap] %s qty=%d add=%.0f pos_ratio=%.2f > cap=%.2f -> skip total=%d'
             % (_sn(sec), qty, add, ratio, cap, g.pos_cap_skips))
    return 0


def _buy_pos_ok(context, sec, qty, limit):
    # 兼容布尔入口：True=闸门放行（shrink 后仍有可买股数），False=整单拒绝
    return _buy_pos_cap_qty(context, sec, qty, limit) > 0

def _set_now(context):
    g.now_dt = getattr(getattr(context, 'blotter', None), 'current_dt', None) or None


def _hhmm():
    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            return nd.strftime('%H:%M')
        except Exception:
            pass
    return time.strftime('%H:%M')


def _hhmmss():
    # 秒级时钟（HH:MM:SS），供 P2E 竞价核卖确认段窗口判定（_hhmm 仅到分钟）
    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            return nd.strftime('%H:%M:%S')
        except Exception:
            pass
    return time.strftime('%H:%M:%S')


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
            ma5b4 = _ma5_base4(sec) or 0.0
            chg = _auction_change(sec)
            tags = ','.join(_tags(sec)) or '-'
            st = _board_strength(sec)
            sc = score_now(sec)
            if sc is None:
                _skip_log('score_na', sec, 'data_na', 'score %s bar=%s data_na -> skip' % (_sn(sec), _hhmm()))
                continue
            log.info('score %s bar=%s px=%.2f ma5=%.2f ma5b4=%.2f chg=%.1f%% board=%.1f tags=%s score=%.1f' % (
                _sn(sec), _hhmm(), px if px else 0.0, ma5, ma5b4, chg, st, tags, sc))
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


def _is_st(sec):
    # v0.75 全链路 ST 判定：zt_lianban 权威 is_st 优先；名单外按名称前缀兜底；
    # 命中结果按交易日缓存 g.st_set；skip_st_pool=False 时一律返回 False 保持旧行为。
    sec = str(sec or '')
    if not sec or not BLS.get('skip_st_pool', True):
        return False
    zt = (getattr(g, 'zt_lianban', None) or {}).get(sec)
    if zt is not None:
        try:
            return bool(zt.get('is_st'))
        except Exception:
            pass
    day = str(get_trading_day())
    st_set = getattr(g, 'st_set', None)
    if st_set is None or getattr(g, 'st_day', None) != day:
        st_set = set(); g.st_set = st_set; g.st_day = day
    if sec in st_set:
        return True
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    if sec not in nm:
        try:
            _got = get_stock_name(sec)
            nm[sec] = str(_got or '').strip()
        except Exception:
            nm[sec] = ''
    _name = (nm.get(sec) or '').strip().upper()
    if _name.startswith('*ST') or _name.startswith('ST') or _name.startswith('S*ST') or _name.startswith('SST'):
        st_set.add(sec)
        return True
    return False


def _warm_name_map(secs):
    # v0.75 ST 名称兜底批量预热：get_stock_name 支持列表，一次 RPC 覆盖整批，避免逐只名称查询拖帧
    secs = [s for s in (_norm_sec(c) for c in (secs or [])) if s]
    if not secs:
        return
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    todo = [s for s in secs if s not in nm]
    if not todo:
        return
    try:
        got = get_stock_name(todo) or {}
        if isinstance(got, dict):
            for _c, _v in got.items():
                _cc = _norm_sec(_c)
                if not _cc:
                    continue
                if isinstance(_v, dict):
                    _v = _v.get('stock_name') or ''
                nm[_cc] = str(_v or '').strip()
        elif isinstance(got, (list, tuple)):
            for _row in got:
                try:
                    if isinstance(_row, dict):
                        _cc = _norm_sec(_row.get('code') or _row.get('security') or '')
                        _v = _row.get('stock_name') or _row.get('name') or ''
                    elif len(_row) >= 2:
                        _cc = _norm_sec(_row[0]); _v = _row[1]
                    else:
                        continue
                    if _cc:
                        nm[_cc] = str(_v or '').strip()
                except Exception:
                    continue
    except Exception:
        pass


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
    if BLS.get('skip_st_pool', True):
        _warm_name_map(pool)
        pool = [x for x in pool if not _is_st(x)]
    g.pool_static = pool
    log.info('[pool] selfwatch=%d expect_buy=%d pool_static=%d' % (len(sw), len(buy_codes), len(pool)))


def _pool():
    # 当前买入/打分迭代目标：动态 watch ∪ 固定池(自选股+预期推荐)；空回落 universe
    out = [x for x in (_norm_sec(s) for s in (list(g.watch or []) + list(g.pool_static or []))) if x]
    if BLS.get('skip_st_pool', True):
        _warm_name_map(out)
        out = [x for x in out if not _is_st(x)]
    out = list(dict.fromkeys(out))
    if out:
        return out
    uni = [x for x in BLS['universe'] if x]
    if BLS.get('skip_st_pool', True):
        _warm_name_map(uni)
        uni = [x for x in uni if not _is_st(x)]
    return uni or BLS['universe']


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


def _hot_scan_set():
    # v0.74 开盘热点优先：昨日涨停/自选/预期/固定池先扫（黄金窗口不浪费在冷门票）
    hot = set(getattr(g, 'zt_lianban', None) or {})
    for c in (getattr(g, 'selfwatch', None) or []):
        _c = _norm_sec(c)
        if _c:
            hot.add(_c)
    for c in (getattr(g, 'pool_static', None) or []):
        hot.add(c)
    for c in (getattr(g, 'exp_file', None) or {}):
        hot.add(c)
    return hot


def _scan_market():
    # 全市场扫描：按涨幅/接近涨停过滤，取 top max_watch 入池（缓存按交易日）
    # v0.74：scan_batch=600 + 开盘热点优先 -> 开盘 10 分钟扫完全市场一轮；
    # near_scan 近涨停快速通道：命中 chg>=scan_near_chg 即跨轮保留，tick 3s 帧优先跟踪，
    # 新发酵票首触不再等 17 分钟轮询。
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
    if getattr(g, 'scan_order_day', None) != day or not g.scan_order:
        order = list(g.pool_all)
        if BLS.get('scan_hot_first', True) and _fast_window():
            hot = [c for c in order if c in _hot_scan_set()]
            order = hot + [c for c in order if c not in hot]
        g.scan_order = order
        g.scan_order_day = day
    total = len(g.scan_order)
    cap = min(int(BLS['scan_batch']), total)
    offset = g.scan_offset % max(total, 1)
    window = g.scan_order[offset:offset + cap]
    if len(window) < cap and total:
        window = window + (g.scan_order + g.scan_order)[offset + cap:offset + cap + (cap - len(window))]
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
    if BLS.get('skip_st_pool', True):
        _warm_name_map([r['code'] for r in rows])
        _pre_st = len(rows)
        rows = [r for r in rows if not _is_st(r['code'])]
        _n_st = _pre_st - len(rows)
        if _n_st and time.time() - float(getattr(g, 'st_skip_log_ts', 0.0) or 0.0) >= 300.0:
            g.st_skip_log_ts = time.time()
            log.info('[st-skip] scan rows=%d skip_st=%d' % (_pre_st, _n_st))
    rows.sort(key=lambda r: r['proxy'], reverse=True)
    watch = [x for x in (_norm_sec(r['code']) for r in rows[:int(BLS['max_watch'])]) if x]
    # v0.74 near_scan 维护：命中近涨停阈值入补充池；跨轮保留；已 first_zt 移除；超上限按涨幅+时间淘汰
    g.scan_round = int(getattr(g, 'scan_round', 0) or 0) + 1
    cur_round = g.scan_round
    keep_rounds = int(BLS.get('scan_near_keep_rounds', 3))
    near_cap = int(BLS.get('scan_near_cap', 20))
    near = getattr(g, 'near_scan', None)
    if near is None:
        near = {}; g.near_scan = near
    ft = getattr(g, 'first_zt', None) or {}
    if BLS.get('skip_st_pool', True):
        _warm_name_map(list(near))
        for code in [x for x in near if _is_st(x)]:
            near.pop(code, None)   # 存量 near_scan 也剔除 ST（防旧状态残留）
    for code in [x for x in near if x in ft]:
        near.pop(code, None)
    for code in [x for x in near if (near[x].get('round') or 0) < cur_round - keep_rounds]:
        near.pop(code, None)
    near_chg = float(BLS.get('scan_near_chg', 7.0))
    for r in rows:
        code = _norm_sec(r['code'])
        if not code or code in ft:
            continue
        if r['chg'] >= near_chg or r['limit']:
            rec = near.get(code)
            near[code] = {'ts': rec.get('ts') if rec else time.time(),
                          'round': cur_round, 'chg': r['chg']}
    if len(near) > near_cap:
        ranked = sorted(near.items(), key=lambda kv: (-(kv[1].get('chg') or 0.0), kv[1].get('ts') or 0.0))
        near = dict(ranked[:near_cap])
        g.near_scan = near
    near_secs = [c for c in near if c not in ft]
    watch = list(dict.fromkeys(watch + near_secs))
    if watch:
        g.watch = watch
    return (watch or BLS['universe'])


def _sync_watch(context):
    try:
        watch = _scan_market()
        if watch:
            g.watch = list(dict.fromkeys(watch))
        log.info('market_scan bar=%s pool=%d watch=%d near=%d off=%d cap=%d' % (
            _hhmm(), len(g.pool_all or []), len(g.watch),
            len(getattr(g, 'near_scan', None) or {}),
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

def _load_expectation(merge=False):
    # 读 AXquant 竞价终态文件（docs/25 契约）；缺失/坏文件自动跳过（扫描兜底）。
    # v0.68 C：盘中重读 merge=True 逐 code 合并（新文件胜出冲突；旧有但新文件缺失的 code 保留，
    # 防盘中 15->5 收缩丢候选）；首载(08:59 before_trading_start)保持全量替换。
    # 上传时间契约：定时上传任务需 9:15 前完成（09:25 竞价终态重读命中当日文件）。
    if not merge:
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
        if not merge:
            log.info("expectation file not found (tried %s)" % _expectation_paths())
        return len(g.exp_file)
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        # v0.68 C2 日期身份守卫：盘中重载文件带日期列且非今日 -> 拒绝（保留当前已载），防旧文件回填覆盖
        if merge and g.exp_file:
            _dat = None
            for _dk in ('date', 'trading_date', 'generated_at'):
                if _dk in hdr:
                    _idx = hdr.index(_dk)
                    for r in rows[1:]:
                        if len(r) > _idx and str(r[_idx]).strip():
                            _dat = str(r[_idx]).strip()
                            break
                    break
            if _dat and _dat != str(get_trading_day()):
                log.info("expectation file skip(date=%s != today) %s keep=%d" % (_dat, fp, len(g.exp_file)))
                return len(g.exp_file)
        _old = set(g.exp_file)
        _new = {}
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            _ry = (rec.get("yesterday_open_pct") or "").strip()
            _ra = (rec.get("expected_auction_change_pct") or "").strip()
            _new[code] = {
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
        if merge:
            g.exp_file.update(_new)   # 新文件胜出；旧有但新文件缺失的 code 保留（_src 不变）
            _keep = len(_old - set(_new))
            log.info("expectation file merged %s old=%d new=%d total=%d keep_old=%d"
                     % (fp, len(_old), len(_new), len(g.exp_file), _keep))
            return len(g.exp_file)
        g.exp_file = _new
        log.info("expectation file loaded %s -> %d" % (fp, len(g.exp_file)))
        return len(g.exp_file)
    except Exception as e:
        log.info("expectation file skip (none/invalid) %s: %r" % (fp, e))
        return len(g.exp_file)

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

def _load_zt_lianban(merge=False):
    # 读 T-1 涨停/连板名单（docs/33 导出契约）：zt_lianban_latest.csv / zt_lianban_<date>.csv；缺失不崩。
    # v0.79 P1 防收缩：盘中重读 merge=True（新文件 code 字段胜出 + 旧有缺失保留 + 日期守卫 + 收缩护栏）；
    # 首载(09:10 before_trading_start)保持全量替换。上传时间契约：9:15 前完成（09:25 竞价终态重读命中）。
    if not merge:
        g.zt_lianban = {}
    elif not getattr(g, 'zt_lianban', None):
        g.zt_lianban = {}   # merge 且尚无现有一致视为全量（如盘中重启后首次加载）
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
        return len(g.zt_lianban)
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        has_unq = 'unique_high' in hdr
        has_flw = 'follower_count' in hdr
        has_theme = 'theme' in hdr
        g.zt_unq_authoritative = has_unq    # v0.37 文件带权威唯一列（AXquant 同源预计算）-> 优先读列
        g.zt_theme_authoritative = has_theme  # v0.38 文件带权威题材列（theme.buckets 同源）
        # v0.79 日期身份守卫（merge 且现有非空）：文件 date 列非空且 != 现有 date -> 拒绝（防旧文件回填覆盖）
        if merge and g.zt_lianban:
            _dat = None
            if 'date' in hdr:
                _di = hdr.index('date')
                for r in rows[1:]:
                    if len(r) > _di and str(r[_di]).strip():
                        _dat = str(r[_di]).strip()
                        break
            if _dat:
                _cur = None
                for _rec in g.zt_lianban.values():
                    if (_rec.get('date') or '').strip():
                        _cur = str(_rec['date']).strip()
                        break
                if _cur and _dat != _cur:
                    log.info("[zt-lianban] merge skip(date=%s != %s) %s keep=%d" % (_dat, _cur, fp, len(g.zt_lianban)))
                    return len(g.zt_lianban)
        _new = {}
        themed = 0
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            theme = (rec.get("theme") or "").strip()
            themes = (rec.get("themes") or "").strip()
            if theme:
                themed += 1
            _new[code] = {
                "date": (rec.get("date") or "").strip(),
                "board_cnt": int(_fnum(rec.get("board_cnt"))),
                "limit_up_time": (rec.get("limit_up_time") or "").strip(),
                "seal_money": _fnum(rec.get("seal_money")),
                "chg_pct": _fnum(rec.get("chg_pct")),
                "is_st": bool(int(_fnum(rec.get("is_st"))) or 0),
                "reason": (rec.get("reason") or "").strip(),
                "unique_high": bool(int(_fnum(rec.get("unique_high"))) or 0) if has_unq else False,
                "follower_count": int(_fnum(rec.get("follower_count"))) if has_flw else 0,  # v0.78 C 仅记录字段，决策用动态 follower（_dyn_theme_status）
                "theme": theme,
                "theme_count": int(_fnum(rec.get("theme_count"))) if has_theme else 0,      # v0.78 C 仅记录字段，决策用 alive_count/max_board_dyn
                "theme_max_board": int(_fnum(rec.get("theme_max_board"))) if has_theme else 0,  # v0.78 C 仅记录字段，决策用 alive_count/max_board_dyn
                "theme_rank": int(_fnum(rec.get("theme_rank"))) if has_theme else 0,
                "themes": themes,
            }
        if merge and g.zt_lianban:
            # v0.79 防收缩护栏：新文件行数 < 现有 50% -> 视为异常覆盖，完全保留现有
            if len(_new) * 2 < len(g.zt_lianban):
                log.info("[zt-lianban] merge skip(shrink %d<50%% of %d) %s keep=%d" % (len(_new), len(g.zt_lianban), fp, len(g.zt_lianban)))
                return len(g.zt_lianban)
            _old = set(g.zt_lianban)
            g.zt_lianban.update(_new)   # 新文件 code 字段胜出；旧有但新文件缺失的 code 保留
            _keep = len(_old - set(_new))
            n_unq = _annotate_zt_uniqueness()
            _build_zt_theme_index()
            log.info("[zt-lianban] merged %s old=%d new=%d total=%d keep_old=%d unique_high=%d themed=%d"
                     % (fp, len(_old), len(_new), len(g.zt_lianban), _keep, n_unq, themed))
            return len(g.zt_lianban)
        else:
            g.zt_lianban = _new
            n_unq = _annotate_zt_uniqueness()   # v0.34b 兜底标注；v0.37 文件权威列优先
            _build_zt_theme_index()             # v0.55 静态锚：题材索引（themes 全量）
            log.info("[zt-lianban] loaded %s -> %d unique_high=%d themed=%d"
                     % (fp, len(g.zt_lianban), n_unq, themed))
            return len(g.zt_lianban)
    except Exception as e:
        log.info("[zt-lianban] skip(invalid) %s: %r" % (fp, e))
        return len(g.zt_lianban)

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
    # v0.38：文件带权威题材列时按主题材分组（对齐 AXquant theme.buckets 口径）；
    # 缺列仍回退涨停原因首 token 分组。
    use_theme = bool(getattr(g, 'zt_theme_authoritative', False))
    groups = {}
    for code, rec in zt.items():
        if use_theme:
            key = str(rec.get('theme') or '').strip()
        else:
            reason = str(rec.get('reason') or '')
            toks = [t.strip() for t in reason.replace('+', ' ').replace('、', ' ').replace(',', ' ').replace('，', ' ').replace('/', ' ').replace('；', ' ').split() if t.strip()]
            key = toks[0] if toks else ''
        if not key:
            key = '__noboard__' + str(code)
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


def _build_zt_theme_index():
    # v0.55 静态锚（docs/41 §2.1）：按 themes 全量列表建题材索引，交叉题材不漏归；
    # 无 themes 列时用单一 theme 字段兜底。theme_rank 取成员权威名次最大值。
    g.zt_theme = {}
    g.zt_themes_of = {}
    zt = getattr(g, 'zt_lianban', {}) or {}
    for code, rec in zt.items():
        names = [t.strip() for t in str(rec.get('themes') or '').split('|') if t.strip()]
        if not names:
            single = str(rec.get('theme') or '').strip()
            if single:
                names = [single]
        g.zt_themes_of[code] = names
        for name in names:
            b = g.zt_theme.setdefault(name, {'members': set(), 'max_board': 0, 'count': 0, 'rank': 0})
            b['members'].add(code)
    for name, b in g.zt_theme.items():
        hs = [int(zt[c].get('board_cnt') or 0) for c in b['members']]
        b['max_board'] = max(hs) if hs else 0
        b['count'] = len(b['members'])
        rk = [int(zt[c].get('theme_rank') or 0) for c in b['members']]
        b['rank'] = max(rk) if rk else 0


def _zt_themes_of(sec):
    return list((getattr(g, 'zt_themes_of', {}) or {}).get(sec) or [])


def _dyn_theme_status():
    # v0.55 动态修正层（docs/41 §2.2）：T-1 题材索引 + 今日实时（_today_zt 续板 /
    # _limitup_days 动态身位）重算每题材的存活最高身位、唯一龙头、存活跟风与实时家数；
    # 15s 节流缓存（成员均来自 T-1 池，last_px/pre_close 读 g.spot 内存，开销小）。
    if not BLS.get('zt_theme_dyn_enabled', True):
        return {}
    now = time.time()
    cache = getattr(g, 'zt_dyn_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
        return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    thememap = getattr(g, 'zt_theme', {}) or {}
    out = {}
    for name, b in thememap.items():
        members = sorted(b['members'])
        lvl_of = {}
        for c in members:
            rec = zt.get(c) or {}
            if not rec or not rec.get('board_cnt'):
                continue
            lvl_of[c] = _limitup_days(c)
        alive = [c for c in lvl_of if _today_zt(c)]
        alive_lvls = [lvl_of[c] for c in alive]
        mx = max(alive_lvls) if alive_lvls else 0   # 只统计存活者，龙头炸板后身位转授
        top = [c for c in alive if lvl_of[c] == mx]
        leader = top[0] if len(top) == 1 else ''
        followers = [c for c in alive if c != leader and lvl_of[c] < mx]
        out[name] = {
            'members': members,
            'max_board_static': int(b.get('max_board') or 0),
            'max_board_dyn': mx,
            'count_static': int(b.get('count') or 0),
            'alive_count': len(alive),
            'rank': int(b.get('rank') or 0),
            'leader': leader,
            'follower_count': len(followers),
        }
    if getattr(g, 'zt_dyn_cache', None) is None:
        g.zt_dyn_cache = {}
    g.zt_dyn_cache['ts'] = now
    g.zt_dyn_cache['data'] = out
    return out


def _dyn_theme_leader(sec):
    # v0.55 sec 是否为任一所属题材的当前唯一最高身位存活者（动态龙头，docs/41 §2.2/§3.2）。
    # 盘中龙头炸板后唯一性可转移到同题材最高身位唯一存活者（静态 unique_high 失效时兜底）。
    st = _dyn_theme_status()
    for name in _zt_themes_of(sec):
        d = st.get(name) or {}
        if d.get('leader') == sec:
            return True
    # v0.56 新题材发酵前排：已确认/高潮题材的存活前排视为动态龙头（docs/42 §3，中位放行/排序共用）
    fm = _dyn_theme_ferment()
    for name in _new_themes_of(sec):
        d = fm.get(name) or {}
        if d.get('front') == sec and d.get('confirmed'):
            return True
    return False


def _zt_theme_sort_bonus(code):
    # v0.55/v0.56 题材强度/身位排序加分（_pool_exp_priority）：动态龙头 + 题材梯队名次 +
    # 新题材发酵（确认成员/前排）；仅参与排序观察、不放大追高（docs/41 §3.4 / docs/42 §3）。
    try:
        # v1.24 跌停题材因子：所属题材/概念跌停 hard -> 排序加分归零；soft -> 扣减（回避/减分消费）
        ld_hit = _ld_theme_hit(code)
        if ld_hit and ld_hit.get('hard'):
            return 0.0
        ld_penalized = bool(ld_hit and int(ld_hit.get('n') or 0) >= int(BLS.get('ld_theme_soft_min', 1)))
        st = _dyn_theme_status()
        fm = _dyn_theme_ferment()
        best = 0.0
        for name in _zt_themes_of(code):
            d = st.get(name) or {}
            v = 0.0
            if d.get('leader') == code:
                v += float(BLS.get('zt_theme_leader_sort_bonus', 1.5) or 1.5)
            rk = int(d.get('rank') or 0)
            if rk > 0:
                v += float(BLS.get('zt_theme_rank_bonus_step', 0.3) or 0.3) * (6 - min(rk, 6))
            fd = fm.get(name) or {}
            if fd.get('confirmed'):
                if fd.get('front') == code:
                    v += float(BLS.get('zt_theme_ferment_front_bonus', 0.8) or 0.8)
                else:
                    v += float(BLS.get('zt_theme_ferment_sort_bonus', 0.5) or 0.5)
            best = max(best, v)
        for name in _new_themes_of(code):
            if name in _zt_themes_of(code):
                continue
            d = fm.get(name) or {}
            if not d or not d.get('confirmed'):
                continue
            if d.get('front') == code:
                best = max(best, float(BLS.get('zt_theme_ferment_front_bonus', 0.8) or 0.8))
            else:
                best = max(best, float(BLS.get('zt_theme_ferment_sort_bonus', 0.5) or 0.5))
        if ld_penalized:
            best = max(0.0, best - float(BLS.get('ld_sort_penalty', 1.5)))
        return best
    except Exception:
        return 0.0


def _new_themes_of(sec):
    # v0.56 盘中新首板题材归属（docs/42 §2.2）：THS 概念 -> T-1 题材桶交集桥接；
    # 无交集建临时桶 THS:<概念名>（收盘复盘回填权威桶）。15s 节流缓存。
    sec = str(sec or '')
    if not sec or not BLS.get('zt_theme_ferment_enabled', True):
        return []
    now = time.time()
    cache = getattr(g, 'zt_new_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data') and sec in cache['data']:
        return list(cache['data'].get(sec) or [])
    thememap = getattr(g, 'zt_theme', {}) or {}
    boards = getattr(g, 'boards', None) or {}
    if not (getattr(g, 'stock_boards', None) or {}):
        # v0.57 无概念映射文件时不落 API（避免 3s tick 帧阻塞）；发酵覆盖缺口单独计数
        return []
    out = []
    for nm in _concept_boards_of(sec):
        nm = str(nm or '').strip()
        if not nm:
            continue
        hit = ''
        for tname, tb in thememap.items():
            members = set(tb.get('members') or [])
            if not members:
                continue
            bm = set(boards.get(nm) or [])
            if bm and (members & bm):
                hit = tname
                break
        if hit:
            if hit not in out:
                out.append(hit)
        else:
            t = 'THS:' + nm
            if t not in out:
                out.append(t)
    if getattr(g, 'zt_new_cache', None) is None:
        g.zt_new_cache = {}
    g.zt_new_cache.setdefault('data', {})[sec] = out
    g.zt_new_cache['ts'] = now
    return out


def _merge_temp_themes(by_theme):
    # v0.57 临时题材桶合并（docs/42 修复 5）：THS:* 桶若概念成员有交集或共享今日新首板，
    # 合并为同一临时题材，避免同一逻辑新题材被拆成多个单成员桶永远达不到 assist_min。
    temp_names = sorted([str(n) for n in by_theme if str(n).startswith('THS:')])
    if len(temp_names) <= 1:
        return
    boards = getattr(g, 'boards', None) or {}
    code_sets = {n: {r[2] for r in by_theme[n]} for n in temp_names}
    parent = {n: n for n in temp_names}
    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def _bmap(nm):
        return set(boards.get(str(nm).split(':', 1)[1]) or [])
    for i in range(len(temp_names)):
        for j in range(i + 1, len(temp_names)):
            a, b = temp_names[i], temp_names[j]
            if (code_sets[a] & code_sets[b]) or (_bmap(a) & _bmap(b)):
                parent[_find(a)] = _find(b)
    groups = {}
    for n in temp_names:
        groups.setdefault(_find(n), []).append(n)
    for names in groups.values():
        if len(names) <= 1:
            continue
        merged = []
        for n in names:
            merged.extend(by_theme.pop(n))
        by_code = {}
        for r in merged:
            cur = by_code.get(r[2])
            if cur is None or (r[0], r[1]) > (cur[0], cur[1]):
                by_code[r[2]] = r
        merged = list(by_code.values())
        best = sorted(names, key=lambda n: (-len(code_sets[n]), n))[0]
        by_theme['THS:' + str(best).split(':', 1)[1]] = merged


def _dyn_theme_ferment():
    # v0.56 盘中新题材发酵状态机（docs/42 §2.3/§2.4）：以 g.first_zt 首触为源，
    # 筛「今日新首板（T-1 不在池）+ 仍封板」；题材归属走 THS 概念桥接（_new_themes_of）。
    # 窗内助攻家数 >= assist_min 且时间跨度 <= window -> confirmed；>= hot_assist -> hot。
    # 前排=存量题材动态龙头（_dyn_theme_status）或全新题材最早触板存活者；龙头炸板可转授。
    if not BLS.get('zt_theme_ferment_enabled', True):
        return {}
    now = time.time()
    cache = getattr(g, 'zt_ferment_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
        return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    base = _dyn_theme_status()
    by_theme = {}
    n_unmapped = 0
    for c, ft in (getattr(g, 'first_zt', None) or {}).items():
        c = str(c or '')
        if not c or not isinstance(ft, dict) or c in zt:
            continue
        # v0.57 不再调 _is_first_board（c not in zt 即首板），避免 tick 决策路径触发 get_price
        if not _today_zt(c):
            continue
        if _is_one_word_open(c):
            continue                     # 一字板不参与助攻/前排竞争（对齐 _board_first_zt）
        ms = _first_zt_ms(c)
        if not ms:
            continue
        seal = float(ft.get('first_seal') or 0.0)
        names = _new_themes_of(c)
        if not names:
            n_unmapped += 1
            continue
        for name in names:
            by_theme.setdefault(name, []).append((ms, seal, c))
    if n_unmapped != getattr(g, 'zt_unmapped_n', 0):
        g.zt_unmapped_n = n_unmapped
        log.info('[ferment] unmapped=%d' % n_unmapped)
    _merge_temp_themes(by_theme)
    win_ms = int(float(BLS.get('zt_theme_ferment_window_min', 25) or 25)) * 60 * 1000
    assist_min = int(BLS.get('zt_theme_ferment_assist_min', 2) or 2)
    hot_assist = int(BLS.get('zt_theme_ferment_hot_assist', 5) or 5)
    seal_min = float(BLS.get('zt_theme_ferment_seal_min', 50000.0) or 0.0)
    prev = getattr(g, 'zt_ferment_stage', None) or {}
    out = {}
    for name, rows in by_theme.items():
        alive = [r for r in rows if _today_zt(r[2])]
        if not alive:
            continue
        alive.sort(key=lambda r: (r[0], -(r[1])))
        bd = base.get(name) or {}
        leader = bd.get('leader') or ''
        max_dyn = int(bd.get('max_board_dyn') or 0)
        assist = len(alive)
        span_ms = max(r[0] for r in alive) - min(r[0] for r in alive)
        # v1.36 滚动窗口：取任意 win_ms 内最大助攻簇（burst），解决上午存活成员拖垮午后新簇跨度的问题；
        # 午后爆发通道按 burst_front（簇内最早触板）识别前排，不沿用全天最早触板。
        burst_count = 0
        burst_span = 0
        burst_front = ''
        if len(alive) >= 1:
            _n = len(alive)
            _best_n = 0
            _best_span = 0
            _best_i = 0
            for _i in range(_n):
                _j = _i
                while _j + 1 < _n and alive[_j + 1][0] - alive[_i][0] <= win_ms:
                    _j += 1
                _c = _j - _i + 1
                _sp = alive[_j][0] - alive[_i][0]
                if _c > _best_n or (_c == _best_n and (_best_n == 0 or _sp < _best_span)):
                    _best_n = _c
                    _best_span = _sp
                    _best_i = _i
            burst_count = _best_n
            burst_span = _best_span
            burst_front = alive[_best_i][2]
        confirmed = burst_count >= assist_min
        stage = 'hot' if (confirmed and burst_count >= hot_assist) else ('confirmed' if confirmed else 'watch')
        front = leader
        front_ms = 0
        seal_ok = True
        if not front or not _today_zt(front):
            # 存量龙头炸板/缺位 -> 存活最高（最早触板）转授；全新题材无存量时同样取最早
            candidates = [r for r in alive if not _is_one_word_open(r[2])]
            if candidates:
                # v0.57 前排封单下限：first_seal<=0 视为无 L2 不拦截；全低于下限时不转授但标记弱
                pool = candidates
                if seal_min > 0:
                    strong = [r for r in candidates if r[1] <= 0 or r[1] >= seal_min]
                    if strong:
                        pool = strong
                    else:
                        seal_ok = False
                pool.sort(key=lambda r: (r[0], -(r[1])))
                front = pool[0][2]
                front_ms = pool[0][0]
                if not leader and not max_dyn:
                    max_dyn = 1
        out[name] = {
            'members': [r[2] for r in alive],
            'assist_count': assist,
            'confirmed': bool(confirmed),
            'stage': stage,
            'front': front,
            'front_first_ms': front_ms,
            'burst_count': burst_count,
            'burst_span_ms': burst_span,
            'burst_front': burst_front,
            'max_board_dyn': max(1, max_dyn),
            'temp': bool(name.startswith('THS:')),
            'span_ms': span_ms,
            'seal_min': seal_min,
            'seal_ok': bool(seal_ok),
        }
        if prev.get(name) != stage:
            log.info('[ferment] %s assist=%d stage=%s front=%s span=%dms' % (
                name, assist, stage, front, span_ms))
        prev[name] = stage
    if getattr(g, 'zt_ferment_stage', None) is None:
        g.zt_ferment_stage = {}
    g.zt_ferment_stage.update({k: v for k, v in prev.items() if k in out})
    if getattr(g, 'zt_ferment_cache', None) is None:
        g.zt_ferment_cache = {}
    g.zt_ferment_cache['ts'] = now
    g.zt_ferment_cache['data'] = out
    return out


def _ferment_front_gate(sec):
    # v0.56/v0.57 新题材首板打板闸门（docs/42 §3）：存量题材的新首板助攻不抢前排（不做打板候选）；
    # 全新题材前排 / 存量题材前排（含龙头炸板转授后的最早存活首板）放行走原闸门。
    # 返回 True=放行, False=跳过, None=不适用（T-1 池成员或非新题材，走原逻辑）。
    try:
        if sec in (getattr(g, 'zt_lianban', {}) or {}):
            return None
        fm = _dyn_theme_ferment()
        themes = _new_themes_of(sec)
        if not themes:
            return None
        known = False
        base = None
        for name in themes:
            d = fm.get(name) or {}
            if not d:
                # v0.57 冷缓存补齐：临时题材首个成员即前排放行；存量题材有存活龙头则助攻不放行
                if name.startswith('THS:'):
                    return True
                if base is None:
                    base = _dyn_theme_status()
                leader = (base.get(name) or {}).get('leader') or ''
                if leader and _today_zt(leader):
                    return False
                continue
            known = True
            if d.get('front') == sec:
                return True
        return False if known else None
    except Exception:
        return None


# ================= v0.65 连板盘中情绪动态（docs/43） =================
# 竞价终态(09:25/09:31) -> 盘中确认(09:30-10:00, 15s 缓存) -> 10:00 冻结(降频监控不归零)。
# 分档：low=首板/一进二（T-1 board_cnt<=1 或今日新首板）；mid=中高位 2-5 板；high=高标（>=6 或权威 unique_high）。
# 状态机：high_continue 高位延续 / high_diverg 高位分歧(兑现预警) / rotate_low 切低位新方向首板 / ice_wait 冰点观望 / watch 样本不足。
def _lb_senti_state():
    # 情绪动态容器（按日重置；同日重启随 _save_state/load_state 恢复）
    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    st = getattr(g, 'lb_senti', None)
    if not isinstance(st, dict):
        st = {}
    if st.get('day') != day:
        st = {'day': day, 'auction': {}, 'mid': {}, 't100': {}, 'cut_seen': {}, 'gate_seen': {}}
        g.lb_senti = st
    st.setdefault('auction', {})
    st.setdefault('mid', {})
    st.setdefault('t100', {})
    st.setdefault('cut_seen', {})
    st.setdefault('gate_seen', {})
    st.setdefault('reject_cnt', {})   # v1.12 方向闸门拒绝计数（heartbeat 审计）
    st.setdefault('ld', {})           # v1.24 竞价-开盘-10:00 跌停题材因子（auction/open/t100）
    return st


def _lb_senti_tier(sec):
    # 分档（docs/43）：low=首板/一进二；mid=中高位 2-5 板；high=高标（>=6 或权威唯一高标）
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        bc = int(zt.get('board_cnt') or 0)
    except Exception:
        bc = 0
    if not zt or bc <= 1:
        return 'low'
    if bc > int(BLS.get('lb_senti_high_max', 5)) or bool(zt.get('unique_high')):
        return 'high'
    return 'mid'


def _lb_senti_t100_passed():
    # 10:00 已过 -> 降频分界（缓存 15s -> 60s，参与缩放不归零）
    return _hhmm() >= '10:00'


def _fill_zt_spot():
    # v1.4 B：竞价情绪全池缺 spot 批量补快照（复用 _elastic_yizi_scan 范式，0 额外逐只串行）
    # v1.8 C：已在 spot 但 open/preclose 缺失的票也重拉并合并字段
    # （2026-10-29 not_ready mid=4/7 low=60/62 根因：仅补 sec not in g.spot，漏掉 open_px=0 的在库票）
    zt = getattr(g, 'zt_lianban', {}) or {}

    def _incomplete(sec):
        s2 = g.spot.get(sec) or {}
        return not (float(s2.get('open_px') or 0.0) > 0 and float(s2.get('preclose_px') or 0.0) > 0)

    _need = [sec for sec in zt if _incomplete(sec)]
    if not _need:
        return 0, []
    try:
        _sn = _get_snapshot_many(_need, len(_need)) or {}
        _got = 0
        for _cc, _dd in _sn.items():
            if not _dd:
                continue
            _old = g.spot.get(_cc) or {}
            if _old:
                _old = dict(_old)
                for _k, _v in _dd.items():
                    if _old.get(_k) in (None, 0, '', 0.0):
                        _old[_k] = _v
                g.spot[_cc] = _old
            else:
                g.spot[_cc] = dict(_dd)
            if not _incomplete(_cc):
                _got += 1
        if _got:
            log.info('[lb-senti] auction 全池补快照 got=%d/%d' % (_got, len(_need)))
        return _got, [sec for sec in _need if _incomplete(sec)]
    except Exception:
        return 0, _need


def _lb_senti_auction():
    # 竞价终态（09:25/09:31）：中高位高开/绿开/一字率 + 低位高开率；纯 g.auction_c/spot 读取，零行情 API
    # v0.78 D：统计前按 _auction_ready 校验 mid/low 就绪率，不足 -> ready=False 不写率（防 09:26 竞价数据未就绪假 0）
    # v1.4 B：缺 spot 批量补快照；就绪率仍不足再补一次重算，输出 ready_detail（mid/low 分别就绪数）
    st = _lb_senti_state()
    zt = getattr(g, 'zt_lianban', {}) or {}
    if not zt:
        st['auction'] = {'ts': time.time(), 'note': 'no_zt_lianban'}
        return st['auction']
    day = str(get_trading_day())

    def _stats():
        mid_n = high_n = low_n = mid_open = mid_green = mid_yizi = low_open = low_yizi = 0
        mid_ready = low_ready = 0
        for sec in zt:
            tier = _lb_senti_tier(sec)
            rdy = _auction_ready(sec)
            c = g.auction_c.get(sec)
            chg = 0.0
            if c and c[0] == day:
                chg = float(c[1] or 0.0)
            else:
                s = g.spot.get(sec) or {}
                pre = float(s.get('preclose_px') or 0.0)
                op = float(s.get('open_px') or 0.0)
                chg = (op / pre - 1.0) * 100.0 if pre > 0 and op > 0 else 0.0
            yizi = _is_one_word_open(sec)
            if tier == 'mid':
                mid_n += 1
                if rdy:
                    mid_ready += 1
                if chg > 0:
                    mid_open += 1
                if chg < 0:
                    mid_green += 1
                if yizi:
                    mid_yizi += 1
            elif tier == 'high':
                high_n += 1
            else:
                low_n += 1
                if rdy:
                    low_ready += 1
                if chg > 0:
                    low_open += 1
                if yizi:
                    low_yizi += 1
        ready_min = float(BLS.get('lb_senti_auction_ready_min', 0.6))
        ready = ((mid_ready >= ready_min * mid_n) if mid_n else True) and ((low_ready >= ready_min * low_n) if low_n else True)
        return {
            'mid_n': mid_n, 'high_n': high_n, 'low_n': low_n,
            'mid_open_rate': (float(mid_open) / mid_n) if mid_n else 0.0,
            'mid_green_rate': (float(mid_green) / mid_n) if mid_n else 0.0,
            'mid_yizi': mid_yizi,
            'mid_yizi_rate': (float(mid_yizi) / mid_n) if mid_n else 0.0,
            'low_open_rate': (float(low_open) / low_n) if low_n else 0.0,
            'low_yizi': low_yizi,
            'ready': ready,
            'ready_detail': {'mid': mid_ready, 'low': low_ready},
        }, ready, mid_n, high_n, low_n

    _got, _missing = _fill_zt_spot()
    out, ready, mid_n, high_n, low_n = _stats()
    if not ready:
        _got2, _missing2 = _fill_zt_spot()
        if _missing2:
            _missing = _missing2
        if _got2:
            out, ready, mid_n, high_n, low_n = _stats()
    if not ready:
        _ready_n = out['ready_detail']['mid'] + out['ready_detail']['low']
        _mid_missing = [c for c in zt if _lb_senti_tier(c) == 'mid' and not _auction_ready(c)]
        _low_missing = [c for c in zt if _lb_senti_tier(c) == 'low' and not _auction_ready(c)]
        _total_n = mid_n + low_n
        _ready_pct = 100.0 * _ready_n / _total_n if _total_n else 100.0
        out = {
            'ts': time.time(),
            'ready': False,
            'ready_detail': out['ready_detail'],
            'ready_pct': _ready_pct,
            'mid_n': mid_n, 'high_n': high_n, 'low_n': low_n,
            'mid_open_rate': None, 'mid_green_rate': None,
            'mid_yizi': out.get('mid_yizi', 0), 'mid_yizi_rate': None,
            'low_open_rate': None, 'low_yizi': out.get('low_yizi', 0),
            'missing': {'mid': _mid_missing[:10], 'low': _low_missing[:10]},
            'note': 'auction_data_not_ready ready=%.0f%%' % _ready_pct,
        }
        st['auction'] = out
        log.info('[lb-senti] auction not_ready mid=%d/%d low=%d/%d ready=%.0f%% -> 不写 open/green/yizi 率; missing=mid:%s low:%s'
                 % (out['ready_detail']['mid'], mid_n, out['ready_detail']['low'], low_n,
                    _ready_pct, ','.join(_mid_missing[:5]), ','.join(_low_missing[:5])))
        return out
    out['ts'] = time.time()
    out['ready'] = True
    st['auction'] = out
    log.info('[lb-senti] auction mid=%d open=%.1f%% green=%.1f%% yizi=%d low=%d open=%.1f%% ready_detail=mid:%d/%d low:%d/%d'
             % (mid_n, out['mid_open_rate'] * 100.0, out['mid_green_rate'] * 100.0,
                out['mid_yizi'], low_n, out['low_open_rate'] * 100.0,
                out['ready_detail']['mid'], mid_n, out['ready_detail']['low'], low_n))
    return out


def _lb_senti_set_phase(st, cand, note, now, force_confirm=False):
    # 状态机滞回（docs/43）：风险升级（rank 增大）需同候选持续 hysteresis_sec 才切换，防单帧抖动；
    # 回暖/持平直接切换。v0.78 A1：force_confirm=True 跳过滞回直接切换（10:00 冻结必落档）；
    # v0.78 A2：10:00 前用 lb_senti_hysteresis_sec_before（30s），10:00 后保持 60s。
    prev = st['mid'].get('phase') or 'watch'
    rank = {'high_continue': 0, 'watch': 1, 'high_diverg': 2, 'rotate_low': 2, 'ice_wait': 3}
    if cand == prev or rank.get(cand, 1) <= rank.get(prev, 1):
        if prev != cand:
            log.info('[lb-senti] phase %s -> %s (%s)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
        return
    if force_confirm:
        log.info('[lb-senti] phase %s -> %s (%s, force 10:00)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
        return
    pend = st.get('risk_pending') or {}
    hyst = float(BLS.get('lb_senti_hysteresis_sec_before', 30.0)) if not _lb_senti_t100_passed() else float(BLS.get('lb_senti_hysteresis_sec', 60.0))
    if pend.get('phase') == cand and now - float(pend.get('ts') or 0) < hyst:
        log.info('[lb-senti] phase %s -> %s (%s, 确认)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
    else:
        st['risk_pending'] = {'phase': cand, 'ts': now}


def _lb_senti_mid(force=False, force_confirm=False):
    # 盘中确认状态机（docs/43）：中高位晋级率/炸板率/封单留存 + 低位承接（发酵新方向）+ 红盘比；
    # 10:00 前 15s 缓存、10:00 后降频 60s（不归零）；force=True 供 10:00 冻结（v0.78 A1 必落档）。
    # v0.78 A3：10:00 前样本门槛 0.3 且绝对下限 3（早盘不因样本不足锁死 watch）。
    if not BLS.get('lb_senti_enabled', True):
        return {}
    now = time.time()
    st = _lb_senti_state()
    if not force:
        cache = getattr(g, 'lb_senti_cache', None) or {}
        ttl = float(BLS.get('lb_senti_cache_sec_after', 60.0) if _lb_senti_t100_passed() else BLS.get('lb_senti_cache_sec', 15.0))
        if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
            return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    mid_pool = [c for c in zt if _lb_senti_tier(c) == 'mid']
    ft = getattr(g, 'first_zt', None) or {}
    touched = [c for c in mid_pool if c in ft]
    alive = [c for c in touched if _today_zt(c)]
    break_n = sum(1 for c in touched if bool(ft.get(c, {}).get('break')))
    sealed_alive = sum(1 for c in alive if not bool(ft.get(c, {}).get('break')))
    ferm = _dyn_theme_ferment()
    new_min = int(BLS.get('lb_senti_new_dir_min', 2))
    new_dir = sum(1 for d in ferm.values() if d.get('temp') and d.get('confirmed')
                  and int(d.get('assist_count') or 0) >= new_min)
    low_assist = sum(int(d.get('assist_count') or 0) for d in ferm.values() if d.get('confirmed'))
    try:
        red = _market_red_ratio()
    except Exception:
        red = None
    promo = (float(len(alive)) / len(touched)) if touched else 0.0
    break_rate = (float(break_n) / len(touched)) if touched else 0.0
    out = {
        'ts': now,
        'hhmm': _hhmm(),
        'mid_pool': len(mid_pool),
        'touch_n': len(touched),
        'alive_n': len(alive),
        'promo': promo,
        'break_n': break_n,
        'break_rate': break_rate,
        'seal_retain': (float(sealed_alive) / len(alive)) if alive else 0.0,
        'low_assist': low_assist,
        'new_dir_n': new_dir,
        'red': red,
        'phase': 'watch',
        'note': '',
    }
    if not mid_pool:
        _lb_senti_set_phase(st, 'watch', 'no_mid_pool', now)
        out['note'] = 'no_mid_pool'
    else:
        if _lb_senti_t100_passed():
            min_touch = max(1, int(len(mid_pool) * float(BLS.get('lb_senti_min_touch_ratio', 0.5))))
        else:
            _ratio = float(BLS.get('lb_senti_min_touch_ratio_before', 0.3))
            _floor = int(BLS.get('lb_senti_min_touch_floor', 3))
            _est = max(1, int(len(mid_pool) * _ratio))
            min_touch = max(_est, _floor) if len(mid_pool) >= _floor else _est   # 池小于 floor 不强制（防小池锁死）
        if len(touched) < min_touch:
            _lb_senti_set_phase(st, 'watch', 'sample_insufficient', now)
            out['note'] = 'sample_insufficient touched=%d/%d' % (len(touched), len(mid_pool))
        else:
            promo_min = float(BLS.get('lb_senti_promo_min', 0.60))
            break_max = float(BLS.get('lb_senti_break_max', 0.20))
            red_cold = float(BLS.get('lb_senti_red_cold', 0.40))
            risk_ok = promo >= promo_min and break_rate <= break_max
            low_ok = low_assist >= new_min or new_dir >= new_min
            if risk_ok:
                if red is not None and red < red_cold and not low_ok:
                    _lb_senti_set_phase(st, 'ice_wait', 'red_cold_weak_low', now, force_confirm)
                    out['note'] = 'red_cold_weak_low'
                else:
                    _lb_senti_set_phase(st, 'high_continue', 'promo_ok', now, force_confirm)
                    out['note'] = 'promo_ok'
            else:
                rot_ok = promo < float(BLS.get('lb_senti_rotation_promo', 0.40)) or break_rate > float(BLS.get('lb_senti_rotation_break', 0.30))
                if low_ok and rot_ok:
                    _lb_senti_set_phase(st, 'rotate_low', 'high_break_low_rotate', now, force_confirm)
                    out['note'] = 'high_break_low_rotate'
                elif low_ok:
                    _lb_senti_set_phase(st, 'high_diverg', 'low_ok_but_break_mild', now, force_confirm)
                    out['note'] = 'low_ok_but_break_mild'
                elif red is not None and red < red_cold:
                    _lb_senti_set_phase(st, 'ice_wait', 'red_cold', now, force_confirm)
                    out['note'] = 'red_cold'
                else:
                    _lb_senti_set_phase(st, 'high_diverg', 'high_break', now, force_confirm)
                    out['note'] = 'high_break'
    out['phase'] = st['mid'].get('phase') or 'watch'
    st['mid'].update(out)
    g.lb_senti_cache = {'ts': now, 'data': out}
    _rc = st.get('reject_cnt') or {}
    _rc_sum = sum(int(v or 0) for v in _rc.values())
    _rc_note = ','.join('%s:%d' % (str(k).split('(')[0], int(v or 0)) for k, v in sorted(_rc.items()))
    _hb = float(BLS.get('lb_senti_heartbeat_sec', 60.0) or 60.0)
    if out['phase'] != st.get('last_log_phase') or now - float(st.get('last_log_ts') or 0) >= _hb:
        st['last_log_phase'] = out['phase']
        st['last_log_ts'] = now
        log.info('[lb-senti] %s phase=%s promo=%.0f%%(alive=%d/%d) break=%.1f%%(n=%d) red=%s low_assist=%d new_dir=%d reject=%d(%s)'
                 % (out['hhmm'], out['phase'], promo * 100.0, len(alive), len(touched),
                    break_rate * 100.0, break_n,
                    ('%.2f' % red) if red is not None else '-', low_assist, new_dir, _rc_sum, _rc_note))
    return out


def _lb_senti_phase():
    # 当前阶段（懒计算 + 缓存；买卖消费统一判定口）
    try:
        if BLS.get('lb_senti_enabled', True):
            d = _lb_senti_mid()
            if d:
                return d
        st = _lb_senti_state()
        return st.get('mid') or {'phase': 'watch'}
    except Exception as e:
        _warn('lb_senti_phase fail %r' % e)
        return {'phase': 'watch'}


def lb_senti_t100_freeze(context):
    # 10:00 定时冻结：强制重算盘中状态 -> 快照持久化；之后降频监控（60s）且参与缩放不归零
    if not BLS.get('lb_senti_enabled', True):
        return
    _set_now(context)
    st = _lb_senti_state()
    try:
        d = _lb_senti_mid(force=True, force_confirm=True) or {}   # v0.78 A1 10:00 冻结必落档
    except Exception as e:
        _warn('lb_senti t100 freeze fail %r' % e)
        d = st.get('mid') or {}
    st['t100'] = {
        'ts': time.time(),
        'hhmm': _hhmm(),
        'phase': st['mid'].get('phase') or 'watch',
        'auction': dict(st.get('auction') or {}),
        'mid': dict(d),
    }
    dir_n = {'attack_high': 0, 'attack_low': 0, 'neutral': 0, 'avoid': 0}
    for _c, _en in (getattr(g, 'exp_file', {}) or {}).items():
        if str((_en or {}).get('side') or '') != 'buy':
            continue
        _k = str(_exp_direction_eval(_c).get('kind') or 'neutral')
        dir_n[_k if _k in dir_n else 'neutral'] += 1
    st['t100']['direction'] = dict(dir_n)
    log.info('[lb-senti] t100 freeze phase=%s promo=%.1f%% break=%.1f%% red=%s low=%d new_dir=%d dir_high=%d dir_low=%d dir_avoid=%d'
             % (st['t100']['phase'], float(d.get('promo') or 0.0) * 100.0,
                float(d.get('break_rate') or 0.0) * 100.0,
                ('%.2f' % d['red']) if d.get('red') is not None else '-',
                int(d.get('low_assist') or 0), int(d.get('new_dir_n') or 0),
                dir_n['attack_high'], dir_n['attack_low'], dir_n['avoid']))
    try:
        _ld_senti_snapshot('t100')   # v1.24 10:00 跌停题材因子冻结
    except Exception:
        pass
    try:
        _senti_hist_touch('t100')   # v1.31 10:00 情绪温度冻结落档
    except Exception as e:
        _warn('senti_hist t100 touch fail: %r' % e)
    _save_state()


def _lb_senti_direction_bonus(sec):
    # v0.71：预期方向分统一由 _exp_direction_eval 计算，禁止与旧 phase 分数重复叠加。
    try:
        return float(_exp_direction_eval(sec).get('score') or 0.0)
    except Exception:
        return 0.0


def _lb_senti_participate_scale():
    # 10:00 后参与优先级缩放（降频不归零）：10:00 前 1.0；10:00 后 lb_senti_participate_scale；
    # 冰点观望再减半（仍不归零，保留低位试错通道）。
    try:
        if not _lb_senti_t100_passed():
            return 1.0
        scale = float(BLS.get('lb_senti_participate_scale', 0.5))
        if _lb_senti_phase().get('phase') == 'ice_wait':
            scale *= 0.5
        return scale
    except Exception:
        return 1.0


def _unq_height_space(sec):
    # v1.13 唯一连板距压制位比例空间（docs/40 连板高度压制，2026-10-29 用户修正）：
    #   space = (height_suppress - 参与目标板数) / height_suppress，>= unq_space_min 才博弈。
    #   参与目标板数 = 权威 T-1 board_cnt + 1（昨日4板参与4进5按5板计：压制5即0%拦截、
    #   压制6即16.7%放行；昨日5板参与5进6按6板计，压制6即0%拦截）。
    # 无压制数据（旧文件/不足 5 日）或非连板 -> 1.0（放行）。
    try:
        st = getattr(g, 'sentiment', None) or {}
        suppress = int(st.get('height_suppress') or 0)
        if suppress <= 0:
            return 1.0
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        if zt:
            cnt = max(1, int(zt.get('board_cnt') or 0) + 1)
        else:
            cnt = max(1, _limitup_days(sec) + 1)
        return (suppress - cnt) / suppress
    except Exception:
        return 1.0


def _is_unique_lianban(sec):
    # v1.2 唯一连板判定（空间闸门用）：权威 unique_high / 动态唯一 / 原题材唯一存活龙头 任一命中
    try:
        zt = ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {})
        if zt.get('unique_high'):
            return True
        if _unique_stand(sec):
            return True
        if _exp_original_theme_leader(sec):
            return True
    except Exception:
        pass
    return False


def _lb_senti_gate_reject(note):
    # v1.12 方向闸门拒绝计数（每原因累计，[lb-senti] heartbeat 输出，审计拦截是否实际生效）
    try:
        st = _lb_senti_state()
        rc = st.setdefault('reject_cnt', {})
        rc[str(note)] = int(rc.get(str(note)) or 0) + 1
    except Exception:
        pass


def _lb_senti_buy_gate(sec):
    # 参与方向闸门（docs/43 + v0.71）：高位分歧/冰点仅低位；切低位默认低位，
    # 允许 T-1 原题材当前唯一存活龙头例外。返回 (allow, note)。
    try:
        ph = _lb_senti_phase().get('phase') or 'watch'
        if ph in ('high_diverg', 'rotate_low', 'ice_wait'):
            if _lb_senti_tier(sec) == 'low':
                return (True, 'low_ok(%s)' % ph)
            if (ph == 'rotate_low' and BLS.get('exp_direction_rotate_leader_exception', True)
                    and _exp_original_theme_leader(sec)):
                return (True, 'origin_unique_leader_ok(rotate_low)')
            _note = 'mid_high_skip(%s)' % ph
            _lb_senti_gate_reject(_note)
            return (False, _note)
        # v1.2 唯一连板空间闸门（docs/40 连板高度压制）：low 档（首板/一进二）天然空间大豁免；
        # 唯一连板距压制位空间 < unq_space_min（默认 15%）-> 不参与（唯一高标空间≈0 自然拦截）
        if BLS.get('unq_space_gate_enabled', True) and _lb_senti_tier(sec) != 'low':
            if _is_unique_lianban(sec):
                sp = _unq_height_space(sec)
                if sp < float(BLS.get('unq_space_min', 0.15)):
                    sup = ((getattr(g, 'sentiment', None) or {}).get('height_suppress') or 0)
                    _note = 'unq_space_skip(space=%.1f%%,suppress=%d)' % (sp * 100.0, sup)
                    _lb_senti_gate_reject(_note)
                    return (False, _note)
        return (True, 'normal(%s)' % ph)
    except Exception:
        return (True, 'normal')


def _exp_original_theme_leader(sec):
    # v0.71：仅识别 T-1 原题材中当前唯一存活、动态最高身位的中高位龙头。
    try:
        if _lb_senti_tier(sec) == 'low':
            return ''
        if not ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}):
            return ''
        dyn = _dyn_theme_status()
        for name in _zt_themes_of(sec):
            d = dyn.get(name) or {}
            if d.get('leader') == sec and int(d.get('max_board_dyn') or 0) >= 2:
                return name
    except Exception:
        pass
    return ''


def _ld_theme_hit(sec, old_themes=None, new_themes=None):
    # v1.24 所属题材/概念跌停命中（消费 _market_ld_senti 全市场归集）：
    #   theme_ld = 昨日涨停池题材桶内跌停（强负反馈，>=1 即 hard）；
    #   concept_ld = 全市场 THS 概念跌停（>=ld_theme_hard_min 才 hard，否则减分）。
    # 数据缺失返回 None，绝不把“无数据”当“无跌停”。
    if not BLS.get('ld_senti_enabled', True):
        return None
    try:
        if _hhmm() < '09:25':
            # 竞价终态前无有效跌停口径（last_px 尚未进入竞价），不消费也不视为无跌停
            return None
        d = _market_ld_senti()
        if not d:
            return None
        old = list(old_themes) if old_themes is not None else _zt_themes_of(sec)
        new = list(new_themes) if new_themes is not None else _new_themes_of(sec)
        theme_ld = d.get('theme_ld') or {}
        concept_ld = d.get('concept_ld') or {}
        n_old = max((int(theme_ld.get(t) or 0) for t in old), default=0) if old else 0
        concepts = []
        for nm in new:
            if str(nm).startswith('THS:'):
                concepts.append(str(nm).split(':', 1)[1])
        if _concept_active():
            concepts.extend(_concept_boards_of(sec))
        n_new = max((int(concept_ld.get(c) or 0) for c in concepts), default=0) if concepts else 0
        n = max(n_old, n_new)
        hard = (n_old >= 1 and bool(BLS.get('ld_zt_ld_hard_enabled', True))) \
            or n_new >= int(BLS.get('ld_theme_hard_min', 2))
        name = ''
        if n_old > 0:
            name = max(old, key=lambda t: int(theme_ld.get(t) or 0))
        elif n_new > 0:
            name = max(concepts, key=lambda c: int(concept_ld.get(c) or 0))
        return {'hard': hard, 'n': n, 'theme': name, 'n_old': n_old, 'n_new': n_new}
    except Exception:
        return None


def _exp_direction_eval(sec):
    # v0.71 预期买入方向裁判：attack_high/attack_low 仅排序 +0.8；avoid 直接不参与。
    # 技术三态 CX/CM/PM/CS 不在此函数内改变，仓位比例也不消费 direction score。
    # v0.72 watch 预确认：样本不足时仍按静态唯一龙头/已确认发酵前排给出进攻方向，
    # 避免开盘 30 分钟方向分全部为 0；high_diverg/ice_wait 仍只放行低位。
    out = {
        'kind': 'neutral', 'score': 0.0, 'hard_skip': False, 'size_mult': 1.0,
        'theme': '', 'role': 'outside', 'stage': 'watch', 'phase': 'watch', 'reason': '',
    }
    if not BLS.get('exp_direction_enabled', True):
        out['reason'] = 'disabled'
        return out
    try:
        ph = _lb_senti_phase().get('phase') or 'watch'
        tier = _lb_senti_tier(sec)
        zt_rec = ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {})
        static_leader = bool(zt_rec.get('unique_high'))
        old_themes = _zt_themes_of(sec)
        new_themes = _new_themes_of(sec)
        dyn = _dyn_theme_status()
        fm = _dyn_theme_ferment()
        hot_rear = ''
        old_leader = ''
        old_front = ''
        old_front_stage = ''
        new_front = ''
        new_front_stage = ''

        for name in old_themes:
            d = dyn.get(name) or {}
            f = fm.get(name) or {}
            if (d.get('leader') == sec or static_leader) and tier in ('mid', 'high'):
                old_leader = old_leader or name
            if f.get('confirmed') and f.get('front') == sec:
                old_front = old_front or name
                old_front_stage = str(f.get('stage') or 'confirmed')
            elif (BLS.get('exp_direction_hot_front_only', True)
                  and f.get('confirmed') and f.get('stage') == 'hot'):
                hot_rear = hot_rear or name

        for name in new_themes:
            if name in old_themes:
                continue
            f = fm.get(name) or {}
            if f.get('confirmed') and f.get('front') == sec:
                new_front = new_front or name
                new_front_stage = str(f.get('stage') or 'confirmed')
            elif (BLS.get('exp_direction_hot_front_only', True)
                  and f.get('confirmed') and f.get('stage') == 'hot'):
                hot_rear = hot_rear or name

        out['phase'] = ph
        bonus = float(BLS.get('exp_direction_attack_bonus', 0.8) or 0.0)
        # watch 阶段不视为“方向不明”：静态/动态唯一龙头与已确认发酵前排仍给进攻分；
        # 但 watch 不做 hard_skip，避免样本不足误杀早盘灵敏度。
        leader_ok = (ph == 'high_continue'
                     or (ph == 'rotate_low' and BLS.get('exp_direction_rotate_leader_exception', True))
                     or ph == 'watch')
        front_ok = (ph not in ('high_diverg', 'ice_wait') or tier == 'low')
        if old_leader and leader_ok:
            _reason = ('origin_leader_watch_preconfirm' if ph == 'watch'
                       else 'origin_leader_rotate_exception' if ph == 'rotate_low'
                       else 'origin_leader_high_continue')
            out.update(kind='attack_high', score=bonus, theme=old_leader, role='leader',
                       stage=(fm.get(old_leader) or {}).get('stage') or 'watch',
                       reason=_reason)
        elif new_front and front_ok:
            _reason = 'new_theme_front_watch' if ph == 'watch' else 'new_theme_front'
            out.update(kind='attack_low', score=bonus, theme=new_front, role='front',
                       stage=new_front_stage, reason=_reason)
        elif old_front and front_ok:
            _kind = 'attack_low' if tier == 'low' else 'attack_high'
            _reason = 'theme_ferment_front_watch' if ph == 'watch' else 'theme_ferment_front'
            out.update(kind=_kind, score=bonus, theme=old_front, role='front',
                       stage=old_front_stage, reason=_reason)
        elif hot_rear and BLS.get('exp_direction_hot_front_only', True):
            out.update(kind='avoid', theme=hot_rear, role='rear', stage='hot',
                       reason='hot_rear')
        elif ph in ('rotate_low', 'high_diverg', 'ice_wait') and tier in ('mid', 'high'):
            out.update(kind='avoid', role='follower', reason='mid_high_%s' % ph)
        elif tier in ('mid', 'high'):
            out['role'] = 'follower'

        # v1.24 跌停题材因子消费：硬回避优先（昨日涨停池题材跌停 >=1 或所属概念跌停 >=hard_min），
        # 软命中只减方向分（默认抵消 attack bonus），全市场跌停扩散再全局减分，均不改仓位规则。
        ld_hit = _ld_theme_hit(sec, old_themes, new_themes)
        if ld_hit and ld_hit.get('hard'):
            out.update(kind='avoid',
                       theme=ld_hit.get('theme') or out.get('theme') or '',
                       reason='theme_limit_down(n=%d,old=%d)' % (ld_hit.get('n'), ld_hit.get('n_old')))
            out['ld_hit'] = ld_hit
        else:
            _ld = _market_ld_senti()
            if ld_hit and int(ld_hit.get('n') or 0) >= int(BLS.get('ld_theme_soft_min', 1)):
                out['score'] = float(out.get('score') or 0.0) - float(BLS.get('ld_theme_penalty', 0.8))
                out['ld_hit'] = ld_hit
                out['ld_penalized'] = True
            if _ld and int(_ld.get('ld_n') or 0) >= int(BLS.get('ld_market_soft_n', 20)):
                out['score'] = float(out.get('score') or 0.0) - float(BLS.get('ld_market_penalty', 0.3))
                out['market_ld_n'] = int(_ld.get('ld_n') or 0)
            out['score'] = max(0.0, out['score'])

        out['hard_skip'] = bool(out['kind'] == 'avoid'
                                and BLS.get('exp_direction_avoid_hard_skip', True))
        if out['kind'] == 'avoid':
            out['score'] = 0.0
        return out
    except Exception as e:
        out['reason'] = 'fallback:%r' % e
        return out


def _exp_direction_log(sec, ctx, action):
    # 方向裁决日志：按 code/kind/reason 每日节流，避免 3s tick 刷屏。
    if not BLS.get('exp_direction_log', True):
        return
    try:
        st = _lb_senti_state()
        key = 'expdir:%s:%s:%s:%s' % (sec, ctx.get('kind'), ctx.get('reason'), action)
        if key in st.setdefault('gate_seen', {}):
            return
        st['gate_seen'][key] = time.time()
        en = ((getattr(g, 'exp_file', {}) or {}).get(sec) or {})
        src = str(en.get('_src') or 'provider')
        log.info('[exp-dir] %s source=%s phase=%s kind=%s score=%.1f size_mult=1.0 role=%s stage=%s theme=%s action=%s reason=%s'
                 % (_sn(sec), src, ctx.get('phase') or '-', ctx.get('kind') or 'neutral',
                    float(ctx.get('score') or 0.0), ctx.get('role') or '-', ctx.get('stage') or '-',
                    ctx.get('theme') or '-', action, ctx.get('reason') or '-'))
    except Exception:
        pass


def _lb_senti_gate_apply(sec, action):
    # v0.78 B 统一参与方向闸门（首板/回封/弹性共用）：low 恒放行（低位试错语义），
    # mid/high 在 rotate_low/high_diverg/ice_wait 下拦截；expected_buy 仍走原入口。
    # 返回 True=可参与；拦截/放行均已打日志（区分「有意低位试错」与漏闸）。
    try:
        if not BLS.get('lb_senti_gate_all_buys_enabled', True):
            return True
        # v1.24 跌停题材因子：所属题材/概念 hard 命中时首板/回封/弹性同样回避（与方向裁判同口径）
        ld_hit = _ld_theme_hit(sec)
        if ld_hit and ld_hit.get('hard'):
            _note = 'theme_ld_hard(n=%d,old=%d)' % (ld_hit.get('n'), ld_hit.get('n_old'))
            _lb_gate_seen(sec, _note, action)
            return False
        allow, note = _lb_senti_buy_gate(sec)
        if not allow:
            _lb_gate_seen(sec, note, action)
            return False
        st = _lb_senti_state()
        key = 'allow:%s:%s' % (action, sec)
        if key not in st.setdefault('gate_seen', {}):
            st['gate_seen'][key] = time.time()
            log.info('[lb-senti] %s %s allow (%s)' % (_sn(sec), action, note))
        return True
    except Exception:
        return True


def _lb_gate_seen(sec, note, action='expected_buy'):
    # 参与方向闸门日志节流：每 (sec, action, note) 每日只打一次（防 tick 高频刷屏）；
    # v0.78 B 增加 action 区分通道（expected_buy/first_board/reboard/elastic）
    try:
        st = _lb_senti_state()
        key = '%s:%s:%s' % (sec, action, note)
        if key in st.setdefault('gate_seen', {}):
            return
        st['gate_seen'][key] = time.time()
        log.info('[lb-senti] %s %s -> skip %s' % (_sn(sec), note, action))
    except Exception:
        pass


# ================= v1.31 云端近期情绪温度历史（docs/40 扩展） =================
# sentiment_latest.csv 为 T-1 情绪基线（只读）；云端盘中/收盘确认写入 sentiment_hist.pkl，
# 独立于 buysell_core_state.pkl，保留最近 10 个交易日。阶段只做方向排序与 P8 兑现参考，
# 不改仓位上限规则。
def senti_hist_fp():
    return get_research_path() + 'sentiment_hist.pkl'


def _senti_hist_paths():
    # 读路径对齐研究根（base/upload_file/data/data_upload_file），写只走主根
    return [r + 'sentiment_hist.pkl' for r in _research_roots()]


def _senti_hist_load():
    # 加载云端近期情绪温度历史；损坏/缺失降级为空（hist_fallback 由 _senti_baseline 兜底）
    g.senti_hist = {}
    for cand in _senti_hist_paths():
        try:
            with open(cand, 'rb') as f:
                data = pickle.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        hist = {}
        for d, r in data.items():
            if not isinstance(r, dict):
                continue
            r2 = dict(r)
            r2['date'] = str(r2.get('date') or d)
            hist[str(d)] = r2
        g.senti_hist = hist
        log.info('[senti-hist] loaded %s -> days=%d' % (cand, len(hist)))
        return len(hist)
    log.info('[senti-hist] file not found (tried %s)' % _senti_hist_paths())
    return 0


def _senti_hist_save():
    # 保留最近 N 个交易日；日期字符串 YYYY-MM-DD 字典序即时间序
    try:
        if not BLS.get('senti_hist_enabled', True):
            return 0
        hist = getattr(g, 'senti_hist', None) or {}
        keep = max(1, int(BLS.get('senti_hist_keep_days', 10) or 10))
        dates = sorted(hist, reverse=True)[:keep]
        out = {d: dict(hist[d]) for d in dates}
        with open(senti_hist_fp(), 'wb') as f:
            pickle.dump(out, f, protocol=2)
        return len(out)
    except Exception as e:
        _warn('senti_hist save fail %r' % e)
        return 0


def _senti_baseline():
    # T-1 情绪基线：sentiment_latest.csv 优先；缺失/坏档回退最近一条历史终态（hist_fallback）
    s = getattr(g, 'sentiment', None)
    if isinstance(s, dict) and (s.get('date') or s.get('ice') is not None or s.get('emotion')):
        out = dict(s)
        out.setdefault('hist_fallback', False)
        return out
    hist = getattr(g, 'senti_hist', None) or {}
    today = str(get_trading_day())
    prev = [r for d, r in sorted(hist.items()) if str(d) < today]
    if prev:
        r = dict(prev[-1])
        flags = set(r.get('stage_flags') or [])
        ice = bool(r.get('ice')) or ('cold' in flags)
        out = {
            'date': str(r.get('date') or ''),
            'ice': ice,
            'ice_streak': int(r.get('ice_streak') or (1 if ice else 0)),
            'warm_days': int(r.get('warm_days') or 0),
            'divergence': bool(r.get('divergence')) or bool(r.get('stage_flags') and 'diverging' in flags),
            'emotion': str(r.get('emotion') or ''),
            'emotion_basis': str(r.get('emotion_basis') or ''),
            'phase': str(r.get('phase') or ''),
            'hist_fallback': True,
        }
        return out
    return {'hist_fallback': True, 'ice': False, 'ice_streak': 0, 'warm_days': 0, 'divergence': False,
            'emotion': '', 'emotion_basis': '', 'phase': '', 'date': ''}


def _senti_theme_zt_n():
    # 题材涨停家数近似（用户确认口径）：T-1 题材桶存活 + 今日新首板助攻，取最大题材
    try:
        dyn = _dyn_theme_status() or {}
        fm = _dyn_theme_ferment() or {}
        best_n = 0; best = ''
        for name in list(dyn) + list(fm):
            n = int((dyn.get(name) or {}).get('alive_count') or 0) \
                + int((fm.get(name) or {}).get('assist_count') or 0)
            if n > best_n:
                best_n = n; best = str(name or '')
        return best_n, best
    except Exception:
        return 0, ''


def _senti_theme_zt_members(theme):
    # v1.32 落档主题涨停清单：T-1 题材桶存活 + 今日新首板助攻（与家数同口径），
    # 供核对 09:25 光伏 11 家 -> 10:00 羊字辈 8 家是轮动还是口径漂移
    try:
        dyn = _dyn_theme_status() or {}
        fm = _dyn_theme_ferment() or {}
        members = list((dyn.get(theme) or {}).get('members') or [])
        for m in (fm.get(theme) or {}).get('members') or []:
            if m not in members:
                members.append(m)
        return members
    except Exception:
        return []


def _theme_first_burst_day():
    # 历史已发生题材首爆（>20 家）的题材名集合；今日首次不算过热（first_burst）
    try:
        hist = getattr(g, 'senti_hist', None) or {}
        today = str(get_trading_day())
        th = float(BLS.get('theme_overheat_zt_min', 20) or 20)
        burst = set()
        for d, r in sorted(hist.items()):
            if str(d) >= today:
                continue
            fb = r.get('first_burst_themes') or []
            if isinstance(fb, str) and fb:
                burst.add(fb)
            elif isinstance(fb, (list, tuple, set)):
                burst.update(str(x) for x in fb)
            if float(r.get('theme_zt_n') or 0) > th:
                t = str(r.get('theme_zt_name') or '').strip()
                if t:
                    burst.add(t)
        return burst
    except Exception:
        return set()


def _senti_stage(force=False):
    # v1.31 阶段判定（15s 缓存）：T-1 基线 + 当日实测（红盘比/题材家数/连板盘中阶段）。
    # flags: cold/deep_ice/warm_confirm_day/warm_continue/first_burst/theme_overheat/diverging
    # 只做方向排序与 P8 兑现参考，不改变仓位上限规则。
    try:
        if not BLS.get('senti_hist_enabled', True):
            return {'ts': time.time(), 'flags': set(), 'note': 'disabled'}
        now = time.time()
        day = str(get_trading_day())
        cache = getattr(g, 'senti_stage_cache', None)
        ttl = float(BLS.get('senti_stage_cache_sec', 15.0) or 15.0)
        if not force and isinstance(cache, dict) and cache.get('day') == day \
                and now - float(cache.get('ts') or 0) < ttl and cache.get('flags') is not None:
            return cache
        base = _senti_baseline()
        hist = getattr(g, 'senti_hist', None) or {}
        rec = hist.get(day) or {}
        flags = set()
        red = rec.get('red')
        if red is None:
            try:
                red = _market_red_ratio()
            except Exception:
                red = None
        base_ice = bool(base.get('ice'))
        streak = max(int(base.get('ice_streak') or 0), 0)
        warm_days = max(int(base.get('warm_days') or 0), 0)
        ice_ratio = float(BLS.get('sentiment_ice_ratio', 0.40) or 0.40)
        warm_min = float(BLS.get('sentiment_warm_min', 0.45) or 0.45)
        warm_base = float(BLS.get('sentiment_warm_base', 0.55) or 0.55)
        decay = float(BLS.get('sentiment_warm_decay', 0.02) or 0.02)
        th = max(warm_min, warm_base - max(streak, 1) * decay)
        if red is None:
            # 无当日实测：非冰点基线软给回暖延续；冰点基线不提前授回暖
            if not base_ice and warm_days > 0:
                flags.add('warm_continue')
        else:
            today_cold = float(red) < ice_ratio
            today_warm = not today_cold and float(red) >= th
            if today_cold:
                flags.add('cold')
                if streak >= int(BLS.get('cold_streak_min', 3) or 3):
                    flags.add('deep_ice')
            elif today_warm:
                if base_ice:
                    flags.add('warm_confirm_day')
                else:
                    flags.add('warm_continue')
        n, theme = _senti_theme_zt_n()
        if n > int(BLS.get('theme_overheat_zt_min', 20) or 20):
            burst = _theme_first_burst_day()
            if theme and theme in burst:
                flags.add('theme_overheat')
            else:
                flags.add('first_burst')
        if bool(base.get('divergence')) \
                or warm_days >= int(BLS.get('warm_taper_start', 3) or 3) \
                or 'theme_overheat' in flags:
            flags.add('diverging')
        try:
            ph = _lb_senti_phase().get('phase') or 'watch'
        except Exception:
            ph = 'watch'
        out = {
            'ts': now, 'day': day, 'flags': flags, 'red': red,
            'cold_streak': streak, 'warm_days': warm_days,
            'theme_zt_n': n, 'theme_zt_name': theme, 'phase': ph,
            'hist_fallback': bool(base.get('hist_fallback')),
            'note': '',
        }
        g.senti_stage_cache = out
        return out
    except Exception as e:
        return {'ts': time.time(), 'flags': set(), 'note': 'fail:%r' % e}


def _senti_hist_touch(stage):
    # 每日幂等更新：auction(09:25/09:26/09:31) / t100(10:00) / final(收盘) 覆盖当日记录；
    # 日期守卫防跨日污染，落档后保留最近 10 个交易日并落盘。
    try:
        if not BLS.get('senti_hist_enabled', True):
            return None
        day = str(get_trading_day())
        hist = getattr(g, 'senti_hist', None)
        if not isinstance(hist, dict):
            hist = {}
            g.senti_hist = hist
        rec = dict(hist.get(day) or {})
        rec['day'] = day
        rec['date'] = day
        base = _senti_baseline()
        for k in ('ice', 'ice_streak', 'warm_days', 'divergence', 'emotion', 'emotion_basis', 'phase'):
            if k not in rec:
                rec[k] = base.get(k)
        try:
            lb = _lb_senti_state()
            au = lb.get('auction') or {}
            if stage in ('auction', 't100', 'final') and au:
                rec['auction'] = {
                    'ts': au.get('ts'),
                    'ready': bool(au.get('ready')),
                    'ready_pct': au.get('ready_pct'),
                    'mid_open_rate': au.get('mid_open_rate'),
                    'mid_green_rate': au.get('mid_green_rate'),
                    'low_open_rate': au.get('low_open_rate'),
                    'mid_yizi_rate': au.get('mid_yizi_rate'),
                }
            if stage == 't100':
                t100 = lb.get('t100') or {}
                if t100:
                    rec['t100'] = {
                        'ts': t100.get('ts'),
                        'phase': t100.get('phase'),
                        'direction': dict(t100.get('direction') or {}),
                    }
            if stage == 'final':
                rec['final_ts'] = time.time()
        except Exception:
            pass
        if rec.get('red') is None:
            try:
                rec['red'] = _market_red_ratio()
            except Exception:
                rec['red'] = None
        n, theme = _senti_theme_zt_n()
        if n > 0:
            rec['theme_zt_n'] = n
            rec['theme_zt_name'] = theme
            rec['theme_zt_list'] = _senti_theme_zt_members(theme)[:20]   # v1.32 落档主题涨停清单
        if n > int(BLS.get('theme_overheat_zt_min', 20) or 20) and theme:
            rec['first_burst_themes'] = [theme]
        hist[day] = rec
        stg = _senti_stage(force=True)
        rec['stage_flags'] = sorted(stg.get('flags') or [])
        rec['stage'] = ','.join(rec['stage_flags']) or 'watch'
        hist[day] = rec
        keep = max(1, int(BLS.get('senti_hist_keep_days', 10) or 10))
        for d in sorted(hist)[:-keep]:
            hist.pop(d)
        _senti_hist_save()
        _lg = getattr(g, 'senti_stage_sell_log', None)
        if not isinstance(_lg, dict):
            _lg = {}
            g.senti_stage_sell_log = _lg
        key = 'touch:%s:%s' % (day, stage)
        if key not in _lg:
            _lg[key] = time.time()
            log.info('[senti-hist] %s %s red=%s theme_zt=%d(%s) members=%s stage=%s' % (
                day, stage,
                ('%.2f' % rec['red']) if rec.get('red') is not None else '-',
                int(rec.get('theme_zt_n') or 0), rec.get('theme_zt_name') or '-',
                ','.join(_snl(rec.get('theme_zt_list') or [])[:10]),
                rec.get('stage') or '-'))
        return rec
    except Exception as e:
        _warn('senti_hist touch fail %r' % e)
        return None


def _lb_cut_round(sec):
    # 当前已兑现轮次；兼容旧版纯 ts 记录（视为已完成 1 轮）
    try:
        st = _lb_senti_state()
        rec = (st.get('cut_seen') or {}).get(sec)
        if isinstance(rec, dict):
            return max(0, int(rec.get('round') or 1))
        if isinstance(rec, (int, float)):
            n = int(rec)
            return 1 if n > 1000000000 else max(1, n)   # 旧版纯时间戳按 1 轮处理
        return 0
    except Exception:
        return 0


def _senti_rear_exempt(sec):
    # 阶段后排清仓豁免：高标/动态唯一/发酵前排/唯一龙头（含原题材唯一存活龙头）
    try:
        if _lb_senti_tier(sec) == 'high':
            return True
        if _dyn_theme_leader(sec):
            return True
        if _dyn_unq_confirmed(sec):
            return True
        fm = _dyn_theme_ferment()
        for name in _new_themes_of(sec):
            d = fm.get(name) or {}
            if d.get('confirmed') and d.get('front') == sec:
                return True
        return False
    except Exception:
        return False


def _lb_senti_cut_hold(sec):
    # P8 中高位兑现指导（docs/43）：高位分歧/切低位 + 持仓为连板中位股（非唯一高标） + 今日晋级失败(未续板)
    # -> 减半兑现；高标/低位/已封板/已兑现不重复触发。返回 (fraction, note) 或 None。
    # v1.31 阶段模式：theme_overheat/diverging 时，中位/后排/杂毛（除唯一龙头/发酵前排/高标豁免）
    # 按轮次逐步减半清仓，仍要求未续板、阶段持续；原 high_diverg/rotate_low+mid 单次口径不变。
    try:
        if not BLS.get('lb_senti_cut_enabled', True):
            return None
        ph = _lb_senti_phase().get('phase') or 'watch'
        if ph not in ('high_diverg', 'rotate_low'):
            return None
        if _today_zt(sec):
            return None                      # 续板封住不兑现
        stg = _senti_stage()
        flags = stg.get('flags') or set()
        stage_mode = bool(flags & {'theme_overheat', 'diverging'}) \
            and bool(BLS.get('stage_rear_round_enabled', True))
        tier = _lb_senti_tier(sec)
        if stage_mode and _senti_rear_exempt(sec):
            return None
        if tier == 'mid':
            pass
        elif stage_mode and tier == 'low':
            pass
        else:
            return None
        st = _lb_senti_state()
        rounds = _lb_cut_round(sec)
        cut = (st.get('cut_seen') or {}).get(sec)
        ts = float(cut.get('ts') or 0.0) if isinstance(cut, dict) else 0.0
        now = time.time()
        if stage_mode:
            if rounds >= max(1, int(BLS.get('stage_rear_max_rounds', 3) or 3)):
                return None
            gap = float(BLS.get('stage_rear_round_gap_sec', 60.0) or 60.0)
            if rounds > 0 and ts and now - ts < gap:
                return None
            frac = float(BLS.get('stage_rear_cut_ratio', 0.5) or 0.5)
            note = 'P8_stage_rear_cut phase=%s stage=%s round=%d' % (
                ph, ','.join(sorted(flags)) or '-', rounds + 1)
        else:
            if rounds > 0:
                return None
            frac = float(BLS.get('lb_senti_cut_half_ratio', 0.5) or 0.5)
            note = 'P8_lb_senti_cut_half phase=%s' % ph
        return (frac, note)
    except Exception:
        return None


def _mark_lb_cut(sec):
    # P8 兑现轮次标记（跨重启持久化，防同日重启后重复卖；旧纯 ts 记录按 1 轮兼容）
    try:
        st = _lb_senti_state()
        st.setdefault('cut_seen', {})[sec] = {'ts': time.time(), 'round': _lb_cut_round(sec) + 1}
        _save_state()
    except Exception:
        pass


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
        log.info('[boards] loaded %s -> boards=%d stocks=%d unified=%s' % (
            cand, len(g.boards), len(g.stock_boards), bool(BLS.get('board_concept_unified', True))))
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
            # v1.2 连板高度压制（docs/40）：近 10 日最高板路径与压制位（唯一连板空间闸门消费；旧表头缺省放行）
            "max_board_10d": int(_fnum(rec.get("max_board_10d"))),
            "max_board_10d_path": (rec.get("max_board_10d_path") or "").strip(),
            "height_suppress": int(_fnum(rec.get("height_suppress"))),
        }
        log.info("[sentiment] loaded %s -> ice=%s streak=%d adv=%.1f%% seal=%.0f%% emotion=%s (date=%s)" % (
            fp, g.sentiment["ice"], g.sentiment["ice_streak"], g.sentiment["advance_rate"],
            g.sentiment["seal_rate"] * 100.0, g.sentiment["emotion"] or "-", g.sentiment["date"]))
        return g.sentiment
    except Exception as e:
        log.info("[sentiment] skip(invalid) %s: %r" % (fp, e))
        return None


def _auction_confirm_log(sec, st, chg, yopen, has, src):
    # v1.32 三态逐票日志：09:25 original 与 09:31/重启 restart_rebuild 可精确比对，幂等去重
    try:
        d = getattr(g, 'auction_confirm_log', None)
        if not isinstance(d, dict):
            d = {}; g.auction_confirm_log = d
        key = '%s|%s|%s|%s' % (str(get_trading_day()), sec, st, src)
        if key in d:
            return
        d[key] = time.time()
        log.info('[auction-confirm] %s status=%s open_chg=%.2f%% yopen=%s has=%d src=%s' % (
            _sn(sec), st, float(chg or 0.0),
            ('%.2f%%' % float(yopen)) if has else '-', int(bool(has)), src))
    except Exception:
        pass


def _synth_pool_expect(src='original_0925'):
    # v0.27 涨停池预期三态：T-1 涨停池标的在竞价后也做三态初步确认——
    #   竞价涨幅>昨日开盘涨幅 = 竞价超预期(pending_exceed,观察)；绿开 = pending_miss(放弃)；其余 pending_meet(等盘中)。
    # 供方文件条目优先不覆盖；批量快照预置 g.auction_c（开盘口径=09:25 竞价价），避免 09:25 逐只 get_trend_data。
    # v1.32 src=original_0925 表示 09:25 原始竞价终态，src=restart_rebuild 表示 09:31 兜底/重启重建，防结果混源。
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
            _auction_confirm_log(code, st, chg, yopen, has, src)
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

def _synth_selfwatch_expect(src='original_0925'):
    # v0.35e 自选股预期三态：对自选股（未在供方/涨停池条目中）在竞价后做三态初步确认，
    # 复用涨停池合成口径——竞价涨幅>昨日开盘涨幅=竞价超预期(观察)、绿开=miss(放弃)、其余=meet(等盘中)。
    # 数据（T 日开盘涨幅 _auction_change / 昨日开盘基准 _yesterday_open_chg）全部云端算法供给，
    # 与持仓股 _hold_exp_init 同源，不依赖供方文件；供方/涨停池条目优先不覆盖。
    # v1.32 src 同涨停池合成口径（original_0925 / restart_rebuild）。
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
            _auction_confirm_log(code, st, chg, yopen, has, src)
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
        bm, has_bm = _auction_benchmark(code)   # v1.27 基准缺失才不判；0/负基均合法
        if not has_bm:
            return PM, actual
        return (CX if actual > bm else PM), actual
    if "miss" in exp_status:
        return (CS if actual < 0 else PM), actual
    return PM, actual   # meet/未标注 -> 等盘中确认

def _resync_buy_entry_type(code):
    # v0.73 开盘重标 side=buy 候选入口类型：一字开板 -> one_word（走封单三态，防 below_vwap 误弃）；
    # 文件标 one_word 但实时已开板 -> 回落 normal。仅改 buy 候选，不动持仓卖出路径。
    if not BLS.get('exp_entry_type_resync', True):
        return str((g.exp.get(code) or {}).get('entry_type') or 'normal')
    en = g.exp_file.get(code) or {}
    if str(en.get('side') or (g.exp.get(code) or {}).get('side') or 'hold') != 'buy':
        return str((g.exp.get(code) or {}).get('entry_type') or en.get('entry_type') or 'normal')
    e = g.exp.setdefault(code, {})
    cur = str(e.get('entry_type') or en.get('entry_type') or 'normal')
    if str(cur).lower().startswith('one_word'):
        cur = 'one_word'
    ow = _is_one_word_open(code)
    if ow and cur != 'one_word':
        e['entry_type'] = 'one_word'
        en['entry_type'] = 'one_word'
        log.info('[exp-rt] %s entry_type=%s -> one_word(开盘重标)' % (_sn(code), cur))
        return 'one_word'
    if not ow and cur == 'one_word':
        e['entry_type'] = 'normal'
        en['entry_type'] = 'normal'
        log.info('[exp-rt] %s entry_type=one_word -> normal(已开板重标)' % _sn(code))
        return 'normal'
    return cur

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
    entry = _resync_buy_entry_type(code)
    exp_status = str(e.get("expected_status") or en.get("expected_status") or "")
    au, _ra = _eval_auction(code)
    e["auction_status"] = au
    if entry == "one_word":
        st, _r = _exp_one_word(code)
        # v1.27 一字/近一字开盘档位：非超预期且竞价涨幅低于涨停幅*0.8（主板+8%/20cm+16%/30cm+24%）判不及预期
        if st not in (AW,) and _auction_ready(code):
            _ac = _auction_change(code)
            _min_open = _limit_pct_by_sec(code) * float(
                BLS.get('one_word_open_meet_ratio', 0.8) or 0.8
            )
            if _ac < _min_open:
                return CS, "one_word_open_below_min(%.1f%%)" % _ac
        if "exceed" in exp_status and st == CM:
            return PM, "seal_wait"      # 一字超预期：封单未超预期(CM)不下单，等封单超预期(CX)才买
        return st, "seal"
    # v1.27 放量烂板/炸板不回封独立三态：红开超预期走盘中确认；小绿符合；大绿/跌停低于
    if _bad_seal_role(code):
        if au == AW:
            return PM, "bad_seal_auction_awaiting"
        if au == PX:
            _t1 = _two_1m_break(code)
            _t2 = _limit_up_within_1m(code)
            if (_t1 or _t2) and not _below_vwap_confirm(code):
                _src = 'two_1m' if _t1 else 'limit_1m'
                return CX, "bad_seal_intraday_exceed_%s" % _src
            if _below_vwap_confirm(code):
                return CS, "below_vwap_weak"
            return PM, "observe_bad_seal_red_open"
        if au == PM:
            return PM, "bad_seal_small_green_meet"
        return CS, "bad_seal_green_open_miss"
    if "exceed" in exp_status:
        # 用户确认逻辑（T+1）：先竞价终态「初判」——竞价超预期才观察；未超预期则放弃（兜底，不再放任盘中买入）
        acon, actual = _confirm_expected(code)
        if acon != CX:
            # 兜底：基准缺失 / 真竞价缺失(actual~-100) / 竞价数据未就绪(actual=0且open未回填) 均不误弃，保持等待；确未达标 -> 放弃
            _bm, _has_bm = _auction_benchmark(code)
            _s0 = g.spot.get(code) or {}
            _op0 = float(_s0.get('open_px') or 0.0)
            # v0.68 B2：actual==0 且数据未就绪(缺前收/无价)不误弃 -> 等待；就绪后按真值判定
            # （修今日 09:30 首帧 4 唯一预判误弃；actual 非 0 真值不受影响）
            if (not _has_bm or actual < -90.0
                    or (actual == 0.0 and (_op0 <= 0 or not _auction_ready(code)))):
                return PM, "await_intraday_confirm"
            return CS, "auction_not_met(%.1f%%)" % actual    # 竞价初判未超预期 -> 放弃
        _t1 = _two_1m_break(code)
        _t2 = _limit_up_within_1m(code)
        if (_t1 or _t2) and not _below_vwap_confirm(code):
            _src = 'two_1m' if _t1 else 'limit_1m'
            return CX, "intraday_exceed_%s(%.1f%%)" % (_src, actual)   # 分时确认超预期(两分钟上攻/一分钟冲涨停) -> 买
        if _below_vwap_confirm(code):
            return CS, "below_vwap_weak"                    # 分时转弱 -> 放弃
        return PM, "observe_auction_exceed %.1f%%" % actual   # 竞价超预期初步确认 -> 观察，等分时
    if "miss" in exp_status:
        return CS, "expect_miss"
    if not _intraday_confirmed_ready(code):
        return PM, "intraday_not_confirmed_ready"   # v1.8 meet/未标注：1m 或评分未就绪 -> 等待，不误发单
    if BLS.get('exp_meet_require_intraday_confirm', True):
        # v1.11 meet/未标注与 exceed 对齐：必须两1m强势或1分钟内触板，且不破 VWAP 才放行；
        # 无分时超预期确认一律等待（2026-10-29 三笔 09:30:04-05 meet 首帧误发单根因）。
        if _below_vwap_confirm(code):
            return CS, "below_vwap_weak"
        _mt1 = _two_1m_break(code)
        _mt2 = _limit_up_within_1m(code)
        if _mt1 or _mt2:
            return CX, "meet_intraday_exceed_%s" % ('two_1m' if _mt1 else 'limit_1m')
        return PM, "meet_wait_intraday_confirm"
    st = _eval_intraday(code, au)[0]
    return st, "intraday"

def _attempt_expected_buy(context, code, direction=None):
    # 统一入口（tick/bar 共用）：超预期确认 -> 发单；确认 miss -> 放弃；否则等待
    dctx = direction if isinstance(direction, dict) else _exp_direction_eval(code)
    if dctx.get('hard_skip'):
        _exp_direction_log(code, dctx, 'skip')
        return None
    if _mid_board_avoid(code):
        _skip_log('mid_avoid', code, 'expected_buy', '[mid-avoid] %s 连板中位股规避(expected_buy)' % _sn(code)); return None
    _lbg, _lbg_note = _lb_senti_buy_gate(code)   # v0.65 连板盘中情绪参与方向闸门（切低位/冰点只放行低位试错）
    if not _lbg:
        _lb_gate_seen(code, _lbg_note, 'expected_buy')
        return None
    if code in (context.portfolio.positions or {}):
        return None
    if code in (g.exp_fired or set()):
        return None
    now = time.time()
    if now - g.buy_log.get(code, 0) < BLS["cold_secs"]:
        return None
    if not trade_open(code):
        return None
    _s0 = (getattr(g, 'spot', None) or {}).get(code) or {}
    _px0 = float(_s0.get('last_px') or 0.0)
    _up0 = float(_s0.get('up_px') or 0.0)
    _kind = 'board'   # v1.26 预期买入统一涨停价打板（删 exp_chase 追涨路径）
    if not _buy_slot_ok(_kind):
        return None   # v1.26 预期买入计入打板类名额
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
        if not _board_first_frame_ok(code):
            _buy_ff_log(code, 'expected', 'wait')
            _skip_log('exp_board', code, 'no_first_frame',
                      '[exp-board] %s %s 已确认但非涨停价首帧成交 -> 等待(不追涨)' % (_sn(code), reason),
                      throttle_sec=5.0)
            return None   # v1.26 不追涨：等涨停价首帧成交后按打板执行
        _buy_ff_log(code, 'expected', 'ok')
        _exp_direction_log(code, dctx, 'allow')
        note = 'exp_rt %s %s dir=%s score=%.1f size_mult=1.0 reason=%s ft_state=%s' % (
            st, reason, dctx.get('kind') or 'neutral', float(dctx.get('score') or 0.0),
            dctx.get('reason') or '-', _ft_state_str(code))
        if not place_expected_order(context, code, note=note):
            return None   # 发单失败 -> 下次重试，不置 fired
        if st == CX and _dyn_unq_confirmed(code):
            log.info('[dyn-unq] %s CX 动态唯一龙头确认 -> 预期买入' % _sn(code))
        _buy_slot_add(code, _kind)
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

def _auction_board_of(sec):
    # v0.73 竞价唯一板块归属：概念板块文件映射优先；概念未命中时回退任意板块成员，
    # 避免“板块映射缺失 -> 竞品=0 -> 假唯一”。
    try:
        for b in _concept_boards_of(sec):
            if _board_members_file(b, 1):
                return b
        if getattr(g, 'stock_boards', None):
            for b in (g.stock_boards.get(sec) or []):
                if _board_members_file(b, 1):
                    return b
    except Exception:
        pass
    return None

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
        b = _auction_board_of(c)
        if b:
            cboard[c] = b
            board_of.setdefault(b, []).append(c)
    for c, en in entries.items():
        st_ = str(en.get('expected_status') or '')
        exceed = 'exceed' in st_
        if BLS.get('dyn_unq_mid_skip', True) and _mid_board_avoid(c):
            log.info('[dyn-unq] %s 中位股不参与唯一预判 -> skip' % _sn(c))
            continue
        b = cboard.get(c)
        mapped = bool(b)
        lvl = _auction_level(c)
        peer_n = 0; peer_ex = 0
        for p in (board_of.get(b) or []) if mapped else []:
            if p == c:
                continue
            if _auction_level(p) != lvl:
                continue
            peer_n += 1
            if 'exceed' in str((g.exp_file.get(p) or {}).get('expected_status') or ''):
                peer_ex += 1
        unique = (exceed and peer_ex == 0
                  and (mapped or not BLS.get('dyn_unq_require_board_map', True)))
        st['auction'][c] = {'exceed': exceed, 'level': lvl, 'peer_cnt': peer_n,
                            'peer_exceed': peer_ex, 'mapped': mapped, 'unique': unique}
        if exceed:
            if mapped:
                log.info('[dyn-unq] 竞价唯一预判 %s 身位=%s 竞品=%d/超预期=%d -> %s' % (
                    _sn(c), lvl, peer_n, peer_ex, '唯一' if peer_ex == 0 else '并列'))
            else:
                log.info('[dyn-unq] %s 板块未映射/成员缺失 -> 不判唯一 (竞品无法评估)' % _sn(c))
    st['auction_done'] = True
    return len(st['auction'])


def _dyn_unq_themes_of(sec):
    # v1.30 盘中唯一主题口径：T-1 题材桶 + 当日新题材（THS 临时桶）并集，交叉题材不漏归。
    out = []
    for t in (_zt_themes_of(sec) + _new_themes_of(sec)):
        if t and t not in out:
            out.append(t)
    return out


def _dyn_unq_theme_pool(theme):
    # v1.30 主题比较池：T-1 题材桶成员 + 今日已首触命中该主题的票（含新首板）；
    # THS:* 无存量时回退概念板块文件。15s 节流缓存，缺行情批量补快照。
    now = time.time()
    cache = getattr(g, 'dyn_unq_pool_cache', None)
    if not isinstance(cache, dict):
        cache = {'ts': 0.0, 'data': {}}
        g.dyn_unq_pool_cache = cache
    cache.setdefault('data', {})
    ttl = float(BLS.get('dyn_unq_pool_cache_sec', 15) or 15)
    ent = cache['data'].get(theme)
    if ent and now - float(ent.get('ts') or 0) < ttl:
        return ent.get('members') or [], float(ent.get('covered') or 0.0)
    members = set()
    tb = (getattr(g, 'zt_theme', {}) or {}).get(theme) or {}
    for m in (tb.get('members') or []):
        m = _norm_sec(m)
        if m:
            members.add(m)
    for c, ft in (getattr(g, 'first_zt', None) or {}).items():
        c = _norm_sec(c)
        if not c or not ft:
            continue
        if theme.startswith('THS:'):
            hit = theme in _new_themes_of(c)
        else:
            hit = theme in _zt_themes_of(c)
        if hit:
            members.add(c)
    if not members and theme.startswith('THS:'):
        name = theme.split(':', 1)[1]
        for m in _board_members_file(name, int(BLS.get('dyn_unq_member_cap', 15))):
            m = _norm_sec(m)
            if m:
                members.add(m)
    members = sorted(m for m in members if m)
    _need = [m for m in members if not (g.spot.get(m) or {}).get('last_px')]
    if _need:
        try:
            _snap = _get_snapshot_many(_need, len(_need)) or {}
            for _m, _d in _snap.items():
                if _d:
                    g.spot[_m] = _d
        except Exception:
            pass
    covered = (sum(1 for m in members if (g.spot.get(m) or {}).get('last_px')) / len(members)) if members else 0.0
    cache['data'][theme] = {'ts': now, 'members': members, 'covered': covered}
    cache['ts'] = now
    return members, covered


def _dyn_unq_peer_chg(sec, d=None):
    # 现价相对前收涨幅；行情缺失返回 None（不视为分离）。
    d = d if d is not None else (g.spot.get(sec) or {})
    try:
        px = float(d.get('last_px') or 0.0)
        pre = float(d.get('preclose_px') or 0.0)
        if px > 0 and pre > 0:
            return (px / pre - 1.0) * 100.0
    except Exception:
        pass
    return None


def _dyn_unq_peer_alive(sec):
    # 今日已首触且当前未破板，才算存活竞品。
    ft = (g.first_zt or {}).get(sec) or {}
    return bool(ft and not ft.get('break'))


def _dyn_unq_peer_separated(sec, peer, my_chg):
    # 竞品分离：今日未首触 / 已破板 / 涨幅落后本票 >= sep_gap；行情缺失不视为分离。
    pft = (g.first_zt or {}).get(peer) or {}
    if not pft:
        return True
    if pft.get('break'):
        return True
    pchg = _dyn_unq_peer_chg(peer)
    if pchg is None or my_chg is None:
        return False
    return (my_chg - pchg) >= float(BLS.get('dyn_unq_sep_chg_gap', 2.0) or 2.0)


def _dyn_unq_surge_raw(sec):
    # v1.30 原始 1m surge：None=数据缺失（供跟风确认 na 占比），不走 _elastic_1m_surge 抹零。
    try:
        dh = _get_ds()
        return dh.cached('m1_surge', sec, float(BLS.get('m1_surge_cache_ttl', 15.0)),
                         lambda: _calc_1m_surge(sec), budget='m1')
    except Exception:
        return None


def _dyn_unq_theme_rank_ok(sec):
    # v1.30 扫板 B 题材强度门：存量题材梯队名次 <= theme_rank_max；临时 THS 桶需发酵 confirmed/hot。
    themes = _dyn_unq_themes_of(sec)
    if not themes:
        return False
    fm = _dyn_theme_ferment()
    mx = int(BLS.get('dyn_unq_theme_rank_max', 3) or 3)
    for name in themes:
        if name.startswith('THS:'):
            d = fm.get(name) or {}
            if d.get('confirmed') or d.get('stage') in ('confirmed', 'hot'):
                return True
        else:
            rk = int((getattr(g, 'zt_theme', {}) or {}).get(name, {}).get('rank') or 0)
            if 0 < rk <= mx:
                return True
    return False


def _dyn_unq_skip_log(sec, theme, reason, extra='', throttle_sec=5.0):
    # v1.30 动态唯一跳过审计：theme/member/covered/in_sample/lvl/same/higher/reason 留痕。
    try:
        _skip_log('dyn_unq', sec, reason,
                  '[dyn-unq-skip] %s theme=%s reason=%s%s' % (
                      _sn(sec), theme or '-', reason, (' ' + extra) if extra else ''),
                  throttle_sec=throttle_sec)
    except Exception:
        pass


def _dyn_unq_eval_uniq(sec, st, now):
    # v1.30 动态唯一重构：以题材桶 + 连板梯队为比较集（T-1 涨停池成员 + 今日已首触/近涨停成员），
    # 唯一 = 主题内最高存活身位且身位>=2；同身位竞品全部分离；覆盖不足/成员不足不判唯一。
    uniq_map = st.setdefault('uniq', {})
    themes = _dyn_unq_themes_of(sec)
    if not themes:
        _dyn_unq_skip_log(sec, '-', 'no_theme')
        uniq_map.pop(sec, None)
        return
    my_lvl = _dyn_level_of(sec, {sec: g.spot.get(sec) or {}})
    if my_lvl < int(BLS.get('dyn_unq_min_level', 2) or 2):
        _dyn_unq_skip_log(sec, ','.join(themes[:3]), 'low_level', 'lvl=%d' % my_lvl)
        uniq_map.pop(sec, None)
        return
    pool = set()
    in_sample = False
    for theme in themes:
        members, covered = _dyn_unq_theme_pool(theme)
        if not members:
            continue
        mset = set(_norm_sec(m) for m in members)
        if _norm_sec(sec) in mset:
            in_sample = True
        pool.update(mset)
    pool = sorted(m for m in pool if m)
    if not in_sample:
        _dyn_unq_skip_log(sec, ','.join(themes[:3]), 'no_in_sample')
        uniq_map.pop(sec, None)
        return
    member_total = len(pool)
    if member_total < int(BLS.get('dyn_unq_min_members', 3) or 3):
        _dyn_unq_skip_log(sec, ','.join(themes[:3]), 'member_low', 'total=%d' % member_total)
        uniq_map.pop(sec, None)
        return
    covered = sum(1 for m in pool if (g.spot.get(m) or {}).get('last_px')) / float(member_total)
    if covered < float(BLS.get('dyn_unq_min_covered', 0.8) or 0.8):
        _dyn_unq_skip_log(sec, ','.join(themes[:3]), 'covered_low',
                          'total=%d covered=%.0f%%' % (member_total, covered * 100))
        uniq_map.pop(sec, None)
        return
    my_chg = _dyn_unq_peer_chg(sec)
    higher = False
    same = []
    for m in pool:
        if m == sec:
            continue
        ml = _dyn_level_of(m, {m: g.spot.get(m) or {}})
        if ml > my_lvl and _dyn_unq_peer_alive(m):
            higher = True
        elif ml == my_lvl and _dyn_unq_peer_alive(m) and not _dyn_unq_peer_separated(sec, m, my_chg):
            same.append(m)
    old = uniq_map.get(sec) or {}
    if higher or same:
        uniq_map[sec] = {'theme': ','.join(themes[:3]), 'uniq': False, 'ts': now,
                         'level': my_lvl, 'members': pool, 'member_total': member_total,
                         'covered': covered, 'higher': higher, 'same': same,
                         'confirm': False, 'confirm_ts': 0, 'follow_ev': False,
                         'last_follow': 0.0, 'surge_cnt': 0}
        log.info('[dyn-unq] %s theme=%s 身位=%d total=%d covered=%.0f%% higher=%d same=%s -> 非唯一(15s重评)' % (
            _sn(sec), uniq_map[sec]['theme'], my_lvl, member_total, covered * 100,
            int(higher), ','.join(_sn(x) for x in same[:5])))
        return
    prev_uniq = bool(old.get('uniq'))
    uniq_map[sec] = {'theme': ','.join(themes[:3]), 'uniq': True, 'ts': now,
                     'level': my_lvl, 'members': pool, 'member_total': member_total,
                     'covered': covered,
                     'unique_ts': old.get('unique_ts') if prev_uniq else now,
                     'separation_ts': old.get('separation_ts') if prev_uniq else now,
                     'confirm': bool(old.get('confirm')),
                     'confirm_ts': old.get('confirm_ts') or 0,
                     'follow_ev': bool(old.get('follow_ev')),
                     'last_follow': float(old.get('last_follow') or 0.0),
                     'surge_cnt': int(old.get('surge_cnt') or 0)}
    log.info('[dyn-unq] %s theme=%s 身位=%d total=%d covered=%.0f%% sep=%.1f%% -> 动态唯一成立' % (
        _sn(sec), uniq_map[sec]['theme'], my_lvl, member_total, covered * 100,
        my_chg if my_chg is not None else -99.0))
def _dyn_unq_eval_follow(sec, st, u):
    # v1.30 跟风确认同主题化：候选 = 主题池内同题材、身位更低、未封板、涨幅>0 前 N；
    # surge 缺失计 na，缺失占比超限不确认；达标家数 >= follower_min -> confirm（15s 节流重评）。
    now = time.time()
    if u.get('confirm'):
        return
    if now - float(u.get('last_follow') or 0) < float(BLS.get('dyn_unq_sep_recheck_sec', 15) or 15):
        return
    u['last_follow'] = now
    first_ts = ((g.first_zt or {}).get(sec) or {}).get('ts') or u.get('ts') or now
    if now - float(first_ts) > float(BLS.get('dyn_unq_follow_win_sec', 300.0)):
        return
    members = u.get('members') or []
    if not members:
        return
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
            up = float(d.get('up_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
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
    top = followers[:int(BLS.get('dyn_unq_surge_top_n', 5))]
    surge_cnt = 0
    na_cnt = 0
    for _chg, m in top:
        try:
            v = _dyn_unq_surge_raw(m)
            if v is None:
                na_cnt += 1
            elif v >= float(BLS.get('dyn_unq_surge_pct', 1.5)):
                surge_cnt += 1
        except Exception:
            na_cnt += 1
    u['surge_cnt'] = surge_cnt
    u['surge_na'] = na_cnt
    if top and float(na_cnt) / float(len(top)) > float(BLS.get('dyn_unq_surge_na_max', 0.5) or 0.5):
        log.info('[dyn-unq] %s 跟风确认 surge_na=%d/%d -> 暂不确认(数据缺失)' % (_sn(sec), na_cnt, len(top)))
        return
    if surge_cnt >= int(BLS.get('dyn_unq_follower_min', 2)):
        u['confirm'] = True
        u['confirm_ts'] = now
        log.info('[dyn-unq] %s 跟风确认 %d家(1m>=%.1f%%) -> 确认' % (
            _sn(sec), surge_cnt, float(BLS.get('dyn_unq_surge_pct', 1.5))))


def _try_elastic_from_sweep_buy(context, sec, px, up, chg, big, themes, warm=False):
    # v1.32 A分流：20cm/北交票当前涨幅>=弹性下限且<涨停价×0.99 -> 弹性语义
    # (10%仓位 + elastic_arb 独立名额 + chase 卖2/上浮限价)；技术条件沿用 sweep A
    # （新题材前排/两1m或1分钟内触板/均价跟随/L2净量>=10%）。回暖确认日最前排排序优先。
    try:
        if not BLS.get('elastic_from_sweep_enabled', True):
            return False
        if not _buy_slot_ok('elastic_arb'):
            _skip_log('slot_skip', sec, 'elastic_arb',
                      '[elastic-sweep] %s reason=slot used=%d/%d'
                      % (_sn(sec), len((getattr(g, 'daily', None) or {}).get('bought_elastic_arb') or []),
                         _buy_slot_limit('elastic_arb')), throttle_sec=60.0)
            return False
        if not _lb_senti_gate_apply(sec, 'elastic'):
            return False
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            _skip_log('elastic_arb_skip', sec, 'cold_or_trade',
                      '[elastic-sweep] %s reason=cold_or_trade' % _sn(sec), throttle_sec=60.0)
            return False
        if _block_sealed_buy(sec):
            _skip_log('elastic_arb_skip', sec, 'sealed',
                      '[elastic-sweep] %s reason=sealed' % _sn(sec), throttle_sec=60.0)
            return False
        limit = _order_limit(sec, 'buy', 'chase')
        if not limit:
            return False
        pre = float((g.spot.get(sec) or {}).get('preclose_px') or 0.0)
        if pre > 0:
            chg = (px / pre - 1.0) * 100.0
        warm_txt = ' stage=warm_confirm_day' if warm else ''
        note = 'elastic_sweep px=%.2f limit=%.2f chg=%.1f%% board_limit=%.2f big=%s src=elastic_arb themes=%s%s' % (
            px, limit or px, chg, up, _fmt_big_ratio(big), themes, warm_txt)
        if place_order(context, sec, 'buy', note=note, mode='chase',
                       ratio=float(BLS.get('elastic_from_sweep_ratio',
                                           BLS.get('ordinary_buy_ratio', 0.10)))):
            _buy_slot_add(sec, 'elastic_arb'); g.buy_log[sec] = now
            log.info('[elastic-sweep] %s order px=%.2f limit=%.2f chg=%.1f%% board_limit=%.2f big=%s src=elastic_arb themes=%s%s' % (
                _sn(sec), px, limit or px, chg, up, _fmt_big_ratio(big), themes, warm_txt))
            _save_state()
            return True
        return False
    except Exception as e:
        _warn('elastic_sweep buy fail: %r' % e)
        return False


def _try_new_theme_sweep(context, event_sec=None):
    # v1.26/v1.34 A 新题材首板提前扫板（09:30-09:40）：新题材前排首板 + 分时拉升均价跟随拉高
    # + L2 净大单占比>=10%；未触板时按 sweep(卖2/上浮封顶涨停价) 扫入，避免涨停价排队。
    # v1.32 20cm/北交票当前涨幅>=弹性下限且<涨停价×0.99 优先归弹性语义（10%仓位+独立名额），
    #        回暖确认日弹性最前排同享排序优先；临板(>=涨停价×0.99)保留 sweep A 打板语义。
    # v1.34 event_sec 由 near 同帧事件派发，跳过全池扫描；None 走帧末全量兜底。
    if not BLS.get('new_theme_sweep_enabled', True):
        return False
    if _min_age() > int(BLS.get('new_theme_sweep_window_min', 10)):
        return False
    if not (_buy_slot_ok('board') or _buy_slot_ok('elastic_arb')):
        return False
    positions = context.portfolio.positions
    now = time.time()
    _src = []
    for _c in (list((getattr(g, 'near_scan', None) or {}).keys()) +
               list(getattr(g, 'pool_static', None) or []) +
               list(getattr(g, 'watch', None) or []) +
               list((getattr(g, 'exp_file', None) or {}).keys())):
        _x = _norm_sec(_c)
        if _x:
            _src.append(_x)
    cands = list(dict.fromkeys(_src))
    if event_sec is not None:
        cands = [_norm_sec(event_sec)]
    elastic_cands = []
    stg = _senti_stage()
    warm_day = 'warm_confirm_day' in (stg.get('flags') or set())
    for sec in cands:
        if sec in positions or sec in g.daily['bought']:
            continue
        if not trade_open(sec):
            continue
        if BLS.get('skip_st_pool', True) and _is_st(sec):
            continue
        if _is_one_word_open(sec) or _block_sealed_buy(sec):
            continue
        if not _is_first_board(sec):
            continue
        if _mid_board_avoid(sec):
            _skip_log('sweep_a', sec, 'mid_avoid',
                      '[sweep-a] %s 连板中位股规避 -> skip' % _sn(sec), throttle_sec=60.0)
            continue
        if _ferment_front_gate(sec) is not True:
            continue                       # 仅新题材前排/最早存活首板
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or up <= 0:
            continue
        pre = float(s.get('preclose_px') or 0.0)
        chg = (px / pre - 1.0) * 100.0 if pre > 0 else 0.0
        elastic_cand = _is_elastic_eligible(sec) and pre > 0 \
            and chg >= _elastic_min_change(sec) - 1e-9 \
            and px < up * float(BLS.get('elastic_from_sweep_limit_ratio', 0.99))
        if not elastic_cand and px >= up * 0.998:
            continue                       # 已触板/现价=涨停价：不扫，改走打板通道
        if not (_two_1m_break(sec) or _limit_up_within_1m(sec)):
            continue                       # 分时拉升（两分钟上攻/一分钟冲涨停）
        if not _vwap_follow_up(sec):
            continue                       # 分时均价跟随拉高
        big = _l2_big_ratio(sec)
        if not _l2_big_ok(sec):
            continue                       # L2 净大单占比>=10%
        if elastic_cand:
            elastic_cands.append((sec, px, up, chg, big))
            continue                       # v1.32 弹性语义：帧末按加分排序统一评估
        if not _buy_slot_ok('board'):
            continue
        if not _lb_senti_gate_apply(sec, 'sweep_a'):
            continue
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            continue
        ld = _ld_theme_hit(sec)
        ld_txt = ('%d/%d' % (int(ld.get('n') or 0), int(ld.get('n_old') or 0))) \
            if isinstance(ld, dict) else 'NA'
        limit = _order_limit(sec, 'buy', 'sweep')
        if not limit:
            continue
        themes = ','.join(_new_themes_of(sec)[:3])
        if place_order(context, sec, 'buy',
                       note='sweep_a px=%.2f limit=%.2f big=%s vwap_follow=1 themes=%s ld=%s' % (
                           px, limit, _fmt_big_ratio(big), themes, ld_txt),
                       mode='sweep', ratio=float(BLS.get('board_buy_budget_ratio', 0.20))):
            _buy_slot_add(sec, 'board'); g.buy_log[sec] = now
            try:
                day = str(get_trading_day())
                sb = getattr(g, 'sweep_a_ld_buy', None)
                if not isinstance(sb, dict):
                    sb = {}; g.sweep_a_ld_buy = sb
                sb[sec] = {'day': day, 'hard': bool(isinstance(ld, dict) and ld.get('hard')),
                           'n': int((ld or {}).get('n') or 0),
                           'n_old': int((ld or {}).get('n_old') or 0)}
            except Exception:
                pass
            log.info('[sweep-a] %s order px=%.2f limit=%.2f big=%s themes=%s ld=%s' % (
                _sn(sec), px, limit, _fmt_big_ratio(big), themes, ld_txt))
            _save_state()
            return True                              # 一帧一单
    if elastic_cands:
        # v1.32 弹性语义候选排序：回暖确认日最前排优先，其次 L2 大单加分与涨幅（一帧一单）
        elastic_cands.sort(
            key=lambda t: (float(BLS.get('warm_confirm_front_bonus', 0.4) or 0.4) if warm_day else 0.0)
                          + _elastic_big_bonus_pts(t[0]) + t[3] / 100.0,
            reverse=True)
        for sec, px, up, chg, big in elastic_cands:
            themes = ','.join(_new_themes_of(sec)[:3])
            if _try_elastic_from_sweep_buy(context, sec, px, up, chg, big, themes, warm=warm_day):
                return True
    return False


def _try_pm_theme_buy(context, event_sec=None):
    # v1.36 午后新题材爆发前排试点（13:00-13:30）：仅消费滚动窗口 confirmed/hot 题材的 burst_front，
    # 技术条件沿用扫板 A（非一字/非封死、分时拉升、均价跟随、L2 净大单>=10%、方向闸非 avoid）。
    # 打板名额可用走 board/sweep（20%）；打板名额已耗尽则快速切前排弹性套利（10%、elastic_arb 独立名额）。
    try:
        if not BLS.get('pm_theme_buy_enabled', True):
            return False
        hm = _hhmm()
        a = str(BLS.get('pm_theme_buy_after_hhmm', '13:00') or '13:00')
        u = str(BLS.get('pm_theme_buy_until_hhmm', '13:30') or '13:30')
        if not (a <= hm < u):
            return False
        if len((getattr(g, 'daily', None) or {}).get('bought') or []) >= int(BLS.get('daily_max_buy', 3)):
            return False
        if not (_buy_slot_ok('board') or _buy_slot_ok('elastic_arb')):
            return False
        positions = context.portfolio.positions
        _src = []
        for _c in (list((getattr(g, 'near_scan', None) or {}).keys()) +
                   list(getattr(g, 'pool_static', None) or []) +
                   list(getattr(g, 'watch', None) or []) +
                   list((getattr(g, 'exp_file', None) or {}).keys())):
            _x = _norm_sec(_c)
            if _x:
                _src.append(_x)
        cands = list(dict.fromkeys(_src))
        if event_sec is not None:
            cands = [_norm_sec(event_sec)]
        fm = _dyn_theme_ferment()
        for sec in cands:
            if sec in positions or sec in ((getattr(g, 'daily', None) or {}).get('bought') or []):
                continue
            if not trade_open(sec):
                continue
            if BLS.get('skip_st_pool', True) and _is_st(sec):
                continue
            if _is_one_word_open(sec) or _block_sealed_buy(sec):
                continue
            if _mid_board_avoid(sec):
                _skip_log('pm_theme', sec, 'mid_avoid',
                          '[pm-theme] %s 连板中位股规避 -> skip' % _sn(sec), throttle_sec=60.0)
                continue
            best = None
            for name in _new_themes_of(sec):
                d = fm.get(name) or {}
                if not d or not d.get('confirmed') or str(d.get('stage') or '') not in ('confirmed', 'hot'):
                    continue
                if d.get('burst_front') == sec or (not d.get('burst_front') and d.get('front') == sec):
                    best = d
                    break
            if best is None:
                _skip_log('pm_theme', sec, 'not_front',
                          '[pm-theme] %s 非午后题材窗口前排 -> skip' % _sn(sec), throttle_sec=60.0)
                continue
            s = g.spot.get(sec) or {}
            px = last_px(sec)
            up = float(s.get('up_px') or 0.0)
            if not px or up <= 0:
                continue
            pre = float(s.get('preclose_px') or 0.0)
            chg = (px / pre - 1.0) * 100.0 if pre > 0 else 0.0
            if px >= up * 0.998:
                _skip_log('pm_theme', sec, 'sealed',
                          '[pm-theme] %s 已触板/封死 -> 不追板单' % _sn(sec), throttle_sec=60.0)
                continue
            if not (_two_1m_break(sec) or _limit_up_within_1m(sec)):
                continue
            if not _vwap_follow_up(sec):
                continue
            big = _l2_big_ratio(sec)
            if not _l2_big_ok(sec):
                _skip_log('pm_theme', sec, 'l2_big_low',
                          '[pm-theme] %s 大单净量=%.2f%%<10%% -> skip' % (
                              _sn(sec), big * 100.0 if big >= 0 else 0.0), throttle_sec=60.0)
                continue
            if not _lb_senti_gate_apply(sec, 'pm_theme'):
                continue
            now = time.time()
            if now - (getattr(g, 'buy_log', None) or {}).get(sec, 0) < BLS['cold_secs']:
                continue
            themes = ','.join(_new_themes_of(sec)[:3])
            ld = _ld_theme_hit(sec)
            ld_txt = ('%d/%d' % (int(ld.get('n') or 0), int(ld.get('n_old') or 0))) \
                if isinstance(ld, dict) else 'NA'
            stage = str(best.get('stage') or '')
            burst = int(best.get('burst_count') or 0)
            span = int(best.get('burst_span_ms') or 0)
            if _buy_slot_ok('board'):
                limit = _order_limit(sec, 'buy', 'sweep')
                if not limit:
                    continue
                if place_order(context, sec, 'buy',
                               note='pm_theme_board px=%.2f limit=%.2f chg=%.1f%% stage=%s burst=%d/%dms themes=%s ld=%s' % (
                                   px, limit, chg, stage, burst, span, themes, ld_txt),
                               mode='sweep',
                               ratio=float(BLS.get('pm_theme_buy_board_ratio', 0.20))):
                    _buy_slot_add(sec, 'board')
                    g.buy_log[sec] = now
                    log.info('[pm-theme] %s order px=%.2f limit=%.2f chg=%.1f%% stage=%s burst=%d/%dms themes=%s ld=%s' % (
                        _sn(sec), px, limit, chg, stage, burst, span, themes, ld_txt))
                    _save_state()
                    return True
            elif _buy_slot_ok('elastic_arb'):
                limit = _order_limit(sec, 'buy', 'chase')
                if not limit:
                    continue
                if place_order(context, sec, 'buy',
                               note='pm_theme_elastic px=%.2f limit=%.2f chg=%.1f%% stage=%s burst=%d/%dms src=elastic_arb themes=%s ld=%s' % (
                                   px, limit, chg, stage, burst, span, themes, ld_txt),
                               mode='chase',
                               ratio=float(BLS.get('pm_theme_buy_ratio', 0.10))):
                    _buy_slot_add(sec, 'elastic_arb')
                    g.buy_log[sec] = now
                    log.info('[pm-theme] %s order px=%.2f limit=%.2f chg=%.1f%% stage=%s burst=%d/%dms src=elastic_arb themes=%s ld=%s' % (
                        _sn(sec), px, limit, chg, stage, burst, span, themes, ld_txt))
                    _save_state()
                    return True
            else:
                _skip_log('slot_skip', sec, 'pm_theme',
                          '[pm-theme] %s 打板/弹性名额均耗尽 -> skip' % _sn(sec), throttle_sec=60.0)
                continue
        return False
    except Exception as e:
        _warn('pm_theme buy fail: %r' % e)
        return False


def _try_dyn_sweep(context, st=None):
    # v1.11/v1.26 B 动态唯一扫板：竞价终态超预期+同身位竞品不及预期(竞价唯一)+开盘上攻冲板(_two_1m_break/
    # _limit_up_within_1m)+跟风确认+现价<涨停价(未封板) -> sweep(卖2/上浮封顶涨停价)扫入；已封板不扫。
    # 生命周期 09:30-10:00（dyn_sweep_window_minute=30，与动态唯一/预期买入窗口对齐）。
    if not BLS.get('dyn_sweep_enabled', True):
        return
    if _min_age() > int(BLS.get('dyn_sweep_window_minute', 30)):
        return
    if not _buy_slot_ok('board'):   # v1.14 竞价唯一扫板计入打板类
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
        if not _dyn_unq_theme_rank_ok(sec):
            _skip_log('sweep_b', sec, 'theme_rank',
                      '[sweep-b] %s 题材强度不足(rank>%d或新题材未确认) -> skip' % (
                          _sn(sec), int(BLS.get('dyn_unq_theme_rank_max', 3))),
                      throttle_sec=60.0)
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
        limit = _order_limit(sec, 'buy', 'sweep')
        if not limit:
            log.info('[sweep-b] %s sealed -> no sweep' % _sn(sec))
            continue
        if place_order(context, sec, 'buy',
                       note='sweep_b px=%.2f limit=%.2f 跟风%d家' % (
                           px, limit, (st.get('uniq', {}).get(sec) or {}).get('surge_cnt', 0)),
                       mode='sweep', ratio=float(BLS.get('dyn_sweep_budget_ratio', 0.20))):
            _buy_slot_add(sec, 'board'); g.buy_log[sec] = now
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
                if now - float(u.get('ts') or 0) < float(BLS.get('dyn_unq_sep_recheck_sec', 15) or 15):
                    continue                       # v1.30 非唯一 15s 重评（竞品炸板/分离可转唯一）
                u['ts'] = now
            if u is None or u.get('uniq') is False:
                _dyn_unq_eval_uniq(sec, st, now)   # A 动态唯一（首评/重评）
                u = st['uniq'].get(sec)
            if not u or not u.get('uniq'):
                continue
            _dyn_unq_eval_follow(sec, st, u)       # B 跟风确认
        except Exception as e:
            _warn('dyn_unq %s fail %r' % (_sn(sec), e))
    # v1.30 并发唯一上限：按 (-身位, 首触时间) 保留前 N，超出淘汰（防截断式假唯一扩散）。
    active = {s: u for s, u in st.get('uniq', {}).items() if u and u.get('uniq')}
    mx_active = int(BLS.get('dyn_unq_max_active', 3) or 3)
    if len(active) > mx_active:
        rank = sorted(active.items(),
                      key=lambda kv: (-int(kv[1].get('level') or 0),
                                      float(kv[1].get('unique_ts') or 0.0)))
        keep = set(k for k, _ in rank[:mx_active])
        for k in list(active):
            if k not in keep:
                _dyn_unq_skip_log(k, str((active[k] or {}).get('theme') or '-'),
                                  'over_cap', 'active=%d' % len(active), throttle_sec=60.0)
                st['uniq'].pop(k, None)
    _try_dyn_sweep(context, st)                    # B 动态唯一扫板


def _pool_exp_priority(code, direction=None):
    # v0.71 预期候选统一排序：评分 + 动态唯一 + 题材身位 + 方向裁决，其次最早触板。
    try:
        sc = float(score_now(code) or 0.0)
    except Exception:
        sc = 0.0
    dctx = direction if isinstance(direction, dict) else _exp_direction_eval(code)
    if _dyn_unq_confirmed(code):
        sc += float(BLS.get('dyn_unq_sort_bonus', 2.0))   # v0.38 动态唯一龙头确认排序加分
    sc += _zt_theme_sort_bonus(code)                      # v0.55 题材强度/身位排序加分
    sc += float(dctx.get('score') or 0.0) * _lb_senti_participate_scale()   # v0.71 方向奖励，10:00 后缩放不归零
    # v1.31 回暖确认日：已确认前排（attack_high/attack_low）额外排序加分，不放开技术硬条件/仓位
    stg = _senti_stage()
    if 'warm_confirm_day' in (stg.get('flags') or set()) \
            and dctx.get('kind') in ('attack_high', 'attack_low'):
        sc += float(BLS.get('warm_confirm_front_bonus', 0.4) or 0.4)
    act = _first_zt_ms(code) or 1e18   # v0.37 毫秒归一（逐笔 ms 优先, 帧 ts 归一）
    return (-sc, act)


def _tick_buy_event_key(sec, kind):
    # v1.34 同帧事件优先级：复用 _pool_exp_priority（评分+唯一+题材+方向），
    # 最早首触优先；同类事件按 kind 次序，打板类事件优先于近涨停扫板/弹性。
    try:
        prio = _pool_exp_priority(sec)
    except Exception:
        prio = (1e18, 1e18)
    rank = {'firstzt': 0, 'reboard': 1, 'near': 2}.get(kind or '', 9)
    return (prio[0], prio[1], rank)


def _tick_buy_event_seen(sec, kind):
    # v1.34 事件去重：同票同类当日只派发一次（firstzt/near 天然单次；reboard 由全局 fired 兜底）
    try:
        d = getattr(g, 'tick_buy_event_seen', None)
        if not isinstance(d, dict):
            d = {}; g.tick_buy_event_seen = d
        day = str(get_trading_day())
        if d.get('day') != day:
            d.clear(); d['day'] = day
        key = '%s|%s' % (sec, kind or '')
        if key in d:
            return True
        d[key] = time.time()
        return False
    except Exception:
        return False


def _run_tick_buy_events(context, events):
    # v1.34 同帧事件统一派发：firstzt/reboard/near 按评分/最早首触/题材排序，
    # 事件帧内立即评估（6s 首帧窗由 _board_first_frame_ok/reboard fresh 门保证），
    # 避免帧末全量扫描把首帧成交拖到窗口之后；各通道保留名额/方向/冷却/封死门禁。
    if not BLS.get('firstzt_buy_event_enabled', True):
        return
    if not events:
        return
    ev = []
    for e in events:
        sec = e.get('sec') if isinstance(e, dict) else None
        kind = e.get('kind') if isinstance(e, dict) else None
        if not sec:
            continue
        if _tick_buy_event_seen(sec, kind):
            continue
        ev.append((_tick_buy_event_key(sec, kind), kind, sec))
    ev.sort(key=lambda x: x[0])
    _bought = (getattr(g, 'daily', None) or {}).get('bought') or []
    _positions = getattr(context, 'portfolio', None).positions if getattr(context, 'portfolio', None) else {}
    for _prio, kind, sec in ev:
        try:
            if kind == 'firstzt':
                if sec in _positions or sec in _bought:
                    continue
                _try_first_board_buy(context, sec)
                _bought = (getattr(g, 'daily', None) or {}).get('bought') or []
                if sec in _bought:
                    continue
                _try_core_buy_single(context, sec)
                _bought = (getattr(g, 'daily', None) or {}).get('bought') or []
                if sec in _bought:
                    continue
                _attempt_expected_buy(context, sec)
                if _try_pm_theme_buy(context, event_sec=sec) \
                        and BLS.get('tick_event_sweep_one_per_frame', True):
                    continue
            elif kind == 'reboard':
                if not getattr(g, 'reboard_fired', False):
                    _try_reboard_buy(context, event_sec=sec)
            elif kind == 'near':
                placed = bool(_try_new_theme_sweep(context, event_sec=sec))
                if placed and BLS.get('tick_event_sweep_one_per_frame', True):
                    continue
                placed = bool(_try_elastic_arb_buy(context, event_sec=sec))
                if placed and BLS.get('tick_event_sweep_one_per_frame', True):
                    continue
                placed = bool(_try_pm_theme_buy(context, event_sec=sec))
                if placed and BLS.get('tick_event_sweep_one_per_frame', True):
                    continue
        except Exception as e:
            _warn('tick buy event %s %s fail: %r' % (kind or '-', _sn(sec), e))


# ---------- v1.21 每日买入分类闸门 ----------
# 打板类 2 个名额；其它每个策略各自 1 个名额、不共用（用户确认 2026-11-02）。
# v1.26 预期买入统一打板（删 exp_chase 追涨路径），扫板 A/B 计入打板类。
_BUY_STRATEGY_KINDS = ('ma5', 'core', 'elastic_arb', 'elastic_top')
_BUY_SLOT_LIST_KEYS = ('bought', 'bought_board') + tuple('bought_%s' % k for k in _BUY_STRATEGY_KINDS) + ('bought_other', 'legacy_other')


def _new_daily():
    # 新建当日买入状态；旧 bought_other/legacy_other 仅在迁移/未知 kind 兜底时出现
    d = {'bought': [], 'bought_board': [], 'bought_kind': {}, 'sold': []}
    for k in _BUY_STRATEGY_KINDS:
        d['bought_' + k] = []
    return d


def _buy_slot_list_key(kind):
    if kind == 'board':
        return 'bought_board'
    if kind in _BUY_STRATEGY_KINDS:
        return 'bought_' + kind
    return 'bought_other'


def _buy_slot_limit(kind):
    if kind == 'board':
        return int(BLS.get('daily_max_board_buy', 2) or 0)
    lim = (BLS.get('daily_strategy_buy_limit') or {}).get(kind)
    if lim is None:
        lim = int(BLS.get('daily_max_other_buy', 1) or 1)   # 未知/旧口径兜底
    return int(lim or 0)


def _buy_slot_used(kind):
    # 分类占用：打板类 2 个，其它每个策略各自 1 个，互不占用
    _d = getattr(g, 'daily', None)
    if not isinstance(_d, dict):
        return False
    _lst = _d.get(_buy_slot_list_key(kind))
    return isinstance(_lst, list) and len(_lst) >= _buy_slot_limit(kind)


def _buy_slot_ok(kind):
    # 分类上限 + 总闸门双重约束；未成交终态释放后对应分类名额恢复
    if _buy_slot_used(kind):
        return False
    _d = getattr(g, 'daily', None)
    return isinstance(_d, dict) and len(_d.get('bought') or []) < int(BLS.get('daily_max_buy', 3))


def _buy_slot_add(sec, kind):
    _d = getattr(g, 'daily', None)
    if not isinstance(_d, dict):
        _d = _new_daily(); g.daily = _d
    _d.setdefault('bought', []).append(sec)
    _key = _buy_slot_list_key(kind)
    _d.setdefault(_key, []).append(sec)
    _d.setdefault('bought_kind', {})[sec] = kind
    log.info('[slot] %s kind=%s used=%d/%d total=%d/%d' % (
        _sn(sec), kind, len(_d.get(_key) or []), _buy_slot_limit(kind),
        len(_d.get('bought') or []), int(BLS.get('daily_max_buy', 3))))


def _buy_slot_rel(sec):
    # REJECTED/CANCELLED/重启对账释放：全量列表与分类列表同步移除（打板未成交不算占用）
    _d = getattr(g, 'daily', None)
    if not isinstance(_d, dict):
        return
    for _k in _BUY_SLOT_LIST_KEYS:
        _lst = _d.get(_k)
        if isinstance(_lst, list) and sec in _lst:
            _lst.remove(sec)
    _kd = _d.get('bought_kind')
    if isinstance(_kd, dict):
        _kd.pop(sec, None)

def _try_expected_buys(context):
    # 预期买入：tick(3s) 与 handle_data(1m) 共用同一判定/去重，避免双触发
    if _min_age() > int(BLS.get('exp_buy_window_min', 30)):
        return                       # 预期买入窗口：10:00 前（其它类）
    if not g.exp_file or len(g.daily["bought"]) >= BLS["daily_max_buy"]:
        return
    cands = []
    for idx, (code, en) in enumerate(g.exp_file.items()):
        if str(en.get("side") or "") != "buy":
            continue
        dctx = _exp_direction_eval(code)
        if dctx.get('hard_skip'):
            _exp_direction_log(code, dctx, 'skip')
            continue
        cands.append((code, dctx, _pool_exp_priority(code, direction=dctx), idx))
    # v0.71 所有预期来源统一参与方向/评分排序；来源不再天然前置，idx 仅作稳定平局条件。
    cands.sort(key=lambda x: (x[2][0], x[2][1], x[3]))
    for code, dctx, _prio, _idx in cands:
        _attempt_expected_buy(context, code, direction=dctx)
        if len(g.daily["bought"]) >= BLS["daily_max_buy"]:
            return

# ================= 买入 =================
def _ma5_first_5d(sec):
    # 对齐 AXquant：5日内首次回踩 MA5 = 此前 4 个交易日盘中最低均未触及/跌破各自 MA5。
    # 数据不足(少于9根)保守返回 False（与 AXquant 一致）；缺 low 列时用 close 近似。
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
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
    if not _buy_slot_ok('ma5'):     # v1.21 5D低吸独立1个名额
        _skip_log('slot_skip', '__ma5__', 'ma5',
                  '[slot-skip] kind=ma5 used=%d/%d total=%d/%d -> skip entry'
                  % (len((getattr(g, 'daily', None) or {}).get('bought_ma5') or []),
                     _buy_slot_limit('ma5'), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                     int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
        return
    positions = context.portfolio.positions
    day = str(get_trading_day())
    if getattr(g, 'ma5_touch_day', None) != day:
        g.ma5_touch_day = day; g.ma5_touched = set()
    if not isinstance(getattr(g, 'ma5_touched', None), set):
        g.ma5_touched = set(getattr(g, 'ma5_touched', None) or [])
    if getattr(g, 'ma5_lifecycle_day', None) != day:
        g.ma5_lifecycle_day = day; g.ma5_lows = {}; g.ma5_pending = set()
    if not isinstance(getattr(g, 'ma5_lows', None), dict):
        g.ma5_lows = {}
    for sec in _pool():
        if sec in positions:
            continue
        tags = _tags(sec)
        if BLS.get('ma5_core_only', True) and 'CORE' not in tags:
            _skip_log('ma5_skip', sec, 'core_only',
                      '[ma5-skip] %s 非CORE -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue   # 低吸仅对核心(CORE)标签股（对齐 AXquant）
        px = last_px(sec)
        if not px or px <= 0:
            _skip_log('ma5_skip', sec, 'no_px',
                      '[ma5-skip] %s 现价缺失 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue
        second_low = _ma5_second_low(sec, px)
        if _mid_board_avoid(sec):
            _skip_log('mid_avoid', sec, 'ma5', '[mid-avoid] %s 连板中位股规避(ma5)' % _sn(sec)); continue
        if BLS.get('ma5_require_bs', False) and 'BS' not in tags:
            _skip_log('ma5_skip', sec, 'bs_req',
                      '[ma5-skip] %s 无BS标签 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue   # v0.69 默认不要求 BS；保留开关兼容旧口径
        if BLS.get('ma5_first_5d', False) and not _ma5_first_5d(sec):
            _skip_log('ma5_skip', sec, 'first5d',
                      '[ma5-skip] %s 非5日内首次回踩 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue   # 对齐 AXquant：只有 5日内首次回踩 MA5 才触发，防重复低吸
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            _skip_log('ma5_skip', sec, 'cold_or_trade',
                      '[ma5-skip] %s 冷却/不可交易 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue
        ma5 = _ensure_ma5(sec)
        if not ma5:
            g.ma5_pending.add(sec)   # v1.21 日线未就绪待补评，不静默当“未触线”
            _skip_log('ma5_skip', sec, 'ma5_na',
                      '[ma5-skip] %s MA5日线未就绪 -> 待补评(ma5)' % _sn(sec), throttle_sec=30.0)
            continue
        if BLS.get('ma5_second_low_enabled', True):
            ref_px = second_low
            ma5_ref = _ma5_at_price(sec, ref_px) if ref_px else None
        else:
            ref_px = px
            ma5_ref = ma5
        if not ref_px or not ma5_ref:
            _skip_log('ma5_skip', sec, 'no_ref',
                      '[ma5-skip] %s 次低价/MA5基准缺失 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
            continue
        band = abs(float(ref_px) - float(ma5_ref)) / float(ma5_ref)
        if band > float(BLS.get('ma5_touch_band', 0.02)) + 1e-12:
            _skip_log('ma5_skip', sec, 'band',
                      '[ma5-skip] %s 未触线 band=%.2f%% ref=%.2f ma5ref=%.2f' %
                      (_sn(sec), band * 100.0, ref_px, ma5_ref), throttle_sec=60.0)
        if band <= float(BLS.get('ma5_touch_band', 0.02)) + 1e-12:
            score = score_now(sec)
            if not score:
                _skip_log('ma5_skip', sec, 'score_na',
                      '[ma5-skip] %s 评分未就绪 -> 跳过(ma5)' % _sn(sec), throttle_sec=30.0)
                continue   # v0.68 评分未就绪 -> 不评估买入
            if sec in g.ma5_touched:
                _skip_log('ma5_skip', sec, 'touched',
                      '[ma5-skip] %s 当日已评估触线 -> 跳过(ma5)' % _sn(sec), throttle_sec=60.0)
                continue   # v0.69 当日首次触线后不再重复评估
            if score >= float(BLS.get('ma5_buy_score_min', 50.0)) and _buy_red_ok(sec):
                note = ('ma_pullback px=%.2f low2=%.2f ref=%.2f ma5=%.2f ma5ref=%.2f '
                        'band=%.2f%% ma5b4=%.2f score=%.1f l2=%.2f%% red=%.2f tags=%s') % (
                    px, ref_px, ref_px, ma5, ma5_ref, band * 100.0, (_ma5_base4(sec) or 0.0),
                    score, _l2_big_ratio(sec) * 100.0, _red_ratio(sec), ','.join(_tags(sec)))
                if place_order(context, sec, 'buy', note=note, mode='pullback',
                               ratio=float(BLS.get('ma5_buy_ratio', 0.10))):
                    g.ma5_touched.add(sec)
                    _buy_slot_add(sec, 'ma5'); g.buy_log[sec] = now
                    _save_state()
                    if not _buy_slot_ok('ma5'):
                        break
            else:
                if score < float(BLS.get('ma5_buy_score_min', 50.0)):
                    _skip_log('ma5_skip', sec, 'score',
                      '[ma5-skip] %s 触线但评分不足 score=%.1f' % (_sn(sec), score), throttle_sec=60.0)
                else:
                    _skip_log('ma5_skip', sec, 'red',
                      '[ma5-skip] %s 触线但红盘闸不达 red=%.2f' % (_sn(sec), _red_ratio(sec)), throttle_sec=60.0)
                g.ma5_touched.add(sec)   # 首次进入MA5带但评分/风控不达标：当日不再追补


def _core_confirm_ok(sec):
    # v1.26 核心票确认门：盘中超预期确认（两1m强势/1分钟内触板且不破VWAP），
    # 或 L2 净大单占比>=10% 放行（用户确认“有大单净量>=10%可路”）。
    try:
        if _two_1m_break(sec) or _limit_up_within_1m(sec):
            return not _below_vwap_confirm(sec)
        return _l2_big_ok(sec)
    except Exception:
        return False


def try_core_buy(context):
    # 核心票买入（v0.18/v1.26，对齐 AXquant CORE 门禁）：score>=buy_score_min 且 连板<core_max_lianban；
    # 必须满足确认门（盘中超预期确认 或 L2 净量>=10%），且命中涨停价首帧成交时按打板点执行。
    # 一字/封死涨停不排队；tag CORE 已并入打分，本入口补门禁与执行。
    if not BLS.get('core_buy_enabled', True):
        return
    if not _buy_slot_ok('core'):    # v1.21 核心票独立1个名额
        _skip_log('slot_skip', '__core__', 'core',
                  '[slot-skip] kind=core used=%d/%d total=%d/%d -> skip entry'
                  % (len((getattr(g, 'daily', None) or {}).get('bought_core') or []),
                     _buy_slot_limit('core'), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                     int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
        return
    if _min_age() > int(BLS.get('core_buy_window_min', 30)):
        return                       # 核心票买入窗口：10:00 前（其它类）
    for sec in _pool():
        if _try_core_buy_single(context, sec) and not _buy_slot_ok('core'):
            break


def _try_core_buy_single(context, sec):
    # v1.34 核心票单票入口：帧末全池循环与首触同帧事件共用同一门禁
    try:
        if sec in context.portfolio.positions:
            return False
        if 'CORE' not in _tags(sec):
            return False
        if _mid_board_avoid(sec):
            _skip_log('mid_avoid', sec, 'core_buy', '[mid-avoid] %s 连板中位股规避(core_buy)' % _sn(sec)); return False
        if _is_one_word_open(sec):
            return False                       # 一字板（开盘即涨停）不追（对齐 first_board/elastic 排除）
        if _limitup_days(sec) >= int(BLS.get('core_max_lianban', 6)):
            return False
        if BLS.get('core_sealed_skip', True) and _block_sealed_buy(sec):
            return False
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            return False
        px = last_px(sec)
        if not px or px <= 0:
            return False
        if not _core_confirm_ok(sec):
            _skip_log('core_buy', sec, 'confirm',
                      '[core-board] %s 确认门未达(盘中超预期或L2净量>=10%%) -> skip' % _sn(sec),
                      throttle_sec=60.0)
            return False
        if not _board_first_frame_ok(sec):
            _buy_ff_log(sec, 'core', 'wait')
            _skip_log('core_buy', sec, 'no_first_frame',
                      '[core-board] %s 非涨停价首帧成交 -> 等待(不追涨) %s' % (_sn(sec), _ft_state_str(sec)),
                      throttle_sec=60.0)
            return False
        _buy_ff_log(sec, 'core', 'ok')
        score = score_now(sec)
        if not score:
            return False   # v0.68 评分未就绪 -> 不评估买入
        if score >= BLS['buy_score_min'] and _buy_red_ok(sec):
            if place_order(context, sec, 'buy', note='core_buy px=%.2f score=%.1f tags=%s ft=%s' % (
                    px, score, ','.join(_tags(sec)), _ft_state_str(sec)),
                    mode='board', ratio=float(BLS.get('board_buy_budget_ratio', 0.20))):
                _buy_slot_add(sec, 'core'); g.buy_log[sec] = now
                log.info('[core-board] %s order px=%.2f score=%.1f mode=board ft=%s' % (
                    _sn(sec), px, score, _ft_state_str(sec)))
                _save_state()
                return True
        return False
    except Exception as _e:
        _warn('core buy single fail: %r' % _e)
        return False


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


def _ms_epoch(ms):
    # YYYYMMDDHHMMSSmmm 逐笔/快照毫秒 -> epoch 秒（本地时区），解析失败返回 0
    try:
        s = str(int(ms))
        if len(s) < 14:
            return 0.0
        dt = datetime.strptime(s[:14], '%Y%m%d%H%M%S')
        frac = 0.0
        if len(s) > 14:
            frac = float(s[14:17]) / 1000.0
        return dt.timestamp() + frac
    except Exception:
        return 0.0


def _first_zt_ms_epoch(ft):
    # firstzt 真实首笔 epoch（tx/snap ms 优先），缺失回退检测帧 ts
    try:
        ft = ft or {}
        ms = ft.get('ms')
        t = _ms_epoch(ms) if ms else 0.0
        if t:
            return t
        return float(ft.get('ts') or 0.0)
    except Exception:
        return 0.0


def _feed_lag_sec(ft):
    # 检测帧 ts - 真实首笔 tx_ms 的延迟；无真实首笔返回 -1
    try:
        ft = ft or {}
        ms = ft.get('ms')
        if not ms:
            return -1.0
        t = _ms_epoch(ms)
        ts = float(ft.get('ts') or 0.0)
        if not t or not ts:
            return -1.0
        return max(0.0, ts - t)
    except Exception:
        return -1.0


def _tx_lag_warn(sec, ft=None):
    # provider/批处理延迟审计：feed_lag 超阈值打 [tx-lag]，同票 60s 节流
    try:
        ft = ft if isinstance(ft, dict) else (g.first_zt or {}).get(sec)
        lag = _feed_lag_sec(ft)
        warn = float(BLS.get('tx_lag_warn_sec', 10.0) or 10.0)
        if lag < 0 or lag < warn:
            return
        _st = getattr(g, 'tx_lag_stats', None)   # v1.35 日终 [tx-lag-summary] 累计
        if not isinstance(_st, dict):
            _st = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}; g.tx_lag_stats = _st
        _st['cnt'] = int(_st.get('cnt') or 0) + 1
        _st['sum'] = float(_st.get('sum') or 0.0) + float(lag)
        if float(lag) > float(_st.get('max') or 0.0):
            _st['max'] = float(lag)
            _st['sample'] = '%s tx_ms=%s src=%s' % (_sn(sec), ft.get('ms') or '-', ft.get('src') or '-')
        _skip_log('tx_lag', sec, 'lag',
                  '[tx-lag] %s feed_lag=%.2fs tx_ms=%s src=%s' % (
                      _sn(sec), lag, ft.get('ms') or '-', ft.get('src') or '-'),
                  throttle_sec=60.0)
    except Exception:
        pass


def _buy_ff_log(sec, path, gate):
    # 统一首帧门审计：baseline/age/tx_ms/feed_lag/src/break_cnt
    try:
        ft = (g.first_zt or {}).get(sec) or {}
        baseline = str(BLS.get('board_first_frame_baseline', 'ts') or 'ts')
        ts = float(ft.get('ts') or 0.0)
        age = time.time() - ts if ts else -1.0
        lag = _feed_lag_sec(ft)
        log.info('[buy-ff] %s path=%s baseline=%s age=%.2f tx_ms=%s feed_lag=%.2f src=%s bc=%d gate=%s' % (
            _sn(sec), path, baseline, age, ft.get('ms') or '-', lag,
            ft.get('src') or '-', int(ft.get('break_cnt') or 0), gate))
    except Exception:
        pass


def _first_zt_ms(sec):
    # 首触时刻归一（YYYYMMDDHHMMSSmmm 毫秒整数, 与逐笔 business_time / 快照 hsTimeStamp 同格式）：
    # 逐笔/快照 ms 优先；缺省把帧 ts（epoch 秒）归一到同格式, 避免 17 位与 13 位 epoch 混比错序。
    f = (g.first_zt or {}).get(sec) or {}
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


def _board_first_frame_ok(sec, baseline=None, fresh_sec=None):
    # v1.26/v1.34 涨停价首帧成交：现价=涨停价，且首触发生在 board_first_frame_fresh_sec 内。
    # baseline 支持 ts（检测帧，动作基准，灵敏）与 tx（真实首笔，严格审计/回放）。
    # 打板类入口统一用该判定，避免对已封一段/排单靠后的票追板。
    try:
        s = g.spot.get(sec) or {}
        px = last_px(sec)
        up = float(s.get('up_px') or 0.0)
        if not px or up <= 0 or px < up - 1e-9:
            return False
        ft = (g.first_zt or {}).get(sec) or {}
        baseline = baseline or str(BLS.get('board_first_frame_baseline', 'ts') or 'ts')
        fresh = float(fresh_sec if fresh_sec is not None
                      else BLS.get('board_first_frame_fresh_sec', 6.0) or 6.0)
        ts = _first_zt_ms_epoch(ft) if baseline == 'tx' else float(ft.get('ts') or 0.0)
        return bool(ts and time.time() - ts <= fresh)
    except Exception:
        return False


def _ft_state_str(sec):
    # v1.18/v1.34 买入审计：first_zt 的 src/ms/break_cnt/seal/feed_lag 快照（首帧失真与数据延迟定位）
    ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
    if not ft:
        return 'src:- ms:- bc:0 seal:0 lag:-'
    return 'src:%s ms:%s bc:%d seal:%.0f lag:%.2f' % (
        ft.get('src') or '-', ft.get('ms') or '-', int(ft.get('break_cnt') or 0),
        float(ft.get('first_seal') or 0.0), _feed_lag_sec(ft))


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
    if not _buy_slot_ok('board'):   # v1.14 首板打板计入打板类（每日2次）
        return
    if BLS.get('skip_st_pool', True) and _is_st(sec):
        _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股首板拦截(first_board)' % _sn(sec)); return
    if _is_one_word_open(sec):
        return                       # 除一字板
    if not _is_first_board(sec):
        return                       # 仅首板（T-1 无连板）
    if not _lb_senti_gate_apply(sec, 'first_board'):
        return                       # v0.78 B1 统一方向闸（首板 tier=low 恒放行，日志区分有意低位试错）
    _fg = _ferment_front_gate(sec)   # v0.56 新题材发酵闸门：助攻非前排不抢首板
    if _fg is False:
        log.info('[ferment] %s 新题材助攻非前排 -> skip first_board' % _sn(sec)); return
    if _mid_board_avoid(sec):
        _skip_log('mid_avoid', sec, 'first_board', '[mid-avoid] %s 连板中位股规避(first_board)' % _sn(sec)); return
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
    if not _board_first_frame_ok(sec):
        _buy_ff_log(sec, 'first_board', 'wait')
        _skip_log('firstboard', sec, 'no_first_frame',
                  '[firstboard] %s 非涨停价首帧成交 -> 等待(不追涨) %s' % (_sn(sec), _ft_state_str(sec)),
                  throttle_sec=60.0)
        return                       # v1.34 首板统一首帧门（tx 首帧成交豁免封单硬门但仍在新鲜窗内）
    _buy_ff_log(sec, 'first_board', 'ok')
    amt, _cnt = _seal_metrics(sec)   # v0.46 首板封单下限（L2 买一挂单金额, 防假封秒炸）
    seal_min = float(BLS.get('first_board_seal_min', 50000.0))
    _big_r = _l2_big_ratio(sec)   # v0.47 大单加持：占比>=10% 豁免封单下限（预封扫板）
    _ft0 = (g.first_zt or {}).get(sec) or {}
    if _ft0.get('src') != 'tx' and seal_min > 0 and amt > 0 and amt < seal_min and not _l2_big_ok(sec):
        log.info('[firstboard] %s 封单不足 seal=%.0f<%.0f 且无大单加持(big=%.2f%%) -> skip' % (
            _sn(sec), amt, seal_min, _big_r * 100.0 if _big_r >= 0 else 0.0))
        return                       # v1.26 tx 首帧成交豁免封单硬门（保证最快打板）
    s = g.spot.get(sec) or {}
    up = float(s.get('up_px') or 0.0)
    if not up or up <= 0:
        return
    limit = _order_limit(sec, 'buy', 'board')
    if not limit:
        log.info('[firstboard] %s sealed -> skip board queue' % _sn(sec))
        return
    if place_order(context, sec, 'buy', note='first_board_buy px=%.2f limit=%.2f chg=%.1f%% tags=%s ft=%s' % (
        last_px(sec) or 0.0, limit, _sector_chg(sec) * 100.0, ','.join(_tags(sec)), _ft_state_str(sec)), mode='board',
        ratio=BLS.get('board_buy_budget_ratio', 0.20)):
        _buy_slot_add(sec, 'board'); g.buy_log[sec] = now
        if not getattr(g, 'first_board_fired', None):
            g.first_board_fired = set()
        g.first_board_fired.add(sec)
        log.info('[board-feed] %s order limit=%.2f ft=%s' % (_sn(sec), limit, _ft_state_str(sec)))
        _save_state()


def _try_reboard_buy(context, event_sec=None):
    # v0.49/v1.34 回封打板：前排首板/2板 10:00前炸板后回封，大单占比>=10% -> 打板参与（每日全局1次）
    # event_sec 由回封翻转同帧派发；None 走帧末全量扫描兜底。
    if not BLS.get('reboard_buy_enabled', True):
        return
    if _min_age() > int(BLS.get('reboard_until_minute', 30)):
        return
    if getattr(g, 'reboard_fired', False):
        return                                   # 每日全局 1 次
    if not _buy_slot_ok('board'):   # v1.14 回封打板计入打板类（每日2次）
        return
    cands = []
    if event_sec is not None:
        _sec = event_sec
        ft = (getattr(g, 'first_zt', None) or {}).get(_sec)
        if isinstance(ft, dict):
            _ok = True
            if int(ft.get('break_cnt') or 0) < 1 or ft.get('break'):
                _ok = False
            s0 = g.spot.get(_sec) or {}
            last = float(s0.get('last_px') or 0.0); u0 = float(s0.get('up_px') or 0.0)
            if last <= 0 or u0 <= 0 or last < u0 * 0.998:
                _ok = False
            if _is_one_word_open(_sec) or _sec in context.portfolio.positions:
                _ok = False
            fresh = float(BLS.get('board_first_frame_fresh_sec', 6.0) or 6.0)
            if time.time() - float(ft.get('reboard_ts') or 0.0) > fresh:
                _buy_ff_log(_sec, 'reboard', 'wait')
                _ok = False
            if _mid_board_avoid(_sec):
                _ok = False
            if _limitup_days(_sec) > int(BLS.get('reboard_max_lianban', 2)):
                _ok = False
            if _ok:
                cands.append((float(ft.get('reboard_ts') or 0.0), _sec))
    else:
        for sec, ft in (getattr(g, 'first_zt', None) or {}).items():
            if not isinstance(ft, dict):
                continue
            if int(ft.get('break_cnt') or 0) < 1:
                continue
            if ft.get('break'):
                continue                             # 需已回封（未处于破板状态）
            s0 = g.spot.get(sec) or {}
            last = float(s0.get('last_px') or 0.0); u0 = float(s0.get('up_px') or 0.0)
            if last <= 0 or u0 <= 0 or last < u0 * 0.998:
                continue
            if _is_one_word_open(sec) or sec in context.portfolio.positions:
                continue
            fresh = float(BLS.get('board_first_frame_fresh_sec', 6.0) or 6.0)
            if time.time() - float(ft.get('reboard_ts') or 0.0) > fresh:
                continue                             # v1.26 仅回封首帧打板，错过不追
            if _mid_board_avoid(sec):
                continue
            if _limitup_days(sec) > int(BLS.get('reboard_max_lianban', 2)):
                continue                             # 仅首板或2板
            cands.append((float(ft.get('reboard_ts') or 0), sec))
    if not cands:
        return
    cands.sort(key=lambda x: x[0])               # 只打第一个回封
    _ts, sec = cands[0]
    if not _lb_senti_gate_apply(sec, 'reboard'):
        return                       # v0.78 B2 统一方向闸（回封 2 板 tier=mid，切低位/冰点拦截）
    if BLS.get('board_rank_enabled', True):
        rs = _near_limit_cands(_pool())
        if not _board_rank_top3(sec, rs or [sec]):
            _skip_log('reboard', sec, 'non_front', '[reboard] %s 非前排(强度前三) -> skip' % _sn(sec)); return
    amt, _cnt = _seal_metrics(sec)
    seal_min = float(BLS.get('reboard_seal_min', 50000.0))
    big_r = _l2_big_ratio(sec)
    big_ok = _l2_big_ok(sec) and big_r >= float(BLS.get('reboard_l2_big_min', 0.10))
    if not big_ok:
        _skip_log('reboard', sec, 'l2_big_low', '[reboard] %s 大单占比=%.2f%%<%s%% -> skip' % (_sn(sec), big_r * 100.0 if big_r >= 0 else 0.0, float(BLS.get('reboard_l2_big_min', 0.10)) * 100.0)); return
    if seal_min > 0 and amt > 0 and amt < seal_min:
        _skip_log('reboard', sec, 'seal_low', '[reboard] %s 封单不足 seal=%.0f<%.0f -> skip' % (_sn(sec), amt, seal_min)); return
    if _block_sealed_buy(sec):
        return
    _buy_ff_log(sec, 'reboard', 'ok')
    limit = _order_limit(sec, 'buy', 'board')
    if not limit:
        log.info('[reboard] %s sealed -> skip board queue' % _sn(sec)); return
    if place_order(context, sec, 'buy', note='reboard_buy break_cnt=%d l2_big=%.2f%% px=%.2f limit=%.2f' % (
        int(((g.first_zt or {}).get(sec) or {}).get('break_cnt') or 0), big_r * 100.0 if big_r >= 0 else 0.0, last_px(sec) or 0.0, limit), mode='board',
        ratio=BLS.get('board_buy_budget_ratio', 0.20)):
        _buy_slot_add(sec, 'board'); g.buy_log[sec] = time.time()
        g.reboard_fired = True
        _save_state()


def _try_first_board_buy_1m(context):
    # 1m 兜底（回测/丢 tick）：对池内逼近涨停的首板候选补一次首板闸门评估
    if not BLS.get('first_board_buy_enabled', True):
        return
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        if not _buy_slot_ok('board'):   # v1.14 1m 兜底首板同打板类
            return
        if sec in (getattr(g, 'first_board_fired', None) or set()):
            continue
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or not up or px < up * 0.998:
            continue
        if not g.first_zt.get(sec):
            g.first_zt[sec] = {'first_seal': 0.0, 'first_bids': 0, 'ts': time.time(),
                               'break': False, 'day': str(get_trading_day())}   # v1.3 首触交易日戳（防跨日残留）
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
        for b in _concept_boards_of(sec):   # v0.60 统一 THS 概念口径（未加载回退 API）
            cnt[b] += 1
    strong = {b: n for b, n in cnt.items() if n >= int(BLS.get('elastic_arb_min_yizi', 2))}
    c.update(day=day, ts=now, strong=strong)
    log.info('[elastic] yizi=%d strong_boards=%d' % (len(yizi), len(strong)))
    return strong


def _elastic_in_strong_board(sec, strong):
    # 候选属于任一强板块（v0.60 统一 THS 概念口径；未加载回退 API）
    for b in _concept_boards_of(sec):
        if b in strong:
            return True
    return False


def _calc_1m_surge(sec):
    # 最新 1m 柱 (close-open)/open 涨幅 %；无数据返回 0（对齐 AXquant min_1m_surge）
    df = get_price(sec, start_date=None, end_date=None, count=2, frequency='1m')
    if df is None or len(df) < 1:
        return None   # v1.30 None=数据缺失，供跟风确认 surge_na 判定；_elastic_1m_surge 已兼容转 0
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


def _try_elastic_arb_buy(context, event_sec=None):
    # 弹性套利（v0.19 Phase 1，AXquant elastic_arb）：板块一字>=2 情绪爆发 -> 抓同板块 20cm/北交所弹性标的
    # v1.34 event_sec 由 near 同帧事件派发，跳过全池扫描；None 走帧末全量兜底。
    if not BLS.get('elastic_arb_enabled', True):
        return False
    if _min_age() > int(BLS.get('elastic_arb_window_minute', 20)):
        return False                 # 仅开盘后 20 分钟内（09:30-09:50）
    if not _buy_slot_ok('elastic_arb'):   # v1.21 弹性 arb 独立1个名额
        _skip_log('slot_skip', '__elastic_arb__', 'elastic_arb',
                  '[slot-skip] kind=elastic_arb used=%d/%d total=%d/%d -> skip entry'
                  % (len((getattr(g, 'daily', None) or {}).get('bought_elastic_arb') or []),
                     _buy_slot_limit('elastic_arb'), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                     int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
        return False
    strong = _elastic_yizi_scan()
    if not strong:
        return
    positions = context.portfolio.positions
    rank_secs = [c for c in _pool() if _is_elastic_eligible(c)]   # v0.23/v1.6 板块目标：池内 20cm+北交所属板块
    cands = []
    for sec in ([event_sec] if event_sec is not None else _pool()):
        if sec in positions:
            continue
        if not _buy_slot_ok('elastic_arb'):
            _skip_log('slot_skip', sec, 'elastic_arb',
                      '[elastic-arb-skip] %s reason=slot total=%d/%d'
                      % (_sn(sec), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                         int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
            return False
        if not _is_elastic_eligible(sec):
            _skip_log('elastic_arb_skip', sec, 'not_eligible',
                      '[elastic-arb-skip] %s reason=not_eligible' % _sn(sec), throttle_sec=300.0)
            continue                 # v1.6 仅 20cm（300/301/688/689）+ 北交所（8/4/92）
        if not _lb_senti_gate_apply(sec, 'elastic'):
            continue                 # v0.78 B3 统一方向闸（弹性首板 low 恒放行，2 板候选切低位/冰点拦截）
        if not _elastic_in_strong_board(sec, strong):
            _skip_log('elastic_arb_skip', sec, 'not_strong_board',
                      '[elastic-arb-skip] %s reason=not_strong_board boards=%s'
                      % (_sn(sec), ','.join(list(strong.keys())[:4])), throttle_sec=60.0)
            continue                 # 属于强板块
        if BLS.get('board_rank_enabled', True) and not _board_rank_top3(sec, rank_secs or [sec]):
            _skip_log('elastic_arb_skip', sec, 'board_rank',
                      '[elastic-arb-skip] %s reason=board_rank' % _sn(sec), throttle_sec=60.0)
            continue                 # 板块目标：强度前三（v0.23）
        if _is_one_word_open(sec):
            _skip_log('elastic_arb_skip', sec, 'one_word',
                      '[elastic-arb-skip] %s reason=one_word' % _sn(sec), throttle_sec=60.0)
            continue                 # 不追一字
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            _skip_log('elastic_arb_skip', sec, 'no_preclose',
                      '[elastic-arb-skip] %s reason=no_preclose' % _sn(sec), throttle_sec=60.0)
            continue
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > _elastic_max_open_change(sec) + 1e-9:
            _skip_log('elastic_arb_skip', sec, 'open_high',
                      '[elastic-arb-skip] %s reason=open_high open=%.1f%% max=%.1f%%'
                      % (_sn(sec), open_chg, _elastic_max_open_change(sec)), throttle_sec=60.0)
            continue                 # 大幅高开兑现
        px = last_px(sec)
        if not px or px <= 0:
            _skip_log('elastic_arb_skip', sec, 'no_px',
                      '[elastic-arb-skip] %s reason=no_px' % _sn(sec), throttle_sec=60.0)
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg < _elastic_min_change(sec) - 1e-9 or chg > _elastic_max_change(sec) + 1e-9:
            _skip_log('elastic_arb_skip', sec, 'chg_range',
                      '[elastic-arb-skip] %s reason=chg_range chg=%.1f%% min=%.1f%% max=%.1f%%'
                      % (_sn(sec), chg, _elastic_min_change(sec), _elastic_max_change(sec)), throttle_sec=60.0)
            continue                 # 20cm 6~10% / 北交 8~15% 区间（防炸板）
        surge = _elastic_1m_surge(sec)
        if surge < float(BLS.get('elastic_arb_min_1m_surge', 3.0)):
            _skip_log('elastic_arb_skip', sec, '1m_surge',
                      '[elastic-arb-skip] %s reason=1m_surge surge=%.1f%% min=%.1f%%'
                      % (_sn(sec), surge, float(BLS.get('elastic_arb_min_1m_surge', 3.0))), throttle_sec=60.0)
            continue                 # 1m 大阳线力度不足
        big = _l2_big_ratio(sec)
        cands.append((sec, px, chg, open_chg, surge, _elastic_big_bonus_pts(sec), big, bool(_l2_big_ok(sec))))
    cands.sort(key=lambda t: (-(t[5] + t[4]), -t[2]))   # v1.6 大单净量>=10% 进攻加分后按主动度排序
    for sec, px, chg, open_chg, surge, _big_bonus, big, big_ok in cands:
        if not _buy_slot_ok('elastic_arb'):
            _skip_log('slot_skip', sec, 'elastic_arb',
                      '[elastic-arb-skip] %s reason=slot total=%d/%d'
                      % (_sn(sec), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                         int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
            return
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            _skip_log('elastic_arb_skip', sec, 'cold_or_trade',
                      '[elastic-arb-skip] %s reason=cold_or_trade' % _sn(sec), throttle_sec=60.0)
            continue
        if _block_sealed_buy(sec):
            _skip_log('elastic_arb_skip', sec, 'sealed',
                      '[elastic-arb-skip] %s reason=sealed' % _sn(sec), throttle_sec=60.0)
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        if place_order(context, sec, 'buy', note='elastic_arb px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%% open=%.1f%% big=%s big_ok=%d boards=%s' % (
            px, limit or px, chg, surge, open_chg, _fmt_big_ratio(big), int(big_ok), ','.join(list(strong.keys())[:2])), mode='chase'):
            _buy_slot_add(sec, 'elastic_arb'); g.buy_log[sec] = now
            _save_state()
            return True
    return False


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


# ================= v0.36e 概念板块口径（文件 THS 概念 -> 未加载回退 API；v0.60 起全链路统一口径） =================
def _concept_active():
    # v0.60 概念口径开关：board_concept_unified 关闭 或 板块映射文件未加载 -> 回退 API
    try:
        return bool(BLS.get('board_concept_unified', True)) and bool(getattr(g, 'boards', None))
    except Exception:
        return False


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


def _concept_snap_for(board, mem):
    # v0.60 概念快照统一入口：共享合并账本（csnap_led）新鲜且覆盖该板块时零额外 RPC，
    # 否则单板批量走预算缓存（_board_refresh_ttl，budget=board 与 API 旧链同节奏，防 score_now 高频触发批量）
    try:
        led = getattr(g, 'csnap_led', None)
        if led and (time.time() - float(led.get('ts') or 0.0)) < float(BLS.get('board_rank_ttl_fast', 3.0)):
            if str(board) in (str(led.get('key') or '')).split('|'):
                return led.get('snap') or {}
    except Exception:
        pass
    try:
        dh = _get_ds()
        v = dh.cached(('cbsnap', str(board)), '_', _board_refresh_ttl(),
                      lambda: _get_snapshot_many(mem, len(mem)) or {}, budget='board', stale_ok=True)
        return v if v is not None else {}
    except Exception:
        return {}


def _concept_board_strength(board, snap=None):
    # 概念板块强度（v0.60 统一口径）：文件已加载 -> 成员=_board_members_file、快照=同帧合并 snap 优先，
    # 账本非新鲜 -> 单板预算缓存（_concept_snap_for）；文件未加载 -> 回退 API _board_strength_by_code。
    try:
        if not _concept_active():
            return _board_strength_by_code(board)
    except Exception:
        return _board_strength_by_code(board)
    mem = _board_members_file(board, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return 0.0
    if snap is None:
        snap = _concept_snap_for(board, mem)
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
    # v1.11 5日均值样本未就绪时 09:35 宽限内降级触发（avg5_pending_degrade），之后仍严格等样本。
    # 触发后持续跟踪（易主/09:50/买入 为止）；易主同样需连续 N 帧确认（防单帧抖动打断）。
    if not BLS.get('elastic_top_enabled', True):
        _skip_log('elastic_top_skip', '__elastic_top__', 'disabled',
                  '[elastic-top-skip] 总开关关闭', throttle_sec=300.0)
        return None
    if _min_age() > int(BLS.get('elastic_top_window_minute', 20)):
        _skip_log('elastic_top_skip', '__elastic_top__', 'window',
                  '[elastic-top-skip] 已过 %s 分钟窗口' % BLS.get('elastic_top_window_minute', 20), throttle_sec=300.0)
        return None
    et = getattr(g, 'elastic_top', None) or {'day': '', 'top': '', 'ts': 0.0, 'tracked': set(), 'trig': 0, 'done': False}
    g.elastic_top = et
    day = str(get_trading_day())
    if et.get('day') != day:
        et.update(day=day, top='', ts=0.0, tracked=set(), trig=0, done=False)
        et.pop('stab', None)
    top, lead = _concept_board_rank_top1(_elastic_top_cand_src())   # v0.36e 概念口径（文件未加载回退 API）
    if not top:
        _skip_log('elastic_top_scan', '__elastic_top__', 'no_top',
                  '[elastic-top-scan] 无最强板块候选', throttle_sec=30.0)
        return None
    n_need = int(BLS.get('elastic_top_stable_frames', 2))
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
        _skip_log('elastic_top_scan', '__elastic_top__', 'stability',
                  '[elastic-top-scan] 稳定帧不足 n=%d/%d top=%s lead=%.1f%%' %
                  (stab['n'], n_need, top, lead), throttle_sec=30.0)
        return None
    st = _concept_board_strength(top)   # v0.36e 概念板块强度（合并快照）
    if st < float(BLS.get('elastic_top_min_strength', 2.0)):
        _skip_log('elastic_top_scan', '__elastic_top__', 'strength',
                  '[elastic-top-scan] 板块强度不足 st=%.1f%% < %s%%' %
                  (st, BLS.get('elastic_top_min_strength', 2.0)), throttle_sec=30.0)
        return None
    open_g = _board_open_gain(top)
    if open_g < float(BLS.get('elastic_top_breakout_min_open', 1.0)):
        _skip_log('elastic_top_scan', '__elastic_top__', 'open',
                  '[elastic-top-scan] 开盘板块涨幅不足 open=%.1f%% < %s%%' %
                  (open_g, BLS.get('elastic_top_breakout_min_open', 1.0)), throttle_sec=30.0)
        return None                                     # 开盘板块涨幅自身下限
    avg5 = _board_5d_strength(top)
    avg5_degraded = False
    if avg5 is None:
        # v1.11 5日均值样本未就绪：09:35 宽限内先按强度/开盘/领先降级触发，防首 5 分钟被日线续算卡住；
        # 超过宽限仍严格等待样本，防无历史数据全天误判。
        if _min_age() > float(BLS.get('elastic_top_avg5_grace_min', 5.0)):
            _skip_log('elastic_top_scan', '__elastic_top__', 'avg5_na',
                  '[elastic-top-scan] 5日均值未就绪且超过宽限', throttle_sec=30.0)
            return None
        avg5_degraded = True
    elif open_g < avg5 + float(BLS.get('elastic_top_breakout_min_boost', 2.0)):
        _skip_log('elastic_top_scan', '__elastic_top__', 'boost',
                  '[elastic-top-scan] 非新爆发 open=%.1f%% avg5=%.1f%% boost<%.1f%%' %
                  (open_g, avg5, float(BLS.get('elastic_top_breakout_min_boost', 2.0))), throttle_sec=30.0)
        return None                                     # 未显著强于自身5日 -> 非新爆发
    if et.get('trig', 0) >= int(BLS.get('elastic_top_max_trigger_per_day', 2)):
        _skip_log('elastic_top_scan', '__elastic_top__', 'trig_max',
                  '[elastic-top-scan] 当日触发已达上限 %s' % BLS.get('elastic_top_max_trigger_per_day', 2), throttle_sec=300.0)
        return None
    et['top'] = top; et['ts'] = time.time(); et['done'] = False
    if top in (et.get('tracked') or set()):
        _skip_log('elastic_top_scan', '__elastic_top__', 'tracked',
                  '[elastic-top-scan] %s 已跟踪过 -> 不再重复触发' % top, throttle_sec=300.0)
        return None
    et['tracked'].add(top); et['trig'] = et.get('trig', 0) + 1
    log.info('[elastic] new_top_board %s strength=%.1f%% open=%.1f%% avg5=%s lead=%.1f%% -> 启动弹性跟踪(最主动20cm/北交,10%%/15%%前买)' % (
        top, st, open_g, ('pending_degrade' if avg5_degraded else ('%.1f%%' % avg5)), lead))
    return top


def _calc_elastic_top_candidates(top):
    # 最强板块内 20cm/北交所弹性标的（v0.36e 两段）：批量快照按涨幅粗排（过滤非弹性/已过 10%/15%/不涨），
    # 只对前 elastic_top_surge_top_n 只算 1m surge（砍掉全成员串行拉取），按最主动（surge 降序）排序
    out = []
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(top, 30)) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        pre_rank = []
        for m in mem:
            if not _is_elastic_eligible(m):
                continue
            d = sn.get(m) or g.spot.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre <= 0 or px <= 0:
                continue
            chg = (px / pre - 1.0) * 100.0
            if chg <= 0 or chg >= _elastic_top_buy_before(m):
                continue
            pre_rank.append((chg, m))
        pre_rank.sort(key=lambda t: -t[0])
        for chg, m in pre_rank[:int(BLS.get('elastic_top_surge_top_n', 5))]:
            surge = _elastic_1m_surge(m)
            out.append((surge, chg, _elastic_big_bonus_pts(m), m))
    except Exception:
        return []
    out.sort(key=lambda t: (-(t[0] + t[2]), -t[1]))   # v1.6 大单净量>=10% 进攻加分后按最主动排序
    return [m for _, _, _, m in out]


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
    # v0.36 新最强板块弹性套利：第一时间跟踪最主动弹性标的，20cm 10%/北交 15% 涨幅前买入
    if not BLS.get('elastic_top_enabled', True):
        _skip_log('elastic_top_skip', '__elastic_top__', 'disabled',
                  '[elastic-top-skip] 总开关关闭', throttle_sec=300.0)
        return
    if _min_age() > int(BLS.get('elastic_top_window_minute', 20)):
        _skip_log('elastic_top_skip', '__elastic_top__', 'window',
                  '[elastic-top-skip] 已过 %s 分钟窗口' % BLS.get('elastic_top_window_minute', 20), throttle_sec=300.0)
        return                       # 09:50 前
    if not _buy_slot_ok('elastic_top'):   # v1.21 弹性 top 独立1个名额
        _skip_log('slot_skip', '__elastic_top__', 'elastic_top',
                  '[slot-skip] kind=elastic_top used=%d/%d total=%d/%d -> skip entry'
                  % (len((getattr(g, 'daily', None) or {}).get('bought_elastic_top') or []),
                     _buy_slot_limit('elastic_top'), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                     int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
        return
    top = _new_top_board_scan()
    if not top:
        return
    positions = context.portfolio.positions
    for sec in _elastic_top_candidates(top):
        if sec in positions:
            _skip_log('elastic_top_skip', sec, 'position',
                      '[elastic-top-skip] %s 已在持仓 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        if sec in g.daily['bought']:
            _skip_log('elastic_top_skip', sec, 'bought',
                      '[elastic-top-skip] %s 当日已买 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue                 # 当日已买（含其它策略）不再评估
        if not _buy_slot_ok('elastic_top'):
            _skip_log('slot_skip', sec, 'elastic_top',
                      '[slot-skip] kind=elastic_top used=%d/%d total=%d/%d -> skip loop'
                      % (len((getattr(g, 'daily', None) or {}).get('bought_elastic_top') or []),
                         _buy_slot_limit('elastic_top'), len((getattr(g, 'daily', None) or {}).get('bought') or []),
                         int(BLS.get('daily_max_buy', 3))), throttle_sec=60.0)
            return
        if not trade_open(sec):
            _skip_log('elastic_top_skip', sec, 'trade_closed',
                      '[elastic-top-skip] %s 不可交易 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        if not _lb_senti_gate_apply(sec, 'elastic'):
            _skip_log('elastic_top_skip', sec, 'direction_gate',
                      '[elastic-top-skip] %s 情绪方向闸拦截 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue                 # v0.78 B3 统一方向闸（弹性首板 low 恒放行，2 板候选切低位/冰点拦截）
        if _is_one_word_open(sec):
            _skip_log('elastic_top_skip', sec, 'one_word',
                      '[elastic-top-skip] %s 一字板 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue                 # 不追一字
        if _block_sealed_buy(sec):
            _skip_log('elastic_top_skip', sec, 'sealed',
                      '[elastic-top-skip] %s 封死涨停 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue                 # 封死不排队
        if _mid_board_avoid(sec):
            _skip_log('elastic_top_skip', sec, 'mid_avoid',
                      '[elastic-top-skip] %s 连板中位股规避 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            _skip_log('elastic_top_skip', sec, 'no_preclose',
                      '[elastic-top-skip] %s 前收缺失 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        px = last_px(sec)
        if not px or px <= 0:
            _skip_log('elastic_top_skip', sec, 'no_px',
                      '[elastic-top-skip] %s 现价缺失 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg <= 0 or chg >= _elastic_top_buy_before(sec):
            _skip_log('elastic_top_skip', sec, 'chg_range',
                      '[elastic-top-skip] %s 涨幅越界 chg=%.1f%% before=%.1f%%' %
                      (_sn(sec), chg, _elastic_top_buy_before(sec)), throttle_sec=60.0)
            continue                 # 20cm 10% / 北交 15% 前买入
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > _elastic_max_open_change(sec) + 1e-9:
            _skip_log('elastic_top_skip', sec, 'open_high',
                      '[elastic-top-skip] %s 高开过大 open=%.1f%%' % (_sn(sec), open_chg), throttle_sec=60.0)
            continue                 # 防大幅高开兑现
        surge = _elastic_1m_surge(sec)
        if surge < float(BLS.get('elastic_top_min_1m_surge', 2.0)):
            _skip_log('elastic_top_skip', sec, '1m_surge',
                      '[elastic-top-skip] %s 1m 大阳线不足 surge=%.1f%% < %s%%' %
                      (_sn(sec), surge, BLS.get('elastic_top_min_1m_surge', 2.0)), throttle_sec=60.0)
            continue                 # 最主动要求
        big = _l2_big_ratio(sec)
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            _skip_log('elastic_top_skip', sec, 'cold',
                      '[elastic-top-skip] %s 冷却中 -> 跳过' % _sn(sec), throttle_sec=60.0)
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        if place_order(context, sec, 'buy', note='elastic_top board=%s px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%% big=%s big_ok=%d' % (
            top, px, limit or px, chg, surge, _fmt_big_ratio(big), int(_l2_big_ok(sec))), mode='chase'):
            _buy_slot_add(sec, 'elastic_top'); g.buy_log[sec] = now
            et = getattr(g, 'elastic_top', None)
            if et:
                et['done'] = True        # 本轮跟踪结束（易主/09:50/买入 三终止条件）
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


def _p2e_reverse_log(sec, msg):
    # v1.28 P2E 持仓自身反证审计（60s/股节流）
    try:
        gl = getattr(g, 'p2e_reverse_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.p2e_reverse_log = gl
        now = time.time()
        hb = float(BLS.get('p2e_audit_heartbeat_sec', 60.0) or 60.0)
        if now - float(gl.get(sec) or 0) < hb:
            return
        gl[sec] = now
        log.info('[P2E-reverse] %s %s' % (_sn(sec), msg))
    except Exception:
        pass


def _p2e_skip_log(sec, why):
    # v1.28 P2E 确认段跳过原因审计（60s/股节流）
    try:
        gl = getattr(g, 'p2e_skip_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.p2e_skip_log = gl
        now = time.time()
        hb = float(BLS.get('p2e_audit_heartbeat_sec', 60.0) or 60.0)
        if now - float(gl.get(sec) or 0) < hb:
            return
        gl[sec] = now
        log.info('[P2E-skip] %s %s' % (_sn(sec), why))
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
def _sold_today_fully(sec):
    # v1.33 整票卖完判定改为数量级：daily.sold 只记录“已卖完”，
    # FILLED 只代表本次卖单完成，不代表整票清仓（P6/P8/P7 部分卖出仍有剩余仓）。
    try:
        if str(sec) not in ((getattr(g, 'daily', None) or {}).get('sold') or []):
            return False
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        if str(pp.get('side') or '') != 'sell':
            return True
        st = str(pp.get('status') or '').upper()
        if st == 'PARTIAL' or st in ('CANCELLED', 'REJECTED'):
            return False
        src = int(pp.get('src_qty') or 0)
        filled = int(pp.get('filled') or 0)
        if src > 0:
            return filled >= src
        if st == 'FILLED':
            # v1.33 旧状态无 src_qty：以桥当前总量兜底，总量缺失/不可得视为仍有剩余
            try:
                _tot = _sell_pos_total(sec, get_positions() or {})
                return _tot is not None and _tot <= 0
            except Exception:
                return False
        return True
    except Exception:
        return False


def _sell_order_sold_out(sec):
    # v1.33 单笔卖单是否代表整票卖完：src_qty>0 时按 src_qty 与 filled 比较；
    # 旧状态无 src_qty 时用桥当前总量兜底（总量>0 视为仍有剩余）。
    try:
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        if str(pp.get('side') or '') != 'sell':
            return False
        src = int(pp.get('src_qty') or 0)
        filled = int(pp.get('filled') or 0)
        if src > 0:
            return filled >= src
        st = str(pp.get('status') or '').upper()
        if st == 'FILLED':
            try:
                _tot = _sell_pos_total(sec, get_positions() or {})
                return _tot is not None and _tot <= 0
            except Exception:
                return False
        return False
    except Exception:
        return False


def _sellable_source():
    # 持仓量/成本来源：优先 get_positions()（规范键 .XSHG + amount/enable_amount/cost_basis, docs/06）；
    # 兜底 context.portfolio.positions（实盘原始键 .SS 且字段名随柜台而异）。
    # v1.18 当日已全部成交的卖出票从视图过滤（防桥残留回填导致 [sell-skip]/[pos-stale] 刷屏）。
    try:
        p = get_positions() or {}
    except Exception:
        p = {}
    if not (isinstance(p, dict) and p):
        return {}
    try:
        if BLS.get('sell_source_filter_sold', True):
            sold = set((getattr(g, 'daily', None) or {}).get('sold') or [])
            if sold:
                out = {}
                for k, v in p.items():
                    nk = _norm_sec(k)
                    if nk not in sold or not _sold_today_fully(nk):
                        out[k] = v
                p = out
    except Exception:
        pass
    return p

_SEL_FIELDS_AVAIL = ('enable_amount', 'available_amount', 'sellable_amount', 'closeable_amount',
                     'real_enable_amount', 'm_nCanUseVolume', 'm_nPREnableVolume',
                     'can_use_volume', 'enable_volume', 'sellable_volume')
_SEL_FIELDS_TOTAL = ('current_amount', 'amount', 'hold_amount', 'holding_amount', 'm_nVolume', 'volume')

def _sellable_total(sec, positions):
    # v1.20 总量字段明细：(qty, key, present)。m_nVolume 扣冻结量，供 enable 回填审计。
    p = positions.get(sec)
    if p is None:
        return 0, '', False
    for key in _SEL_FIELDS_TOTAL:
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is None:
                continue
            qty = max(int(float(v) or 0), 0)
            if key == 'm_nVolume':
                try:
                    fv = p.get('m_nFrozenVolume') if isinstance(p, dict) else getattr(p, 'm_nFrozenVolume', None)
                    qty = max(qty - max(int(float(fv) or 0), 0), 0)
                except Exception:
                    pass
            return qty, key, True
        except Exception:
            continue
    return 0, '', False


def _find_pos_raw(sec, positions):
    # v1.33 按标准化代码匹配桥持仓原始键（.SS/.SZ/.SH），供数量级卖完判定复用
    try:
        if sec in positions:
            return sec
        for k in positions:
            if _norm_sec(k) == sec:
                return k
    except Exception:
        pass
    return sec


def _sell_pos_total(sec, positions):
    # v1.33 桥当前持仓总量；None 表示总量字段缺失/不可得，调用方按“仍有剩余”处理
    try:
        qty, _key, present = _sellable_total(_find_pos_raw(sec, positions), positions)
        return qty if present else None
    except Exception:
        return None


def _sellable_detail(sec, positions):
    # v1.8 可卖数量明细：(qty, key, avail_present, total_present)。
    # 可卖类字段优先（A股T+1：当日买入 enable=0 正确返回 0，不回退总量）；
    # 兼容 QMT 桥 m_nCanUseVolume/m_nPREnableVolume/m_nVolume（m_nVolume 扣冻结量），供 [sell-skip] 定位链路。
    p = positions.get(sec)
    for key in _SEL_FIELDS_AVAIL:
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is None:
                continue
            qty = max(int(float(v) or 0), 0)
            if qty == 0:   # v1.35 字段存在但值为 0：dump 全字段定位真实可卖字段（如 603533 enable/amount 双 0）
                try:
                    _audit_pos_fields(sec, positions.get(_find_pos_raw(sec, positions)))
                except Exception:
                    pass
            _tq, _tk, _tok = _sellable_total(sec, positions)   # v1.22 总量字段存在性一并上报（amt0 审计用）
            return qty, key, True, _tok
        except Exception:
            continue
    tq, tk, ok = _sellable_total(sec, positions)
    if ok:
        return tq, tk, False, True
    if p is not None:
        _audit_pos_fields(sec, p)
    return 0, '', False, False

def _sell_avail_backfill_log(sec, qty, avail_key, kind):
    # v1.20 可卖回填审计（60s/股节流）：桥 enable_amount 未回填时按总量兜底的依据留痕
    try:
        gl = getattr(g, 'sell_avail_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.sell_avail_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0.0) < 60.0:
            return
        gl[sec] = now
        log.info('[sell-avail] %s 回填 qty=%d src=%s kind=%s' % (_sn(sec), qty, avail_key, kind))
    except Exception:
        pass


def _sell_avail_amt0_log(sec, avail_key, avail_present, total_present, total_key='', total_qty=0, avail_qty=0):
    # v1.22 桥持仓 amount=0 审计：可卖字段存在但总量缺失/为 0 时打印明细，不回填可卖（不虚构）
    # v1.28 追加可卖字段真实值 avail_qty，消除“avail=1 是数量还是字段存在标志”的误读。
    try:
        if not BLS.get('sell_avail_amt0_warn_only', True):
            return
        gl = getattr(g, 'sell_avail_amt0_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.sell_avail_amt0_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0.0) < 60.0:
            return
        gl[sec] = now
        _bq = int((getattr(g, 'bought_qty', None) or {}).get(sec) or 0)
        log.info('[pos-amt0] %s 可卖字段=%s avail_present=%d avail_val=%d total_present=%d total_field=%s total_qty=%d bought_qty=%d -> 不回填(防虚构可卖)' % (
            _sn(sec), avail_key or '-', int(bool(avail_present)), int(avail_qty or 0), int(bool(total_present)),
            total_key or '-', int(total_qty or 0), _bq))
    except Exception:
        pass


def _sellable_backfill_detail(sec, positions):
    # v1.20 可卖回填：(qty, key, avail_present, total_present)。
    # 桥/PTrade 持仓成交后 enable_amount 常缺回填 -> 非当日买入按总量兜底，恢复卖出保护；
    # 当日买入默认 T+1 严格（enable=0 不回填），需账户支持 T+0 才可放开。
    qty, key, avail_present, total_present = _sellable_detail(sec, positions)
    if qty > 0 or not avail_present or not BLS.get('sell_avail_backfill_enabled', True):
        return qty, key, avail_present, total_present
    tq, tk, ok = _sellable_total(sec, positions)
    if not ok or tq <= 0:
        try:   # v1.35 [pos-dump]：enable 与 amount 双 0 时打印全字段，供 603533 类账户口径核对
            _audit_pos_fields(sec, positions.get(_find_pos_raw(sec, positions)))
        except Exception:
            pass
        _sell_avail_amt0_log(sec, key, avail_present, total_present, tk, tq, qty)
        return qty, key, avail_present, total_present
    _bought = str(sec) in ((getattr(g, 'daily', None) or {}).get('bought') or [])
    if _bought and BLS.get('sell_avail_t1_strict', True):
        return qty, key, avail_present, total_present   # T+1 当日买入不回填
    _sell_avail_backfill_log(sec, tq, tk, 't0' if _bought else 'prev')
    return tq, 'enable_backfill', True, True


def _audit_sell_amt0(sec, raw, positions):
    # v1.28 T+1 当日买入可卖 0 审计：打印可卖字段真实值 + 总量，供桥侧核对（sell_manager 1m 心跳）
    try:
        _q0, _k0, _av0, _tv0 = _sellable_detail(raw, positions)
        _tq0, _tk0, _tok0 = _sellable_total(raw, positions)
        _bought_today = '1' if str(raw) in ((getattr(g, 'daily', None) or {}).get('bought') or []) else '0'
        _bq0 = int((getattr(g, 'bought_qty', None) or {}).get(raw) or 0)
        _audit_sell_skip(sec, 'amt0(lookup key=%s field=%s avail_present=%d avail_val=%d total_field=%s total_qty=%d total_present=%d t1=%s bought_qty=%d)' % (
            raw, _k0 or '-', int(_av0), int(_q0), _tk0 or '-', int(_tq0), int(bool(_tok0)), _bought_today, _bq0))
    except Exception:
        pass

def _sellable(sec, positions):
    return _sellable_backfill_detail(sec, positions)[0]

def _p6_weak_reset(sec):
    # v1.20 P6 评分恢复/离开弱分区 -> 清空两帧计数
    try:
        w = getattr(g, 'p6_weak', None)
        if isinstance(w, dict):
            w.pop(sec, None)
    except Exception:
        pass

def _p6_weak_step(sec, sc):
    # v1.20 P6 两帧确认：连续弱分（间隔<=p6_confirm_win_sec）才返回 trigger=True；
    # 超窗重新计数，触发后清计数（保留后续再次减半能力）。返回 (cnt, trigger, note)。
    try:
        w = getattr(g, 'p6_weak', None)
        if not isinstance(w, dict):
            w = {}; g.p6_weak = w
        rec = w.get(sec)
        now = time.time()
        if rec and now - float(rec.get('ts') or 0) > float(BLS.get('p6_confirm_win_sec', 30.0) or 30.0):
            rec = None
        cnt = (int(rec.get('cnt') or 0) + 1) if rec else 1
        w[sec] = {'cnt': cnt, 'ts': now, 'score': float(sc)}
        if cnt >= int(BLS.get('p6_confirm_frames', 2) or 2):
            w.pop(sec, None)
            try:
                _save_state()
            except Exception:
                pass
            return cnt, True, '[p6-confirm] %s score=%.1f cnt=%d -> sell' % (_sn(sec), sc, cnt)
        try:
            _save_state()
        except Exception:
            pass
        return cnt, False, '[p6-confirm] %s score=%.1f cnt=%d -> hold' % (_sn(sec), sc, cnt)
    except Exception:
        return 1, False, '[p6-confirm] %s state error -> hold' % (_sn(sec))

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
    # v1.13 超时后先查 open/all orders：在途/查询失败继续等；FILLED 禁止重投；
    # CANCELLED/REJECTED 或无匹配才放行重试（防 2026-10-30 徕木 120s 重复投递）。
    # v1.15 连续 CANCELLED/REJECTED 熔断暂停；零回报单按 symbol 回填委托号。
    p = (getattr(g, 'pending', None) or {}).get(sec) or {}
    if str(p.get('side') or '') != 'sell':
        return False
    _pu = float(p.get('retry_pause_until') or 0)
    if str(p.get('retry_blocked')) == 'True' and _pu > time.time():
        return True   # v1.15 熔断暂停期：不重投
    st = str(p.get('status') or 'SENT').upper()
    if st == 'FILLED':
        return True   # v1.13 已成交不再重投（桥残留由 [pos-stale]/sync_positions 收敛）
    if st in ('CANCELLED', 'REJECTED'):
        return False
    ts = float(p.get('ts') or 0)
    if ts > 0 and (time.time() - ts) > float(BLS.get('sell_pending_timeout', 120.0)):
        ent = str(p.get('no') or '')
        if ent:
            st2 = _query_open_order_status(ent, sec=sec, side='sell', qty=p.get('qty'), backfill=True)
            if st2 == 'SENT':
                p['ts'] = time.time()   # 仍在在途：刷新时间戳继续等
                return True
            if st2 is None:
                p['ts'] = time.time()   # 查询失败：保守等待
                return True
            if st2 == 'FILLED':
                p['status'] = 'FILLED'
                p['filled'] = int(p.get('qty') or 0)
                log.info('[sell-replace] %s 查询确认已成交 -> 不重投' % _sn(sec))
                return True
            if st2 in ('CANCELLED', 'REJECTED'):
                # v1.15 熔断：连续超限后暂停重投，暂停到期放行一次试探
                _rc = int((getattr(g, 'sell_retry_cnt', None) or {}).get(sec) or 0) + 1
                if not isinstance(getattr(g, 'sell_retry_cnt', None), dict):
                    g.sell_retry_cnt = {}
                g.sell_retry_cnt[sec] = _rc
                _max = int(BLS.get('sell_retry_max', 3) or 3)
                if _rc > _max:
                    _pu2 = float(p.get('retry_pause_until') or 0)
                    _ps = float(BLS.get('sell_retry_pause_sec', 600.0) or 600.0)
                    if _pu2 <= 0:
                        p['retry_pause_until'] = time.time() + _ps
                        p['retry_blocked'] = True
                        g.sell_retry_cnt[sec] = 1
                        log.info('[sell-retry-pause] %s 连续%d轮%s -> 暂停重投%.0fs' % (_sn(sec), _rc, st2, _ps))
                    elif time.time() < _pu2:
                        p['retry_blocked'] = True
                        _skip_log('sell_retry', sec, 'pause',
                                  '[sell-retry-pause] %s 暂停中(至%.1f) %s' % (_sn(sec), _pu2, st2),
                                  throttle_sec=60.0)
                    else:
                        g.sell_retry_cnt[sec] = 0
                        p.pop('retry_pause_until', None)
                        p['retry_blocked'] = False
                        log.info('[sell-retry-resume] %s 暂停到期 -> 放行一次重试' % _sn(sec))
                    p['status'] = st2
                    if str(p.get('retry_blocked')) == 'True':
                        return True
                    return False
                p['retry_blocked'] = False
                p['status'] = st2
                log.info('[sell-replace] %s 查询确认终态=%s -> 放行重试' % (_sn(sec), st2))
                return False
            # st2 == ''：查询成功无匹配 -> 确认不在在途，放行重试
            log.info('[sell-replace] %s 查询无匹配 -> 放行重试' % _sn(sec))
            return False
        return False   # 无委托号仍按疑似丢失放行重试
    return True


def _retry_sell_blocked(sec):
    # v1.15 卖单重投前可卖量校验：桥可卖0/不可用 -> 停止重投，防止连续废单刷屏
    # v1.20 在途卖单优先拦截（防止 enable 回填后对冻结份额重复重投）
    try:
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        if str(pp.get('side') or '') != 'sell':
            return False
        if str(pp.get('status') or '').upper() == 'FILLED':
            return False
        if _sell_inflight(sec):
            return True
        _pos = _sellable_source() or {}
        _q = _sellable(sec, _pos)
        if _q <= 0:
            pp['retry_blocked'] = True
            _skip_log('sell_retry', sec, 'block',
                      '[sell-retry-block] %s 重投前可卖量=0 -> 停止重投' % _sn(sec),
                      throttle_sec=60.0)
            return True
        pp['retry_blocked'] = False
        return False
    except Exception:
        return False


def _do_sell(context, sec, qty, note, urgent=False, mode=None, cool=True):
    # 统一卖出入口：sold_log 冷却 + 在途挂单守卫(_sell_inflight)；urgent(核卖)限价用跌停地板价保成交
    if qty <= 0:
        return
    if _retry_sell_blocked(sec):
        return
    if not isinstance(getattr(g, 'sold_log', None), dict):
        g.sold_log = {}
    if cool:
        g.sold_log[sec] = time.time()   # v0.59 P7c 分批卖出 cool=False：批次间隔自控（10s）不写通用 30s 冷却
    _src_qty = int(qty)
    try:
        _pos = _sellable_source() or context.portfolio.positions
        _raw = _find_pos_raw(sec, _pos)
        _av = _sellable(_raw, _pos)
        if _av > 0:
            _src_qty = int(_av)
    except Exception:
        pass
    _ok = place_order(context, sec, 'sell', qty=qty, note=note, mode=mode or ('sell_urgent' if urgent else 'sell'))
    if _ok:
        try:
            _pp = (getattr(g, 'pending', None) or {}).get(sec)
            if _pp and str(_pp.get('side') or '') == 'sell':
                _pp['src_qty'] = _src_qty   # v1.33 FILLED 后按 src_qty 判定整票是否卖完
        except Exception:
            pass

def _t1_protect_capture(sec, raw, positions):
    # v1.30 T+1 当日买入保护：可卖=0 时只记录保护触发（不卖单），次日 09:30-10:00 复核再执行。
    try:
        if not BLS.get('t1_protect_enabled', True):
            return
        daily = getattr(g, 'daily', None) or {}
        bought = daily.get('bought') or []
        if sec not in bought and raw not in bought:
            return
        bq = int((getattr(g, 'bought_qty', None) or {}).get(sec) or 0)
        if bq <= 0:
            bq = int((getattr(g, 'bought_qty', None) or {}).get(raw) or 0)
        if bq <= 0:
            return
        today = str(get_trading_day())
        px = last_px(sec) or 0.0
        cost = my_cost(raw, positions)
        ft = (g.first_zt or {}).get(sec) or {}
        triggers = []
        if ft.get('break'):
            triggers.append('BREAK')
        if ft.get('seal_low') or ft.get('seal_low_fast'):
            triggers.append('SEAL_LOW')
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= float(BLS.get('green_open_drop', -5.0) or -5.0) * float(rp.get('green_tol') or 1.0):
            triggers.append('P1_green_open')
        try:
            if _p2e_core_sell_check(sec)[0]:
                triggers.append('P2E')
        except Exception:
            pass
        if cost > 0 and px > 0 and (px / cost - 1.0) <= -get_stop_loss_pct(sec) * float(rp.get('stop_adj') or 1.0):
            triggers.append('P3_stop')
        for _nm, _chk in (('P7a', _p7a_check), ('P7b', _p7b_check), ('P7d', _p7d_check)):
            try:
                if _chk(sec, 100):
                    triggers.append(_nm)
            except Exception:
                pass
        try:
            if _lb_senti_cut_hold(sec):
                triggers.append('P8')
        except Exception:
            pass
        # v1.32 扫板A买入后同题材跌停 hard 由 0->1：只标记 LD_HARD_AFTER_BUY（不主动卖），次日复核优先
        try:
            sb = (getattr(g, 'sweep_a_ld_buy', None) or {}).get(sec) or {}
            if str(sb.get('day') or '') == today and not sb.get('hard'):
                ld_now = _ld_theme_hit(sec)
                if isinstance(ld_now, dict) and ld_now.get('hard'):
                    triggers.append('LD_HARD_AFTER_BUY')
        except Exception:
            pass
        if not triggers:
            triggers.append('amt0')
        now = time.time()
        pend = getattr(g, 't1_pending_sell', None)
        if not isinstance(pend, dict):
            pend = {}
            g.t1_pending_sell = pend
        rec = pend.get(sec)
        if not isinstance(rec, dict) or rec.get('day') != today:
            rec = {'day': today, 'triggers': [], 'ts': 0.0, 'qty': bq, 'cost': cost, 'px': px, 'note': ''}
            pend[sec] = rec
        rec['ts'] = now
        rec['qty'] = bq
        rec['cost'] = cost
        rec['px'] = px
        for t in triggers:
            if t not in rec['triggers']:
                rec['triggers'].append(t)
        if 'LD_HARD_AFTER_BUY' in triggers:
            rec['ld_hard_after_buy'] = 1
        rec['note'] = ','.join(rec['triggers'])
        gl = getattr(g, 't1_pending_log_ts', None)
        if not isinstance(gl, dict):
            gl = {}
            g.t1_pending_log_ts = gl
        cnt = getattr(g, 't1_pending_cnt', None)   # v1.35 完整行当日一次，后续 300s 计数心跳
        if not isinstance(cnt, dict):
            cnt = {}; g.t1_pending_cnt = cnt
        _hb = float(BLS.get('t1_pending_heartbeat_sec', 300.0) or 300.0)
        _last = float(gl.get(sec) or 0.0)
        if _last <= 0 or now - _last >= _hb:
            gl[sec] = now
            _n = int(cnt.get(sec) or 0) + 1
            cnt[sec] = _n
            if _n <= 1:
                log.info('[t1-protect] %s 当日买入可卖0 -> 记录保护触发 %s qty=%d cost=%.2f px=%.2f (次日复核)' % (
                    _sn(sec), rec['note'], bq, cost, px))
            else:
                log.info('[t1-protect] %s 当日买入可卖0 累计 %d 次 qty=%d (心跳)' % (
                    _sn(sec), _n, bq))
        if now - float(getattr(g, 't1_pending_save_ts', 0.0) or 0.0) >= float(BLS.get('t1_pending_save_sec', 60.0) or 60.0):
            g.t1_pending_save_ts = now
            _save_state()
    except Exception as e:
        _warn('t1 protect capture fail %r' % e)


def _t1_protect_consume(context):
    # v1.30 T+1 次日复核：仅消费 day != today 的 pending；09:30-10:00 弱开/止损补卖，
    # 强开/封死清 pending 转常规监控；10:00 后清 pending 转常规。
    try:
        if not BLS.get('t1_protect_enabled', True):
            return
        pend = getattr(g, 't1_pending_sell', None)
        if not isinstance(pend, dict) or not pend:
            return
        today = str(get_trading_day())
        positions = _sellable_source() or context.portfolio.positions
        now = time.time()
        until = int(BLS.get('t1_protect_consume_until_minute', 10) or 10)
        gl = getattr(g, 't1_pending_log_ts', None)
        if not isinstance(gl, dict):
            gl = {}
            g.t1_pending_log_ts = gl
        consumed = False
        for sec, rec in list(pend.items()):
            sec = _norm_sec(sec) or sec
            if str(rec.get('day') or '') == today:
                continue
            if _min_age() > until:
                pend.pop(sec, None)
                log.info('[t1-protect] %s 窗口结束(>%d分钟) -> 清 pending 转常规监控' % (_sn(sec), until))
                consumed = True
                continue
            raw = None
            for k in list(positions.keys()):
                if _norm_sec(k) == sec:
                    raw = k
                    break
            if raw is None:
                pend.pop(sec, None)
                log.info('[t1-protect] %s 次日复核 已不在持仓 -> 清理' % _sn(sec))
                consumed = True
                continue
            amt = _sellable(raw, positions)
            if amt <= 0:
                continue                       # 桥可卖仍未回填：保留等下一帧
            ac = _auction_change(sec)
            if ac >= float(BLS.get('t1_protect_strong_open', 3.0) or 3.0) or _sealed_now(sec) or _today_zt(sec):
                pend.pop(sec, None)
                log.info('[t1-protect] %s 次日强开 ac=%.1f%%/封死 -> 清 pending 转常规监控' % (_sn(sec), ac))
                consumed = True
                continue
            cost = float(rec.get('cost') or 0.0) or my_cost(raw, positions)
            px = last_px(sec) or 0.0
            rp = _role_tolerance(sec)
            p3 = cost > 0 and px > 0 and (px / cost - 1.0) <= -get_stop_loss_pct(sec) * float(rp.get('stop_adj') or 1.0)
            # v1.32 LD_HARD_AFTER_BUY（买入后题材跌停 hard）：次日复核优先，绿开即补卖
            ld_prio = 'LD_HARD_AFTER_BUY' in (rec.get('triggers') or [])
            if ld_prio and (ac <= 0.0 or p3):
                note = 'T1_protect_ld_hard ac=%.1f%% triggers=%s' % (ac, rec.get('note') or '-')
                if p3:
                    note = 'T1_protect_stop pnl=%.1f%% triggers=%s' % ((px / cost - 1.0) * 100.0, rec.get('note') or '-')
                pend.pop(sec, None)
                _do_sell(context, sec, amt, note, urgent=True)
                log.info('[t1-protect] %s 次日复核(跌停题材优先) -> %s qty=%d' % (_sn(sec), note, amt))
                consumed = True
                continue
            if ac <= -float(BLS.get('t1_protect_open_drop', 0.02) or 0.02) or p3:
                note = 'T1_protect_weak_open ac=%.1f%% triggers=%s' % (ac, rec.get('note') or '-')
                if p3:
                    note = 'T1_protect_stop pnl=%.1f%% triggers=%s' % ((px / cost - 1.0) * 100.0, rec.get('note') or '-')
                pend.pop(sec, None)
                _do_sell(context, sec, amt, note, urgent=True)
                log.info('[t1-protect] %s 次日复核 -> %s qty=%d' % (_sn(sec), note, amt))
                consumed = True
                continue
            if now - float(gl.get(sec) or 0.0) >= 60.0:
                gl[sec] = now
                log.info('[t1-protect] %s 次日复核 pending 待定 ac=%.1f%% triggers=%s' % (
                    _sn(sec), ac, rec.get('note') or '-'))
        if consumed:
            _save_state()
    except Exception as e:
        _warn('t1 protect consume fail %r' % e)


def _audit_pos_fields(sec, p):
    # v1.35 [pos-dump]：当日/股一次性打印持仓原始全部字段名与值（enable/amount 双 0 时定位真实字段）；
    # 原 1h 节流行为由当日去重替代，避免 603533 类“字段存在但值为 0”场景静默。
    try:
        if not BLS.get('pos_raw_dump_enabled', True):
            return
        gl = getattr(g, 'pos_raw_dump_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.pos_raw_dump_log = gl
        day = str(get_trading_day())
        seen = gl.get(sec)
        if not isinstance(seen, set):
            seen = set(); gl[sec] = seen
        if day in seen:
            return
        seen.add(day)
        if isinstance(p, dict):
            log.info('[pos-dump] %s %s fields=%s' % (_sn(sec), type(p).__name__,
                     {str(k): p[k] for k in sorted(p.keys(), key=str)}))
        else:
            attrs = {}
            for _a in dir(p):
                if _a.startswith('_'):
                    continue
                try:
                    attrs[_a] = getattr(p, _a)
                except Exception:
                    continue
            log.info('[pos-dump] %s %s fields=%s' % (_sn(sec), type(p).__name__, attrs))
    except Exception:
        pass

def _audit_sell_skip(sec, why, now=None):
    # 卖出被静默跳过的原因日志（v1.12 心跳节流 60s + 窗口计数）, 定位实盘持仓为何不下单
    try:
        now = now or time.time()
        # v1.13 桥持仓残留一次性审计：pending sell FILLED 但桥 positions 仍含且可卖为 0
        if 'amt0' in str(why):
            _p0 = (getattr(g, 'pending', None) or {}).get(sec) or {}
            if str(_p0.get('side') or '') == 'sell' and str(_p0.get('status') or '') == 'FILLED':
                ps = getattr(g, 'pos_stale_log', None)
                if ps is None:
                    ps = set(); g.pos_stale_log = ps
                if sec not in ps:
                    ps.add(sec)
                    log.info('[pos-stale] %s 桥持仓残留: pending sell FILLED 但 positions 仍含可卖0 -> 由 sync_positions 收敛(不重投)' % _sn(sec))
        gs = getattr(g, 'last_skip_log', None)
        if not isinstance(gs, dict):
            gs = {}; g.last_skip_log = gs
        cnt = getattr(g, 'sell_skip_cnt', None)
        if not isinstance(cnt, dict):
            cnt = {}; g.sell_skip_cnt = cnt
        cnt[sec] = int(cnt.get(sec) or 0) + 1
        hb = float(BLS.get('sell_skip_heartbeat_sec', 60.0) or 60.0)
        if 't1=1' in str(why):
            hb = float(BLS.get('sell_skip_heartbeat_t1_sec', 300.0) or 300.0)   # v1.18 当日买入 T+1 降频
        if now - float(gs.get(sec) or 0) < hb:
            return
        gs[sec] = now
        _n = int(cnt.get(sec) or 0)
        cnt[sec] = 0
        log.info('[sell-skip] %s %s (positions=%s, %d次/%.0fs)' % (_sn(sec), why, sorted(str(x) for x in (getattr(g, 'holdings_keys_hint', None) or [])), _n, hb))
    except Exception:
        pass

def _p2e_core_sell_check(sec):
    # v0.58 P2E 竞价核卖统一判定（钩子 + 9:30 后 sell_manager/tick_sell_manager 共用，防逻辑漂移），返回 (hit, note)。
    #   触发 A：持仓所属题材存在中位股(T-1 board_cnt 2-5)，中位股最弱竞价 <= p2e_theme_drop_min(-2%)
    #           且中位股自身确认（基准有效: 竞价<基准；基准无效: 绿开<0）。
    #   触发 B：文件 expected_status ∈ (confirmed_miss, degraded)（pending_miss 默认不卖）+
    #           自身竞价 <= p2e_auction_drop_min(-2%)。
    #   豁免：唯一高身位（交盘中监控，不核卖）；v0.33/v1.28 反证守卫（触发A持仓自身超预期/一字封死
    #           与触发B实时 CX 均不核卖，交盘中分时反证）；side 仅 sell/hold。
    #   返回 (hit, note, reversed)：reversed=True 表示命中后被自身反证/身位豁免拦截。
    if not BLS.get('p2e_sell_enabled', True):
        return False, '', False
    en = g.exp_file.get(sec) or {}
    if str(en.get('side') or '') not in ('sell', 'hold'):
        return False, '', False
    _au = _auction_change(sec)
    # A：同题材中位股最弱竞价
    _mid = None
    if BLS.get('p2e_theme_sell_enabled', True):
        try:
            for _nm in _zt_themes_of(sec):
                for _c in ((getattr(g, 'zt_theme', {}) or {}).get(_nm) or {}).get('members') or []:
                    _rec = (getattr(g, 'zt_lianban', {}) or {}).get(_c) or {}
                    _bc = int(_rec.get('board_cnt') or 0)
                    if not (2 <= _bc <= 5):
                        continue
                    _acm = _auction_change(_c)
                    if _mid is None or _acm < _mid[0]:
                        _mid = (_acm, _c, _auction_benchmark(_c))
        except Exception:
            _mid = None
    _hitA = False; _noteA = ''
    if _mid is not None:
        _dm = float(BLS.get('p2e_theme_drop_min', -2.0))
        if _mid[0] <= _dm:
            _bmv, _bmok = _mid[2]
            if (_bmok and _mid[0] < _bmv) or (not _bmok and _mid[0] < 0):
                _hitA = True
                _noteA = 'P2E_theme_mid_break mid=%s ac=%.1f%%' % (_sn(_mid[1]), _mid[0])
    # B：自身大不及（文件 miss/degraded + 今日竞价大低开）
    _est = str(en.get('expected_status') or '')
    _ma = ('confirmed_miss', 'degraded')
    if BLS.get('exp_sell_on_pending_miss', False):
        _ma = _ma + ('pending_miss',)
    _hitB = bool(_est and _est in _ma and _au <= float(BLS.get('p2e_auction_drop_min', -2.0)))
    _reversed = False
    if _hitB:
        try:   # v0.33 反证守卫：文件悲观但云端实时竞价超预期(CX) -> 不核卖，转实时分时三态
            _rev, _ra = _confirm_expected(sec)
            if _rev == CX:
                _p2e_reverse_log(sec, '文件预期=%s 悲观 vs 云端实时竞价超预期(CX) -> 不核卖' % _est)
                _hitB = False
                _reversed = True
        except Exception:
            pass
    # A 反证守卫（v1.28）：持仓自身竞价超预期/一字封死，题材联动不直接清仓，交盘中分时确认
    if _hitA:
        _revA, _revAnote = _p2e_holding_reverse(sec, en)
        if _revA:
            _p2e_reverse_log(sec, '题材中位崩塌被自身反证豁免 %s (A: %s)' % (_revAnote, _noteA))
            _hitA = False
            _reversed = True
    # 唯一高身位豁免（有容忍度交到盘中监控）
    if (_hitA or _hitB) and _unique_stand(sec):
        _p2e_reverse_log(sec, '唯一高身位豁免 P2E 竞价核卖 -> 交盘中监控')
        return False, '', True
    if _hitA:
        return True, _noteA, False
    if _hitB:
        return True, 'P2E_exp_miss %s ac=%.1f%%' % (_est, _au), False
    return False, '', _reversed


def _p2e_holding_reverse(sec, en):
    # v1.28 持仓自身反证判定：竞价超预期（PX/CX）或一字封死 -> 不核卖，给盘中反证机会。
    # 竞价未就绪不误卖（保持等待），大绿开仍由 P1 硬信号兜底。
    try:
        if not BLS.get('p2e_reverse_guard_enabled', True):
            return False, 'disabled'
        if not _auction_ready(sec):
            return False, 'auction_not_ready'
        _au0, _rau = _eval_auction(sec)
        if _au0 == PX:
            return True, 'auction_exceed(%s)' % ','.join(_rau)
        _rev, _ract = _confirm_expected(sec)
        if _rev == CX:
            return True, 'file_cx(%s)' % str(_ract)
        e = g.exp.get(sec) or {}
        if str(e.get('entry_type') or en.get('entry_type') or '') == 'one_word' and _is_one_word_open(sec):
            return True, 'one_word_sealed'
        return False, ''
    except Exception:
        return False, ''


def p2e_auction_core_sell(context):
    # v0.58 P2E 竞价核卖：09:15-09:25 钩子（run_interval 3s）。09:24:45 前预热只日志不触发
    # （避免早期撮合价污染 g.auction_c）；09:24:45-09:25:30 确认段评估触发（先重读当日预期文件 +
    # 刷新竞价缓存）；9:30 后 sell_manager/tick_sell_manager 同条件兜底（sold_log 冷却 + 在途守卫去重）。
    # v1.28 审计：确认段逐票评估 + [P2E-heartbeat] + 跳过原因，命中反证记 [P2E-reverse]。
    _set_now(context)
    if not BLS.get('p2e_sell_enabled', True):
        return
    _hms = _hhmmss()
    _confirm_at = str(BLS.get('p2e_confirm_at', '09:24:45'))
    if not (_confirm_at <= _hms < '09:25:30'):
        if not getattr(g, 'p2e_warm_logged', False):
            g.p2e_warm_logged = True
            log.info('[P2E] 竞价核卖监控启动 预热段 09:15-%s 不触发（确认段 %s-09:25 评估）' % (_confirm_at, _confirm_at))
        return
    if getattr(g, 'p2e_fresh_day', None) != str(get_trading_day()):
        g.auction_c = {}      # 用 9:24:45+ 实时竞价重算（预热不评估，缓存干净）
        g.p2e_fresh_day = str(get_trading_day())
        try:
            _load_expectation(merge=True)   # 幂等重读：命中 9:15 前上传的当日文件（C 合并防收缩）
        except Exception:
            pass
        log.info('[P2E] 确认段开始 hms=%s exp_file=%d' % (_hms, len(g.exp_file or {})))
    positions = _sellable_source() or context.portfolio.positions
    if not positions:
        log.info('[P2E] 确认段 hms=%s 无持仓 positions=0' % _hms)
        return
    _sl = float(BLS.get('sell_cold_secs', 30.0))
    _n_eval = 0; _n_hit = 0; _n_rev = 0; _n_skip = 0
    _hb = float(BLS.get('p2e_audit_heartbeat_sec', 60.0) or 60.0)
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        amt = _sellable(_raw, positions)
        if amt <= 0:
            _n_skip += 1
            _p2e_skip_log(sec, 'amt0(可卖=0)')
            continue
        if _sell_inflight(sec):
            _n_skip += 1
            _p2e_skip_log(sec, 'inflight')
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (time.time() - g.sold_log.get(sec, 0)) < _sl:
            _n_skip += 1
            _p2e_skip_log(sec, 'sold_cold')
            continue
        if not (getattr(g, 'zt_theme', None) or {}):
            _p2e_skip_log(sec, 'theme_data_missing(全局题材索引为空)')
        _n_eval += 1
        try:
            _res = _p2e_core_sell_check(sec)
            _hit, _note = _res[0], _res[1]
            _rev = bool(_res[2]) if len(_res) > 2 else False
        except Exception as _e:
            _warn('p2e check fail %s: %r' % (_sn(sec), _e)); continue
        if _rev:
            _n_rev += 1
        elif _hit:
            _n_hit += 1
        log.info('[P2E] %s hms=%s hit=%d reverse=%d reason=%s' % (_sn(sec), _hms, int(_hit), int(_rev), _note or '-'))
        if _hit:
            _do_sell(context, sec, amt, _note, urgent=True)
    _now = time.time()
    if _now - float(getattr(g, 'p2e_heartbeat_ts', 0) or 0) >= _hb:
        g.p2e_heartbeat_ts = _now
        log.info('[P2E-heartbeat] hms=%s positions=%d eval=%d hit=%d reverse=%d skip=%d' % (
            _hms, len(positions), _n_eval, _n_hit, _n_rev, _n_skip))
    if _hms >= '09:25:00' and not getattr(g, 'p2e_end_logged', False):
        g.p2e_end_logged = True
        log.info('[P2E] 确认段结束 hms=%s positions=%d eval=%d hit=%d reverse=%d skip=%d exp_file=%d' % (
            _hms, len(positions), _n_eval, _n_hit, _n_rev, _n_skip, len(g.exp_file or {})))


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
            _audit_sell_amt0(sec, _raw, positions)   # v1.28 打印可卖字段真实值+总量，防 avail 误读
            try:
                _t1_protect_capture(sec, _raw, positions)   # v1.30 T+1 当日买入保护记录（不卖单）
            except Exception as _e:
                _warn('t1 protect capture fail %r' % _e)
            continue
        now = time.time()
        if _sell_inflight(sec):            # 订单/成交回报驱动的去重：有未终态卖单在途则跳过(防叠单)
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (now - g.sold_log.get(sec, 0)) < sl:
            continue
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open drop=%.1f%%' % _auction_change(sec), urgent=True); continue
        # P2E 竞价核卖（v0.58 docs/33 统一判定）：自身大不及(文件 miss/degraded + 竞价大低开) / 同题材中位崩塌传导
        _hit2, _note2 = _p2e_core_sell_check(sec)[:2]
        if _hit2:
            _do_sell(context, sec, amt, _note2, urgent=True); continue
        if cost > 0:
            pnl_pct = px / cost - 1.0
            if pnl_pct <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss pnl=%.1f%%' % (pnl_pct * 100), urgent=True); continue
        # v0.59 P7 持仓卖出闭环（docs/33）：P7a 连板放量不封板 / P7b 跟风拉升不封板 / P7c 首板次日不主动冲板分批清仓
        if BLS.get('p7_sell_enabled', True):
            _p7a = _p7a_check(sec, amt)
            if _p7a and sec not in (getattr(g, 'p7a_sold', None) or set()):
                _do_sell(context, sec, _p7a[1], _p7a[0]); _mark_p7(sec, 'p7a'); continue
            _p7b = _p7b_check(sec, amt)
            if _p7b and sec not in (getattr(g, 'p7b_sold', None) or set()):
                _do_sell(context, sec, _p7b[1], _p7b[0]); _mark_p7(sec, 'p7b'); continue
            _p7c = _p7c_check(sec, amt)
            if _p7c:
                _do_sell(context, sec, _p7c[1], _p7c[0], cool=False); _save_state(); continue
            _p7d = _p7d_check(sec, amt)
            if _p7d and sec not in (getattr(g, 'p7d_sold', None) or set()):
                _do_sell(context, sec, _p7d[1], _p7d[0]); _mark_p7(sec, 'p7d'); continue
        # v0.65 P8 中高位兑现指导（docs/43）：高位分歧/切低位 + 中位股晋级失败 -> 减半兑现
        _p8 = _lb_senti_cut_hold(sec)
        if _p8:
            _q8 = int(int(amt * float(_p8[0])) // 100) * 100
            if _q8 < 100:
                _q8 = amt if amt < 100 else 100
            _do_sell(context, sec, _q8, _p8[1]); _mark_lb_cut(sec); continue
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
        if sc is None:
            continue   # v0.68 评分未就绪 -> 跳过 P5/P6（防数据真空误卖）
        if sc < BLS['score_sell_clear'] * rp['score_clear_adj']:
            _p6_weak_reset(sec)
            _do_sell(context, sec, amt, 'P5_score_clear score=%.1f' % sc)
        elif sc < BLS['score_sell_half'] * rp['score_half_adj']:
            if BLS.get('p6_two_frame_enabled', True):
                _cnt, _trig, _note = _p6_weak_step(sec, sc)
                log.info(_note)
                if not _trig:
                    continue
            _p6_weak_reset(sec)
            half = int(amt * float(BLS.get('sell_half_ratio', 0.5)))
            qty = int(half // 100) * 100
            if qty < 1:
                qty = amt if amt < 100 else 100
            if qty > amt:
                qty = amt
            _do_sell(context, sec, qty, 'P6_score_half score=%.1f' % sc)
        else:
            _p6_weak_reset(sec)



def tick_sell_manager(context):
    g.sellscan_used = 0   # v0.53 评分卖出每帧计数（重置）
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
            try:
                _t1_protect_capture(sec, _raw, positions)   # v1.30 T+1 当日买入保护记录（不卖单）
            except Exception as _e:
                _warn('t1 protect capture fail %r' % _e)
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
        ft = (g.first_zt or {}).get(sec) or {}
        # \u70b8\u677f\u5356\u51fa\uff1a\u6da8\u505c\u9996\u89e6\u540e\u6389\u51fa\u6da8\u505c\u4ef7\uff08break \u9996\u89e6\u53d1 -> \u5356\uff0c\u73b0\u4ef7\u9650\u4ef7\u9632\u8fc7\u5ea6\u6740\u4ef7\uff09
        if BLS.get('break_sell_enabled', True) and ft.get('break'):
            _bc = int(ft.get('break_cnt') or 0)
            if _bc >= 2 and _unique_stand(sec):
                if sec not in (getattr(g, 'break2_sold', None) or set()):
                    _half = int(amt * float(BLS.get('break2_half_ratio', 0.5)))
                    _half = int(_half // 100) * 100
                    _do_sell(context, sec, _half if _half >= 100 else amt,
                             'TICK_break2_half_sell break_cnt=%d held=%.0fs' % (_bc, now - _break_held_ts(ft, now)), mode='sell_break')
                    _mark_sold_event(sec, 'break2')
                    continue
            else:
                if sec not in (getattr(g, 'break_sold', None) or set()):
                    _do_sell(context, sec, amt, 'TICK_break_sell break_cnt=%d held=%.0fs' % (_bc, now - _break_held_ts(ft, now)), mode='sell_break')
                    _mark_sold_event(sec, 'break')
                    continue
        # \u5c01\u5355\u5927\u51cf\u5356\u51fa\uff1a\u5c01\u5355<=\u9996\u5c01*seal_fail_ratio \u6216\u59d4\u6258\u7b14\u6570\u8870\u7aed\uff08seal_low \u9996\u89e6\u53d1\uff0c\u9632\u70b8\u677f\u63d0\u524d\u8d70\uff09
        if BLS.get('seal_low_sell_enabled', True) and ft.get('seal_low'):
            if getattr(g, 'seal_batch_unhealthy', False):
                log.info('[seal-low-guard] %s 本帧 L2 整批缺失 -> SEAL_LOW 跳过卖出，等待恢复' % _sn(sec))
                continue
            _cts = ft.get('seal_low_confirm_ts') or 0.0
            _cnf = float(BLS.get('seal_low_confirm_sec', 6.0) or 0.0)
            _fast = bool(ft.get('seal_low_fast') or False)
            if _fast:
                log.info('[seal-low-guard] %s SEAL_LOW_FAST 1帧确认 -> 立即卖出' % _sn(sec))
            elif _cnf > 0 and (time.time() - _cts) < _cnf:
                _skip_log('seal', sec, 'confirm_wait',
                          '[seal-low-guard] %s SEAL_LOW 单帧待确认 age=%.0fs < %.0fs -> 不卖' % (
                              _sn(sec), time.time() - _cts, _cnf),
                          throttle_sec=3.0)
                continue
            if sec not in (getattr(g, 'seal_sold', None) or set()):
                _do_sell(context, sec, amt,
                         'TICK_seal_low_sell ratio<=%.2f' % float(BLS.get('seal_fail_ratio', 0.333)),
                         mode='sell_break')   # v1.10 封单衰减紧急卖出统一 L2 买N档+0.95 下限定价
                _mark_sold_event(sec, 'seal')
                continue
        # \u6025\u5356\u8fc1\u79fb\uff1aP1 \u7eff\u5f00 / P2E \u9884\u671f miss / P3 \u6b62\u635f\uff083s \u54cd\u5e94\uff1b\u6838\u5356\u9650\u4ef7\u8dcc\u505c\u5730\u677f\u4ef7\u4fdd\u6210\u4ea4\uff09
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open_tick drop=%.1f%%' % _auction_change(sec), urgent=True); continue
        _hit2, _note2 = _p2e_core_sell_check(sec)[:2]
        if _hit2:
            _do_sell(context, sec, amt, _note2, urgent=True); continue
        cost = my_cost(_raw, positions)
        if cost > 0:
            pnl = px / cost - 1.0
            if pnl <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss_tick pnl=%.1f%%' % (pnl * 100), urgent=True); continue
        # v0.59 P7 持仓卖出闭环（docs/33）：P7a 连板放量不封板 / P7b 跟风拉升不封板 / P7c 首板次日不主动冲板分批清仓
        if BLS.get('p7_sell_enabled', True):
            _p7a = _p7a_check(sec, amt)
            if _p7a and sec not in (getattr(g, 'p7a_sold', None) or set()):
                _do_sell(context, sec, _p7a[1], _p7a[0]); _mark_p7(sec, 'p7a'); continue
            _p7b = _p7b_check(sec, amt)
            if _p7b and sec not in (getattr(g, 'p7b_sold', None) or set()):
                _do_sell(context, sec, _p7b[1], _p7b[0]); _mark_p7(sec, 'p7b'); continue
            _p7c = _p7c_check(sec, amt)
            if _p7c:
                _do_sell(context, sec, _p7c[1], _p7c[0], cool=False); _save_state(); continue
            _p7d = _p7d_check(sec, amt)
            if _p7d and sec not in (getattr(g, 'p7d_sold', None) or set()):
                _do_sell(context, sec, _p7d[1], _p7d[0]); _mark_p7(sec, 'p7d'); continue
        # v0.65 P8 中高位兑现指导（docs/43）：高位分歧/切低位 + 中位股晋级失败 -> 减半兑现（tick 3s 兜底）
        _p8 = _lb_senti_cut_hold(sec)
        if _p8:
            _q8 = int(int(amt * float(_p8[0])) // 100) * 100
            if _q8 < 100:
                _q8 = amt if amt < 100 else 100
            _do_sell(context, sec, _q8, _p8[1]); _mark_lb_cut(sec); continue
        # v0.53 持仓监控全覆盖：P4 预期三态 / P5 评分清仓 / P6 评分半仓 3s 评估（1m sell_manager 保留兜底）
        if not BLS.get('tick_full_sell_enabled', True):
            continue
        if int(getattr(g, 'sellscan_used', 0)) >= int(BLS.get('frame_sellscan_limit', 8)):
            continue
        g.sellscan_used = int(getattr(g, 'sellscan_used', 0)) + 1
        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word' and _is_one_word_open(sec):
                st4, _r4 = _exp_one_word(sec, quiet=True)
                if st4 in (CS, PS):
                    _do_sell(context, sec, amt, 'P4_exp_one_word_tick ' + st4); continue
            else:
                if g.exp[sec].get('entry_type') == 'one_word' and not _is_one_word_open(sec):
                    _hold_arb_log(sec, '文件 entry_type=one_word 但实时已开板 -> 回落普通分时三态')
                au4 = g.exp[sec].get('auction_status') or _eval_auction(sec)[0]
                st4 = _eval_intraday(sec, au4)[0]
                if st4 in (PS, CS):
                    _do_sell(context, sec, amt, 'P4_exp_miss_tick ' + st4); continue
        # P5/P6 评分：hist1d 数据缺失/预算降级 -> 跳过（防降级误触发），1m 兜底
        if _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0) is None:
            continue
        sc = score_now(sec)
        if sc is None:
            continue   # v0.68 评分未就绪 -> 跳过 P5/P6（防数据真空误卖）
        if sc < BLS['score_sell_clear'] * rp['score_clear_adj']:
            _p6_weak_reset(sec)
            _do_sell(context, sec, amt, 'P5_score_clear_tick score=%.1f' % sc)
        elif sc < BLS['score_sell_half'] * rp['score_half_adj']:
            if BLS.get('p6_two_frame_enabled', True):
                _cnt, _trig, _note = _p6_weak_step(sec, sc)
                log.info(_note)
                if not _trig:
                    continue
            _p6_weak_reset(sec)
            half = int(amt * float(BLS.get('sell_half_ratio', 0.5)))
            qty = int(half // 100) * 100
            if qty < 1:
                qty = amt if amt < 100 else 100
            if qty > amt:
                qty = amt
            _do_sell(context, sec, qty, 'P6_score_half_tick score=%.1f' % sc)
        else:
            _p6_weak_reset(sec)


def _mark_sold_event(sec, kind):
    # \u4e8b\u4ef6\u5356\u51fa\u9996\u89e6\u53d1\u6807\u8bb0\uff08\u8de8\u91cd\u542f\u6301\u4e45\u5316\uff0c\u9632\u540c\u65e5\u91cd\u542f\u540e\u5bf9\u5df2\u70b8\u677f/\u5df2\u8870\u7aed\u6807\u7684\u91cd\u590d\u5356\uff09
    try:
        key = 'break_sold' if kind == 'break' else ('break2_sold' if kind == 'break2' else 'seal_sold')
        st = getattr(g, key, None)
        if not isinstance(st, set):
            st = set(); setattr(g, key, st)
        st.add(sec)
        _save_state()
    except Exception:
        pass

# ================= v0.59 持仓地位评估 + P7 卖出闭环（docs/33） =================
def _hold_stand_pts(role, active, board):
    # 持仓地位评分（仅持仓消费）：leader+3 / follower-1 / mid-3 / active+3 / 跟风-3 / 板块弱-3
    pts = 0.0
    pts += {'leader': 3.0, 'follower': -1.0, 'mid': -3.0}.get(role, 0.0)
    pts += {'active': 3.0, 'follow': -3.0}.get(active, 0.0)
    if board == 'weak':
        pts -= 3.0
    return pts


def _hold_board_strong(sec):
    # 板块加持（v0.59 P7b）：板块强度>=p7b_board_min 或 所属题材存活龙头/发酵前排封板
    try:
        if _board_strength(sec) >= float(BLS.get('p7b_board_min', 1.0) or 1.0):
            return True
        st = _dyn_theme_status()
        for nm in _zt_themes_of(sec):
            d = st.get(nm) or {}
            ld = d.get('leader')
            if ld and _sealed_now(ld):
                return True
        fm = _dyn_theme_ferment()
        for nm in _new_themes_of(sec):
            d = fm.get(nm) or {}
            if d.get('confirmed') and d.get('front') and _sealed_now(d['front']):
                return True
    except Exception:
        pass
    return False


def _hold_stand(sec):
    # v0.59 持仓地位评估（docs/33）：role（leader/follower/mid/outside）+ active（主动/跟风/中性）+ board（强/平/弱）
    # 15s 节流缓存；评分仅持仓消费（leader+3/follower-1/mid-3/active+3/跟风-3/板块弱-3），日志 [hold] 60s/股节流
    try:
        cache = getattr(g, 'hold_stand_cache', None)
        if not isinstance(cache, dict):
            cache = {}; g.hold_stand_cache = cache
        now = time.time()
        hit = cache.get(sec)
        if hit and now - float(hit.get('ts') or 0) < float(BLS.get('hold_stand_cache_sec', 15.0) or 15.0):
            return hit
        role = 'outside'; active = 'neutral'; board = 'mid'
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        cnt = int(zt.get('board_cnt') or 0)
        if _dyn_theme_leader(sec):
            role = 'leader'
        elif zt and cnt >= 1:
            if 2 <= cnt <= 5 and not zt.get('unique_high'):
                role = 'mid'
            else:
                # 池内非龙头：同题材有存活更高身位 -> follower，否则 outside
                st = _dyn_theme_status()
                is_fol = False
                for nm in _zt_themes_of(sec):
                    d = st.get(nm) or {}
                    if d.get('leader') and d.get('leader') != sec and int(d.get('alive_count') or 0) > 1:
                        is_fol = True; break
                role = 'follower' if is_fol else 'outside'
        # active：主动=涨幅显著强于所属板块均值；跟风=板块强但个股明显弱于板块
        try:
            my_chg = _sector_chg(sec) * 100.0
            bstr = _board_strength(sec)
            if bstr > 0 and my_chg >= bstr + float(BLS.get('p7c_active_threshold', 0.5) or 0.5):
                active = 'active'
            elif bstr >= 1.0 and my_chg <= bstr - float(BLS.get('p7c_active_threshold', 0.5) or 0.5):
                active = 'follow'
        except Exception:
            pass
        # board：强=板块强度>=p7b_board_min 或题材龙头封板；弱=板块强度<=-1；平=其它
        try:
            if _hold_board_strong(sec):
                board = 'strong'
            elif _board_strength(sec) <= -1.0:
                board = 'weak'
            else:
                board = 'mid'
        except Exception:
            pass
        out = {'ts': now, 'role': role, 'active': active, 'board': board}
        cache[sec] = out
        gl = getattr(g, 'hold_stand_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.hold_stand_log = gl
        if now - float(gl.get(sec) or 0) >= float(BLS.get('hold_stand_log_sec', 60.0) or 60.0):
            gl[sec] = now
            log.info('[hold] %s role=%s active=%s board=%s pts=%+.1f' % (
                _sn(sec), role, active, board, _hold_stand_pts(role, active, board)))
        return out
    except Exception:
        return {'ts': time.time(), 'role': 'outside', 'active': 'neutral', 'board': 'mid'}


def _p7a_check(sec, amt):
    # v0.59 P7a 连板放量不封板（docs/33）：持仓 + T-1 board_cnt>=2 + 今日量>=昨日量×p7a_vol_ratio + 未封板
    # 唯一身位降级减半（p7a_half_ratio=0.5），否则清仓；现价限价非地板价。返回 (note, qty) 或 None。
    if not BLS.get('p7_sell_enabled', True):
        return None
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
    if int(zt.get('board_cnt') or 0) < 2:
        return None
    if _sealed_now(sec):
        return None
    df = _hist_1d(sec, prio=1 if _is_hist_priority(sec) else 0)
    if df is None or len(df) < 2:
        return None
    vols = list(df['volume'])
    yv = float(vols[-2] or 0.0)   # 昨日量（hist1d [-1]=今日 [-2]=昨日，与 _volume_ratio 同口径；[vol] 探针核对单位）
    tv = _snap_vol(g.spot.get(sec) or {})
    if yv <= 0 or tv <= 0:
        return None
    if tv < yv * float(BLS.get('p7a_vol_ratio', 1.10) or 1.10):
        return None
    if _unique_stand(sec):
        half = int(amt * float(BLS.get('p7a_half_ratio', 0.5) or 0.5))
        half = int(half // 100) * 100
        qty = half if half >= 100 else amt
        return ('P7a_vol_break_half vol=%.0f yv=%.0f' % (tv, yv), qty)
    return ('P7a_vol_break vol=%.0f yv=%.0f' % (tv, yv), amt)


def _p7b_check(sec, amt):
    # v0.59 P7b 跟风拉升不封板（docs/33）：持仓 + role∈(follower,outside) + 板块强 + 1m surge>=p7b_surge_min + 未封板 -> 减半
    if not BLS.get('p7_sell_enabled', True):
        return None
    st = _hold_stand(sec)
    if st.get('role') not in ('follower', 'outside'):
        return None
    if st.get('board') != 'strong':
        return None
    if _sealed_now(sec):
        return None
    sg = _elastic_1m_surge(sec)
    if sg < float(BLS.get('p7b_surge_min', 1.5) or 1.5):
        return None
    half = int(amt * float(BLS.get('p7b_half_ratio', 0.5) or 0.5))
    half = int(half // 100) * 100
    qty = half if half >= 100 else amt
    return ('P7b_follow_break surge=%.1f%%' % sg, qty)


def _p7c_check(sec, amt):
    # v0.59 P7c 首板次日不主动冲板 -> 冲高分批清仓（docs/33）：T-1 board_cnt==1 + 09:30-10:00 窗口 active!=主动
    # 标记 p7c_price；现价>=标记价×(1+p7c_surge_min%) -> 每 p7c_batch_cold_secs(10s) 卖一批（2×50%）；回封取消标记；
    # 破 VWAP 由 P4 兜底。返回 (note, qty) 或 None（含标记/取消副作用）。
    if not BLS.get('p7_sell_enabled', True):
        return None
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
    if int(zt.get('board_cnt') or 0) != 1:
        return None
    if _min_age() > int(BLS.get('p7c_until_minute', 30) or 30):
        return None
    # 回封取消标记（若回封涨停则不再继续卖，等待后续重新标记）
    if _today_zt(sec) or _sealed_now(sec):
        part = getattr(g, 'p7c_part', None)
        if isinstance(part, dict) and sec in part:
            del part[sec]
        sold = getattr(g, 'p7c_sold', None)
        if isinstance(sold, set) and sec in sold:
            sold.discard(sec)
        return None
    st = _hold_stand(sec)
    if st.get('active') == 'active':
        part = getattr(g, 'p7c_part', None)
        if isinstance(part, dict) and sec in part:
            del part[sec]
        return None
    part = getattr(g, 'p7c_part', None)
    if not isinstance(part, dict):
        part = {}; g.p7c_part = part
    px = last_px(sec) or 0.0
    rec = part.get(sec)
    if rec is None:
        part[sec] = {'ts': time.time(), 'price': px}
        return None
    tripx = float(rec.get('price') or 0.0) * (1.0 + float(BLS.get('p7c_surge_min', 1.5) or 1.5) / 100.0)
    if px < tripx:
        return None
    now = time.time()
    cold = float(BLS.get('p7c_batch_cold_secs', 10.0) or 10.0)
    if rec.get('sold1_ts'):
        if now - float(rec['sold1_ts']) < cold:
            return None
        qty = min(int(float(rec.get('half') or amt)), amt)
        if qty < 100:
            qty = amt
        part.pop(sec, None)
        sold = getattr(g, 'p7c_sold', None)
        if not isinstance(sold, set):
            sold = set(); g.p7c_sold = sold
        sold.add(sec)
        return ('P7c_passive_sweep b2 px=%.2f tripx=%.2f' % (px, tripx), qty)
    half = int(amt * 0.5)
    half = int(half // 100) * 100
    if half < 1:
        half = amt if amt < 100 else 100
    rec['half'] = half
    rec['sold1_ts'] = now
    return ('P7c_passive_sweep b1 px=%.2f tripx=%.2f' % (px, tripx), half)


def _p7d_check(sec, amt):
    # v1.19 P7d 核心冲高偏离（docs/33 扩展）：核心(CORE=连板>=3) + 非唯一身位 + 冲高逼近涨停未封板
    # + 现价偏离分时均价过远 -> 减半兑现，防冲高回落无溢价。
    if not BLS.get('p7d_sell_enabled', True):
        return None
    if _limitup_days(sec) < 3:
        return None                      # CORE 口径与 _tags 一致，不调 100 日新高减负
    if _unique_stand(sec):
        return None                      # 唯一性龙头不执行
    if _sealed_now(sec) or _today_zt(sec):
        return None                      # 已封板/涨停不卖
    s = g.spot.get(sec) or {}
    px = last_px(sec) or 0.0
    up = float(s.get('up_px') or 0.0)
    vwap = float(s.get('wavg_px') or 0.0)
    if not (px > 0 and up > 0 and vwap > 0):
        return None                      # 数据缺失保守不卖
    if px < up * (1.0 - float(BLS.get('p7d_limit_gap', 0.04) or 0.04)):
        return None                      # 未进入冲高区
    if px < vwap * (1.0 + float(BLS.get('p7d_vwap_dev_min', 3.0) or 3.0) / 100.0):
        return None                      # 偏离分时均价不足
    half = int(amt * float(BLS.get('p7d_half_ratio', 0.5) or 0.5))
    half = int(half // 100) * 100
    qty = half if half >= 100 else amt
    return ('P7d_core_surge_dev px=%.2f up=%.2f vwap=%.2f dev=%.1f%%' % (
        px, up, vwap, (px / vwap - 1.0) * 100.0), qty)


def _mark_p7(sec, kind):
    # v0.59 P7a/P7b 事件卖出首触发标记（跨重启持久化，防同日重启后重复卖）
    try:
        key = 'p7a_sold' if kind == 'p7a' else ('p7b_sold' if kind == 'p7b' else 'p7d_sold')
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
        # v0.59 [vol] 探针：核对 P7a 量比单位（快照 volume vs hist1d 最后两根；[-1]=今日 [-2]=昨日 口径）
        try:
            _dfv = _hist_1d(sec)
            _vv = list(_dfv['volume']) if _dfv is not None and len(_dfv) >= 2 else []
            _sv = g.spot.get(sec) or {}
            log.info('[vol] %s snap business_amount=%s volume=%s trd_volume=%s hist1d[-1]=%s hist1d[-2]=%s' % (
                _sn(sec), _sv.get('business_amount'), _sv.get('volume'), _sv.get('trd_volume'),
                (_vv[-1] if len(_vv) >= 1 else 'NA'), (_vv[-2] if len(_vv) >= 2 else 'NA')))
        except Exception:
            pass
        g.l2_probed = True
    except Exception as e:
        _warn('l2 probe fail: %r' % e)

def _tick_targets():
    # tick 采集目标：持仓 + universe 恒有 + near_scan 近涨停补充 + watch 前 N（控 3s 帧负担，避免丢帧）
    # v0.74 near_scan 优先于 watch：新发酵票从 scan 命中起即被 3s 帧盯住，首触不再等整轮轮询
    # v0.36 帧缓存：同一 3s 帧内多消费（snapshot/gear 限额动态化）复用，避免重复 get_positions
    tok = int(time.time() / 3.0)
    _c = getattr(g, 'tick_targets_cache', None) or {}
    if _c.get('tok') == tok:
        return _c['secs']
    pos = list(get_positions())
    _skip_st = BLS.get('skip_st_pool', True)
    if _skip_st:
        _warm_name_map(list(BLS['universe']) + (g.pool_static or []) + list((getattr(g, 'near_scan', None) or {}).keys()) + (g.watch or []))
    uni = [x for x in BLS['universe'] if x not in pos and not (_skip_st and _is_st(x))]
    static = [x for x in (g.pool_static or []) if x not in pos and x not in uni and not (_skip_st and _is_st(x))]
    ft = getattr(g, 'first_zt', None) or {}
    near_cap = int(BLS.get('tick_near_cap', 12))
    near = [x for x in (getattr(g, 'near_scan', None) or {})
            if x not in pos and x not in uni and x not in static and x not in ft and not (_skip_st and _is_st(x))][:near_cap]
    cap = int(BLS.get('tick_watch_cap', 15))
    watch = [x for x in (g.watch or []) if x not in pos and x not in uni and x not in static and x not in near and not (_skip_st and _is_st(x))][:cap]
    out = pos + uni + near + static + watch
    if BLS.get('tick_board_scan', True) and _fast_window():
        # v0.48/v1.36 快速窗口生效：开盘首板窗口 + 13:00-13:30 午后通道同享板块成员采集
        try:
            top3 = _board_rank_top3_set(_pool() or out)
            if top3:
                _cap_m = int(BLS.get('tick_board_member_cap', 10))
                for _b in top3:
                    for _m in _board_members_file(_b, _cap_m):
                        if _m and _m not in out and _m not in pos and not (_skip_st and _is_st(_m)):
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


def _tick_seed_cands(_near):
    # v0.74 近涨停 L2 播种候选：逐笔 near + near_scan 未首触票（未到 0.98 也补历史大单，防无数据当无大单）
    out = list(_near or [])
    ft = getattr(g, 'first_zt', None) or {}
    _skip_st = BLS.get('skip_st_pool', True)
    for s in (getattr(g, 'near_scan', None) or {}):
        if s not in ft and s not in out and not (_skip_st and _is_st(s)):
            out.append(s)
    return out


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
    _td = str(get_trading_day()).replace('-', '')
    if len(_td) == 8 and _td.isdigit():
        day_open = int(_td + '093000000')
    else:
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


def _rows_have_limit_tx(sec, rows, fields):
    # v1.12 重建诊断：逐笔中是否存在 09:30 后涨停价成交（区分“未涨停正确放弃”与“回看失败”）
    if not rows or not isinstance(rows, list):
        return False
    try:
        def _idx(name, default):
            return fields.index(name) if name in fields else default
        i_t = _idx('business_time', 0); i_p = _idx('hq_px', 1)
        u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
        if u <= 0:
            return False
        _td = str(get_trading_day()).replace('-', '')
        if len(_td) == 8 and _td.isdigit():
            day_open = int(_td + '093000000')
        else:
            lt = time.localtime()
            day_open = int('%04d%02d%02d093000000' % (lt.tm_year, lt.tm_mon, lt.tm_mday))
        for row in rows:
            try:
                ms = int(row[i_t]); px = float(row[i_p])
                if ms >= day_open and px >= u - 1e-9:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _tx_dir(v):
    # v0.51 方向映射按官方字典校准（l2_big_dir_map 可配置纠偏）：0=卖、1=买、2=借入/3=出借->不计净量；'B'/'buy'/'买'/'S'/'sell'/'卖' 字符串兼容
    try:
        if v is None:
            return None
        sv = str(v).strip().lower()
        if sv in ('', 'none'):
            return None
        _m = BLS.get('l2_big_dir_map') or {}
        if sv in _m:
            _r = _m[sv]
            return _r if _r in ('buy', 'sell') else None
        if sv in ('b', 'buy', '买'):
            return 'buy'
        if sv in ('s', 'sell', '卖'):
            return 'sell'
    except Exception:
        pass
    return None


def _tx_big_feed(secs, fields, raw):
    # v0.47 L2 大单累计：逐笔 business_amount 按 trade_index 去重（防跨帧重复），累计当日大单金额
    # v0.50 方向分计：buy/sell/un 累计，净量 = 买-卖（l2_big_dir_enabled）
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
    i_a = _idx('business_amount', -1); i_t = _idx('trade_index', -1); i_p = _idx('hq_px', -1); i_d = _idx('business_direction', -1); i_bt = _idx('business_time', -1)
    if i_a < 0:
        return
    unit = str(BLS.get('l2_big_amt_unit', 'shares')).lower()   # v0.48 business_amount 单位换算
    mult = 100.0 if unit == 'lots' else 1.0
    yuan_mode = (unit == 'yuan')
    dir_on = BLS.get('l2_big_dir_enabled', True)
    acc = getattr(g, 'l2_big', None)
    if acc is None:
        acc = {}; g.l2_big = acc
    probed = getattr(g, 'l2_big_probed', None)
    if probed is None:
        probed = set(); g.l2_big_probed = probed
    wm = getattr(g, 'l2_big_wm', None)
    if wm is None:
        wm = {}; g.l2_big_wm = wm
    dist = getattr(g, 'l2_dir_dist', None)
    if dist is None:
        dist = {}; g.l2_dir_dist = dist
    _cap = int(BLS.get('l2_big_seen_cap', 20000))
    for sec in secs:
        rows = raw.get(sec) or []
        if not rows:
            continue
        a = acc.setdefault(sec, {'amt': 0.0, 'buy': 0.0, 'sell': 0.0, 'un': 0.0,
                                 'bn': 0, 'sn': 0, 'un_n': 0, 'seen': set(), 'max': 0.0, 'first_ts': None})
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
                if i_bt >= 0:
                    _bt = int(row[i_bt])
                    if _bt <= wm.get(sec, 0):
                        continue
                va = float(row[i_a])
                if yuan_mode:
                    yuan = va
                else:
                    px = float(row[i_p]) if i_p >= 0 else 0.0
                    yuan = va * mult * px
                if yuan >= min_amt:
                    a['amt'] += yuan
                    if yuan > a.get('max', 0.0):
                        a['max'] = yuan
                    if i_bt >= 0 and _bt > wm.get(sec, 0):
                        wm[sec] = _bt
                    if dir_on and i_d >= 0:
                        _rk = str(row[i_d]).strip().lower()
                        dist[_rk] = dist.get(_rk, 0) + 1
                    if dir_on:
                        _d = _tx_dir(row[i_d]) if i_d >= 0 else None
                        if _d == 'buy':
                            a['buy'] += yuan
                            a['bn'] = a.get('bn', 0) + 1
                        elif _d == 'sell':
                            a['sell'] += yuan
                            a['sn'] = a.get('sn', 0) + 1
                        else:
                            a['un'] += yuan
                            a['un_n'] = a.get('un_n', 0) + 1
            except Exception:
                continue
        now = time.time()
        log_ts = getattr(g, 'l2_big_log_ts', None)
        if log_ts is None:
            log_ts = {}; g.l2_big_log_ts = log_ts
        first = sec not in probed
        # v0.67 分钟节流重复打印：首帧立即，之后按 l2_big_log_sec 间隔重打（盘中核对累计变化）
        if first or now - log_ts.get(sec, 0.0) >= float(BLS.get('l2_big_log_sec', 300)):
            probed.add(sec)
            log_ts[sec] = now
            r = _l2_big_ratio(sec)
            _to = _l2_big_turnover(sec)
            if dir_on:
                _dd = '{%s}' % ', '.join('%s:%d' % (k, dist[k]) for k in sorted(dist)) if dist else '{}'
                log.info('[l2-big] %s 大单买=%.0f(%d笔) 卖=%.0f(%d笔) 净=%.0f 占比=%.2f%% 分母=%.0f 未知=%.0f(%d笔) 最大单笔=%.0f元 全局分布=%s (阈值=%.0f unit=%s)' % (
                    _sn(sec), a.get('buy', 0.0), a.get('bn', 0), a.get('sell', 0.0), a.get('sn', 0),
                    a.get('buy', 0.0) - a.get('sell', 0.0), r * 100.0 if r >= 0 else -1.0, _to,
                    a.get('un', 0.0), a.get('un_n', 0), a.get('max', 0.0), _dd, min_amt, unit))
                # direction 全部未识别告警仍只在首帧（后续重复打印不刷屏）
                if first and a.get('amt', 0.0) > 0 and a.get('buy', 0.0) <= 0 and a.get('sell', 0.0) <= 0:
                    w = getattr(g, 'l2_big_dir_warn', None)
                    if w is None:
                        w = set(); g.l2_big_dir_warn = w
                    if sec not in w:
                        w.add(sec)
                        log.info('[l2-big] %s 逐笔 direction 全部未识别(未知=%.0f) 净量口径待探针校准' % (_sn(sec), a.get('un', 0.0)))
            else:
                log.info('[l2-big] %s 累计大单=%.0f 占比=%.2f%% 分母=%.0f 最大单笔=%.0f元 (阈值=%.0f unit=%s)' % (
                    _sn(sec), a['amt'], r * 100.0 if r >= 0 else -1.0, _to, a.get('max', 0.0), min_amt, unit))


def _fmt_tick_ts(ms):
    # v0.52 毫秒时间戳 -> HH:MM:SS.mmm（探针/播种日志）
    try:
        ms = int(ms)
        return '%02d:%02d:%02d.%03d' % ((ms // 10000000) % 100, (ms // 100000) % 100, (ms // 1000) % 100, ms % 1000)
    except Exception:
        return str(ms)


def _l2_big_seed(secs, pages=None):
    # v0.52 已成交大单回看播种：get_tick_direction 分时成交行情（含竞价终态 09:25 与重启前已成交），
    # 分笔 business_balance >= l2_big_amt_min 且 time_stamp > 水印才计入（与 live 逐笔水印防重，双源不重复）；
    # 播种只推进水印不写 seen（分笔无 trade_index），live 逐笔按 business_time>水印 跳过已覆盖时段。
    if not BLS.get('l2_tickdir_enabled', True) or not secs:
        return
    try:
        min_amt = float(BLS.get('l2_big_amt_min', 1000000.0))
        if min_amt <= 0:
            return
        pages = int(pages or BLS.get('l2_tickdir_pages', 3))
        count = 200
        wm = getattr(g, 'l2_big_wm', None)
        if wm is None:
            wm = {}; g.l2_big_wm = wm
        acc = getattr(g, 'l2_big', None)
        if acc is None:
            acc = {}; g.l2_big = acc
        dist = getattr(g, 'l2_dir_dist', None)
        if dist is None:
            dist = {}; g.l2_dir_dist = dist
        seeded = getattr(g, 'l2_big_seeded', None)
        if seeded is None:
            seeded = set(); g.l2_big_seeded = seeded
        all_rows = {}
        flds = []
        try:
            for pg in range(max(1, pages)):
                raw = get_tick_direction(secs, start_pos=pg * count, search_direction=1, data_count=count, is_dict=True) or {}
                if pg == 0:
                    flds = raw.get('fields') or []
                for _sec in secs:
                    rws = raw.get(_sec) or []
                    if not rws:
                        continue
                    all_rows.setdefault(_sec, []).extend(rws)
        except Exception as e:
            log.info('[tickdir] pull fail %r' % e)
        for sec in secs:
            rows = all_rows.get(sec) or []
            if not rows:
                continue
            def _idx(name, default):
                return flds.index(name) if name in flds else default
            i_t = _idx('time_stamp', 0); i_b = _idx('business_balance', -1); i_d = _idx('business_direction', -1)
            if i_b < 0:
                log.info('[tickdir] %s fields 缺 business_balance 跳过' % _sn(sec)); continue
            a = acc.setdefault(sec, {'amt': 0.0, 'buy': 0.0, 'sell': 0.0, 'un': 0.0,
                                     'bn': 0, 'sn': 0, 'un_n': 0, 'seen': set(), 'max': 0.0, 'first_ts': None})
            w = wm.get(sec, 0); w_new = w; big = 0; first_ts = None; n = 0; seen_ts = set()
            for row in rows:
                try:
                    ts = int(row[i_t])
                except Exception:
                    continue
                n += 1
                if ts in seen_ts:
                    continue
                seen_ts.add(ts)
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if ts <= w:
                    continue
                if ts > w_new:
                    w_new = ts
                try:
                    bal = float(row[i_b])
                except Exception:
                    continue
                if bal < min_amt:
                    continue
                big += 1
                a['amt'] += bal
                if bal > a.get('max', 0.0):
                    a['max'] = bal
                if i_d >= 0:
                    _rk = str(row[i_d]).strip().lower()
                    dist[_rk] = dist.get(_rk, 0) + 1
                _d = _tx_dir(row[i_d]) if i_d >= 0 else None
                if _d == 'buy':
                    a['buy'] += bal
                    a['bn'] = a.get('bn', 0) + 1
                elif _d == 'sell':
                    a['sell'] += bal
                    a['sn'] = a.get('sn', 0) + 1
                else:
                    a['un'] += bal
                    a['un_n'] = a.get('un_n', 0) + 1
            a['first_ts'] = first_ts
            wm[sec] = w_new
            if sec not in seeded:
                seeded.add(sec)
                log.info('[tickdir] %s 首笔=%s 条数=%d 大单分笔=%d 水印=%s (阈值=%.0f)' % (
                    _sn(sec), _fmt_tick_ts(first_ts), n, big, _fmt_tick_ts(w_new), min_amt))
    except Exception as e:
        _warn('l2_big_seed fail %r' % e)


def _rebuild_first_zt_queue():
    # v0.75 同日重启登记：候选 = 买入池 + 持仓 + 预期文件，缺失 first_zt 且非 ST 的票排队，
    # 由 tick 帧分批重建（ms 优先用 _l2_big_seed 回看首笔，其次逐笔回看，最后快照时间戳）。
    cands = [x for x in dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])]
    pending = getattr(g, 'first_zt_rebuild_pending', None)
    if pending is None:
        pending = []; g.first_zt_rebuild_pending = pending
    ft = getattr(g, 'first_zt', None) or {}
    added = 0
    for sec in cands:
        if sec in ft or sec in pending or _is_st(sec):
            continue
        pending.append(sec)
        try:
            g.first_zt_rebuild_ts[sec] = time.time()   # v0.80 入队时间戳（超时放弃判定）
        except Exception:
            pass
        added += 1
    if added:
        log.info('[restart-rebuild] 登记待重建首触 %d 家（新增 %d）' % (len(pending), added))


def _rebuild_first_zt_tick():
    # v0.76 tick/1m 消化重建队列：不要求“当前仍封板”（当日已涨停即可重建），
    # 缺涨停价的票批量补快照（一次 RPC），仍缺则 30s 后重试且不阻塞后续批次；
    # ms 只取 _parse_tx_zt_ms 最早涨停价成交，失败才降级快照 hsTimeStamp；
    # 记录 src=restart_rebuild / restart_rebuild_fallback，幂等（已有记录/ST 跳过）。
    pending = getattr(g, 'first_zt_rebuild_pending', None)
    if not pending:
        return
    now = time.time()
    # v1.5 放弃判定改重试轮次：不再用入队墙钟/10:00 一刀切（12:16 午后重启 13:00 首帧曾把
    # 整队 34 家误杀）；每票实际尝试 first_zt_rebuild_max_attempts 次仍无涨停证据才放弃。
    # 当日有涨停证据的票首次尝试即可由 tx 回看重建，无证据票（今日未涨停）轮次耗尽自然移出。
    _max_att = max(1, int(BLS.get('first_zt_rebuild_max_attempts', 8) or 8))
    _attempts = getattr(g, 'first_zt_rebuild_attempts', None)
    if _attempts is None:
        _attempts = {}; g.first_zt_rebuild_attempts = _attempts
    _giveup = []
    for _sec in list(pending):
        if int(_attempts.get(_sec, 0) or 0) >= _max_att:
            _giveup.append(_sec)
    if _giveup:
        for _sec in _giveup:
            _px = last_px(_sec) or 0.0
            _up = float((g.spot.get(_sec) or {}).get('up_px') or 0.0)
            _had = bool((getattr(g, 'first_zt_rebuild_zt_seen', None) or {}).get(_sec))
            _hit = int((getattr(g, 'first_zt_rebuild_zt_hit', None) or {}).get(_sec) or 0)   # v1.35 回看命中笔数审计
            log.info('[restart-rebuild] 放弃(重试%d轮无涨停证据) %s last=%.2f up=%.2f had_zt=%d tx_zt_hit=%d'
                     % (_max_att, _sn(_sec), _px, _up, int(_had), _hit))
            try:
                _gu = getattr(g, 'first_zt_rebuild_gave_up', None)
                if _gu is None:
                    _gu = set(); g.first_zt_rebuild_gave_up = _gu
                _gu.add(_sec)   # v1.35 后续 tick 正常补建时打 rebuilt_later 审计
            except Exception:
                pass
        pending[:] = [x for x in pending if x not in set(_giveup)]
        if not pending:
            _restart_rebuild_heartbeat(now, done=len(_giveup), wait=0)
            return
    cap = int(BLS.get('first_zt_rebuild_cap', 5))
    retry = getattr(g, 'first_zt_rebuild_retry_ts', None)
    if retry is None:
        retry = {}; g.first_zt_rebuild_retry_ts = retry
    ft = getattr(g, 'first_zt', None)
    if ft is None:
        ft = {}; g.first_zt = ft
    retry_sec = float(BLS.get('first_zt_rebuild_retry_sec', 30.0))
    done = set()
    wait = set()
    got = []
    # 本帧可处理票：已有记录/ST 移出；冷却中的票不占 cap，避免无快照票阻塞后续批次。
    batch = []
    for sec in pending:
        if sec in ft:
            done.add(sec)
            continue
        if _is_st(sec):
            done.add(sec)
            continue
        if now - float(retry.get(sec, 0.0) or 0.0) < retry_sec:
            continue
        batch.append(sec)
        _attempts[sec] = int(_attempts.get(sec, 0) or 0) + 1   # v1.5 实际尝试轮次（进批即计）
        if len(batch) >= cap:
            break
    if not batch:
        _restart_rebuild_heartbeat(now)
        return
    # 缺涨停价的票先批量补快照（一次 RPC），仍缺则 30s 后重试，不阻塞本批次其余票。
    try:
        _need_snap = [sec for sec in batch if not float((g.spot.get(sec) or {}).get('up_px') or 0.0)]
        if _need_snap:
            _get_ds().snapshot(_need_snap)
    except Exception:
        pass
    need_tx = []
    for sec in batch:
        s = g.spot.get(sec) or {}
        u = float(s.get('up_px') or 0.0)
        if u <= 0:
            wait.add(sec)
            continue
        need_tx.append(sec)
    if need_tx:
        try:
            raw = get_individual_transaction(need_tx, data_count=int(BLS.get('first_zt_rebuild_tx_count', 200)), is_dict=True) or {}
            fields = raw.get('fields') or []
            for sec in need_tx:
                _rows = raw.get(sec) or []
                if _rows_have_limit_tx(sec, _rows, fields):
                    try:
                        g.first_zt_rebuild_zt_seen[sec] = True
                    except Exception:
                        pass
                    try:   # v1.35 命中轮次累计（放弃日志 tx_zt_hit 用）
                        _zh = getattr(g, 'first_zt_rebuild_zt_hit', None)
                        if not isinstance(_zh, dict):
                            _zh = {}; g.first_zt_rebuild_zt_hit = _zh
                        _zh[sec] = int(_zh.get(sec) or 0) + 1
                    except Exception:
                        pass
                ms = _parse_tx_zt_ms(sec, _rows, fields)
                src = 'restart_rebuild'
                if ms is None:
                    _s2 = g.spot.get(sec) or {}
                    _last = float(_s2.get('last_px') or 0.0)
                    _u2 = float(_s2.get('up_px') or 0.0)
                    h = _s2.get('hsTimeStamp') or 0
                    # 逐笔无涨停价成交时，仅当前仍封板可用快照时间戳兜底；
                    # 从未涨停的票不能靠 hsTimeStamp 误建首触。
                    if h and _u2 > 0 and _last >= _u2 - 1e-9:
                        ms = int(h)
                        src = 'restart_rebuild_fallback'
                if ms is not None:
                    got.append((sec, ms, src))
                else:
                    wait.add(sec)
        except Exception as _e:
            _warn('restart-rebuild tx fail: %r' % _e)
            wait.update(need_tx)
    for sec, ms, src in got:
        if sec in ft:
            done.add(sec)
            continue
        s = g.spot.get(sec) or {}
        seal, bids = _seal_metrics(sec)
        vol = _snap_vol(s)
        amt = _l2_big_turnover(sec)
        ft[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': now,
                   'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False,
                   'src': src, 'day': str(get_trading_day())}   # v1.3 首触交易日戳（重启重建同口径）
        done.add(sec)
        log.info('[restart-rebuild] %s 恢复首触 ms=%s seal=%.0f bids=%d src=%s' % (_sn(sec), ms, seal, bids, src))
    if wait:
        for sec in wait:
            retry[sec] = now   # 数据未就绪/回看失败：30s 后重试，不每帧拉 API
    if done:
        pending[:] = [x for x in pending if x not in done]
    _restart_rebuild_heartbeat(now, done=len(done), wait=len(wait))


def _restart_rebuild_heartbeat(now, done=0, wait=0):
    # v0.76 进度 heartbeat：60s 节流，队列仍存在时打印 pending/done/wait，便于现场核对。
    hb = float(getattr(g, 'restart_rebuild_hb_ts', 0.0) or 0.0)
    if now - hb < float(BLS.get('first_zt_rebuild_heartbeat_sec', 60.0)):
        return
    g.restart_rebuild_hb_ts = now
    pending = getattr(g, 'first_zt_rebuild_pending', None) or []
    _left = ','.join([_sn(x) for x in pending[:6]]) if pending else '-'
    log.info('[restart-rebuild] pending=%d done=%d wait=%d left=%s' % (len(pending), done, wait, _left))


def _restart_rebuild_later_log(sec):
    # v1.35 重建放弃后当日又被 tick 正常补建：证明放弃不是终态，避免误判为回看失败
    try:
        _gu = getattr(g, 'first_zt_rebuild_gave_up', None)
        if not isinstance(_gu, set):
            return
        if sec not in _gu:
            return
        _gu.discard(sec)
        log.info('[restart-rebuild] %s rebuilt_later 放弃后由 tick 正常补建首触' % _sn(sec))
    except Exception:
        pass


def _log_l2_big_seed_summary(sec):
    # v0.73 播种后补打 [l2-big-seed] 摘要：新入池票首帧有历史累计可核对，避免“无数据”被当成“无大单”。
    try:
        a = (getattr(g, 'l2_big', {}) or {}).get(sec) or {}
        if not a.get('amt'):
            return
        r = _l2_big_ratio(sec)
        _to = _l2_big_turnover(sec)
        log.info('[l2-big-seed] %s 播种后 大单买=%.0f(%d笔) 卖=%.0f(%d笔) 净=%.0f 占比=%.2f%% 分母=%.0f' % (
            _sn(sec), a.get('buy', 0.0), a.get('bn', 0), a.get('sell', 0.0), a.get('sn', 0),
            a.get('buy', 0.0) - a.get('sell', 0.0), r * 100.0 if r >= 0 else -1.0, _to))
    except Exception:
        pass


def _l2_big_seed_onjoin(secs):
    # v0.67 盘中新入池触板票补播种；v0.73 改逐票节流：每票当日首见即种（不被全局 60s 节流阻塞），
    # 空结果不写 seeded 下帧重试；单帧上限防拖帧；水印与既有路径共用，双源不重复。
    if not BLS.get('l2_big_seed_onjoin_enabled', True):
        return
    secs = [s for s in (secs or []) if s]
    if not secs:
        return
    seeded = getattr(g, 'l2_big_seeded', None)
    if seeded is None:
        seeded = set(); g.l2_big_seeded = seeded
    todo = [s for s in secs if s not in seeded]
    if not todo:
        return
    now = time.time()
    px_ts = getattr(g, 'l2_big_seed_onjoin_px', None)
    if px_ts is None:
        px_ts = {}; g.l2_big_seed_onjoin_px = px_ts
    gap_px = float(BLS.get('l2_big_seed_onjoin_px_sec', 0))
    max_frame = int(BLS.get('l2_big_seed_onjoin_max_per_frame', 5))
    pages = int(BLS.get('l2_tickdir_pages_onjoin', 5))
    done = 0
    for s in todo:
        if done >= max_frame:
            break
        if now - float(px_ts.get(s, 0.0) or 0.0) < gap_px:
            continue
        px_ts[s] = now
        try:
            _l2_big_seed([s], pages=pages)
            done += 1
            if BLS.get('l2_big_seed_log', True):
                _log_l2_big_seed_summary(s)
        except Exception as e:
            _warn('l2_big_seed_onjoin %s fail %r' % (_sn(s), e))


def _l2_big_turnover(sec):
    # v0.66 L2 大单占比分母（当日成交额，元）：云端快照 business_balance=总成交额 优先；
    # 缺失回退 business_amount(总成交量股)x均价，再回退 turnover/amount（旧环境/本地测试兼容）
    try:
        s = g.spot.get(sec) or {}
        to = float(s.get('business_balance') or 0.0)
        if to > 0:
            return to
        vol = float(s.get('business_amount') or 0.0)
        px = float(s.get('wavg_px') or s.get('last_px') or 0.0)
        if vol > 0 and px > 0:
            return vol * px
        to = float(s.get('turnover') or s.get('amount') or 0.0)
        return to if to > 0 else 0.0
    except Exception:
        return 0.0


def _l2_big_day_summary(limit=30):
    # v0.66 买入/卖出大单日结：按票汇总 买额/卖额/净额/笔数（净额降序，前 limit 只），供 after_trading_end 输出核对
    try:
        acc = getattr(g, 'l2_big', None) or {}
        out = []
        for sec, a in acc.items():
            if not isinstance(a, dict) or not a.get('amt'):
                continue
            buy = float(a.get('buy') or 0.0)
            sell = float(a.get('sell') or 0.0)
            out.append((sec, buy, sell, buy - sell,
                        int(a.get('bn') or 0), int(a.get('sn') or 0), int(a.get('un_n') or 0)))
        out.sort(key=lambda x: x[3], reverse=True)
        return out[:int(limit)]
    except Exception:
        return []


def _l2_big_ratio(sec):
    # v0.66 L2 大单净量占比 = (大单买-大单卖)/当日成交额（_l2_big_turnover 元）；净<=0/无数据/单位异常 -> -1
    try:
        acc = (getattr(g, 'l2_big', None) or {}).get(sec)
        if not acc:
            return -1.0
        if BLS.get('l2_big_dir_enabled', True):
            num = float(acc.get('buy') or 0.0) - float(acc.get('sell') or 0.0)
            if num <= 0:
                return -1.0
        else:
            num = float(acc.get('amt') or 0.0)
            if num <= 0:
                return -1.0
        to = _l2_big_turnover(sec)
        if to <= 0:
            return -1.0
        r = num / to
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


def _tx_frame_zt_ms(sec, frame_data):
    # 帧内推送逐笔（tick_data 的 data[sec]['transaction']，0 额外 API 调用）：最早一笔涨停价成交
    # 若成交价>=涨停价返回其 business_time(毫秒)，否则 None；无 L2 字段/异常 -> None（由拉取兜底）
    # v0.74 多行 DataFrame/Series 扫描最早一笔（原取 iloc[-1] 会把首笔延后到帧末）
    try:
        t = (frame_data or {}).get(sec) or {}
        tx = t.get('transaction') if isinstance(t, dict) else None
        if tx is None:
            return None
        u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
        if not u or u <= 0:
            return None
        best = None
        if hasattr(tx, 'iloc'):            # DataFrame/Series/沙盒 iloc 形态：遍历取最早
            iloc = tx.iloc
            if isinstance(iloc, (list, tuple)):
                rows_iter = [(0, r) for r in iloc]
            elif hasattr(tx, 'iterrows'):
                rows_iter = tx.iterrows()
            else:
                rows_iter = [(0, tx)]
            for _, row in rows_iter:
                try:
                    ms = row.get('business_time'); px = float(row.get('hq_px'))
                except Exception:
                    continue
                if not ms:
                    continue
                ms = int(ms)
                if px >= u - 1e-9 and (best is None or ms < best):
                    best = ms
        elif isinstance(tx, dict):
            try:
                ms = int(tx.get('business_time')); px = float(tx.get('hq_px'))
            except Exception:
                return None
            if ms and px >= u - 1e-9:
                return ms
        return best
    except Exception:
        return None


def _break_held_ts(ft, now=None):
    # v1.22 反复炸板 held 基准：优先最近一次破板时间 last_break_ts，首破 break_ts 仅兜底
    try:
        now = now or time.time()
        ft = ft or {}
        return float(ft.get('last_break_ts') or ft.get('break_ts') or now)
    except Exception:
        return now


def _firstzt_rebreak_log(sec):
    # v1.22 反复炸板/回封日志节流：同票 firstzt_rebreak_log_sec 内只打一次，不抑制状态翻转
    try:
        gl = getattr(g, 'firstzt_log_ts', None)
        if not isinstance(gl, dict):
            gl = {}; g.firstzt_log_ts = gl
        now = time.time()
        sec_sec = float(BLS.get('firstzt_rebreak_log_sec', 30.0) or 30.0)
        if now - float(gl.get(sec) or 0.0) < sec_sec:
            return False
        gl[sec] = now
        return True
    except Exception:
        return True


def tick_data(context, data):
    # 仅交易，9:30-14:59 每 3s 一次。L2 涨停首笔成交感知 + 封单/破板节奏。
    # 只采集状态与 [firstzt] 日志，下单仍走 1m handle_data（采集/决策解耦）。
    try:
        _set_now(context)   # v1.29 尾盘竞价段判定需要当前交易时间
    except Exception:
        pass
    try:
        g.gear_invalid_cnt = 0
        g.gear_total_cnt = 0
    except Exception:
        pass
    if not BLS.get('tick_enabled', True):
        return
    _secs = _tick_targets()
    _dh = _get_ds()
    try:
        _dh.snapshot(_secs)                     # 帧首批量快照（一次 get_snapshot(列表)）
    except Exception:
        pass
    try:
        _rebuild_first_zt_tick()                # v0.76 重启重建缺失 first_zt（在 _near 判定前，防重复首触）
    except Exception as _e:
        _warn('restart-rebuild fail: %r' % _e)
    # v0.22 近涨停候选批量逐笔（统一入口）：先帧推送，缺者一次 get_individual_transaction(列表)
    _tx_map = {}
    buy_events = []   # v1.34 同帧事件收集（firstzt/reboard/near，帧末统一派发）
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
                _l2_big_seed_onjoin(_tick_seed_cands(_near))   # v0.67/v0.74 盘中新入池触板票补播种（含 near_scan 未触板票）
            except Exception:
                pass
            try:
                # v1.34 帧内预算优先：高分/最早首触票先拉逐笔（同帧事件排序口径一致）
                _near.sort(key=lambda s: _pool_exp_priority(s))
            except Exception:
                pass
            try:
                _tx_map = _dh.tx_zt_batch(_near, data)
            except Exception:
                _tx_map = {}
            # v1.34 near 事件：新入近涨停池票同帧派发 sweep A/弹性（防帧末全量排队错过窗口）
            _nev = getattr(g, 'tick_near_evt', None)
            if not isinstance(_nev, dict):
                _nev = {}; g.tick_near_evt = _nev
            for _sec in _near:
                if _sec not in _nev:
                    _nev[_sec] = time.time()
                    buy_events.append({'kind': 'near', 'sec': _sec})
    for sec in _secs:
        try:
            s = g.spot.get(sec) or {}
            g.spot[sec] = s                     # 顺带刷新 1m 打分用的快照
            last = float(s.get('last_px') or 0.0)
            u = float(s.get('up_px') or 0.0)
            if last <= 0 or u <= 0:
                continue
            seal, bids = _seal_metrics(sec)
            _book_ok = _seal_book_ok(sec)
            try:
                g.gear_total_cnt = int(getattr(g, 'gear_total_cnt', 0) or 0) + 1
                if not _book_ok:
                    g.gear_invalid_cnt = int(getattr(g, 'gear_invalid_cnt', 0) or 0) + 1
            except Exception:
                pass
            ft = g.first_zt.get(sec)
            if ft is None:
                vol = _snap_vol(s)
                amt = _l2_big_turnover(sec)
                ms = s.get('hsTimeStamp') or 0   # 快照毫秒时间戳，精确还原触板时刻
                # v0.20/v0.22 L2 逐笔首笔成交感知（优先，灵敏度<=3s）：涨停价逐笔成交即确认首触；
                # _tx_map 已按近涨停候选批量取好（帧推送优先 + 批量拉取兜底），此处直接读
                tx_ms = _tx_map.get(sec) if BLS.get('firsttx_enabled', True) else None
                if tx_ms is not None:
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': tx_ms, 'break': False, 'seal_low': False,
                                       'src': 'tx', 'day': str(get_trading_day())}   # v1.3 首触交易日戳
                    log.info('[firstzt] %s price=%.2f tx_ms=%s vol=%.0f seal=%.0f bids=%d state=first(src=tx)' % (_sn(sec), last, tx_ms, vol, seal, bids))
                    _restart_rebuild_later_log(sec)   # v1.35 重建放弃后补建审计
                    if BLS.get('l2_big_seed_on_firstzt', True) and sec not in (getattr(g, 'l2_big_seeded', None) or set()):
                        try:
                            _l2_big_seed([sec])
                            if BLS.get('l2_big_seed_log', True):
                                _log_l2_big_seed_summary(sec)
                        except Exception as _e:
                            _warn('l2_big_seed firstzt %r' % _e)
                    buy_events.append({'kind': 'firstzt', 'sec': sec})
                    _tx_lag_warn(sec, g.first_zt[sec])
                    continue
                if (last >= u - 1e-9 and seal >= float(BLS.get('firstzt_min_seal', 0.0))
                        and bids >= int(BLS.get('firstzt_min_bids', 0))):   # 快照兜底：首此涨停上报最小封单/挂单门槛,过滤假封            # 首次触板
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False,
                                       'src': 'snap', 'day': str(get_trading_day())}   # v1.3 首触交易日戳
                    log.info('[firstzt] %s price=%.2f vol=%.0f ms=%s seal=%.0f bids=%d state=first(src=snap)' % (_sn(sec), last, vol, ms, seal, bids))
                    _restart_rebuild_later_log(sec)   # v1.35 重建放弃后补建审计
                    if BLS.get('l2_big_seed_on_firstzt', True) and sec not in (getattr(g, 'l2_big_seeded', None) or set()):
                        try:
                            _l2_big_seed([sec])
                            if BLS.get('l2_big_seed_log', True):
                                _log_l2_big_seed_summary(sec)
                        except Exception as _e:
                            _warn('l2_big_seed firstzt %r' % _e)
                    # v0.18 首板确认->打板：开盘10分钟内+非一字板+板块内涨幅最高+主动最快拉升+强度前三
                    buy_events.append({'kind': 'firstzt', 'sec': sec})
                    _tx_lag_warn(sec, g.first_zt[sec])
                continue
            if last < u - 1e-9:                 # 破板
                if not ft.get('break'):
                    ft['break'] = True; ft['break_ts'] = time.time()
                    ft['last_break_ts'] = time.time()   # v1.22 反复炸板：最近破板时间戳每次翻转更新
                    ft['break_cnt'] = int(ft.get('break_cnt') or 0) + 1
                    if _firstzt_rebreak_log(sec):
                        log.info('[firstzt] %s price=%.2f -> BREAK#%d seal=%.0f held=%.0fs' % (_sn(sec), last, int(ft.get('break_cnt') or 0), seal, time.time() - ft.get('ts', time.time())))
                continue
            if ft.get('break') and last >= u - 1e-9 and seal >= float(BLS.get('firstzt_min_seal', 0.0)):
                ft['break'] = False
                ft['last_reboard_ts'] = time.time()   # v1.22 最近回封时间戳每次翻转更新
                if not ft.get('reboard_ts'):
                    ft['reboard_ts'] = time.time()
                buy_events.append({'kind': 'reboard', 'sec': sec})   # v1.34 回封同帧派发
                if _firstzt_rebreak_log(sec):
                    log.info('[firstzt] %s 回封 reboard_ts=%.0f break_cnt=%d seal=%.0f' % (_sn(sec), float(ft.get('reboard_ts') or 0), int(ft.get('break_cnt') or 0), seal))
            fs = ft.get('first_seal') or 0.0
            _sfr = float(BLS.get('seal_fail_ratio', 0.333))
            if _unique_stand(sec):   # v0.49 唯一身位连板更容忍（后排助攻/人气龙头）
                _sfr = float(BLS.get('seal_fail_ratio_unique', 0.25))    # 封单衰竭（相对首封）
            _update_seal_low_state(ft, sec, last, u, seal, bids, _book_ok, fs, _sfr,
                                   float(BLS.get('seal_low_fast_ratio', 0.15) or 0.0))
            try:
                _board_queue_cancel(sec, seal, bids)   # v1.6 打板未成交排单：封单衰减撤单
            except Exception as _e:
                _warn('board queue cancel scan fail %r' % _e)
        except Exception:
            continue
    # v1.34 同帧事件统一派发（firstzt/reboard/near；按优先级排序，6s 首帧窗内立即评估）
    try:
        _run_tick_buy_events(context, buy_events)
    except Exception as e:
        _warn('tick buy events fail: %r' % e)
    # v0.26 tick 级卖出：3s 帧末（炸板/封单大减/急卖；first_zt 状态已在本帧采集）
    try:
        _unhealthy, _tot, _inv, _ratio = _gear_batch_health()
        g.seal_batch_unhealthy = _unhealthy
        if _unhealthy:
            log.info('[gear-na] 本帧 L2 十档缺失 %d/%d 占比=%.0f%% -> 整批不健康，跳过 SEAL_LOW 卖出' % (_inv, _tot, _ratio * 100.0))
            _reset_seal_low_confirm_on_batch_bad()
    except Exception as _e:
        _warn('gear batch health fail: %r' % _e)
    try:
        _t1_protect_consume(context)   # v1.30 T+1 次日复核（3s 帧）
    except Exception as e:
        _warn('t1 protect consume fail: %r' % e)
    try:
        tick_sell_manager(context)
    except Exception as e:
        _warn('tick sell fail: %r' % e)
    # v0.49 回封打板：3s 帧末评估（前排首板/2板 10:00前炸板回封 + 大单占比>=10%）
    try:
        _try_reboard_buy(context)
    except Exception as e:
        _warn('reboard buy fail: %r' % e)

    # v0.13：3s 帧末统一评估预期买入（竞价超预期/快速上攻/封单超预期 -> 立买；走弱 -> 放弃）
    if BLS.get('tick_exp_enabled', True):
        try:
            _try_expected_buys(context)
        except Exception as e:
            _warn('tick exp buy fail: %r' % e)
    # v0.19 弹性套利：3s 帧末评估（09:30-09:50，板块一字>=2 抓 20cm/北交）
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
    # v1.26 A 新题材首板扫板（独立于动态唯一，窗口 09:30-09:40）
    try:
        _try_new_theme_sweep(context)
    except Exception as e:
        _warn('new_theme_sweep fail: %r' % e)
    # v1.36 午后新题材前排试点（13:00-13:30，打板名额耗尽切 10% 弹性）
    try:
        _try_pm_theme_buy(context)
    except Exception as e:
        _warn('pm_theme buy fail: %r' % e)
    # v0.81 帧末拉取预算统计（节流：常规 60s 心跳 + over/degraded 事件行，见 _budget_log）
    _budget_log()


def auction_pre_confirm(context):
    # 09:25 竞价终态：重读 9:20 定时上传的预期前瞻文件，对 side=buy 做「竞价超预期初步确认 -> 观察」节奏。
    # 时机说明：before_trading_start(~9:10) 早于上传点，须在此重读当日文件才命中；观察不买，等分时(9:30+)确认。
    _set_now(context)
    _cache_cash_baseline(context)   # v1.13 09:25 缓存开盘资金基线（防开盘首帧 cash=0）
    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) != day:
        g.exp_day = day
    _load_expectation(merge=True)  # 幂等重读：命中 9:15 前上传的当日文件（C 合并防收缩）
    _load_zt_lianban(merge=True)   # v0.79 P1 防收缩：命中 9:20 上传（新文件胜出 + 旧有保留 + 日期/收缩守卫）
    _load_boards()               # v0.36d 板块映射文件 09:25 重读（命中 9:20 上传）
    _synth_pool_expect(src='original_0925')   # v0.27：涨停池竞价三态初步确认（超预期->观察）
    _dyn_unq_auction_eval()      # v0.38 竞价唯一预判（同身位竞品不及预期 -> 扫板前提，0 盘中 RPC）
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect(src='original_0925')   # v0.35e：自选股竞价三态（超预期->观察）
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))  # v0.36 覆盖兜底
    _sync_pool_static()
    _mark_one_word_open()
    try:
        _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))   # v0.52 竞价终态已成交大单播种
    except Exception:
        pass
    _hist1d_prewarm('09:25')   # v1.16 核心/预期票日线预暖
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
    try:
        _fill_zt_spot()   # v1.4 B：09:25 竞价情绪全池缺 spot 批量补快照，防 ready=26/41 类就绪率不足
        _lb_senti_auction()   # v0.65 竞价终态：中高位高开/绿开/一字率 + 低位高开率
        _lb_senti_mid()
        try:
            _senti_hist_touch('auction')   # v1.31 竞价终态情绪温度落档
        except Exception as e:
            _warn('senti_hist auction touch fail: %r' % e)
    except Exception as e:
        _warn('lb_senti auction eval fail: %r' % e)
    log.info('auction_pre_confirm 09:25 done exp_file=%d' % len(g.exp_file))


def _after_open_state_sync():
    # v1.13 09:31 不再无条件清空当日 first_zt/L2/情绪（上海港湾 09:30:22 firstzt 被 09:31 清空根因）。
    # 当日已有状态保留，缺失项由后续 _mark_one_word_open/_l2_big_seed/盘中采集补齐；跨日才全量重置。
    today = str(get_trading_day())
    if getattr(g, 'exp_day', None) == today:
        log.info('[aop-keep] 保留当日状态 first_zt=%d l2_big=%d lb_senti=%d' % (
            len(g.first_zt or {}), len(g.l2_big or {}), len(g.lb_senti or {})))
        return 'keep'
    g.exp_day = today
    g.hist_prio_cache = {}; g.hist_na_pending = {}
    g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.break2_sold = set(); g.board_cancel_log = set(); g.reboard_fired = False; g.sealed_since = {}; g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}; g.zt_ferment_stage = {}; g.zt_unmapped_n = 0; g.lb_senti = {}; g.lb_senti_cache = {}
    g.hist_recover_once = {}; g.firstzt_log_ts = {}; g.bought_qty = {}   # v1.22 aop 重置同步清恢复日志去重/炸板日志节流/买入成交累计
    log.info('[aop-reset] 首日/跨日重置盘中状态 first_zt=0 l2_big=0')
    return 'reset'


def lb_senti_auction_retry(context):
    # v1.16 09:26 竞价情绪补拉：09:25 未就绪票再补一轮，09:31 仅异常兜底
    try:
        if not BLS.get('lb_senti_auction_retry_enabled', True):
            return
        _set_now(context)
        st = _lb_senti_state()
        a = st.get('auction') or {}
        if a.get('ready'):
            return
        _got, _missing = _fill_zt_spot()
        if _got:
            out = _lb_senti_auction() or {}
            try:
                _senti_hist_touch('auction')   # v1.31 09:26 补拉后重写当日情绪温度记录
            except Exception as e:
                _warn('senti_hist auction retry touch fail: %r' % e)
            _rd = out.get('ready_detail') or {}
            _mn = int(out.get('mid_n') or 0); _ln = int(out.get('low_n') or 0)
            _mr = int(_rd.get('mid') or 0); _lr = int(_rd.get('low') or 0)
            _pct = 100.0 * (_mr + _lr) / (_mn + _ln) if (_mn + _ln) else 100.0
            log.info('[lb-senti] auction retry 09:26 got=%d ready=%s ready_pct=%.0f%% missing=%s'
                     % (_got, bool(out.get('ready')), _pct, ','.join(_missing[:10])))
        else:
            log.info('[lb-senti] auction retry 09:26 got=0 ready=%s missing=%d'
                     % (a.get('ready'), len(_missing or [])))
        # v1.24 竞价跌停快照缺失补拉（09:25 run_daily 预算/数据异常时兜底，幂等）
        st2 = _lb_senti_state()
        if not (st2.get('ld') or {}).get('auction'):
            _ld_senti_snapshot('auction')
    except Exception as e:
        _warn('lb_senti auction retry fail: %r' % e)


def _ld_senti_snapshot(stage='auction'):
    # v1.24 跌停题材因子阶段快照：强制刷新全市场统计并落 st['ld']（竞价 09:25 -> 开盘 09:30 -> 10:00）。
    # 数据缺失只打日志不写档，消费端以最新可用档位为准，绝不把“无数据”当“无跌停”。
    if not BLS.get('ld_senti_enabled', True):
        return None
    try:
        st = _lb_senti_state()
        d = _market_ld_senti(force_fetch=True)
        if not d:
            log.info('[ld-senti] %s 跌停快照无数据 -> 不写档' % stage)
            return None
        rec = {
            'ts': time.time(),
            'n': int(d.get('ld_n') or 0),
            'zt_ld_n': int(d.get('zt_ld_n') or 0),
            'theme': dict(d.get('theme_ld') or {}),
            'concept': dict(d.get('concept_ld') or {}),
            'zt_ld_codes': list(d.get('zt_ld_codes') or [])[:30],
        }
        st.setdefault('ld', {})[stage] = rec
        st['ld']['last'] = stage
        st['ld']['ts'] = rec['ts']
        _top = sorted(rec['theme'].items(), key=lambda kv: -kv[1])[:5]
        log.info('[ld-senti] stage=%s 跌停=%d 昨日涨停池跌停=%d 题材=%s'
                 % (stage, rec['n'], rec['zt_ld_n'],
                    ','.join('%s:%d' % (k, v) for k, v in _top) or '-'))
        return rec
    except Exception as e:
        _warn('ld-senti snapshot fail: %r' % e)
        return None


def ld_senti_auction(context):
    _set_now(context)
    _ld_senti_snapshot('auction')


def ld_senti_open(context):
    _set_now(context)
    _ld_senti_snapshot('open')


def after_open_probe(context):
    _set_now(context)
    log.info('after_open_probe 09:31')
    # 兜底重读：9:15 前上传若稍晚到，09:31 再读一次（幂等，C 合并防收缩）
    _load_expectation(merge=True)
    _synth_pool_expect(src='restart_rebuild')   # v0.27：涨停池三态（09:31 兜底重合成，覆盖重读清空）
    _dyn_unq_auction_eval()      # v0.38 竞价唯一预判（09:31 兜底重算）
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect(src='restart_rebuild')   # v0.35e：自选股三态（09:31 兜底重合成）
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))  # v0.36 覆盖兜底
    _sync_pool_static()
    _after_open_state_sync()   # v1.13 当日保留 first_zt/L2/情绪，仅跨日重置
    _mark_one_word_open()
    try:
        _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))   # v0.52 09:31 兜底重播种（覆盖重置窗口）
    except Exception:
        pass
    _hist1d_prewarm('09:31')   # v1.16 09:31 核心日线补暖
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
    try:
        _lb_senti_auction()   # v0.65 09:31 兜底重算竞价终态（重置后补齐）
        _lb_senti_mid()
        try:
            _senti_hist_touch('auction')   # v1.31 09:31 兜底重写（防 09:25 未就绪）
        except Exception as e:
            _warn('senti_hist auction 09:31 touch fail: %r' % e)
    except Exception as e:
        _warn('lb_senti after_open eval fail: %r' % e)


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


def _sell2_price(sec):
    # v1.12 追高/预期买入成交率优化：L2 卖2价（缺失/异常返回 0，调用方回退）
    try:
        gp = _gear(sec)
        lv = int(BLS.get('buy_limit_sell2_level', 2) or 2)
        a = (gp.get('ask_grp') or {}).get(lv) or []
        if isinstance(a, (list, tuple)) and len(a) >= 1 and float(a[0] or 0) > 0:
            return float(a[0])
    except Exception:
        pass
    return 0.0


def _log_order_limit(sec, limit):
    # v1.12 下单限价来源核对（成交率优化审计，买路径发单前打一次）
    try:
        if not BLS.get('order_limit_log', True):
            return
        s2 = _sell2_price(sec)
        up = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
        log.info('[order-limit] %s src=%s limit=%s up=%s sell2=%s' % (
            _sn(sec), getattr(g, 'order_limit_src', 'px'),
            ('%.2f' % limit) if limit else '-',
            ('%.2f' % up) if up else '-',
            ('%.2f' % s2) if s2 else '-'))
    except Exception:
        pass


def _order_limit(sec, side, mode):
    # 下单限价策略：板(涨停价) / 追高+sweep(卖2或现价上浮后封顶涨停价) / 回踩(现价) / 卖出(现价限价防急跌垃圾价)
    s = g.spot.get(sec) or {}
    px = last_px(sec)
    up = float(s.get('up_px') or 0.0) if s else 0.0
    if not px or px <= 0:
        return None
    if side == 'sell':
        g.order_limit_src = 'sell'
        if mode == 'sell_urgent' and BLS.get('sell_urgent_floor', 1):
            # v1.15 urgent 卖出贴近现价：现价-1档（下限现价*0.98），跌停地板价仅接近跌停/无现价时降级
            floor = _limit_down_price(sec)
            _near = _round_price(px - 0.01)
            _low = _round_price(px * (1.0 - float(BLS.get('urgent_sell_max_discount', 0.02) or 0.02)))
            if _near < _low:
                _near = _low
            if floor and floor > 0 and px <= floor * (1.0 + float(BLS.get('urgent_sell_floor_near', 0.01) or 0.01)):
                g.order_limit_src = 'sell_floor'
                return _round_price(floor)
            g.order_limit_src = 'sell_near'
            return _near
        if mode == 'sell_break':   # v0.49 炸板卖出：L2 买N档限价（默认买3），缺失回退现价；0.95 下限防过度杀价
            try:
                gp = _gear(sec)
                _lv = int(BLS.get('break_sell_bid_level', 3))
                b = (gp.get('bid_grp') or {}).get(_lv) or []
                if isinstance(b, (list, tuple)) and len(b) >= 1 and float(b[0] or 0) > 0:
                    bid = float(b[0])
                    floor = px * float(BLS.get('break_sell_floor_ratio', 0.95))
                    if bid < floor:
                        bid = floor
                    return _round_price(bid)
            except Exception:
                pass
            return _round_price(px)
        return _round_price(px)
    if mode == 'board':
        if _sealed_at_limit(sec):
            g.order_limit_src = 'board_sealed'
            return None                                   # 一字/封死涨停：挂单只能排队，不参考排单 -> 不买
        g.order_limit_src = 'board'
        return _round_price(up if up and up > 0 else px)   # 打板：挂涨停价排队
    if mode == 'pullback':
        g.order_limit_src = 'px'
        return _round_price(px)                             # 回踩：现价限价
    p = px * (1 + float(BLS.get('buy_chase_pct', 0.008)))   # 追高：现价上浮后封顶涨停价
    g.order_limit_src = 'pct'
    if BLS.get('buy_limit_use_sell2', True):
        s2 = _sell2_price(sec)
        if s2 > 0 and s2 >= px - 1e-9:
            p = s2
            g.order_limit_src = 'sell2'                     # v1.12 卖2价提升成交率（仅 chase/expected）
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


def _sim_mode():
    # v0.80 纯模拟模式：DO_ORDER=False 且 EXPECT_ORDER=False 且 sim_cash_base>0（SIM 虚拟资金基准生效）
    try:
        if BLS.get('DO_ORDER', False) or BLS.get('EXPECT_ORDER', False):
            return False
        return float(BLS.get('sim_cash_base', 0.0) or 0.0) > 0
    except Exception:
        return False


def _size_cash(context):
    # v0.80 下单资金基准：SIM 模式用 sim_cash_base（信号可观察，不发真单）；真实路径始用真实现金
    if _sim_mode():
        return float(BLS.get('sim_cash_base', 0.0) or 0.0)
    return _avail_cash(context)


def _size_total(context):
    # v0.80 下单总资产基准：SIM 模式用 sim_cash_base；真实路径用真实总资产
    if _sim_mode():
        return float(BLS.get('sim_cash_base', 0.0) or 0.0)
    return _total_asset(context)


def _calc_buy_qty(context, sec, price, ratio):
    # 买入量(整手)：期望金额=min(总资产×比例, 单支上限, 现金)；单支上限=总资产×single_stock_cap-已持市值
    # v1.17 口径修正：与 AXquant _calc_buy_volume 对齐（此前误用现金×比例，持仓时低于总资产预算）
    if price is None or price <= 0:
        return 0
    try:
        cash = _size_cash(context)   # v0.64 资金实时最新（减在途买单承诺）; v0.80 SIM 虚拟资金基准
    except Exception:
        return 0
    if cash <= 0:
        return 0
    total = _size_total(context) or cash
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
        budget = min(total * float(ratio), cap, cash)
    except Exception:
        return 0
    if budget <= 0:
        return 0
    lot_step = int(BLS.get('buy_lot_step', 100) or 100)
    lot = price * lot_step
    if lot <= 0:
        return 0
    qty = int(budget / lot) * lot_step
    try:
        g.qty_calc_last = {'sec': sec, 'price': price, 'cash': cash, 'total': total,
                           'held_mv': held_mv, 'cap': cap, 'budget': budget,
                           'ratio': ratio, 'lot': lot, 'qty': qty}
    except Exception:
        pass
    return qty


def _qty_calc_log(context, sec, tag='order'):
    # v1.18 发单前 [qty-calc] 审计（cash/total/held_mv/cap/budget/lot/qty），按票+tag 节流防刷屏
    try:
        d = getattr(g, 'qty_calc_last', None)
        if not isinstance(d, dict) or d.get('sec') != sec:
            return
        _skip_log('qty_calc', sec, tag,
                  '[qty-calc] %s %s cash=%.2f total=%.2f held_mv=%.2f cap=%.2f budget=%.2f lot=%.2f qty=%d' % (
                      tag, _sn(sec), float(d.get('cash') or 0), float(d.get('total') or 0),
                      float(d.get('held_mv') or 0), float(d.get('cap') or 0),
                      float(d.get('budget') or 0), float(d.get('lot') or 0), int(d.get('qty') or 0)),
                  throttle_sec=30.0)
    except Exception:
        pass


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


def _o_get(obj, *keys, default=None):
    # 兼容对象属性/字典键取值（PTrade 委托/成交主推为 dict，Order/Trade 对象为属性）
    for k in keys:
        try:
            if isinstance(obj, dict):
                if k in obj:
                    return obj[k]
            else:
                v = getattr(obj, k, None)
                if v is not None:
                    return v
        except Exception:
            continue
    return default


def _map_order_status(st):
    # PTrade 委托状态码映射（docs/07: '0'未报 '1'待报 '2'已报 '3'已报待撤 '4'部成待撤 '5'已撤 '6'废单 '7'部成 '8'已成 '9'部撤 'V'已确认）
    s = str(st or '').strip().upper()
    if s in ('FILLED', '8', 'V'):
        return 'FILLED'
    if s in ('CANCELLED', 'CANCELED', '5', '9'):
        return 'CANCELLED'
    if s in ('REJECTED', '6'):
        return 'REJECTED'
    if s in ('PARTIAL', '7', '4'):
        return 'PARTIAL'
    return 'SENT'


def _trade_side(bs):
    # 委托方向：PTrade entrust_bs '1'=买 '2'=卖（兼容 S/B 语义）
    s = str(bs or '').strip().upper()
    if s in ('2', 'S', 'SELL', 'SALE'):
        return 'sell'
    if s in ('1', 'B', 'BUY'):
        return 'buy'
    return ''


def _order_matches_symbol(o, sec, side=None, qty=None):
    # v1.15 按 symbol 匹配委托（零回报 UUID 单找回数字委托号的辅助判断）
    try:
        _sym = str(_o_get(o, 'symbol') or _o_get(o, 'stock_code') or '')
        if not _sym:
            return False
        if _norm_sec(_sym) != _norm_sec(sec):
            return False
        _bs = _trade_side(str(_o_get(o, 'side', 'entrust_bs') or ''))
        if side and _bs and _bs != side:
            return False
        if qty:
            _amt = int(float(_o_get(o, 'amount') or 0) or 0)
            if _amt and abs(_amt) != int(qty):
                return False
        return True
    except Exception:
        return False


def _backfill_entrust(sec, o, st):
    # v1.15 把云端数字 entrust_no 回填 pending.no，后续撤单/查询才能命中
    try:
        _ent = str(_o_get(o, 'entrust_no') or '')
        if not _ent:
            return st or ''
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        old = str(pp.get('no') or '')
        if old != _ent:
            pp['no'] = _ent
            log.info('[entrust-backfill] %s 按symbol回填委托号 old=%s -> %s status=%s' % (
                _sn(sec), old or '-', _ent, st or '?'))
        return st or ''
    except Exception:
        return st or ''


def _query_open_order_status(ent, sec=None, side=None, qty=None, backfill=False):
    # v1.13 委托兜底查询：get_open_orders() 在途 -> SENT；get_all_orders() 终态回填；
    # 查询失败返回 None（保守等待），查询成功无匹配返回 ''（确认不在在途）。
    # v1.15 零回报 UUID 单按 symbol 找回数字委托号（backfill=True 时回填 pending.no）。
    ent = str(ent or '')
    if not ent:
        return None
    try:
        for o in (get_open_orders() or []):
            if str(_o_get(o, 'entrust_no') or '') == ent:
                return 'SENT'
        if backfill and sec:
            for o in (get_open_orders() or []):
                if _order_matches_symbol(o, sec, side, qty):
                    return _backfill_entrust(sec, o, 'SENT')
    except Exception:
        return None
    try:
        for o in (get_all_orders() or []):
            if str(_o_get(o, 'entrust_no') or '') == ent:
                return _map_order_status(_o_get(o, 'order_status', 'status'))
        if backfill and sec:
            for o in reversed(list(get_all_orders() or [])):
                if _order_matches_symbol(o, sec, side, qty):
                    return _backfill_entrust(sec, o, _map_order_status(_o_get(o, 'order_status', 'status')))
    except Exception:
        return None
    return ''


def _cache_cash_baseline(context):
    # v1.13 开盘资金未就绪基线：before_trading_start/09:25 缓存一次真实正现金，
    # 开盘首帧 portfolio.cash=0 时在窗口内用基线兜底，防 qty<=0 错失买点。
    try:
        c = float(getattr(context.portfolio, 'cash', 0) or 0)
        if c > 0:
            g.cash_baseline = c
            g.cash_baseline_ts = time.time()
    except Exception:
        pass


def _avail_cash(context):
    # v0.64 资金实时最新：portfolio.cash(6s 同步+主推更新) - 在途买单承诺(g.buy_commit)，
    # 防资金同步滞后窗口内超配；commit 由主推回报终态释放（FILLED/CANCELLED/REJECTED/PARTIAL 按成交额释放）。
    # v1.13 开盘首帧真实现金未刷新（2026-10-30 qty<=0 根因）：窗口内用 09:25 基线兜底，
    # 真实现金恢复后切换并滚动基线；切换打 [cash-src] 审计日志。
    try:
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
    except Exception:
        cash = 0.0
    now = time.time()
    _bl = float(getattr(g, 'cash_baseline', 0.0) or 0.0)
    _bl_ts = float(getattr(g, 'cash_baseline_ts', 0.0) or 0.0)
    _win = float(BLS.get('cash_baseline_window', 300.0) or 300.0)
    src = 'real'
    if cash <= 0 and _bl > 0 and now - _bl_ts <= _win:
        cash = _bl
        src = 'baseline'
    elif cash > 0:
        g.cash_baseline = cash
        g.cash_baseline_ts = now
        src = 'real'
    g.cash_src = src
    try:
        if src != str(getattr(g, 'cash_src_logged', 'real')):
            g.cash_src_logged = src
            log.info('[cash-src] src=%s cash=%.2f baseline=%.2f window=%.0fs age=%.1fs' % (
                src, cash, _bl, _win, (now - _bl_ts) if _bl_ts else 0.0))
    except Exception:
        pass
    try:
        cm = getattr(g, 'buy_commit', None)
        if isinstance(cm, dict) and cm:
            cash = max(0.0, cash - float(sum(cm.values()) or 0.0))
    except Exception:
        pass
    return cash


def _buy_commit_add(sec, qty, px):
    try:
        cm = getattr(g, 'buy_commit', None)
        if not isinstance(cm, dict):
            cm = {}; g.buy_commit = cm
        cm[sec] = float(cm.get(sec, 0.0) or 0.0) + max(0.0, float(qty or 0) * float(px or 0))
    except Exception:
        pass


def _buy_commit_rel(sec, qty, px):
    # 按成交/终态释放买入承诺（防资金双扣或占坑）
    try:
        cm = getattr(g, 'buy_commit', None)
        if not isinstance(cm, dict) or sec not in cm:
            return
        _rel = max(0.0, float(qty or 0) * float(px or 0))
        if _rel <= 0:
            cm.pop(sec, None); return
        cm[sec] = max(0.0, float(cm.get(sec, 0.0) or 0.0) - _rel)
        if cm[sec] <= 0:
            cm.pop(sec, None)
    except Exception:
        pass


def _release_buy_slot(sec):
    # v0.64 买单 REJECTED/CANCELLED：释放当日买入名额（防占坑）；buy_log 冷却保留防信号风暴
    # v1.21 全量/打板/各策略分类列表同步释放（打板未成交不算占用）
    try:
        _db = getattr(g, 'daily', None)
        if isinstance(_db, dict):
            for _k in _BUY_SLOT_LIST_KEYS:
                _lst = _db.get(_k)
                if isinstance(_lst, list) and sec in _lst:
                    _lst.remove(sec)
            _kd = _db.get('bought_kind')
            if isinstance(_kd, dict):
                _kd.pop(sec, None)
        if isinstance(getattr(g, 'exp_fired', None), set):
            g.exp_fired.discard(sec)
        log.info('[buy-slot] %s 释放当日买入名额(REJECTED/CANCELLED)' % _sn(sec))
        _save_state()
    except Exception:
        pass


def _reconcile_buy_slot_lists(_db, _keep):
    # v1.21 重启对账同步分类列表：只保留真实持仓/已成交买单位
    try:
        _keep_set = set(_keep)
        for _k in _BUY_SLOT_LIST_KEYS:
            if _k == 'bought':
                continue
            _lst = _db.get(_k)
            if isinstance(_lst, list):
                _db[_k] = [x for x in _lst if x in _keep_set]
        _kd = _db.get('bought_kind')
        if isinstance(_kd, dict):
            for _c in list(_kd):
                if _c not in _keep_set:
                    _kd.pop(_c, None)
    except Exception:
        pass


def _board_cancel_reconcile():
    # v1.13 撤单失败 cancel_pending 兜底：60s 一次查询 open/all，终态才释放名额/承诺
    # （2026-10-30 富佳/中重“撤单失败: 订单id 不存在”仍释放名额根因）。
    try:
        now = time.time()
        if now - float(getattr(g, 'last_board_cancel_reconcile_ts', 0.0) or 0.0) < float(BLS.get('order_reconcile_interval_sec', 60.0) or 60.0):
            return 0
        g.last_board_cancel_reconcile_ts = now
        pend = getattr(g, 'pending', None)
        if not isinstance(pend, dict):
            return 0
        n = 0
        for sec, pp in list(pend.items()):
            if str(pp.get('side') or '') != 'buy' or str(pp.get('cancel_pending')) != 'True':
                continue
            if str(pp.get('status') or '') in ('CANCELLED', 'REJECTED', 'FILLED'):
                pp.pop('cancel_pending', None)
                continue
            ent = str(pp.get('no') or '')
            if not ent:
                continue
            st = _query_open_order_status(ent, sec=sec, side='buy', qty=pp.get('qty'), backfill=True)
            if st == 'SENT':
                pp['cancel_pending_ts'] = now   # 撤单请求可能在途：继续等
                continue
            if st in ('CANCELLED', 'REJECTED'):
                pp['status'] = st
                pp['filled'] = int(pp.get('filled') or 0)
                _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
                _release_buy_slot(sec)
                log.info('[board-cancel-reconcile] %s 查询终态=%s -> 释放名额/承诺' % (_sn(sec), st))
                pp.pop('cancel_pending', None)
                n += 1
                continue
            if st == 'FILLED':
                pp['status'] = 'FILLED'
                pp['filled'] = int(pp.get('qty') or 0)
                _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
                log.info('[board-cancel-reconcile] %s 查询已成交 -> 保留名额释放承诺' % _sn(sec))
                pp.pop('cancel_pending', None)
                continue
            if st is None:
                pp['cancel_pending_ts'] = now   # 查询失败：保守等待
                continue
            # st == ''：查询成功无匹配，无法确认终态，不释放（on_order_response 仍会兜底）
            _skip_log('board_cancel', sec, 'lost', '[board-cancel-lost] %s 查询无匹配，不释放名额/承诺' % _sn(sec), throttle_sec=60.0)
            # v1.15 长时间无法确认终态告警（保留占坑，不新增重试频率）
            _ts0 = float(pp.get('cancel_pending_ts') or 0)
            if _ts0 > 0 and now - _ts0 > float(BLS.get('board_cancel_warn_sec', 300.0) or 300.0):
                _skip_log('board_cancel_warn', sec, 'pending',
                          '[board-cancel-warn] %s 撤单终态长时间未确认(%.0fs) -> 保留名额占坑' % (_sn(sec), now - _ts0),
                          throttle_sec=300.0)
        return n
    except Exception:
        return 0


def _no_reply_reconcile():
    # v1.13 发单后无任何回报兜底：SENT 超时后查询 open/all；在途保持、终态回填；
    # 无匹配打 [order-lost]（买入不释放 slot，卖出由 _sell_inflight 查询放行重投）。
    try:
        now = time.time()
        if now - float(getattr(g, 'last_no_reply_reconcile_ts', 0.0) or 0.0) < float(BLS.get('order_reconcile_interval_sec', 60.0) or 60.0):
            return 0
        g.last_no_reply_reconcile_ts = now
        pend = getattr(g, 'pending', None)
        if not isinstance(pend, dict):
            return 0
        timeout = float(BLS.get('order_no_reply_timeout', 90.0) or 90.0)
        n = 0
        for sec, pp in list(pend.items()):
            if str(pp.get('status') or 'SENT').upper() != 'SENT':
                continue
            ts = float(pp.get('ts') or 0)
            if ts <= 0 or now - ts <= timeout:
                continue
            ent = str(pp.get('no') or '')
            if not ent:
                continue
            st = _query_open_order_status(ent, sec=sec, side=pp.get('side'), qty=pp.get('qty'), backfill=True)
            if st in ('SENT', 'PARTIAL'):
                pp['ts'] = now   # 仍在在途/部分成交：刷新时间戳继续等
                continue
            if st in ('FILLED', 'CANCELLED', 'REJECTED'):
                pp['status'] = st
                if st == 'FILLED':
                    pp['filled'] = int(pp.get('qty') or 0)
                else:
                    pp['filled'] = int(pp.get('filled') or 0)
                if str(pp.get('side') or '') == 'buy':
                    _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
                    if st in ('CANCELLED', 'REJECTED'):
                        _release_buy_slot(sec)
                log.info('[order-reconcile] %s 查询终态=%s -> 回填' % (_sn(sec), st))
                n += 1
                continue
            # st is None（查询失败）或 ''（无匹配）：不释放/不重投，告警留痕
            _skip_log('order_lost', sec, 'noreply',
                      '[order-lost] %s SENT %.0fs 无回报且查询=%s 不释放/不重投' % (
                          _sn(sec), now - ts, st if st is not None else 'fail'),
                      throttle_sec=60.0)
        return n
    except Exception:
        return 0


def _reconcile_pending():
    # v0.64 重启对账：get_open_orders()+get_all_orders() 重建在途委托（跨重启防重复卖/买，配合 pending 持久化）
    try:
        oo = get_open_orders() or []
    except Exception:
        oo = []
    if not isinstance(oo, (list, tuple)) or not oo:
        return 0
    try:
        ao = get_all_orders() or []
    except Exception:
        ao = []
    info = {}
    for _d in (ao or []):
        try:
            if isinstance(_d, dict) and str(_d.get('entrust_no') or ''):
                info[str(_d['entrust_no'])] = _d
        except Exception:
            continue
    pend = getattr(g, 'pending', None)
    if not isinstance(pend, dict):
        pend = {}; g.pending = pend
    n = 0
    now = time.time()
    for o in oo:
        try:
            _ent = str(_o_get(o, 'entrust_no') or '')
            _sym = str(_o_get(o, 'symbol') or _o_get(o, 'stock_code') or '')
            sec = _norm_sec(_sym) if _sym else ''
            if not _ent or not sec:
                continue
            _di = info.get(_ent) or {}
            _amt = int(float(_o_get(_di, 'amount', 'business_amount') or _o_get(o, 'amount') or 0) or 0)
            _fld = int(float(_o_get(_di, 'filled_amount') or _o_get(o, 'filled') or 0) or 0)
            _px = float(_o_get(_di, 'price') or _o_get(o, 'limit') or _o_get(o, 'price') or 0)
            _bs = str(_di.get('entrust_bs') or _o_get(o, 'side', 'entrust_bs') or '')
            _sd = _trade_side(_bs) or ('buy' if _bs else '')
            _st = _map_order_status(_o_get(_di, 'status') or _o_get(o, 'status'))
            if sec in pend and str(pend[sec].get('no') or '') == _ent:
                pend[sec]['status'] = _st
                if _st == 'FILLED':
                    pend[sec]['filled'] = _fld or int(pend[sec].get('qty') or 0)
                elif _st in ('CANCELLED', 'REJECTED'):
                    pend[sec]['filled'] = _fld
                continue
            if _sd not in ('buy', 'sell'):
                _sd = 'buy'   # 方向不可判时按 buy 处理（不参与卖出在途守卫）
            _sb, _sbc = _seal_metrics(sec)   # v1.6 重启对账补排单封单基准（封单衰减撤单可继续生效）
            pend[sec] = {'no': _ent, 'side': _sd, 'qty': _amt, 'limit': _px,
                         'status': _st if _st in ('CANCELLED', 'REJECTED', 'FILLED') else 'SENT',
                         'filled': _fld, 'ts': now, 'mode': 'board' if _sd == 'buy' else '',
                         'seal_base': _sb, 'seal_bid_base': _sbc}
            n += 1
        except Exception:
            continue
    if n:
        log.info('[pending-restore] 重启对账在途委托 %d 单' % n)
    return n


def _reconcile_daily_bought_slots():
    # v1.5 同日重启交叉核对：daily.bought 只保留真实持仓或已成交买单，
    # 挂单未成交（无持仓且无 FILLED buy 在途）释放名额，防 daily_max_buy 被幽灵占坑。
    try:
        _db = getattr(g, 'daily', None)
        if not isinstance(_db, dict):
            return 0
        _bought = list(_db.get('bought') or [])
        if not _bought:
            return 0
        _pos = set()
        try:
            _p = get_positions() or {}
            for _k, _v in _p.items():
                _amt = 0
                try:
                    _amt = int(float((_v.get('amount') if isinstance(_v, dict) else getattr(_v, 'amount', 0) or 0) or 0) or 0)
                except Exception:
                    _amt = 0
                if _amt > 0:
                    _pos.add(_norm_sec(_k) or _k)
        except Exception:
            _pos = set()
        if not _pos:
            return 0   # 桥数据为空/不可用：保守不动，避免误杀真实成交
        _pend = getattr(g, 'pending', None) or {}
        _keep = []
        _rel = []
        for _c in _bought:
            _pp = _pend.get(_c) or {}
            _filled = int(_pp.get('filled') or 0)
            _filled_buy = (str(_pp.get('side') or '') == 'buy' and
                           (str(_pp.get('status') or '') == 'FILLED' or _filled > 0))
            if _c in _pos or _filled_buy:
                _keep.append(_c)
            else:
                _rel.append(_c)
        if not _rel:
            return 0
        _db['bought'] = _keep
        _reconcile_buy_slot_lists(_db, _keep)   # v1.14 分类列表同步（未成交释放不占对应名额）
        for _c in _rel:
            try:
                if isinstance(getattr(g, 'buy_commit', None), dict):
                    g.buy_commit.pop(_c, None)
                if isinstance(getattr(g, 'exp_fired', None), set):
                    g.exp_fired.discard(_c)
            except Exception:
                pass
        log.info('[buy-slot] 重启对账释放未成交占坑 %s (保留 %s)' % (_snl(_rel), _snl(_keep)))
        _save_state()
        return len(_rel)
    except Exception as e:
        _warn('buy-slot restart reconcile fail %r' % e)
        return 0


def place_order(context, sec, side, qty=None, note='', mode='chase', ratio=None):
    # v0.64 返回 bool：True=已发单/SIM 信号，False=跳过/失败（买入信号点仅成功才记 daily.bought）
    positions = context.portfolio.positions
    _lag, _lv = _rt_lag_info(sec)   # v0.43 灵敏度（检测->下单时延）
    if side == 'buy':
        if _mid_board_avoid(sec):   # v0.34 连板中位股统一兜底闸（覆盖弹性套利等入口，幂等）
            _skip_log('mid_avoid', sec, 'order', '[mid-avoid] %s 连板中位股规避(order)' % _sn(sec)); return False
        if BLS.get('skip_st_pool', True) and _is_st(sec):   # v0.77 全链路 ST 兜底（首板/回封/弹性/低吸统一）
            _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股拦截(order)' % _sn(sec)); return False
        limit = _order_limit(sec, side, mode)
        _log_order_limit(sec, limit)   # v1.12 限价来源审计
        px = limit or last_px(sec) or 0.0
        cash = _size_cash(context)   # v0.64 资金实时最新（减在途买单承诺）; v0.80 SIM 虚拟资金基准
        if px <= 0 or cash <= 0:
            if cash <= 0:
                return False   # v0.68 B3 首帧资金未就绪：静默跳过，下帧重试（不刷日志）
            _skip_log('place_order', sec, 'no_px_cash', 'place_order skip(no px/cash) %s' % _sn(sec)); return False
        qty = _calc_buy_qty(context, sec, px, float(ratio) if ratio else float(BLS.get('ordinary_buy_ratio', 0.10)))
        if qty <= 0:
            if _sim_mode():
                qty = int(BLS.get('sim_min_lot', 100) or 100)   # v0.80 SIM 最小一手兜底（信号可观察，不发真单）
                log.info('[sim-min-lot] %s buy qty 0->%d (SIM 最小一手兜底)' % (_sn(sec), qty))
            else:
                _skip_log('place_order', sec, 'qty0', 'place_order skip(qty<=0) %s' % _sn(sec)); return False
        qty = _buy_pos_cap_qty(context, sec, qty, limit)
        if qty <= 0:
            return False   # v0.30 情绪总仓位上限（冰点40%/回暖80%，连续回暖递减；v1.17 超限缩量/skip 参数化）
        _qty_calc_log(context, sec, 'order')
    else:
        limit = _order_limit(sec, side, mode)
        if qty is None:
            qty = int(getattr(positions.get(sec), 'amount', 0) or 0)
    if not qty or qty <= 0:
        _warn('place_order skip qty<=0 %s' % _sn(sec)); return False
    if not BLS['DO_ORDER']:
        log.info('[may-order] %s %s qty=%s limit=%s %s %s (DO_ORDER=False)' % (_sn(sec), side, qty, limit, note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent='', status='SIM')
        return True
    try:
        amt = qty if side == 'buy' else -qty   # v1.10 PTrade order(amount) 正=买/负=卖
        ent = order(sec, amt, limit_price=limit) if limit else order(sec, amt)
        _sb, _sbc = _seal_metrics(sec)   # v1.6 打板排单封单基准（封单衰减撤单用）
        _bc_send = int((getattr(g, 'first_zt', None) or {}).get(sec, {}).get('break_cnt') or 0) if mode in ('board', 'sweep') else 0
        g.pending[sec] = {'no': ent, 'side': side, 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0,
                          'ts': time.time(), 'mode': mode, 'seal_base': _sb, 'seal_bid_base': _sbc,
                          'break_cnt_at_send': _bc_send}   # v1.18 在途 break 保护基准
        if side == 'buy':
            _buy_commit_add(sec, qty, limit or px)   # v0.64 记入在途买单承诺（资金实时扣减）
        log.info('order sent %s %s qty=%s amt=%s limit=%s ent=%s ft_state=%s %s %s' % (
            _sn(sec), side, qty, amt, limit, ent, _ft_state_str(sec) if side == 'buy' else '-', note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent=ent, status='SENT')
        return True
    except Exception as e:
        log.error('order fail %s: %r' % (_sn(sec), e))
        return False


def place_expected_order(context, sec, note=''):
    _lag, _lv = _rt_lag_info(sec)   # v0.43 灵敏度（检测->下单时延）
    # 预期买入独立下单门控（EXPECT_ORDER）：仅此路径可在 DO_ORDER=False 时发真实单（模拟盘小额测试）
    if _mid_board_avoid(sec):   # v0.34 连板中位股统一兜底闸
        _skip_log('mid_avoid', sec, 'exp_order', '[mid-avoid] %s 连板中位股规避(exp-order)' % _sn(sec)); return False
    if BLS.get('skip_st_pool', True) and _is_st(sec):   # v0.77 预期买入 ST 兜底
        _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股拦截(exp-order)' % _sn(sec)); return False
    s = g.spot.get(sec) or {}
    px = last_px(sec) or 0.0
    up = float(s.get('up_px') or 0.0) if s else 0.0
    cash = _size_cash(context)   # v0.64 资金实时最新（减在途买单承诺）; v0.80 SIM 虚拟资金基准
    if px <= 0 or cash <= 0:
        if cash <= 0:
            return False   # v0.68 B3 首帧资金未就绪：静默跳过，下帧重试（不刷日志）
        _skip_log('exp_order', sec, 'no_px_cash', 'exp order skip(no px/cash) %s' % _sn(sec))
        return False
    rd = _intraday_ready_detail(sec)   # v1.4 A1：发单前分时就绪兜底，防状态机间隙 spot 失效误发
    if not rd:
        _skip_log('exp_order', sec, 'intraday_data_not_ready',
                  '[exp-order] %s intraday_data_not_ready(兜底) ready=%s %s' % (_sn(sec), rd, note))
        return False
    if _block_sealed_buy(sec):
        return False   # 一字/封死涨停：不排队买入（v0.15 对齐 AXquant limit_up_sealed_no_queue）
    if not _board_first_frame_ok(sec):
        _buy_ff_log(sec, 'expected', 'wait')
        _skip_log('exp_order', sec, 'no_first_frame',
                  '[exp-order] %s 非涨停价首帧成交 -> 等待(不追涨)' % _sn(sec),
                  throttle_sec=5.0)
        return False   # v1.26 预期买入统一打板，仅首帧涨停价成交后执行
    _buy_ff_log(sec, 'expected', 'ok')
    # 定价：v1.26 预期买入统一涨停价打板（首帧成交后最快排队），不再走追高。
    mode = 'board'
    if mode == 'board' and BLS.get('exp_board_queue_gate', True):
        _ok, _r = _exp_board_gate(sec)
        if not _ok:
            _bc = int((getattr(g, 'first_zt', None) or {}).get(sec, {}).get('break_cnt') or 0)
            _skip_log('exp_board', sec, _r,
                      '[exp-board-gate] %s break_cnt=%d 未回封/封单不足(%s) -> 等回封后重评' % (
                          _sn(sec), _bc, _r),
                      throttle_sec=5.0)
            return False   # v1.18 不置 exp_fired，回封后重新评估
    limit = _order_limit(sec, 'buy', mode)
    _log_order_limit(sec, limit)   # v1.12 限价来源审计
    p_for_size = limit or px
    ratio = float(BLS.get('board_buy_budget_ratio', BLS.get('exp_order_pct', 0.3)))
    qty = _calc_buy_qty(context, sec, p_for_size, ratio)
    if qty <= 0:
        if _sim_mode():
            qty = int(BLS.get('sim_min_lot', 100) or 100)   # v0.80 SIM 最小一手兜底（信号可观察，不发真单）
            log.info('[sim-min-lot] %s exp buy qty 0->%d (SIM 最小一手兜底)' % (_sn(sec), qty))
        else:
            _skip_log('exp_order', sec, 'qty0', 'exp order skip(qty<=0) %s' % _sn(sec)); return False
    qty = _buy_pos_cap_qty(context, sec, qty, limit)
    if qty <= 0:
        return False   # v0.30 情绪总仓位上限（v1.17 超限缩量/skip 参数化）
    _qty_calc_log(context, sec, 'exp-order')
    if BLS.get('EXPECT_ORDER', False):
        try:
            ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
            _sb, _sbc = _seal_metrics(sec)   # v1.6 一字/打板排单封单基准（封单衰减撤单用）
            _bc_send = int((getattr(g, 'first_zt', None) or {}).get(sec, {}).get('break_cnt') or 0) if mode in ('board', 'sweep') else 0
            g.pending[sec] = {'no': ent, 'side': 'buy', 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0,
                              'ts': time.time(), 'mode': mode, 'seal_base': _sb, 'seal_bid_base': _sbc,
                              'break_cnt_at_send': _bc_send}   # v1.18 字段与 place_order 对齐 + break 保护基准
            _buy_commit_add(sec, qty, limit or px)   # v0.64 记入在途买单承诺
            log.info('[exp-order] %s buy qty=%s limit=%s ent=%s ready=%s ft_state=%s %s %s (EXPECT_ORDER=True)' % (
                _sn(sec), qty, limit, ent, rd, _ft_state_str(sec), note, _lag))
            _signal(sec, 'BUY', qty, limit, mode, note, ent=ent, status='SENT')
            return True
        except Exception as e:
            log.error('exp order fail %s: %r' % (_sn(sec), e))
            return False
    log.info('[exp-order] %s buy qty=%s limit=%s ready=%s ft_state=%s %s %s (EXPECT_ORDER=False)' % (
        _sn(sec), qty, limit, rd, _ft_state_str(sec), note, _lag))
    _signal(sec, 'BUY', qty, limit, mode, note, ent='', status='SIM')
    return True


def on_order_response(context, order_list):
    # v0.64 委托主推（PTrade 回调传 list[dict]，兼容单对象）：回填 pending 状态、终态释放买名额/买入承诺
    try:
        items = order_list if isinstance(order_list, (list, tuple)) else [order_list]
        for _o in items:
            try:
                _ent = str(_o_get(_o, 'entrust_no', 'order_id') or '')
                _st_raw = _o_get(_o, 'order_status', 'status') or 'SENT'
                _st = _map_order_status(_st_raw)
                _sec_m = None; _p = {}
                if _ent:
                    for _sec, _pp in (getattr(g, 'pending', None) or {}).items():
                        if str(_pp.get('no') or '') == _ent:
                            _sec_m = _sec; _p = _pp
                            break
                if _sec_m is None:
                    # v1.9 委托号关联兜底：order() 返回 UUID，而 PTrade 回报 entrust_no 为数字，
                    # 2026-10-29 日志 [signal] side=ORD qty=0 空代码即根因（撤单/废单不释放名额与承诺）。
                    # 回报带股票代码时按 code 关联，并把网关委托号回填 pending.no，供后续回报与撤单使用。
                    _sec_r = _norm_sec(_o_get(_o, 'stock_code', 'ticker', 'code', 'sec', 'symbol') or '')
                    _pp2 = (getattr(g, 'pending', None) or {}).get(_sec_r) if _sec_r else None
                    if _pp2:
                        _sec_m = _sec_r; _p = _pp2
                        if _ent:
                            _p['no'] = _ent
                if _sec_m:
                    _p['status'] = _st
                    if _st == 'FILLED':
                        _p['filled'] = int(_p.get('qty') or 0)
                    elif _st in ('CANCELLED', 'REJECTED'):
                        _p['filled'] = int(_p.get('filled') or 0)   # 保留已成交部分
                log.info('on_order_response %s status=%s sec=%s pend_side=%s' % (
                    _ent, _st_raw, _sn(_sec_m) if _sec_m else '-', _p.get('side') or '-'))
                _signal(_sec_m, 'ORD', int(_p.get('qty') or 0), float(_p.get('limit') or 0.0), 'ord', 'order_response', ent=_ent, status=_st)
                if _sec_m and str(_p.get('side') or '') == 'buy' and _st in ('CANCELLED', 'REJECTED', 'FILLED'):
                    _buy_commit_rel(_sec_m, int(_p.get('qty') or 0), float(_p.get('limit') or 0.0))
                    if _st in ('CANCELLED', 'REJECTED'):
                        _release_buy_slot(_sec_m)
            except Exception:
                continue
    except Exception as e:
        _warn('on_order_response err %r' % e)


def on_trade_response(context, trade_list):
    # v0.64 成交主推（PTrade 回调传 list[dict]，兼容单对象）：sell 成交回填 filled+sold_log+daily.sold；
    #       buy 成交回填 pending 并按成交额释放买入承诺（资金实时扣减）；撤单/废单主推跳过
    try:
        items = trade_list if isinstance(trade_list, (list, tuple)) else [trade_list]
        for _t in items:
            try:
                code = _norm_sec(_o_get(_t, 'stock_code', 'ticker', 'code', 'sec', 'symbol') or '')
                if not code:
                    continue
                _rt = str(_o_get(_t, 'real_type') or '0')
                _ts = _map_order_status(_o_get(_t, 'status'))
                if _rt == '2' or _ts in ('CANCELLED', 'REJECTED'):
                    continue   # 撤单/废单主推：非成交，跳过（成交累积不误加）
                try:
                    _hold_exp_init(code)   # v0.32 持仓预期管理：成交即建立条目（幂等）
                except Exception:
                    pass
                qty = abs(int(float(_o_get(_t, 'business_amount', 'quantity', 'volume', 'amount') or 0) or 0))   # v0.64 成交量为负(撤单/卖)取绝对值
                side = str(_o_get(_t, 'entrust_bs', 'side', 'business_bs') or '')
                _side = _trade_side(side)
                p = (getattr(g, 'pending', None) or {}).get(code) or {}
                _ps = str(p.get('side') or '')
                # v1.10 成交方向优先真实 entrust_bs/side（PTrade '1'=买 '2'=卖）；pending 仅作缺失回退。
                # 方向冲突必须告警：2026-10-29 卖出误发为买入时回报 side=1，v1.8 用 pending 掩盖了该缺陷。
                _eff = _side if _side in ('buy', 'sell') else _ps
                if _side in ('buy', 'sell') and _ps in ('buy', 'sell') and _side != _ps:
                    _warn('side-conflict %s raw=%s pend=%s eff=%s' % (_sn(code), side, _ps, _eff))
                if _eff == 'sell':
                    p['filled'] = int(p.get('filled') or 0) + qty
                    p['last_trade_ts'] = time.time()
                    if p['filled'] >= int(p.get('qty') or p['filled']):
                        p['status'] = 'FILLED'
                    else:
                        p['status'] = 'PARTIAL'
                    if not isinstance(getattr(g, 'sold_log', None), dict):
                        g.sold_log = {}
                    g.sold_log[code] = time.time()
                    _sold_out = _sell_order_sold_out(code)
                    daily = g.daily.setdefault('sold', [])
                    if _sold_out:
                        if code not in daily:
                            daily.append(code)   # v1.33 仅整票卖完才进入 sold 过滤视图
                    elif code in daily:
                        daily.remove(code)   # v1.33 清掉旧版误标的半仓/分批卖单
                    if str(p.get('status') or '').upper() == 'FILLED' and not _sold_out:
                        log.info('[sell-remain] %s 卖单FILLED但仍有剩余 src_qty=%s filled=%s -> 继续卖出监控' % (
                            _sn(code), p.get('src_qty') or '-', p.get('filled') or '-'))
                    _save_state()
                elif _eff == 'buy':
                    p['filled'] = int(p.get('filled') or 0) + qty
                    if p['filled'] >= int(p.get('qty') or p['filled']):
                        p['status'] = 'FILLED'
                    else:
                        p['status'] = 'PARTIAL'
                    _bq = getattr(g, 'bought_qty', None)
                    if not isinstance(_bq, dict):
                        _bq = {}; g.bought_qty = _bq
                    _bq[code] = int(_bq.get(code, 0) or 0) + qty   # v1.22 当日买入成交累计（桥 enable 未回填审计基准）
                    _buy_commit_rel(code, qty, float(p.get('limit') or 0.0))   # 按成交额释放承诺
                log.info('on_trade_response %s qty=%s raw_side=%s pend_side=%s eff=%s' % (
                    _sn(code), qty, side, _ps, _eff))
                _signal(code, _eff or _ps or side, qty, 0, 'fill', 'trade_response', ent='', status=str(p.get('status') or 'TRADE'))
            except Exception:
                continue
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
        _d = st.get('daily', {'bought': [], 'sold': []})
        if not isinstance(_d, dict):
            _d = {}
        _d.setdefault('bought', [])
        _d.setdefault('bought_board', [])
        _d.setdefault('bought_other', [])
        for _k in _BUY_STRATEGY_KINDS:
            _d.setdefault('bought_' + _k, [])
        _d.setdefault('bought_kind', {})
        g.daily = _d
        g.exp_fired = set(st.get('exp_fired') or [])
        g.state_day = st.get('day')
        _today = str(get_trading_day())
        if st.get('day') == _today:
            # v1.3 双重守卫：state 的 day 是今日不代表行情/首触状态属于今日（进程跨日或状态文件异常时
            # 昨日 auction_c/first_zt 可能被写成今日），非当日残留一律清空并由 _rebuild_first_zt_queue 重建。
            _ac_day = str(st.get('ac_day') or '')
            _fz_day = str(st.get('first_zt_day') or '')
            if _ac_day == _today:
                g.auction_c = dict(st.get('auction_c') or {})
            else:
                g.auction_c = {}
                if st.get('auction_c'):
                    log.info('[restart-guard] auction_c 非当日残留(ac_day=%s) -> 清空' % _ac_day)
            if _fz_day == _today:
                _fz0 = dict(st.get('first_zt') or {})
                g.first_zt = {k: dict(v) for k, v in _fz0.items()
                              if str((v or {}).get('day') or '') == _today}
                if len(g.first_zt) != len(_fz0):
                    log.info('[restart-guard] first_zt 含跨日/无日期记录 %d 家 -> 丢弃(保留 %d)'
                             % (len(_fz0) - len(g.first_zt), len(g.first_zt)))
            else:
                g.first_zt = {}
                if st.get('first_zt'):
                    log.info('[restart-guard] first_zt 非当日残留(first_zt_day=%s) -> 清空重建' % _fz_day)
            g.break_sold = set(st.get('break_sold') or [])
            g.seal_sold = set(st.get('seal_sold') or [])
            g.break2_sold = set(st.get('break2_sold') or [])
            g.board_cancel_log = set(st.get('board_cancel_log') or [])   # v1.6 同日重启恢复撤单去重
            g.reboard_fired = bool(st.get('reboard_fired'))
            g.l2_big = {k: dict(v, seen=set(v.get('seen') or [])) for k, v in (st.get('l2_big') or {}).items()}
            g.l2_dir_dist = dict(st.get('l2_dir_dist') or {})
            g.l2_big_wm = dict(st.get('l2_big_wm') or {})
            g.dyn_unq = st.get('dyn_unq')
            g.exp_day = st.get('exp_day')   # v0.53 同日重启恢复 exp_day，首帧日切不清盘中状态
            g.exp_file = dict(st.get('exp_file') or {})   # v1.5 同日重启恢复盘中合成预期池（防 34->5 收缩）
            g.p7a_sold = set(st.get('p7a_sold') or [])
            g.p7b_sold = set(st.get('p7b_sold') or [])
            g.p7c_part = dict(st.get('p7c_part') or {})
            g.p7c_sold = set(st.get('p7c_sold') or [])
            g.p7d_sold = set(st.get('p7d_sold') or [])
            g.p6_weak = dict(st.get('p6_weak') or {})   # v1.20 同日重启恢复 P6 两帧计数
            g.pending = {k: dict(v) for k, v in (st.get('pending') or {}).items()}   # v0.64 同日重启恢复在途委托
            g.buy_commit = dict(st.get('buy_commit') or {})   # v0.64 同日重启恢复买入承诺
            g.lb_senti = dict(st.get('lb_senti') or {})   # v0.65 同日重启恢复连板盘中情绪动态
            g.ma5_touch_day = st.get('ma5_touch_day')
            g.ma5_touched = set(st.get('ma5_touched') or [])   # v0.69 同日重启恢复当日首触去重
            g.ma5_lifecycle_day = st.get('ma5_lifecycle_day')
            g.ma5_lows = {k: list(v or [])[:2] for k, v in (st.get('ma5_lows') or {}).items()}
            g.ma5_pending = set(st.get('ma5_pending') or [])   # v1.21 MA5 未就绪待补评
            g.bought_qty = dict(st.get('bought_qty') or {})   # v1.22 当日买入成交累计跨重启恢复
            g.hist_recover_once = dict(st.get('hist_recover_once') or {})   # v1.22 恢复日志去重跨重启恢复
            g.t1_pending_sell = dict(st.get('t1_pending_sell') or {})   # v1.30 T+1 保护记录跨重启恢复
            g.t1_pending_log_ts = dict(st.get('t1_pending_log_ts') or {})
            g.tx_lag_stats = dict(st.get('tx_lag_stats') or {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''})   # v1.35 延迟汇总跨重启保留
        else:
            g.auction_c = {}   # v1.3 跨日不再沿用内存旧值（防进程跨日残留）
            g.first_zt = {}    # v1.3 跨日强制清空，由当日 tick/重建队列重新建立
            g.break_sold = set()
            g.seal_sold = set()
            g.break2_sold = set()
            g.board_cancel_log = set()   # v1.6 跨日清空撤单去重
            g.reboard_fired = False
            g.dyn_unq = None
            g.l2_big = {}; g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}
            g.buy_commit = {}     # 跨日清空在途买单承诺
            g.lb_senti = {}       # v0.65 跨日清空连板盘中情绪动态
            g.ma5_touch_day = None; g.ma5_touched = set()   # v0.69 跨日清空低吸首触去重
            g.ma5_lifecycle_day = None; g.ma5_lows = {}     # v0.70 跨日清空次低价状态
            g.ma5_pending = set()                            # v1.21 跨日清空 MA5 待补评
            g.p6_weak = {}       # v1.20 跨日清空 P6 两帧计数
            g.exp_day = None   # v0.53 跨日：首帧日切正常触发
            g.exp_file = {}      # v1.5 跨日强制清空预期文件池
            g.bought_qty = {}    # v1.22 跨日清空买入成交累计
            g.hist_recover_once = {}   # v1.22 跨日清空恢复日志去重
            g.t1_pending_sell = dict(st.get('t1_pending_sell') or {})   # v1.30 跨日保留 T+1 pending 给次日消费
            g.t1_pending_log_ts = {}
            g.tx_lag_stats = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}   # v1.35 跨日清零
    except Exception:
        g.buy_log = {}; g.sold_log = {}
        g.daily = _new_daily(); g.state_day = None
        g.exp_fired = set(); g.ma5_touch_day = None; g.ma5_touched = set()
        g.ma5_lifecycle_day = None; g.ma5_lows = {}; g.ma5_pending = set()
        g.p6_weak = {}          # v1.20 异常分支同样清空 P6 两帧计数
        g.auction_c = {}; g.first_zt = {}   # v1.3 异常分支不保留内存旧行情/首触（防毒状态固化）
        g.exp_file = {}                      # v1.5 异常分支同样清空预期文件池
        g.bought_qty = {}; g.hist_recover_once = {}   # v1.22 异常分支同样清空
        g.t1_pending_sell = {}; g.t1_pending_log_ts = {}   # v1.30 异常分支清空保护记录
        g.tx_lag_stats = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}   # v1.35 异常分支清零


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
                         'break2_sold': sorted(getattr(g, 'break2_sold', None) or []),
                         'board_cancel_log': sorted(getattr(g, 'board_cancel_log', None) or []),   # v1.6 打板撤单去重
                         'reboard_fired': bool(getattr(g, 'reboard_fired', False)),
                         'dyn_unq': dict(getattr(g, 'dyn_unq', None) or {}),
                         'l2_big': dict(getattr(g, 'l2_big', None) or {}),
                         'l2_dir_dist': dict(getattr(g, 'l2_dir_dist', None) or {}),
                         'l2_big_wm': dict(getattr(g, 'l2_big_wm', None) or {}),
                         'exp_day': getattr(g, 'exp_day', None),
                         'exp_file': dict(getattr(g, 'exp_file', None) or {}),   # v1.5 盘中合成预期池持久化
                         'p7a_sold': sorted(getattr(g, 'p7a_sold', None) or []),
                         'p7b_sold': sorted(getattr(g, 'p7b_sold', None) or []),
                         'p7c_part': dict(getattr(g, 'p7c_part', None) or {}),
                         'p7c_sold': sorted(getattr(g, 'p7c_sold', None) or []),
                         'p7d_sold': sorted(getattr(g, 'p7d_sold', None) or []),
                         'p6_weak': dict(getattr(g, 'p6_weak', None) or {}),   # v1.20 P6 两帧计数
                         'pending': {k: dict(v) for k, v in (getattr(g, 'pending', None) or {}).items()},   # v0.64 在途委托持久化
                         'buy_commit': dict(getattr(g, 'buy_commit', None) or {}),
                         'lb_senti': dict(getattr(g, 'lb_senti', None) or {}),
                         'ma5_touch_day': getattr(g, 'ma5_touch_day', None),
                         'ma5_touched': sorted(getattr(g, 'ma5_touched', None) or []),
                         'ma5_lifecycle_day': getattr(g, 'ma5_lifecycle_day', None),
                         'ma5_lows': dict(getattr(g, 'ma5_lows', None) or {}),
                         'ma5_pending': sorted(getattr(g, 'ma5_pending', None) or []),
                         'bought_qty': dict(getattr(g, 'bought_qty', None) or {}),   # v1.22 当日买入成交累计持久化
                         'hist_recover_once': dict(getattr(g, 'hist_recover_once', None) or {}),   # v1.22 恢复日志去重持久化
                         't1_pending_sell': dict(getattr(g, 't1_pending_sell', None) or {}),   # v1.30 T+1 保护记录持久化
                         't1_pending_log_ts': dict(getattr(g, 't1_pending_log_ts', None) or {}),
                         'tx_lag_stats': dict(getattr(g, 'tx_lag_stats', None) or {})}, f, protocol=2)   # v1.30 保护日志节流持久化 + v1.35 延迟汇总
    except Exception as e:
        _warn('save_state fail %r' % e)


def after_trading_end(context, data):
    _save_state()
    try:
        _senti_hist_touch('final')   # v1.31 收盘终态情绪温度落档
    except Exception as e:
        _warn('senti_hist final touch fail: %r' % e)
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
    try:
        _dd = getattr(g, 'l2_dir_dist', None)
        if isinstance(_dd, dict) and _dd:
            log.info('[l2-dir] 当日大单方向取值分布=%s' % ({k: v for k, v in sorted(_dd.items())},))
    except Exception:
        pass
    try:   # v1.35 逐笔延迟日终汇总（provider 水印落后溯源）
        _tl = getattr(g, 'tx_lag_stats', None)
        if isinstance(_tl, dict) and int(_tl.get('cnt') or 0) > 0:
            log.info('[tx-lag-summary] cnt=%d avg=%.1fs max=%.1fs sample=%s' % (
                int(_tl.get('cnt') or 0), float(_tl.get('sum') or 0.0) / int(_tl.get('cnt') or 0),
                float(_tl.get('max') or 0.0), str(_tl.get('sample') or '-')))
            g.tx_lag_stats = {'cnt': 0, 'sum': 0.0, 'max': 0.0, 'sample': ''}
    except Exception:
        pass
    try:   # v1.35 预算超限峰值日终汇总
        _pk = getattr(g, 'budget_over_peak', None)
        if isinstance(_pk, dict) and _pk:
            log.info('[budget-over-summary] %s' % (','.join('%s=%d' % (k, int(v)) for k, v in sorted(_pk.items()))))
            g.budget_over_peak = {}
    except Exception:
        pass
    try:
        _rows = _l2_big_day_summary()
        if _rows:
            _parts = ['%s 买=%.0f/%d笔 卖=%.0f/%d笔 净=%.0f' % (
                _sn(sec), buy, bn, sell, sn, buy - sell) for sec, buy, sell, _n, bn, sn, _u in _rows]
            log.info('[l2-big-sum] 当日买入/卖出大单(买-卖=净, 元): %s' % ' | '.join(_parts))
    except Exception:
        pass
    _strategy_used = ' '.join('%s=%d/%d' % (
        k, len(g.daily.get('bought_' + k) or []), _buy_slot_limit(k)) for k in _BUY_STRATEGY_KINDS)
    log.info('buysell_core end bought=%s board=%d total=%d %s sold=%s' % (
        _snl(g.daily.get('bought')), len(g.daily.get('bought_board') or []),
        len(g.daily.get('bought') or []), _strategy_used, _snl(g.daily.get('sold'))))
