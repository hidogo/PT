# -*- coding: utf-8 -*-
"""
示例 02：run_daily 定时任务的托管策略
- 每日指定时刻执行一次策略逻辑（这里演示开盘后1分钟取财务指标）
说明：run_daily 只能在 initialize 中注册；累计定时任务不超过5个。
"""

def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    # 每个交易日 09:31 运行 once_a_day；交易场景 time 可设 00:00-23:59
    run_daily(context, once_a_day, time='09:31')

def once_a_day(context):
    try:
        re = get_fundamentals(g.security, 'balance_statement', 'total_assets')
        log.info('total_assets: %s' % re)
    except Exception as e:
        log.warn('get fundamentals failed: %s' % e)

def handle_data(context, data):
    pass
