# -*- coding: utf-8 -*-
"""
PTrade 托管策略 - 前期必要冒烟测试（只读，不真实下单）v2
v2 变更：
  1) 主探针从 handle_data 移入 before_trading_start —— 策略被吊起时立即执行，
     盘后也能跑（历史行情/证券信息/板块财务/持久化）；盘中字段最准。
  2) 资产字段修正为 context.portfolio.cash（Ptrade 托管字段；聚宽的
     available_cash 不存在，会取到默认值 n/a）。
  3) L2 实时接口仅在交易时段 + 已开通 Level2 才有真实数据，盘后返回 None/0 属正常。
结果：写入 get_research_path() 下的 precheck_result_YYYYMMDD.txt，另见日志。
"""
import pickle, time

DO_ORDER = False               # 前期阶段保持只读
WRITE_RESULT = True


def initialize(context):
    g.security = '600570.XSHG'   # 改这里
    set_universe(g.security)
    g.done = False
    g.lines = []
    g.t0 = time.time()


def _log(context, tag, obj):
    line = '[' + tag + '] ' + time.strftime('%H:%M:%S') + ' -> ' + str(obj)
    g.lines.append(line)
    try:
        log.info(line)
    except Exception:
        pass


def _rl(s):
    """截断超长串，便于日志/结果文件阅读"""
    s = str(s)
    return s if len(s) <= 800 else s[:800] + '...(truncated ' + str(len(s)) + ')'


def save_result():
    if not WRITE_RESULT:
        return
    try:
        path = get_research_path()
        day = str(get_trading_day())
        with open(path + 'precheck_result_' + day + '.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(g.lines))
        log.info('result saved -> ' + path + 'precheck_result_' + day + '.txt')
    except Exception as e:
        try:
            log.warn('save_result failed: %r' % e)
        except Exception:
            pass


def probe(context):
    s = g.security
    _log(context, 'probe', 'start security=' + s)

    # A) 账户与持仓（portfolio 字段用 context.portfolio.cash；盘后可能未同步）
    for tag, fn in [
            ('context.portfolio.cash', lambda: getattr(getattr(context, 'portfolio', None), 'cash', 'n/a')),
            ('context.portfolio.portfolio_value', lambda: getattr(getattr(context, 'portfolio', None), 'portfolio_value', 'n/a')),
            ('get_positions', lambda: _rl(get_positions()))]:
        try:
            _log(context, tag, fn())
        except Exception as e:
            _log(context, tag, 'ERR %r' % e)

    # B) 行情
    for tag, fn in [
            ('get_history(1d)', lambda: _rl(get_history(5, '1d', 'close', s, fq=None, include=False))),
            ('get_price(1m)', lambda: _rl(get_price(s, start_date=None, end_date=None, count=5, frequency='1m'))),
            ('get_snapshot', lambda: _rl(get_snapshot(s)))]:
        try:
            _log(context, tag, fn())
        except Exception as e:
            _log(context, tag, 'ERR %r' % e)

    # C) 证券信息
    for tag, fn in [
            ('get_stock_name', lambda: get_stock_name(s)),
            ('get_stock_info', lambda: _rl(get_stock_info(s))),
            ('get_stock_status', lambda: _rl(get_stock_status(s)))]:
        try:
            _log(context, tag, fn())
        except Exception as e:
            _log(context, tag, 'ERR %r' % e)

    # D) 板块 / 财务 / 指数
    for tag, fn in [
            ('get_stock_blocks', lambda: _rl(get_stock_blocks(s))),
            ('get_index_stocks(000001.XSHG)', lambda: _rl(get_index_stocks('000001.XSHG')[:10])),
            ('get_fundamentals', lambda: _rl(get_fundamentals(s, 'balance_statement', 'total_assets')))]:
        try:
            _log(context, tag, fn())
        except Exception as e:
            _log(context, tag, 'ERR %r' % e)

    # E) L2 相关（仅交易时段 + 已开通 Level2 才有真实数据）
    for tag, fn in [
            ('get_gear_price(L2五档)', lambda: _rl(get_gear_price(s))),
            ('get_individual_transaction(L2逐笔成交)', lambda: _rl(get_individual_transaction([s], data_count=10, is_dict=True))),
            ('get_individual_entrust(L2逐笔委托)', lambda: _rl(get_individual_entrust([s], data_count=10, is_dict=True)))]:
        try:
            _log(context, tag, fn())
        except Exception as e:
            _log(context, tag, 'ERR %r' % e)

    # F) 涨跌停
    try:
        _log(context, 'check_limit', _rl(check_limit(s)))
    except Exception as e:
        _log(context, 'check_limit', 'ERR %r' % e)

    # G) 持久化自检（写研究目录 pickle）
    try:
        path = get_research_path() + 'g_test.pkl'
        with open(path, 'wb') as f:
            pickle.dump({'sec': s, 'ts': g.t0}, f, protocol=2)
        with open(path, 'rb') as f:
            d = pickle.load(f)
        _log(context, 'persistence(pickle)', 'OK sec=' + str(d.get('sec')))
    except Exception as e:
        _log(context, 'persistence(pickle)', 'ERR %r' % e)

    g.done = True
    save_result()
    log.info('precheck done')


def before_trading_start(context, data):
    if g.done:
        return
    try:
        _log(context, 'before_trading_start', '交易日=' + str(get_trading_day()))
    except Exception as e:
        _log(context, 'before_trading_start', 'ERR %r' % e)
    probe(context)   # 吊起即执行主探针


def handle_data(context, data):
    # 盘中每根 bar 触发；探针已在 before_trading_start 跑过，这里仅兜底补跑一次
    if g.done:
        return
    probe(context)


def after_trading_end(context, data):
    save_result()
    try:
        log.info('[after_trading_end] probe finished %.1fs' % (time.time() - g.t0))
    except Exception:
        pass
