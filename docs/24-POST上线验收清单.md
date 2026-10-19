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

- [ ] 【统一股池（v0.12）】[pool] 日志 selfwatch=N expect_buy=M（N 来自上传的 selfwatch.csv；推荐池 side=buy 计入）；确认超预期(CX)候选可被买入、一字板/卖侧推荐能触发。

## 4. 买入管理（入池标的）
- [ ] MA5 低吸：见 [may-order] ma_pullback px=.. ma5=.. score=..（score>=55）。
- [ ] 同标的冷却：同一标的两次买入间隔>=cold_secs(60)。
- [ ] 每日封顶：单日 [may-order] 买入数<=daily_max_buy(1)。

## 4b. 预期文件桥接（docs/25，v0.8）
- [ ] before_trading_start 日志出现 expect file loaded <path> -> N（N=读取条目数；缺失属正常，扫描兜底）。
- [ ] 09:31 后对文件内 code 做竞价确认：_try_expected_buys 打 [may-order] expect_buy <status> auction=..%%（side=buy 且未miss）。
- [ ] side=sell 的条目进 P4（P4_exp_miss / one_word 封单）卖出通道。
- [ ] AXquant 侧已 export_expectation_csv() 生成 expectation_<生成日期>.csv 与 expectation_latest.csv 并定时/手动上传到研究 /data/（以生成日期命名，云端优先读 latest）。

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

## 8. v0.15 对齐 AXquant 买卖逻辑验收点（重传后逐项勾选，见 docs/33）

### 8.1 一字板·封单超预期不参考排单
- [ ] 一字封死涨停标的：盘中出现 `[seal] <code> sealed at limit -> no queue buy`（每日仅一次），且**不产生** [may-order]/[exp-order] 买入委托。
- [ ] 未封死（卖盘有挂单）的涨停：仍可打板排队买入（挂涨停价 limit=up_px）。
- [ ] 已持仓自检：`_order_limit(board)` 封死返回 None、`place_expected_order` 返回 False 不置 fired（次日仍可再评估）。

### 8.2 竞价核卖 P2E（预期确认 miss）
- [ ] 持仓预期 expected_status=confirmed_miss/degraded：卖出一侧见 `[may-order] ... P2E_exp_miss confirmed_miss`（DO_ORDER=True 时真实卖单）。
- [ ] pending_miss 默认不卖（exp_sell_on_pending_miss=False）；置 True 后才核卖 pending_miss。
- [ ] pending_meet/pending_exceed 不会误触发 P2E。

### 8.3 弹性买入价 10% 上限（300/688）
- [ ] 300/301/688/689 追高：下单价不超前收×1.10（`_order_limit chase` 封顶），日志可见 limit 合理。
- [ ] 300/688 打板（board 模式）豁免 10% 上限，仍挂涨停价。
- [ ] 主板（非 300/688）追高不受此限制。

### 8.4 回归
- [ ] selftest_exp_rt.py 本机 30/30 通过；PT3.7 + py310 均 py_compile 通过。
- [ ] 重传策略后首启动日志：buysell_core init universe=... DO_ORDER=... EXPECT_ORDER=...（确认 v0.15 生效，无 initialize 异常）。
- [ ] 盘中/收盘把沙盒日志 ingest 进 log_collector，核对 [seal]/P2E_exp_miss/追高限价 三条。

### 8.5 T-1 涨停/连板名单（zt_lianban_latest.csv）
> 说明：涨停/连板不再由云端逐只行情调用，改为取本地 AXquant 已产出的涨停池，经 expectation 上传链路到研究目录（详见 docs/33）。

- [ ] 收盘后（本地）`run_one_click_after_close.py` 内 `export_lianban` 已生成 `data\ptrade_bridge\zt_lianban_latest.csv`
- [ ] 确认 `zt_lianban_latest.csv` 已上传研究目录（定时上传按文件夹，落 `upload_file/` 等路径，云端优先读 latest）
- [ ] 重传 `strategy.py`
- [ ] 盘前一碰：`before_trading_start` / 09:25 / 09:31 对应日志 `[zt-lianban] loaded <...>zt_lianban_latest.csv -> N`，N=涨停只数
- [ ] 验证 `_limitup_days` 走权威 `board_cnt`（+今日续板 1），tags（LB/CORE）用权威连板
- [ ] 异常/细节应对：`[pool]` / `[zt-lianban]` 空值时确认重传 latest 是否最新一份
- [ ] 未上传时不报错：`_load_zt_lianban()` 返回 0，`_limitup_days` 自动回退 1d 历史近似

### 8.6 提供方（AXquant）对接与产出一致性核验（verify_provider.py，可随时跑）
- [ ] 任意时刻探活：`python research/expectation/verify_provider.py --date <复盘日> --next-date <预期日>`，步骤A 打印 AXquant 6 条输入 OK/MISS + 时效。
- [ ] 盘前勾选：确认 `zt_lianban_latest.csv` / `expectation_latest.csv` 已上传，`verify_provider.py` 步骤B `[预期] CSV==src ok=True`、`[名单] zt==boards ok=True`。
- [ ] 收盘勾选：跑 `run_one_click_after_close.py`，核对其 `步骤0 提供方就绪校验`（缺失会告警、`--require-provider` 直接中止）与 `步骤5 产出一致性核对` 均为 ok=True。
- [ ] 门禁（可选）：`verify_provider.py --strict`，存在缺失/不一致时返回非零，可用于排程/脚本门禁。
- [ ] 契约变更走 `docs/34-数据提供方对接矩阵.md`（目录布局 + 代码后缀归一规则），勿散落硬编码路径。

---
配套文档：docs/16、17、18、20、23；AXquant 参数来源见 strategies/buysell_core/notes.md；v0.15 对齐细节见 docs/33。


## 9. v0.20/v0.23/v0.24 盘中共核点（重传后逐项勾选）

### 9.1 L2 逐笔首触（v0.20，docs/30 §6）
- [ ] `[l2] <code> tx_row=... / tx_fields=...`：核对逐笔成交字段结构（business_time/hq_px 等，与 `_parse_tx_zt_ms` 解析一致）。
- [ ] `[firstzt] <code> ... state=first(src=tx)`：L2 逐笔涨停价成交触发，时点接近真实封板（灵敏度 <=3s）；推送缺字段自动回退拉取（src 仍为 tx 但走批量兜底）。

### 9.2 板块强度前三门控（v0.23，docs/38 §7）
- [ ] 首板/弹性仅对"强度前三板块"出单：`_board_rank_top3` 命中才 `[may-order] first_board_buy / elastic_arb`。
- [ ] `score ... board=..` 与弹性日志 `boards=..` 板块值合理（非全 0；失败归 0 属降级）。
- [ ] 板块强度排名 60s 缓存复用（同板块多次消费不重复拉快照）。

### 9.3 板块刷新提速（v0.24，docs/38 §8）
- [ ] 09:30-10:00：`score ... board=..` 随 3s 帧刷新（值变化更敏捷；`_board_refresh_ttl()=3s`）。
- [ ] 10:00 后：刷新回落 60s（`_board_refresh_ttl()=60s`）。
- [ ] 性能对照：若 3s 快速刷新导致帧内调用偏多/丢帧告警，调大 `board_rank_fast_until_minute` 或临时恢复 `board_rank_cache_ttl=60` 对照。

### 9.4 生命周期窗口（v0.24）
- [ ] 首板打板：09:30-09:40 前出单；09:40 后不再出现 `first_board_buy`。
- [ ] 5日低吸：10:30 前出单；10:30 后不再出现 `ma_pullback`。
- [ ] 核心票/预期买入/弹性套利：10:00 前出单；10:00 后不再出现 `core_buy` / `expected` / `elastic_arb` 买入。

### 9.5 回归
- [ ] selftest_exp_rt.py 219 PASS / 0 FAIL；PT3.7 + py310 py_compile 通过。
- [ ] 重传后首启动日志：buysell_core init universe=... DO_ORDER=...（确认 v0.24 生效，无 initialize 异常）。
