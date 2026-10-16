# -*- coding: utf-8 -*-
"""
示例 03：run_interval 秒级周期的托管策略
- 每隔10秒取一次行情快照（建议用 interval_timer_ranges 限定交易时段）
说明：run_interval 仅在交易场景可用，最小间隔：期货1秒/股票等其他3秒。
"""

def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    # 在 09:15-11:30 与 13:00-15:00 内每10秒执行 interval_handle
    run_interval(context, interval_handle, seconds=10,
                 interval_timer_ranges='09:15-11:30,13:00-15:00')

def interval_handle(context):
    snap = get_snapshot(g.security)
    log.info(str(snap))

def handle_data(context, data):
    pass
