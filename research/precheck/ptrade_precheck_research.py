# -*- coding: utf-8 -*-
"""
PTrade 研究环境冒烟测试（只读）——在「研究」模块直接运行本文件。
重点：数据/L2 可用性体检。运行后把上方 Output 贴给开发者即可。
L2 接口在「研究」通常返回 None/无数据（仅交易模块为准），见结果对比。
"""
import time


def probe(tag, fn):
    try:
        r = fn()
        s = str(r)
        print('[%s] OK  %s' % (tag, s if len(s) <= 800 else s[:800] + '...'))
    except Exception as e:
        print('[%s] ERR %r' % (tag, e))


def main():
    s = '600570.XSHG'   # 默认标的，可改
    print('== PTrade 研究冒烟测试 start ==', time.strftime('%Y-%m-%d %H:%M:%S'))
    print('交易日:', end=' ')
    try:
        print(get_trading_day())
    except Exception as e:
        print('ERR', e)

    probe('get_history(1d)', lambda: get_history(5, '1d', 'close', s, fq=None, include=False))
    probe('get_price(1m)', lambda: get_price(s, start_date=None, end_date=None, count=5, frequency='1m'))
    probe('get_snapshot', lambda: get_snapshot(s))
    probe('get_stock_name', lambda: get_stock_name(s))
    probe('get_stock_info', lambda: get_stock_info(s))
    probe('get_stock_status', lambda: get_stock_status(s))
    probe('get_stock_blocks', lambda: get_stock_blocks(s))
    probe('get_index_stocks(000001.XSHG)', lambda: get_index_stocks('000001.XSHG')[:10])
    probe('get_fundamentals', lambda: get_fundamentals(s, 'balance_statement', 'total_assets'))
    probe('check_limit', lambda: check_limit(s))
    probe('get_Ashares', lambda: get_Ashares(str(get_trading_day()))[:10])
    # L2（研究环境大多无数据，仅供参考）
    probe('get_gear_price(L2五档)', lambda: get_gear_price(s))
    probe('get_individual_transaction(L2)', lambda: get_individual_transaction([s], data_count=10, is_dict=True))
    probe('get_individual_entrust(L2)', lambda: get_individual_entrust([s], data_count=10, is_dict=True))
    # 研究路径
    probe('get_research_path', lambda: get_research_path())
    print('== done ==')


if __name__ == '__main__':
    main()
