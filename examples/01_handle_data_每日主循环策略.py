# -*- coding: utf-8 -*-
"""
示例 01：handle_data 每日/分钟主循环策略（5日均线突破）
- 上一价格高出5日均价 1% 时全仓买入
- 上一价格跌破5日均价时清仓
平台：PTrade 托管策略；上线前请在模拟盘先行验证。
说明：该脚本为示例骨架，实际使用时请按自身风控与业务调整。
"""

def initialize(context):
    g.security = '600570.SS'          # 需在 set_universe 股票池内
    set_universe(g.security)          # 设置股票池：只能操作池内标的

def handle_data(context, data):
    security = g.security

    # 过去5天收盘价
    df = get_history(5, '1d', 'close', security, fq=None, include=False)
    avg = round(df['close'][-5:].mean(), 3)   # 5日均价
    price = data[security]['close']            # 上一时间点价格
    cash = context.portfolio.cash

    if price > 1.01 * avg:
        order_value(security, cash)            # 全仓买入
        log.info('buy %s' % security)
    elif price < avg and get_position(security).amount > 0:
        order_target(security, 0)              # 清仓卖出
        log.info('sell %s' % security)
