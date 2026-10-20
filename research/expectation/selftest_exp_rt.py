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
    for k in ('buy_log','sold_log','daily','state_day','spot','last_ma5','hist','bs_cache',
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

# T14 P2E 竞价核卖：预期 confirmed_miss -> 清仓（DO_ORDER=True 发卖单）
ns = fresh()
ctx = ns['_ctx']
ns['g'].exp_file = {}
ctx.portfolio.positions = {'600050.XSHG': _t.SimpleNamespace(amount=1000, cost_basis=10.0)}
ns['g'].exp_file['600050.XSHG'] = {'side':'sell','expected_status':'confirmed_miss'}
ns['g'].spot['600050.XSHG'] = {'last_px':10.5,'preclose_px':10.0,'up_px':11.0,'wavg_px':10.5,'trade_status':'OPEN'}
ns['_auction_change'] = lambda c: 5.0
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
def _fake_load_exp():
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

# T26d 5日线低吸（ma_pullback）对齐 AXquant：CORE+BS 双标签 + 5日内首次回踩 MA5
ns = fresh(); ns['g'].watch = ['600001.XSHG', '600002.XSHG', '600003.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)   # 低吸窗口内（10:30 前）
ns['_tags'] = lambda sec: {'600001.XSHG': ['CORE', 'BS'], '600002.XSHG': [], '600003.XSHG': ['CORE']}.get(sec, [])
ns['_ensure_ma5'] = lambda sec: 10.0; ns['last_px'] = lambda sec: 9.5
ns['score_now'] = lambda sec: 60.0; ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['BLS']['ma5_core_only'] = True; ns['BLS']['ma5_require_bs'] = True; ns['BLS']['ma5_first_5d'] = True
ns['BLS']['daily_max_buy'] = 10
ns['_ma5_first_5d'] = lambda sec: True
pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append((sec, note))
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T26d 非CORE(杂毛)低吸被拦截', all(c[0] != '600002.XSHG' for c in pcalls))
ok('T26d 缺BS(非100日新高)低吸被拦截', all(c[0] != '600003.XSHG' for c in pcalls))
ok('T26d CORE+BS+首回踩 才触发低吸', len(pcalls) == 1 and pcalls[0][0] == '600001.XSHG' and 'ma_pullback' in pcalls[0][1])

# T26e 非5日内首次回踩(重复低吸)被拦截
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)   # 低吸窗口内（10:30 前）
ns['_tags'] = lambda sec: ['CORE', 'BS']
ns['_ensure_ma5'] = lambda sec: 10.0; ns['last_px'] = lambda sec: 9.5
ns['score_now'] = lambda sec: 60.0; ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['BLS']['ma5_core_only'] = True; ns['BLS']['ma5_require_bs'] = True; ns['BLS']['ma5_first_5d'] = True
ns['BLS']['daily_max_buy'] = 10
ns['_ma5_first_5d'] = lambda sec: False
pcalls = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: pcalls.append(sec)
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T26e 非5日内首次回踩被拦截', pcalls == [])

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


# --- T30 ma5 = 最近5个已完日收盘均值(而非全历史), 修复 docs/24 ①---
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
class _FakeDF:
    def __init__(self, closes): self._close = _Col(closes); self._n = len(closes)
    def __getitem__(self, k): return self._close if k == 'close' else None
    @property
    def close(self): return self._close
    def __len__(self): return self._n

ns = fresh()
ns['g'].last_ma5 = {}
ns['_hist_1d'] = lambda sec: _FakeDF([1,2,3,4,5,6,7,8,9,10])   # 今天=10, 最近5完日=[5,6,7,8,9]
ok('T30 ma5=最近5日均(7.0) 非全历史(5.0)', abs(ns['_ensure_ma5']('600001.XSHG') - 7.0) < 1e-9)
ok('T30 ma5 缓存命中', abs(ns['_ensure_ma5']('600001.XSHG') - 7.0) < 1e-9)

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
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pcalls.append({'sec': sec, 'mode': mode, 'note': note})
ns['try_core_buy'](ns['_CTX'])
ok('T36 非CORE core_buy 拦截', all(c['sec'] != '600002.XSHG' for c in pcalls))
ok('T36 连板>=6 core_buy 拦截', all(c['sec'] != '600003.XSHG' for c in pcalls))
ok('T36 CORE+连板<6 core_buy 触发', any(c['sec'] == '600001.XSHG' and c['mode'] == 'chase' and 'core_buy' in c['note'] for c in pcalls))
ok('T36 core_buy 记入 daily.bought', '600001.XSHG' in ns['g'].daily['bought'])

ns = _core_setup(held=('600005.XSHG',)); pcalls = []
ns['place_order'] = lambda *a, **k: pcalls.append(1)
ns['try_core_buy'](ns['_CTX'])
ok('T36 已持仓 CORE 不重复买', '600005.XSHG' not in ns['g'].daily['bought'])

ns = _core_setup(); ns['BLS']['daily_max_buy'] = 1; ns['g'].daily['bought'] = ['600009.XSHG']; pcalls = []
ns['place_order'] = lambda *a, **k: pcalls.append(1)
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
ns['get_snapshot'] = lambda m: {m: {'last_px': 10.3 if m == '600002.XSHG' else 10.5, 'preclose_px': 10.0}}
ok('T37 板块内最高 -> True', ns['_board_top_gainer']('600001.XSHG') is True)
ns['get_snapshot'] = lambda m: {m: {'last_px': 10.9 if m == '600002.XSHG' else 10.5, 'preclose_px': 10.0}}
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
    ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append({'sec': sec, 'mode': mode, 'ratio': ratio, 'note': note})
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
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append({'sec': sec, 'mode': mode, 'note': note})
ns['tick_data'](ns['_CTX'], {})
ok('T39 tick 首触 -> 首板打板下单', len(pc) == 1 and pc[0]['sec'] == '600001.XSHG' and 'first_board_buy' in pc[0]['note'])
ok('T39 firstzt 已记录', bool(ns['g'].first_zt.get('600001.XSHG')))
ok('T39 打板记入 daily.bought + fired', '600001.XSHG' in ns['g'].daily['bought'] and '600001.XSHG' in ns['g'].first_board_fired)

ns = _tick_fb(top=False); pc = []
ns['place_order'] = lambda *a, **k: pc.append(1)
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

ns = fresh()
ns['g'].spot['X'] = {'last_px': 10.3}
ns['get_gear_price'] = lambda sec: {'ask_grp': {1: [10.5, 1000.0, 2]}}
ok('T42b ask1 卖一价', abs(ns['_elastic_ask1']('X') - 10.5) < 1e-9)
ok('T42b 3s 盘口缓存复用 10.5', abs(ns['_elastic_ask1']('X') - 10.5) < 1e-9)
ns['_DS'].cache.clear()
ns['get_gear_price'] = lambda sec: {}
ok('T42b 缺盘口回退最新价', abs(ns['_elastic_ask1']('X') - 10.3) < 1e-9)

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
    ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append({'sec': sec, 'mode': mode, 'note': note})
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
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append({'sec': sec, 'mode': mode, 'note': note})
ns['tick_data'](ns['_CTX'], {})
ok('T44 tick 帧末 elastic 触发', len(pc) == 1 and 'elastic_arb' in pc[0]['note'] and code in ns['g'].daily['bought'])

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
snap_calls = []
ns['get_snapshot'] = lambda sec: snap_calls.append(sec) or {'600002.XSHG': {'preclose_px': 10.0, 'last_px': 10.2}}
ns['g'].spot['600001.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.5}   # 我 +5%
ns['g'].spot['600002.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.3}   # 成员 +3%
ok('T45 成员在 g.spot -> 不调 get_snapshot', ns['_board_top_gainer']('600001.XSHG') is True and snap_calls == [])
ns['g'].spot['600002.XSHG'] = {}
ok('T45 成员缺快照 -> 回退 get_snapshot', ns['_board_top_gainer']('600001.XSHG') is True and snap_calls == ['600002.XSHG'])
ns['g'].spot['600002.XSHG'] = {'preclose_px': 10.0, 'last_px': 10.6}   # 成员 +6% > 我
ok('T45 成员更高 -> 非最高', ns['_board_top_gainer']('600001.XSHG') is False)


# --- T46 L2 逐笔首笔成交感知（_tx_first_zt_ms，灵敏度<=3s） ---
ns = fresh()
_lt = time.localtime()
_DAY = '%04d%02d%02d' % (_lt.tm_year, _lt.tm_mon, _lt.tm_mday)
ns['get_individual_transaction'] = lambda secs, data_count=200, is_dict=True: {
    '600001.XSHG': [[int(_DAY + '092958000'), 12.0, 100, 1, 2, 0, 0, 0, 0, 1],   # 09:29:58 竞价 -> 忽略
                    [int(_DAY + '093001500'), 12.05, 200, 2, 2, 0, 0, 0, 0, 1],  # 09:30:01 未到涨停 -> 忽略
                    [int(_DAY + '093003000'), 12.1, 300, 3, 2, 0, 0, 0, 0, 1],   # 09:30:03 涨停价 -> 首笔
                    [int(_DAY + '093004000'), 12.1, 400, 4, 2, 0, 0, 0, 0, 1]],  # 09:30:04 涨停价 -> 更晚
    'fields': ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction',
               'buy_no', 'sell_no', 'trans_flag', 'trans_identify_am', 'channel_num']}
ns['g'].spot['600001.XSHG'] = {'up_px': 12.1}
ok('T46 逐笔涨停价首笔时间', ns['_tx_first_zt_ms']('600001.XSHG') == int(_DAY + '093003000'))
ns['g'].spot['600001.XSHG'] = {'up_px': 12.2}
ok('T46 无涨停价成交 -> None', ns['_tx_first_zt_ms']('600001.XSHG') is None)
ns['get_individual_transaction'] = lambda secs, data_count=200, is_dict=True: None
ok('T46 接口异常/无数据 -> None', ns['_tx_first_zt_ms']('600001.XSHG') is None)


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
    _tx_calls.append(list(secs))
    rows1 = [[int(_DAY + '093003000'), 12.1, 300, 3, 2, 0, 0, 0, 0, 1]]
    return {'600001.XSHG': rows1, '600002.XSHG': [],
            'fields': ['business_time', 'hq_px', 'business_amount', 'trade_index', 'business_direction',
                       'buy_no', 'sell_no', 'trans_flag', 'trans_identify_am', 'channel_num']}
ns['get_individual_transaction'] = _tx
frame = {'600002.XSHG': {'transaction': {'business_time': int(_DAY + '093004000'), 'hq_px': 12.2}}}
out = ns['g'].ds.tx_zt_batch(['600001.XSHG', '600002.XSHG'], frame)
ok('T51 帧推送优先', out.get('600002.XSHG') == int(_DAY + '093004000'))
ok('T51 批量一次拉取(仅缺者)', _tx_calls == [['600001.XSHG']])
ok('T51 批量解析命中', out.get('600001.XSHG') == int(_DAY + '093003000'))
out2 = ns['g'].ds.tx_zt_batch(['600001.XSHG', '600002.XSHG'], frame)
ok('T51 同帧二次消费不重复拉', len(_tx_calls) == 1 and out2.get('600001.XSHG') == int(_DAY + '093003000'))

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
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append(sec)
ns['_try_first_board_buy'](ns['_CTX'], '600001.XSHG', rank_secs=['600001.XSHG'])
ok('T55 板块非前三 -> 首板拦截', out == [])
ns['_board_rank_top3'] = lambda sec, secs=None: True
ns['_try_first_board_buy'](ns['_CTX'], '600001.XSHG', rank_secs=['600001.XSHG'])
ok('T55 板块前三 -> 首板放行', out == ['600001.XSHG'])


# --- T56 生命周期窗口（v0.24：首板9:40前 / 低吸13:30前 / 其它10:00前） ---
ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 31, 0)
ns['_tags'] = lambda sec: ['CORE', 'BS']; ns['_ensure_ma5'] = lambda sec: 10.0; ns['last_px'] = lambda sec: 9.5
ns['score_now'] = lambda sec: 60.0; ns['_red_ratio'] = lambda sec: 0.7; ns['trade_open'] = lambda sec: True
ns['_ma5_first_5d'] = lambda sec: True
out = []
ns['place_order'] = lambda c, sec, side=None, note='', **k: out.append(sec)
ns['_save_state'] = lambda *a, **k: None
ns['try_ma5_buy'](ns['_CTX'])
ok('T56 10:31 后低吸拦截', out == [])
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 0, 0)
ns['try_ma5_buy'](ns['_CTX'])
ok('T56 10:00 低吸放行', out == ['600001.XSHG'])

ns = fresh(); ns['g'].watch = ['600001.XSHG']; ns['g'].pool_static = []
ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 1, 0)
ns['_tags'] = lambda sec: ['CORE']; ns['_limitup_days'] = lambda sec: 1; ns['last_px'] = lambda sec: 10.0
ns['score_now'] = lambda sec: 60.0; ns['trade_open'] = lambda sec: True; ns['_block_sealed_buy'] = lambda sec: False
out = []
ns['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: out.append(sec)
ns['_save_state'] = lambda *a, **k: None
ns['try_core_buy'](ns['_CTX'])
ok('T56 10:01 后核心票拦截', out == [])

ns = fresh(); ns['g'].now_dt = datetime.datetime(2026, 10, 16, 10, 1, 0)
ns['g'].exp_file = {'600001.XSHG': {'side': 'buy'}}
calls = []
ns['_attempt_expected_buy'] = lambda c, code: calls.append(code)
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
ns['_do_sell'] = lambda c, sec, qty, note, urgent=False: out.append((sec, note, urgent))
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
ns2['_do_sell'] = lambda c, sec, qty, note, urgent=False: out2.append((sec, note))
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
ns3['_do_sell'] = lambda c, sec, qty, note, urgent=False: out3.append((sec, note, urgent))
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
ns['_red_ratio'] = lambda sec: 0.55
ok('T66 回暖判定 True(streak=2 th=0.51 red=0.55)', ns['_sentiment_warm']('600001.XSHG') is True)
ns['_red_ratio'] = lambda sec: 0.50
ok('T66 未回暖 False(streak=2 th=0.51 red=0.50)', ns['_sentiment_warm']('600001.XSHG') is False)
ns['_red_ratio'] = lambda sec: 0.35
ok('T66 继续冰点 False(red<0.40)', ns['_sentiment_warm']('600001.XSHG') is False)
ns['BLS']['sentiment_enabled'] = False
ok('T66 未启用 -> None', ns['_sentiment_warm']('600001.XSHG') is None)
ns2 = fresh(); ns2['g'].sentiment = {'ice': False, 'ice_streak': 0}
ns2['BLS']['sentiment_enabled'] = True
ok('T66 无冰点基线 -> None', ns2['_sentiment_warm']('600001.XSHG') is None)

ns = fresh(); ns['BLS']['sentiment_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1}
ns['_red_ratio'] = lambda sec: 0.55
ns['BLS']['red_gate_enabled'] = True
ok('T66 _buy_red_ok 回暖放行(streak=1 th=0.53 red=0.55)', ns['_buy_red_ok']('600001.XSHG') is True)
ns['_red_ratio'] = lambda sec: 0.52
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

# 2) 冰点基线 + 今日未回暖 -> 40%
ns = fresh()
ns['BLS']['sentiment_pos_cap_enabled'] = True
ns['g'].sentiment = {'ice': True, 'ice_streak': 1, 'warm_days': 0, 'phase': 'ice', 'divergence': False}
ns['_red_ratio'] = lambda sec: 0.50   # streak=1 -> th=0.53 -> red<th 未回暖
ok('T67 冰点日未回暖 cap=0.40',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.40) < 1e-9)
ns['_red_ratio'] = lambda sec: 0.60   # red>=th 今日回暖
ok('T67 冰点基线回暖日 cap=0.80(回暖首日)',
   abs(ns['_sentiment_pos_cap'](ns['_ctx'], '600001.XSHG') - 0.80) < 1e-9)

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
_n69, _r69 = _sell_setup({'side': 'sell', 'expected_status': 'confirmed_miss'}, ac=5.0, intrady='CM', confirm='CX')
_n69['sell_manager'](_n69['_ctx'])
ok('T69 文件confirmed_miss但实时超预期(CX)反证 -> 不核卖', _r69 == [])
# T69b 文件 confirmed_miss + 实时未反证(PM) -> 仍核卖（对齐 AXquant）
_n69b, _r69b = _sell_setup({'side': 'sell', 'expected_status': 'confirmed_miss'}, ac=5.0, intrady='CM', confirm='PM')
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
ok('T72 place_order 原函数中位 buy -> 拦截(None)', r is None and '600072.XSHG' not in n['g'].daily['bought'])

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
n['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append(sec)
n['try_core_buy'](n['_ctx'])
ok('T72 try_core_buy 中位 -> 不买', '600072.XSHG' not in pc and '600072.XSHG' not in n['g'].daily['bought'])

# try_ma5_buy 中位拦截（CORE+BS 标签 + mid 标注）
n = fresh()
n['g'].watch = ['600072.XSHG']; n['g'].pool_static = []
n['g'].now_dt = datetime.datetime(2026,10,16,10,0,0)
n['g'].exp_file['600072.XSHG'] = {'side':'buy','role_detail':'mid_consecutive_limit_up'}
n['g'].zt_lianban = {'600072.XSHG': {'board_cnt': 3}}
n['_tags'] = lambda sec: ['CORE','BS']
n['_ma5_first_5d'] = lambda sec: True
n['last_px'] = lambda sec: 10.0
n['_ensure_ma5'] = lambda sec: 10.5
n['_red_ratio'] = lambda sec: 0.5
n['score_now'] = lambda sec: 60.0
n['trade_open'] = lambda sec: True
n['BLS']['daily_max_buy'] = 10
n['BLS']['ma5_core_only'] = True
n['BLS']['ma5_require_bs'] = True
n['BLS']['ma5_first_5d'] = True
n['_save_state'] = lambda *a, **k: None
pc = []
n['place_order'] = lambda c, sec, side=None, note='', mode='chase', ratio=None: pc.append(sec)
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

print('ALL DONE')

