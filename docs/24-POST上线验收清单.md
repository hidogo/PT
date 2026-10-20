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

## 10. v0.25 帧级拉取预算（Phase 3）盘中勾选

- [ ] 帧末 `[budget] ...` 日志每帧出现（snapshot/tx/gear/m1/board/blocks 计数可见）。
- [ ] 09:30-10:00 高频段：`[budget]` 中 gear/board/m1 不长期顶格（顶格说明预算偏小，调大对应 frame_*_limit）。
- [ ] 出现 `over:xxx=n` 时核对：P0（tx/snapshot/gear）不应丢关键首触；P1 回退旧板块值不影响首板/弹性门控。
- [ ] 灵敏度回归：`[firstzt] state=first(src=tx)` 仍在涨停价逐笔成交 ~3s 内触发（预算未拖慢 P0）。
- [ ] 无丢帧告警（若快速刷新段告警，调大 budget 或恢复 board_rank_cache_ttl=60 对照）。
- [ ] selftest 233 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 11. v0.26 tick 级卖出（事件驱动 3s 响应）盘中勾选

- [ ] 炸板卖出：持仓股涨停首触后掉出涨停价 -> `[may-order] ... TICK_break_sell`（现价限价，防过度杀价）；同一标的当日仅一次（break_sold 标记）。
- [ ] 封单大减卖出：封单<=首封×1/3 或委托笔数衰竭 -> `[may-order] ... TICK_seal_low_sell`；当日仅一次。
- [ ] 急卖迁移：P1 绿开 / P2E 预期 miss / P3 止损 在 3s 帧末评估（`P1_green_open_tick` / `P2E_exp_miss_tick` / `P3_stop_loss_tick`，核卖限价跌停地板价）。
- [ ] 去重生效：在途挂单 `_sell_inflight` + sold_log 30s 冷却，不叠单；跨重启 break_sold/seal_sold 持久化，同日重启不重复卖。
- [ ] 灵敏度对照：同一持仓从 `[firstzt] ... -> BREAK` 到 `TICK_break_sell` 的日志间隔 <=3s（1m 时代最快 60s）。
- [ ] selftest 239 PASS / 0 FAIL（T59 六项）；双编译 py310 + PT37 通过。

## 12. v0.26b DataHub 模块级单例（修复 g 持久化 pickle 报错）盘中勾选

- [ ] 首启动日志不再出现 `全局对象g持久化对象保存失败，对象名：ds`（DataHub 已移出 g、改模块级单例 `_get_ds()`；引擎仅对 g 内对象做 pickle 持久化，模块级不入列）。
- [ ] 跨重启拉起后 DataHub 缓存自动重建、`_maybe_reset` 日切逻辑不失效（[budget] 帧账本 / [firstzt] / [seal] 行为与 v0.26 一致）。
- [ ] 重传后首启动日志：buysell_core init universe=... DO_ORDER=...（无 initialize 异常、无 ERROR 刷屏）。
- [ ] selftest_exp_rt.py 248 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 13. v0.26c 预期文件日期对齐 + 一字板 09:25 识别盘中勾选

- [ ] 09:25/09:31 出现 `[seal] <名>(code) 一字板(开=涨停价且无卖盘) -> 买入不排队`（东安动力式一字板应被识别）。
- [ ] 盘中重启（同日）后 `before_trading_start` 重跑 `_mark_one_word_open` 重标一字板（v0.31c）：重启日志应再次出现 `[seal] ... 一字板 ... -> 买入不排队`，免 5s 门槛不丢。
- [ ] 一字板 CORE 票不再触发 `[may-order] ... core_buy`（对齐 first_board/elastic 排除）。
- [ ] 预期文件命中生成日命名：`expectation file loaded <...expectation_<T-1 生成日>.csv> -> N`（昨日复盘文件今日验证；只传生成日命名文件也能读到）。
- [ ] selftest_exp_rt.py 302 PASS / 0 FAIL（含 T64 盘中重启重标一字板）；双编译 py310 + PT37 通过。

## 14. v0.27 涨停池预期三态（竞价超预期->观察，窗口内分最高/最主动优先）盘中勾选

- [ ] 09:25 日志 `[exp] 涨停池竞价三态合成 -> exceed=N meet=N miss=N`（合计≈涨停池只数）。
- [ ] 09:25 竞价终态对超预期涨停池标的打 `[exp] <名>(code) 09:25竞价终态初步确认超预期 -> 观察`（与供方推荐同流程）。
- [ ] 绿开（miss）涨停池标的当日不买入；10:00 前分时确认超预期（两分钟上攻/一分钟冲涨停，不破 VWAP）才买。
- [ ] 多候选竞争日买上限 1 时：供方推荐（文件顺序）优先，涨停池合成按「分最高、最早触板(最主动)」排序后置。
- [ ] `[pool]` 的 expect_buy 计数包含涨停池合成条目（pool_static 同步并入）。
- [ ] selftest_exp_rt.py 271 PASS / 0 FAIL；双编译 py310 + PT37 通过。

## 15. v0.28 涨停池 ST 过滤 + 盘前一键脚本 盘中/盘前勾选

- [ ] 涨停池合成日志带 `st_skip=N`：`[exp] 涨停池竞价三态合成 -> exceed=N meet=N miss=N st_skip=N`（ST 已剔除，对齐 AXquant 复盘口径）。
- [ ] ST 股不进涨停池观察/买入候选（`pool_expect_skip_st=True` 默认开；关掉可放开）。
- [ ] 盘前 09:20 前跑 `run_one_click_premarket.cmd`（或 `python research/expectation/run_one_click_premarket.py`）：
      生成 `expectation_<T>.csv`+latest、`zt_lianban_latest.csv`，打印上传勾选清单；空仓 marker 时提示「今日无预期（正常）」且不覆盖既有文件。
- [ ] 盘前核对清单输出「结论: 待上传文件已就绪」，且盘中日志 `expectation file loaded` / `[pool] expect_buy=N>0` / `[zt-lianban] loaded` 命中。
- [ ] selftest T65（ST 过滤：过滤后仅合成非 ST；开关关闭时 ST 也合成）。

## 16. 实盘单测试就绪度 + 账户资金确认（2026-10-20）

### 16.1 账户资金确认（第 1 步完成）
- **账户性质：实盘（无模拟账户）**，真实资金，规模小 —— 所有门控默认关，只有用户显式确认才开。
- Web 平台「交易-资金」：**可用资金 = 17,106.78 元**（用户提供，2026-10-20）。
- 与云端日志交叉验证：10-20 09:33 `core_buy 600178 qty=100 limit=12.41`（ordinary 10%）→
  budget=1710.7 → 1 手（1241 元）→ qty=100 ✓。推算与实报一致，账户规模 ≈ 1.71 万（非 10 万基准）。
- 探针脚本 `research/precheck/query_account.py`（客户端 API get_portfolio/get_positions 全字段，
  落盘 data/positions/query_account_<date>.json）已就绪；桌面客户端登录后可一键重跑确认。

### 16.2 账户规模对参数的影响（关键）
- 单笔预算 = cash × 比例，且受「1 手 = 100 股」门槛约束：qty = floor(budget/(价×100))×100。
- 可用 17,106.78 元：
  - `exp_order_pct=0.10` → 预算 1711 元 → 可下 1 手的价位 ≤ ~17.1 元；价位更高则 qty=0 跳过下单。
  - `exp_order_pct=0.01`（原建议小额）→ 预算 171 元 → **不足 1 手，无法下单**，勿用。
  - 目标价 20 元需 pct≥0.117、25 元需 pct≥0.146。EXPECT_ORDER 阶段按预期文件标的价位设 pct（建议 0.10~0.15）。
- 买入后单只仓位 ≈ 预算/总资产 ≈ 10%（总资产≈1.71万+持仓市值），低于 single_stock_cap=0.30，安全。
- 卖出通道受 DO_ORDER 门控：DO_ORDER=False 时只记 [may-order]，**买卖闭环需 DO_ORDER=True**。

### 16.3 实盘（真实资金）测试放量三步 —— 风险收紧版
> 无模拟账户 → 一切以真实资金执行。原则：先只读、再 1 手、再卖出；任何一步异常立即回 EXPECT_ORDER=False。
1. ① 重传 strategy.py(v0.28)，EXPECT_ORDER=False 至少跑 1 个交易日：`expectation file loaded`、`[exp] 涨停池竞价三态合成 ... st_skip=N`、`[exp-order] (False)` 时序（超预期确认→信号 ≤3s）、无异常 `[exp] miss` 误杀。
2. ② 你确认信号质量后，EXPECT_ORDER=True + exp_order_pct=0.10（单笔 ≤1 手、约 1.7 千元、占总资产 ≤10%），DO_ORDER 保持 False（卖出仍只读）：
   - 核对 `[exp-order] ... (True)` + `on_trade_response` 成交、限价符合打板/追高定价（涨停价排队或现价×(1+0.8%) 封顶涨停价）；
   - `exp order skip(qty<=0)` → 目标股价位超单笔预算，上调 pct（≤0.15，且单笔市值仍 ≤ 总资产 30%）；
   - 单日买上限 daily_max_buy=1 → 每天最多 1 笔真实买入。
3. ③ 买入成交且隔日卖出决策日志正确（P1 绿开核卖/炸板/封单大减/评分止损）后再 DO_ORDER=True 放开卖出闭环；
   卖出限价现价在下跌/封死场景可能不成交留滞持仓（docs/24 §3/§5 留档），实盘需接受或先用核卖跌停地板价保成交。
4. 实盘止损纪律：连续 2-3 笔亏损、出现未成交/留滞/重复下单/成交回报异常 → 立即回 EXPECT_ORDER=False，复盘后再继续。

### 16.4 剩余前置（第 2/3 步）
- [ ] 今日收盘跑 `run_one_click_after_close.py --date 2026-10-20` 生成 10-21 预期（非空仓）。
- [ ] 明早 `run_one_click_premarket.cmd` 生成+校验，09:20 前定时上传 `expectation_2026-10-21.csv`(+latest)+`zt_lianban_latest.csv`。
- [ ] 重传 strategy.py(v0.28) 到模拟盘，按 16.3 三步放量。

## 17. v0.29 情绪冰点→回暖链（docs/40）盘前/盘中勾选
- [ ] 盘前：`run_one_click_premarket.cmd` 自动导出 `sentiment_latest.csv`；核对 `[sentiment] loaded -> ice=0/1 streak=N`。
- [ ] 冰点日（T）：本地 `export_sentiment.py` 判定 `ice=1`（红盘率<40% 或 封板率<45% 或 涨停<30）；`ice_streak` 连续累计。
- [ ] T+1 盘中（开启时）：`[sentiment] <名>(code) streak=N red=0.xx th=0.xx -> 回暖/未回暖`；`red<0.40` 打「继续冰点，等下一交易日再验证」。
- [ ] 回暖概率增加：ice_streak=1 → 恢复阈值 0.53；=2 → 0.51（上限 0.55、下限 0.45）。
- [ ] `_buy_red_ok` 组合门：`red_gate_enabled`+`sentiment_enabled` 都开才生效；默认全关（实盘安全）。
- [ ] selftest T66（读入/回暖/继续冰点/未启用 None/组合门）通过；281 PASS / 0 FAIL。

## 18. v0.30 情绪仓位闭环（docs/40 §6）盘前/盘中勾选
- [ ] 盘前：核对 `sentiment_latest.csv` 含新列 `warm_days/phase/divergence`（export_sentiment.py v0.30 输出）。
- [ ] v0.31 已默认启用（`sentiment_pos_cap_enabled=True`）：盘前日志必须有 `[pos-cap] 已启用：冰点上限=0.40 回暖上限=0.80 ...` 记录；无此记录说明 strategy.py 未重传到 v0.31。
- [ ] 盘中：冰点日未回暖 `[pos-cap]` 上限 40%；回暖/延续日上限 80%（连续回暖 ≥3 天递减 0.10，下限 50%）；每次买入判定打 `[pos-cap] <名>(code) 情绪仓位上限 cap=0.xx (ice=.. warm_days=.. phase=..)`。
- [ ] 买入超限拦截：`[pos-cap] <名>(code) qty=N add=... pos_ratio=0.xx > cap=0.xx -> skip`（place_order 买分支 + place_expected_order 两路径）。
- [ ] selftest T67（读新列/冰点40%/回暖80%/递减/_buy_pos_ok 超限 skip/两路径闸门/v0.31 默认启用）通过；296 PASS / 0 FAIL。

## 19. v0.32 云端持仓预期管理（2026-10-20，docs/33）
> 本地拉持仓不可行 → 持仓预期管理全部由云端算法完成（_hold_exp_init），不依赖本地文件。
- [ ] 重传 strategy.py（v0.32）后盘中观察 [hold] <名称>(code) 持仓预期管理初始化 entry_type=.. auction_status=.. status=.. sell_policy=..（09:25/09:31/日切 及 每笔成交触发一次）。
- [ ] 盘中新买入持仓：成交回报后当日持仓立即有 [hold] 初始化日志（原缺口：仅 09:25/09:31 初始化）。
- [ ] P4 卖出链对盘中新买入持仓生效：普通持仓走 _eval_intraday（两分钟上攻/破VWAP），一字板持仓走 _exp_one_word 封单实时化（L2 封单超预期 CX/衰竭 CS）。
- [ ] 重启/日切后持仓预期条目自动重建（_hold_exp_init 幂等；handle_data 日切 force 重算）。
- [ ] selftest T66-T68 通过；全量 312 PASS / 0 FAIL；双编译通过。

## 20. v0.33 文件持仓预期 vs 云端实时 防冲突仲裁（docs/33）
- [ ] 重传 strategy.py（v0.33）后，上传复盘文件含 side=hold/sell 行时盘中核对：
  - [ ] 文件乐观容忍（hold_higher_tolerance）+ 实时绿开/破VWAP → [arb] <名>(code) 文件 sell_policy=.. vs 云端实时走弱 -> P1/P3 阈值回落基础（P1 绿开/P3 止损不再被文件宽容压住）。
  - [ ] 文件悲观（confirmed_miss/degraded）+ 实时竞价超预期 → [arb] .. 不核卖（P2E 不误杀转强股）；未反证仍 P2E_exp_miss 核卖。
  - [ ] 文件 ntry_type=one_word + 实时已开板 → [arb] .. 回落普通分时三态（走 P4_exp_miss）；实时仍封板 → 走 P4_exp_one_word 封单。
- [ ] selftest T69/T69b/T70/T71/T71b 通过；全量 318 PASS / 0 FAIL；双编译通过。

## 21. v0.34 连板中位股规避（docs/33）盘前/盘中勾选
- [ ] 盘前：确认 bridge CSV（expectation_<T+1>.csv）表头含 `role_detail` 列，且持仓/苗子行带 mid_consecutive_limit_up / unique_high_board_consecutive / leading_first_board / first_board_arb 标注（AXquant 复盘 publish.py derive_role_detail 已产出）。
- [ ] 重传 strategy.py（v0.34）后盘中核对：预期三态买入/核心/低吸/首板/弹性入口对中位标注股打 `[mid-avoid] <名称>(code) 连板中位股规避(<入口>)`，不进入买入候选；涨停池合成日志含 `mid_skip=N`。
- [ ] 低位/高位放行：role_detail=leading_first_board / first_board_arb / unique_high_board_consecutive 的标的正常进入对应买入场景（不被中位闸误杀）。
- [ ] 无标注兜底：盘前 zt_lianban_latest.csv 已传（T-1 涨停/连板名单，需含 `reason` 列），加载日志 `[zt-lianban] loaded .. -> N unique_high=M`；无 role_detail 时按 T-1 连板数 2-5 近似中位规避、<2 首板/一进二放行、>=6 高标放行。
- [ ] 唯一性兜底（v0.34b）：高度压制到 3/4 板但为板块内唯一高度板+跟风低位板（或全市场唯一高标）→ 放行不规避（`unique_high=True`）；并列最高/板块内有更高身位 → 按中位规避。
- [ ] 卖出链不受影响：持仓股（含中位连板）卖出照常走 P1/P2E/P3/P4，无 [mid-avoid] 日志。
- [ ] selftest T72 系列通过；全量 333 PASS / 0 FAIL；双编译通过。
