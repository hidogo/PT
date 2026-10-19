# -*- coding: utf-8 -*-
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
# v0.14 预期买入两阶段（T+1，side=buy 且预期超预期）：
#   1) 竞价终态初步确认「竞价超预期」-> 观察（不买）；2) 分时确认超预期(两分钟上攻 或 一分钟冲涨停,且不破VWAP) -> 执行买入。
#   tick_data 3s 事件触发 + 一次触发持久化去重(exp_fired) + 独立 EXPECT_ORDER 实盘门控。
import time, pickle, csv


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
    'scan_interval': 4,             # 每 N 根 bar 触发一次全市场扫描
    'score_sell_clear': 30, 'score_sell_half': 50,
    # 止损按板块
    'stop_loss_pct': 0.05, 'stop_loss_chinext': 0.07, 'stop_loss_star': 0.08, 'stop_loss_bse': 0.10,
    'elastic_max_buy_pct': 0.10,      # 弹性追高 300/688 买入价前收*1.10 上限（打板豁免）
    'exp_sell_on_pending_miss': False, # P2E 竞价核卖：pending_miss 默认只记录暂缓，confirmed_miss/degraded 才卖
    'single_stock_cap': 0.30,          # 单支市值上限：买入后该股市值 <= 总资产×30%（AXquant single_stock_cap）
    'ordinary_buy_ratio': 0.10,        # 普通买入单笔=总资产×10%（AXquant ordinary_buy_ratio=1/10，替代硬编码0.3）
    'board_buy_budget_ratio': 0.20,    # 打板买入单笔=总资产×20%（AXquant board_buy_budget_ratio）
    'red_gate_enabled': False,         # 红盘比买入门（默认关；开启才要求板块红盘比>=red_ratio_buy_min）
    'red_ratio_buy_min': 0.55,         # 红盘比下限（对齐 AXquant first_board_buy 回暖下限）
    # v0.18 买入场景补齐：核心票买入 + 首板打板（AXquant first_board_buy / CORE 门禁）
    'core_buy_enabled': True,          # 核心票买入总开关
    'core_max_lianban': 6,             # 核心票连板上限：>=6 不追（高标不接）
    'core_sealed_skip': True,          # 核心票一字/封死涨停不排队买入
    'core_buy_window_min': 30,         # 核心票买入窗口：开盘 N 分钟内（10:00 前，其它类）
    'ma5_buy_window_min': 60,          # 5日低吸窗口：开盘 N 分钟内（10:30 前 = 60 分钟）
    'exp_buy_window_min': 30,          # 预期买入窗口：开盘 N 分钟内（10:00 前，其它类）
    'first_board_buy_enabled': True,   # 首板打板总开关（tick 首触主路径 + 1m 兜底）
    'first_board_minute': 10,          # 首板闸门：开盘 N 分钟内（09:30-09:40）
    'first_board_seal_min': 50000.0,   # 首板打板最小封单额(元)（与 firstzt 门槛一致）
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
    'm1_surge_cache_ttl': 15.0,      # 弹性 1m 大阳线缓存 s（窗口内避免重复拉取）
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
    # 打分引擎（AXquant 默认）
    'score_base': 40, 'score_max': 92, 'score_min': 0,
    'vwap_penalty_per_min': 1.0, 'vwap_daily_limit': 12,
    # 预期角色容忍度（AXquant sell_policy_hint 迁移，docs/17）：绿开/止损/评分阈值缩放系数
    'sell_policy': {
        'hold_higher_tolerance': {'green_tol': 2.5, 'stop_adj': 1.3, 'score_clear_adj': 0.6, 'score_half_adj': 0.8},
        'fast_exit_on_weak':     {'green_tol': 0.5, 'stop_adj': 0.8, 'score_clear_adj': 1.05, 'score_half_adj': 1.0},
        'watch_break_sell':      {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 0.9, 'score_half_adj': 1.0},
        'break_weak_escape':     {'green_tol': 0.6, 'stop_adj': 0.7, 'score_clear_adj': 1.1, 'score_half_adj': 1.0},
        'vwap_follow':           {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
        'none':                  {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
    },
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
    # 单文件内定义，实例挂 g.ds；按交易日惰性自重置（cached/snapshot 自动触发），
    # 避免在 initialize/日切/盘中拉起多处手动清缓存。保持现有过程式函数签名兼容。
    def __init__(self):
        self.cache = {}        # (source, sec) -> (ts, value)
        self.degraded = set()  # 已降级数据源（失败隔离标记）
        self._day = ''

    def reset(self, day=None):
        self.cache.clear(); self.degraded.clear()
        if day is not None:
            self._day = day

    def _maybe_reset(self):
        try:
            day = str(get_trading_day())
        except Exception:
            day = ''
        if day and day != self._day:
            self.cache.clear(); self.degraded.clear(); self._day = day

    def cached(self, source, sec, ttl, fetch):
        # 统一缓存原语：命中直接返回；未命中调 fetch() 并缓存（含安全默认值）；
        # fetch 抛异常 -> 记 degraded、不缓存、返回 None（下一帧再试）
        self._maybe_reset()
        key = (source, sec)
        hit = self.cache.get(key)
        if hit is not None and (time.time() - hit[0]) < ttl:
            return hit[1]
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
        if miss:
            raw = self._tx_pull_raw(miss) or {}
            fields = raw.get('fields') or []
            for sec in miss:
                ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
                if ms is not None:
                    out[sec] = ms
        return out

    def _tx_pull_raw(self, secs):
        # 按 3s 帧缓存原始逐笔（同一帧多消费不重复拉）；异常 -> {}（不缓存，下一帧再试）
        token = int(time.time() / 3.0)
        return self.cached(('tx_pull', token), '_frame_', 3.0,
                           lambda: get_individual_transaction(secs,
                                                              data_count=int(BLS.get('firsttx_data_count', 200)),
                                                              is_dict=True) or {}) or {}

    def snapshot(self, secs):
        # 帧首批量快照：get_snapshot(列表) 一次回填 g.spot；批量缺标再逐只兜底（正常 0 次）
        self._maybe_reset()
        secs = [s for s in (secs or []) if s]
        if not secs:
            return {}
        got = {}
        try:
            sn = get_snapshot(secs)
            if isinstance(sn, dict):
                got = sn
        except Exception:
            self.degraded.add('snapshot')
        for c in secs:
            d = got.get(c)
            if isinstance(d, dict):
                g.spot[c] = d
            else:
                try:
                    one = get_snapshot(c) or {}
                    if isinstance(one, dict) and one:
                        g.spot.update(one)
                    else:
                        g.spot[c] = {}           # 批量/兜底均无 -> 置空，与原逐只行为一致
                except Exception:
                    g.spot[c] = {}
                    self.degraded.add('snapshot')
        return g.spot


def initialize(context):
    set_universe(BLS['universe'])
    g.buy_log = {}; g.sold_log = {}
    g.daily = {'bought': [], 'sold': []}
    g.state_day = None   # 持久化的“交易日”戳（跨重启每日买入计数恢复）
    g.spot = {}; g.last_ma5 = {}
    g.ds = DataHub()   # 聚合数据源薄层（批量快照 + 统一 TTL 缓存）
    g.hist = {}         # sec -> (ts, df)  1d 历史缓存
    g.bs_cache = {}     # sec -> (ts, board_strength)
    g.bs_codes = {}     # sec -> (ts, 板块成分代码)（首板闸门：板块内涨幅最高）
    g.first_board_fired = set()  # 首板打板当日去重（tick 首触 / 1m 兜底共用）
    g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}   # 弹性套利：板块一字板统计缓存（60s，按日重置）
    g.gear_cache = {}     # sec -> (ts, get_gear_price)  L2 十档帧级缓存
    g.m1_surge_cache = {} # sec -> (ts, 1m大阳线%)        弹性窗口缓存
    g.now_dt = None     # 当前 bar 时间（context.blotter.current_dt，回测/交易均可用）
    g.bar_counter = 0
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
    g.zt_lianban = {}   # sec -> T-1 涨停/连板名单（AXquant limit_up_boards 导出, upload_file）
    g.exp_file = {}     # sec -> 预期文件条目（AXquant 竞价终态）
    g.exp_fired = set() # sec -> 本日已触发(买/放弃)的预期买入（一次触发+跨重启去重）
    g.pending = {}      # sec -> 已发送委托（成交确认前的去重/回执）
    run_daily(context, auction_pre_confirm, time='09:25')
    run_daily(context, after_open_probe, time='09:31')
    run_daily(context, mid_probe, time='11:00')
    log.info('buysell_core init universe=%s DO_ORDER=%s EXPECT_ORDER=%s' % (_snl(BLS['universe']), BLS['DO_ORDER'], BLS.get('EXPECT_ORDER', False)))


def before_trading_start(context, data):
    _set_now(context)
    load_state()
    _today = str(get_trading_day())
    if getattr(g, 'state_day', None) == _today:
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
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    for sec in list(dict.fromkeys(BLS['universe'] + list(get_positions()))):
        df = _hist_1d(sec)
        if df is not None and len(df) >= 6:
            g.last_ma5[sec] = float(df['close'].iloc[-6:-1].mean())
    log.info('before_trading_start done positions=%s' % list(get_positions()))


def handle_data(context, data):
    _set_now(context)
    g.bar_counter += 1
    refresh_spot(context)
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
        g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.gear_cache = {}; g.m1_surge_cache = {}; g.ds = DataHub()
        for sec in list(get_positions()):
            g.exp.setdefault(sec, {})
            au, _r = _eval_auction(sec)
            g.exp[sec]['auction_status'] = au
            g.exp[sec]['status'] = _eval_intraday(sec, au)[0]
    sell_manager(context)
    _try_expected_buys(context)
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if BLS['ma5_pullback']:
        try_ma5_buy(context)
    try_core_buy(context)
    _try_first_board_buy_1m(context)
    _try_elastic_arb_buy(context)


# ================= 行情/工具 =================
def _hist_1d(sec):
    # 1d OHLCV 缓存（约 60s 有效，统一 DataHub 注册表）
    try:
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        return dh.cached('hist1d', sec, 60.0,
                         lambda: get_price(sec, start_date=None, end_date=None, count=120, frequency='1d'))
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
    # 低于 VWAP 每 1 分钟扣 1 分，日上限 12（用快照 wavg_px 近似 VWAP）
    px = last_px(sec); s = g.spot.get(sec)
    vwap = float(s.get('wavg_px') or 0.0) if s else 0.0
    if not px or not vwap:
        return 0.0
    if px >= vwap:
        return 0.0
    mins = _min_age()
    return min(BLS['vwap_daily_limit'], mins * BLS['vwap_penalty_per_min'])


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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
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

def _sealed_at_limit(sec):
    # 封死涨停（一字/排满）：现价=涨停价 且 卖盘无挂单 -> 挂单只能排队，AXquant 不参考排单（P1-3 limit_up_sealed_no_queue）
    # 无 L2 盘口(回测)时不判定封死，走保守可买路径，与 AXquant _is_sealed_at_limit has_book 一致。
    s = g.spot.get(sec) or {}
    px = last_px(sec); up = float(s.get('up_px') or 0.0)
    if not px or px <= 0 or up <= 0 or px < up * 0.998:
        return False
    try:
        gp = _gear(sec)
        ask = gp.get('ask_grp')
        if not isinstance(ask, dict):
            return False                      # 无盘口数据 -> 保守判非封死
        if not ask:
            return True                        # 显式空卖盘 -> 封死
        for row in ask.values():
            if isinstance(row, (list, tuple)) and len(row) >= 2 and float(row[1] or 0) > 0:
                return False                   # 任一档有真实卖单金额 -> 未封死
        return True
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

def _two_1m_break(sec):
    # 两根 1m 站上 open*(1+fast_up_ratio)，且当前根仍站上
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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        return dh.cached('bcode', sec, 3600.0, lambda: _fetch_board_code(sec))
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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        v = dh.cached('board_chgs', str(board_code), _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(board_code))
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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        v = dh.cached('board_chgs', b, _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(b))
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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        token = '|'.join(boards)
        v = dh.cached(('board_rank', token), '_', _board_refresh_ttl(),
                      lambda: _compute_board_rank(boards))
        return v if v is not None else set()
    except Exception:
        return set()


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
            log.warn('dump_scores fail %s: %r' % (_sn(sec), e))


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
            log.warn('get_Ashares fail: %r' % e)
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
        log.info('market_scan bar=%s pool=%d watch=%d' % (_hhmm(), len(g.pool_all or []), len(g.watch)))
    except Exception as e:
        log.warn('market_scan fail: %r' % e)



def _expectation_paths():
    # 候选：研究根目录优先，upload_file/（定时上传自建）、data/、data/upload_file/ 兜底
    day = str(get_trading_day())
    suf = BLS.get("expectation_suffix", ".csv")
    latest = [r + "expectation_latest" + suf for r in _research_roots()]   # 稳定指针（生成日期命名，见 docs/25），云端优先读
    return latest + [r + "expectation_" + day + suf for r in _research_roots()]   # 后兜底交易日命名文件

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
    # 复用研究四层根：稳定指针 zt_lianban_latest.csv 优先, 再按当日日期(兼容 upload_file/)。
    day = str(get_trading_day())
    cands = [r + "zt_lianban_latest.csv" for r in _research_roots()]
    for r in _research_roots():
        cands.append(r + "zt_lianban_" + day + ".csv")
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
            }
        log.info("[zt-lianban] loaded %s -> %d" % (fp, len(g.zt_lianban)))
        return len(g.zt_lianban)
    except Exception as e:
        log.info("[zt-lianban] skip(invalid) %s: %r" % (fp, e))
        return 0

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
            # 兜底：基准缺失(has_bm False) 或 真竞价缺失(actual~-100) 均不误弃，保持等待；确未达标 -> 放弃
            _bm, _has_bm = _auction_benchmark(code)
            if not _has_bm or actual < -90.0:
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
        g.daily["bought"].append(code)
        g.exp_fired.add(code)
        g.buy_log[code] = now
        _save_state()
        return True
    return None   # 仍在等待，不爆

def _try_expected_buys(context):
    # 预期买入：tick(3s) 与 handle_data(1m) 共用同一判定/去重，避免双触发
    if _min_age() > int(BLS.get('exp_buy_window_min', 30)):
        return                       # 预期买入窗口：10:00 前（其它类）
    if not g.exp_file or len(g.daily["bought"]) >= BLS["daily_max_buy"]:
        return
    for code, en in g.exp_file.items():
        if str(en.get("side") or "") != "buy":
            continue
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
            if score >= BLS['buy_score_min'] and (not BLS.get('red_gate_enabled', False) or _red_ratio(sec) >= BLS.get('red_ratio_buy_min', 0.55)):
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
        if score >= BLS['buy_score_min'] and (not BLS.get('red_gate_enabled', False) or _red_ratio(sec) >= BLS.get('red_ratio_buy_min', 0.55)):
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
    try:
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
            codes = [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board_code)) or [])[:20]) if x]
    except Exception:
        codes = []
    g.bs_codes[sec] = (time.time(), tuple(codes))
    return codes


def _board_top_gainer(sec):
    # 板块内涨幅最高（且为正）：sec 现价涨幅 >= 同板块全部成员（首板闸门之一）
    my = _sector_chg(sec)
    if my <= 0:
        return False
    for m in _board_member_codes(sec):
        if m == sec:
            continue
        try:
            d = g.spot.get(m) or (get_snapshot(m) or {}).get(m) or {}
            mp = float(d.get('preclose_px') or 0.0); mpx = float(d.get('last_px') or 0.0)
        except Exception:
            continue
        if mp > 0 and mpx > 0 and (mpx / mp - 1.0) > my + 1e-9:
            return False
    return True


def _board_first_zt(sec):
    # 主动（最快拉升）：同板块成员中首个触板（无更早触板成员则本票为最快）；缺成员对比时放行
    my = (g.first_zt.get(sec) or {}).get('ts') or time.time()
    for m in _board_member_codes(sec):
        if m == sec:
            continue
        if _is_one_word_open(m):
            continue                      # 一字板成员不参与"主动最快"竞争（竞价一字非主动拉升）
        f = g.first_zt.get(m) or {}
        t = f.get('ts') or 0
        if t and t < my - 1e-6:
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
            log.warn('first_board_buy(1m) fail %r' % e)


# ================= 弹性套利 elastic_arb（AXquant，v0.19 Phase 1） =================
def _elastic_yizi_pool():
    # 一字板统计候选：池(自选+预期+watch) + T-1 涨停名单（今日续板/一字近似；全市场实时名单 PT 无）
    out = list(_pool()) + list((getattr(g, 'zt_lianban', {}) or {}).keys())
    return [x for x in (_norm_sec(c) for c in out) if x]


def _boards_of(sec):
    # 所属板块代码列表（get_stock_blocks 首层；与 _board_member_codes 同口径）
    try:
        blocks = get_stock_blocks(sec) or {}
        names = []
        for lst in blocks.values():
            if isinstance(lst, list):
                for row in lst:
                    if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                        names.append(str(row[0]).strip())
        return names
    except Exception:
        return []


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
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
        v = dh.cached('m1_surge', sec, float(BLS.get('m1_surge_cache_ttl', 15.0)),
                      lambda: _calc_1m_surge(sec))
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


def _role_tolerance(sec):
    # 按预期 sell_policy_hint 缩放卖出容忍度（AXquant 地位角色迁移，docs/17）；缺省 none=一律基础
    en = g.exp_file.get(sec) or {}
    e = g.exp.get(sec) or {}
    hint = str(e.get('sell_policy_hint') or en.get('sell_policy_hint') or 'none')
    tbl = BLS.get('sell_policy', {})
    return tbl.get(hint) or tbl.get('none') or {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}


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
            _do_sell(context, sec, amt, 'P2E_exp_miss ' + _est, urgent=True); continue
        if cost > 0:
            pnl_pct = px / cost - 1.0
            if pnl_pct <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss pnl=%.1f%%' % (pnl_pct * 100), urgent=True); continue
        # P4 预期三态：普通标的竞价/逆势，一字板封单，docs/17
        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word':
                st, _r = _exp_one_word(sec)
                if st == CS or st == PS:
                    _do_sell(context, sec, amt, 'P4_exp_one_word ' + st); continue
            else:
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
        g.l2_probed = True
    except Exception as e:
        log.warn('l2 probe fail: %r' % e)

def _tick_targets():
    # tick 采集目标：持仓 + universe 恒有 + watch 前 N（控 3s 帧负担，避免丢帧）
    pos = list(get_positions())
    uni = [x for x in BLS['universe'] if x not in pos]
    static = [x for x in (g.pool_static or []) if x not in pos and x not in uni]
    cap = int(BLS.get('tick_watch_cap', 15))
    watch = [x for x in (g.watch or []) if x not in pos and x not in uni and x not in static][:cap]
    return pos + uni + static + watch


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


def _tx_first_zt_ms(sec):
    # 单标逐笔拉取（兼容入口；v0.22 起 tick 主路径走 DataHub.tx_zt_batch 批量）
    try:
        dh = getattr(g, 'ds', None)
        if dh is None:
            dh = g.ds = DataHub()
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
    _dh = getattr(g, 'ds', None)
    if _dh is None:
        _dh = g.ds = DataHub()
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
                        log.warn('first_board_buy fail %r' % _e)
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
                        log.warn('first_board_buy fail %r' % _e)
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
    # v0.13：3s 帧末统一评估预期买入（竞价超预期/快速上攻/封单超预期 -> 立买；走弱 -> 放弃）
    if BLS.get('tick_exp_enabled', True):
        try:
            _try_expected_buys(context)
        except Exception as e:
            log.warn('tick exp buy fail: %r' % e)
    # v0.19 弹性套利：3s 帧末评估（09:30-09:40，板块一字>=2 抓 20cm）
    try:
        _try_elastic_arb_buy(context)
    except Exception as e:
        log.warn('elastic_arb buy fail: %r' % e)


def auction_pre_confirm(context):
    # 09:25 竞价终态：重读 9:20 定时上传的预期前瞻文件，对 side=buy 做「竞价超预期初步确认 -> 观察」节奏。
    # 时机说明：before_trading_start(~9:10) 早于上传点，须在此重读当日文件才命中；观察不买，等分时(9:30+)确认。
    _set_now(context)
    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) != day:
        g.exp_day = day
    _load_expectation()          # 幂等重读：命中 9:20 上传的当日文件
    _load_zt_lianban()
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    for code in list(get_positions()):
        g.exp.setdefault(code, {})
        g.exp[code]['auction_status'] = _eval_auction(code)[0]
    for code in (g.exp_file or {}):
        if str((g.exp_file[code] or {}).get('side') or '') != 'buy':
            continue
        try:
            st, reason = _exp_rt_status(code)
        except Exception as e:
            log.warn('auction_pre_confirm %s fail %r' % (_sn(code), e)); continue
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
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    g.exp_day = str(get_trading_day()); g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set()
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


def place_order(context, sec, side, qty=None, note='', mode='chase', ratio=None):
    positions = context.portfolio.positions
    if side == 'buy':
        limit = _order_limit(sec, side, mode)
        px = limit or last_px(sec) or 0.0
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
        if px <= 0 or cash <= 0:
            log.warn('place_order skip(no px/cash) %s' % _sn(sec)); return
        qty = _calc_buy_qty(context, sec, px, float(ratio) if ratio else float(BLS.get('ordinary_buy_ratio', 0.10)))
        if qty <= 0:
            log.warn('place_order skip(qty<=0) %s' % _sn(sec)); return
    else:
        limit = _order_limit(sec, side, mode)
        if qty is None:
            qty = int(getattr(positions.get(sec), 'amount', 0) or 0)
    if not qty or qty <= 0:
        log.warn('place_order skip qty<=0 %s' % _sn(sec)); return
    if not BLS['DO_ORDER']:
        log.info('[may-order] %s %s qty=%s limit=%s %s (DO_ORDER=False)' % (_sn(sec), side, qty, limit, note))
        return
    try:
        ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
        g.pending[sec] = {'no': ent, 'side': side, 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0, 'ts': time.time()}
        log.info('order sent %s %s qty=%s limit=%s ent=%s %s' % (_sn(sec), side, qty, limit, ent, note))
    except Exception as e:
        log.error('order fail %s: %r' % (_sn(sec), e))


def place_expected_order(context, sec, note=''):
    # 预期买入独立下单门控（EXPECT_ORDER）：仅此路径可在 DO_ORDER=False 时发真实单（模拟盘小额测试）
    s = g.spot.get(sec) or {}
    px = last_px(sec) or 0.0
    up = float(s.get('up_px') or 0.0) if s else 0.0
    cash = float(getattr(context.portfolio, 'cash', 0) or 0)
    if px <= 0 or cash <= 0:
        log.warn('exp order skip(no px/cash) %s' % _sn(sec))
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
        log.warn('exp order skip(qty<=0) %s' % _sn(sec))
        return False
    if BLS.get('EXPECT_ORDER', False):
        try:
            ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
            g.pending[sec] = {'no': ent, 'side': 'buy', 'qty': qty, 'limit': limit}
            log.info('[exp-order] %s buy qty=%s limit=%s ent=%s %s (EXPECT_ORDER=True)' % (_sn(sec), qty, limit, ent, note))
            return True
        except Exception as e:
            log.error('exp order fail %s: %r' % (_sn(sec), e))
            return False
    log.info('[exp-order] %s buy qty=%s limit=%s %s (EXPECT_ORDER=False)' % (_sn(sec), qty, limit, note))
    return True


def on_order_response(context, order):
    # 订单回报：回填 pending 状态；拒绝/撤单即释放在途锁, 允许下帧重试
    try:
        ent = getattr(order, 'entrust_no', None) or getattr(order, 'order_id', None)
        st = getattr(order, 'order_status', None) or getattr(order, 'status', None) or 'SENT'
        if ent is not None:
            for _sec, _p in (getattr(g, 'pending', None) or {}).items():
                if str(_p.get('no') or '') == str(ent):
                    _p['status'] = str(st)
                    if str(st).upper() in ('FILLED', 'CANCELLED', 'REJECTED'):
                        _p['filled'] = int(_p.get('qty') or 0)   # 终态不再在途
                    break
        log.info('on_order_response %s status=%s' % (ent, st))
    except Exception as e:
        log.warn('on_order_response err %r' % e)


def on_trade_response(context, trade):
    # 成交回报：回填 pending 已成交量、按成交释放去重并记 daily.sold（成交驱动的持仓对账）
    try:
        code = (getattr(trade, 'ticker', None) or getattr(trade, 'code', None)
                or getattr(trade, 'sec', None) or getattr(trade, 'stock_code', None)
                or getattr(trade, 'symbol', None))
        code = _norm_sec(code)
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
    except Exception as e:
        log.warn('on_trade_response err %r' % e)


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
        else:
            g.auction_c = getattr(g, 'auction_c', None) or {}
            g.first_zt = getattr(g, 'first_zt', None) or {}
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
                         'first_zt_day': _today}, f, protocol=2)
    except Exception as e:
        log.warn('save_state fail %r' % e)


def after_trading_end(context, data):
    _save_state()
    log.info('buysell_core end bought=%s sold=%s' % (_snl(g.daily.get('bought')), _snl(g.daily.get('sold'))))
