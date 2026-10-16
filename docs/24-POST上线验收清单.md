# POST 上线验收清单 —— buysell_core v0.7（明天盘中逐项勾选）

> 对象：strategies/buysell_core/strategy.py（v0.8e）在当前国金 QTV 托管-模拟盘上线前的验收。
> DO_ORDER 默认 False：本轮“只读验收”，只允许出现 [may-order]，确认无误后才置 True。
> 配套：docs/16（可行性）、docs/17（持久化/三态）、docs/18（买卖分级）、docs/23（首轮冒烟）。

## 0. 前置（开跑前做，不在盘中）
- [ ] 确认跑的是「模拟盘」（非实盘资金）。
- [ ] strategy.py 已重贴到托管策略并重吊起（或明日开盘前自动拉起）。
- [ ] BLS DO_ORDER=False、debug_score=True、scan_enabled=True。
- [ ] 记录起始日、起始资金、持仓（当前 601188/603258/603258? 以实单为准）。

## 1. 启动与入池（开盘~09:31）
- [ ] 日志出现 buysell_core init universe=... DO_ORDER=False（无异常）。
- [ ] before_trading_start done positions=...（持仓/MA5 计算无异常）。
- [ ] 开盘后出现 market_scan bar=.. pool=约4500+ watch=..（入池数合理）。
     ✦ 若 scan 无输出或 watch=0：查 get_Ashares(get_snapshot 批量)是否报错；会自动回退。
- [ ] after_open_probe 09:31 执行、无报错。
- [ ] dump_scores 打印 score ... score=..（评分在跑）。

## 2. 数据/权限核对（盘中任意时段，各一条日志即可）
- [ ] get_trend_data 真竞价：P1 或 _auction_change 返回非 0 竞价涨幅（未报错）。
- [ ] get_snapshot 批量：market_scan 能扫到多只（说明列表快照可用）。
- [ ] get_gear_price（封单，仅交易）：P4 一字路径无异常（回测不可用，见 docs/13）。
- [ ] 【L2 探针（v0.8e）】每日一次打日志 `[l2] code=.. tx=.. entrust=.. gear_bid_cnt=.. -> L2_OK/L2_NONE`（after_open_probe 或盘中重启后 handle_data 首 bar 兜底各一次，g.l2_probed 去重）。
     ✦ 判定：tx/entrust/gear_bid_cnt 任一不为 0 = `L2_OK`（L2 可用）；全 0 = `L2_NONE`（交易模块无 L2 数据或权限不足）。
     ✦ 逐笔成交 get_individual_transaction / 委托 get_individual_entrust 有非 None 返回、十档 bid_grp 委托笔数>0（见 docs/21）。
- [ ] get_stock_blocks/get_industry_stocks 板块强度：board=.. 非全 0（失败会归 0，属降级）。

- [ ] 【入池行情口径（v0.9）】market_scan 后 watch 候选 `px` 且 `ma5` 均非 0（同 px 修复同一类“只刷 universe”问题已收敛）；若仅其一非 0 即持疑。

## 3. 卖出管理（持仓标的，盘中逐项）
- [ ] P1 绿开 / 低开：日志见 [may-order] P1_green_open（竞价跌幅<=-5% 标的）。
- [ ] P3 止损：见 P3_stop_loss pnl=..%（亏损达板块止损线）。
- [ ] P4 预期三态：见 P4_exp_miss / P4_exp_one_word（竞价不及 / 封单衰竭）。
- [ ] P5/P6 分数：见 P5_score_clear / P6_score_half（分数<30 / 30~50）。
- [ ] 每笔卖出都仅 [may-order]、无真实委托（DO_ORDER=False 时）。

## 4. 买入管理（入池标的）
- [ ] MA5 低吸：见 [may-order] ma_pullback px=.. ma5=.. score=..（score>=55）。
- [ ] 同标的冷却：同一标的两次买入间隔>=cold_secs(60)。
- [ ] 每日封顶：单日 [may-order] 买入数<=daily_max_buy(1)。

## 4b. 预期文件桥接（docs/25，v0.8）
- [ ] before_trading_start 日志出现 expect file loaded <path> -> N（N=读取条目数；缺失属正常，扫描兜底）。
- [ ] 09:31 后对文件内 code 做竞价确认：_try_expected_buys 打 [may-order] expect_buy <status> auction=..%%（side=buy 且未miss）。
- [ ] side=sell 的条目进 P4（P4_exp_miss / one_word 封单）卖出通道。
- [ ] AXquant 侧已 export_expectation_csv() 生成 expectation_<次日>.csv 并定时/手动上传到研究 /data/。

## 5. 持久化与收尾（盘后）
- [ ] after_trading_end 打 buysell_core end bought=.. sold=..（buysell_core_state.pkl 写成功）。
- [ ] 结果/日志已归档（贴本会话供对账）。
- [ ] 记录 买入/卖出 触发明细与对应 score/竞价/板块 值，供校准阈值。

- [ ] 【每日买入计数跨重启（v0.11）】盘中重启后 up same-day，daily buy 计数自动恢复（不再同日二买）。日志可见 `before_trading_start restore same-day daily=[..]`。

## 6. 判定与上线开关
- [ ] 只读验收通过 = 全部 [may-order]，无异常/权限报错，行为符合预期。
- [ ] （仅当你确认后）在模拟盘把 DO_ORDER 置 True，小额观察真实委托/成交流。
- [ ] 模拟盘真实下单稳定 -> 再考虑实盘；任何一步异常先回 DO_ORDER=False。
- [ ] 全流程照 docs/20 五阶段清单（编写->上传->回测->模拟->实盘）。

## 7. 记录格式（每项一条）
   [勾选] 时间 bar | 标的 | 事件 | 关键参数（score/竞价/板块/亏损） | 是否符合预期

---
配套文档：docs/16、17、18、20、23；AXquant 参数来源见 strategies/buysell_core/notes.md。
