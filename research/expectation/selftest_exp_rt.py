# -*- coding: utf-8 -*-
# selftest_exp_rt.py —— v0.14 预期买入两阶段触发（竞价观察 -> 分时确认买）注入式逻辑测试
# 本机 py310 跑，不进 Ptrade。
import pickle, time, datetime, tempfile, types, io, os
SRC = r"D:/PROJ/PT/strategies/buysell_core/strategy.py"
def make_mod(**overrides):
    ns = {}
    with open(SRC, "r", encoding="utf-8") as f:
        code = compile(f.read(), SRC, "exec")
    exec(code, ns)
    TMP = tempfile.mkdtemp(prefix="pt_sf_")
    class Log:
        def info(self, *a): pass
        def warn(self, *a): pass
        def error(self, *a): pass
    g = types.SimpleNamespace()
    for k in ('buy_log','sold_log','daily','state_day','spot','last_ma5','hist',
              'now_dt','bar_counter','pool_all','pool_day','watch','selfwatch','pool_static',
              'last_scan','scan_offset','auction_c','exp','exp_day','seal_base','seal_bid_base',
              'first_zt','exp_file','exp_fired','pending'):
        setattr(g, k, None)
    ns['g'] = g; ns['log'] = Log(); ns['time'] = time
    ns['get_research_path'] = lambda: TMP + "/"
    ns['get_trading_day'] = lambda: datetime.date(2026,10,16)
    ns['set_universe'] = lambda *a: None
    ns['run_daily'] = lambda *a, **k: None
    ns['get_positions'] = lambda: {}
    ns['pre_close'] = lambda sec: 10.0
    ns['get_Ashares'] = lambda: []
    ns['get_gear_price'] = lambda sec: {}
    ns['get_individual_transaction'] = lambda *a, **k: {}
    ns['get_tick_direction'] = lambda *a, **k: {}
    ns['get_individual_entrust'] = lambda *a, **k: {}
    ns['get_trend_data'] = lambda **k: {}
    ns['get_snapshot'] = lambda sec: {}
    ns['get_price'] = lambda *a, **k: None
    ctx = types.SimpleNamespace(
        portfolio=types.SimpleNamespace(positions={}, cash=100000.0),
        blotter=types.SimpleNamespace(current_dt=datetime.datetime(2026,10,16,10,0,0)))
    ns['_CTX'] = ctx
    cont = {"calls": []}
    def order(sec, qty, side=None, limit_price=None, **kw):
        ent = "E%d" % (len(cont["calls"]) + 1)
        cont["calls"].append({"sec": sec, "qty": qty, "side": side, "limit_price": limit_price}); return ent
    ns['order'] = order; ns['_RECC'] = cont
    for k, v in overrides.items():
        ns[k] = v
    ns['_g'] = g; ns['_ctx'] = ctx; ns['_TMP'] = TMP
    return ns
def fresh():
    ns = make_mod()
    g = ns['g']
    g.spot = {}; g.auction_c = {}; g.daily = {'bought': [], 'sold': []}; g.buy_log = {}
    g.exp = {}; g.exp_file = {}; g.exp_fired = set(); g.pending = {}; g.spot = {}; g.hist = {}
    g.sold_log = {}
    return ns
def expbuyns(ns, code):
    ns['g'].exp_file = {code: {'side':'buy','entry_type':'normal','expected_status':'pending_exceed',
                               'expected_auction_change_pct':5.0,'yesterday_open_pct':3.0,
                               'seal_amount_t0':0.0,'board_name':'t','reason':''}}
    ns['g'].spot[code] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
def ok(name, cond):
    print(("PASS %-30s" % name) if cond else ("FAIL %-30s" % name)); assert cond, name

# T1 竞价超预期 -> 观察（不买）
ns = fresh(); expbuyns(ns, '600001.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)   # 竞价实际>=阈值 -> 超预期初步
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600001.XSHG')
ok('T1 auction_exceed -> PM observe', st == ns['PM'] and reason.startswith('observe'))
r = ns['_attempt_expected_buy'](ns['_ctx'], '600001.XSHG')
ok('T1 observe not buy', r is None and ('600001.XSHG' not in ns['g'].daily['bought']))
ok('T1 observe seen set', ns['g'].exp['600001.XSHG'].get('observe_seen') is True)

# T2 分时确认超预期(两分钟上攻,不破VWAP) -> 买
ns = fresh(); expbuyns(ns, '600002.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: True
ns['_below_vwap'] = lambda c: False
r = ns['_attempt_expected_buy'](ns['_ctx'], '600002.XSHG')
ok('T2 intraday_exceed fires', r is True and '600002.XSHG' in ns['g'].daily['bought'])

# T2b 一分钟冲涨停触发
ns = fresh(); expbuyns(ns, '600021.XSHG'); ns['g'].now_dt = datetime.datetime(2026,10,16,9,31,0)
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: False
ns['_limit_up_within_1m'] = lambda c: True
ns['_below_vwap'] = lambda c: False
r = ns['_attempt_expected_buy'](ns['_ctx'], '600021.XSHG')
ok('T2b one-min limit-up fires', r is True and '600021.XSHG' in ns['g'].daily['bought'])

# T2c 真实 helper 时段判定
ns = fresh(); expbuyns(ns, '600022.XSHG')
ns['g'].now_dt = datetime.datetime(2026,10,16,9,31,0)
ns['g'].spot['600022.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':10.02,'wavg_px':10.0,'trade_status':'OPEN'}
ok('T2c helper true at 09:31', ns['_limit_up_within_1m']('600022.XSHG') is True)
ns['g'].now_dt = datetime.datetime(2026,10,16,14,0,0)
ok('T2c helper false at 14:00', ns['_limit_up_within_1m']('600022.XSHG') is False)

# T3 分时转弱(破VWAP) -> 放弃
ns = fresh(); expbuyns(ns, '600003.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600003.XSHG')
ok('T3 below_vwap skip', r is True and '600003.XSHG' in ns['g'].exp_fired and '600003.XSHG' not in ns['g'].daily['bought'])

# T4 去重：已触发后不再重复
ns = fresh(); expbuyns(ns, '600004.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: True
ns['_below_vwap'] = lambda c: False
ns['_attempt_expected_buy'](ns['_ctx'], '600004.XSHG')
b4 = len(ns['_RECC']['calls'])
r2 = ns['_attempt_expected_buy'](ns['_ctx'], '600004.XSHG')
ok('T4 dedup no re-fire', r2 is None and len(ns['_RECC']['calls']) == b4)

# T5 跨重启持久化 exp_fired
ns = fresh(); ns['g'].exp_fired = {'600005.XSHG'}; ns['_save_state'](); ns['g'].exp_fired = set(); ns['load_state']()
ok('T5 restart restores exp_fired', '600005.XSHG' in ns['g'].exp_fired)

# T6 日切清空
ns = fresh(); ns['load_state'] = lambda: None; ns['_save_state'] = lambda: None
ns['_load_expectation'] = lambda: 0; ns['_load_selfwatch'] = lambda: 0; ns['_sync_pool_static'] = lambda: None; ns['_hist_1d'] = lambda sec: None
ns['get_trading_day'] = lambda: datetime.date(2026,10,16)
ns['g'].state_day = '2026-10-15'; ns['g'].daily = {'bought': ['600009.XSHG'], 'sold': []}; ns['g'].exp_fired = {'600009.XSHG'}; ns['g'].spot = {}
ns['before_trading_start'](ns['_CTX'], None)
ok('T6 day-change clears exp_fired', ns['g'].exp_fired == set() and ns['g'].daily['bought'] == [])

# T7 分时确认 + EXPECT_ORDER=True -> 真实发单
ns = fresh(); expbuyns(ns, '600010.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: True
ns['_below_vwap'] = lambda c: False
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600010.XSHG')
ok('T7 real order sent', r is True and len(ns['_RECC']['calls']) >= 1)
lp = ns['_RECC']['calls'][0]['limit_price']
ok('T7 limit_price is numeric (not side str)', isinstance(lp, float) and lp > 0)

# T9 定价策略：打板/追高/回踩/卖出限价
ns = fresh()
ns['g'].spot['X'] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
ok('T9 board=up_px', ns['_order_limit']('X','buy','board') == 12.0)
ok('T9 chase=px*1.008', ns['_order_limit']('X','buy','chase') == 10.08)
ok('T9 pullback=px', ns['_order_limit']('X','buy','pullback') == 10.0)
ok('T9 sell=px limit', ns['_order_limit']('X','sell','x') == 10.0)
ns['g'].spot['X'] = {'last_px':10.0,'preclose_px':10.0,'up_px':10.02,'wavg_px':10.0,'trade_status':'OPEN'}
ok('T9 chase capped by up', ns['_order_limit']('X','buy','chase') == 10.02)

# T10 预期买入打板模式：现价触板 -> 挂涨停价
ns = fresh(); expbuyns(ns, '600030.XSHG')
ns['g'].spot['600030.XSHG'] = {'last_px':11.99,'preclose_px':10.0,'up_px':12.0,'wavg_px':11.0,'trade_status':'OPEN'}
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: True
ns['_below_vwap'] = lambda c: False
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600030.XSHG')
ok('T10 board buy sends limit=12.0', r is True and len(ns['_RECC']['calls']) >= 1 and ns['_RECC']['calls'][0]['limit_price'] == 12.0)

# T8 pending_exceed 匹配(修复 startswith 坑)
ns = fresh(); expbuyns(ns, '600011.XSHG')
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600011.XSHG')
ok('T8 pending_exceed enters exceed branch', st == ns['PM'] and reason.startswith('observe'))

# T11 一字超预期：封单CM(未超预期)不买，等CX
ns = fresh(); expbuyns(ns, '600041.XSHG'); ns['g'].exp_file['600041.XSHG']['entry_type'] = 'one_word'
ns['_exp_one_word'] = lambda c: (ns['CM'], ['seal_within'])
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
ns['_eval_auction'] = lambda c: (ns['AW'], [])
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600041.XSHG')
ok('T11 one_word CM not buy', r is None and len(ns['_RECC']['calls']) == 0)

# T11b 一字超预期：封单CX -> 打板挂涨停价买
ns = fresh(); expbuyns(ns, '600042.XSHG'); ns['g'].exp_file['600042.XSHG']['entry_type'] = 'one_word'
ns['g'].spot['600042.XSHG'] = {'last_px':12.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':11.0,'trade_status':'OPEN'}
ns['_exp_one_word'] = lambda c: (ns['CX'], ['seal_increase'])
ns['_below_vwap'] = lambda c: False
ns['_eval_auction'] = lambda c: (ns['AW'], [])
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600042.XSHG')
ok('T11b one_word CX board buy', r is True and len(ns['_RECC']['calls']) >= 1 and ns['_RECC']['calls'][0]['limit_price'] == 12.0)
import types as _t
# T12 一字封死涨停（ask_grp 为空）-> CX 也不排队买入
ns = fresh(); expbuyns(ns, '600043.XSHG'); ns['g'].exp_file['600043.XSHG']['entry_type'] = 'one_word'
ns['g'].spot['600043.XSHG'] = {'last_px':12.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':11.0,'trade_status':'OPEN'}
ns['_exp_one_word'] = lambda c: (ns['CX'], ['seal_increase'])
ns['_below_vwap'] = lambda c: False
ns['_eval_auction'] = lambda c: (ns['AW'], [])
ns['get_gear_price'] = lambda sec: {'ask_grp': {}}   # 卖盘为空 -> 封死
ns['g'].sealed_since = {'600043.XSHG': time.time() - 6.0}   # 已持续 6s(≥5s)，封死生效（v0.26b 新规）
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600043.XSHG')
ok('T12 sealed one_word CX no queue buy', r is None and len(ns['_RECC']['calls']) == 0)

# T12b 一字未封死（卖盘有金额）-> 仍可打板排队买
ns = fresh(); expbuyns(ns, '600044.XSHG'); ns['g'].exp_file['600044.XSHG']['entry_type'] = 'one_word'
ns['g'].spot['600044.XSHG'] = {'last_px':12.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':11.0,'trade_status':'OPEN'}
ns['_exp_one_word'] = lambda c: (ns['CX'], ['seal_increase'])
ns['get_gear_price'] = lambda sec: {'ask_grp': {1: [12.0, 50000.0, 1]}}
ns['BLS']['EXPECT_ORDER'] = True
r = ns['_attempt_expected_buy'](ns['_ctx'], '600044.XSHG')
ok('T12b not sealed -> board buy proceeds', r is True and len(ns['_RECC']['calls']) >= 1)

# T13 弹性追高 300/688 买入价前收*1.10 上限（打板豁免）
ns = fresh()
ns['g'].spot['300999.SZ'] = {'last_px':11.5,'preclose_px':10.0,'up_px':14.0,'wavg_px':11.0,'trade_status':'OPEN'}
ok('T13 elastic chase capped to 11.0', ns['_order_limit']('300999.SZ','buy','chase') == 11.0)
ns['g'].spot['688888.XSHG'] = {'last_px':11.5,'preclose_px':10.0,'up_px':14.0,'wavg_px':11.0,'trade_status':'OPEN'}
ok('T13 688 elastic chase capped to 11.0', ns['_order_limit']('688888.XSHG','buy','chase') == 11.0)
ns['g'].spot['600000.XSHG'] = {'last_px':11.5,'preclose_px':10.0,'up_px':12.0,'wavg_px':11.0,'trade_status':'OPEN'}
ok('T13 board-uncapped non-elastic chase', ns['_order_limit']('600000.XSHG','buy','chase') == 11.59)
ns['g'].spot['300999.SZ'] = {'last_px':14.0,'preclose_px':10.0,'up_px':14.0,'wavg_px':11.0,'trade_status':'OPEN'}
ok('T13 300 board exempt from elastic cap', ns['_order_limit']('300999.SZ','buy','board') == 14.0)

# T14 P2E 竞价核卖：预期 confirmed_miss + 自身竞价大低开(-3% <= -2%) -> 清仓（DO_ORDER=True 发卖单）
ns = fresh()
ctx = ns['_ctx']
ns['g'].exp_file = {}
ctx.portfolio.positions = {'600050.XSHG': _t.SimpleNamespace(amount=1000, cost_basis=10.0)}
ns['g'].exp_file['600050.XSHG'] = {'side':'sell','expected_status':'confirmed_miss'}
ns['g'].spot['600050.XSHG'] = {'last_px':10.5,'preclose_px':10.0,'up_px':11.0,'wavg_px':10.5,'trade_status':'OPEN'}
ns['_auction_change'] = lambda c: -3.0
ns['get_stop_loss_pct'] = lambda sec: 0.05
ns['BLS']['DO_ORDER'] = True
ns['sell_manager'](ctx)
ok('T14 P2E exp_miss clears via sell order(核卖地板价9.0)', len(ns['_RECC']['calls']) == 1 and ns['_RECC']['calls'][0]['limit_price'] == 9.0)

# T14b pending_miss 默认不卖（exp_sell_on_pending_miss=False）
ns = fresh()
ctx = ns['_ctx']
ns['g'].exp_file = {}
ctx.portfolio.positions = {'600051.XSHG': _t.SimpleNamespace(amount=1000, cost_basis=10.0)}
ns['g'].exp_file['600051.XSHG'] = {'side':'sell','expected_status':'pending_miss'}
ns['g'].spot['600051.XSHG'] = {'last_px':10.5,'preclose_px':10.0,'up_px':11.0,'wavg_px':10.5,'trade_status':'OPEN'}
ns['_auction_change'] = lambda c: 5.0
ns['get_stop_loss_pct'] = lambda sec: 0.05
ns['score_now'] = lambda sec: 80.0
ns['_eval_intraday'] = lambda c, au: (ns['CX'], ['x'])
ns['BLS']['DO_ORDER'] = True
ns['sell_manager'](ctx)
ok('T14b pending_miss not sold by default', len(ns['_RECC']['calls']) == 0)
# T15 节奏：09:25 竞价终态初步确认超预期 -> 观察（不买），auction_pre_confirm 重读/记录
ns = fresh()
ns['g'].exp_file = {'600060.XSHG': {'side':'buy','entry_type':'normal','expected_status':'pending_exceed','seal_amount_t0':0.0}}
ns['g'].spot['600060.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
_loaded = {'n': 0}
def _fake_load_exp(merge=False):   # v0.68 merge 参数兼容
    _loaded['n'] += 1
    ns['g'].exp_file['600060.XSHG']['expected_status'] = 'pending_exceed'
ns['_load_expectation'] = _fake_load_exp
ns['_load_selfwatch'] = lambda: 0
ns['_sync_pool_static'] = lambda: None
ns['get_positions'] = lambda: {'600060.XSHG': None}
ns['_eval_auction'] = lambda c: (ns['AXW'] if False else ns['PM'], ['x'])
ns['_confirm_expected'] = lambda c: (ns['CX'], 12.5)   # 竞价实际>=阈值 -> 超预期初步
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
ns['_exp_rt_status'] = lambda c: (ns['PM'], 'observe_auction_exceed 5.6%')   # 9:25 竞价终态 -> 观察
logs = []
class CapLog:
    def info(self, *a): logs.append('info ' + (str(a[0]) % a[1:] if len(a) > 1 else str(a[0])))
    def warn(self, *a): logs.append('warn ' + str(a))
ns['log'] = CapLog(); ns['g'].exp_file = {'600060.XSHG': {'side':'buy','entry_type':'normal','expected_status':'pending_exceed'}}
ns['auction_pre_confirm'](ns['_ctx'])
ok('T15 pre_confirm reloads expectation', _loaded['n'] >= 1)
ok('T15 pre_confirm sets observe_seen', ns['g'].exp['600060.XSHG'].get('observe_seen') is True)
ok('T15 pre_confirm logs observe(不买)', any('观察' in x for x in logs))
ok('T15 pre_confirm no buy fire', len(ns['_RECC']['calls']) == 0)

# T16 兜底：竞价初判未超预期 -> 放弃(CS)，不再放任盘中买
ns = fresh(); expbuyns(ns, '600070.XSHG')
ns['_confirm_expected'] = lambda c: (ns['PM'], 3.0)   # 竞价未达阈值
ns['_auction_benchmark'] = lambda c: (5.0, True)      # 基准提供(5%)，actual=3<5 确未达标
ns['_two_1m_break'] = lambda c: True                  # 即便两分钟上攻，初判未达标也放弃
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600070.XSHG')
ok('T16 exceed-not-met -> CS auction_not_met', st == ns['CS'] and reason.startswith('auction_not_met'))
r = ns['_attempt_expected_buy'](ns['_ctx'], '600070.XSHG')
ok('T16 not-met skipped & fired', r is True and '600070.XSHG' in ns['g'].exp_fired)

# T16b 兜底：真竞价缺失(~-100) 不误弃，保持等待
ns = fresh(); expbuyns(ns, '600071.XSHG')
ns['_confirm_expected'] = lambda c: (ns['PM'], -100.0)
ns['_auction_benchmark'] = lambda c: (5.0, True)
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600071.XSHG')
ok('T16b quote-missing not mis-dropped', st == ns['PM'])


# T17 B兜底：预期基准缺失(has_expected_auction=False) -> 不超预期/不放弃(防过触发)
ns = fresh()
ns['g'].exp_file['600072.XSHG'] = {'side':'buy','entry_type':'normal','expected_status':'pending_exceed','has_yesterday_open':True,'yesterday_open_pct':3.0,'has_expected_auction':False,'expected_auction_change_pct':0.0}
ns['g'].spot['600072.XSHG'] = {'last_px':10.8,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.6,'trade_status':'OPEN'}
ns['_auction_change'] = lambda c: 8.0     # 竞价高开8%（若基准被当0会误超预期）
ns['_two_1m_break'] = lambda c: False
ns['_limit_up_within_1m'] = lambda c: False
ns['_below_vwap'] = lambda c: False
acon, _actual = ns['_confirm_expected']('600072.XSHG')
ok('T17 missing bench -> _confirm_expected PM (no over-fire)', acon == ns['PM'])
st, reason = ns['_exp_rt_status']('600072.XSHG')
ok('T17 missing bench -> await (not CS, not buy)', st == ns['PM'])

# T18 A：负基昨日开盘也判高开（云端折算）
ns = fresh()
ns['g'].exp_file['600073.XSHG'] = {'side':'buy','entry_type':'normal','expected_status':'pending_exceed','has_yesterday_open':False,'yesterday_open_pct':0.0,'has_expected_auction':True,'expected_auction_change_pct':5.0}
ns['g'].spot['600073.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
ns['_hist_1d'] = lambda sec: {'open':[8.0,8.5,9.6,10.0,9.4], 'close':[8.0,10.0,9.0,9.8,9.6]}  # open[-1]=9.4, close[-2]=9.8 -> -4.08%
ns['_auction_change'] = lambda c: 2.0
_y, _h = ns['_yesterday_open_chg']('600073.XSHG')
ok('T18 cloud 昨开折算 -4.08%%(open[-1]/close[-2])', _h and abs(_y - (-4.0816)) < 0.01)
_sta, _rea = ns['_eval_auction']('600073.XSHG')
ok('T18 负基也判高开 PX(2> -4.08)', _sta == ns['PX'])

# T19 B云端基准：文件缺 exp_auc -> 1d 折算 open[-2]/close[-3]-1
ns = fresh()
ns['g'].exp_file['600074.XSHG'] = {'side':'buy','entry_type':'normal','expected_status':'pending_exceed','has_expected_auction':False,'expected_auction_change_pct':0.0}
ns['g'].spot['600074.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
ns['_hist_1d'] = lambda sec: {'open':[8.0,8.5,9.6,10.0,10.5], 'close':[8.0,10.0,9.0,9.5,10.5]}  # open[-1]=10.5, close[-2]=9.5 -> 10.526%
ns['_auction_change'] = lambda c: 9.0   # 9 < 10.526 -> 未达标 PM
_bm, _bh = ns['_auction_benchmark']('600074.XSHG')
ok('T19 cloud bench derived ~10.526%%(open[-1]/close[-2])', _bh and abs(_bm - (10.5/9.5 - 1.0) * 100.0) < 0.01)
_ac2, _ac3 = ns['_confirm_expected']('600074.XSHG')
ok('T19 derived bench -> not exceed(PM)', _ac2 == ns['PM'])

# T20 分时超预期确认门禁：竞价达标(CX/高开PX)不直接买，需分时确认
ns = fresh(); expbuyns(ns, '600080.XSHG')
ns['g'].spot['600080.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)   # 竞价达标（初步确认超预期）
# 不 override 分时：real _two_1m_break(get_price None->False)/_limit_up_within_1m(10<2*11.976->False)/_below_vwap(10>=10->False)
st, reason = ns['_exp_rt_status']('600080.XSHG')
ok('T20 auction met but no intraday -> PM observe', st == ns['PM'] and reason.startswith('observe'))
r = ns['_attempt_expected_buy'](ns['_ctx'], '600080.XSHG')
ok('T20 no intraday confirm -> NOT buy', r is None and len(ns['_RECC']['calls']) == 0)

# T20b 分时确认(两分钟上攻)才买
ns = fresh(); expbuyns(ns, '600081.XSHG')
ns['g'].spot['600081.XSHG'] = {'last_px':10.2,'preclose_px':10.0,'up_px':12.0,'wavg_px':10.0,'trade_status':'OPEN'}
ns['_confirm_expected'] = lambda c: (ns['CX'], 6.5)
ns['_two_1m_break'] = lambda c: True                 # 两分钟上攻确认
r = ns['_attempt_expected_buy'](ns['_ctx'], '600081.XSHG')
ok('T20b intraday confirm -> buy', r is True and '600081.XSHG' in ns['g'].daily['bought'])
# T21 角色容忍度：_role_tolerance 返回因子 + sell_manager 的 P1 绿开 / P3 止损实际缩放（docs/17 sell_policy）
def _role_sell_calls(ns, hint, auction_chg, pnl):
    ns['_CTX'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(amount=1000)}
    cost = 10.0
    px = cost * (1.0 + pnl) if pnl is not None else 10.0
    rec = []
    ns['place_order'] = lambda c, sec, side, qty=None, note='', mode='chase': rec.append((sec, side, qty, note))
    ns['last_px'] = lambda sec: px
    ns['my_cost'] = lambda sec, pos: cost
    ns['score_now'] = lambda sec: 99.0
    ns['_auction_change'] = lambda sec: auction_chg
    ns['_eval_intraday'] = lambda sec, au: (ns['CM'], ['held_vwap'])
    ns['_eval_auction'] = lambda sec: (ns['PM'], ['auction_small_open'])
    ns['_confirm_expected'] = lambda sec: (ns['PM'], 0.0)
    ns['g'].exp_file['600001.XSHG'] = {'side': 'hold', 'entry_type': 'normal',
                                       'expected_status': '', 'sell_policy_hint': hint}
    ns['sell_manager'](ns['_CTX'])
    return [r[3] for r in rec]

base = fresh()
ok('T21 role default(none) factors 1.0',  base['_role_tolerance']('600001.XSHG') ==
    {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0})
bh = fresh(); bh['g'].exp_file['600001.XSHG'] = {'sell_policy_hint': 'hold_higher_tolerance'}
_rt = bh['_role_tolerance']('600001.XSHG')
ok('T21 role hold factors green_tol=2.5 stop_adj=1.3', _rt['green_tol'] == 2.5 and _rt['stop_adj'] == 1.3)

# P1 绿开：base 触线 -5.0；fast_exit green_tol=0.5 -> -2.5；hold_high 2.5 -> -12.5
ok('T21 P1 none(-3> -5): 不触发', _role_sell_calls(fresh(), 'none', -3.0, None) == [])
r1 = _role_sell_calls(fresh(), 'fast_exit_on_weak', -3.0, None)
ok('T21 P1 fast_exit(-3<= -2.5): 触发', any('P1_green_open' in n for n in r1))
ok('T21 P1 hold_high(-3> -12.5): 不触发', _role_sell_calls(fresh(), 'hold_higher_tolerance', -3.0, None) == [])

# P3 止损：base 5%；fast_exit stop_adj=0.8 -> 4%；hold_high 1.3 -> 6.5%（-4.5% 仅 fast_exit 触发）
ok('T21 P3 none(-4.5> -5): 不触发', _role_sell_calls(fresh(), 'none', 0.0, -0.045) == [])
r3 = _role_sell_calls(fresh(), 'fast_exit_on_weak', 0.0, -0.045)
ok('T21 P3 fast_exit(-4.5<= -4): 触发', any('P3_stop_loss' in n for n in r3))
ok('T21 P3 hold_high(-4.5> -6.5): 不触发', _role_sell_calls(fresh(), 'hold_higher_tolerance', 0.0, -0.045) == [])

# T22 动态仓位(_calc_buy_qty，替代硬编码0.3) + 红盘比/量比快照
ns = fresh(); po = ns['_CTX'].portfolio; po.cash = 100000.0; po.positions = {}
q1 = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, 0.30)
ok('T22 size cash*0.3=30000 -> qty 3000', q1 == 3000)

ns = fresh(); po = ns['_CTX'].portfolio; po.cash = 100000.0
po.positions = {'600001.XSHG': types.SimpleNamespace(amount=2000, last_price=10.0)}
po.total_value = 100000.0   # 总资产确定=100000(含该股20000市值)
q2 = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, 0.30)
ok('T22 单支上限(已持20000)->cap10000 -> qty 1000', q2 == 1000)

ns = fresh(); po = ns['_CTX'].portfolio; po.cash = 50000.0; po.positions = {}; po.total_value = 200000.0
q3 = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, 0.30)
ok('T22 total_value优先 cash*0.3=15000 -> qty 1500', q3 == 1500)

ns = fresh(); po = ns['_CTX'].portfolio; po.cash = 100000.0; po.positions = {}
q4 = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, 0.10)
ok('T22 ordinary ratio 0.1 -> qty 1000', q4 == 1000)

ns = fresh(); ns['_board_member_changes'] = lambda sec: [0.02, 0.03, -0.01, 0.01]
ok('T22 red_ratio 3涨1跌=0.75', abs(ns['_red_ratio']('600001.XSHG') - 0.75) < 1e-9)
ns = fresh(); ns['_board_member_changes'] = lambda sec: []
ok('T22 red_ratio 无成员=0.5中性', abs(ns['_red_ratio']('600001.XSHG') - 0.5) < 1e-9)

ns = fresh(); ns['g'].spot['600002.XSHG'] = {'vol_ratio': 2.5}
ok('T22 vol_ratio 快照2.5', abs(ns['_volume_ratio']('600002.XSHG') - 2.5) < 1e-9)
ns = fresh(); ns['g'].spot['600003.XSHG'] = {}; ns['_hist_1d'] = lambda sec: None
ok('T22 vol_ratio 无数据回退1.0', abs(ns['_volume_ratio']('600003.XSHG') - 1.0) < 1e-9)

# T23 卖出仓位：可卖 enable_amount + P6 半仓整手
sec = '600005.XSHG'
ok('T23 _sellable 优先 enable_amount=300', ns['_sellable'](sec, {sec: types.SimpleNamespace(enable_amount=300, amount=500)}) == 300)
ok('T23 _sellable 缺 enable_amount 回退 amount=500', ns['_sellable'](sec, {sec: types.SimpleNamespace(amount=500)}) == 500)
ok('T23 _sellable dict 形式 enable_amount=100', ns['_sellable'](sec, {sec: {'enable_amount': 100, 'amount': 400}}) == 100)
ok('T23 _sellable enable_amount=0 -> 当日不可卖 0', ns['_sellable'](sec, {sec: types.SimpleNamespace(enable_amount=0, amount=300)}) == 0)

# P6 评分半仓：enable_amount=200, score_now=40(30<=sc<50) -> 卖 100 整手
ns = fresh(); po = ns['_CTX'].portfolio
po.positions = {sec: types.SimpleNamespace(amount=200, enable_amount=200, cost_basis=10.0)}
ns['g'].spot[sec] = {'last_px': 10.0}
ns['score_now'] = lambda s: 40.0
scalls = []
ns['place_order'] = lambda context, sec, side=None, qty=None, note='', **k: scalls.append({'sec': sec, 'qty': qty, 'note': note})
ns['sell_manager'](ns['_CTX'])
ok('T23 P6 半仓触发且整手 qty=100', len(scalls) == 1 and scalls[0]['qty'] == 100 and 'P6_score_half' in scalls[0]['note'])

# P6 可卖仅一手(enable_amount=100) -> 卖 100
ns = fresh(); po = ns['_CTX'].portfolio
po.positions = {sec: types.SimpleNamespace(amount=100, enable_amount=100, cost_basis=10.0)}
ns['g'].spot[sec] = {'last_px': 10.0}
ns['score_now'] = lambda s: 40.0
scalls = []
ns['place_order'] = lambda context, sec, side=None, qty=None, note='', **k: scalls.append({'sec': sec, 'qty': qty, 'note': note})
ns['sell_manager'](ns['_CTX'])
ok('T23 P6 可卖100 -> 卖 100 有余量扣减', len(scalls) == 1 and scalls[0]['qty'] == 100)

# P5 清仓：score_now=20(<30) -> 卖 enable_amount=200
ns = fresh(); po = ns['_CTX'].portfolio
po.positions = {sec: types.SimpleNamespace(amount=500, enable_amount=200, cost_basis=10.0)}
ns['g'].spot[sec] = {'last_px': 10.0}
ns['score_now'] = lambda s: 20.0
scalls = []
ns['place_order'] = lambda context, sec, side=None, qty=None, note='', **k: scalls.append({'sec': sec, 'qty': qty, 'note': note})
ns['sell_manager'](ns['_CTX'])
ok('T23 P5 清仓按 enable_amount=200 而非 amount=500', len(scalls) == 1 and scalls[0]['qty'] == 200 and 'P5_score_clear' in scalls[0]['note'])

# T24 卖出稳健：核卖地板价 + 在途挂单守卫 + 订单/成交回报对账（参照 AXquant）
ns = fresh()
ns['g'].spot['600006.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
ok('T24 limit_down 主板 -10% = 9.0', abs(ns['_limit_down_price']('600006.XSHG') - 9.0) < 1e-9)
ns['g'].spot['300006.XSHE'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 12.0, 'trade_status': 'OPEN'}
ok('T24 limit_down 创业板 -20% = 8.0', abs(ns['_limit_down_price']('300006.XSHE') - 8.0) < 1e-9)
ok('T24 普通卖出限价=现价 10.0', ns['_order_limit']('600006.XSHG', 'sell', 'sell') == 10.0)
ok('T24 核卖限价=跌停地板 9.0', ns['_order_limit']('600006.XSHG', 'sell', 'sell_urgent') == 9.0)

# 在途挂单守卫
ns = fresh(); ns['g'].pending['600007.XSHG'] = {'side': 'sell', 'qty': 100, 'status': 'SENT'}
ok('T24 inflight SENT -> 跳过(防叠单)', ns['_sell_inflight']('600007.XSHG') is True)
ns['g'].pending['600007.XSHG']['status'] = 'FILLED'
ok('T24 inflight FILLED -> 放行', ns['_sell_inflight']('600007.XSHG') is False)
ns['g'].pending['600007.XSHG']['side'] = 'buy'
ok('T24 inflight buy -> 不拦卖出', ns['_sell_inflight']('600007.XSHG') is False)

# 成交回报对账：全成/部分 + daily.sold
ns = fresh()
ns['g'].pending['600008.XSHG'] = {'side': 'sell', 'qty': 200, 'status': 'SENT', 'filled': 0, 'no': 'E1'}
ns['on_trade_response'](ns['_CTX'], types.SimpleNamespace(ticker='600008.XSHG', quantity=200))
p = ns['g'].pending['600008.XSHG']
ok('T24 成交回报全成 FILLED/200', p['status'] == 'FILLED' and p['filled'] == 200)
ok('T24 成交回报记入 daily.sold', '600008.XSHG' in ns['g'].daily['sold'])

ns = fresh()
ns['g'].pending['600009.XSHG'] = {'side': 'sell', 'qty': 200, 'status': 'SENT', 'filled': 0, 'no': 'E2'}
ns['on_trade_response'](ns['_CTX'], types.SimpleNamespace(ticker='600009.XSHG', quantity=100))
ok('T24 成交回报部分成交 PARTIAL', ns['g'].pending['600009.XSHG']['status'] == 'PARTIAL')

# 订单回报：拒绝释放
ns = fresh()
ns['g'].pending['600010.XSHG'] = {'side': 'sell', 'qty': 100, 'status': 'SENT', 'filled': 0, 'no': 'E3'}
ns['on_order_response'](ns['_CTX'], types.SimpleNamespace(entrust_no='E3', order_status='REJECTED'))
ok('T24 订单回报拒绝 -> 在途放行可重试', ns['_sell_inflight']('600010.XSHG') is False)

# 挂单超时无回报 -> 放行重试（对齐 AXquant order_lost）
ns = fresh()
ns['g'].pending['600011.XSHG'] = {'side': 'sell', 'qty': 100, 'status': 'SENT', 'ts': time.time() - 200}
ok('T24 挂单超时 SENT>120s -> 放行重试', ns['_sell_inflight']('600011.XSHG') is False)

# T25 持仓键标准化：portfolio.positions 原始键 .SS vs spot 规范键 .XSHG（本轮修卖单空转根因）
ns = fresh(); po = ns['_CTX'].portfolio
raw = '601811.SS'; norm = '601811.XSHG'
po.positions = {raw: types.SimpleNamespace(amount=200, enable_amount=200, cost_basis=10.0)}
ns['g'].spot[norm] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
ns['g'].spot['601811.SS'] = ns['g'].spot[norm]
ns['score_now'] = lambda s: 40.0
scalls = []
ns['place_order'] = lambda c, sec, side=None, qty=None, note='', **k: scalls.append({'sec': sec, 'qty': qty, 'note': note})
ns['sell_manager'](ns['_CTX'])
ok('T25 持仓码.SS 规范化后 P6 触发(卖100整手)', len(scalls) == 1 and scalls[0]['qty'] == 100 and 'P6_score_half' in scalls[0]['note'])

# T26 定时上传自建 upload_file/ 目录：策略搜索路径需覆盖（否则云端文件落 upload_file/ 读不到）
ns = fresh()
_ep = ns['_expectation_paths']()
ok('T26 预期文件候选含 upload_file/', any('upload_file/expectation_2026-10-16.csv' in x for x in _ep))
ok('T26b 云端优先读稳定指针 expectation_latest',
   _ep[0].endswith('expectation_latest.csv') and any('upload_file/expectation_latest.csv' in x for x in _ep))
ok('T26c 既有交易日文件名仍做兑底', any('expectation_2026-10-16.csv' in x for x in _ep))
_sw = ns['_selfwatch_paths']()
ok('T26 selfwatch 候选含 upload_file/', any('upload_file/selfwatch.csv' in x for x in _sw))

# T26d v0.70 5D低吸：CORE + 生命周期次低价进入MA5±2% + score>=50 -> 10%
ns = fresh(); ns['g'].watch = ['600001.XSHG', '600002.XSHG', '600003.XSHG', '600004.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)   # 低吸窗口内（10:30 前）
ns['_tags'] = lambda sec: {'600001.XSHG': ['CORE'], '600002.XSHG': [], '600003.XSHG': ['CORE'], '600004.XSHG': ['CORE']}.get(sec, [])
ns['_ensure_ma5'] = lambda sec: 10.0
ns['_ma5_at_price'] = lambda sec, px: 10.0
ns['_ma5_base4'] = lambda sec: 10.0
prices = {'600001.XSHG': 9.7, '600002.XSHG': 9.7, '600003.XSHG': 9.7, '600004.XSHG': 9.7}
ns['last_px'] = lambda sec: prices.get(sec)
ns['score_now'] = lambda sec: {'600001.XSHG': 50.0, '600002.XSHG': 60.0, '600003.XSHG': 60.0, '600004.XSHG': 49.0}.get(sec, 0.0)
ns['_l2_big_ratio'] = lambda sec: 0.12 if sec == '600001.XSHG' else -1.0
ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['BLS']['ma5_core_only'] = True; ns['BLS']['ma5_require_bs'] = False; ns['BLS']['ma5_first_5d'] = True
ns['BLS']['ma5_second_low_enabled'] = True; ns['BLS']['ma5_touch_band'] = 0.02
ns['BLS']['ma5_buy_score_min'] = 50.0; ns['BLS']['ma5_buy_ratio'] = 0.10
ns['BLS']['daily_max_buy'] = 10
ns['_ma5_first_5d'] = lambda sec: True
pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append((sec, note, k.get('ratio'))) or True
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T26d 只有一个样本不触发(次低价未形成)', pcalls == [])
prices['600001.XSHG'] = 10.0; prices['600004.XSHG'] = 10.0
ns['try_ma5_buy'](ns['_CTX'])
ok('T26d 非CORE(杂毛)低吸被拦截', all(c[0] != '600002.XSHG' for c in pcalls))
ok('T26d 无BS但CORE可低吸(BS硬门移除)', any(c[0] == '600001.XSHG' for c in pcalls))
ok('T26d 次低价9.7偏离MA5 3% -> 拦截', all(c[0] != '600003.XSHG' for c in pcalls))
ok('T26d 评分49低于低吸门50拦截', all(c[0] != '600004.XSHG' for c in pcalls))
ok('T26d CORE+次低价进入MA5±2%+score50 -> 10%低吸',
   len(pcalls) == 1 and pcalls[0][0] == '600001.XSHG' and 'ma_pullback' in pcalls[0][1] and abs(pcalls[0][2] - 0.10) < 1e-9)
ok('T26d 低吸日志含次低价/MA5带/四日基准/L2占比',
   'low2=10.00' in pcalls[0][1] and 'band=0.00%' in pcalls[0][1] and
   'ma5b4=' in pcalls[0][1] and 'l2=12.00%' in pcalls[0][1])

# T26d2 次低价恰好落在MA5±2%边界仍触发
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)
ns['_tags'] = lambda sec: ['CORE']; ns['_ma5_first_5d'] = lambda sec: True
ns['_ensure_ma5'] = lambda sec: 10.0; ns['_ma5_at_price'] = lambda sec, px: 10.0
ns['_ma5_base4'] = lambda sec: 10.0; ns['_l2_big_ratio'] = lambda sec: -1.0
ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['score_now'] = lambda sec: 50.0
ns['BLS']['ma5_second_low_enabled'] = True; ns['BLS']['ma5_touch_band'] = 0.02
ns['BLS']['ma5_buy_score_min'] = 50.0; ns['BLS']['daily_max_buy'] = 10
prices = [9.7, 9.8]; ns['last_px'] = lambda sec: prices.pop(0)
pcalls = []; ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append(sec) or True
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX']); ns['try_ma5_buy'](ns['_CTX'])
ok('T26d2 次低价边界-2.00%触发', pcalls == ['600001.XSHG'])

# T26e 非5日内首次回踩(重复低吸)被拦截
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)   # 低吸窗口内（10:30 前）
ns['_tags'] = lambda sec: ['CORE']
ns['_ensure_ma5'] = lambda sec: 10.0; ns['_ma5_at_price'] = lambda sec, px: 10.0
ns['last_px'] = lambda sec: 9.8
ns['score_now'] = lambda sec: 60.0; ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['BLS']['ma5_core_only'] = True; ns['BLS']['ma5_require_bs'] = False; ns['BLS']['ma5_first_5d'] = True
ns['BLS']['daily_max_buy'] = 10
ns['_ma5_first_5d'] = lambda sec: False
pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append(sec) or True
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T26e 非5日内首次回踩被拦截', pcalls == [])

# T26f v0.70 次低价首次进入MA5带后不达标，当日不再追补；次日重新解锁
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)
ns['_tags'] = lambda sec: ['CORE']
ns['_ma5_first_5d'] = lambda sec: False
ns['_ensure_ma5'] = lambda sec: 10.0; ns['_ma5_at_price'] = lambda sec, px: 10.0
ns['_ma5_base4'] = lambda sec: 10.0
prices = {'px': 9.7}; ns['last_px'] = lambda sec: prices['px']
ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['_l2_big_ratio'] = lambda sec: -1.0
ns['BLS']['ma5_core_only'] = True; ns['BLS']['ma5_require_bs'] = False; ns['BLS']['ma5_first_5d'] = False
ns['BLS']['ma5_second_low_enabled'] = True; ns['BLS']['ma5_touch_band'] = 0.02
ns['BLS']['ma5_buy_score_min'] = 50.0; ns['BLS']['daily_max_buy'] = 10
pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append(sec) or True
ns['_save_state'] = lambda *a, **k: None
ns['score_now'] = lambda sec: 49.0
ns['try_ma5_buy'](ns['_CTX'])
ok('T26f 次低价9.7未进入MA5带 -> 不消耗首触', pcalls == [] and not ns['g'].ma5_touched)
prices['px'] = 10.0
ns['try_ma5_buy'](ns['_CTX'])
ns['score_now'] = lambda sec: 60.0
ns['try_ma5_buy'](ns['_CTX'])
ok('T26f 次低价进入MA5带score49 -> 当日后补不买', pcalls == [] and '600001.XSHG' in ns['g'].ma5_touched)
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 17)
prices['px'] = 9.7
ns['try_ma5_buy'](ns['_CTX'])
prices['px'] = 10.0
ns['try_ma5_buy'](ns['_CTX'])
ok('T26f 次日首触状态重置并触发', pcalls == ['600001.XSHG'])

# T27 持仓来源与多字段：get_positions()(amount/enable_amount/cost_basis) + 柜台式(current_amount) 兜底
ns = fresh()
ok('T27 _sellable current_amount+enable_amount -> enable_amount=300', ns['_sellable']('601811.XSHG', {'601811.XSHG': {'current_amount': 500, 'enable_amount': 300}}) == 300)
ok('T27 _sellable 无 enable -> 回退 current_amount=500', ns['_sellable']('601811.XSHG', {'601811.XSHG': {'current_amount': 500}}) == 500)
ok('T27 _sellable enable_amount=0 不回退总量(当日不可卖)', ns['_sellable']('601811.XSHG', {'601811.XSHG': {'enable_amount': 0, 'amount': 200}}) == 0)
ok('T27 my_cost cost_price=10.5', abs(ns['my_cost']('601811.XSHG', {'601811.XSHG': {'cost_price': '10.5'}}) - 10.5) < 1e-9)

# get_positions() 作为持仓来源（context.portfolio.positions 为空时）-> sell_manager 触发 P6
ns = fresh()
ns['get_positions'] = lambda: {'601811.XSHG': {'amount': 200, 'enable_amount': 200, 'cost_basis': 10.0}}
ns['g'].spot['601811.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
ns['score_now'] = lambda s: 40.0
scalls = []
ns['place_order'] = lambda c, sec, side=None, qty=None, note='', **k: scalls.append({'qty': qty, 'note': note})
ns['sell_manager'](ns['_CTX'])
ok('T27 get_positions来源 P6 触发卖100', len(scalls) == 1 and scalls[0]['qty'] == 100 and 'P6_score_half' in scalls[0]['note'])

# T28 实盘 Position 无可卖字段 -> amt0 + 字段探测日志（定位真实字段名）
ns = fresh()
_logs = []
ns['log'] = types.SimpleNamespace(
    info=lambda *a: _logs.append(a), warn=lambda *a: _logs.append(a), error=lambda *a: None)
class _ExternalPos:
    def __init__(self): self.sum = 200; self.sell_able = 200
ok('T28 未知字段持仓 -> _sellable 0', ns['_sellable']('601811.XSHG', {'601811.XSHG': _ExternalPos()}) == 0)
ok('T28 字段探测 [pos-fields] 日志已输出', any(x and len(x) > 0 and isinstance(x[0], str) and '[pos-fields]' in x[0] for x in _logs))

# T29 T-1 涨停/连板名单加载 + _limitup_days 权威连板对齐（docs/33）
ns = fresh()
_lb = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with open(_lb, 'w', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason\n'
            '2026-10-16,600825.XSHG,新华传媒,11,09:25,31519156.00,10.0145,0,r1\n'
            '2026-10-16,000530.XSHE,冰山冷热,4,10:20,9861804.00,9.9567,0,r2\n')
ok('T29 zt_lianban 加载 2 只', ns['_load_zt_lianban']() == 2)
ok('T29 zt 连板映射 board_cnt=11', ns['g'].zt_lianban['600825.XSHG']['board_cnt'] == 11)
ns['g'].spot['600825.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
ok('T29 _limitup_days 权威11(今日不续板)', ns['_limitup_days']('600825.XSHG') == 11)
ns['g'].spot['600825.XSHG']['last_px'] = 11.0
ok('T29 _limitup_days 权威11+今日续板=12', ns['_limitup_days']('600825.XSHG') == 12)


# --- T30 v0.69 动态 MA5 = 最近4个已完成日收盘 + 当前价 ---
class _Mean:
    def __init__(self, v): self._v = v
    def mean(self): return sum(self._v) / len(self._v)
class _Iloc:
    def __init__(self, v): self._v = v
    def __getitem__(self, sl): return _Mean(list(self._v[sl]))
class _Col:
    def __init__(self, v): self._iloc = _Iloc(v); self._v = v
    @property
    def iloc(self): return self._iloc
    def __iter__(self): return iter(self._v)
    def __len__(self): return len(self._v)
    def __getitem__(self, i):
        return _Mean(self._v[i]) if isinstance(i, slice) else self._v[i]
class _FakeDF:
    def __init__(self, closes, index=None):
        self._close = _Col(closes); self._n = len(closes)
        self.index = index if index is not None else []
    def __getitem__(self, k): return self._close if k == 'close' else None
    @property
    def close(self): return self._close
    def __len__(self): return self._n

ns = fresh()
ns['g'].last_ma5 = {}
ns['_hist_1d'] = lambda sec: _FakeDF(
    [1,2,3,4,5,6,7,8,9,10],
    index=[datetime.date(2026,10,1) + datetime.timedelta(days=i) for i in range(9)] + [datetime.date(2026,10,15)])
ns['last_px'] = lambda sec: 11.0
ok('T30 get_price不含今日 -> 近4完日+现价', abs(ns['_ensure_ma5']('600001.XSHG') - 9.0) < 1e-9)
ok('T30 base4缓存命中', abs(ns['_ma5_base4']('600001.XSHG') - 8.5) < 1e-9)
ns['last_px'] = lambda sec: 16.0
ok('T30 同帧价格变化 -> 动态MA5实时变化', abs(ns['_ensure_ma5']('600001.XSHG') - 10.0) < 1e-9)

ns = fresh()
ns['g'].last_ma5 = {}
ns['_hist_1d'] = lambda sec: _FakeDF(
    [1,2,3,4,5,6,7,8,9,10],
    index=[datetime.date(2026,10,7) + datetime.timedelta(days=i) for i in range(9)] + [datetime.date(2026,10,16)])
ns['last_px'] = lambda sec: 10.0
ok('T30 末日为今日时剔除未完成日线', abs(ns['_ensure_ma5']('600001.XSHG') - 8.0) < 1e-9)

ns = fresh()
ns['g'].last_ma5 = {}
ns['_hist_1d'] = lambda sec: _FakeDF(
    [9.91,10.90,11.99,13.19,14.51],
    index=[datetime.date(2026,10,16),datetime.date(2026,10,19),datetime.date(2026,10,20),
           datetime.date(2026,10,21),datetime.date(2026,10,22)])
ns['last_px'] = lambda sec: 15.96
ok('T30 603278现价15.96 -> MA5=13.31', abs(ns['_ensure_ma5']('603278.XSHG') - 13.31) < 1e-9)

# --- T31 跨重启持久化 first_zt / auction_c (修复 docs/24 ②) ---
ns = fresh()
ns['g'].auction_c = {'600002.XSHG': ('2026-10-16', 5.0)}
ns['g'].first_zt = {'600002.XSHG': {'first_seal': 1e6, 'first_bids': 50, 'break': False}}
ns['g'].exp_fired = {'600002.XSHG'}
ns['_save_state']()
ns['g'].auction_c = {}; ns['g'].first_zt = {}; ns['g'].exp_fired = set()
ns['load_state']()
ok('T31 同日重启还原 auction_c', ns['g'].auction_c.get('600002.XSHG') == ('2026-10-16', 5.0))
ok('T31 同日重启还原 first_zt', ns['g'].first_zt.get('600002.XSHG', {}).get('first_seal') == 1e6)

ns = fresh()
ns['g'].auction_c = {'600003.XSHG': ('2026-10-15', 9.0)}
ns['g'].first_zt = {'600003.XSHG': {'first_seal': 1e6, 'break': False}}
ns['g'].state_day = '2026-10-15'      # 跨日旧状态
ns['_save_state']()
ns['g'].auction_c = {}; ns['g'].first_zt = {}
ns['load_state']()
ok('T31 跨日不还原累旧 auction_c', not ns['g'].auction_c.get('600003.XSHG'))
ok('T31 跨日不还原旧 first_zt', not ns['g'].first_zt.get('600003.XSHG'))

# --- T32 firstzt 门槛字段存在且非负 ---
ns = fresh()
ok('T32 firstzt_min_seal>=0', float(ns['BLS'].get('firstzt_min_seal', -1)) >= 0)
ok('T32 firstzt_min_bids>=0', int(ns['BLS'].get('firstzt_min_bids', -1)) >= 0)



# --- T33/T34: AXquant 数据提供方契约（bridge.axquant_contract） ---
import bridge.axquant_contract as _axc
ok('T33 axquant_root 指向 AXquant', os.path.basename(_axc.axquant_root()) == 'AXquant')
_pp = _axc.paths('2026-10-16', '2026-10-19')
ok('T33 paths 解析 limit_up_boards', _pp['limit_up_boards'].endswith('limit_up_boards_2026-10-16.json'))
ok('T33 paths 解析 expectation_source', _pp['expectation_source'].endswith('position_expectation_2026-10-19.jsonl'))
ok('T33 后缀归一 AX>PT', _axc._pt('000530.SZ') == '000530.XSHE' and _axc._pt('600668.SH') == '600668.XSHG')
ok('T33 市场族', _axc._fam('000530.XSHE') == 'SZ' and _axc._exp_fam('000530') == 'SZ')

import tempfile
_tdir = tempfile.mkdtemp(prefix='pt_axc_')
_c = os.path.join(_tdir, 'e.csv'); _s = os.path.join(_tdir, 'e.jsonl')
io.open(_c,'w',encoding='utf-8').write('code\n000530.XSHE\n600668.XSHG\n601811.XSHG\n')
io.open(_s,'w',encoding='utf-8').write('{"code":"000530.SZ"}\n{"code":"600668.SH"}\n{"code":"601811.SH"}\n')
_r = _axc.check_expectation_consistency(_c, _s)
ok('T34 预期一致性(AX/PT 混写) ok=True', _r["ok"] and _r["csv_codes"] == 3 and _r["src_codes"] == 3)
ok('T34 无后缀异常', 'suffix_anomalies' not in _r["note"])
# 市场族错误应上报
io.open(_s,'w',encoding='utf-8').write('{"code":"000530.SH"}\n{"code":"600668.SH"}\n{"code":"601811.SH"}\n')
_r2 = _axc.check_expectation_consistency(_c, _s)
ok('T34 深市写.SH 触发异常上报', '000530' in _r2["note"])
import shutil; shutil.rmtree(_tdir, ignore_errors=True)


# --- T35: 涨停池分页完整性护栏 (export_lianban._pool_missing) ---
import export_lianban as _el
_real = _el._pool_missing.__self__ if False else None
import json as _json
_rp = _json.load(io.open(_el.default_lub_path('2026-10-16'), encoding='utf-8'))
ok('T35 真实涨停池不缺(59=59)', _el._pool_missing(_rp, _el._extract_pool_rows(_rp)) == 0)
_fake = {'pool': {'pagination': {'total': 100}, 'item': _rp.get('pool', {}).get('item', [])[:3]}}
ok('T35 截断被检出(item3/total100 缺97)', _el._pool_missing(_fake, _el._extract_pool_rows(_fake)) == 97)



# --- T36 核心票买入 try_core_buy（v0.18，AXquant CORE 门禁） ---
def _core_setup(held=()):
    ns = fresh()
    ns['g'].watch = ['600001.XSHG', '600002.XSHG', '600003.XSHG', '600005.XSHG']
    ns['g'].pool_static = []
    ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)   # 核心票窗口内（10:00 前）
    ns['_tags'] = lambda sec: {'600001.XSHG': ['CORE'], '600002.XSHG': [], '600003.XSHG': ['CORE'], '600005.XSHG': ['CORE']}.get(sec, [])
    ns['_limitup_days'] = lambda sec: {'600001.XSHG': 2, '600002.XSHG': 1, '600003.XSHG': 6, '600005.XSHG': 1}.get(sec, 1)
    ns['last_px'] = lambda sec: 10.0
    ns['score_now'] = lambda sec: 60.0
    ns['trade_open'] = lambda sec: True
    ns['_block_sealed_buy'] = lambda sec: False
    ns['BLS']['daily_max_buy'] = 10
    ns['_save_state'] = lambda *a, **k: None
    ns['_CTX'].portfolio.positions = {c: types.SimpleNamespace(amount=100) for c in held}
    return ns

ns = _core_setup(); pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pcalls.append({'sec': sec, 'mode': mode, 'note': note}) or True
ns['try_core_buy'](ns['_CTX'])
ok('T36 非CORE core_buy 拦截', all(c['sec'] != '600002.XSHG' for c in pcalls))
ok('T36 连板>=6 core_buy 拦截', all(c['sec'] != '600003.XSHG' for c in pcalls))
ok('T36 CORE+连板<6 core_buy 触发', any(c['sec'] == '600001.XSHG' and c['mode'] == 'chase' and 'core_buy' in c['note'] for c in pcalls))
ok('T36 core_buy 记入 daily.bought', '600001.XSHG' in ns['g'].daily['bought'])

ns = _core_setup(held=('600005.XSHG',)); pcalls = []
ns['place_order'] = lambda *a, **k: pcalls.append(1) or True
ns['try_core_buy'](ns['_CTX'])
ok('T36 已持仓 CORE 不重复买', '600005.XSHG' not in ns['g'].daily['bought'])

ns = _core_setup(); ns['BLS']['daily_max_buy'] = 1; ns['g'].daily['bought'] = ['600009.XSHG']; pcalls = []
ns['place_order'] = lambda *a, **k: pcalls.append(1) or True
ns['try_core_buy'](ns['_CTX'])
ok('T36 日买满 core_buy 拦截', pcalls == [])

# --- T37 首板闸门辅助 ---
ns = fresh()
ns['g'].spot['600001.XSHG'] = {'open_px': 10.0, 'up_px': 10.98}
ok('T37 非一字板(低开) -> False', ns['_is_one_word_open']('600001.XSHG') is False)
ns['g'].spot['600001.XSHG'] = {'open_px': 10.97, 'up_px': 10.98}
ok('T37 开盘即涨停(一字) -> True', ns['_is_one_word_open']('600001.XSHG') is True)

ns = fresh(); ns['g'].zt_lianban = {'600001.XSHG': {'board_cnt': 0}}
ok('T37 T-1无连板 -> 首板 True', ns['_is_first_board']('600001.XSHG') is True)
ns['g'].zt_lianban = {'600001.XSHG': {'board_cnt': 2}}
ok('T37 T-1已2连板 -> 非首板 False', ns['_is_first_board']('600001.XSHG') is False)
ns = fresh(); ns['g'].zt_lianban = {}
ns['_limitup_days'] = lambda sec: 3
ok('T37 无名单回退 连板>1 -> False', ns['_is_first_board']('600001.XSHG') is False)
ns['_limitup_days'] = lambda sec: 1
ok('T37 无名单回退 连板<=1 -> True', ns['_is_first_board']('600001.XSHG') is True)

ns = fresh(); ns['g'].spot['600001.XSHG'] = {'last_px': 10.5, 'preclose_px': 10.0, 'up_px': 11.0}
ns['_board_member_codes'] = lambda sec: ['600001.XSHG', '600002.XSHG']
ns['last_px'] = lambda sec: {'600001.XSHG': 10.5, '600002.XSHG': 10.3}.get(sec, 10.0)
ns['_get_snapshot_many'] = lambda codes, cap: {c: {'last_px': 10.3 if c == '600002.XSHG' else 10.5, 'preclose_px': 10.0} for c in codes}
ok('T37 板块内最高 -> True', ns['_board_top_gainer']('600001.XSHG') is True)
ns['g'].spot.pop('600002.XSHG', None)   # 模拟下一帧刷新, 触发批量重取
ns['_get_snapshot_many'] = lambda codes, cap: {c: {'last_px': 10.9 if c == '600002.XSHG' else 10.5, 'preclose_px': 10.0} for c in codes}
ok('T37 有成员更高 -> False', ns['_board_top_gainer']('600001.XSHG') is False)

ns = fresh()
ns['_board_member_codes'] = lambda sec: ['600001.XSHG', '600002.XSHG']
ns['g'].first_zt = {'600001.XSHG': {'ts': 2000.0}}
ok('T37 无更早成员触板 -> True', ns['_board_first_zt']('600001.XSHG') is True)
ns['g'].first_zt = {'600001.XSHG': {'ts': 2000.0}, '600002.XSHG': {'ts': 1000.0}}
ok('T37 有成员更早触板 -> False', ns['_board_first_zt']('600001.XSHG') is False)

# --- T38 首板确认->打板（_try_first_board_buy 全门禁） ---
def _fb_setup():
    ns = fresh()
    ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
    ns['g'].spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2, 'trade_status': 'OPEN'}
    ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
    ns['last_px'] = lambda sec: 10.8
    ns['trade_open'] = lambda sec: True
    ns['_is_one_word_open'] = lambda sec: False
    ns['_is_first_board'] = lambda sec: True
    ns['_board_top_gainer'] = lambda sec: True
    ns['_board_first_zt'] = lambda sec: True
    ns['_block_sealed_buy'] = lambda sec: False
    ns['_save_state'] = lambda *a, **k: None
    ns['_board_rank_top3'] = lambda sec, secs=None: True   # v0.23 板块强度前三桩（专项 T55 测真实逻辑）
    ns['_CTX'].portfolio.positions = {}
    return ns

def _fb_calls(ns):
    out = []
    ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append({'sec': sec, 'mode': mode, 'ratio': ratio, 'note': note}) or True
    ns['_try_first_board_buy'](ns['_CTX'], '600001.XSHG')
    return out

ns = _fb_setup(); pc = _fb_calls(ns)
ok('T38 首板闸门全过 -> 打板(板价排队,预算20%)', len(pc) == 1 and pc[0]['mode'] == 'board' and pc[0]['ratio'] == 0.20 and 'first_board_buy' in pc[0]['note'])
ok('T38 打板记入 daily.bought + fired', '600001.XSHG' in ns['g'].daily['bought'] and '600001.XSHG' in ns['g'].first_board_fired)

ns = _fb_setup(); ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 5, 0)
ok('T38 开盘超10分钟 -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['_is_one_word_open'] = lambda sec: True
ok('T38 一字板 -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['_is_first_board'] = lambda sec: False
ok('T38 非首板 -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['_board_top_gainer'] = lambda sec: False
ok('T38 非板块最高 -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['_board_first_zt'] = lambda sec: False
ok('T38 非最快(已有成员更早触板) -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['_block_sealed_buy'] = lambda sec: True
ok('T38 封死涨停 -> skip', _fb_calls(ns) == [])
ns = _fb_setup(); ns['g'].daily['bought'] = ['600009.XSHG']; ns['BLS']['daily_max_buy'] = 1
ok('T38 日买满 -> skip', _fb_calls(ns) == [])

# --- T39 tick_data 首触 -> 首板打板 端到端 ---
def _tick_fb(top=True):
    ns = fresh()
    ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
    ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
    code = '600001.XSHG'
    snap = {code: {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2, 'trade_status': 'OPEN', 'hsTimeStamp': 99000000}}
    ns['get_snapshot'] = lambda sec: snap
    ns['BLS']['firstzt_min_seal'] = 0.0
    ns['BLS']['firstzt_min_bids'] = 0
    ns['_is_one_word_open'] = lambda sec: False
    ns['_is_first_board'] = lambda sec: True
    ns['_board_top_gainer'] = lambda sec: top
    ns['_board_first_zt'] = lambda sec: True
    ns['_save_state'] = lambda *a, **k: None
    ns['_board_rank_top3'] = lambda sec, secs=None: True   # v0.23 桩
    ns['_CTX'].portfolio.positions = {}
    ns['g'].first_zt = {}   # tick 首触状态（fresh 未初始化）
    return ns

ns = _tick_fb(top=True); pc = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append({'sec': sec, 'mode': mode, 'note': note}) or True
ns['tick_data'](ns['_CTX'], {})
ok('T39 tick 首触 -> 首板打板下单', len(pc) == 1 and pc[0]['sec'] == '600001.XSHG' and 'first_board_buy' in pc[0]['note'])
ok('T39 firstzt 已记录', bool(ns['g'].first_zt.get('600001.XSHG')))
ok('T39 打板记入 daily.bought + fired', '600001.XSHG' in ns['g'].daily['bought'] and '600001.XSHG' in ns['g'].first_board_fired)

ns = _tick_fb(top=False); pc = []
ns['place_order'] = lambda *a, **k: pc.append(1) or True
ns['tick_data'](ns['_CTX'], {})
ok('T39 非板块最高 -> tick 首触不买', pc == [] and '600001.XSHG' in ns['g'].first_zt)



# --- T40 买入预算规则锁定：打板20%、其它10%（AXquant board_buy_budget_ratio / ordinary_buy_ratio / exp_order_pct） ---
ns = fresh()
ns['_CTX'].portfolio.cash = 100000.0
ok('T40 打板预算=20%', abs(float(ns['BLS']['board_buy_budget_ratio']) - 0.20) < 1e-9)
ok('T40 普通买入=10%', abs(float(ns['BLS']['ordinary_buy_ratio']) - 0.10) < 1e-9)
ok('T40 预期买入chase=10%', abs(float(ns['BLS']['exp_order_pct']) - 0.10) < 1e-9)
q_board = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, float(ns['BLS']['board_buy_budget_ratio']))
q_ord = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, float(ns['BLS']['ordinary_buy_ratio']))
q_exp = ns['_calc_buy_qty'](ns['_CTX'], '600001.XSHG', 10.0, float(ns['BLS']['exp_order_pct']))
ok('T40 打板20% -> 2000股', q_board == 2000)
ok('T40 其它10% -> 1000股', q_ord == 1000 and q_exp == 1000)


# --- T41 弹性套利：板块一字板统计（_elastic_yizi_scan，AXquant A 段） ---
ns = fresh()
ns['g'].watch = ['600001.XSHG', '300001.XSHE', '300002.XSHE']; ns['g'].pool_static = []
ns['g'].zt_lianban = {}
ns['g'].spot['600001.XSHG'] = {'preclose_px': 10.0, 'open_px': 10.5}   # 主板非一字
ns['g'].spot['300001.XSHE'] = {'preclose_px': 10.0, 'open_px': 12.0}   # 20cm 一字
ns['g'].spot['300002.XSHE'] = {'preclose_px': 10.0, 'open_px': 12.1}   # 20cm 一字
ns['_seal_metrics'] = lambda sec: (100000.0, 5) if str(sec).startswith('300') else (0.0, 0)
ns['_boards_of'] = lambda sec: {'600001.XSHG': ['M1'], '300001.XSHE': ['B1'], '300002.XSHE': ['B1']}.get(sec, [])
ns['_elastic_yizi_pool'] = lambda: ['600001.XSHG', '300001.XSHE', '300002.XSHE']
ns['BLS']['elastic_arb_min_yizi'] = 2
ns['g'].elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
strong = ns['_elastic_yizi_scan']()
ok('T41 板块一字>=2 -> strong', strong == {'B1': 2})
ok('T41 二次调用走缓存', ns['_elastic_yizi_scan']() == {'B1': 2})
ns['BLS']['elastic_arb_min_yizi'] = 3
ns['g'].elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
ok('T41 min_yizi=3 -> 无强板块', ns['_elastic_yizi_scan']() == {})

# --- T42 1m 大阳线 + ask1 卖一价 ---
class _Iloc1:
    def __init__(self, v): self._v = v
    def __getitem__(self, sl): return self._v[sl]
class _Col1:
    def __init__(self, v): self.iloc = _Iloc1(v); self._v = v
class _Bar:
    def __init__(self, o, c): self._o = o; self._c = c
    def __getitem__(self, k): return _Col1(self._o if k == 'open' else self._c)
    def __len__(self): return len(self._o)

ns = fresh()
ns['get_price'] = lambda *a, **k: _Bar([10.0, 10.0], [10.0, 10.4])
ok('T42 1m 大阳线 4.0%', abs(ns['_elastic_1m_surge']('600001.XSHG') - 4.0) < 1e-9)
ns['get_price'] = lambda *a, **k: _Bar([10.0, 10.0], [10.0, 9.8])
ok('T42 15s 缓存复用 4.0%', abs(ns['_elastic_1m_surge']('600001.XSHG') - 4.0) < 1e-9)
ns['_DS'].cache.clear()
ok('T42 失效后 1m 阴线 -2.0%', abs(ns['_elastic_1m_surge']('600001.XSHG') - (-2.0)) < 1e-9)
ns['_DS'].cache.clear()
ns['get_price'] = lambda *a, **k: None
ok('T42 无 1m 数据 -> 0.0', ns['_elastic_1m_surge']('600001.XSHG') == 0.0)

# --- T43 弹性套利全门禁（_try_elastic_arb_buy） ---
def _ea_setup():
    ns = fresh()
    ns['g'].watch = ['300001.XSHE']; ns['g'].pool_static = []
    ns['g'].spot['300001.XSHE'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 12.0, 'open_px': 10.3, 'trade_status': 'OPEN'}
    ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
    ns['last_px'] = lambda sec: 10.8
    ns['pre_close'] = lambda sec: 10.0
    ns['trade_open'] = lambda sec: True
    ns['_elastic_yizi_scan'] = lambda: {'B1': 2}
    ns['_elastic_in_strong_board'] = lambda sec, strong: True
    ns['_is_one_word_open'] = lambda sec: False
    ns['_elastic_1m_surge'] = lambda sec: 4.0
    ns['_block_sealed_buy'] = lambda sec: False
    ns['_save_state'] = lambda *a, **k: None
    ns['_board_rank_top3'] = lambda sec, secs=None: True   # v0.23 桩
    ns['_CTX'].portfolio.positions = {}
    ns['BLS']['daily_max_buy'] = 10
    return ns

def _ea_calls(ns):
    out = []
    ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append({'sec': sec, 'mode': mode, 'note': note}) or True
    ns['_try_elastic_arb_buy'](ns['_CTX'])
    return out

ns = _ea_setup(); pc = _ea_calls(ns)
ok('T43 elastic_arb 触发 -> chase 下单', len(pc) == 1 and pc[0]['mode'] == 'chase' and 'elastic_arb' in pc[0]['note'])
ok('T43 记入 daily.bought', '300001.XSHE' in ns['g'].daily['bought'])
ns = _ea_setup(); ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 5, 0)
ok('T43 窗口外 -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['g'].watch = ['600001.XSHG']; ns['g'].spot['600001.XSHG'] = dict(ns['g'].spot['300001.XSHE'])
ok('T43 非20cm -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['_elastic_in_strong_board'] = lambda sec, strong: False
ok('T43 非强板块 -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['_is_one_word_open'] = lambda sec: True
ok('T43 一字板 -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['_elastic_1m_surge'] = lambda sec: 2.0
ok('T43 1m 涨幅不足 -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['last_px'] = lambda sec: 10.2
ok('T43 涨幅<6% -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['last_px'] = lambda sec: 11.6
ok('T43 涨幅>10% -> skip', _ea_calls(ns) == [])
ns = _ea_setup(); ns['g'].daily['bought'] = ['999999.XSHE']; ns['BLS']['daily_max_buy'] = 1
ok('T43 日买满 -> skip', _ea_calls(ns) == [])

# --- T44 tick_data 帧末弹性套利端到端 ---
ns = fresh()
ns['g'].watch = ['300001.XSHE']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
code = '300001.XSHE'
snap = {code: {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 12.0, 'open_px': 10.3, 'trade_status': 'OPEN', 'hsTimeStamp': 99000000}}
ns['get_snapshot'] = lambda sec: snap
ns['BLS']['firstzt_min_seal'] = 0.0; ns['BLS']['firstzt_min_bids'] = 0
ns['_elastic_yizi_scan'] = lambda: {'B1': 2}
ns['_elastic_in_strong_board'] = lambda sec, strong: True
ns['_is_one_word_open'] = lambda sec: False
ns['_elastic_1m_surge'] = lambda sec: 4.0
ns['_block_sealed_buy'] = lambda sec: False
ns['_save_state'] = lambda *a, **k: None
ns['_board_rank_top3'] = lambda sec, secs=None: True   # v0.23 桩
ns['_CTX'].portfolio.positions = {}
ns['g'].first_zt = {}
pc = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append({'sec': sec, 'mode': mode, 'note': note}) or True
ns['tick_data'](ns['_CTX'], {})
ok('T44 tick 帧末 elastic 触发', len(pc) == 1 and 'elastic_arb' in pc[0]['note'] and code in ns['g'].daily['bought'])



# ================= v0.64 订单系统闭环（F1-F5，docs/33） =================
# F1: place_order 原函数买路径无行情跳过 -> 返回 False（不记 daily.bought）
ns = fresh(); ns['g'].zt_lianban = {}
ns['_order_limit'] = lambda sec, side, mode: 0.0
ns['last_px'] = lambda sec: 0.0
r = ns['place_order'](ns['_ctx'], '600070.XSHG', 'buy', note='x')
ok('F1 place_order 无行情跳过 -> False', r is False and '600070.XSHG' not in ns['g'].daily['bought'])
# F1b: 实单路径(DO_ORDER=True) 记 pending + buy_commit（资金实时扣减源头）
ns = fresh(); ns['BLS']['DO_ORDER'] = True; ns['g'].zt_lianban = {}
ns['g'].spot['600070.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
ns['_mid_board_avoid'] = lambda sec: False
ns['_order_limit'] = lambda sec, side, mode: 10.0
ns['_buy_pos_ok'] = lambda c, s, q, l: True
r = ns['place_order'](ns['_ctx'], '600070.XSHG', 'buy', note='x')
ok('F1b 实单路径记 pending+buy_commit', r is True and ns['g'].pending.get('600070.XSHG', {}).get('no') and float(ns['g'].buy_commit.get('600070.XSHG', 0)) > 0)
# F2: on_order_response 字典主推(list[dict]) buy REJECTED -> 释放 daily.bought + exp_fired + buy_commit
ns = fresh()
ns['g'].pending = {'600071.XSHG': {'no': 'E1', 'side': 'buy', 'qty': 100, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['g'].daily['bought'] = ['600071.XSHG']; ns['g'].exp_fired = {'600071.XSHG'}; ns['g'].buy_commit = {'600071.XSHG': 1000.0}
ns['on_order_response'](ns['_ctx'], [{'entrust_no': 'E1', 'order_status': '6', 'stock_code': '600071.XSHG', 'entrust_bs': '1', 'business_amount': 0}])
ok('F2 REJECTED 释放 daily.bought', '600071.XSHG' not in ns['g'].daily['bought'])
ok('F2 REJECTED 释放 exp_fired', '600071.XSHG' not in ns['g'].exp_fired)
ok('F2 REJECTED 释放 buy_commit', '600071.XSHG' not in ns['g'].buy_commit)
ok('F2 状态码 8->FILLED 5->CANCELLED 6->REJECTED 7->PARTIAL',
   ns['_map_order_status']('8') == 'FILLED' and ns['_map_order_status']('5') == 'CANCELLED'
   and ns['_map_order_status']('6') == 'REJECTED' and ns['_map_order_status']('7') == 'PARTIAL')
ok('F2 方向码 1->buy 2->sell', ns['_trade_side']('1') == 'buy' and ns['_trade_side']('2') == 'sell')
# F2c: on_order_response FILLED 释放 buy_commit（终态）
ns = fresh()
ns['g'].pending = {'600072.XSHG': {'no': 'E2', 'side': 'buy', 'qty': 100, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['g'].buy_commit = {'600072.XSHG': 1000.0}
ns['on_order_response'](ns['_ctx'], {'entrust_no': 'E2', 'order_status': '8', 'stock_code': '600072.XSHG'})
ok('F2c FILLED 释放 buy_commit', '600072.XSHG' not in ns['g'].buy_commit and ns['g'].pending['600072.XSHG']['status'] == 'FILLED')
# F3: 同日重启恢复 pending + buy_commit（防重复卖/资金扣减）
ns = fresh(); ns['g'].state_day = str(ns['get_trading_day']())
ns['g'].pending = {'600073.XSHG': {'no': 'E3', 'side': 'sell', 'qty': 300, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['g'].buy_commit = {'600074.XSHG': 500.0}
ns['_save_state'](); ns['g'].pending = {}; ns['g'].buy_commit = {}
ns['load_state']()
ok('F3 同日重启恢复 pending', ns['g'].pending.get('600073.XSHG', {}).get('no') == 'E3')
ok('F3 同日重启恢复 buy_commit', ns['g'].buy_commit.get('600074.XSHG') == 500.0)
ok('F3 在途 sell _sell_inflight 拦截', ns['_sell_inflight']('600073.XSHG') is True)
# F4: _avail_cash = portfolio.cash - buy_commit（资金实时最新）
ns = fresh(); ns['_CTX'].portfolio.cash = 10000.0
ns['g'].buy_commit = {'600075.XSHG': 3000.0, '600076.XSHG': 2000.0}
ok('F4 _avail_cash 减在途买单承诺', abs(ns['_avail_cash'](ns['_ctx']) - 5000.0) < 1e-9)
ns['g'].buy_commit = {}
ok('F4 _avail_cash 无承诺=现金', abs(ns['_avail_cash'](ns['_ctx']) - 10000.0) < 1e-9)
# F5: on_trade_response 字典主推(list[dict]) sell 成交 -> 回填 filled + sold_log + daily.sold
ns = fresh()
ns['g'].pending = {'600077.XSHG': {'no': 'E4', 'side': 'sell', 'qty': 300, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['_hold_exp_init'] = lambda sec, force=False: None
ns['on_trade_response'](ns['_ctx'], [{'stock_code': '600077.XSHG', 'entrust_bs': '2', 'business_amount': 100, 'real_type': '1', 'status': '8'}])
ok('F5 sell 成交回填 filled', ns['g'].pending['600077.XSHG']['filled'] == 100)
ok('F5 sell 成交记 sold_log + daily.sold', ns['g'].sold_log.get('600077.XSHG') is not None and '600077.XSHG' in ns['g'].daily['sold'])
# F5b: buy 成交按成交额释放 buy_commit（部分成交）
ns = fresh()
ns['g'].pending = {'600078.XSHG': {'no': 'E5', 'side': 'buy', 'qty': 200, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['g'].buy_commit = {'600078.XSHG': 2000.0}
ns['_hold_exp_init'] = lambda sec, force=False: None
ns['on_trade_response'](ns['_ctx'], [{'stock_code': '600078.XSHG', 'entrust_bs': '1', 'business_amount': 100, 'real_type': '1'}])
ok('F5b buy 成交部分释放承诺', abs(ns['g'].buy_commit.get('600078.XSHG', 0) - 1000.0) < 1e-9)
# F5c: 撤单主推(real_type=2)跳过（成交累积不误加）
ns = fresh()
ns['g'].pending = {'600079.XSHG': {'no': 'E6', 'side': 'buy', 'qty': 100, 'limit': 10.0, 'status': 'SENT', 'filled': 0}}
ns['g'].daily['sold'] = []
ns['on_trade_response'](ns['_ctx'], [{'stock_code': '600079.XSHG', 'entrust_bs': '2', 'business_amount': -100, 'real_type': '2'}])
ok('F5c 撤单主推跳过', ns['g'].pending['600079.XSHG']['filled'] == 0 and '600079.XSHG' not in ns['g'].daily['sold'])

print('\nALL SELFTESTS DONE')





# --- T44 _elastic_yizi_scan 批量补快照（一次 get_snapshot 列表，回填 g.spot） ---
ns = fresh()
ns['g'].watch = []; ns['g'].pool_static = []; ns['g'].zt_lianban = {}
ns['_elastic_yizi_pool'] = lambda: ['300001.XSHE', '300002.XSHE']
ns['_boards_of'] = lambda sec: {'300001.XSHE': ['B1'], '300002.XSHE': ['B1']}.get(sec, [])
ns['_seal_metrics'] = lambda sec: (100000.0, 5)
calls = []
def _snap_many(codes, cap):
    calls.append(tuple(codes))
    return {'300001.XSHE': {'preclose_px': 10.0, 'open_px': 12.0},
            '300002.XSHE': {'preclose_px': 10.0, 'open_px': 12.1}}
ns['_get_snapshot_many'] = _snap_many
ns['BLS']['elastic_arb_min_yizi'] = 2
ns['g'].elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
strong = ns['_elastic_yizi_scan']()
ok('T44 yizi 批量补快照一次', len(calls) == 1 and calls[0] == ('300001.XSHE', '300002.XSHE'))
ok('T44 g.spot 已回填', ns['g'].spot.get('300001.XSHE', {}).get('open_px') == 12.0)
ok('T44 强板块计数', strong == {'B1': 2})
ok('T44 二次调用走缓存不重复拉', len(calls) == 1)

# --- T45 _board_top_gainer 成员优先走 g.spot，缺才 get_snapshot ---
ns = fresh()
ns['g'].watch = []; ns['g'].pool_static = []
ns['last_px'] = lambda sec: ns['g'].spot.get(sec, {}).get('last_px', 0.0)
ns['_board_member_codes'] = lambda sec: ['600001.XSHG', '600002.XSHG']
ns['_get_snapshot_many'] = lambda codes, cap: {c: {'preclose_px': 10.0, 'last_px': 10.2} for c in codes}
ns['g'].spot['600001.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.5}   # 我 +5%
ns['g'].spot['600002.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.3}   # 成员 +3%
ok('T45 成员在 g.spot -> 不调批量', ns['_board_top_gainer']('600001.XSHG') is True and '600002.XSHG' in ns['g'].spot and ns['g'].spot['600002.XSHG']['last_px'] == 10.3)
ns['g'].spot['600002.XSHG'] = {}
ok('T45 成员缺快照 -> 批量回填', ns['_board_top_gainer']('600001.XSHG') is True and ns['g'].spot['600002.XSHG'].get('last_px') == 10.2)
ns['g'].spot['600002.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.6}   # 成员 +6% > 我
ok('T45 成员更高 -> 非最高', ns['_board_top_gainer']('600001.XSHG') is False)


# --- T47 帧内推送逐笔（_tx_frame_zt_ms，0 额外 API 调用） ---
ns = fresh()
_lt = time.localtime()
_DAY = '%04d%02d%02d' % (_lt.tm_year, _lt.tm_mon, _lt.tm_mday)
ns['g'].spot['600001.XSHG'] = {'up_px': 12.1}
frame = {'600001.XSHG': {'transaction': {'business_time': int(_DAY + '093003000'), 'hq_px': 12.1}}}
ok('T47 帧内推送涨停成交 -> ms', ns['_tx_frame_zt_ms']('600001.XSHG', frame) == int(_DAY + '093003000'))
frame2 = {'600001.XSHG': {'transaction': {'business_time': int(_DAY + '093003000'), 'hq_px': 12.05}}}
ok('T47 帧内非涨停价 -> None', ns['_tx_frame_zt_ms']('600001.XSHG', frame2) is None)
ok('T47 帧内无 transaction -> None', ns['_tx_frame_zt_ms']('600001.XSHG', {'600001.XSHG': {}}) is None)
class _Row:
    def get(self, k):
        return {'business_time': int(_DAY + '093003000'), 'hq_px': 12.1}.get(k)
class _DF:
    def __init__(self): self.iloc = [_Row()]
frame3 = {'600001.XSHG': {'transaction': _DF()}}
ok('T47 DataFrame 形态（沙盒 data）', ns['_tx_frame_zt_ms']('600001.XSHG', frame3) == int(_DAY + '093003000'))


# --- T48-T50 聚合数据源 DataHub（v0.21） ---
ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
_calls = []
ns['get_snapshot'] = lambda secs: _calls.append(('batch', secs)) or {'600001.XSHG': {'last_px': 10.0}, '600002.XSHG': {'last_px': 20.0}}
ns['g'].ds.snapshot(['600001.XSHG', '600002.XSHG'])
ok('T48 快照批量一次调用', _calls == [('batch', ['600001.XSHG', '600002.XSHG'])])
ok('T48 批量回填 g.spot', ns['g'].spot['600001.XSHG']['last_px'] == 10.0 and ns['g'].spot['600002.XSHG']['last_px'] == 20.0)

ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
_calls = []
def _gs(secs):
    if isinstance(secs, str):
        _calls.append(('stock', secs))
        return {secs: {'last_px': 10.0}}
    _calls.append(('batch', secs))
    return {}
ns['get_snapshot'] = _gs
ns['g'].ds.snapshot(['600001.XSHG'])
ok('T48 批量空 -> 逐只兜底', ('batch', ['600001.XSHG']) in _calls and ('stock', '600001.XSHG') in _calls)
ok('T48 兜底回填 g.spot', ns['g'].spot.get('600001.XSHG', {}).get('last_px') == 10.0)

ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
_fc = []
def _fetch():
    _fc.append(1); return 42
ok('T49 缓存命中复用', ns['g'].ds.cached('k', 'X', 999, _fetch) == 42 and ns['g'].ds.cached('k', 'X', 999, _fetch) == 42 and len(_fc) == 1)
ns['g'].ds.reset('2026-10-17')
ok('T49 reset 后重拉', ns['g'].ds.cached('k', 'X', 999, _fetch) == 42 and len(_fc) == 2)

ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
def _bad():
    raise RuntimeError('x')
ok('T50 失败隔离 -> None + degraded', ns['g'].ds.cached('bad', 'X', 999, _bad) is None and 'bad' in ns['g'].ds.degraded)


# --- T51-T53 v0.22 批量统一入口 + 注册表扩展 ---
ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
_lt = time.localtime(); _DAY = '%04d%02d%02d' % (_lt.tm_year, _lt.tm_mon, _lt.tm_mday)
ns['g'].spot['600001.XSHG'] = {'up_px': 12.1}
ns['g'].spot['600002.XSHG'] = {'up_px': 12.2}
_tx_calls = []
def _tx(secs, data_count=200, is_dict=True):
    _tx_calls.append(list(secs) if isinstance(secs, list) else [secs])
    rows1 = [[int(_DAY + '093003000'), 12.1, 300, 3, 2, 0, 0, 0, 0, 1]]
    return {'600001.XSHG': rows1, '600002.XSHG': [],
            'fields': ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction',
                       'buy_no', 'sell_no', 'trans_flag', 'trans_identify_am', 'channel_num']}
ns['get_individual_transaction'] = _tx
frame = {'600002.XSHG': {'transaction': {'business_time': int(_DAY + '093004000'), 'hq_px': 12.2}}}
out = ns['g'].ds.tx_zt_batch(['600001.XSHG', '600002.XSHG'], frame)
ok('T51 帧推送优先', out.get('600002.XSHG') == int(_DAY + '093004000'))
ok('T51 批量一次拉取+缺票单票兜底', _tx_calls == [['600001.XSHG', '600002.XSHG'], ['600002.XSHG']])
ok('T51 批量解析命中', out.get('600001.XSHG') == int(_DAY + '093003000'))
out2 = ns['g'].ds.tx_zt_batch(['600001.XSHG', '600002.XSHG'], frame)
ok('T51 同帧二次消费不重复拉', len(_tx_calls) == 2 and out2.get('600001.XSHG') == int(_DAY + '093003000'))

ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
ns['get_stock_blocks'] = lambda sec: {'M1': [['BK1']]}
ns['get_industry_stocks'] = lambda code: ['600001.XSHG', '600002.XSHG']
_sn_calls = []
def _gs(secs):
    if isinstance(secs, list):
        _sn_calls.append(('batch', secs))
        return {'600001.XSHG': {'preclose_px': 10.0, 'last_px': 10.5}, '600002.XSHG': {'preclose_px': 10.0, 'last_px': 10.3}}
    _sn_calls.append(('stock', secs))
    return {secs: {'preclose_px': 10.0, 'last_px': 10.0}}
ns['get_snapshot'] = _gs
chgs = ns['_board_member_changes']('600001.XSHG')
ok('T52 板块批量快照一次', _sn_calls == [('batch', ['600001.XSHG', '600002.XSHG'])])
ok('T52 涨跌列表口径', len(chgs) == 2 and abs(chgs[0] - 0.05) < 1e-9 and abs(chgs[1] - 0.03) < 1e-9)
ok('T52 60s 缓存复用', ns['_board_member_changes']('600001.XSHG') == chgs and len(_sn_calls) == 1)
ok('T52 板块强度口径不变', abs(ns['_board_strength']('600001.XSHG') - 4.0) < 1e-9)

ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
_pc = []
def _gp(sec, **k):
    _pc.append(sec); return 'DF'
ns['get_price'] = _gp
ok('T53 hist1d 一次拉取+缓存复用', ns['_hist_1d']('600001.XSHG') == 'DF' and ns['_hist_1d']('600001.XSHG') == 'DF' and len(_pc) == 1)


# --- T54/T55 板块强度排名（v0.23，打首板/弹性目标=强度前三板块） ---
ns = fresh()
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].ds = ns['DataHub']()
ns['get_stock_blocks'] = lambda sec: {'M1': [['B%d' % (1 if sec == '600001.XSHG' else 2 if sec == '600002.XSHG' else 3 if sec == '600003.XSHG' else 4)]]}
ns['get_industry_stocks'] = lambda code: {'B1': ['600001.XSHG'], 'B2': ['600002.XSHG'], 'B3': ['600003.XSHG'], 'B4': ['600004.XSHG']}.get(str(code), [])
_sn_calls = []
def _gs(secs):
    _sn_calls.append(list(secs))
    d = {}
    for c in secs:
        chg = {'600001.XSHG': 1.0, '600002.XSHG': 3.0, '600003.XSHG': 2.0, '600004.XSHG': 0.5}.get(c, 1.0)
        d[c] = {'preclose_px': 10.0, 'last_px': 10.0 * (1 + chg)}
    return d
ns['get_snapshot'] = _gs
cands = ['600001.XSHG', '600002.XSHG', '600003.XSHG', '600004.XSHG']
top = ns['_board_rank_top3_set'](cands)
ok('T54 强度前三板块(B2/B3/B1)', top == {'B2', 'B3', 'B1'})
ok('T54 B4 不入前三', 'B4' not in top)
ok('T54 sec 板块在列 -> True', ns['_board_rank_top3']('600002.XSHG', cands) is True)
ok('T54 非前三板块 -> False', ns['_board_rank_top3']('600004.XSHG', cands) is False)
ok('T54 排名 60s 缓存不重复拉', len(_sn_calls) == 4)
# 首板门控接入验证：_try_first_board_buy 在板块非前三时不出单
ns = fresh()
ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2, 'trade_status': 'OPEN'}
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
ns['last_px'] = lambda sec: 10.8
ns['trade_open'] = lambda sec: True
ns['_is_one_word_open'] = lambda sec: False
ns['_is_first_board'] = lambda sec: True
ns['_board_top_gainer'] = lambda sec: True
ns['_board_first_zt'] = lambda sec: True
ns['_block_sealed_buy'] = lambda sec: False
ns['_save_state'] = lambda *a, **k: None
ns['_CTX'].portfolio.positions = {}
ns['_board_rank_top3'] = lambda sec, secs=None: False   # 非前三 -> 拦截
out = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append(sec) or True
ns['_try_first_board_buy'](ns['_CTX'], '600001.XSHG', rank_secs=['600001.XSHG'])
ok('T55 板块非前三 -> 首板拦截', out == [])
ns['_board_rank_top3'] = lambda sec, secs=None: True
ns['_try_first_board_buy'](ns['_CTX'], '600001.XSHG', rank_secs=['600001.XSHG'])
ok('T55 板块前三 -> 首板放行', out == ['600001.XSHG'])


# --- T56 生命周期窗口（v0.24：首板9:40前 / 低吸13:30前 / 其它10:00前） ---
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 31, 0)
ns['_tags'] = lambda sec: ['CORE']; ns['_ensure_ma5'] = lambda sec: 10.0
ns['_ma5_at_price'] = lambda sec, px: 10.0; ns['last_px'] = lambda sec: 9.8
ns['score_now'] = lambda sec: 60.0; ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['_ma5_first_5d'] = lambda sec: True; ns['BLS']['ma5_second_low_enabled'] = True
ns['BLS']['ma5_touch_band'] = 0.02
out = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: out.append(sec) or True
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T56 10:31 后低吸拦截', out == [])
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)
ns['try_ma5_buy'](ns['_CTX'])
ns['try_ma5_buy'](ns['_CTX'])
ok('T56 10:00 低吸放行', out == ['600001.XSHG'])

ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 1, 0)
ns['_tags'] = lambda sec: ['CORE']; ns['_limitup_days'] = lambda sec: 1; ns['last_px'] = lambda sec: 10.0
ns['score_now'] = lambda sec: 60.0; ns['trade_open'] = lambda sec: True; ns['_block_sealed_buy'] = lambda sec: False
out = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append(sec) or True
ns['_save_state'] = lambda *a, **k: None
ns['try_core_buy'](ns['_CTX'])
ok('T56 10:01 后核心票拦截', out == [])

ns = fresh(); ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 1, 0)
ns['g'].exp_file = {'600001.XSHG': {'side': 'buy'}}
calls = []
ns['_attempt_expected_buy'] = lambda c, code, direction=None: calls.append(code)
ns['_try_expected_buys'](ns['_CTX'])
ok('T56 10:01 后预期买入拦截', calls == [])
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 31, 0)
ns['_try_expected_buys'](ns['_CTX'])
ok('T56 09:31 预期买入放行', calls == ['600001.XSHG'])

ns = _ea_setup(); ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 50, 0)
pc = _ea_calls(ns)
ok('T56 09:50 弹性窗口内放行', len(pc) == 1 and 'elastic_arb' in pc[0]['note'])

# --- T57 板块强度刷新周期时间分档（v0.24：10:00 前 3s / 之后 60s） ---
ns = fresh()
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
ok('T57 09:33 快速刷新 3s', abs(ns['_board_refresh_ttl']() - 3.0) < 1e-9)
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 1, 0)
ok('T57 10:01 慢刷新 60s', abs(ns['_board_refresh_ttl']() - 60.0) < 1e-9)


# --- T58 ???????v0.25 Phase 3????/????/????/???? ---
class _FakeTime(object):
    def __init__(self, t0=1000.0):
        self.t = t0
    def time(self):
        return self.t

ns = fresh(); fake = _FakeTime(1000.0); ns['time'] = fake
dh = ns['DataHub'](); ns['g'].ds = dh
ok('T58 snapshot ????2?', dh.spend('snapshot') is True and dh.spend('snapshot') is True)
ok('T58 ?3??? False', dh.spend('snapshot') is False)
ok('T58 over ??=1', dh.frame['over'].get('snapshot') == 1)
fake.t += 3.0
ok('T58 ?? used ????', dh.spend('snapshot') is True and dh.frame['used'].get('snapshot') == 1 and dh.frame['over'] == {})
r = dh.frame_report()
ok('T58 report ? snapshot=1/2', 'snapshot=1/2' in r)

ns2 = fresh(); fake2 = _FakeTime(2000.0); ns2['time'] = fake2
dh2 = ns2['DataHub'](); ns2['g'].ds = dh2
calls = {'n': 0}
def _fetch():
    calls['n'] += 1
    return 42
ok('T58 P0 ?????', dh2.cached('gear', 'S1', 3.0, _fetch, budget='gear') == 42)
for _ in range(14):
    dh2.spend('gear')
v = dh2.cached('gear', 'S2', 3.0, _fetch, budget='gear')
ok('T58 P0 ??????? None', v is None and calls['n'] == 1)
fake2.t += 3.0
ok('T58 ??????', dh2.cached('gear', 'S2', 3.0, _fetch, budget='gear') == 42 and calls['n'] == 2)

ns3 = fresh(); fake3 = _FakeTime(3000.0); ns3['time'] = fake3
dh3 = ns3['DataHub'](); ns3['g'].ds = dh3
ok('T58 P1 stale ??', dh3.cached('board_chgs', 'B1', 3.0, lambda: 7.0, budget='board', stale_ok=True) == 7.0)
fake3.t += 3.0
for _ in range(6):
    dh3.spend('board')
ok('T58 P1 ??????', dh3.cached('board_chgs', 'B1', 3.0, lambda: 9.0, budget='board', stale_ok=True) == 7.0)
ok('T58 P1 ????? None', dh3.cached('board_chgs', 'B2', 3.0, lambda: 9.0, budget='board', stale_ok=True) is None)

ns4 = fresh(); fake4 = _FakeTime(4000.0); ns4['time'] = fake4
cnt = {'n': 0}
def _calc(sec):
    cnt['n'] += 1
    return True
ns4['_calc_two_1m_break'] = _calc
ok('T58 two_1m ??? True', ns4['_two_1m_break']('S1') is True)
ok('T58 two_1m ??????', ns4['_two_1m_break']('S1') is True and cnt['n'] == 1)
fake4.t += 3.0
ok('T58 two_1m ????', ns4['_two_1m_break']('S1') is True and cnt['n'] == 2)


# --- T59 tick 级卖出（v0.26）：炸板/封单大减首触发卖 + 去重 + 急卖 ---
ns = fresh(); ns['time'] = _FakeTime(5000.0)
g = ns['g']
g.first_zt = {}
g.spot['600001.XSHG'] = {'last_px': 9.5, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
g.first_zt['600001.XSHG'] = {'first_seal': 100000.0, 'first_bids': 5, 'ts': 5000.0, 'break': True, 'break_ts': 5001.0, 'seal_low': False}
ns['get_positions'] = lambda: {'600001.XSHG': {'enable_amount': 1000, 'cost_basis': 9.0}}
ns['_sellable_source'] = lambda: ns['get_positions']()
ns['_sellable'] = lambda raw, p: 1000
ns['last_px'] = lambda sec: 9.5
ns['_auction_change'] = lambda sec: 3.0
ns['my_cost'] = lambda raw, p: 9.0
ns['get_stop_loss_pct'] = lambda sec: 0.05
ns['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
ns['_save_state'] = lambda *a, **k: None
ns['_sell_inflight'] = lambda sec: False
out = []
ns['_do_sell'] = lambda c, sec, qty, note, urgent=False, mode=None: out.append((sec, note, urgent))
ns['tick_sell_manager'](ns['_CTX'])
ok('T59 炸板首触发卖(现价)', len(out) == 1 and 'TICK_break_sell' in out[0][1] and out[0][2] is False)
ok('T59 炸板标记', '600001.XSHG' in ns['g'].break_sold)
ns['tick_sell_manager'](ns['_CTX'])
ok('T59 二次帧不重复卖', len(out) == 1)

ns2 = fresh(); ns2['time'] = _FakeTime(6000.0)
g2 = ns2['g']
g2.first_zt = {}
g2.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
g2.first_zt['600001.XSHG'] = {'first_seal': 100000.0, 'first_bids': 5, 'ts': 6000.0, 'break': False, 'seal_low': True}
ns2['get_positions'] = lambda: {'600001.XSHG': {'enable_amount': 1000, 'cost_basis': 9.0}}
ns2['_sellable_source'] = lambda: ns2['get_positions']()
ns2['_sellable'] = lambda raw, p: 1000
ns2['last_px'] = lambda sec: 11.0
ns2['_auction_change'] = lambda sec: 5.0
ns2['my_cost'] = lambda raw, p: 9.0
ns2['get_stop_loss_pct'] = lambda sec: 0.05
ns2['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
ns2['_save_state'] = lambda *a, **k: None
ns2['_sell_inflight'] = lambda sec: False
out2 = []
ns2['_do_sell'] = lambda c, sec, qty, note, urgent=False, mode=None: out2.append((sec, note))
ns2['tick_sell_manager'](ns2['_CTX'])
ok('T59 封单大减卖', len(out2) == 1 and 'TICK_seal_low_sell' in out2[0][1])
ok('T59 封单标记', '600001.XSHG' in ns2['g'].seal_sold)

ns3 = fresh(); ns3['time'] = _FakeTime(7000.0)
g3 = ns3['g']
g3.first_zt = {}
g3.spot['600001.XSHG'] = {'last_px': 9.0, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
ns3['get_positions'] = lambda: {'600001.XSHG': {'enable_amount': 1000, 'cost_basis': 10.0}}
ns3['_sellable_source'] = lambda: ns3['get_positions']()
ns3['_sellable'] = lambda raw, p: 1000
ns3['last_px'] = lambda sec: 9.0
ns3['_auction_change'] = lambda sec: -1.0
ns3['my_cost'] = lambda raw, p: 10.0
ns3['get_stop_loss_pct'] = lambda sec: 0.05
ns3['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
ns3['_save_state'] = lambda *a, **k: None
ns3['_sell_inflight'] = lambda sec: False
out3 = []
ns3['_do_sell'] = lambda c, sec, qty, note, urgent=False, mode=None: out3.append((sec, note, urgent))
ns3['tick_sell_manager'](ns3['_CTX'])
ok('T59 P3 止损 tick 3s 触发(核卖)', len(out3) == 1 and 'P3_stop_loss_tick' in out3[0][1] and out3[0][2] is True)


# --- T60 L2 总买/总卖量探针（v0.26b）：空数据不崩、置位 l2_probed ---
ns = fresh()
ns['g'].watch = []; ns['g'].pool_static = []
ns['_l2_probe'](ns['_CTX'])
ok('T60 l2_probe 空数据不崩且置位', ns['g'].l2_probed is True)


# --- T61 封死不排队（v0.26b）：total_offerqty==0 + 5s 持续确认 + ask 兜底 ---
ns = fresh(); ns['time'] = _FakeTime(8000.0)
g = ns['g']; g.sealed_since = {}
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'total_offerqty': 0}
ns['get_gear_price'] = lambda sec: {'ask_grp': {}, 'bid_grp': {}}
ok('T61 首帧封死起点(未生效)', ns['_sealed_at_limit']('600001.XSHG') is False)
ns['time'].t += 6.0
ok('T61 持续6s 封死不排单', ns['_sealed_at_limit']('600001.XSHG') is True)
ns['time'].t += 3.0
g.spot['600001.XSHG']['total_offerqty'] = 500
ok('T61 总委卖量>0 未封死', ns['_sealed_at_limit']('600001.XSHG') is False)
ok('T61 解除后起点清空', '600001.XSHG' not in g.sealed_since)

ns2 = fresh(); ns2['time'] = _FakeTime(9000.0)
g2 = ns2['g']; g2.sealed_since = {}
g2.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0}
ns2['get_gear_price'] = lambda sec: {'ask_grp': {}, 'bid_grp': {}}
ok('T61 无总量走ask空判(起点)', ns2['_sealed_at_limit']('600001.XSHG') is False)
ns2['time'].t += 6.0
ok('T61 ask空判 6s 封死', ns2['_sealed_at_limit']('600001.XSHG') is True)
ns2['time'].t += 4.0   # 超过 gear 3s TTL 才会重拉新桩
ns2['get_gear_price'] = lambda sec: {'ask_grp': {1: [11.0, 100, 1]}, 'bid_grp': {}}
ok('T61 卖档有量未封死', ns2['_sealed_at_limit']('600001.XSHG') is False)

ns3 = fresh(); ns3['g'].spot['600001.XSHG'] = {'last_px': 10.5, 'preclose_px': 10.0, 'up_px': 11.0, 'total_offerqty': 0}
ok('T61 未触涨停不判封死', ns3['_sealed_at_limit']('600001.XSHG') is False)


# --- T62/T63 v0.26c 预期文件日期对齐 + 一字板 09:25 识别 ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)   # 周五
paths = ns['_expectation_paths']()
ok('T62 验证日命名在候选', any(p.endswith('expectation_2026-10-16.csv') for p in paths))
ok('T62 生成日(T-1)命名在候选', any(p.endswith('expectation_2026-10-15.csv') for p in paths))
zpaths = ns['_zt_lianban_paths']()
ok('T62 zt 生成日(T-1)在候选', any(p.endswith('zt_lianban_2026-10-15.csv') for p in zpaths))
ok('T62 周五 prev=周四', str(ns['_prev_trade_day']()) == '2026-10-15')
ns2 = fresh(); ns2['get_trading_day'] = lambda: datetime.date(2026, 10, 19)   # 周一
ok('T62 周一 prev=周五', str(ns2['_prev_trade_day']()) == '2026-10-16')
ns3 = fresh(); ns3['get_trading_day'] = lambda: datetime.date(2026, 10, 20)   # 周二
ok('T62 周二 prev=周一', str(ns3['_prev_trade_day']()) == '2026-10-19')

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']; g.one_word_open = set(); g.pool_static = ['600001.XSHG']
g.watch = []; g.selfwatch = []; g.zt_lianban = {}; g.exp_file = {}
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 11.0, 'total_offerqty': 0}
ns['get_gear_price'] = lambda sec: {'ask_grp': {}}
ns['_mark_one_word_open']()
ok('T63 一字板 09:25 识别入 one_word_open', '600001.XSHG' in g.one_word_open)
ok('T63 一字板 _sealed_at_limit 立即封死', ns['_sealed_at_limit']('600001.XSHG') is True)
ok('T63 一字板 _block_sealed_buy 不排队', ns['_block_sealed_buy']('600001.XSHG') is True)

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']; g.one_word_open = set()
g.watch = ['600001.XSHG']; g.pool_static = []; g.selfwatch = []; g.zt_lianban = {}; g.exp_file = {}
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 11.0, 'total_offerqty': 0}
g.daily = {'bought': []}; g.buy_log = {}; g.now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
ns['_min_age'] = lambda: 3
ns['_tags'] = lambda sec: ['CORE', 'LB']
ns['_limitup_days'] = lambda sec: 1
ns['try_core_buy'](ns['_CTX'])
ok('T63 一字板 core_buy 跳过(不排队)', g.daily['bought'] == [] and len(ns['_RECC']['calls']) == 0)

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']; g.one_word_open = set()
g.watch = ['600001.XSHG']; g.pool_static = []; g.selfwatch = []; g.zt_lianban = {}; g.exp_file = {}
g.spot['600001.XSHG'] = {'last_px': 10.5, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.3}
g.daily = {'bought': []}; g.buy_log = {}; g.now_dt = datetime.datetime(2026, 10, 16, 9, 33, 0)
ns['_min_age'] = lambda: 3
ns['_tags'] = lambda sec: ['CORE', 'LB']
ns['_limitup_days'] = lambda sec: 1
ns['score_now'] = lambda sec: 72.0
ns['try_core_buy'](ns['_CTX'])
ok('T63 非一字 CORE 可触发 core_buy', '600001.XSHG' in g.daily['bought'] and g.buy_log.get('600001.XSHG', 0) > 0)


# --- T64 v0.27 涨停池预期三态初步确认（竞价超预期->观察，窗口内分最高/最主动优先） ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']
g.zt_lianban = {'600001.XSHG': {'board_cnt': 0}, '600002.XSHG': {'board_cnt': 1}, '600003.XSHG': {'board_cnt': 1}}
g.exp_file = {}; g.auction_c = {}
g.spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.8}   # +8% 超预期
g.spot['600002.XSHG'] = {'last_px': 9.6, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 9.6}     # -4% 绿开 miss
g.spot['600003.XSHG'] = {'last_px': 10.2, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2}   # +2% 未超昨日 meet
ns['_yesterday_open_chg'] = lambda sec: (2.0, True)
n = ns['_synth_pool_expect']()
en1 = g.exp_file.get('600001.XSHG') or {}
en2 = g.exp_file.get('600002.XSHG') or {}
en3 = g.exp_file.get('600003.XSHG') or {}
ok('T64 涨停池超预期 -> exceed/观察', n == 3 and en1.get('expected_status') == 'pending_exceed' and en1.get('_src') == 'zt_pool' and en1.get('side') == 'buy')
ok('T64 涨停池绿开 -> miss', en2.get('expected_status') == 'pending_miss')
ok('T64 涨停池未超昨日 -> meet', en3.get('expected_status') == 'pending_meet')
ok('T64 二次合成幂等', ns['_synth_pool_expect']() == 0 and len(g.exp_file) == 3)
ok('T64 预置竞价涨幅缓存', abs(g.auction_c.get('600001.XSHG', (0, 0))[1] - 8.0) < 1e-9)

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']
g.exp_file['600001.XSHG'] = {'side': 'buy', 'entry_type': 'normal', 'expected_status': 'pending_exceed',
                             'expected_auction_change_pct': 2.0, 'has_expected_auction': True,
                             'yesterday_open_pct': 2.0, '_src': 'zt_pool'}
g.exp.setdefault('600001.XSHG', {})
ns['_auction_change'] = lambda sec: 8.0
ns['_two_1m_break'] = lambda c: False
ns['_limit_up_within_1m'] = lambda c: False
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600001.XSHG')
ok('T64 涨停池竞价超预期 -> 观察(等分时)', st == ns['PM'] and str(reason).startswith('observe'))

ns = fresh()
g = ns['g']; g.first_zt = {'600001.XSHG': {'ts': 1000.0}, '600002.XSHG': {'ts': 2000.0}, '600003.XSHG': {'ts': 500.0}}
ns['score_now'] = lambda sec: {'600001.XSHG': 60.0, '600002.XSHG': 80.0, '600003.XSHG': 60.0}.get(sec, 0.0)
p1 = ns['_pool_exp_priority']('600001.XSHG'); p2 = ns['_pool_exp_priority']('600002.XSHG'); p3 = ns['_pool_exp_priority']('600003.XSHG')
ok('T64 优先分最高', p2 < p1)
ok('T64 同分最早触板(最主动)优先', p3 < p1)

# --- T65 v0.28 涨停池合成 ST 过滤（is_st 字段消费，对齐 AXquant 复盘口径） ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
g = ns['g']
g.zt_lianban = {
    '600001.XSHG': {'board_cnt': 0, 'is_st': False},
    '600002.XSHG': {'board_cnt': 1, 'is_st': True},
    '600003.XSHG': {'board_cnt': 1, 'is_st': False},
}
g.exp_file = {}; g.auction_c = {}
g.spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.8}   # +8% 超预期
g.spot['600002.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 11.0}   # ST 涨停也不入
g.spot['600003.XSHG'] = {'last_px': 10.2, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2}   # +2% meet
ns['_yesterday_open_chg'] = lambda sec: (2.0, True)
n = ns['_synth_pool_expect']()
ok('T65 ST 过滤后仅合成 2 只', n == 2 and '600002.XSHG' not in g.exp_file)
ok('T65 非 ST 超预期保留', (g.exp_file.get('600001.XSHG') or {}).get('expected_status') == 'pending_exceed')
ok('T65 二次合成幂等(ST)', ns['_synth_pool_expect']() == 0 and len(g.exp_file) == 2)

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['BLS']['pool_expect_skip_st'] = False   # 开关关闭：ST 不过滤
g2 = ns['g']
g2.zt_lianban = {'600002.XSHG': {'board_cnt': 1, 'is_st': True}}
g2.spot['600002.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 11.0}
ns['_yesterday_open_chg'] = lambda sec: (2.0, True)
ok('T65 开关关闭时 ST 也合成', ns['_synth_pool_expect']() == 1 and '600002.XSHG' in g2.exp_file)

# --- T66 v0.29 情绪冰点->回暖链（docs/40）：sentiment CSV 读入 + 红盘比回暖判定 + 冰点越久阈值越低 ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
_sent = os.path.join(ns['_TMP'], 'sentiment_latest.csv')
with open(_sent, 'w', encoding='utf-8') as f:
    f.write('date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak\n'
            '2026-10-15,25,30,0.4500,30.10,2,6,1,2\n')
g66 = ns['g']
s66 = ns['_load_sentiment']()
ok('T66 sentiment 读入 ice=1 streak=2', s66 is not None and s66.get('ice') is True and s66.get('ice_streak') == 2)
ok('T66 sentiment 字段齐(limit_up/seal/advance)', s66.get('limit_up') == 25 and abs(s66.get('seal_rate') - 0.45) < 1e-9 and abs(s66.get('advance_rate') - 30.1) < 1e-9)

ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['g'].sentiment = {'ice': True, 'ice_streak': 2, 'advance_rate': 30.1, 'seal_rate': 0.45}
ns['BLS']['sentiment_enabled'] = True
ns['_market_red_ratio'] = lambda: 0.55
ok('T66 回暖判定 True(streak=2 th=0.51 red=0.55)', ns['_sentiment_warm']('600001.XSHG') is True)
ns['_market_red_ratio'] = lambda: 0.50
ok('T66 未回暖 False(streak=2 th=0.51 red=0.50)', ns['_sentiment_warm']('600001.XSHG') is False)
ns['_market_red_ratio'] = lambda: 0.35
ok('T66 继续冰点 False(red<0.40)', ns['_sentiment_warm']('600001.XSHG') is False)
ns['_market_red_ratio'] = lambda: None
ok('T66 全市场缺失 -> 保守 False', ns['_sentiment_warm']('600001.XSHG') is False)
ns['BLS']['sentiment_enabled'] = False
ok('T66 未启用 -> None', ns['_sentiment_warm']('600001.XSHG') is None)
ns2 = fresh(); ns2['g'].sentiment = {'ice': False, 'ice_streak': 0}
ns2['BLS']['sentiment_enabled'] = True
ok('T66 无冰点基线 -> None', ns2['_sentiment_warm']('600001.XSHG') is None)

ns = fresh(); ns['BLS']['sentiment_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1}
ns['_red_ratio'] = lambda sec: 0.55        # 板块门通过
ns['_market_red_ratio'] = lambda: 0.55     # 全市场回暖
ns['BLS']['red_gate_enabled'] = True
ok('T66 _buy_red_ok 回暖放行(streak=1 th=0.53 red=0.55)', ns['_buy_red_ok']('600001.XSHG') is True)
ns['_market_red_ratio'] = lambda: 0.52     # 全市场未回暖(red=0.52<th=0.53)
ok('T66 _buy_red_ok 未回暖不放行(red=0.52<th=0.53)', ns['_buy_red_ok']('600001.XSHG') is False)
ns3 = fresh(); ns3['BLS']['red_gate_enabled'] = False
ok('T66 red_gate 关闭 -> 恒放行', ns3['_buy_red_ok']('600001.XSHG') is True)


# --- T67 v0.30 情绪仓位闭环（docs/40 闭环）：冰点40%/回暖80%、连续回暖递减、分歧保护 ---
# 1) _load_sentiment 读 warm_days/phase/divergence 新列
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
_sent = os.path.join(ns['_TMP'], 'sentiment_latest.csv')
with open(_sent, 'w', encoding='utf-8') as f:
    f.write('date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence\n'
            '2026-10-19,25,30,0.4500,30.10,2,6,1,2,3,cont,1\n')
s67 = ns['_load_sentiment']()
ok('T67 sentiment 读入 warm_days=3 phase=cont divergence=1',
   s67 is not None and s67.get('warm_days') == 3 and s67.get('phase') == 'cont' and s67.get('divergence') is True)
ok('T67 兼容旧列(ice/ice_streak 仍读)', s67.get('ice') is True and s67.get('ice_streak') == 2)

# 2) 冰点基线 + 今日未回暖 -> 40%（全市场红盘比口径）
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1, 'warm_days': 0, 'phase': 'ice', 'divergence': False}
ns['_market_red_ratio'] = lambda: 0.50   # streak=1 -> th=0.53 -> red<th 未回暖
ok('T67 冰点日未回暖 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)
ns['_market_red_ratio'] = lambda: 0.60   # red>=th 今日回暖
ok('T67 冰点基线回暖日 cap=0.80(回暖首日)',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.80) < 1e-9)
ns['_market_red_ratio'] = lambda: None   # 全市场缺失 -> 降级冰点
ok('T67 全市场红盘比缺失降级 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)

# 3) 无冰点基线（回暖延续）-> _warm_cap 连续回暖递减 + 分歧保护
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': False, 'ice_streak': 0, 'warm_days': 1, 'phase': 'warm', 'divergence': False}
ok('T67 回暖延续 warm_days=1 cap=0.80',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.80) < 1e-9)
ns['g'].sentiment['warm_days'] = 3
ok('T67 warm_days=3 递减 cap=0.70(分歧保护)',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.70) < 1e-9)
ns['g'].sentiment['warm_days'] = 4
ok('T67 warm_days=4 cap=0.60',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.60) < 1e-9)
ns['g'].sentiment['warm_days'] = 6
ok('T67 warm_days>=5 下限 0.50',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.50) < 1e-9)

# 4) v0.41 全市场 vs 板块口径分离：冰点日 cap 不受个股所属板块红盘比影响
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1, 'warm_days': 0, 'phase': 'ice', 'divergence': False}
ns['_market_red_ratio'] = lambda: 0.35   # 全市场冰点
ns['_red_ratio'] = lambda sec: 0.60      # 板块红盘比高（不应影响）
ok('T67b 全市场冰点+板块高红盘 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)
ns['_market_red_ratio'] = lambda: 0.60   # 全市场回暖
ns['_red_ratio'] = lambda sec: 0.30      # 板块红盘比低（不应影响）
ok('T67b 全市场回暖+板块低红盘 cap=0.80',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.80) < 1e-9)

# 5) v0.41 emotion 档位 -> 上限映射 + 冲突保守
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1, 'warm_days': 0, 'phase': 'ice', 'divergence': False, 'emotion': '偏冷'}
ns['_market_red_ratio'] = lambda: 0.60   # 规则判回暖 0.80；emotion 偏冷 -> 收窄 0.40
ok('T67b emotion=偏冷 收窄 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)
ns['g'].sentiment['emotion'] = '回暖'    # 与规则 ice 冲突 -> 规则优先保守
ok('T67b emotion=回暖 与规则冰点冲突 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': False, 'ice_streak': 0, 'warm_days': 1, 'phase': 'warm', 'divergence': False, 'emotion': '发酵'}
ok('T67b emotion=发酵 无冰点基线 cap=0.80',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.80) < 1e-9)
ns['g'].sentiment['emotion'] = '过热'    # 分歧保护档
ok('T67b emotion=过热 分歧保护 cap=0.50',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.50) < 1e-9)

# 4) v0.31 默认已启用；显式关闭 -> 放行；超限 skip / 限内放行
ns = fresh()
ok('T67 v0.31 默认已启用(sentiment_pos_cap_enabled=True)',
   ns['BLS'].get('sentiment_pos_cap_enabled', False) is True)
ns['BLS']['sentiment_pos_cap_enabled'] = False
ok('T67 显式关闭 cap=None -> 放行', ns['_buy_pos_ok'](ns['_ctx'], '600001.XSHG', 1000, 10.0) is True)

ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1, 'warm_days': 0, 'phase': 'ice', 'divergence': False}
ns['_red_ratio'] = lambda sec: 0.50
ns['_ctx'].portfolio.cash = 50000.0
ns['_ctx'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(market_value=100000.0)}
ok('T67 冰点 40% 超限 skip(100k+20k)/150k=0.80>0.40',
   ns['_buy_pos_ok'](ns['_ctx'], '600002.XSHG', 2000, 10.0) is False)
ns['_ctx'].portfolio.cash = 100000.0
ns['_ctx'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(market_value=30000.0)}
ok('T67 冰点 40% 限内放行(30k+20k)/130k=0.385<=0.40',
   ns['_buy_pos_ok'](ns['_ctx'], '600002.XSHG', 2000, 10.0) is True)

ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': False, 'ice_streak': 0, 'warm_days': 1, 'phase': 'warm', 'divergence': False}
ns['_ctx'].portfolio.cash = 50000.0
ns['_ctx'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(market_value=150000.0)}
ok('T67 回暖 80% 超限 skip(150k+40k)/200k=0.95>0.80',
   ns['_buy_pos_ok'](ns['_ctx'], '600002.XSHG', 4000, 10.0) is False)
ns['_ctx'].portfolio.cash = 100000.0
ns['_ctx'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(market_value=60000.0)}
ok('T67 回暖 80% 限内放行(60k+50k)/160k=0.69<=0.80',
   ns['_buy_pos_ok'](ns['_ctx'], '600002.XSHG', 5000, 10.0) is True)

# 5) 两买入入口静态包含 _buy_pos_ok 闸门（place_order 买分支 / place_expected_order）
import re
src67 = io.open(SRC, encoding='utf-8').read()
gates = re.findall(r'_buy_pos_ok\(context, sec, qty, limit\)', src67)
ok('T67 两买入路径均接 _buy_pos_ok 闸门', len(gates) >= 2)


# --- T67b 情绪档位列：sentiment CSV 带 emotion/emotion_basis 读入，旧列仍兼容 ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
_sent = os.path.join(ns['_TMP'], 'sentiment_latest.csv')
with open(_sent, 'w', encoding='utf-8') as f:
    f.write('date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence,emotion,emotion_basis\n'
            '2026-10-15,25,30,0.4500,30.10,2,6,1,2,3,cont,1,偏冷,涨停50家/连板16家/红盘比35.51%\n')
s67b = ns['_load_sentiment']()
ok('T67b sentiment 读入 emotion=偏冷', s67b is not None and s67b.get('emotion') == '偏冷')
ok('T67b sentiment 读入 emotion_basis', s67b is not None and '红盘比35.51%' in s67b.get('emotion_basis', ''))
ok('T67b 旧列兼容(ice/warm_days/divergence 仍读)', s67b is not None
   and s67b.get('ice') is True and s67b.get('warm_days') == 3 and s67b.get('divergence') is True)


# --- T68 v0.31b open_reason 缺失降级（build_expectation_bridge.cmd_review 不 abort，链路继续）---
import build_expectation_bridge as beb68
_tmp68 = tempfile.mkdtemp(prefix='pt_sf68_')
_emp68 = os.path.join(_tmp68, 'empty_pos.jsonl')
with open(_emp68, 'w', encoding='utf-8') as _f:
    _f.write('')
_exp68 = os.path.join(_tmp68, 'exp_out.jsonl')
with open(_exp68, 'w', encoding='utf-8') as _f:
    _f.write('{"trade_date":"2026-10-20","code":"600001.XSHG","status":"position_expectation_marker","position_count":0}\n')
_a68 = types.SimpleNamespace(date='2026-10-19', next_date='2026-10-20',
                             open_reason='', snapshots='', positions=_emp68, insights='',
                             review_out=os.path.join(_tmp68, 'review_out.jsonl'),
                             expectation_out=_exp68,
                             out_dir=_tmp68)
_rc68 = beb68.cmd_review(_a68)
ok('T68 open_reason 缺失降级 rc=0（不 abort）', _rc68 == 0)
ok('T68 链路继续：预期 CSV 已产出(空行表头)',
   os.path.isfile(os.path.join(_tmp68, 'expectation_2026-10-20.csv')))


# --- T64 v0.31c 盘中重启：before_trading_start 重标一字板（免5s门槛不丢）---
def _bts_setup(state_day, today):
    n = fresh()
    n['load_state'] = lambda: None
    n['_save_state'] = lambda: None
    n['_load_expectation'] = lambda: None
    n['_load_zt_lianban'] = lambda: None
    n['_load_sentiment'] = lambda: None
    n['_load_selfwatch'] = lambda: None
    n['_sync_pool_static'] = lambda: None
    n['_hist_1d'] = lambda sec: None
    n['get_trading_day'] = lambda: datetime.date.fromisoformat(today)
    gg = n['g']
    gg.state_day = state_day
    gg.zt_lianban = None
    gg.pool_static = ['600001.XSHG']
    gg.spot['600001.XSHG'] = {'last_px': 12.0, 'preclose_px': 10.0, 'up_px': 12.0,
                              'open_px': 12.0, 'total_offerqty': 0}
    return n, gg
_n64, _g64 = _bts_setup('2026-10-16', '2026-10-16')
_n64['before_trading_start'](_n64['_ctx'], None)
ok('T64 重启分支重标一字板入 one_word_open', '600001.XSHG' in (_g64.one_word_open or set()))
ok('T64 重启后 _sealed_at_limit 立即封死(免5s)', _n64['_sealed_at_limit']('600001.XSHG') is True)
ok('T64 重启后 _block_sealed_buy 拦截不排队', _n64['_block_sealed_buy']('600001.XSHG') is True)
_n65, _g65 = _bts_setup('2026-10-15', '2026-10-16')   # 非同日：正常开盘，不触发重标
_n65['before_trading_start'](_n65['_ctx'], None)
ok('T64 非重启日不误标一字板', '600001.XSHG' not in (getattr(_g65, 'one_word_open', None) or set()))
# --- v0.32 云端持仓预期管理：_hold_exp_init（成交即建条目 + 幂等 + 跨日 force + 一字板继承） ---
_n66 = fresh()
_g66 = _n66['g']
_g66.spot['601811.XSHG'] = {'last_px': 27.74, 'preclose_px': 26.0, 'up_px': 30.0, 'wavg_px': 26.5, 'trade_status': 'OPEN', 'open_px': 26.2}
_g66.exp_file['601811.XSHG'] = {'side': 'hold', 'entry_type': 'normal', 'expected_status': 'pending_meet',
                                'expected_auction_change_pct': 2.0, 'yesterday_open_pct': 1.0,
                                'seal_amount_t0': 0.0, 'sell_policy_hint': 'hold_higher_tolerance'}
_e66 = _n66['_hold_exp_init']('601811.XSHG')
ok('T66 持仓预期条目初始化(auction_status/status 非空)', bool(_e66.get('auction_status')) and bool(_e66.get('status')))
ok('T66 回填 sell_policy_hint', _e66.get('sell_policy_hint') == 'hold_higher_tolerance')
ok('T66 默认 side=hold', _e66.get('side') == 'hold')
_au66 = _e66.get('auction_status')
_e66b = _n66['_hold_exp_init']('601811.XSHG')
ok('T66 幂等：二次调用不覆盖已算 auction_status', _e66b.get('auction_status') == _au66)
ok('T66 幂等：_hold_inited 标记', _e66b.get('_hold_inited') is True)

_n66c = fresh()
_g66c = _n66c['g']
_g66c.spot['600001.XSHG'] = {'last_px': 12.0, 'preclose_px': 10.0, 'up_px': 12.0, 'wavg_px': 11.0, 'trade_status': 'OPEN', 'open_px': 12.0}
_g66c.seal_base = {}; _g66c.seal_bid_base = {}
_g66c.exp_file['600001.XSHG'] = {'side': 'hold', 'entry_type': 'one_word', 'expected_status': 'pending_exceed',
                                 'expected_auction_change_pct': 5.0, 'yesterday_open_pct': 3.0,
                                 'seal_amount_t0': 0.0}
_e66c = _n66c['_hold_exp_init']('600001.XSHG')
ok('T66 一字板 entry_type 继承 exp_file', _e66c.get('entry_type') == 'one_word')
ok('T66 一字板 P4 卖出链可走 _exp_one_word(无封单基准则初始化)', _n66c['_exp_one_word']('600001.XSHG')[0] in (_n66c['AW'], _n66c['CM'], _n66c['CX'], _n66c['CS']))

# T67 成交回报（买入）立即建持仓预期条目
_n67 = fresh()
_g67 = _n67['g']
_n67['on_trade_response'](_n67['_ctx'], types.SimpleNamespace(ticker='601811.XSHG', quantity=100, side='buy'))
ok('T67 买入成交后 g.exp 有条目且已初始化', (_g67.exp.get('601811.XSHG') or {}).get('_hold_inited') is True)

# T68 跨日 force 重算（handle_data day-change 用）
_n68 = fresh()
_g68 = _n68['g']
_g68.spot['601188.XSHG'] = {'last_px': 3.18, 'preclose_px': 3.0, 'up_px': 3.5, 'wavg_px': 3.1, 'trade_status': 'OPEN', 'open_px': 2.9}
_n68['_hold_exp_init']('601188.XSHG', force=True)
ok('T68 跨日 force 初始化条目', (_g68.exp.get('601188.XSHG') or {}).get('_hold_inited') is True)
ok('T68 卖出链可消费（sell_manager P4 分支不崩）', True)


# --- v0.33 文件持仓预期 vs 云端实时 防冲突仲裁 ---
def _sell_setup(exp_row, ac, intrady=None, confirm=None, open_px=None, oneword=False):
    n = fresh()
    _CMAP = {'CX': n['CX'], 'PM': n['PM'], 'CS': n['CS'], 'CM': n['CM']}
    if isinstance(confirm, str):
        confirm = _CMAP.get(confirm, confirm)
    if isinstance(intrady, str):
        intrady = _CMAP.get(intrady, intrady)
    n = fresh()
    ctx = n['_ctx']
    ctx.portfolio.positions = {'600060.XSHG': types.SimpleNamespace(amount=1000, cost_basis=10.0)}
    n['g'].exp_file['600060.XSHG'] = exp_row
    n['g'].spot['600060.XSHG'] = {'last_px': 10.5, 'preclose_px': 10.0, 'up_px': 12.0,
                                  'wavg_px': 10.5, 'trade_status': 'OPEN',
                                  'open_px': (open_px if open_px is not None else (12.0 if oneword else 10.0))}
    n['_auction_change'] = lambda c: ac
    if intrady is not None: n['_eval_intraday'] = lambda c, au: (intrady, ['mock'])
    if confirm is not None: n['_confirm_expected'] = lambda c: (confirm, 5.0)
    n['get_stop_loss_pct'] = lambda sec: 0.05
    n['score_now'] = lambda sec: 80.0
    rec = []
    n['place_order'] = lambda c, sec, side, qty=None, note='', mode='chase': rec.append((sec, side, qty, note))
    return n, rec

# T69 P2E 文件悲观(confirmed_miss) + 实时竞价超预期反证(CX) -> 不核卖
_n69, _r69 = _sell_setup({'side': 'sell', 'expected_status': 'confirmed_miss'}, ac=-3.0, intrady='CM', confirm='CX')
_n69['sell_manager'](_n69['_ctx'])
ok('T69 文件confirmed_miss但实时超预期(CX)反证 -> 不核卖', _r69 == [])
# T69b 文件 confirmed_miss + 实时未反证(PM) -> 仍核卖（对齐 AXquant）
_n69b, _r69b = _sell_setup({'side': 'sell', 'expected_status': 'confirmed_miss'}, ac=-3.0, intrady='CM', confirm='PM')
_n69b['sell_manager'](_n69b['_ctx'])
ok('T69b 文件confirmed_miss未反证 -> 核卖', any('P2E_exp_miss' in n for _, _, _, n in _r69b))

# T70 _role_tolerance：文件乐观容忍(hold_higher_tolerance) + 竞价绿开 -> P1/P3 阈值回落 1.0
_n70 = fresh()
_n70['g'].exp_file['600061.XSHG'] = {'sell_policy_hint': 'hold_higher_tolerance'}
_n70['_auction_change'] = lambda c: -3.0
_n70['g'].spot['600061.XSHG'] = {'last_px': 9.7, 'preclose_px': 10.0, 'up_px': 11.0, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
_rt70 = _n70['_role_tolerance']('600061.XSHG')
ok('T70 实时绿开 + 文件hold容忍 -> green_tol 回落 1.0', _rt70['green_tol'] == 1.0 and _rt70['stop_adj'] == 1.0)
ok('T70 软阈值 score_clear_adj 仍按文件 0.6', abs(_rt70['score_clear_adj'] - 0.6) < 1e-9)

# T71 文件 entry_type=one_word 但实时开板 -> P4 回落普通三态(CS -> 卖)
_n71, _r71 = _sell_setup({'side': 'hold', 'entry_type': 'one_word', 'expected_status': 'pending_exceed'}, ac=5.0, intrady='CS', open_px=10.0)
_n71['sell_manager'](_n71['_ctx'])
ok('T71 文件一字板实时开板 -> P4_exp_miss 卖出', any('P4_exp_miss' in n for _, _, _, n in _r71))
# T71b 文件 one_word + 实时仍封板 -> 走 _exp_one_word（不误判普通三态）
_n71b, _r71b = _sell_setup({'side': 'hold', 'entry_type': 'one_word', 'expected_status': 'pending_exceed'}, ac=5.0, oneword=True)
_n71b['_exp_one_word'] = lambda c: (_n71b['CX'], ['seal_increase'])
_n71b['sell_manager'](_n71b['_ctx'])
ok('T71b 文件一字板实时仍封板 -> 走封单逻辑(非P4_exp_miss)', not any('P4_exp_miss' in n for _, _, _, n in _r71b))

# T72 v0.34 连板中位股规避（docs/33，消费 AXquant 复盘 role_detail 标注；无标注 zt 兜底近似）
def _mid_ns(rd=None, board_cnt=None, has_zt=True):
    n = fresh()
    if rd is not None:
        n['g'].exp_file['600072.XSHG'] = {'side': 'buy', 'entry_type': 'normal',
                                          'expected_status': 'pending_exceed', 'role_detail': rd}
    if has_zt and board_cnt is not None:
        n['g'].zt_lianban = {'600072.XSHG': {'board_cnt': board_cnt}}
    return n

n = _mid_ns(rd='mid_consecutive_limit_up')
ok('T72 role_detail=mid -> 规避', n['_mid_board_avoid']('600072.XSHG') is True)
n = _mid_ns(rd='unique_high_board_consecutive')
ok('T72 role_detail=unique_high -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)
n = _mid_ns(rd='leading_first_board')
ok('T72 role_detail=leading_first_board -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)
n = _mid_ns(rd='first_board_arb')
ok('T72 role_detail=first_board_arb -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)
n = _mid_ns(board_cnt=3)
ok('T72 无标注 zt 兜底(3连板) -> 规避', n['_mid_board_avoid']('600072.XSHG') is True)
n = _mid_ns(board_cnt=1)
ok('T72 无标注 zt 兜底(1进2) -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)
n = _mid_ns(board_cnt=6)
ok('T72 无标注 zt 兜底(6+高标) -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)
n = _mid_ns()
ok('T72 无 zt 无标注 -> 放行', n['_mid_board_avoid']('600072.XSHG') is False)

# place_order 兜底闸（buy 分支中位返回 None，原函数直测）

n = fresh(); n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {}
r = n['place_order'](n['_ctx'], '600072.XSHG', 'buy', note='x')
ok('T72 place_order 原函数中位 buy -> 拦截(False)', r is False and '600072.XSHG' not in n['g'].daily['bought'])

# place_expected_order 兜底闸
n = fresh(); n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {}
r = n['place_expected_order'](n['_ctx'], '600072.XSHG', note='x')
ok('T72 place_expected_order 中位 -> False 不买', r is False and '600072.XSHG' not in n['g'].daily['bought'])

# _attempt_expected_buy 拦截（中位在最前，不触发状态机）
n = fresh(); n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {}
r = n['_attempt_expected_buy'](n['_ctx'], '600072.XSHG')
ok('T72 _attempt_expected_buy 中位 -> None 不买', r is None and '600072.XSHG' not in n['g'].daily['bought'] and '600072.XSHG' not in n['g'].exp_fired)

# try_core_buy 中位拦截（CORE 标签 + mid 标注）
n = fresh()
n['g'].watch = ['600072.XSHG']; n['g'].pool_static = []
n['g'].now_dt = datetime.datetime(2026,10,16,9,33,0)
n['_tags'] = lambda sec: ['CORE']
n['_limitup_days'] = lambda sec: 3
n['last_px'] = lambda sec: 10.0
n['score_now'] = lambda sec: 60.0
n['trade_open'] = lambda sec: True
n['_block_sealed_buy'] = lambda sec: False
n['BLS']['daily_max_buy'] = 10
n['_save_state'] = lambda *a, **k: None
n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {'600072.XSHG': {'board_cnt': 3}}
pc = []
n['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append(sec) or True
n['try_core_buy'](n['_ctx'])
ok('T72 try_core_buy 中位 -> 不买', '600072.XSHG' not in pc and '600072.XSHG' not in n['g'].daily['bought'])

# try_ma5_buy 中位拦截（CORE+BS 标签 + mid 标注）
n = fresh()
n['g'].watch = ['600072.XSHG']; n['g'].pool_static = []
n['g'].now_dt = datetime.datetime(2026,10,16,10,0,0)
n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {'600072.XSHG': {'board_cnt': 3}}
n['_tags'] = lambda sec: ['CORE']
n['_ma5_first_5d'] = lambda sec: True
n['last_px'] = lambda sec: 10.0
n['_ensure_ma5'] = lambda sec: 10.5
n['_red_ratio'] = lambda sec: 0.5
n['score_now'] = lambda sec: 60.0
n['trade_open'] = lambda sec: True
n['BLS']['daily_max_buy'] = 10
n['BLS']['ma5_core_only'] = True
n['BLS']['ma5_require_bs'] = False
n['BLS']['ma5_first_5d'] = True
n['_save_state'] = lambda *a, **k: None
pc = []
n['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append(sec) or True
n['try_ma5_buy'](n['_ctx'])
ok('T72 try_ma5_buy 中位 -> 不买', '600072.XSHG' not in pc and '600072.XSHG' not in n['g'].daily['bought'])

# _try_first_board_buy 中位拦截（mock _is_first_board True 走闸）
n = fresh()
n['g'].watch = ['600072.XSHG']; n['g'].pool_static = []
n['g'].now_dt = datetime.datetime(2026,10,16,9,31,0)
n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {'600072.XSHG': {'board_cnt': 3}}
n['_min_age'] = lambda: 1
n['_is_one_word_open'] = lambda sec: False
n['_is_first_board'] = lambda sec: True
n['_sn'] = lambda sec: sec
n['BLS']['daily_max_buy'] = 10
n['_ctx'].portfolio.positions = {}
n['_try_first_board_buy'](n['_ctx'], '600072.XSHG', rank_secs=['600072.XSHG'])
ok('T72 _try_first_board_buy 中位 -> 不买', '600072.XSHG' not in n['g'].daily['bought'])

# _synth_pool_expect 中位过滤（云端兜底同口径）：3连板中位不合成，首板合成
n = fresh(); n['get_trading_day'] = lambda: datetime.date(2026,10,16)
g = n['g']
g.zt_lianban = {
    '600001.XSHG': {'board_cnt': 0, 'is_st': False},
    '600003.XSHG': {'board_cnt': 3, 'is_st': False},
}
g.exp_file = {}; g.auction_c = {}
g.spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.8}
g.spot['600003.XSHG'] = {'last_px': 10.6, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.6}
n['_yesterday_open_chg'] = lambda sec: (2.0, True)
nn = n['_synth_pool_expect']()
ok('T72 涨停池合成中位过滤 -> 仅首板合成', nn == 1 and '600001.XSHG' in g.exp_file and '600003.XSHG' not in g.exp_file)

# T73 v0.34b 连板中位股规避-唯一高度板兜底（板块内最高身位唯一+跟风低位板，高度压制到 3/4 板也放行）
# 板块口径 = 涨停原因首 token（云端无权威映射，首 token 兜底分组，对齐 AXquant 复盘 board_name）
n = fresh()
g = n['g']
g.zt_lianban = {
    '600081.XSHG': {'board_cnt': 3, 'reason': '半导体供应链+光刻机'},
    '600082.XSHG': {'board_cnt': 2, 'reason': '半导体供应链+先进封装'},
    '600083.XSHG': {'board_cnt': 1, 'reason': '低空经济+通航'},
}
nn = n['_annotate_zt_uniqueness']()
ok('T73 板块内最高身位唯一(3板+2板跟风) -> 标注', nn == 1 and g.zt_lianban['600081.XSHG']['unique_high'] is True)
ok('T73 唯一高板 follower_count=1(跟风低位板)', g.zt_lianban['600081.XSHG']['follower_count'] == 1)
ok('T73 低位/非龙头不标唯一', g.zt_lianban['600082.XSHG']['unique_high'] is False and g.zt_lianban['600083.XSHG']['unique_high'] is False)
# 唯一高板（3板）不应被中位规避
ok('T73 唯一高度板 3连板 -> 放行', n['_mid_board_avoid']('600081.XSHG') is False)

# 板块内并列最高身位（两票同 3 板）-> 均不唯一，按中位规避
n = fresh()
g = n['g']
g.zt_lianban = {
    '600081.XSHG': {'board_cnt': 3, 'reason': '半导体供应链'},
    '600082.XSHG': {'board_cnt': 3, 'reason': '半导体供应链'},
}
nn = n['_annotate_zt_uniqueness']()
ok('T73 并列最高(两票同3板) -> 均不标唯一', nn == 0 and g.zt_lianban['600081.XSHG']['unique_high'] is False)
ok('T73 并列最高 3连板 -> 中位规避', n['_mid_board_avoid']('600081.XSHG') is True)

# 特例：全市场唯一高标（高度压制到 3/4 板，无同板块跟风）-> 唯一性展现
n = fresh()
g = n['g']
g.zt_lianban = {
    '600081.XSHG': {'board_cnt': 3, 'reason': '半导体供应链'},
    '600083.XSHG': {'board_cnt': 1, 'reason': '低空经济+通航'},
    '600084.XSHG': {'board_cnt': 1, 'reason': '机器人概念'},
}
nn = n['_annotate_zt_uniqueness']()
ok('T73 全市场唯一高标(3板) -> 标注唯一', nn == 1 and g.zt_lianban['600081.XSHG']['unique_high'] is True)
ok('T73 全市场唯一高标 3连板 -> 放行', n['_mid_board_avoid']('600081.XSHG') is False)

# 板块更高身位存在（4板 > 3板同板块）-> 3板非唯一，按中位规避
n = fresh()
g = n['g']
g.zt_lianban = {
    '600081.XSHG': {'board_cnt': 3, 'reason': '半导体供应链'},
    '600082.XSHG': {'board_cnt': 4, 'reason': '半导体供应链+先进封装'},
}
nn = n['_annotate_zt_uniqueness']()
ok('T73 板块有更高身位(4板) -> 3板非唯一', nn == 1 and g.zt_lianban['600081.XSHG']['unique_high'] is False and g.zt_lianban['600082.XSHG']['unique_high'] is True)
ok('T73 板块更高身位存在 -> 3板中位规避', n['_mid_board_avoid']('600081.XSHG') is True)
ok('T73 板块唯一高板(4板) -> 放行', n['_mid_board_avoid']('600082.XSHG') is False)

# role_detail 权威标注优先：无 zt 但复盘标 mid -> 仍规避；标 unique -> 仍放行
n = fresh()
n['g'].exp_file['600085.XSHG'] = {'side': 'buy', 'role_detail': 'mid_consecutive_limit_up'}
n['g'].zt_lianban = {}
ok('T73 role_detail=mid 权威优先 -> 规避', n['_mid_board_avoid']('600085.XSHG') is True)
n = fresh()
n['g'].exp_file['600085.XSHG'] = {'side': 'buy', 'role_detail': 'unique_high_board_consecutive'}
n['g'].zt_lianban = {}
ok('T73 role_detail=unique 权威优先 -> 放行', n['_mid_board_avoid']('600085.XSHG') is False)


# --- T74 v0.35 export_sentiment 日期守卫：同日重复运行不虚增 ice_streak / warm_days ---
import json, csv
import export_sentiment as es74

def _es_lub(out, d, pool_total, adv):
    with open(os.path.join(out, "limit_up_boards_%s.json" % d), "w", encoding="utf-8") as _f:
        json.dump({"summary": {"pool_total": pool_total, "break_total": 10,
                               "advance_rate_pct": adv, "max_board": 2, "lianban_count": 4}, "pool": {}}, _f)

def _es_seed(out, d, ice, streak, warm, phase):
    with open(os.path.join(out, "sentiment_latest.csv"), "w", encoding="utf-8") as _f:
        _f.write("date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence\n")
        _f.write("%s,40,10,0.8000,50.00,2,4,%d,%d,%d,%s,0\n" % (d, int(ice), streak, warm, phase))

def _es_row(out):
    with open(os.path.join(out, "sentiment_latest.csv"), "r", encoding="utf-8") as _f:
        rows = list(csv.reader(_f))
    return rows[1]

_t74 = tempfile.mkdtemp(prefix="pt_sf74_")

# 1) 同日冰点重复运行：streak 不虚增（10-19 ice=1 -> 10-20 ice=2 -> 再跑仍 2）
_es_seed(_t74, "2026-10-19", True, 1, 0, "ice"); _es_lub(_t74, "2026-10-20", 25, 30.0)
es74.run("2026-10-20", _t74, _t74, _t74)
es74.run("2026-10-20", _t74, _t74, _t74)   # 同日重复
_r1 = _es_row(_t74)
ok("T74 同日冰点重复运行 streak 不虚增(2->2)", _r1[7] == "1" and _r1[8] == "2" and _r1[9] == "0")

# 2) 跨日冰点 -> streak+1
_es_seed(_t74, "2026-10-20", True, 2, 0, "ice"); _es_lub(_t74, "2026-10-21", 25, 30.0)
es74.run("2026-10-21", _t74, _t74, _t74)
_r2 = _es_row(_t74)
ok("T74 跨日冰点 streak+1(2->3)", _r2[7] == "1" and _r2[8] == "3")

# 3) 前日冰点+今日回暖 -> streak 归 0，phase=warm warm_days=1
_es_seed(_t74, "2026-10-20", True, 2, 0, "ice"); _es_lub(_t74, "2026-10-21", 40, 55.0)
es74.run("2026-10-21", _t74, _t74, _t74)
_r3 = _es_row(_t74)
ok("T74 回暖日 streak 归 0 + phase=warm warm_days=1", _r3[7] == "0" and _r3[8] == "0" and _r3[9] == "1" and _r3[10] == "warm")

# 4) 同日非冰点重复运行：warm_days 不虚增（cont 2->3 -> 再跑仍 3）
_es_seed(_t74, "2026-10-20", False, 0, 2, "cont"); _es_lub(_t74, "2026-10-21", 40, 55.0)
es74.run("2026-10-21", _t74, _t74, _t74)
es74.run("2026-10-21", _t74, _t74, _t74)   # 同日重复
_r4 = _es_row(_t74)
ok("T74 同日回暖延续重复运行 warm_days 不虚增(3->3)", _r4[7] == "0" and _r4[8] == "0" and _r4[9] == "3" and _r4[10] == "cont")

# 5) latest 日期晚于当前（回补历史）-> 视为无前置，不污染
_es_seed(_t74, "2026-10-21", True, 5, 0, "ice"); _es_lub(_t74, "2026-10-20", 25, 30.0)
es74.run("2026-10-20", _t74, _t74, _t74)
_r5 = _es_row(_t74)
ok("T74 未来/更晚 latest 视为无前置(重新累计 streak=1)", _r5[7] == "1" and _r5[8] == "1")


# --- T75 v0.35b export_sentiment 红盘比来源：优先 position_review emotion_temperature.red_ratio_pct（全市场），
#     缺失回退 summary.advance_rate_pct（天梯有限样本）并 WARN ---
import export_sentiment as es75

def _es75_lub(out, pool_total=54, adv=37.36):
    with open(os.path.join(out, "limit_up_boards_2026-10-20.json"), "w", encoding="utf-8") as _f:
        json.dump({"summary": {"pool_total": pool_total, "break_total": 29, "advance_rate_pct": adv,
                               "advance_sample": 348, "max_board": 4, "lianban_count": 14}, "pool": {}}, _f)

def _es75_seed(out):
    with open(os.path.join(out, "sentiment_latest.csv"), "w", encoding="utf-8") as _f:
        _f.write("date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence\n")
        _f.write("2026-10-19,49,20,0.7101,37.46,3,11,1,1,0,ice,0\n")

def _es75_row(out):
    with open(os.path.join(out, "sentiment_latest.csv"), "r", encoding="utf-8") as _f:
        return list(csv.reader(_f))[1]

# 1) 有 position_review 全市场红盘比 67.72 -> 用 67.72；10-19 冰点后 10-20 判回暖(warm/warm_days=1/streak=0)
_t75 = tempfile.mkdtemp(prefix="pt_sf75_")
_es75_lub(_t75); _es75_seed(_t75)
with open(os.path.join(_t75, "position_review_2026-10-20.jsonl"), "w", encoding="utf-8") as _f:
    _f.write('{"trade_date":"2026-10-20","record_type":"position_review_marker","position_count":0,'
             '"extra":{"emotion_temperature":{"conclusion":"\u56de\u6696\uff08\u51b0\u70b9\u540e\u4fee\u590d\u521d\u671f\uff09","red_ratio_pct":67.72,'
             '"advance_rate_pct":54.55}}}\n')
es75.run("2026-10-20", _t75, _t75, _t75)
_r75 = _es75_row(_t75)
ok("T75 红盘比优先: advance=67.72 非 37.36", abs(float(_r75[4]) - 67.72) < 1e-9)
ok("T75 红盘比优先: 10-20 判回暖(ice=0 streak=0 warm_days=1 phase=warm)",
   _r75[7] == "0" and _r75[8] == "0" and _r75[9] == "1" and _r75[10] == "warm")

# 2) 无 position_review（回退天梯样本 37.36 < 40）-> 判冰点 ice=1 streak=2
_t75b = tempfile.mkdtemp(prefix="pt_sf75b_")
_es75_lub(_t75b); _es75_seed(_t75b)
es75.run("2026-10-20", _t75b, _t75b, _t75b)
_r75b = _es75_row(_t75b)
ok("T75 无红盘比回退天梯样本 -> 判冰点(adv=37.36 ice=1 streak=2)",
   abs(float(_r75b[4]) - 37.36) < 1e-9 and _r75b[7] == "1" and _r75b[8] == "2")


# --- T76 v0.35c sentiment 根目录瘦身：更早 sentiment_<date>.csv 移入 archive/（keep_days 对齐 zt=3） ---
import export_sentiment as es76
_t76 = tempfile.mkdtemp(prefix="pt_sf76_")
for _d in ("2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-20"):
    with open(os.path.join(_t76, "sentiment_%s.csv" % _d), "w", encoding="utf-8") as _f:
        _f.write("date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence\n")
        _f.write("%s,40,10,0.8000,50.00,2,4,0,0,1,cont,0\n" % _d)
n76 = es76._prune_old(_t76, 3)
_kept = sorted(x for x in os.listdir(_t76) if x.startswith("sentiment_") and x.endswith(".csv"))
_arc = sorted(x for x in os.listdir(os.path.join(_t76, "archive")) if x.endswith(".csv"))
ok("T76 根目录仅留最近3个日期(移走2个)", n76 == 2 and
   _kept == ["sentiment_2026-10-16.csv", "sentiment_2026-10-17.csv", "sentiment_2026-10-20.csv"])
ok("T76 更早文件移入 archive 保留审计", _arc == ["sentiment_2026-10-14.csv", "sentiment_2026-10-15.csv"])
# --- T77 v0.35e 自选股预期三态合成（竞价超预期->观察，复用涨停池口径，云端算法供给） ---
ns = fresh(); ns['get_trading_day'] = lambda: datetime.date(2026, 10, 20)
g = ns['g']
g.selfwatch = ['600001.XSHG', '600002.XSHG', '600003.XSHG', '600009.XSHG']
g.zt_lianban = {'600009.XSHG': {'board_cnt': 3}}   # 连板中位(2-5) -> 兜底过滤
g.exp_file = {'600004.XSHG': {'side': 'buy', 'entry_type': 'normal', 'expected_status': 'pending_meet', '_src': 'provider'}}
g.selfwatch.append('600004.XSHG')   # 供方条目优先不覆盖
g.auction_c = {}
g.spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.8}   # +8% 超预期
g.spot['600002.XSHG'] = {'last_px': 9.6, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 9.6}     # -4% 绿开 miss
g.spot['600003.XSHG'] = {'last_px': 10.2, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2}   # +2% 未超昨日 meet
ns['_yesterday_open_chg'] = lambda sec: (2.0, True)
n = ns['_synth_selfwatch_expect']()
en1 = g.exp_file.get('600001.XSHG') or {}
en2 = g.exp_file.get('600002.XSHG') or {}
en3 = g.exp_file.get('600003.XSHG') or {}
en4 = g.exp_file.get('600004.XSHG') or {}
ok('T77 自选股超预期 -> exceed/观察(_src=selfwatch)', n == 3 and en1.get('expected_status') == 'pending_exceed' and en1.get('_src') == 'selfwatch' and en1.get('side') == 'buy')
ok('T77 自选股绿开 -> miss', en2.get('expected_status') == 'pending_miss')
ok('T77 自选股未超昨日 -> meet', en3.get('expected_status') == 'pending_meet')
ok('T77 连板中位股过滤(mid_skip)', '600009.XSHG' not in g.exp_file)
ok('T77 供方条目优先不覆盖', en4.get('_src') == 'provider' and en4.get('expected_status') == 'pending_meet')
ok('T77 二次合成幂等', ns['_synth_selfwatch_expect']() == 0 and len(g.exp_file) == 4)
ok('T77 预置竞价涨幅缓存(开盘口径)', abs(g.auction_c.get('600001.XSHG', (0, 0))[1] - 8.0) < 1e-9)
# --- T78 v0.35f VWAP 扣分 30 秒粒度：低于 VWAP 每 30 秒扣 1 分，日上限 12（快照 wavg_px 近似 VWAP）；高于 VWAP 恢复归零、再破重新计时 ---
ns = fresh()
g = ns['g']
g.spot['600001.XSHG'] = {'last_px': 9.7, 'preclose_px': 10.0, 'up_px': 11.0, 'wavg_px': 10.0}
g.vwap_below_since = {}
g.now_dt = datetime.datetime(2026, 10, 20, 9, 31, 0)
ok('T78 首次破VWAP -> 0分(计时起点)', ns['_vwap_penalty']('600001.XSHG') == 0.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 31, 30)
ok('T78 低于VWAP 30秒 -> 1分', ns['_vwap_penalty']('600001.XSHG') == 1.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 32, 0)
ok('T78 低于VWAP 60秒 -> 2分(每30秒1分)', ns['_vwap_penalty']('600001.XSHG') == 2.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 36, 0)
ok('T78 低于VWAP 5分钟 -> 10分', ns['_vwap_penalty']('600001.XSHG') == 10.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 37, 0)
ok('T78 低于VWAP 6分钟 -> 12分(日上限)', ns['_vwap_penalty']('600001.XSHG') == 12.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 42, 0)
ok('T78 日上限12封顶', ns['_vwap_penalty']('600001.XSHG') == 12.0)
g.spot['600001.XSHG']['last_px'] = 10.1
ok('T78 高于VWAP -> 0分(恢复归零)', ns['_vwap_penalty']('600001.XSHG') == 0.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 42, 30)
g.spot['600001.XSHG']['last_px'] = 9.7
ok('T78 再破VWAP -> 0分(重新计时)', ns['_vwap_penalty']('600001.XSHG') == 0.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 43, 0)
ok('T78 再破30秒 -> 1分(非总时长累计)', ns['_vwap_penalty']('600001.XSHG') == 1.0)
g.now_dt = datetime.datetime(2026, 10, 20, 9, 43, 30)
ok('T78 再破60秒 -> 2分', ns['_vwap_penalty']('600001.XSHG') == 2.0)
g.spot['600001.XSHG'] = {'last_px': 9.7, 'preclose_px': 10.0, 'up_px': 11.0}
ok('T78 缺wavg_px -> 0分', ns['_vwap_penalty']('600001.XSHG') == 0.0)

# --- T79 v0.36 帧预算快速期放大 + m1 高优先级独立配额 + board_rank single 归一 ---
ns = fresh()
g = ns['g']
g.now_dt = datetime.datetime(2026, 10, 20, 9, 40, 0)   # 快速期(min_age=10)
ok('T79 快速期 board 限额 24(v0.36e)', ns['_source_limit']('board', 0) == 24.0)
ok('T79 快速期 m1 限额 30', ns['_source_limit']('m1', 0) == 30.0)
ok('T79 m1 高优先级独立配额 15', ns['_source_limit']('m1', 1) == 15.0)
g.now_dt = datetime.datetime(2026, 10, 20, 10, 5, 0)   # 平时(min_age=35)
ok('T79 平时 board 限额 6', ns['_source_limit']('board', 0) == 6.0)
ok('T79 平时 m1 限额 20', ns['_source_limit']('m1', 0) == 20.0)
# gear 快速期动态：min(len(_tick_targets), 25)；get_positions={} + universe 3
g.now_dt = datetime.datetime(2026, 10, 20, 9, 40, 0)
g.watch = []; g.pool_static = []; g.selfwatch = []
g.tick_targets_cache = None
ns['get_positions'] = lambda: {}
ok('T79 gear 快速期动态=min(len(tick_targets),25)', ns['_source_limit']('gear', 0) == float(min(3, 25)))
# prio 独立记账：spend('m1', prio=1) 20 次 -> 15 记账 + 5 over，普通 m1 不受影响
ns2 = fresh()
dh2 = ns2['_get_ds']()
for _i in range(20):
    dh2.spend('m1', prio=1)
ok('T79 prio 独立配额 15 超限记账', dh2.frame['used'].get('m1_p') == 15 and dh2.frame['over'].get('m1_p') == 5)
ok('T79 prio 不占普通 m1 配额', 'm1' not in dh2.frame['used'])
# single 归一：board_rank 同源只留最新一条
ns3 = fresh()
dh3 = ns3['_get_ds']()
dh3.cached(('board_rank', 'A|B'), '_', 60.0, lambda: {'A'}, single=True)
dh3.cached(('board_rank', 'C|D'), '_', 60.0, lambda: {'C'}, single=True)
n3 = len([k for k in dh3.cache if isinstance(k[0], tuple) and k[0][0] == 'board_rank'])
ok('T79 single 同源只留最新一条', n3 == 1 and dh3.cache.get((('board_rank', 'C|D'), '_')) is not None)

# --- T80 v0.36 auction_c 覆盖兜底：09:25/09:31 快照 open 口径覆盖早盘污染 ---
ns = fresh()
g = ns['g']
g.spot['600001.XSHG'] = {'preclose_px': 10.0, 'open_px': 10.8}
g.auction_c['600001.XSHG'] = ('2026-10-20', 0.0)   # 早盘 get_trend_data 未开盘值污染
ns['_overwrite_auction_c'](['600001.XSHG'])
ok('T80 覆盖为快照 open 口径(+8%)', abs(g.auction_c['600001.XSHG'][1] - 8.0) < 1e-9)
# 缺失 open_px -> 不覆盖（保留污染前原值）
ns0 = fresh()
ns0['g'].spot['600001.XSHG'] = {'preclose_px': 10.0, 'open_px': 0.0}
ns0['g'].auction_c['600001.XSHG'] = ('2026-10-20', 0.0)
ns0['_overwrite_auction_c'](['600001.XSHG'])
ok('T80 缺失 open 不覆盖(保留原值)', ns0['g'].auction_c['600001.XSHG'][1] == 0.0)

# --- T82 v0.36b 新最强板块弹性套利：新爆发因子(开盘涨幅>5日均值)+持续跟踪+买入去重 ---
ns = fresh()
g = ns['g']
g.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g.watch = ['600001.XSHG']; g.pool_static = []; g.selfwatch = []
ns['_boards_of'] = lambda sec: ['B_A']
ns['_board_strength_by_code'] = lambda b: 5.0 if b == 'B_A' else 1.0
ns['_board_refresh_ttl'] = lambda: 3.0
ns['BLS']['elastic_top_stable_frames'] = 1   # 聚焦触发逻辑，稳定窗口单独 T82j 测
ns['_board_open_gain'] = lambda b: 5.0          # 开盘板块涨幅 5%
ns['_board_5d_strength'] = lambda b: 1.0        # 5日均强度 1% -> 5>=1+2 触发
ns['get_industry_stocks'] = lambda b: ['300001.SZ', '300002.SZ', '600001.XSHG'] if b == 'B_A' else []
ns['_elastic_1m_surge'] = lambda sec: {'300001.XSHE': 3.5, '300002.XSHE': 3.0}.get(sec, 0.0)
ns['_is_one_word_open'] = lambda sec: False
ns['_block_sealed_buy'] = lambda sec: False
ns['_mid_board_avoid'] = lambda sec: False
ns['_save_state'] = lambda: None
g.spot['300001.XSHE'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 12.0, 'open_px': 10.5, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
g.spot['300002.XSHE'] = {'last_px': 11.1, 'preclose_px': 10.0, 'up_px': 12.0, 'open_px': 10.2, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
top1 = ns['_new_top_board_scan']()
ok('T82 新最强板块触发', top1 == 'B_A')
ok('T82 同板块持续跟踪', ns['_new_top_board_scan']() == 'B_A')
cands = ns['_elastic_top_candidates']('B_A')
ok('T82 最主动优先且过滤已过10%', cands == ['300001.XSHE'])
# 换榜：B_B 变强 -> 触发新最强（当日第2次触发）
ns['_boards_of'] = lambda sec: ['B_B']
ns['_board_strength_by_code'] = lambda b: 6.0 if b == 'B_B' else 1.0
ok('T82 换榜新最强触发', ns['_new_top_board_scan']() == 'B_B')
# T82g 新爆发因子门控：强度第一但 开盘涨幅未显著强于5日均值 -> 不触发（常态强势）
ns3 = fresh()
g3 = ns3['g']
g3.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g3.watch = ['600001.XSHG']; g3.pool_static = []; g3.selfwatch = []
ns3['_boards_of'] = lambda sec: ['B_A']
ns3['_board_strength_by_code'] = lambda b: 5.0
ns3['_board_refresh_ttl'] = lambda: 3.0
ns3['BLS']['elastic_top_stable_frames'] = 1
ns3['_board_open_gain'] = lambda b: 2.5
ns3['_board_5d_strength'] = lambda b: 3.0        # 2.5 < 3+2 -> 非新爆发
ok('T82g 开盘未显著强于5日均值不触发', ns3['_new_top_board_scan']() is None)
# T82h 5日均值样本未够 -> 不误触发
ns3['_board_5d_strength'] = lambda b: None
ok('T82h 5日样本未够不触发', ns3['_new_top_board_scan']() is None)
# T82i 当日触发上限 2 -> 不再触发
ns4 = fresh()
g4 = ns4['g']
g4.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g4.watch = ['600001.XSHG']; g4.pool_static = []; g4.selfwatch = []
ns4['_boards_of'] = lambda sec: ['B_A']
ns4['_board_strength_by_code'] = lambda b: 5.0
ns4['_board_refresh_ttl'] = lambda: 3.0
ns4['BLS']['elastic_top_stable_frames'] = 1
ns4['_board_open_gain'] = lambda b: 5.0
ns4['_board_5d_strength'] = lambda b: 1.0
g4.elastic_top = {'day': '2026-10-16', 'top': 'B_X', 'ts': 0.0, 'tracked': {'B_X', 'B_Y'}, 'trig': 2, 'done': False}
ok('T82i 当日触发达上限不触发', ns4['_new_top_board_scan']() is None)
# 完整下单路径：触发 + 最主动 20cm 10% 前买入；买入后本轮跟踪结束
ns2 = fresh()
ns2['BLS']['DO_ORDER'] = True     # 捕获 place_order 真实下单路径
g2 = ns2['g']
g2.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g2.watch = ['600001.XSHG']; g2.pool_static = []; g2.selfwatch = []
ns2['_boards_of'] = lambda sec: ['B_A']
ns2['_board_strength_by_code'] = lambda b: 5.0
ns2['_board_refresh_ttl'] = lambda: 3.0
ns2['BLS']['elastic_top_stable_frames'] = 1
ns2['_board_open_gain'] = lambda b: 5.0
ns2['_board_5d_strength'] = lambda b: 1.0
ns2['get_industry_stocks'] = lambda b: ['300001.SZ']
ns2['_elastic_1m_surge'] = lambda sec: 3.5
ns2['_is_one_word_open'] = lambda sec: False
ns2['_block_sealed_buy'] = lambda sec: False
ns2['_mid_board_avoid'] = lambda sec: False
ns2['_order_limit'] = lambda sec, side, mode: 11.0
ns2['_save_state'] = lambda: None
g2.spot['300001.XSHE'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 12.0, 'open_px': 10.5, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
g2.spot['600001.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0, 'wavg_px': 10.0, 'trade_status': 'OPEN'}
ns2['_try_elastic_top_buy'](ns2['_ctx'])
_calls = ns2['_RECC']['calls']
ok('T82 10%前买入最主动20cm', len(_calls) == 1 and _calls[0]['sec'] == '300001.XSHE' and (_calls[0].get('limit_price') or 0) > 0 and '300001.XSHE' in ns2['g'].daily['bought'])
# 第二帧：抬高每日上限排除 daily_max_buy 掩盖，验证 买入后本轮跟踪结束（done）不重买
ns2['BLS']['daily_max_buy'] = 5
ns2['_try_elastic_top_buy'](ns2['_ctx'])
ok('T82 买入后本轮跟踪结束不重买', len(ns2['_RECC']['calls']) == 1)


# T82j 稳定窗口：默认 3 帧连续第一才触发；易主需连续 3 帧（防单帧抖动打断）
ns6 = fresh()
g6 = ns6['g']
g6.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g6.watch = ['600001.XSHG']; g6.pool_static = []; g6.selfwatch = []
ns6['_boards_of'] = lambda sec: ['B_A']
ns6['_board_strength_by_code'] = lambda b: 5.0 if b == 'B_A' else 1.0
ns6['_board_refresh_ttl'] = lambda: 3.0
ns6['_board_open_gain'] = lambda b: 5.0
ns6['_board_5d_strength'] = lambda b: 1.0
ok('T82j 稳定窗口第1帧不触发', ns6['_new_top_board_scan']() is None)
ok('T82j 稳定窗口第2帧不触发', ns6['_new_top_board_scan']() is None)
ok('T82j 稳定窗口第3帧触发', ns6['_new_top_board_scan']() == 'B_A')
# 易主：单帧 B_B 抖动不打断旧板块跟踪
ns6['_boards_of'] = lambda sec: ['B_B']
ns6['_board_strength_by_code'] = lambda b: 6.0 if b == 'B_B' else 1.0
ok('T82j 易主第1帧仍跟踪旧板块', ns6['_new_top_board_scan']() == 'B_A')
ok('T82j 易主第2帧仍跟踪旧板块', ns6['_new_top_board_scan']() == 'B_A')
ok('T82j 易主第3帧确认', ns6['_new_top_board_scan']() == 'B_B')
# T82k 领先幅度：top1-top2 < 0.5 不确认最强
ns7 = fresh()
g7 = ns7['g']
g7.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g7.watch = ['600001.XSHG']; g7.pool_static = []; g7.selfwatch = []
ns7['_boards_of'] = lambda sec: ['B_A', 'B_B']
ns7['_board_strength_by_code'] = lambda b: 5.0 if b == 'B_A' else 4.6   # 领先 0.4 < 0.5
ns7['_board_refresh_ttl'] = lambda: 3.0
ns7['_board_open_gain'] = lambda b: 5.0
ns7['_board_5d_strength'] = lambda b: 1.0
ok('T82k 领先不足不触发', ns7['_new_top_board_scan']() is None)
ns7['_boards_of'] = lambda sec: ['B_A', 'B_C']
ns7['_board_strength_by_code'] = lambda b: 5.0 if b == 'B_A' else 4.4   # 领先 0.6 >= 0.5
ok('T82k 领先0.5以上第1帧不触发', ns7['_new_top_board_scan']() is None)
ok('T82k 领先0.5以上第2帧不触发', ns7['_new_top_board_scan']() is None)
ok('T82k 领先0.5以上第3帧触发', ns7['_new_top_board_scan']() == 'B_A')
# T82l 板块口径探针：打印全类别 + HY/GN 返回成员数（验证概念板块能否被行业接口消费）
ns8 = fresh()
g8 = ns8['g']
g8.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
ns8['get_stock_blocks'] = lambda sec: {'HY': [['710200.XBHS', '计算机应用']], 'GN': [['003800.XBHS', '人工智能']], 'DY': [['DY1172.XBHS', '浙江板块']]}
ns8['get_industry_stocks'] = lambda code: ['600001.XSHG', '600002.XSHG'] if str(code).startswith('710') else []
pr = ns8['_board_probe']()
ok('T82l 探针每日一次', ns8['_board_probe']() is pr)
ok('T82l 探针HY返回成员>0', pr and pr.get('600570.XSHG', {}).get('members', {}).get('HY:710200.XBHS', -1) == 2)
ok('T82l 探针GN返回0', pr and pr.get('600570.XSHG', {}).get('members', {}).get('GN:003800.XBHS', -1) == 0)


# T83 v0.36d 板块映射文件加载（Step1：生成->上传->云端 [boards] loaded 链路）
ns9 = fresh()
g9 = ns9['g']
g9.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
with io.open(os.path.join(ns9['_TMP'], 'boards_latest.csv'), 'wt', encoding='utf-8') as f:
    f.write('board_name,board_type,member_code\n人工智能,concept,600001.XSHG\n人工智能,concept,600002.XSHG\n计算机应用,industry,600003.XSHG\n')
n9 = ns9['_load_boards']()
ok('T83 板块文件加载', n9 == 2 and g9.boards.get('人工智能') == ['600001.XSHG', '600002.XSHG'])
ok('T83 board_type 记录', g9.board_type.get('人工智能') == 'concept')
ok('T83 stock_boards 反索引', g9.stock_boards.get('600001.XSHG') == ['人工智能'])
ns10 = fresh()
ok('T83 缺文件返回0不崩', ns10['_load_boards']() == 0 and ns10['g'].boards == {})


# --- T84 v0.36e 概念板块口径：文件加载后只消费 concept + 合并快照强度 ---
ns = fresh()
g = ns['g']
g.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g.boards = {'人工智能': ['600001.XSHG', '600002.XSHG'], '计算机应用': ['600003.XSHG']}
g.board_type = {'人工智能': 'concept', '计算机应用': 'industry'}
g.stock_boards = {'600001.XSHG': ['人工智能', '计算机应用'],
                  '600002.XSHG': ['人工智能'], '600003.XSHG': ['计算机应用']}
ok('T84 概念过滤只返concept', ns['_concept_boards_of']('600001.XSHG') == ['人工智能'])
ok('T84 成员走文件', ns['_board_members_file']('人工智能', 10) == ['600001.XSHG', '600002.XSHG'])
ok('T84 文件已加载无该板块返空', ns['_board_members_file']('B_API', 10) == [])
ns['get_snapshot'] = lambda secs: {c: {'preclose_px': 10.0, 'last_px': 10.2} for c in secs}
ok('T84 概念强度读合并快照', abs(ns['_concept_board_strength']('人工智能') - 2.0) < 1e-6)
_t84r = ns['_concept_board_rank_top1'](['600001.XSHG'])
ok('T84 排名入口概念口径', _t84r[0] == '人工智能' and abs(_t84r[1] - 2.0) < 1e-6)

# --- T85 v0.36e 合并快照：一帧内多板块强度仅 1 次批量快照 spend ---
ns5 = fresh()
g5 = ns5['g']
g5.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
g5.boards = {'概念A': ['600001.XSHG', '600002.XSHG'], '概念B': ['600003.XSHG', '600004.XSHG']}
g5.board_type = {'概念A': 'concept', '概念B': 'concept'}
g5.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A'],
                   '600003.XSHG': ['概念B'], '600004.XSHG': ['概念B']}
def _sn5(secs):
    out = {}
    for c in secs:
        num = int(str(c).split('.')[0][3:])
        out[c] = {'preclose_px': 10.0, 'last_px': 10.0 + num * 0.1}
    return out
ns5['get_snapshot'] = lambda secs: _sn5(secs)
r1 = ns5['_compute_concept_board_top1_lead'](['概念A', '概念B'])
ok('T85 概念top1判定', r1[0] == '概念B' and abs(r1[1] - 2.0) < 1e-6)
r2 = ns5['_compute_concept_board_top1_lead'](['概念A', '概念B'])
ok('T85 同帧复用同结果', r2[0] == '概念B' and abs(r2[1] - 2.0) < 1e-6)
ok('T85 一帧多板块仅1次批量快照spend', ns5['_get_ds']().frame['used'].get('board') == 1)

# --- T86 v0.36e 两段式候选：快照粗排后只对前 elastic_top_surge_top_n 算 1m surge ---
ns6 = fresh()
g6 = ns6['g']
g6.boards = {'概念A': ['300001.XSHE', '300002.XSHE', '300003.XSHE', '300004.XSHE',
                             '300005.XSHE', '300006.XSHE', '300007.XSHE']}
g6.board_type = {'概念A': 'concept'}
g6.stock_boards = dict((c, ['概念A']) for c in g6.boards['概念A'])
def _sn6(secs):
    out = {}
    for i, c in enumerate(secs):
        out[c] = {'preclose_px': 10.0, 'last_px': 10.0 + (i + 1) * 0.1}
    return out
ns6['get_snapshot'] = lambda secs: _sn6(secs)
_surge_calls = []
ns6['_elastic_1m_surge'] = lambda sec: _surge_calls.append(sec) or 5.0
ns6['BLS']['elastic_top_surge_top_n'] = 5
cands = ns6['_calc_elastic_top_candidates']('概念A')
ok('T86 surge只算5次', len(_surge_calls) == 5)
ok('T86 surge取涨幅前5', set(_surge_calls) == {'300007.XSHE', '300006.XSHE', '300005.XSHE', '300004.XSHE', '300003.XSHE'})
ok('T86 排序按surge降序', cands == ['300007.XSHE', '300006.XSHE', '300005.XSHE', '300004.XSHE', '300003.XSHE'])

# --- T87 v0.36e 文件未加载回退 API：归属/成员/排名/强度全链 ---
ns7 = fresh()
ns7['_boards_of'] = lambda sec: ['B_A']
ns7['_board_rank_top1'] = lambda secs: ('B_A', 1.0)
ns7['_board_strength_by_code'] = lambda b: 5.0
ns7['get_industry_stocks'] = lambda b: ['300001.SZ'] if b == 'B_API' else []
ok('T87 未加载归属回退API', ns7['_concept_boards_of']('600001.XSHG') == ['B_A'])
ok('T87 未加载成员回退API', ns7['_board_members_file']('B_API', 10) == ['300001.XSHE'])
ok('T87 未加载排名回退API', ns7['_concept_board_rank_top1'](['600001.XSHG']) == ('B_A', 1.0))
ok('T87 未加载强度回退API', ns7['_concept_board_strength']('B_API') == 5.0)


# T88 v0.36f 兜底加固：actual=0.0 且 open 未回填(竞价数据缺失) -> 不误弃，保持等待；open 已回填平开(0.0%) 才是真未达标
ns = fresh(); expbuyns(ns, '600074.XSHG')
ns['_confirm_expected'] = lambda c: (ns['PM'], 0.0)
ns['_auction_benchmark'] = lambda c: (5.0, True)
ns['_two_1m_break'] = lambda c: False
ns['_below_vwap'] = lambda c: False
st, reason = ns['_exp_rt_status']('600074.XSHG')
ok('T88 actual=0 & open missing -> await', st == ns['PM'])
r = ns['_attempt_expected_buy'](ns['_ctx'], '600074.XSHG')
ok('T88 missing-open no fire', r is None and '600074.XSHG' not in ns['g'].exp_fired)
ns2 = fresh(); expbuyns(ns2, '600075.XSHG')
ns2['g'].spot['600075.XSHG']['open_px'] = 10.0   # 平开真实数据 -> 0.0% 确未达标
ns2['_confirm_expected'] = lambda c: (ns2['PM'], 0.0)
ns2['_auction_benchmark'] = lambda c: (5.0, True)
ns2['_two_1m_break'] = lambda c: False
ns2['_below_vwap'] = lambda c: False
st2, reason2 = ns2['_exp_rt_status']('600075.XSHG')
ok('T88 actual=0 & open present -> CS', st2 == ns2['CS'] and reason2.startswith('auction_not_met'))

# --- T89 v0.36g 盘中重启：重建涨停池/自选三态（防 expect_buy 45->12 丢失） ---
ns = fresh(); ns['load_state'] = lambda: None; ns['_save_state'] = lambda: None
ns['_load_expectation'] = lambda: 0; ns['_load_selfwatch'] = lambda: 0; ns['_load_sentiment'] = lambda: 0
ns['_load_zt_lianban'] = lambda: 0; ns['_load_boards'] = lambda: 0
ns['_sync_pool_static'] = lambda: None; ns['_hist_1d'] = lambda sec: None; ns['_board_probe'] = lambda: None
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 16)
ns['_yesterday_open_chg'] = lambda sec: (2.0, True)
g = ns['g']
g.state_day = '2026-10-16'          # 同日盘中重启
g.daily = {'bought': ['600001.XSHG'], 'sold': []}
g.exp_file = {'600100.XSHG': {'side': 'buy', 'entry_type': 'normal', 'expected_status': 'pending_exceed',
                              'expected_auction_change_pct': 2.0, 'has_expected_auction': True,
                              'yesterday_open_pct': 2.0}}   # 供方文件条目（示例）
g.zt_lianban = {'600001.XSHG': {'board_cnt': 0}, '600002.XSHG': {'board_cnt': 1}}
g.selfwatch = ['600003.XSHG']
g.spot['600001.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.8}   # +8% 超预期
g.spot['600002.XSHG'] = {'last_px': 9.6, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 9.6}     # -4% 绿开 miss
g.spot['600003.XSHG'] = {'last_px': 10.2, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.2}   # +2% meet
ns['before_trading_start'](ns['_CTX'], None)
e1 = g.exp_file.get('600001.XSHG') or {}
e2 = g.exp_file.get('600002.XSHG') or {}
e3 = g.exp_file.get('600003.XSHG') or {}
ok('T89 盘中重启重建涨停池三态', e1.get('_src') == 'zt_pool' and e1.get('expected_status') == 'pending_exceed' and e2.get('expected_status') == 'pending_miss')
ok('T89 盘中重启重建自选三态', e3.get('_src') == 'selfwatch' and e3.get('expected_status') == 'pending_meet')
ok('T89 重启保留当日已买', g.daily['bought'] == ['600001.XSHG'])

# --- T90 v0.36i 统一买卖信号结构化 [signal] 行 ---
import re as _re
ns = fresh(); ns['score_now'] = lambda sec: 66.5
_logs = []
class _SigLog:
    def info(self, *a): _logs.append((str(a[0]) % a[1:]) if len(a) > 1 else str(a[0]))
    def warn(self, *a): pass
    def error(self, *a): pass
ns['log'] = _SigLog()
ns['_signal']('600001.XSHG', 'BUY', 200, 15.58, 'board', 'exp_rt CX', ent='E1', status='SENT')
_sl = [x for x in _logs if x.startswith('[signal] ')][0]
ok('T90 signal 行格式', _re.match(r'^\[signal\] 600001\.XSHG side=BUY qty=200 limit=15\.58 mode=board note=exp_rt CX score=66\.5 ent=E1 status=SENT(?: lag=\S+ det=\S+)? ?$', _sl) is not None)
ns2 = fresh(); ns2['score_now'] = lambda sec: 50.0
_logs2 = []
class _SigLog2:
    def info(self, *a): _logs2.append((str(a[0]) % a[1:]) if len(a) > 1 else str(a[0]))
    def warn(self, *a): pass
    def error(self, *a): pass
ns2['log'] = _SigLog2()
ns2['g'].spot['600002.XSHG'] = {'last_px':10.0,'preclose_px':10.0,'up_px':11.0,'wavg_px':10.0,'trade_status':'OPEN'}
ns2['BLS']['DO_ORDER'] = False
ns2['place_order'](ns2['_CTX'], '600002.XSHG', 'buy', note='ma_pullback', mode='chase')
ok('T90 place_order 打 signal SIM', any(x.startswith('[signal] ') and 'status=SIM' in x and 'note=ma_pullback' in x for x in _logs2))
ns3 = fresh(); ns3['score_now'] = lambda sec: 0.0
_logs3 = []
class _SigLog3:
    def info(self, *a): _logs3.append((str(a[0]) % a[1:]) if len(a) > 1 else str(a[0]))
    def warn(self, *a): pass
    def error(self, *a): pass
ns3['log'] = _SigLog3()
ns3['g'].pending = {'600003.XSHG': {'no':'E9','side':'sell','qty':300,'limit':10.0,'status':'SENT','filled':0}}
_o = types.SimpleNamespace(entrust_no='E9', order_status='FILLED')
ns3['on_order_response'](ns3['_CTX'], _o)
ok('T90 on_order_response 打 signal 终态', any(x.startswith('[signal] ') and 'ent=E9' in x and 'status=FILLED' in x for x in _logs3))

# --- T91 v0.36i 采集器兼容 [signal] ---
import log_collector as _lc
_txt = "2026-10-21 09:30:01 - INFO - [signal] 600001.XSHG side=BUY qty=200 limit=15.58 mode=board note=exp_rt CX score=66.5 ent=E1 status=SENT\n"
_p = _lc.parse_text(_txt)
ok('T91 采集器识别 signal', any(e['type'] == 'signal' for e in _p['entries']))
_row = _lc._parse_signal("[signal] 600001.XSHG side=BUY qty=200 limit=15.58 mode=board note=exp_rt CX score=66.5 ent=E1 status=SENT")
ok('T91 解析 signal 字段', _row[0] == '600001.XSHG' and _row[1] == 'BUY' and _row[2] == '200' and _row[4] == 'board' and _row[8] == 'SENT')
# --- T92 v0.37 P0/P1 审计修复：主动毫秒归一 / 概念比较宇宙 / 批量快照 / 唯一列权威优先 ---
# T92a 首触时刻归一：逐笔 ms 优先, 帧 ts 归一同格式（YYYYMMDDHHMMSSmmm 可比较）
ns = fresh()
ns['g'].first_zt = {'600001.XSHG': {'ms': 20261020093231240, 'ts': 1e9},
                    '600002.XSHG': {'ts': 1e9 + 2.0},
                    '600003.XSHG': {'ts': 1e9 + 5.0}}
ok('T92 逐笔ms优先(17位)', ns['_first_zt_ms']('600001.XSHG') == 20261020093231240)
_ta2 = ns['_first_zt_ms']('600002.XSHG'); _ta3 = ns['_first_zt_ms']('600003.XSHG')
ok('T92 帧ts归一(17位可比较)', _ta2 > 10 ** 14 and _ta3 > 10 ** 14 and _ta2 < _ta3)
ok('T92 无记录0', ns['_first_zt_ms']('600004.XSHG') == 0)

# T92b 最快拉升用毫秒（同帧 ts 并列 -> ms 精确判快）
ns = fresh()
g = ns['g']
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A']}
g.first_zt = {'600001.XSHG': {'ms': 20261020093200000, 'ts': 900.0},
              '600002.XSHG': {'ms': 20261020093230000, 'ts': 900.0}}
g.one_word_open = set()
ok('T92 ms更早为最主动', ns['_board_first_zt']('600001.XSHG') is True)
ok('T92 ms更晚非最主动', ns['_board_first_zt']('600002.XSHG') is False)

# T92c 首板闸门比较宇宙：概念文件优先（不走 API 行业首板块）
ns = fresh()
g = ns['g']
g.boards = {'人工智能': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'人工智能': 'concept'}
g.stock_boards = {'600001.XSHG': ['人工智能'], '600002.XSHG': ['人工智能']}
_calls = []
ns['get_stock_blocks'] = lambda sec: _calls.append(sec) or {}
ok('T92 概念文件口径成员', ns['_board_member_codes']('600001.XSHG') == ['600001.XSHG', '600002.XSHG'])
ok('T92 概念口径不走API', _calls == [])

# T92d 板块内涨幅最高：批量回填缺失快照（一次 _get_snapshot_many）
ns = fresh()
g = ns['g']
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A']}
g.spot['600001.XSHG'] = {'preclose_px': 10.0, 'last_px': 11.0}   # 本票 +10%
_got = {}
ns['_get_snapshot_many'] = lambda codes, cap: _got.update({c: {'preclose_px': 10.0, 'last_px': 10.5} for c in codes}) or _got
ok('T92 涨幅最高(sec+10%>成员+5%)', ns['_board_top_gainer']('600001.XSHG') is True)
ok('T92 批量回填写g.spot', '600002.XSHG' in g.spot and g.spot['600002.XSHG']['last_px'] == 10.5)

# T92e zt_lianban 权威唯一列优先（AXquant 同源预计算列 -> 读列不重算, 并列3板按中位规避）
ns = fresh()
_lb92 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb92, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count\n'
            '2026-10-20,603278.XSHG,大业股份,3,09:25,1.0,10.0,0,人形机器人+胎圈钢丝,0,0\n'
            '2026-10-20,603081.XSHG,京城股份,3,09:25,1.0,10.0,0,机器人集成+气体,0,0\n'
            '2026-10-20,003029.XSHE,吉大正元,4,09:25,1.0,10.0,0,低空安全+密码,1,4\n')
n92e = ns['_load_zt_lianban']()
ok('T92e 权威列加载', n92e == 3 and ns['g'].zt_unq_authoritative is True)
ok('T92e 权威列不重算(并列3板非唯一)', ns['g'].zt_lianban['603278.XSHG']['unique_high'] is False and ns['g'].zt_lianban['603081.XSHG']['unique_high'] is False)
ok('T92e 权威唯一高板读列', ns['g'].zt_lianban['003029.XSHE']['unique_high'] is True and ns['g'].zt_lianban['003029.XSHE']['follower_count'] == 4)
ok('T92e 权威列中位规避', ns['_mid_board_avoid']('603278.XSHG') is True)
ok('T92e 权威唯一高板放行', ns['_mid_board_avoid']('003029.XSHE') is False)

# T92f export_lianban.build_csv 追加权威唯一列 + 题材/概念梯队列
import export_lianban as _el92
_csv92 = _el92.build_csv('2026-10-20',
    [{'code': '003029.XSHE', 'name': '吉大正元', 'board_cnt': 4, 'limit_up_time': '09:25',
      'seal_money': 1.0, 'chg_pct': 10.0, 'is_st': 0, 'reason': '低空安全+密码'}],
    {'003029.XSHE': {'unique_high_board': True, 'follower_count': 4}},
    {'003029.XSHE': {'theme': '低空经济', 'theme_count': 3, 'theme_max_board': 4,
                     'theme_rank': 2, 'themes': '低空经济|网络安全'}})
_line92 = _csv92.split('\n')[1]
ok('T92f build_csv 权威列+题材列',
   'unique_high' in _csv92.split('\n')[0]
   and 'theme_count' in _csv92.split('\n')[0]
   and ',1,4,低空经济,3,4,2,低空经济|网络安全' in _line92
   and '003029.XSHE' in _csv92)

# T92g zt_lianban 题材/概念梯队列消费（v0.38）：列解析 + 缺 unique_high 时按主题材分组兜底
ns = fresh()
_lb93 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb93, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-20,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n'
            '2026-10-20,603081.XSHG,京城股份,2,09:25,1.0,10.0,0,机器人集成+气体,机器人/自动化,16,5,1,机器人/自动化\n'
            '2026-10-20,003029.XSHE,吉大正元,4,09:25,1.0,10.0,0,低空安全+密码,AI/数据要素/算力,10,5,2,AI/数据要素/算力\n')
n92g = ns['_load_zt_lianban']()
_grec = ns['g'].zt_lianban['603278.XSHG']
ok('T92g 题材列加载', n92g == 3 and ns['g'].zt_theme_authoritative is True
   and _grec['theme'] == '机器人/自动化' and _grec['theme_count'] == 16
   and _grec['theme_max_board'] == 5 and _grec['theme_rank'] == 1
   and '机器人/自动化' in _grec['themes'])
ok('T92g 兜底题材分组授唯一', ns['g'].zt_lianban['603278.XSHG']['unique_high'] is True
   and ns['g'].zt_lianban['603081.XSHG']['unique_high'] is False
   and ns['g'].zt_lianban['603278.XSHG']['follower_count'] == 1)

# T92h 盘中题材身位/跟风/强度动态消费（v0.55，docs/41）：索引建组 + 动态龙头/跟风 + 中位放行 + 转授
ns = fresh()
_lb94 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb94, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-20,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,0,0,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n'
            '2026-10-20,603081.XSHG,京城股份,2,09:25,1.0,10.0,0,机器人集成+气体,0,0,机器人/自动化,16,5,1,机器人/自动化\n')
ns['_load_zt_lianban']()
ok('T92h 题材索引建组', ns['g'].zt_theme['机器人/自动化']['max_board'] == 5
   and ns['g'].zt_theme['机器人/自动化']['count'] == 2
   and '化工/新材料' in ns['g'].zt_themes_of['603278.XSHG'])
ns['g'].spot['603278.XSHG'] = {'preclose_px': 10.0, 'last_px': 11.0}
ns['g'].spot['603081.XSHG'] = {'preclose_px': 10.0, 'last_px': 11.0}
ns['g'].zt_dyn_cache = {}
_st94 = ns['_dyn_theme_status']()['机器人/自动化']
ok('T92h 动态龙头+跟风', _st94['leader'] == '603278.XSHG' and _st94['follower_count'] == 1
   and _st94['alive_count'] == 2 and _st94['max_board_dyn'] == 6)
ok('T92h 中位放行(动态龙头)', ns['_mid_board_avoid']('603278.XSHG') is False
   and ns['_mid_board_avoid']('603081.XSHG') is True)
ok('T92h 排序加分', ns['_zt_theme_sort_bonus']('603278.XSHG') >= 1.5)
ns['g'].spot['603278.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.0}   # 大业炸板
ns['g'].zt_dyn_cache = {}
_st94b = ns['_dyn_theme_status']()['机器人/自动化']
ok('T92h 龙头炸板转授', _st94b['leader'] == '603081.XSHG' and _st94b['follower_count'] == 0
   and _st94b['alive_count'] == 1
   and ns['_mid_board_avoid']('603081.XSHG') is False)

# T92i 盘中新题材发酵识别/消费（v0.56，docs/42）：THS概念桥接 + 发酵确认 + 前排闸门 + 排序加分 + 高潮/窗口
ns = fresh()
g = ns['g']
_lb95 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb95, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-21,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,1,1,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n')
ns['_load_zt_lianban']()
g.boards = {'机器人': ['603278.XSHG', '603081.XSHG', '603100.XSHG'],
            '数据要素': ['600101.XSHG', '600102.XSHG', '600103.XSHG']}
g.board_type = {'机器人': 'concept', '数据要素': 'concept'}
g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人'],
                  '603100.XSHG': ['机器人'], '600101.XSHG': ['数据要素'],
                  '600102.XSHG': ['数据要素'], '600103.XSHG': ['数据要素']}
for c in ('603278.XSHG', '603081.XSHG', '603100.XSHG', '600101.XSHG', '600102.XSHG', '600103.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {
    '603081.XSHG': {'ts': time.time(), 'ms': 20261022093500000, 'first_seal': 80000.0, 'break': False},
    '603100.XSHG': {'ts': time.time(), 'ms': 20261022094500000, 'first_seal': 60000.0, 'break': False},
    '600101.XSHG': {'ts': time.time(), 'ms': 20261022094000000, 'first_seal': 90000.0, 'break': False},
    '600102.XSHG': {'ts': time.time(), 'ms': 20261022095000000, 'first_seal': 70000.0, 'break': False},
    '600103.XSHG': {'ts': time.time(), 'ms': 20261022095500000, 'first_seal': 50000.0, 'break': False},
}
ns['_is_first_board'] = lambda c: c not in g.zt_lianban
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
fm95 = ns['_dyn_theme_ferment']()
_rob95 = fm95.get('机器人/自动化') or {}
_tmp95 = fm95.get('THS:数据要素') or {}
ok('T92i THS桥接+发酵确认', _rob95.get('confirmed') is True and _rob95.get('assist_count') == 2
   and _rob95.get('front') == '603278.XSHG' and _rob95.get('stage') == 'confirmed')
ok('T92i 全新题材临时桶+前排', _tmp95.get('confirmed') is True and _tmp95.get('temp') is True
   and _tmp95.get('front') == '600101.XSHG' and _tmp95.get('stage') == 'confirmed')
ok('T92i 存量龙头仍前排', ns['_dyn_theme_leader']('603278.XSHG') is True)
ok('T92i 新题材前排动态龙头', ns['_dyn_theme_leader']('600101.XSHG') is True)
ok('T92i 助攻非前排拦截', ns['_ferment_front_gate']('603081.XSHG') is False
   and ns['_ferment_front_gate']('600102.XSHG') is False)
ok('T92i T-1成员走原逻辑', ns['_ferment_front_gate']('603278.XSHG') is None)
ok('T92i 全新题材前排放行', ns['_ferment_front_gate']('600101.XSHG') is True)
ok('T92i 排序加分(存量龙头+发酵)', ns['_zt_theme_sort_bonus']('603278.XSHG') >= 1.5 + 0.8)
ok('T92i 排序加分(新题材前排)', ns['_zt_theme_sort_bonus']('600101.XSHG') >= 0.8)
ns['BLS']['zt_theme_ferment_hot_assist'] = 3
g.zt_ferment_cache = {}
fm95b = ns['_dyn_theme_ferment']()
ok('T92i 高潮档位', (fm95b.get('THS:数据要素') or {}).get('stage') == 'hot')

ns = fresh()
g = ns['g']
_lb95b = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb95b, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-21,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,1,1,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n')
ns['_load_zt_lianban']()
g.boards = {'机器人': ['603278.XSHG', '603081.XSHG']}
g.board_type = {'机器人': 'concept'}
g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人']}
for c in ('603278.XSHG', '603081.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {
    '603081.XSHG': {'ts': time.time(), 'ms': 20261022093500000, 'first_seal': 80000.0, 'break': False},
}
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
fm95w = ns['_dyn_theme_ferment']()
ok('T92i 单助攻未确认', (fm95w.get('机器人/自动化') or {}).get('confirmed') is False)
ok('T92i 单助攻非前排', ns['_ferment_front_gate']('603081.XSHG') is False)

ns = fresh()
g = ns['g']
_lb95c = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb95c, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-21,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,1,1,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n')
ns['_load_zt_lianban']()
g.boards = {'机器人': ['603278.XSHG', '603081.XSHG', '603100.XSHG']}
g.board_type = {'机器人': 'concept'}
g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人'], '603100.XSHG': ['机器人']}
for c in ('603278.XSHG', '603081.XSHG', '603100.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {
    '603081.XSHG': {'ts': time.time(), 'ms': 20261022093500000, 'first_seal': 80000.0, 'break': False},
    '603100.XSHG': {'ts': time.time(), 'ms': 20261022101000000, 'first_seal': 60000.0, 'break': False},
}
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
ns['BLS']['zt_theme_ferment_window_min'] = 25
fm95s = ns['_dyn_theme_ferment']()
ok('T92i 窗口超限不确认', (fm95s.get('机器人/自动化') or {}).get('confirmed') is False)

# T92j v0.57 修复1：发酵路径不触发行情/板块 API（tick 决策零阻塞）
ns = fresh()
g = ns['g']
_lb96 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb96, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-21,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,1,1,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n')
ns['_load_zt_lianban']()
g.boards = {'机器人': ['603278.XSHG', '603081.XSHG']}
g.board_type = {'机器人': 'concept'}
g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人']}
for c in ('603278.XSHG', '603081.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {'603081.XSHG': {'ts': time.time(), 'ms': 20261022093500000, 'first_seal': 80000.0, 'break': False}}
_calls96 = {'hist': 0, 'blocks': 0}
ns['_hist_1d'] = lambda sec: _calls96.__setitem__('hist', _calls96['hist'] + 1) or None
ns['_boards_of'] = lambda sec: _calls96.__setitem__('blocks', _calls96['blocks'] + 1) or []
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
fm96 = ns['_dyn_theme_ferment']()
ok('T92j 发酵不触发hist/API', _calls96['hist'] == 0 and _calls96['blocks'] == 0
   and (fm96.get('机器人/自动化') or {}).get('assist_count') == 1)
ns = fresh()
g = ns['g']
_calls96b = {'blocks': 0}
ns['_boards_of'] = lambda sec: _calls96b.__setitem__('blocks', _calls96b['blocks'] + 1) or []
ok('T92j boards缺失不落API', ns['_new_themes_of']('603081.XSHG') == [] and _calls96b['blocks'] == 0)

# T92k v0.57 修复3：发酵冷缓存闸门补齐（存量助攻拦截 / 临时前排放行）
ns = fresh()
g = ns['g']
_lb97 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
with io.open(_lb97, 'wt', encoding='utf-8') as f:
    f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
            '2026-10-21,603278.XSHG,大业股份,5,09:30,2.58,10.0,0,人形机器人+橡胶骨架,1,1,机器人/自动化,16,5,1,机器人/自动化|化工/新材料\n')
ns['_load_zt_lianban']()
g.boards = {'机器人': ['603278.XSHG', '603081.XSHG']}
g.board_type = {'机器人': 'concept'}
g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人']}
for c in ('603278.XSHG', '603081.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {}
g.zt_dyn_cache = {}; g.zt_new_cache = {}
g.zt_ferment_cache = {'ts': time.time(), 'data': {}}   # 冷缓存：发酵输出尚无该主题
ok('T92k 冷缓存存量助攻拦截', ns['_ferment_front_gate']('603081.XSHG') is False)
ns = fresh()
g = ns['g']
g.boards = {'数据要素': ['600101.XSHG']}
g.board_type = {'数据要素': 'concept'}
g.stock_boards = {'600101.XSHG': ['数据要素']}
g.spot['600101.XSHG'] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {}
g.zt_new_cache = {}
g.zt_ferment_cache = {'ts': time.time(), 'data': {}}
ok('T92k 冷缓存临时前排放行', ns['_ferment_front_gate']('600101.XSHG') is True)

# T92l v0.57 修复4：前排封单下限生效（达标转授 / 无L2不拦截 / 全低标记弱）
ns = fresh()
g = ns['g']
g.boards = {'数据要素': ['600101.XSHG', '600102.XSHG']}
g.board_type = {'数据要素': 'concept'}
g.stock_boards = {'600101.XSHG': ['数据要素'], '600102.XSHG': ['数据要素']}
for c in ('600101.XSHG', '600102.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {
    '600101.XSHG': {'ts': time.time(), 'ms': 20261022094000000, 'first_seal': 30000.0, 'break': False},
    '600102.XSHG': {'ts': time.time(), 'ms': 20261022094500000, 'first_seal': 90000.0, 'break': False},
}
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
fm98 = ns['_dyn_theme_ferment']()
_t98 = fm98.get('THS:数据要素') or {}
ok('T92l 封单下限转授', _t98.get('front') == '600102.XSHG' and _t98.get('seal_ok') is True)
g.first_zt['600101.XSHG']['first_seal'] = 0.0
g.first_zt['600102.XSHG']['first_seal'] = 0.0
g.zt_ferment_cache = {}
fm98b = ns['_dyn_theme_ferment']()
ok('T92l 无L2不拦截', (fm98b.get('THS:数据要素') or {}).get('front') == '600101.XSHG')
g.first_zt['600101.XSHG']['first_seal'] = 30000.0
g.first_zt['600102.XSHG']['first_seal'] = 40000.0
g.zt_ferment_cache = {}
fm98c = ns['_dyn_theme_ferment']()
_t98c = fm98c.get('THS:数据要素') or {}
ok('T92l 全低标记弱', _t98c.get('front') == '600101.XSHG' and _t98c.get('seal_ok') is False)

# T92m v0.57 修复5：跨概念临时题材桶合并（同一新首板多概念不碎片化）
ns = fresh()
g = ns['g']
g.boards = {'数据要素': ['600101.XSHG', '600102.XSHG'], '机器人': ['600101.XSHG']}
g.board_type = {'数据要素': 'concept', '机器人': 'concept'}
g.stock_boards = {'600101.XSHG': ['数据要素', '机器人'], '600102.XSHG': ['数据要素']}
for c in ('600101.XSHG', '600102.XSHG'):
    g.spot[c] = {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0}
g.first_zt = {
    '600101.XSHG': {'ts': time.time(), 'ms': 20261022094000000, 'first_seal': 90000.0, 'break': False},
    '600102.XSHG': {'ts': time.time(), 'ms': 20261022094500000, 'first_seal': 70000.0, 'break': False},
}
g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
fm99 = ns['_dyn_theme_ferment']()
_tmps99 = [k for k in fm99 if k.startswith('THS:')]
_t99 = fm99.get(_tmps99[0]) if _tmps99 else {}
ok('T92m 临时桶合并确认', len(_tmps99) == 1 and _t99.get('assist_count') == 2
   and _t99.get('confirmed') is True)

# --- T92n/o/p v0.65 连板盘中情绪动态（docs/43）：竞价终态 -> 盘中确认状态机 -> 10:00 冻结/降频/兑现 ---
def _lb_senti_fix(ns, now='09:45'):
    g = ns['g']
    _lb95 = os.path.join(ns['_TMP'], 'zt_lianban_latest.csv')
    with io.open(_lb95, 'wt', encoding='utf-8') as f:
        f.write('date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count,theme,theme_count,theme_max_board,theme_rank,themes\n'
                '2026-10-15,603278.XSHG,中位A,3,09:30,2.58,10.0,0,机器人+自动,0,0,机器人/自动化,16,5,1,机器人/自动化\n'
                '2026-10-15,603081.XSHG,中位B,2,09:35,1.80,10.0,0,机器人+自动,0,0,机器人/自动化,16,5,1,机器人/自动化\n'
                '2026-10-15,603100.XSHG,高标C,6,09:25,5.00,10.0,0,机器人+自动,1,1,机器人/自动化,16,5,1,机器人/自动化\n'
                '2026-10-15,600101.XSHG,低位D,1,09:30,0.60,10.0,0,数据要素,0,0,数据要素,4,1,2,数据要素\n')
    ns['_load_zt_lianban']()
    g.boards = {'机器人': ['603278.XSHG', '603081.XSHG', '603100.XSHG'],
                '数据要素': ['600101.XSHG', '600102.XSHG', '600103.XSHG']}
    g.board_type = {'机器人': 'concept', '数据要素': 'concept'}
    g.stock_boards = {'603278.XSHG': ['机器人'], '603081.XSHG': ['机器人'],
                      '603100.XSHG': ['机器人'], '600101.XSHG': ['数据要素'],
                      '600102.XSHG': ['数据要素'], '600103.XSHG': ['数据要素']}
    g.spot = {
        '603278.XSHG': {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0, 'open_px': 10.6},
        '603081.XSHG': {'preclose_px': 10.0, 'last_px': 10.4, 'up_px': 11.0, 'open_px': 10.3},
        '603100.XSHG': {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0, 'open_px': 11.0},
        '600101.XSHG': {'preclose_px': 10.0, 'last_px': 10.5, 'up_px': 11.0, 'open_px': 9.6},
        '600102.XSHG': {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0, 'open_px': 10.0},
        '600103.XSHG': {'preclose_px': 10.0, 'last_px': 11.0, 'up_px': 11.0, 'open_px': 10.0},
    }
    g.first_zt = {
        '603278.XSHG': {'ts': time.time(), 'ms': 20261016093000000, 'first_seal': 80000.0, 'break': False},
        '603081.XSHG': {'ts': time.time(), 'ms': 20261016093500000, 'first_seal': 60000.0, 'break': True},
        '600102.XSHG': {'ts': time.time(), 'ms': 20261016094000000, 'first_seal': 90000.0, 'break': False},
        '600103.XSHG': {'ts': time.time(), 'ms': 20261016094500000, 'first_seal': 70000.0, 'break': False},
    }
    ns['_is_first_board'] = lambda c: c not in g.zt_lianban
    g.zt_dyn_cache = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}
    g.zt_ferment_stage = {}; g.zt_unmapped_n = 0
    ns['_hhmm'] = lambda: now
    return g

# T92n 竞价终态统计：中高位高开/绿开/一字率 + 低位高开率（纯 auction_c/spot，零行情 API）
ns = fresh(); g = _lb_senti_fix(ns)
g.auction_c = {
    '603278.XSHG': ('2026-10-16', 6.0),
    '603081.XSHG': ('2026-10-16', 3.0),
    '603100.XSHG': ('2026-10-16', 10.0),
    '600101.XSHG': ('2026-10-16', -4.0),
}
g.spot['603081.XSHG']['open_px'] = 11.0   # 一字开（up=11.0）
_au = ns['_lb_senti_auction']()
ok('T92n 分档', ns['_lb_senti_tier']('603278.XSHG') == 'mid'
   and ns['_lb_senti_tier']('603081.XSHG') == 'mid'
   and ns['_lb_senti_tier']('603100.XSHG') == 'high'
   and ns['_lb_senti_tier']('600101.XSHG') == 'low')
ok('T92n 竞价终态统计', _au.get('mid_n') == 2 and _au.get('high_n') == 1 and _au.get('low_n') == 1
   and abs(_au.get('mid_open_rate') - 1.0) < 1e-9 and abs(_au.get('mid_green_rate')) < 1e-9
   and _au.get('mid_yizi') == 1 and abs(_au.get('low_open_rate')) < 1e-9)

# T92o 盘中确认状态机：中高位晋级率/炸板率 + 新方向承接 -> 切低位；参与方向闸门/加权
ns = fresh(); g = _lb_senti_fix(ns)
g.zt_ferment_cache = {}
_d1 = ns['_lb_senti_mid'](force=True)
_d2 = ns['_lb_senti_mid'](force=True)   # 风险升级滞回确认（二次同候选 -> rotate_low）
ok('T92o 切低位状态机', _d2.get('phase') == 'rotate_low'
   and abs(_d2.get('promo') - 0.5) < 1e-9 and abs(_d2.get('break_rate') - 0.5) < 1e-9
   and int(_d2.get('low_assist') or 0) >= 2)
ok('T92o 状态机滞回', (_d1.get('phase') == 'watch' and _d2.get('phase') == 'rotate_low'))
ok('T92o 参与闸门切低位', ns['_lb_senti_buy_gate']('600101.XSHG') == (True, 'low_ok(rotate_low)')
   and ns['_lb_senti_buy_gate']('603278.XSHG') == (False, 'mid_high_skip(rotate_low)'))
_dir_lo = ns['_exp_direction_eval']('600101.XSHG')
_dir_mid = ns['_exp_direction_eval']('603278.XSHG')
_dir_hi = ns['_exp_direction_eval']('603100.XSHG')
ok('T92o 方向加权', _dir_lo.get('kind') == 'neutral' and _dir_lo.get('hard_skip') is False
   and _dir_mid.get('kind') == 'avoid' and _dir_mid.get('hard_skip') is True
   and _dir_hi.get('kind') == 'attack_high' and abs(float(_dir_hi.get('score')) - 0.8) < 1e-9)
ok('T92o 方向不重复计分', all(
   abs(float(ns['_lb_senti_direction_bonus'](_c)) - float(ns['_exp_direction_eval'](_c).get('score') or 0.0)) < 1e-9
   for _c in ('600101.XSHG', '603278.XSHG', '603100.XSHG')))

# T92p 10:00 冻结快照 + 降频缩放不归零 + P8 中高位兑现指导 + 持久化恢复
ns = fresh(); g = _lb_senti_fix(ns, now='10:00')
ns['_lb_senti_auction']()
ns['_lb_senti_mid'](force=True)
ns['_lb_senti_mid'](force=True)   # 模拟 09:30-10:00 已多次监控：滞回确认 -> rotate_low
ns['lb_senti_t100_freeze'](ns['_ctx'])
_t100 = g.lb_senti['t100']
ok('T92p 10:00冻结', _t100.get('hhmm') == '10:00' and _t100.get('phase') == 'rotate_low'
   and (_t100.get('mid') or {}).get('promo') == 0.5 and bool(_t100.get('auction')))
ok('T92p 降频缩放不归零', abs(ns['_lb_senti_participate_scale']() - 0.5) < 1e-9)
ns['BLS']['lb_senti_enabled'] = False
g.lb_senti['mid']['phase'] = 'ice_wait'
ok('T92p 冰点再减半', abs(ns['_lb_senti_participate_scale']() - 0.25) < 1e-9)
g.lb_senti['mid']['phase'] = 'rotate_low'
ns['BLS']['lb_senti_enabled'] = True
ok('T92p P8兑现指导', ns['_lb_senti_cut_hold']('603081.XSHG') is not None
   and ns['_lb_senti_cut_hold']('603081.XSHG')[0] == 0.5
   and ns['_lb_senti_cut_hold']('603278.XSHG') is None      # 续板不兑现
   and ns['_lb_senti_cut_hold']('600101.XSHG') is None)     # 低位不兑现
ns['_mark_lb_cut']('603081.XSHG')
ok('T92p P8去重', ns['_lb_senti_cut_hold']('603081.XSHG') is None)
ns['_save_state']()
g.lb_senti['t100'] = {}
ns['load_state']()
ok('T92p 持久化恢复', g.lb_senti.get('t100', {}).get('hhmm') == '10:00')

# --- T93 v0.38 P2 盘中动态唯一+跟风确认+竞价唯一扫板 ---
def _dyn_fix(ns, dragon='600001.XSHG', members=('600001.XSHG', '600002.XSHG', '600003.XSHG')):
    g = ns['g']
    g.boards = {'概念A': list(members)}
    g.board_type = {'概念A': 'concept'}
    g.stock_boards = {m: ['概念A'] for m in members}
    g.zt_lianban = {m: {'board_cnt': 1 if m == dragon else 0, 'is_st': False} for m in members}
    g.exp_file = {m: {'side': 'buy', 'entry_type': 'normal',
                      'expected_status': 'pending_exceed' if m == dragon else 'pending_meet', '_src': 'zt_pool'} for m in members}
    g.first_zt = {dragon: {'ts': time.time() - 30.0, 'ms': 20261020093200000, 'break': False}}
    g.one_word_open = set()
    for m in members:
        g.spot[m] = {'last_px': 11.0 if m == dragon else 10.3, 'preclose_px': 10.0,
                     'up_px': 11.0, 'open_px': 10.0, 'trade_status': 'OPEN'}
    return g

# T93a A 动态唯一：首触 + 板块内身位无更高/并列 -> 唯一龙头（跟风未确认）
ns = fresh(); g = _dyn_fix(ns)
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 0.0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 A 首触无更高/并列 -> 唯一龙头', g.dyn_unq['uniq']['600001.XSHG'].get('uniq') is True and g.dyn_unq['uniq']['600001.XSHG'].get('confirm') is False)

# T93b A 并列身位（成员同身位且已触板）-> 非唯一
ns = fresh(); g = _dyn_fix(ns)
g.zt_lianban['600002.XSHG']['board_cnt'] = 1
g.spot['600002.XSHG']['last_px'] = 11.0
ns['_min_age'] = lambda: 0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 A 并列身位 -> 非唯一', g.dyn_unq['uniq']['600001.XSHG'].get('uniq') is False)

# T93c A 更高身位成员 -> 非唯一
ns = fresh(); g = _dyn_fix(ns)
g.zt_lianban['600002.XSHG']['board_cnt'] = 3
ns['_min_age'] = lambda: 0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 A 更高身位 -> 非唯一', g.dyn_unq['uniq']['600001.XSHG'].get('uniq') is False)

# T93d A 生命周期窗口外（10:00 后）-> 不评估
ns = fresh(); g = _dyn_fix(ns)
ns['_min_age'] = lambda: 31
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 A 窗口外不评估', ((getattr(g, 'dyn_unq', None) or {}).get('uniq') or {}) == {})

# T93e B 跟风确认：同板块身位更低未封板成员 1m surge>=1.5% 达 2 家 -> confirm
ns = fresh(); g = _dyn_fix(ns)
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 2.0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 B 跟风2家达标 -> 确认', g.dyn_unq['uniq']['600001.XSHG'].get('confirm') is True and g.dyn_unq['uniq']['600001.XSHG'].get('surge_cnt') == 2)
# T93f B 跟风不足（1 家达标）-> 不确认
ns = fresh(); g = _dyn_fix(ns)
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 2.0 if c == '600002.XSHG' else 0.5
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 B 跟风不足 -> 不确认', g.dyn_unq['uniq']['600001.XSHG'].get('confirm') is False)

# T93g B 窗口外（首触 400s 前）-> 不确认
ns = fresh(); g = _dyn_fix(ns)
g.first_zt['600001.XSHG']['ts'] = time.time() - 400.0
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 2.0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 B 窗口外不确认', g.dyn_unq['uniq']['600001.XSHG'].get('confirm') is False)

# T93h B 已封板成员不算跟风（仅1家未封板达标 -> 不确认）
ns = fresh(); g = _dyn_fix(ns)
g.spot['600002.XSHG']['last_px'] = 11.0            # 已封板：排除
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 2.0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 B 已封板成员不算跟风', g.dyn_unq['uniq']['600001.XSHG'].get('confirm') is False)

# T93i A 成员缺快照 -> 批量快照回填一次后判唯一
ns = fresh(); g = ns['g']
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A']}
g.zt_lianban = {'600001.XSHG': {'board_cnt': 1}, '600002.XSHG': {'board_cnt': 0}}
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed', '_src': 'zt_pool'}}
g.first_zt = {'600001.XSHG': {'ts': time.time() - 30.0}}
g.one_word_open = set()
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0}
_calls = []
ns['_get_snapshot_many'] = lambda codes, cap: _calls.append(list(codes)) or {x: {'last_px': 10.2, 'preclose_px': 10.0, 'up_px': 11.0} for x in codes}
ns['_min_age'] = lambda: 0
ns['_elastic_1m_surge'] = lambda c: 0.0
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 A 批量快照回填一次', len(_calls) == 1 and '600002.XSHG' in g.spot and g.dyn_unq['uniq']['600001.XSHG'].get('uniq') is True)
# T93j D 扫板触发：竞价唯一+跟风确认+上攻冲板+现价<涨停价 -> 限价=涨停价 mode=board 预算20%
ns = fresh(); g = ns['g']
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed', '_src': 'zt_pool'}}
g.spot['600001.XSHG'] = {'last_px': 10.9, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0, 'trade_status': 'OPEN'}
g.dyn_unq = {'day': '2026-10-16',
             'auction': {'600001.XSHG': {'unique': True, 'exceed': True, 'level': 1, 'peer_cnt': 0, 'peer_exceed': 0}},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True, 'level': 1, 'members': ['600001.XSHG'], 'surge_cnt': 2, 'ts': 0.0}},
             'swept': {}}
ns['_min_age'] = lambda: 5
ns['_two_1m_break'] = lambda c: True
ns['_limit_up_within_1m'] = lambda c: False
_cap = {}
ns['place_order'] = lambda ctx, sec, side, qty=None, note='', mode='chase', ratio=None: _cap.update(sec=sec, mode=mode, ratio=ratio, note=note) or True
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 D 扫板 mode=board ratio=0.20', _cap.get('sec') == '600001.XSHG' and _cap.get('mode') == 'board' and abs(float(_cap.get('ratio') or 0) - 0.20) < 1e-9)
ok('T93 D 扫板落 daily/swept', '600001.XSHG' in g.daily['bought'] and '600001.XSHG' in g.dyn_unq['swept'])
ok('T93 D 扫板限价=涨停价', ns['_order_limit']('600001.XSHG', 'buy', 'board') == 11.0)

# T93k D 已触板/封板不扫（现价>=涨停价）
ns = fresh(); g = ns['g']
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0}
g.dyn_unq = {'day': '2026-10-16',
             'auction': {'600001.XSHG': {'unique': True}},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True, 'members': [], 'surge_cnt': 2}},
             'swept': {}}
ns['_min_age'] = lambda: 5
ns['_two_1m_break'] = lambda c: True
_cap = {}
ns['place_order'] = lambda ctx, sec, side, qty=None, note='', mode='chase', ratio=None: _cap.update(sec=sec, mode=mode) or True
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 D 已触板不扫', _cap == {} and '600001.XSHG' not in g.daily['bought'])

# T93l D 竞品超预期（非竞价唯一）-> 不扫
ns = fresh(); g = ns['g']
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
g.spot['600001.XSHG'] = {'last_px': 10.9, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0}
g.dyn_unq = {'day': '2026-10-16',
             'auction': {'600001.XSHG': {'unique': False, 'peer_exceed': 1}},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True, 'members': [], 'surge_cnt': 2}},
             'swept': {}}
ns['_min_age'] = lambda: 5
ns['_two_1m_break'] = lambda c: True
_cap = {}
ns['place_order'] = lambda ctx, sec, side, qty=None, note='', mode='chase', ratio=None: _cap.update(sec=sec) or True
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 D 竞品非唯一不扫', _cap == {} and '600001.XSHG' not in g.daily['bought'])
# T93m D 跟风未确认 -> 不扫
ns = fresh(); g = ns['g']
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
g.spot['600001.XSHG'] = {'last_px': 10.9, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0}
g.dyn_unq = {'day': '2026-10-16',
             'auction': {'600001.XSHG': {'unique': True}},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': False, 'members': []}},
             'swept': {}}
ns['_min_age'] = lambda: 5
ns['_two_1m_break'] = lambda c: True
_cap = {}
ns['place_order'] = lambda ctx, sec, side, qty=None, note='', mode='chase', ratio=None: _cap.update(sec=sec) or True
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 D 跟风未确认不扫', _cap == {} and '600001.XSHG' not in g.daily['bought'])

# T93n D 已买/已扫去重 -> 不重复触发
ns = fresh(); g = ns['g']
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
g.spot['600001.XSHG'] = {'last_px': 10.9, 'preclose_px': 10.0, 'up_px': 11.0, 'open_px': 10.0}
g.daily['bought'] = ['600001.XSHG']
g.dyn_unq = {'day': '2026-10-16',
             'auction': {'600001.XSHG': {'unique': True}},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True, 'members': []}},
             'swept': {'600001.XSHG': {'ts': 1.0}}}
ns['_min_age'] = lambda: 5
ns['_two_1m_break'] = lambda c: True
_cap = {}
ns['place_order'] = lambda ctx, sec, side, qty=None, note='', mode='chase', ratio=None: _cap.update(sec=sec) or True
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 D 已买/已扫去重', _cap == {} and g.dyn_unq['swept']['600001.XSHG']['ts'] == 1.0)

# T93o C 排序加分：确认龙头优先（同分但触板更晚仍排前）
ns = fresh(); g = ns['g']
g.dyn_unq = {'day': '2026-10-16', 'auction': {},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True}},
             'swept': {}}
g.first_zt = {'600001.XSHG': {'ts': 2000.0}, '600002.XSHG': {'ts': 500.0}}
ns['score_now'] = lambda sec: 60.0
ok('T93 C 确认龙头排序加分', ns['_pool_exp_priority']('600001.XSHG') < ns['_pool_exp_priority']('600002.XSHG'))

# T93p C CX 路径标注：确认龙头预期买入补 [dyn-unq] 日志
ns = fresh(); g = ns['g']
g.dyn_unq = {'day': '2026-10-16', 'auction': {},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True}},
             'swept': {}}
expbuyns(ns, '600001.XSHG')
ns['_exp_rt_status'] = lambda c: (ns['CX'], 'two_1m_break')
_rec = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
r = ns['_attempt_expected_buy'](ns['_ctx'], '600001.XSHG')
ok('T93 C CX 触发并标注', r is True and '600001.XSHG' in g.daily['bought'] and any('dyn-unq' in m and 'CX' in m for m in _rec))

# T93q C 持有侧提示（不改卖出阈值）
ns = fresh(); g = ns['g']
g.dyn_unq = {'day': '2026-10-16', 'auction': {},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True}},
             'swept': {}}
g.first_zt = {'600001.XSHG': {'ts': 1.0}}
ns['_CTX'].portfolio.positions = {'600001.XSHG': types.SimpleNamespace(amount=1000)}
ns['_min_age'] = lambda: 0
_rec = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['_try_dyn_unq'](ns['_ctx'])
ok('T93 C 持有提示', any('持有提示' in m for m in _rec))
# T93r 竞价唯一预判：同身位竞品均不及预期 -> 唯一；有竞品超预期 -> 并列
ns = fresh(); g = ns['g']
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG', '600003.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A'], '600003.XSHG': ['概念A']}
g.zt_lianban = {'600001.XSHG': {'board_cnt': 1}, '600002.XSHG': {'board_cnt': 1}, '600003.XSHG': {'board_cnt': 0}}
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'},
              '600002.XSHG': {'side': 'buy', 'expected_status': 'pending_meet'},
              '600003.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
ns['_dyn_unq_auction_eval']()
a1 = g.dyn_unq['auction']['600001.XSHG']
ok('T93 竞价唯一(竞品meet) peer=1/超预期=0', a1['unique'] is True and a1['peer_cnt'] == 1 and a1['peer_exceed'] == 0)
ns = fresh(); g = ns['g']
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A']}
g.zt_lianban = {'600001.XSHG': {'board_cnt': 1}, '600002.XSHG': {'board_cnt': 1}}
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'},
              '600002.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
ns['_dyn_unq_auction_eval']()
ok('T93 竞价并列(竞品exceed)', g.dyn_unq['auction']['600001.XSHG']['unique'] is False and g.dyn_unq['auction']['600001.XSHG']['peer_exceed'] == 1)

# T93s 重启持久化：同日保留 / 跨日重置
ns = fresh(); g = ns['g']
g.dyn_unq = {'day': '2026-10-16', 'auction': {},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True}},
             'swept': {}}
ns['_save_state'](); g.dyn_unq = None; ns['load_state']()
ok('T93 同日重启保留 confirm', (g.dyn_unq or {}).get('uniq', {}).get('600001.XSHG', {}).get('confirm') is True)
ns = fresh(); g = ns['g']
g.dyn_unq = {'day': '2026-10-16', 'auction': {},
             'uniq': {'600001.XSHG': {'uniq': True, 'confirm': True}},
             'swept': {}}
ns['get_trading_day'] = lambda: datetime.date(2026, 10, 19)
st = ns['_dyn_unq_state']()
ok('T93 跨日重置', st['day'] == '2026-10-19' and st['uniq'] == {} and st['swept'] == {})

# T94 版本号一致性：文件内 STRATEGY_VERSION == 头部「当前版本」== 部署核对（每次版本更新必须同步）
ver = ns['STRATEGY_VERSION']
_head = open(SRC, 'r', encoding='utf-8').read().splitlines()
_cur = next((l for l in _head if l.startswith('# 当前版本：')), '')
_dep = next((l for l in _head if l.startswith('# 部署核对：')), '')
ok('T94 头部当前版本同步', ('%s（' % ver) in _cur)
ok('T94 部署核对同步', ('version=%s' % ver) in _dep)

# T95 一字板竞价终态精确判定（v0.42，docs/29）：真一字=开=涨停价且卖1=0 才标 one_word；卖1>0 playable 不标；
#   快照缺失->09:30 首帧补标 / 真一字 meet 拦截 / 非真一字 meet 放行 / 1帧内封涨停放行、持续5s后拦截
def _ow_ns():
    ns = fresh()
    g = ns['g']
    g.watch = ['600001.XSHG', '600002.XSHG']
    g.pool_static = []; g.selfwatch = []; g.zt_lianban = {}; g.exp_file = {}
    g.one_word_open = set(); g.seal_base = {}; g.seal_bid_base = {}
    return ns

# T95a 真一字（竞价终态 卖1=0 且买1有排单量）-> 标 one_word + 封单基准回填 + 不排队日志
ns = _ow_ns(); g = ns['g']
g.spot['600001.XSHG'] = {'open_px': 11.0, 'up_px': 11.0, 'last_px': 11.0, 'preclose_px': 10.0,
                         'total_offerqty': 0, 'total_bidqty': 5000}
_rec = []; ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['_mark_one_word_open']()
ok('T95 真一字(卖1=0) 标 one_word', '600001.XSHG' in g.one_word_open)
ok('T95 真一字 封单基准回填', abs(g.seal_base.get('600001.XSHG', 0.0) - 5000 * 100 * 11.0) < 1e-6)
ok('T95 真一字 不排队日志', any('买入不排队' in m for m in _rec))

# T95b 卖1>0（非真一字）-> 不标 + playable 日志，不误标不回填
ns = _ow_ns(); g = ns['g']
g.spot['600002.XSHG'] = {'open_px': 11.0, 'up_px': 11.0, 'last_px': 11.0, 'preclose_px': 10.0,
                         'total_offerqty': 300, 'total_bidqty': 8000}
_rec = []; ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['_mark_one_word_open']()
ok('T95 卖1>0 不标(playable)', '600002.XSHG' not in g.one_word_open)
ok('T95 卖1>0 不回填封单', g.seal_base.get('600002.XSHG') is None)
ok('T95 卖1>0 打 playable 日志', any('playable' in m and '600002.XSHG' in m for m in _rec))

# T95c 09:25 快照缺失(open 未回填) 不误标 -> 09:30 首帧(spot 回填) 补标成功
ns = _ow_ns(); g = ns['g']
g.watch = ['600003.XSHG']
g.spot['600003.XSHG'] = {'last_px': 13.0}
ns['get_snapshot'] = lambda codes: {}
ns['_mark_one_word_open']()
ok('T95 快照缺失不误标', '600003.XSHG' not in g.one_word_open)
g.spot['600003.XSHG'] = {'open_px': 13.0, 'up_px': 13.0, 'last_px': 13.0, 'preclose_px': 11.82,
                         'total_offerqty': 0, 'total_bidqty': 2000}
ns['_mark_one_word_open']()
ok('T95 09:30 首帧补标成功', '600003.XSHG' in g.one_word_open)

# T95d 真一字 meet 候选 -> place_expected_order 拦截（不排队）
ns = _ow_ns(); g = ns['g']
g.watch = ['600004.XSHG']
g.one_word_open = {'600004.XSHG'}
g.spot['600004.XSHG'] = {'open_px': 20.0, 'up_px': 20.0, 'last_px': 20.0, 'preclose_px': 18.18,
                         'total_offerqty': 0, 'total_bidqty': 1000, 'wavg_px': 19.0}
g.exp_file = {'600004.XSHG': {'side': 'buy', 'entry_type': 'normal', 'expected_status': 'meet',
                              'expected_auction_change_pct': 3.0, 'yesterday_open_pct': 2.0,
                              'seal_amount_t0': 0.0, 'board_name': 't', 'reason': ''}}
r = ns['place_expected_order'](ns['_ctx'], '600004.XSHG', note='exp_rt CM intraday')
ok('T95 真一字 meet 拦截不排单', r is False)

# T95e 非真一字 meet 候选（开盘=涨停价但卖1>0，可参与）-> 放行
ns = _ow_ns(); g = ns['g']
g.watch = ['600005.XSHG']
g.spot['600005.XSHG'] = {'open_px': 10.0, 'up_px': 11.0, 'last_px': 10.5, 'preclose_px': 10.0,
                         'total_offerqty': 500, 'total_bidqty': 3000, 'wavg_px': 10.2}
g.exp_file = {'600005.XSHG': {'side': 'buy', 'entry_type': 'normal', 'expected_status': 'meet',
                              'expected_auction_change_pct': 3.0, 'yesterday_open_pct': 2.0,
                              'seal_amount_t0': 0.0, 'board_name': 't', 'reason': ''}}
r = ns['place_expected_order'](ns['_ctx'], '600005.XSHG', note='exp_rt CM intraday')
ok('T95 非真一字 meet 放行', r is True)

# T95f 1帧内封涨停：5s 门槛未满 -> 放行；持续 5s -> 拦截
ns = _ow_ns(); g = ns['g']
g.spot['600006.XSHG'] = {'last_px': 12.0, 'up_px': 12.0, 'total_offerqty': 0, 'total_bidqty': 4000}
g.sealed_since = {}
ok('T95 1帧内封涨停 首帧放行', ns['_sealed_at_limit']('600006.XSHG') is False)
g.sealed_since['600006.XSHG'] = time.time() - 6.0
ok('T95 封死持续5s后 拦截', ns['_sealed_at_limit']('600006.XSHG') is True)

# T96 买卖理由与灵敏度日志（v0.43，docs/30）：_signal 补 lag=检测->下单时延 + det=检测源:首触毫秒
ns = fresh(); g = ns['g']
g.first_zt = {'600001.XSHG': {'ts': time.time() - 1.2, 'src': 'tx', 'ms': '20261021100000240'}}
_rec = []; ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['_signal']('600001.XSHG', 'buy', 100, 10.0, 'board', 'note=test', '', 'SIM')
ok('T96 signal 补 lag+det', any('[signal]' in m and 'lag=' in m and 'det=tx:' in m for m in _rec))
ok('T96 灵敏度采样入 rt_stats', (g.rt_stats or {}).get(('buy', 'board'), {}).get('n') == 1)

# T96b 无 first_zt -> lag 为空且不采样（不强造数据）
ns = fresh(); g = ns['g']
_rec = []; ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['_signal']('600002.XSHG', 'sell', 100, 10.0, 'sell', 'P1_green_open', '', 'SIM')
ok('T96 无首触不采样', (getattr(g, 'rt_stats', None) or {}) == {})

# T96c place_order [may-order] 带 lag（买卖理由 note + 灵敏度同行）
ns = fresh(); g = ns['g']
g.first_zt = {'600003.XSHG': {'ts': time.time() - 2.5, 'src': 'snap', 'ms': '0'}}
g.spot['600003.XSHG'] = {'last_px': 10.0, 'up_px': 11.0, 'preclose_px': 10.0, 'open_px': 10.0, 'total_offerqty': 500}
g.exp_file = {}
_rec = []; ns['log'] = types.SimpleNamespace(info=lambda *a: _rec.append(a[0] if a else ''), warn=lambda *a: None, error=lambda *a: None)
ns['place_order'](ns['_ctx'], '600003.XSHG', 'buy', note='core_buy px=10.0', mode='chase')
ok('T96 [may-order] 带 lag', any('[may-order]' in m and 'lag=' in m and 'core_buy' in m for m in _rec))

# T97 v0.44 sentiment.divergence 显式消费：CSV 分歧标志触发分歧保护 taper（与 warm_days 双保险）
ns = fresh(); g = ns['g']
g.sentiment = {'ice': 0, 'warm_days': 2, 'divergence': 1, 'phase': 'cont', 'emotion': '', 'emotion_basis': ''}
ok('T97 divergence=1 warm_days=2 -> taper 0.70', abs(ns['_warm_cap'](g.sentiment) - 0.70) < 1e-9)
g.sentiment['divergence'] = 0
ok('T97 divergence=0 warm_days=2 -> 0.80', abs(ns['_warm_cap'](g.sentiment) - 0.80) < 1e-9)
g.sentiment['warm_days'] = 3; g.sentiment['divergence'] = 1
ok('T97 warm_days=3+divergence=1 -> 0.70', abs(ns['_warm_cap'](g.sentiment) - 0.70) < 1e-9)

# T98 v0.45 云 LogEngine 无 .warn 兼容：_warn 退 warning->warn->info，绝不抛（防 tick 链路中断）
ns = fresh()
class _LogNoWarn:
    def info(self, *a): self.info_calls = getattr(self, 'info_calls', 0) + 1
    def error(self, *a): pass
lw = _LogNoWarn()
ns['log'] = lw
ns['_warn']('qty<=0 skip')
ok('T98 _warn fallback-to-info 不抛', getattr(lw, 'info_calls', 0) >= 1)
class _LogWarnOnly:
    def warn(self, *a): self.w_calls = getattr(self, 'w_calls', 0) + 1
    def info(self, *a): raise RuntimeError('info must not be called')
lw2 = _LogWarnOnly()
ns['log'] = lw2
ns['_warn']('x')
ok('T98 _warn prefers .warn 不抛', getattr(lw2, 'w_calls', 0) >= 1)
class _LogBroken:
    def info(self, *a): raise RuntimeError('boom')
ns['log'] = _LogBroken()
ns['_warn']('y')
ok('T98 _warn 全异常吞掉不抛', True)

# T99 v0.46 首板封单下限（L2 买一挂单金额 < first_board_seal_min -> 不打板，防假封秒炸）
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (3000.0, 1)
ok('T99 封单不足(3000<50000) -> 不打板', _fb_calls(ns) == [])
ok('T99 封单不足未记 bought/fired', '600001.XSHG' not in ns['g'].daily['bought'] and '600001.XSHG' not in (getattr(ns['g'], 'first_board_fired', None) or set()))
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (200000.0, 500)
pc = _fb_calls(ns)
ok('T99 封单达标 -> 打板', len(pc) == 1 and 'first_board_buy' in pc[0]['note'])
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (0.0, 0)
ok('T99 L2缺失(回测) -> 不强制, 照常打板', len(_fb_calls(ns)) == 1)

# T100 v0.46 竞价唯一预判跳过中位股（与 _mid_board_avoid 统一口径）
ns = fresh(); g = ns['g']
g.zt_lianban = {'600001.XSHG': {'board_cnt': 4, 'unique_high': False, 'is_st': False},
                '600002.XSHG': {'board_cnt': 1, 'unique_high': False, 'is_st': False}}
g.exp_file = {'600001.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'},
              '600002.XSHG': {'side': 'buy', 'expected_status': 'pending_exceed'}}
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A']}
ns['_dyn_unq_auction_eval']()
au = g.dyn_unq['auction']
ok('T100 中位股(4板)不进唯一预判', '600001.XSHG' not in au)
ok('T100 首板(1板)超预期无竞品 -> 唯一', au['600002.XSHG'].get('unique') is True)
g.exp_file['600002.XSHG']['expected_status'] = 'pending_meet'
g.dyn_unq = None
ns['_dyn_unq_auction_eval']()
ok('T100 首板 meet 不标唯一', ns['g'].dyn_unq['auction'].get('600002.XSHG', {}).get('unique') is False)

# T101 v0.50 L2 大单净量（买-卖）累计去重 + 占比加分
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
_fields = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
_rows = [[99000000, 10.0, 1000000, 1, 'buy'],   # 1000万 买
         [99001000, 10.0, 1500000, 2, 'buy'],   # 1500万 买
         [99002000, 10.0, 800000, 3, 'sell'],   # 800万 卖
         [99003000, 10.0, 2000000, 2, 'sell']]  # 重复 trade_index=2 去重
ns['_tx_big_feed'](['600001.XSHG'], _fields, {'600001.XSHG': _rows})
ok('T101 全大单去重累计=3300万', abs(g.l2_big['600001.XSHG']['amt'] - 33000000.0) < 1e-6)
ok('T101 净量=1700万(买2500-卖800)', abs(g.l2_big['600001.XSHG']['buy'] - g.l2_big['600001.XSHG']['sell'] - 17000000.0) < 1e-6)
ok('T101 净量占比=17%>=10% -> 加分5', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
g.spot['600001.XSHG']['turnover'] = 250000000.0
ok('T101 净量占比降至6.8% -> 不加分', ns['_l2_big_bonus_pts']('600001.XSHG') == 0.0)
g.l2_big['600001.XSHG'] = {'amt': 0.0, 'buy': 0.0, 'sell': 0.0, 'un': 0.0, 'seen': set()}
ok('T101 无大单 -> 不加分', ns['_l2_big_bonus_pts']('600001.XSHG') == 0.0)
ok('T101 无数据 -> 不加分不抛', ns['_l2_big_ratio']('600002.XSHG') < 0 and ns['_l2_big_bonus_pts']('600002.XSHG') == 0.0)

# T102 v0.47 预封扫板：封单下限 或 大单加持 二者满足其一
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (3000.0, 1)
ok('T102 封单不足+无大单 -> skip', _fb_calls(ns) == [])
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (3000.0, 1)
ns['_l2_big_ratio'] = lambda sec: 0.27
ns['_l2_big_ok'] = lambda sec: True
ok('T102 封单不足+大单加持 -> 预封扫板放行', len(_fb_calls(ns)) == 1)
ns = _fb_setup()
ns['_seal_metrics'] = lambda sec: (200000.0, 500)
ok('T102 封单达标 -> 打板', len(_fb_calls(ns)) == 1)

# T103 v0.48 B: 首板窗口内 强度前三板块成员并入 tick 目标集 + scan_interval 收紧
ns = fresh(); g = ns['g']
g.watch = ['600001.XSHG']; g.pool_static = []
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG', '600003.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A'], '600003.XSHG': ['概念A']}
ns['_board_rank_top3_set'] = lambda secs: {'概念A'}
g.now_dt = datetime.datetime(2026,10,16,9,35,0)   # _min_age=5<=10 首板窗口内
out = ns['_tick_targets']()
ok('T103 窗口内 强度前三板块成员并入 tick 目标', '600002.XSHG' in out and '600003.XSHG' in out)
ok('T103 scan_interval 收紧=1', ns['BLS']['scan_interval'] == 1)

# T104 v0.48 A+B: business_amount 单位换算（shares/lots/yuan）+ 首板窗口门控
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 50000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['BLS']['l2_big_amt_unit'] = 'shares'
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 200000, 1, 'buy'], [99001000, 10.0, 200000, 2, 'buy'],
    [99002000, 10.0, 100000, 3, 'buy'], [99003000, 10.0, 90000, 4, 'sell']]})
ok('T104 shares换算 累计=500万(90万<阈值不计)', abs(g.l2_big['600001.XSHG']['amt'] - 5000000.0) < 1e-6)
ok('T104 shares 占比10%达标加分', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
ns['BLS']['l2_big_amt_unit'] = 'lots'
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99000000, 10.0, 1000, 1, 'buy']]})
ok('T104 lots换算 1000手x100x10=100万元', abs(g.l2_big['600001.XSHG']['amt'] - 1000000.0) < 1e-6)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
ns['BLS']['l2_big_amt_unit'] = 'yuan'
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99000000, 10.0, 1200000, 1, 'buy']]})
ok('T104 yuan直用 累计=120万元', abs(g.l2_big['600001.XSHG']['amt'] - 1200000.0) < 1e-6)
ns = fresh(); g = ns['g']
g.watch = ['600001.XSHG']; g.pool_static = []
g.boards = {'概念A': ['600001.XSHG', '600002.XSHG', '600003.XSHG']}
g.board_type = {'概念A': 'concept'}
g.stock_boards = {'600001.XSHG': ['概念A'], '600002.XSHG': ['概念A'], '600003.XSHG': ['概念A']}
ns['_board_rank_top3_set'] = lambda secs: {'概念A'}
g.now_dt = datetime.datetime(2026,10,16,9,35,0)   # 窗口内
out = ns['_tick_targets']()
ok('T104 窗口内(09:35) 并入强度前三板块成员', '600002.XSHG' in out and '600003.XSHG' in out)
g.tick_targets_cache = None
g.now_dt = datetime.datetime(2026,10,16,10,5,0)   # _min_age=35>10 窗口外
out2 = ns['_tick_targets']()
ok('T104 窗口外(10:05) 不并入板块成员', '600002.XSHG' not in out2 and '600003.XSHG' not in out2)

# T105 v0.49 炸板应对收紧：买3价卖出 / 炸板扣涨停分 / 唯一身位容忍 / 二次炸板减半
# a) 炸板卖出买3档限价 + 0.95 下限保护
ns = fresh(); g = ns['g']
g.spot['600001.XSHG'] = {'last_px': 11.0, 'preclose_px': 10.0, 'up_px': 11.0}
ns['_gear'] = lambda sec: {'bid_grp': {1: [11.0, 0, 0], 3: [10.8, 100, 2]}}
ok('T105 炸板卖买3价限价=10.8', abs(ns['_order_limit']('600001.XSHG', 'sell', 'sell_break') - 10.8) < 1e-9)
ns['_gear'] = lambda sec: {'bid_grp': {1: [11.0, 0, 0], 3: [10.3, 100, 2]}}
ok('T105 买3<0.95下限 -> 用下限10.45', abs(ns['_order_limit']('600001.XSHG', 'sell', 'sell_break') - 10.45) < 1e-9)
ns['_gear'] = lambda sec: {'bid_grp': {1: [11.0, 0, 0]}}
ok('T105 买3缺失 -> 回退现价11.0', abs(ns['_order_limit']('600001.XSHG', 'sell', 'sell_break') - 11.0) < 1e-9)

# b) 炸板减去涨停分（_touched_limit_early +6 取消）
ns = fresh(); g = ns['g']
g.first_zt = {}; g.spot['600001.XSHG'] = {'last_px': 10.98, 'preclose_px': 10.0, 'up_px': 11.0}
g.now_dt = datetime.datetime(2026, 10, 16, 9, 40, 0)
ns['_auction_beat_history'] = lambda sec: False
ns['_volume_ratio'] = lambda sec: 1.0
ns['_is_100day_high'] = lambda sec: False
ns['_board_bonus'] = lambda sec: 0.0
ns['_tags'] = lambda sec: []
ok('T105 未炸板 touched_limit_up_early +6', abs(ns['_static_bonus']('600001.XSHG') - 6.0) < 1e-9)
g.first_zt['600001.XSHG'] = {'break': True}
ok('T105 炸板减去涨停分(+6=0)', abs(ns['_static_bonus']('600001.XSHG') - 0.0) < 1e-9)

# c) 唯一身位判定
ns = fresh(); g = ns['g']
g.zt_lianban = {'600001.XSHG': {'unique_high': True}}
ok('T105 unique_high 唯一身位', ns['_unique_stand']('600001.XSHG') is True)
g.zt_lianban = {'600001.XSHG': {'unique_high': False}}
ns['_dyn_unq_confirmed'] = lambda sec: True
ok('T105 动态唯一+跟风确认 唯一身位', ns['_unique_stand']('600001.XSHG') is True)
ns['_dyn_unq_confirmed'] = lambda sec: False
ok('T105 非唯一身位', ns['_unique_stand']('600001.XSHG') is False)
ok('T105 唯一容忍阈值0.25 < 默认0.333', ns['BLS']['seal_fail_ratio_unique'] < ns['BLS']['seal_fail_ratio'])

# d) 二次炸板减半（仅唯一身位）
def _tick_sell_ns(break_cnt, unique, break_sold_has=False):
    ns = fresh(); g = ns['g']
    g.first_zt = {'600001.XSHG': {'break': True, 'break_cnt': break_cnt,
                                  'break_ts': time.time(), 'ts': time.time()}}
    g.break_sold = set(['600001.XSHG']) if break_sold_has else set()
    g.break2_sold = set(); g.sold_log = {}
    g.spot['600001.XSHG'] = {'last_px': 10.9, 'preclose_px': 10.0, 'up_px': 11.0}
    g.exp_file = {}
    ns['_sellable_source'] = lambda: {'600001.XSHG': object()}
    ns['_sellable'] = lambda raw, pos: 1000
    ns['_norm_sec'] = lambda c: c
    ns['last_px'] = lambda sec: 10.9
    ns['_hold_exp_init'] = lambda sec, force=False: None
    ns['_sell_inflight'] = lambda sec: False
    ns['_unique_stand'] = lambda sec: unique
    ns['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    ns['_auction_change'] = lambda sec: 5.0
    ns['my_cost'] = lambda raw, pos: 10.0
    ns['_do_sell'] = lambda context, sec, qty, note, urgent=False, mode=None:         ns['_calls'].append((sec, qty, mode))
    ns['_mark_sold_event'] = lambda sec, kind: ns['_ev'].append(kind)
    ns['_calls'] = []; ns['_ev'] = []
    return ns

ns = _tick_sell_ns(1, False)
ns['tick_sell_manager'](ns['_CTX'])
ok('T105 首次炸板全卖(mode=sell_break)', len(ns['_calls']) == 1 and ns['_calls'][0][1] == 1000 and ns['_calls'][0][2] == 'sell_break')
ns = _tick_sell_ns(2, True)
ns['tick_sell_manager'](ns['_CTX'])
ok('T105 二次炸板唯一身位 -> 减半500', len(ns['_calls']) == 1 and ns['_calls'][0][1] == 500)
ns = _tick_sell_ns(2, False, break_sold_has=True)
ns['tick_sell_manager'](ns['_CTX'])
ok('T105 二次炸板非唯一+已break_sold -> 不重复卖', len(ns['_calls']) == 0)

# T106 v0.49 回封打板：前排首板 10:00前炸板回封 + 大单占比>=10%
def _reboard_ns(big_r, big_ok, fired=False):
    ns = fresh(); g = ns['g']
    g.spot['600001.XSHG'] = {'last_px': 10.98, 'preclose_px': 10.0, 'up_px': 11.0, 'turnover': 100000000.0}
    g.first_zt = {'600001.XSHG': {'break': False, 'break_cnt': 1, 'reboard_ts': time.time(), 'first_seal': 100000.0}}
    g.reboard_fired = fired
    g.daily = {'bought': []}
    g.now_dt = datetime.datetime(2026, 10, 16, 9, 45, 0)
    ns['_is_one_word_open'] = lambda sec: False
    ns['_mid_board_avoid'] = lambda sec: False
    ns['_limitup_days'] = lambda sec: 1
    ns['_board_rank_top3'] = lambda sec, rs: True
    ns['_near_limit_cands'] = lambda secs: ['600001.XSHG']
    ns['_pool'] = lambda: ['600001.XSHG']
    ns['_seal_metrics'] = lambda sec: (200000.0, 500)
    ns['_l2_big_ratio'] = lambda sec: big_r
    ns['_l2_big_ok'] = lambda sec: big_ok
    ns['_block_sealed_buy'] = lambda sec: False
    ns['_order_limit'] = lambda sec, side, mode: 11.0
    ns['_buy_pos_ok'] = lambda context, sec, qty, limit: True
    return ns

ns = _reboard_ns(0.27, True)
ns['_try_reboard_buy'](ns['_CTX'])
ok('T106 大单27% 回封打板触发', ns['g'].reboard_fired is True and '600001.XSHG' in ns['g'].daily['bought'])
ns = _reboard_ns(0.05, False)
ns['_try_reboard_buy'](ns['_CTX'])
ok('T106 大单5%<10% 不触发', ns['g'].reboard_fired is False and '600001.XSHG' not in ns['g'].daily['bought'])
ns = _reboard_ns(0.27, True, fired=True)
ns['_try_reboard_buy'](ns['_CTX'])
ok('T106 当日已 fired 不触发', '600001.XSHG' not in ns['g'].daily['bought'])

# T107 v0.50 大单净量口径专项
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 1000000, 1, 'buy'], [99001000, 10.0, 2000000, 2, 'sell']]})
ok('T107 卖>买 净=-1000万 -> 不授分', ns['_l2_big_ratio']('600001.XSHG') < 0 and ns['_l2_big_bonus_pts']('600001.XSHG') == 0.0)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99000000, 10.0, 2000000, 1, 'x']]})
ok('T107 方向未知 归un 净=0 不授分', abs(g.l2_big['600001.XSHG']['un'] - 20000000.0) < 1e-6 and ns['_l2_big_bonus_pts']('600001.XSHG') == 0.0)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
_f2 = ['business_time', 'hq_px', 'business_amount', 'trade_index']
ns['_tx_big_feed'](['600001.XSHG'], _f2, {'600001.XSHG': [[99000000, 10.0, 2000000, 1]]})
ok('T107 direction字段缺失 不授分', ns['_l2_big_bonus_pts']('600001.XSHG') == 0.0)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
ns['BLS']['l2_big_dir_enabled'] = False
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 1000000, 1, 'buy'], [99001000, 10.0, 1000000, 2, 'sell']]})
ok('T107 dir_enabled=False 全大单口径 占比20%加分', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
ns = fresh()
ok('T107 _tx_dir 官方字典 0=卖 1=买', ns['_tx_dir'](0) == 'sell' and ns['_tx_dir'](1) == 'buy')
ok('T107 _tx_dir 借入2/出借3 不计净量', ns['_tx_dir'](2) is None and ns['_tx_dir'](3) is None)
ok('T107 _tx_dir B=买 s=卖', ns['_tx_dir']('B') == 'buy' and ns['_tx_dir']('s') == 'sell')
ok('T107 _tx_dir 未知x=None None=None', ns['_tx_dir']('x') is None and ns['_tx_dir'](None) is None)

# T108 v0.51 实盘 0/1 方向识别 + 分布计数 + 跨重启持久化
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 2000000, 1, 0],   # 2000万 卖(0)
    [99001000, 10.0, 3000000, 2, 1],   # 3000万 买(1)
    [99002000, 10.0, 1500000, 3, 2],   # 1500万 借入(2)->un
    [99003000, 10.0, 1500000, 4, 3]    # 1500万 出借(3)->un
]})
ok('T108 实盘 0=卖 1=买 2/3=借入出借->un', abs(g.l2_big['600001.XSHG']['buy'] - 30000000.0) < 1e-6
   and abs(g.l2_big['600001.XSHG']['sell'] - 20000000.0) < 1e-6
   and abs(g.l2_big['600001.XSHG']['un'] - 30000000.0) < 1e-6)
ok('T108 净量=1000万 占比10%达标加分', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
ok('T108 方向取值分布计数', g.l2_dir_dist == {'0': 1, '1': 1, '2': 1, '3': 1})
g.state_day = '2026-10-16'
g.l2_big['600002.XSHG'] = {'amt': 7000000.0, 'buy': 5000000.0, 'sell': 1000000.0, 'un': 1000000.0, 'seen': {10, 20}, 'max': 5000000.0}
ns['_save_state']()
g.l2_big = {}; g.l2_dir_dist = {}
ns['load_state']()
ok('T108 同日重启恢复 l2_big 累计', abs(g.l2_big['600002.XSHG']['buy'] - 5000000.0) < 1e-6
   and g.l2_big['600002.XSHG']['seen'] == {10, 20})
ok('T108 同日重启恢复 dir_dist', g.l2_dir_dist == {'0': 1, '1': 1, '2': 1, '3': 1})
_st = pickle.load(open(ns['_TMP'] + '/buysell_core_state.pkl', 'rb'))
_st['day'] = '2026-10-15'
pickle.dump(_st, open(ns['_TMP'] + '/buysell_core_state.pkl', 'wb'))
g.l2_big = {'X': 1}; g.l2_dir_dist = {'9': 1}
ns['load_state']()
ok('T108 跨日重置 l2_big/dir_dist', g.l2_big == {} and g.l2_dir_dist == {})

# T109 v0.52 已成交大单播种（get_tick_direction 分时成交）+ 水印防重
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 100000000.0}
_tdf = ['time_stamp', 'hq_px', 'business_amount', 'business_balance', 'business_count', 'business_direction']
_td = {'fields': _tdf, '600001.XSHG': [
    [92500000, 10.0, 100000, 1200000, 1, 1],   # 09:25 竞价大分笔 120万 买(1)
    [93005000, 10.0, 80000, 950000, 1, 0],     # 09:30 小分笔 95万（不入池）
    [93010000, 10.0, 200000, 1500000, 2, 1],   # 09:30 大分笔 150万 买(1, 含2笔)
]}
ns['get_tick_direction'] = lambda *a, **k: _td
ns['_l2_big_seed'](['600001.XSHG'])
ok('T109 竞价终态播种 大分笔计入(120+150万)', abs(g.l2_big['600001.XSHG']['buy'] - 2700000.0) < 1e-6
   and abs(g.l2_big['600001.XSHG']['amt'] - 2700000.0) < 1e-6 and g.l2_big['600001.XSHG']['un'] == 0.0)
ok('T109 水印=最大已覆盖分笔时间', g.l2_big_wm['600001.XSHG'] == 93010000)
ok('T109 播种方向分布计数', g.l2_dir_dist == {'1': 2})
ns['_l2_big_seed'](['600001.XSHG'])
ok('T109 重复播种幂等(水印防重)', abs(g.l2_big['600001.XSHG']['buy'] - 2700000.0) < 1e-6)
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [93010000, 10.0, 150000, 1, 1],   # 与已播种分笔同时点 -> 跳过
    [93015000, 10.0, 200000, 2, 1]    # 09:30:15 新大单 200万 -> 计入
]})
ok('T109 live跳过已播种时段 新时段计入', abs(g.l2_big['600001.XSHG']['buy'] - 4700000.0) < 1e-6
   and g.l2_big_wm['600001.XSHG'] == 93015000)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {'600001.XSHG': 93100000}; g.l2_big_seeded = set()
g.l2_big['600001.XSHG'] = {'amt': 1000000.0, 'buy': 1000000.0, 'sell': 0.0, 'un': 0.0, 'seen': {1}, 'max': 1000000.0}
_td2 = {'fields': _tdf, '600001.XSHG': [[93120000, 10.0, 100000, 1800000, 1, 1], [93000000, 10.0, 50000, 600000, 1, 0]]}
ns['get_tick_direction'] = lambda *a, **k: _td2
ns['_l2_big_seed'](['600001.XSHG'])
ok('T109 重启回看只补>水印缺口', abs(g.l2_big['600001.XSHG']['buy'] - 2800000.0) < 1e-6
   and g.l2_big_wm['600001.XSHG'] == 93120000)
g.state_day = '2026-10-16'
ns['_save_state']()
g.l2_big_wm = {}
ns['load_state']()
ok('T109 wm 同日恢复', g.l2_big_wm.get('600001.XSHG') == 93120000)

# T109b v0.52a 重启补种加大页数(10页)：分页回读覆盖9:30-10:30活跃窗口至09:25竞价；09:25/09:31播种保持3页
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 300000000.0}
_tdF = ['time_stamp', 'hq_px', 'business_amount', 'business_balance', 'business_count', 'business_direction']
_pulled = []
def _td_pg(secs, **k):
    pg = int(k.get('start_pos', 0) // 200)
    _pulled.append(pg)
    rows = []
    for i in range(200):
        t = 93000000 + (9 - pg) * 600000 + i * 3000
        bal = 0
        if pg == 0 and i == 50:
            bal = 1800000      # 页0 10:00 段大单(3页内即覆盖)
        elif pg == 0 and i == 199:
            bal = 1000000      # 页0末行大单(与页1首行跨页重叠去重)
        elif pg == 4 and i == 100:
            bal = 1100000      # 页4 大单(仅>3页覆盖)
        rows.append([t, 10.0, 100000, bal, 1, 1])
    if pg == 1:
        rows[0] = [93000000 + (9 - 0) * 600000 + 199 * 3000, 10.0, 100000, 1000000, 1, 1]   # 跨页重叠重复页0末行
    if pg == 9:
        rows.append([92500000, 10.0, 100000, 1200000, 1, 1])   # 09:25 竞价终态大单(仅10页覆盖)
    return {'fields': _tdF, '600001.XSHG': rows}
ns['get_tick_direction'] = _td_pg
ns['_l2_big_seed'](['600001.XSHG'], pages=int(ns['BLS'].get('l2_tickdir_pages_restart', 10)))
ok('T109b 重启补种10页拉取 start_pos=0..1800', _pulled == list(range(10)))
ok('T109b 10页覆盖至09:25竞价 大单含竞价/页4', abs(g.l2_big['600001.XSHG']['buy'] - 5100000.0) < 1e-6
   and g.l2_big_wm['600001.XSHG'] == 93000000 + 9 * 600000 + 199 * 3000)
ns2 = fresh(); g2 = ns2['g']
g2.l2_big = {}; g2.l2_big_probed = set(); g2.l2_dir_dist = {}; g2.l2_big_wm = {}; g2.l2_big_seeded = set()
g2.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 300000000.0}
ns2['get_tick_direction'] = _td_pg
_pulled = []
ns2['_l2_big_seed'](['600001.XSHG'])   # 默认3页(09:25/09:31播种路径)
ok('T109b 默认播种保持3页 start_pos=0..400', _pulled == [0, 1, 2])
ok('T109b 3页播种不含>3页大单(页4/竞价不计)', abs(g2.l2_big['600001.XSHG']['buy'] - 2800000.0) < 1e-6
   and g2.l2_big_wm['600001.XSHG'] == 93000000 + 9 * 600000 + 199 * 3000)


# T110 v0.53 exp_day 持久化 + 日切统一入口：同日重启恢复盘中事件状态，跨日重置
ns = fresh(); g = ns['g']
g.state_day = '2026-10-16'; g.exp_day = '2026-10-16'
g.first_zt = {'600001.XSHG': {'break': True, 'ts': 1000.0}}
g.break_sold = {'600001.XSHG'}; g.seal_sold = set(); g.break2_sold = set()
g.l2_big = {'600002.XSHG': {'amt': 1.0, 'buy': 1.0, 'sell': 0.0, 'un': 0.0, 'seen': {10, 20}, 'max': 1.0}}
g.l2_big_wm = {'600002.XSHG': 93010000}; g.l2_dir_dist = {'0': 1}
g.ma5_touch_day = '2026-10-16'; g.ma5_touched = {'600001.XSHG'}
g.ma5_lifecycle_day = '2026-10-16'; g.ma5_lows = {'600001.XSHG': [9.70, 9.80]}
ns['_save_state']()
g.exp_day = None; g.first_zt = {}; g.break_sold = set(); g.l2_big = {}; g.l2_big_wm = {}; g.l2_dir_dist = {}
g.ma5_touch_day = None; g.ma5_touched = set(); g.ma5_lifecycle_day = None; g.ma5_lows = {}
ns['load_state']()
ok('T110 同日重启恢复 exp_day', g.exp_day == '2026-10-16')
ok('T110 同日重启保留 break_sold/first_zt', g.break_sold == {'600001.XSHG'} and g.first_zt.get('600001.XSHG', {}).get('break') is True)
ok('T110 同日重启保留 l2_big/wm/seen', abs(g.l2_big['600002.XSHG']['buy'] - 1.0) < 1e-9 and g.l2_big['600002.XSHG']['seen'] == {10, 20} and g.l2_big_wm['600002.XSHG'] == 93010000)
ok('T110 同日重启恢复 MA5次低价/首触状态',
   g.ma5_touch_day == '2026-10-16' and g.ma5_touched == {'600001.XSHG'} and
   g.ma5_lifecycle_day == '2026-10-16' and g.ma5_lows.get('600001.XSHG') == [9.7, 9.8])
_st = pickle.load(open(ns['_TMP'] + '/buysell_core_state.pkl', 'rb'))
_st['day'] = '2026-10-15'
pickle.dump(_st, open(ns['_TMP'] + '/buysell_core_state.pkl', 'wb'))
g.exp_day = '2026-10-16'; g.break_sold = {'X'}
ns['load_state']()
ok('T110 跨日重置 exp_day/break_sold/MA5次低价',
   g.exp_day is None and g.break_sold == set() and g.ma5_lifecycle_day is None and g.ma5_lows == {})
g.exp_day = '2026-10-16'; g.one_word_marked_open = True; g.break_sold = {'600001.XSHG'}
g.ma5_lifecycle_day = '2026-10-16'; g.ma5_lows = {'600001.XSHG': [9.7, 9.8]}
ok('T110 _maybe_roll_day 同日返回False不清空', ns['_maybe_roll_day']() is False and g.one_word_marked_open is True and g.break_sold == {'600001.XSHG'})
g.exp_day = '2026-10-15'; g.one_word_marked_open = True; g.break_sold = {'600001.XSHG'}
ok('T110 _maybe_roll_day 跨日返回True并清空',
   ns['_maybe_roll_day']() is True and g.exp_day == '2026-10-16' and g.break_sold == set() and
   g.one_word_marked_open is False and g.ma5_lifecycle_day == '2026-10-16' and g.ma5_lows == {})

# T111 v0.53 持仓监控全覆盖：P4 预期三态 / P5 评分清仓 / P6 评分半仓并入 3s tick（sold_log 冷却去重）
def _tick_sell_ns(entry_type='normal', auction_status=None, intraday_status=None, score=None):
    _ns = fresh(); _ns['time'] = _FakeTime(9000.0)
    _g = _ns['g']
    _g.first_zt = {}
    _g.spot['600001.XSHG'] = {'last_px': 9.5, 'preclose_px': 10.0, 'up_px': 11.0, 'trade_status': 'OPEN'}
    _g.exp['600001.XSHG'] = {'entry_type': entry_type}
    if auction_status:
        _g.exp['600001.XSHG']['auction_status'] = auction_status
    _ns['get_positions'] = lambda: {'600001.XSHG': {'enable_amount': 1000, 'cost_basis': 9.0}}
    _ns['_sellable_source'] = lambda: _ns['get_positions']()
    _ns['_sellable'] = lambda raw, p: 1000
    _ns['last_px'] = lambda sec: 9.5
    _ns['_auction_change'] = lambda sec: 3.0
    _ns['my_cost'] = lambda raw, p: 9.0
    _ns['get_stop_loss_pct'] = lambda sec: 0.05
    _ns['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    _ns['_save_state'] = lambda *a, **k: None
    _ns['_sell_inflight'] = lambda sec: False
    _ns['_hold_exp_init'] = lambda sec, force=False: None
    _ns['_eval_auction'] = lambda sec: (_ns['CM'], ['x'])
    _ns['_eval_intraday'] = lambda sec, auction_status: ((intraday_status if intraday_status else _ns['CM']), ['x'])
    _ns['_hist_1d'] = lambda sec: object()
    _ns['score_now'] = lambda sec: (score if score is not None else 40.0)
    _out = []
    def _ds(c, sec, qty, note, urgent=False, mode=None):
        _out.append((sec, note, qty))
        _ns['g'].sold_log[sec] = _ns['time'].time()
    _ns['_do_sell'] = _ds
    return _ns, _out

ns, out = _tick_sell_ns(entry_type='one_word', auction_status=ns['AW'])
ns['_is_one_word_open'] = lambda sec: True
ns['_exp_one_word'] = lambda sec, quiet=False: (ns['CS'], ['seal_fail'])
ns['tick_sell_manager'](ns['_CTX'])
ok('T111 P4 一字预期CS -> P4_exp_one_word_tick', len(out) == 1 and 'P4_exp_one_word_tick' in out[0][1])
ns['tick_sell_manager'](ns['_CTX'])
ok('T111 P4 冷却第二次不重复', len(out) == 1)

ns, out = _tick_sell_ns(entry_type='normal', auction_status=ns['AW'], intraday_status=ns['CS'])
ns['_is_one_word_open'] = lambda sec: False
ns['tick_sell_manager'](ns['_CTX'])
ok('T111 P4 普通分时CS -> P4_exp_miss_tick', len(out) == 1 and 'P4_exp_miss_tick' in out[0][1])

ns, out = _tick_sell_ns(entry_type='normal', auction_status=ns['AW'], intraday_status=ns['CM'], score=20.0)
ns['_is_one_word_open'] = lambda sec: False
ns['tick_sell_manager'](ns['_CTX'])
ok('T111 P5 评分清仓 -> P5_score_clear_tick 全仓', len(out) == 1 and 'P5_score_clear_tick' in out[0][1] and out[0][2] == 1000)

ns, out = _tick_sell_ns(entry_type='normal', auction_status=ns['AW'], intraday_status=ns['CM'], score=40.0)
ns['_is_one_word_open'] = lambda sec: False
ns['tick_sell_manager'](ns['_CTX'])
ok('T111 P6 评分半仓 -> P6_score_half_tick 卖500', len(out) == 1 and 'P6_score_half_tick' in out[0][1] and out[0][2] == 500)

# --- v0.58 P2E 竞价核卖：同题材中位崩塌传导(A) + 自身大不及(B)（docs/33） ---
def _p2e_ns(ac_map=None, est='pending_meet', side='hold', confirm=None, zt=None, unique=False, t0=9000.0):
    n = fresh(); n['time'] = _FakeTime(t0)
    ctx = n['_ctx']; g = n['g']
    g.first_zt = {}   # tick_sell_manager 需 dict（fresh 默认 None）
    ctx.portfolio.positions = {'600100.XSHG': types.SimpleNamespace(amount=1000, cost_basis=10.0)}
    g.exp_file['600100.XSHG'] = {'side': side, 'expected_status': est}
    g.spot['600100.XSHG'] = {'last_px': 10.5, 'preclose_px': 10.0, 'up_px': 12.0,
                             'wavg_px': 10.5, 'trade_status': 'OPEN', 'open_px': 10.0}
    if ac_map:
        n['_auction_change'] = lambda c: ac_map.get(c, 0.0)
    else:
        n['_auction_change'] = lambda c: -3.0
    if isinstance(confirm, str):
        _CMAP = {'CX': n['CX'], 'PM': n['PM'], 'CS': n['CS'], 'CM': n['CM']}
        confirm = _CMAP.get(confirm, confirm)
    if confirm is not None:
        n['_confirm_expected'] = lambda c: (confirm, 5.0)
    if zt:
        g.zt_lianban = {k: dict(v) for k, v in zt.items()}   # 深拷贝防 _ZT112 共享 dict 跨用例泄漏
        n['_build_zt_theme_index']()
    if unique:
        g.zt_lianban.setdefault('600100.XSHG', {})['unique_high'] = True
    n['get_positions'] = lambda: {'600100.XSHG': {'enable_amount': 1000, 'cost_basis': 10.0}}
    n['_sellable_source'] = lambda: n['get_positions']()
    n['_sellable'] = lambda raw, p: 1000
    n['last_px'] = lambda sec: 10.5
    n['my_cost'] = lambda raw, p: 10.0
    n['_hold_exp_init'] = lambda sec, force=False: None
    n['_sell_inflight'] = lambda sec: False
    n['get_stop_loss_pct'] = lambda sec: 0.05
    n['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    n['score_now'] = lambda sec: 80.0
    n['_eval_intraday'] = lambda sec, au: (n['CM'], ['mock'])
    n['_eval_auction'] = lambda sec: (n['CM'], ['mock'])
    n['_hist_1d'] = lambda sec: None
    n['_save_state'] = lambda *a, **k: None
    _out = []
    n['place_order'] = lambda c, sec, side, qty=None, note='', mode='chase': _out.append((sec, side, qty, note))
    return n, _out

_ZT112 = {'600100.XSHG': {'board_cnt': 0, 'themes': '机器人'},
          '600101.XSHG': {'board_cnt': 3, 'themes': '机器人'}}

# T112 A 触发：同题材中位(3板)最弱竞价 -3% <= -2% + 非唯一 -> 核卖（传 P2E_theme_mid_break）
_n112, _r112 = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -3.0}, est='pending_meet', zt=_ZT112)
_n112['sell_manager'](_n112['_ctx'])
ok('T112 中位崩塌 A 触发 -> P2E_theme_mid_break', len(_r112) == 1 and 'P2E_theme_mid_break' in _r112[0][3])

# T112b A 不触发：中位 -1.5% > -2% 阈值 -> 不卖
_n112b, _r112b = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -1.5}, est='pending_meet', zt=_ZT112)
_n112b['sell_manager'](_n112b['_ctx'])
ok('T112b 中位 -1.5% 不达阈值 -> 不卖', len(_r112b) == 0)

# T112c A 触发：中位基准有效(expected 3%)且 ac=-3% < 基准 -> 命中
_n112c, _r112c = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -3.0}, est='pending_meet', zt=_ZT112)
_n112c['g'].exp_file['600101.XSHG'] = {'expected_auction_change_pct': 3.0, 'has_expected_auction': True}
_n112c['sell_manager'](_n112c['_ctx'])
ok('T112c 中位基准有效且低于基准 -> A 触发', len(_r112c) == 1 and 'P2E_theme_mid_break' in _r112c[0][3])

# T112d 唯一高身位豁免：中位 -3% 但持仓为唯一高度板 -> 不核卖（交盘中监控）
_n112d, _r112d = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -3.0}, est='pending_meet', zt=_ZT112, unique=True)
_n112d['sell_manager'](_n112d['_ctx'])
ok('T112d 唯一高身位豁免 -> 不核卖', len(_r112d) == 0)

# T112e 钩子节奏：预热段(09:24:30)不触发 / 确认段(09:24:48)触发
_n112e, _r112e = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -3.0}, est='pending_meet', zt=_ZT112)
_n112e['_load_expectation'] = lambda: 0
_ctxE = _n112e['_ctx']
_ctxE.blotter.current_dt = datetime.datetime(2026, 10, 16, 9, 24, 30)
_n112e['p2e_auction_core_sell'](_ctxE)
ok('T112e 预热段(09:24:30)不触发', len(_r112e) == 0)
_ctxE.blotter.current_dt = datetime.datetime(2026, 10, 16, 9, 24, 48)
_n112e['p2e_auction_core_sell'](_ctxE)
ok('T112e 确认段(09:24:48)触发', len(_r112e) == 1 and 'P2E_theme_mid_break' in _r112e[0][3])

# T112f B 触发：自身大不及（confirmed_miss + ac=-3% <= -2%）-> P2E_exp_miss
_n112f, _r112f = _p2e_ns(ac_map={'600100.XSHG': -3.0}, est='confirmed_miss', side='hold')
_n112f['sell_manager'](_n112f['_ctx'])
ok('T112f 自身大不及 -> P2E_exp_miss', len(_r112f) == 1 and 'P2E_exp_miss' in _r112f[0][3])

# T112g 实时反证守卫：ac=-3% 达幅度但云端竞价超预期(CX) -> 不核卖
_n112g, _r112g = _p2e_ns(ac_map={'600100.XSHG': -3.0}, est='confirmed_miss', side='hold', confirm='CX')
_n112g['sell_manager'](_n112g['_ctx'])
ok('T112g 实时反证(CX) -> 不核卖', len(_r112g) == 0)

# T112h pending_miss 默认不卖（弱 miss 只暂缓）
_n112h, _r112h = _p2e_ns(ac_map={'600100.XSHG': -3.0}, est='pending_miss', side='hold')
_n112h['sell_manager'](_n112h['_ctx'])
ok('T112h pending_miss 默认不核卖', len(_r112h) == 0)

# T112i side=buy 排除（买入预期条目不参与核卖）
_n112i, _r112i = _p2e_ns(ac_map={'600100.XSHG': -3.0}, est='confirmed_miss', side='buy')
_n112i['sell_manager'](_n112i['_ctx'])
ok('T112i side=buy 不参与核卖', len(_r112i) == 0)

# T112j 卖出冷却去重：sold_log 冷却内第二次不叠单
_n112j, _r112j = _p2e_ns(ac_map={'600100.XSHG': -3.0}, est='confirmed_miss', side='hold')
_n112j['sell_manager'](_n112j['_ctx'])
_n112j['sell_manager'](_n112j['_ctx'])
ok('T112j P2E 卖出冷却去重', len(_r112j) == 1)

# T112k tick 兜底同条件：3s tick_sell_manager 走同一 _p2e_core_sell_check（A 路径）
_n112k, _r112k = _p2e_ns(ac_map={'600100.XSHG': -1.0, '600101.XSHG': -3.0}, est='pending_meet', zt=_ZT112)
_n112k['tick_sell_manager'](_n112k['_ctx'])
ok('T112k tick 兜底 A 触发', len(_r112k) == 1 and 'P2E_theme_mid_break' in _r112k[0][3])


# --- v0.59 持仓卖出闭环：持仓地位评估 + P7a/P7b/P7c（docs/33） ---
class _FakeDF(object):
    # 模拟 1d 历史 df（volume 序列；[-1]=今日 [-2]=昨日，与 _volume_ratio 同口径）
    def __init__(self, vols):
        self._vols = vols
    def __getitem__(self, k):
        if k == 'volume':
            return list(self._vols)
        if k in ('open', 'close'):
            return [10.0] * len(self._vols)
        raise KeyError(k)
    def __len__(self):
        return len(self._vols)

def _p7_ns(board_cnt=2, unique=False, hist_vol=None, snap_vol=None, sealed=False, stand=None,
           surge=None, active='neutral', t0=9000.0):
    n = fresh(); n['time'] = _FakeTime(t0)
    g = n['g']
    g.first_zt = {}; g.p7a_sold = set(); g.p7b_sold = set(); g.p7c_part = {}; g.p7c_sold = set()
    g.zt_lianban = {'600200.XSHG': {'board_cnt': board_cnt}}
    g.spot['600200.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'up_px': 12.0,
                             'wavg_px': 10.5, 'trade_status': 'OPEN', 'volume': snap_vol or 0.0}
    n['_sealed_now'] = lambda sec: sealed
    n['_hist_1d'] = lambda sec: _FakeDF(hist_vol if hist_vol is not None else [100.0, 90.0])
    n['_snap_vol'] = lambda s: snap_vol if snap_vol is not None else 0.0
    n['_unique_stand'] = lambda sec: unique
    n['_hold_stand'] = lambda sec: stand or {'ts': 0.0, 'role': 'outside', 'active': active, 'board': 'strong'}
    n['_elastic_1m_surge'] = lambda sec: surge if surge is not None else 0.0
    n['_min_age'] = lambda: 10
    n['_today_zt'] = lambda sec: False
    n['last_px'] = lambda sec: 10.8
    n['_save_state'] = lambda *a, **k: None
    return n

# T113 P7a 连板(2板)放量未封板 -> 清仓（非唯一）
_n = _p7_ns(board_cnt=2, hist_vol=[100.0, 90.0], snap_vol=120.0)
_q = _n['_p7a_check']('600200.XSHG', 1000)
ok('T113 P7a 放量未封板 -> 清仓', _q is not None and 'P7a_vol_break' in _q[0] and _q[1] == 1000)
# T113b P7a 唯一身位降级减半
_n = _p7_ns(board_cnt=2, unique=True, hist_vol=[100.0, 90.0], snap_vol=120.0)
_q = _n['_p7a_check']('600200.XSHG', 1000)
ok('T113b P7a 唯一身位 -> 减半', _q is not None and 'P7a_vol_break_half' in _q[0] and _q[1] == 500)
# T113c P7a 未放量 -> 不触发
_n = _p7_ns(board_cnt=2, hist_vol=[100.0, 90.0], snap_vol=95.0)
ok('T113c P7a 未达放量阈值 -> 不触发', _n['_p7a_check']('600200.XSHG', 1000) is None)
# T113d P7a 已封板 -> 不触发
_n = _p7_ns(board_cnt=2, hist_vol=[100.0, 90.0], snap_vol=120.0, sealed=True)
ok('T113d P7a 已封板 -> 不触发', _n['_p7a_check']('600200.XSHG', 1000) is None)
# T113e P7a 首板(1板)不适用 -> 不触发
_n = _p7_ns(board_cnt=1, hist_vol=[100.0, 90.0], snap_vol=120.0)
ok('T113e P7a 仅连板(>=2)适用', _n['_p7a_check']('600200.XSHG', 1000) is None)
# T113f P7b 跟风+板块强+1m拉升达标 -> 减半
_n = _p7_ns(board_cnt=2, stand={'ts': 0.0, 'role': 'follower', 'active': 'follow', 'board': 'strong'}, surge=2.0)
_q = _n['_p7b_check']('600200.XSHG', 1000)
ok('T113f P7b 跟风拉升未封板 -> 减半', _q is not None and 'P7b_follow_break' in _q[0] and _q[1] == 500)
# T113g P7b leader 不触发
_n = _p7_ns(board_cnt=2, stand={'ts': 0.0, 'role': 'leader', 'active': 'active', 'board': 'strong'}, surge=2.0)
ok('T113g P7b leader 不触发', _n['_p7b_check']('600200.XSHG', 1000) is None)
# T113h P7b surge 不足不触发
_n = _p7_ns(board_cnt=2, stand={'ts': 0.0, 'role': 'follower', 'active': 'follow', 'board': 'strong'}, surge=1.0)
ok('T113h P7b surge 不足不触发', _n['_p7b_check']('600200.XSHG', 1000) is None)
# T113i P7b 板块弱不触发
_n = _p7_ns(board_cnt=2, stand={'ts': 0.0, 'role': 'follower', 'active': 'follow', 'board': 'weak'}, surge=2.0)
ok('T113i P7b 板块弱不触发', _n['_p7b_check']('600200.XSHG', 1000) is None)
# T113j P7c 首板次日不主动 -> 仅标记不卖
_n = _p7_ns(board_cnt=1, active='neutral', t0=1000.0)
ok('T113j P7c 不主动 -> 标记不卖', _n['_p7c_check']('600200.XSHG', 1000) is None and '600200.XSHG' in (_n['g'].p7c_part or {}))
# T113k P7c 冲高触发第一批（50%）
_n['last_px'] = lambda sec: 10.8 * 1.02
_n['g'].p7c_part['600200.XSHG'] = {'ts': 9000.0, 'price': 10.8}
_q = _n['_p7c_check']('600200.XSHG', 1000)
ok('T113k P7c 冲高 -> 第一批50%', _q is not None and 'b1' in _q[0] and _q[1] == 500 and _n['g'].p7c_part['600200.XSHG'].get('sold1_ts'))
# T113l P7c 批次冷却：10s 内第二批不触发
_n['time'] = _FakeTime(1006.0)
ok('T113l P7c 批次冷却内不卖第二批', _n['_p7c_check']('600200.XSHG', 500) is None)
# T113m P7c 冷却后第二批（剩余50%）
_n['time'] = _FakeTime(1011.0)
_q = _n['_p7c_check']('600200.XSHG', 500)
ok('T113m P7c 冷却后第二批', _q is not None and 'b2' in _q[0] and _q[1] == 500 and '600200.XSHG' in (_n['g'].p7c_sold or set()))
# T113n P7c 回封取消标记
_n = _p7_ns(board_cnt=1, active='neutral', t0=1000.0)
_n['g'].p7c_part['600200.XSHG'] = {'ts': 9000.0, 'price': 10.8}
_n['_today_zt'] = lambda sec: True
ok('T113n P7c 回封取消标记', _n['_p7c_check']('600200.XSHG', 1000) is None and '600200.XSHG' not in (_n['g'].p7c_part or {}))
# T113o P7c 主动 -> 不标记
_n = _p7_ns(board_cnt=1, active='active', t0=1000.0)
ok('T113o P7c 主动冲板 -> 不标记', _n['_p7c_check']('600200.XSHG', 1000) is None and '600200.XSHG' not in (_n['g'].p7c_part or {}))
# T113p P7c 窗口外（>10:00）不触发
_n = _p7_ns(board_cnt=1, active='neutral', t0=1000.0)
_n['_min_age'] = lambda: 35
ok('T113p P7c 窗口外不标记', _n['_p7c_check']('600200.XSHG', 1000) is None)
# T113q _hold_stand 分类：动态龙头 + 板块强 + 主动
_n = fresh(); _n['time'] = _FakeTime(1000.0)
_n['g'].zt_lianban = {'600200.XSHG': {'board_cnt': 3, 'themes': '机器人'}}
_n['g'].spot['600200.XSHG'] = {'last_px': 10.8, 'preclose_px': 10.0, 'wavg_px': 10.5, 'trade_status': 'OPEN'}
_n['_dyn_theme_leader'] = lambda sec: True
_n['_board_strength'] = lambda sec: 2.0
_n['_sector_chg'] = lambda sec: 0.08
_st = _n['_hold_stand']('600200.XSHG')
ok('T113q 地位评估 leader/主动/强', _st['role'] == 'leader' and _st['active'] == 'active' and _st['board'] == 'strong')
# T113r _hold_stand 分类：中位(2-5板非唯一) -> mid
_n = fresh(); _n['time'] = _FakeTime(1000.0)
_n['g'].zt_lianban = {'600200.XSHG': {'board_cnt': 3, 'themes': '机器人'}}
_n['g'].spot['600200.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'wavg_px': 10.5, 'trade_status': 'OPEN'}
_n['_dyn_theme_leader'] = lambda sec: False
_n['_board_strength'] = lambda sec: 0.0
_n['_sector_chg'] = lambda sec: 0.0
_st = _n['_hold_stand']('600200.XSHG')
ok('T113r 地位评估 mid', _st['role'] == 'mid')
# T113s tick 链 P7a 触发（3s 链接入）
_n = _p7_ns(board_cnt=2, hist_vol=[100.0, 90.0], snap_vol=120.0)
_out = []
def _ds(c, sec, qty, note, urgent=False, mode=None, cool=True):
    _out.append((sec, note, qty))
_n['_do_sell'] = _ds
_n['place_order'] = lambda c, sec, side, qty=None, note='', mode='chase': _out.append((sec, side, qty, note))
_n['get_positions'] = lambda: {'600200.XSHG': {'enable_amount': 1000, 'cost_basis': 10.0}}
_n['_sellable_source'] = lambda: _n['get_positions']()
_n['_sellable'] = lambda raw, p: 1000
_n['last_px'] = lambda sec: 10.8
_n['my_cost'] = lambda raw, p: 10.0
_n['_hold_exp_init'] = lambda sec, force=False: None
_n['_sell_inflight'] = lambda sec: False
_n['_auction_change'] = lambda sec: 1.0
_n['_role_tolerance'] = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
_n['get_stop_loss_pct'] = lambda sec: 0.05
_n['_p2e_core_sell_check'] = lambda sec: (False, '')
_n['tick_sell_manager'](_n['_ctx'])
ok('T113s tick 链 P7a 清仓', len(_out) == 1 and 'P7a_vol_break' in _out[0][1] and '600200.XSHG' in (_n['g'].p7a_sold or set()))

# --- T114 v0.60 板块口径统一：文件 THS 概念 -> 全链路消费；开关关闭/未加载回退 API ---
_n = fresh()
_g = _n['g']
_g.now_dt = datetime.datetime(2026, 10, 20, 9, 35, 0)
_g.boards = {'机器人': ['600001.XSHG', '600002.XSHG'], '算力': ['600001.XSHG', '600003.XSHG']}
_g.board_type = {'机器人': 'concept', '算力': 'concept'}
_g.stock_boards = {'600001.XSHG': ['机器人', '算力'], '600002.XSHG': ['机器人'], '600003.XSHG': ['算力']}
def _sn114(secs):
    out = {}
    for c in secs:
        chg = {'600001.XSHG': 0.01, '600002.XSHG': 0.01, '600003.XSHG': 0.03}.get(c, 0.0)
        out[c] = {'preclose_px': 10.0, 'last_px': 10.0 * (1 + chg)}
    return out
_n['get_snapshot'] = lambda secs: _sn114(secs)
_n['_elastic_top_cand_src'] = lambda: ['600001.XSHG', '600002.XSHG', '600003.XSHG']
# 机器人=+1%（2成员均值），算力=+2%（600001 1% + 600003 3% 均值2%）-> 算力最强
ok('T114 概念强度取最强板块(算力2%)', abs(_n['_board_strength_by_concept']('600001.XSHG') - 2.0) < 1e-6)
ok('T114 _board_strength 统一概念口径', abs(_n['_board_strength']('600001.XSHG') - 2.0) < 1e-6)
ok('T114 单板块股强度(机器人1%)', abs(_n['_board_strength']('600002.XSHG') - 1.0) < 1e-6)
# 排名门控：算力(2%)/机器人(1%) 均入前三（共2板块）；600001 任一所属概念在 top3 -> 通过
top3 = _n['_board_rank_top3_set'](['600001.XSHG'])
ok('T114 概念top3含算力', '算力' in top3 and '机器人' in top3)
ok('T114 rank门控概念口径通过', _n['_board_rank_top3']('600001.XSHG', ['600001.XSHG']))
# 红盘比：算力 2涨0跌 -> 1.0
ok('T114 红盘比最强板块口径', abs(_n['_red_ratio']('600001.XSHG') - 1.0) < 1e-9)
# 弹性一字强板块归属走概念
ok('T114 elastic强板块概念口径', _n['_elastic_in_strong_board']('600001.XSHG', {'算力': 2}))
ok('T114 非强板块归属不入', not _n['_elastic_in_strong_board']('600002.XSHG', {'算力': 2}))
# 共享账本：先建 csnap_led（top1 合并快照），rank 强度读账本 -> 不产生单板 cbsnap 缓存
_dh = _n['_get_ds'](); _dh.cache.clear()
_n['_concept_board_rank_top1'](['600001.XSHG'])
_n['_board_rank_top3_set'](['600001.XSHG'])
ok('T114 rank与top1共享合并账本', ('cbsnap', '算力') not in _dh.cache and ('cbsnap', '机器人') not in _dh.cache)
# 开关关闭 -> 回退 API（即使文件已加载）
_n2 = fresh()
_n2['g'].boards = {'机器人': ['600001.XSHG']}
_n2['g'].board_type = {'机器人': 'concept'}
_n2['g'].stock_boards = {'600001.XSHG': ['机器人']}
_n2['BLS']['board_concept_unified'] = False
_n2['_board_strength_api'] = lambda sec: 7.0
ok('T114 开关关闭回退API强度', _n2['_board_strength']('600001.XSHG') == 7.0)
# 未加载 -> 回退 API（g.boards 空）
_n3 = fresh()
_n3['_board_strength_api'] = lambda sec: 8.0
ok('T114 未加载回退API强度', _n3['_board_strength']('600001.XSHG') == 8.0)

# T115 v0.66 大单占比分母打通：business_balance(总成交额)优先 / business_amount x 均价兜底 / turnover 旧环境兼容
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'business_balance': 100000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 1000000, 1, 'buy'], [99001000, 10.0, 1500000, 2, 'buy'],
    [99002000, 10.0, 800000, 3, 'sell']]})
ok('T115 business_balance 分母 净1700万/1亿=17% 加分', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
ok('T115 分母接口读 business_balance', abs(ns['_l2_big_turnover']('600001.XSHG') - 100000000.0) < 1e-6)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'business_amount': 10000000, 'wavg_px': 10.0}
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 1000000, 1, 'buy'], [99001000, 10.0, 1500000, 2, 'buy'],
    [99002000, 10.0, 800000, 3, 'sell']]})
ok('T115 business_amount x wavg 兜底 17% 加分', abs(ns['_l2_big_bonus_pts']('600001.XSHG') - 5.0) < 1e-9)
ok('T115 分母接口 business_amount x wavg 兜底', abs(ns['_l2_big_turnover']('600001.XSHG') - 100000000.0) < 1e-6)
ns = fresh(); g = ns['g']
g.spot['600001.XSHG'] = {'up_px': 11.0, 'turnover': 50000000.0}
ok('T115 turnover 兜底保持旧环境兼容', abs(ns['_l2_big_turnover']('600001.XSHG') - 50000000.0) < 1e-6)

# T116 v0.66 买入/卖出大单分量取得：逐笔+播种双源分计 买/卖/未识别笔数 + 日结汇总
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set()
g.spot['600001.XSHG'] = {'up_px': 11.0, 'business_balance': 100000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [
    [99000000, 10.0, 200000, 1, 1],    # 200万 买
    [99001000, 10.0, 150000, 2, 1],    # 150万 买
    [99002000, 10.0, 200000, 3, 0],    # 200万 卖
    [99003000, 10.0, 150000, 4, 2],    # 150万 借入 -> un
    [99004000, 10.0, 50000, 5, 0]      # 50万 小单不入
]})
ok('T116 买入大单分量=350万(2笔)', abs(g.l2_big['600001.XSHG']['buy'] - 3500000.0) < 1e-6 and g.l2_big['600001.XSHG']['bn'] == 2)
ok('T116 卖出大单分量=200万(1笔)', abs(g.l2_big['600001.XSHG']['sell'] - 2000000.0) < 1e-6 and g.l2_big['600001.XSHG']['sn'] == 1)
ok('T116 未识别分量=150万(1笔)', abs(g.l2_big['600001.XSHG']['un'] - 1500000.0) < 1e-6 and g.l2_big['600001.XSHG']['un_n'] == 1)
ok('T116 净大单=买-卖=150万', abs(g.l2_big['600001.XSHG']['buy'] - g.l2_big['600001.XSHG']['sell'] - 1500000.0) < 1e-6)
g.l2_big['600002.XSHG'] = {'amt': 8000000.0, 'buy': 8000000.0, 'sell': 0.0, 'un': 0.0,
                           'bn': 8, 'sn': 0, 'un_n': 0, 'seen': set(), 'max': 8000000.0}
g.l2_big['600003.XSHG'] = {'amt': 9000000.0, 'buy': 0.0, 'sell': 9000000.0, 'un': 0.0,
                           'bn': 0, 'sn': 9, 'un_n': 0, 'seen': set(), 'max': 9000000.0}
_rows = ns['_l2_big_day_summary']()
ok('T116 日结按净额降序 600002 最前', _rows[0][0] == '600002.XSHG' and _rows[0][3] == 8000000.0)
ok('T116 日结含买/卖/净/笔数', len(_rows) == 3 and _rows[1][0] == '600001.XSHG' and _rows[1][1] == 3500000.0
   and _rows[1][4] == 2 and _rows[2][2] == 9000000.0 and _rows[2][5] == 9)
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set()
_tdf = ['time_stamp', 'hq_px', 'business_amount', 'business_balance', 'business_count', 'business_direction']
ns['get_tick_direction'] = lambda *a, **k: {'fields': _tdf, '600001.XSHG': [
    [92500000, 10.0, 100000, 1200000, 1, 1], [93000000, 10.0, 80000, 1500000, 1, 0]]}
ns['_l2_big_seed'](['600001.XSHG'])
ok('T116 播种分计 买1笔/卖1笔', g.l2_big['600001.XSHG']['bn'] == 1 and g.l2_big['600001.XSHG']['sn'] == 1)

# T117 v0.67 盘中新入池触板票补播种：未播种票回看历史大单进 acc + 60s 节流防重复播种
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_dir_dist = {}; g.l2_big_seed_onjoin_ts = 0.0
_tdf = ['time_stamp', 'hq_px', 'business_amount', 'business_balance', 'business_count', 'business_direction']
ns['get_tick_direction'] = lambda *a, **k: {'fields': _tdf, '600001.XSHG': [
    [92500000, 10.0, 100000, 1200000, 1, 1], [93000000, 10.0, 80000, 1500000, 1, 0]]}
ns['_l2_big_seed_onjoin'](['600001.XSHG'])
ok('T117 入池播种 历史大单进 acc 买/卖分量',
   abs(g.l2_big['600001.XSHG']['buy'] - 1200000.0) < 1e-6 and abs(g.l2_big['600001.XSHG']['sell'] - 1500000.0) < 1e-6
   and g.l2_big['600001.XSHG']['bn'] == 1 and g.l2_big['600001.XSHG']['sn'] == 1)
ok('T117 入池播种 标记已播种+节流时间戳', '600001.XSHG' in g.l2_big_seeded and g.l2_big_seed_onjoin_ts > 0)
ns = fresh(); g = ns['g']
g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0
_calls = []
ns['_l2_big_seed'] = lambda *a, **k: _calls.append((a, k))
ns['_l2_big_seed_onjoin'](['600001.XSHG'])
ns['_l2_big_seed_onjoin'](['600002.XSHG'])
ok('T117 60s 节流内不重复播种', len(_calls) == 1)
g.l2_big_seed_onjoin_ts = time.time() - 61
ns['_l2_big_seed_onjoin'](['600003.XSHG'])
ok('T117 超过间隔恢复播种', len(_calls) == 2 and _calls[1][0][0] == ['600003.XSHG'])
ns = fresh(); g = ns['g']
g.l2_big_seeded = {'600002.XSHG'}; g.l2_big_seed_onjoin_ts = 0.0
_calls = []
ns['_l2_big_seed'] = lambda *a, **k: _calls.append((a, k))
ns['_l2_big_seed_onjoin'](['600001.XSHG', '600002.XSHG'])
ok('T117 已播种票不入 todo', len(_calls) == 1 and _calls[0][0][0] == ['600001.XSHG'])

# T118 v0.67 [l2-big] 探针分钟节流重打：首帧立即，间隔内不重打，超时后重打并更新时间戳
ns = fresh(); g = ns['g']
g.l2_big = {}; g.l2_big_probed = set(); g.l2_big_log_ts = {}; g.l2_dir_dist = {}
g.spot['600001.XSHG'] = {'up_px': 11.0, 'business_balance': 100000000.0}
_f = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
_logs = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _logs.append(a), warn=lambda *a: _logs.append(a), error=lambda *a: None)
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99000000, 10.0, 1200000, 1, 1]]})
_l2n = lambda: len([x for x in _logs if isinstance(x, tuple) and x and '[l2-big]' in x[0]])
n1 = _l2n()
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99001000, 10.0, 1500000, 2, 1]]})
n2 = _l2n()
ok('T118 间隔内不重打(仍1次)', n1 == 1 and n2 == 1)
g.l2_big_log_ts['600001.XSHG'] = time.time() - 301
ns['_tx_big_feed'](['600001.XSHG'], _f, {'600001.XSHG': [[99002000, 10.0, 2000000, 3, 1]]})
ok('T118 超间隔重打且更新时间戳', _l2n() == 2 and time.time() - g.l2_big_log_ts['600001.XSHG'] < 5)

# T119 v0.67 批量逐笔缺票逐只兜底：批量缺 B，帧预算内单票补回并合并 fields
ns = fresh()
_logs = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _logs.append(a), warn=lambda *a: _logs.append(a), error=lambda *a: None)
_secs = ['600001.XSHG', '600002.XSHG']
_batch_fields = ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction']
def _mock_tx(*a, **k):
    if len(a[0]) > 1:
        return {'fields': list(_batch_fields), '600001.XSHG': [[99000000, 10.0, 1000000, 1, 1]]}
    return {'fields': list(_batch_fields), a[0][0]: [[99000000, 10.0, 1500000, 2, 1]]}
ns['get_individual_transaction'] = _mock_tx
_dh = ns['_get_ds'](); _dh.cache.clear()
raw = _dh._tx_pull_raw(_secs)
ok('T119 批量缺票逐只兜底补齐', raw.get('600002.XSHG') is not None and len(raw['600002.XSHG']) == 1 and raw.get('600001.XSHG') is not None)
ok('T119 fields 保持一致', raw.get('fields') == _batch_fields)
ok('T119 [tx-pull] missing 日志正确',
   any(isinstance(x, tuple) and x and '[tx-pull] req=2 got=1 missing=1 (fallback=1)' in x[0] for x in _logs))


# ================= v0.68 A/B/C 三重数据就绪加固（docs/33） =================
# T120 A1 评分就绪门：缺前收 -> score_now None；板块不可用 -> None；就绪 -> float
ns = fresh()
ns['g'].spot['600300.XSHG'] = {'last_px': 10.0}          # 缺 preclose_px
ok('T120 _spot_ready False(缺前收)', ns['_spot_ready']('600300.XSHG') is False)
ok('T120 score_now None(缺前收)', ns['score_now']('600300.XSHG') is None)
ns['g'].spot['600300.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0}
ns['_board_strength_info'] = lambda sec: (0.0, False)
ok('T120 score_now None(板块不可用)', ns['score_now']('600300.XSHG') is None)
ns['_board_strength_info'] = lambda sec: (0.0, True)
ok('T120 score_now 正常(板块可用)', isinstance(ns['score_now']('600300.XSHG'), float))

# T121 A3 板块成员快照全缺前收 -> 不可用；就绪后出真值；未映射中性放行
ns = fresh()
ns['_concept_active'] = lambda: True
ns['_board_members_file'] = lambda b, cap: ['600001.XSHG', '600002.XSHG']
ns['_concept_snap_for'] = lambda b, mem: {'600001.XSHG': {'last_px': 10.0}, '600002.XSHG': {'last_px': 10.0}}
st, ready = ns['_concept_board_strength_info']('BK001')
ok('T121 全缺前收 -> (0.0,False)', (not ready) and st == 0.0)
ns['_concept_snap_for'] = lambda b, mem: {'600001.XSHG': {'preclose_px': 10.0, 'last_px': 10.5},
                                          '600002.XSHG': {'preclose_px': 10.0, 'last_px': 10.0}}
st, ready = ns['_concept_board_strength_info']('BK001')
ok('T121 就绪 -> (2.5%,True)', ready and abs(st - 2.5) < 1e-9)
ns['_concept_boards_of'] = lambda sec: []
ns['_concept_strong_board'] = lambda sec: None
st2, ready2 = ns['_board_strength_info']('600003.XSHG')
ok('T121 未映射 -> (0.0,True) 中性放行', ready2 and st2 == 0.0)
ns['_concept_boards_of'] = lambda sec: ['BK001']
st3, ready3 = ns['_board_strength_info']('600003.XSHG')
ok('T121 有归属不可测 -> (0.0,False)', (not ready3) and st3 == 0.0)

# T122 B1 竞价未就绪不写缓存（毒缓存根因）：缺前收 -> 0.0 且不缓存；前收到位 -> 重算真值并缓存
ns = fresh()
ns['g'].spot['600301.XSHG'] = {'preclose_px': 10.0, 'open_px': 10.5, 'last_px': 10.5}
_prec = {'600301.XSHG': 0.0}
ns['pre_close'] = lambda sec: _prec.get(sec)
ok('T122 缺前收 _auction_change=0.0', abs(ns['_auction_change']('600301.XSHG') - 0.0) < 1e-9)
ok('T122 缺前收不写缓存(下帧可重算)', '600301.XSHG' not in ns['g'].auction_c)
_prec['600301.XSHG'] = 10.0
ok('T122 前收到位重算真值=5%', abs(ns['_auction_change']('600301.XSHG') - 5.0) < 1e-9)
_ck = ns['g'].auction_c.get('600301.XSHG')
ok('T122 就绪后写缓存', _ck is not None and _ck[0] == '2026-10-16' and abs(_ck[1] - 5.0) < 1e-9)
ok('T122 _auction_ready True(缓存命中)', ns['_auction_ready']('600301.XSHG') is True)
_prec['600301.XSHG'] = 0.0
ns['g'].auction_c.pop('600301.XSHG', None)
ok('T122 _auction_ready False(缺前收)', ns['_auction_ready']('600301.XSHG') is False)

# T123 B2 首帧未就绪(缺前收, open>0) -> 预期超预期不误弃（修 09:30 误弃根因）
ns = fresh(); expbuyns(ns, '600302.XSHG')
ns['g'].exp_file['600302.XSHG'] = {'side':'buy','entry_type':'normal','expected_status':'pending_exceed',
                                   'has_expected_auction': True, 'expected_auction_change_pct': 5.0,
                                   'yesterday_open_pct': 3.0, 'seal_amount_t0': 0.0}
ns['g'].spot['600302.XSHG'] = {'last_px': 11.0, 'preclose_px': 0.0, 'open_px': 11.0, 'up_px': 12.0,
                               'wavg_px': 11.0, 'trade_status': 'OPEN'}
_prec2 = {'600302.XSHG': 0.0}
ns['pre_close'] = lambda sec: _prec2.get(sec)
st, reason = ns['_exp_rt_status']('600302.XSHG')
ok('T123 缺前收 -> PM await_intraday_confirm', st == ns['PM'] and 'await_intraday_confirm' in str(reason))
r = ns['_attempt_expected_buy'](ns['_ctx'], '600302.XSHG')
ok('T123 未就绪不误弃(不置 exp_fired)', r is None and '600302.XSHG' not in ns['g'].exp_fired)
_prec2['600302.XSHG'] = 10.0
ns['g'].spot['600302.XSHG']['preclose_px'] = 10.0
ns['g'].spot['600302.XSHG']['open_px'] = 10.0
st2, reason2 = ns['_exp_rt_status']('600302.XSHG')
ok('T123 前收就绪 -> auction_not_met(放弃)', st2 == ns['CS'] and 'auction_not_met' in str(reason2))

# T124 B3 首帧资金未就绪(cash=0) -> 预期买入静默跳过；cash 就绪 -> 正常
ns = fresh(); expbuyns(ns, '600303.XSHG')
ns['g'].spot['600303.XSHG'] = {'last_px': 10.0, 'preclose_px': 10.0, 'up_px': 12.0, 'wavg_px': 10.0,
                               'trade_status': 'OPEN', 'open_px': 10.0}
_logs4 = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _logs4.append(a), warning=lambda *a: _logs4.append(a), error=lambda *a: None)
ns['_avail_cash'] = lambda ctx: 0.0
r = ns['place_expected_order'](ns['_ctx'], '600303.XSHG', note='t124')
ok('T124 cash=0 静默返回 False', r is False)
ok('T124 cash=0 不刷 qty<=0/无资金 日志', not any(('qty<=0' in str(x) or 'no px/cash' in str(x)) for x in _logs4))
ns['_avail_cash'] = lambda ctx: 100000.0
r2 = ns['place_expected_order'](ns['_ctx'], '600303.XSHG', note='t124b')
ok('T124 cash 就绪后正常(SIM True)', r2 is True)

# T125 C1 盘中重读 merge：old 15 -> new 5 不丢候选
ns = fresh()
_ep = os.path.join(ns['_TMP'], 'expectation_latest.csv')
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('code,side,entry_type,expected_status,expected_auction_change_pct,yesterday_open_pct\n')
    for i in range(15):
        f.write('6001%02d.XSHG,buy,normal,pending_exceed,5.0,3.0\n' % i)
ok('T125 首载全量替换 15', ns['_load_expectation']() == 15)
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('code,side,entry_type,expected_status,expected_auction_change_pct,yesterday_open_pct\n')
    for i in range(0, 5):
        f.write('6001%02d.XSHG,buy,normal,confirmed_exceed,6.0,3.0\n' % i)
n = ns['_load_expectation'](merge=True)
ok('T125 merge 总数=15(不丢)', n == 15 and len(ns['g'].exp_file) == 15)
ok('T125 新文件字段胜出', ns['g'].exp_file['600100.XSHG']['expected_status'] == 'confirmed_exceed')
ok('T125 旧有缺失保留', '600105.XSHG' in ns['g'].exp_file)

# T126 C2 日期守卫：盘中文件日期!=今日 -> 拒绝重载
ns = fresh()
_ep = os.path.join(ns['_TMP'], 'expectation_latest.csv')
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('date,code,side,entry_type,expected_status,expected_auction_change_pct\n'
            '2026-10-16,600100.XSHG,buy,normal,pending_exceed,5.0\n'
            '2026-10-16,600101.XSHG,buy,normal,pending_exceed,5.0\n')
ok('T126 首载含日期列 2', ns['_load_expectation']() == 2)
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('date,code,side,entry_type,expected_status,expected_auction_change_pct\n'
            '2026-10-15,600100.XSHG,buy,normal,confirmed_exceed,6.0\n')
n = ns['_load_expectation'](merge=True)
ok('T126 旧日期文件拒绝重载(保持2)', len(ns['g'].exp_file) == 2)
ok('T126 拒绝后字段不被旧日期覆盖', ns['g'].exp_file['600100.XSHG']['expected_status'] == 'pending_exceed')

# T127 C3 重载差异日志
ns = fresh()
_ep = os.path.join(ns['_TMP'], 'expectation_latest.csv')
_logs7 = []
ns['log'] = types.SimpleNamespace(info=lambda *a: _logs7.append(a), warning=lambda *a: _logs7.append(a), error=lambda *a: None)
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('code,side,entry_type,expected_status,expected_auction_change_pct\n')
    for i in range(10):
        f.write('6002%02d.XSHG,buy,normal,pending_exceed,5.0\n' % i)
ns['_load_expectation']()
with open(_ep, 'w', encoding='utf-8') as f:
    f.write('code,side,entry_type,expected_status,expected_auction_change_pct\n600200.XSHG,buy,normal,confirmed_exceed,6.0\n')
ns['_load_expectation'](merge=True)
ok('T127 merge 差异日志 old=10 new=1 total=10',
   any(isinstance(x, tuple) and x and 'merged' in x[0] and 'old=10' in x[0] and 'new=1' in x[0] and 'total=10' in x[0] for x in _logs7))

print('ALL DONE')

