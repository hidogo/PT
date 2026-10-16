# -*- coding: utf-8 -*-
# buysell_core —— Ptrade 托管「高可靠买卖子集」迁移骨架（v0.4）
# 依据：docs/16 + docs/18；AXquant 真实参数取自 D:/PROJ/AXquant/axquant/strategy
#   (decision/sell.py, decision/__init__.py, scorer/*, btree/builder.py ma_pullback)
# v0.4 把 score_now 做成真实版（结构等价，数据用 Ptrade 内置接口近似）：
#   分 = clamp(base40 + 静态加分 - 静态扣分 + 攻击加分 - VWAP扣分 + 外内盘, 0..92)
# 兼容国金：run_daily(context,func)+回调单参；log 先 % 拼单字符串；禁用 os。
# 只读安全：DO_ORDER=False 不发真单，仅记 [may-order]。
import time, pickle, csv


# ---------- 参数 ----------
BLS = {
    'DO_ORDER': False,
    'universe': ['600570.XSHG', '603528.XSHG', '601188.XSHG'],   # 占位自选池，待接全市场扫描
    'buy_score_min': 55.0, 'auction_buy_score_min': 50.0,
    'ma5_pullback': True, 'ma5_loose_high': 1.02,
    'cold_secs': 60, 'daily_max_buy': 1,
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
    'seal_fail_ratio': 0.333,       # 封单衰竭：<= 基准*(1/3) -> 卖
    # 预期文件（AXquant 竞价终态 csv，docs/25）
    'expectation_base': 'data/expectation_',
    'expectation_suffix': '.csv',
    'scan_interval': 4,             # 每 N 根 bar 触发一次全市场扫描
    'score_sell_clear': 30, 'score_sell_half': 50,
    # 止损按板块
    'stop_loss_pct': 0.05, 'stop_loss_chinext': 0.07, 'stop_loss_star': 0.08, 'stop_loss_bse': 0.10,
    # 打分引擎（AXquant 默认）
    'score_base': 40, 'score_max': 92, 'score_min': 0,
    'vwap_penalty_per_min': 1.0, 'vwap_daily_limit': 12,
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


def initialize(context):
    set_universe(BLS['universe'])
    g.buy_log = {}; g.sold_log = {}
    g.daily = {'bought': [], 'sold': []}
    g.state_day = None   # 持久化的“交易日”戳（跨重启每日买入计数恢复）
    g.spot = {}; g.last_ma5 = {}
    g.hist = {}         # sec -> (ts, df)  1d 历史缓存
    g.bs_cache = {}     # sec -> (ts, board_strength)
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
    g.exp_file = {}     # sec -> 预期文件条目（AXquant 竞价终态）
    run_daily(context, after_open_probe, time='09:31')
    run_daily(context, mid_probe, time='11:00')
    log.info('buysell_core init universe=%s DO_ORDER=%s' % (BLS['universe'], BLS['DO_ORDER']))


def before_trading_start(context, data):
    _set_now(context)
    load_state()
    _today = str(get_trading_day())
    if getattr(g, 'state_day', None) == _today:
        # 同日盘中重启：保留当日已买计数（跨重启恢复），sold 本就每日清
        g.daily = {'bought': [x for x in (g.daily.get('bought') or [])], 'sold': []}
        log.info('before_trading_start restore same-day daily=%s (restart)' % (g.daily.get('bought'),))
    else:
        g.daily = {'bought': [], 'sold': []}
    g.state_day = _today
    _save_state()
    _load_expectation()
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    for sec in list(dict.fromkeys(BLS['universe'] + list(get_positions()))):
        df = _hist_1d(sec)
        if df is not None and len(df) >= 6:
            g.last_ma5[sec] = float(df['close'].iloc[:-1].mean())
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
        g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}
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


# ================= 行情/工具 =================
def _hist_1d(sec):
    # 1d OHLCV 缓存（约 60s 有效）
    h = g.hist.get(sec)
    if h and (time.time() - h[0]) < 60:
        return h[1]
    try:
        df = get_price(sec, start_date=None, end_date=None, count=120, frequency='1d')
        g.hist[sec] = (time.time(), df)
        return df
    except Exception:
        return h[1] if h else None


def _ensure_ma5(sec):
    # 惰性算 MA5（watch/盘中入池才需要；1d 历史缓存，60s 内复用）
    if sec in g.last_ma5:
        return g.last_ma5[sec]
    df = _hist_1d(sec)
    if df is not None and len(df) >= 6:
        v = float(df['close'].iloc[:-1].mean())
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
    p = positions.get(sec)
    c = getattr(p, 'cost_basis', None)
    if c is None and isinstance(p, dict):
        c = p.get('cost_basis')
    return float(c or 0.0)


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
            sec, base, bonus, penalty, atk, vp, ei, raw))
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


def _limitup_days(sec):
    # 连续涨停天数（近似：收盘较前收 == 0.098）——从 1d 历史倒推
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
    # 量比：今日量 / 前5日均量（用 1d 历史 volume 近似）
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

def _seal_metrics(sec):
    # 实时封单（L2）：十档买一挂单金额 + 买一委托笔数（仅交易；回测返回 (0.0, 0)）
    try:
        gp = get_gear_price(sec) or {}
        b = (gp.get("bid_grp") or {}).get(1) or [0, 0, 0]
        amt = float(b[1] or 0.0)
        cnt = int(b[2] or 0)
        return amt, cnt
    except Exception:
        return 0.0, 0

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
    yopen = float(e.get("yesterday_open_pct") or 0.0)
    if chg < 0:
        return PS, ["auction_green_open"]
    if yopen > 0 and chg > yopen:
        return PX, ["auction_higher_than_yesterday"]
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
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d bid_fail=%s -> CS" % (sec, seal, base, ratio, bids, bbase, bid_fail))
        return CS, ["seal_fail"]
    if ratio >= float(BLS["seal_exceed_ratio"]):
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CX" % (sec, seal, base, ratio, bids))
        return CX, ["seal_increase"]
    log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CM" % (sec, seal, base, ratio, bids))
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


def _board_strength(sec):
    # 板块强度：取所属板块成员实时涨跌均值(缓存60s)。
    # 注：不做 get_sort_msg(该券商签名不适配会刷 ERROR)，统一走板块代码取成员。
    c = g.bs_cache.get(sec)
    if c and (time.time() - c[0]) < 60:
        return c[1]
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
        val = _board_strength_by_members(board_code) if board_code else 0.0
    except Exception:
        val = 0.0
    return _set_bs(sec, val)

def _board_strength_by_members(board_code):
    # 板块成员实时涨跌均值（用板块代码取成分股；失败返回0）
    try:
        mem = list(get_industry_stocks(str(board_code)) or [])[:20]
        if not mem:
            return 0.0
        chgs = []
        for m in mem:
            try:
                sn = get_snapshot(m) or {}
                d = sn.get(m) or {}
                pre = float(d.get('preclose_px') or 0.0)
                px = float(d.get('last_px') or 0.0)
                if pre > 0:
                    chgs.append(px / pre - 1.0)
            except Exception:
                continue
        return (sum(chgs) / len(chgs)) * 100.0 if chgs else 0.0
    except Exception:
        return 0.0
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
                sec, _hhmm(), px if px else 0.0, ma5, chg, st, tags, sc))
        except Exception as e:
            log.warn('dump_scores fail %s: %r' % (sec, e))


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

def _selfwatch_paths():
    base = get_research_path()
    return [base + 'selfwatch.csv', base + 'data/selfwatch.csv']


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
    buy_codes.sort(key=lambda c: 0 if str((getattr(g, 'exp_file', {}).get(c) or {}).get('expected_status') or '').startswith('exceed') else 1)
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
    # 候选：研究根目录优先，data/ 兜底（研究目录为云端，见 get_research_path）
    day = str(get_trading_day())
    base = get_research_path()
    suf = BLS.get("expectation_suffix", ".csv")
    return [
        base + "expectation_" + day + suf,
        base + "data/expectation_" + day + suf,
    ]

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
            g.exp_file[code] = {
                "side": (rec.get("side") or "hold").strip(),
                "entry_type": (rec.get("entry_type") or "normal").strip(),
                "expected_status": (rec.get("expected_status") or "").strip(),
                "yesterday_open_pct": _fnum(rec.get("yesterday_open_pct")),
                "expected_auction_change_pct": _fnum(rec.get("expected_auction_change_pct")),
                "seal_amount_t0": _fnum(rec.get("seal_amount_t0")),
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

def _confirm_expected(code):
    # 用真实竞价(get_trend_data)确认预期命中：exceed/meet/miss
    en = g.exp_file.get(code) or {}
    actual = _auction_change(code)   # 真实竞价涨幅%（标准函数）
    exp_status = en.get("expected_status") or ""
    exp_auc = float(en.get("expected_auction_change_pct") or 0.0)
    if exp_status.startswith("exceed"):
        return (CX if actual >= exp_auc else PM), actual
    if exp_status.startswith("miss"):
        return (CS if actual < 0 else PM), actual
    return PM, actual   # meet/未标注 -> 等盘中确认

def _try_expected_buys(context):
    # 预期文件里 side=buy 且竞价确认未 miss -> 按现有买入通道执行
    if not g.exp_file or len(g.daily["bought"]) >= BLS["daily_max_buy"]:
        return
    positions = context.portfolio.positions
    for code, en in g.exp_file.items():
        if code in positions or str(en.get("side") or "") != "buy":
            continue
        st, actual = _confirm_expected(code)
        if st != CS:   # CX 超预期确认/CM 符合/PM 待定都买；仅排除确认 miss
            g.exp.setdefault(code, {})["auction_status"] = st
            place_order(context, code, "buy", note="expect_buy %s auction=%.1f%%" % (st, actual))
            g.daily["bought"].append(code)
            _save_state()
        if len(g.daily["bought"]) >= BLS["daily_max_buy"]:
            break

# ================= 买入 =================
def try_ma5_buy(context):
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        px = last_px(sec); ma5 = _ensure_ma5(sec)
        if not px or px <= 0 or not ma5:
            continue
        if px <= ma5 * BLS['ma5_loose_high']:
            score = score_now(sec)
            if score >= BLS['buy_score_min']:
                place_order(context, sec, 'buy', note='ma_pullback px=%.2f ma5=%.2f score=%.1f' % (px, ma5, score))
                g.daily['bought'].append(sec); g.buy_log[sec] = now
                _save_state()
            if len(g.daily['bought']) >= BLS['daily_max_buy']:
                break


def try_core_buy(context):
    pass    # 核心票：score>=min 且连板<6（tag CORE 已并入打分），涨幅/热度门禁待接


# ================= 卖出（P1绿开>P3止损>P5/P6分数） =================
def sell_manager(context):
    positions = context.portfolio.positions
    for sec in list(positions.keys()):
        px = last_px(sec); cost = my_cost(sec, positions)
        if not px or px <= 0:
            continue
        amt = int(getattr(positions[sec], 'amount', 0) or 0)
        if amt <= 0:
            continue
        if _auction_change(sec) <= BLS['green_open_drop']:
            place_order(context, sec, 'sell', qty=amt, note='P1_green_open drop=%.1f%%' % _auction_change(sec)); continue
        if cost > 0:
            pnl_pct = px / cost - 1.0
            if pnl_pct <= -get_stop_loss_pct(sec):
                place_order(context, sec, 'sell', qty=amt, note='P3_stop_loss pnl=%.1f%%' % (pnl_pct * 100)); continue
        # P4 预期三态：普通标的竞价/逆势，一字板封单，docs/17
        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word':
                st, _r = _exp_one_word(sec)
                if st == CS or st == PS:
                    place_order(context, sec, 'sell', qty=amt, note='P4_exp_one_word ' + st); continue
            else:
                au = g.exp[sec].get('auction_status') or _eval_auction(sec)[0]
                st = _eval_intraday(sec, au)[0]
                if st in (PS, CS):
                    place_order(context, sec, 'sell', qty=amt, note='P4_exp_miss ' + st); continue
        _en = g.exp_file.get(sec) or {}
        if str(_en.get('side') or '') == 'sell':
            _eun, _ea2 = _confirm_expected(sec)
            if _eun == CS:
                place_order(context, sec, 'sell', qty=amt, note='P4_exp_sell ' + _eun); continue
        sc = score_now(sec)
        if sc < BLS['score_sell_clear']:
            place_order(context, sec, 'sell', qty=amt, note='P5_score_clear score=%.1f' % sc)
        elif sc < BLS['score_sell_half']:
            place_order(context, sec, 'sell', qty=max(amt // 2, 1), note='P6_score_half score=%.1f' % sc)


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
        ok = 'L2_OK' if (n_tx or n_ent or bid_cnt) else 'L2_NONE'
        log.info('[l2] code=%s tx=%d entrust=%d gear_bid_cnt=%d -> %s' % (sec, n_tx, n_ent, bid_cnt, ok))
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


def tick_data(context, data):
    # 仅交易，9:30-14:59 每 3s 一次。L2 涨停首笔成交感知 + 封单/破板节奏。
    # 只采集状态与 [firstzt] 日志，下单仍走 1m handle_data（采集/决策解耦）。
    if not BLS.get('tick_enabled', True):
        return
    for sec in _tick_targets():
        try:
            sn = get_snapshot(sec) or {}
            s = sn.get(sec) or {}
            g.spot[sec] = s                     # 顺带刷新 1m 打分用的快照
            last = float(s.get('last_px') or 0.0)
            u = float(s.get('up_px') or 0.0)
            if last <= 0 or u <= 0:
                continue
            seal, bids = _seal_metrics(sec)
            ft = g.first_zt.get(sec)
            if ft is None:
                if last >= u - 1e-9:            # 首次触板
                    vol = _snap_vol(s)
                    amt = float(s.get('turnover') or s.get('amount') or 0.0)
                    ms = s.get('hsTimeStamp') or 0   # 快照毫秒时间戳，精确还原触板时刻
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False}
                    log.info('[firstzt] %s price=%.2f vol=%.0f ms=%s seal=%.0f bids=%d state=first' % (sec, last, vol, ms, seal, bids))
                continue
            if last < u - 1e-9:                 # 破板
                if not ft.get('break'):
                    ft['break'] = True; ft['break_ts'] = time.time()
                    log.info('[firstzt] %s price=%.2f -> BREAK seal=%.0f held=%.0fs' % (sec, last, seal, time.time() - ft.get('ts', time.time())))
                continue
            fs = ft.get('first_seal') or 0.0    # 封单衰竭（相对首封）
            if fs > 0 and seal < fs * float(BLS.get('seal_fail_ratio', 0.333)):
                if not ft.get('seal_low'):
                    ft['seal_low'] = True
                    log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW' % (sec, seal, fs, seal / fs, bids))
        except Exception:
            continue


def after_open_probe(context):
    _set_now(context)
    log.info('after_open_probe 09:31')
    g.exp_day = str(get_trading_day()); g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}
    for sec in list(get_positions()):
        g.exp.setdefault(sec, {})
        au, _r = _eval_auction(sec)
        g.exp[sec]['auction_status'] = au
        _en = g.exp_file.get(sec) or {}
        for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct', 'seal_amount_t0'):
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
def place_order(context, sec, side, qty=None, note=''):
    positions = context.portfolio.positions
    if side == 'buy':
        px = last_px(sec) or 0.0
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
        if px <= 0 or cash <= 0:
            log.warn('place_order skip(no px/cash) %s' % sec); return
        qty = int((cash * 0.3) / (px * 100)) * 100 or 100
    else:
        if qty is None:
            qty = int(getattr(positions.get(sec), 'amount', 0) or 0)
    if not qty or qty <= 0:
        log.warn('place_order skip qty<=0 %s' % sec); return
    if not BLS['DO_ORDER']:
        log.info('[may-order] %s %s qty=%s %s (DO_ORDER=False)' % (sec, side, qty, note))
        return
    try:
        ent = order(sec, qty, side)
        g.pending[sec] = {'no': ent, 'side': side, 'qty': qty}
        log.info('order sent %s %s qty=%s ent=%s %s' % (sec, side, qty, ent, note))
    except Exception as e:
        log.error('order fail %s: %r' % (sec, e))


def on_order_response(context, order):
    log.info('on_order_response %s status=%s' % (getattr(order, 'entrust_no', '?'), getattr(order, 'order_status', '?')))


def on_trade_response(context, trade):
    log.info('on_trade_response %s' % trade)


# ================= 持久化（无 os 依赖） =================
def state_fp():
    return get_research_path() + 'buysell_core_state.pkl'


def load_state():
    try:
        with open(state_fp(), 'rb') as f:
            st = pickle.load(f)
        g.buy_log = st.get('buy_log', {}); g.sold_log = st.get('sold_log', {})
        g.daily = st.get('daily', {'bought': [], 'sold': []})
        g.state_day = st.get('day')
    except Exception:
        g.buy_log = {}; g.sold_log = {}
        g.daily = {'bought': [], 'sold': []}; g.state_day = None


def _save_state():
    # 写入 buy_log/sold_log（冷却）+ daily 每日计数 + day 戳（跨重启恢复）
    try:
        if not getattr(g, 'state_day', None):
            g.state_day = str(get_trading_day())
        with open(state_fp(), 'wb') as f:
            pickle.dump({'buy_log': g.buy_log, 'sold_log': g.sold_log,
                         'daily': g.daily, 'day': getattr(g, 'state_day', None)}, f, protocol=2)
    except Exception as e:
        log.warn('save_state fail %r' % e)


def after_trading_end(context, data):
    _save_state()
    log.info('buysell_core end bought=%s sold=%s' % (g.daily.get('bought'), g.daily.get('sold')))
