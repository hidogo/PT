# 30-涨停首笔成交感知与节奏控制（tick_data v0.10）

> 版本：buyesell_core v0.10（采集模式，DO_ORDER=False）　配套 docs/21（L2）、docs/29（封单实时化）

## 1. 目标
- 用 L2 + 事件触发（tick_data）把「涨停首笔成交」感知从 1 分钟提高到约 3 秒（决策节拍仍锁死 3s，不做真亚秒）。
- 采集/决策解耦：tick_data 只写状态与 [firstzt] 日志，下单仍在 1m handle_data，规避重入与丢帧。

## 2. 节奏控制设计
采集(tick_data 3s) --感知/确认--> 决策(1m handle_data) --下单（冷却+日封顶）
- 首次触板：last>=up_px 记 first（first_seal/first_bids/ts/vol）。
- 在板节奏：破板 ->BREAK；封单<首封*seal_fail_ratio ->SEAL_LOW（提前卖/撤依据）。
- 后续接线点（未启用）：确认窗（N tick 封单达标）-> 打板买入；SEAL_LOW/BREAK -> P4 卖出加速。

## 3. 实现要点
- _tick_targets()：持仓+universe 恒有+watch 前 15，控 3s 帧负担避免丢帧。
- 用 get_snapshot(sec) 逐帧（文档建议 tick_data 内直接用 snapshot 最快），顺带刷 g.spot 供 1m 打分。
- 新参数：tick_enabled=true、tick_watch_cap=15。
- g.first_zt 每日重置（init/按日切块/after_open_probe 三处）。

## 4. 采集器
- log_collector 新增 firstzt 分桶 + summary；[firstzt] 三类：state=first / ->BREAK / ->SEAL_LOW。

## 5. 明日盘中核对（v0.10 复传后）
- [ ] [firstzt] state=first 触发时间接近真实封板时刻（误差~3s）。
- [ ] 一字/秒板标的出现 ->BREAK / ->SEAL_LOW，ratio/held 合理。
- [ ] 无丢帧/超时告警（tick 帧内仅轻量 snapshot+gear，无重计算）。


## 6. v0.20 L2 逐笔首笔成交感知（2026-10-19）

目标：打板首触灵敏度提升到 <=3s（平台回调周期上限），并消除"一字板成员误挡板块最快"。

- 验证结论（docs/37）：平台无订阅模式、无亚秒推送；tick_data 3s 回调与 run_interval(股票最小3s) 是上限节拍，
  L2 逐笔为拉取式/帧推送式数据，无逐笔订阅接口。
- 事件模型澄清：Ptrade 只有 tick_data 每 3s 一次回调，L2 逐笔（get_individual_transaction）为拉取式数据。
  信号在"逐笔涨停价成交 + 最多3s轮询间隔"内发出（均值~1.5s），无法做真亚秒推送（PT 无 hot_ticks 通道）。
- 新函数 `_tx_frame_zt_ms(sec, data)`：优先消费 tick_data 帧推送 data[sec]['transaction']（0 额外 API 调用，
  沙盒 DataFrame/dict 形态兼容），命中即确认；推送缺 L2 字段时回退拉取兜底。
- 新函数 `_tx_first_zt_ms(sec)`：拉最近 N 笔逐笔成交（默认200，字段按返回 fields 映射+位序兜底），
  返回最早一笔"成交价>=涨停价 且 09:30 后"的毫秒时间戳（business_time）；无则 None。
- tick_data 首触双源（择先触发）：
  1) L2 逐笔优先：`firsttx_enabled` + 现价>=涨停*firsttx_near_px(0.98) + 非一字板；先读帧推送 data.transaction，
     缺字段再拉 get_individual_transaction（控 API 负担）；
     命中即 g.first_zt[sec] 置 first(src=tx)，ms=逐笔毫秒，并立即 `_try_first_board_buy`。
  2) 快照兜底：原 last>=up + 封单/挂单门槛（src=snap），防逐笔接口抖动漏报。
- `_board_first_zt` 修正：一字板成员不参与"主动最快"竞争（竞价一字非主动拉升，避免误挡同板块打板）。
- `_l2_probe` 增强：每日一次输出 tx_row / tx_fields 样例，盘中核对逐笔字段结构。
- 新参数：firsttx_enabled(true) / firsttx_near_px(0.98) / firsttx_data_count(200)。
- 自测：T46 逐笔解析/涨停价过滤/09:30 过滤/异常兜底 + T47 帧推送优先（188 PASS / 0 FAIL）；双编译 py310+PT3.7 通过。
- 补充（2026-10-19 二次验证）：帧内推送优先已接入（data.transaction -> 0 额外调用，get_individual_transaction 仅兜底）；
  订阅模式/亚秒级能力完整验证矩阵见 docs/37。

## 灵敏度与买卖理由日志（v0.43）
- 结构化信号行 `[signal]` 追加灵敏度字段：`lag=检测->下单时延(秒) det=检测源:首触毫秒`（源=tx/snap，无 L2 首触不强造数据）。
- 人类可读行同步补 lag：`[may-order]`（买入/卖出，note 即操作理由）、`[exp-order]`、`order sent`。
- 买卖操作理由已在各行 note 记录（买入：core_buy/first_board_buy/ma_pullback/elastic_arb/elastic_top/dyn_sweep/exp_rt 状态+原因；卖出：P1_green_open/P2E_exp_miss/P3_stop_loss/P4_exp_*/P5_score_clear/P6_score_half/TICK_break_sell/TICK_seal_low 等）。
- 日结：`after_trading_end` 打 `[rt-summary] side=.. mode=.. n=.. avg=..s max=..s`（按 买卖×模式 汇总当日检测->下单时延）。
- 自测：T96（_signal 补 lag+det / 无首触不采样 / [may-order] 带 lag）+ T90 正则同步更新；全量 PASS / 0 FAIL。


## v0.74 近涨停快速通道与首笔精度（2026-10-26）

**根因（10-26 日志实证）**：`market_scan bar=10:31 pool=5224 watch=6 off=300 cap=300`，
`scan_batch=300` 每分钟只扫 300 只，全市场 5224 只一轮约 17 分钟；新发酵票只有轮到自己窗口才进 watch，
首触滞后 5-17 分钟（良品铺子 `tx_ms=10:17:58` / `[firstzt] 10:35:02`；和泰机电 `10:23:08` / `10:38:02`）。
已在池内票正常（百洋股份约 1 分钟），说明主导瓶颈是候选池覆盖滞后，不是帧内 ms 精度。

**改动**
- `scan_batch 300 -> 600` + 开盘 10 分钟热点优先（`scan_hot_first=True`）：昨日涨停/自选/预期/固定池先扫，
  开盘 10 分钟扫完全市场一轮（6000>=5224），黄金窗口不再等 17 分钟轮询。
- `near_scan` 近涨停快速通道：`_scan_market` 命中 `chg>=scan_near_chg(7.0)` 或贴板入补充池，
  跨轮保留 `scan_near_keep_rounds=3`、上限 `scan_near_cap=20`；已 `first_zt` 移出；`market_scan` 日志加 `near=N`。
- `_tick_targets`：`near_scan` 未首触票排在 watch 前纳入 3s 帧目标，上限 `tick_near_cap=12`；
  新票从 7% 起被盯住，达 `up*0.98` 立即拉逐笔回看最早一笔。
- `_tick_seed_cands`：L2 播种候选 = 逐笔 near + near_scan 未首触票（未到 0.98 也补历史大单，防无数据当无大单）。
- `_tx_frame_zt_ms`：多行 DataFrame/Series/沙盒 iloc 扫描最早一笔涨停价成交（原取 `iloc[-1]`）；
  `tx_zt_batch` 帧推送命中票用同帧 raw 回填更早 ms（0 额外 API）。

**新参数**：`scan_near_chg=7.0`、`scan_near_cap=20`、`scan_near_keep_rounds=3`、`tick_near_cap=12`、
`scan_hot_first=True`；`scan_batch=600`。

**验收口径（下个交易日盘中核对）**
- `[firstzt]` 的 `tx_ms` 与日志时间差值：新发酵票由当前 5-17 分钟降到 ≤2 分钟（扫描轮 + 3s 帧），已入池票 ≤1 分钟。
- `market_scan ... near=N` 应稳定 >0（有近涨停票时），`scan_batch` 日志显示 600。
- 帧内 ms 取最早一笔，误差 ≤1.5s；回填后逐笔 ms 尽量贴近真实首笔。

## v0.76 重启重建 first_zt 修复：不阻塞 / 破板可重建 / ms 口径修正（2026-10-26）

**根因（10-26 14:49 日志实证）**：重启后仅出现 `[restart-rebuild] 登记待重建首触 59 家`，
之后无任何 `恢复首触`；14:50-14:59 仍大量 `state=first(src=tx)` 下午补记
（大名城 `tx_ms=14:26:03`、海量数据 `14:31:26`、良品铺子 `13:31:09` 等）。

**改动**
- 重建不要求“当前仍封板”：只要有 `up_px` 即回看最早涨停价成交，破板票也能补当日首触。
- 缺 `up_px` 的票先批量补快照（一次 RPC），仍缺则 30s 重试；冷却票不占单帧 cap，
  队列不再被无快照票永久阻塞（旧实现固定取 `pending[:5]`，spot 缺失即无限卡死）。
- `ms` 只取 `_parse_tx_zt_ms` 最早涨停价成交；失败才降级快照 `hsTimeStamp`，
  记录 `src=restart_rebuild_fallback`；不再使用 tickdir `first_ts`（那是逐笔首笔，不是涨停首触）。
- 新增 60s heartbeat `[restart-rebuild] pending=N done=M wait=W` 与逐笔失败告警。
- `handle_data` 1m 兜底消化重建队列（`restart_rebuild_1m_enabled=True`），tick 禁用/丢帧仍可恢复。

**新参数**：`first_zt_rebuild_heartbeat_sec=60.0`、`restart_rebuild_1m_enabled=True`。

**验收口径（重传后核对）**
- 日志首行 `buysell_core init version=v0.76`；重启后出现
  `[restart-rebuild] 恢复首触 ... src=restart_rebuild`。
- 上午已触板票 `first_zt.ms` 回到上午真实涨停首笔，不再以 200 笔窗口截断；
  下午不再出现 `state=first(src=tx)` 补记。
- `[restart-rebuild] pending=.. done=.. wait=..` heartbeat 60s 一次，队列能持续推进。

## v0.75 盘中定期保存 / 重启重建首触 / 全链路剔除 ST（2026-10-26）

**根因（10-26 日志实证）**：12:52 盘中重启后，上午已首触票（海量数据、良品铺子、和泰机电等）
13:00-13:05 被重新识别 `state=first(src=tx)`，`tx_ms` 只回看最近 200 笔窗口，拿不到上午真实首笔；
同时 scan/watch/near 仍可能收录 ST。

**改动**
- A 盘中定期保存：`handle_data` 帧末按 `state_save_interval=60.0` 节流 `_save_state()`，
  `first_zt/l2_big/买卖标记`持续落盘，重启恢复到分钟级。
- B 重启重建 first_zt：`_l2_big_seed` 累计器新增 `first_ts`（分时成交最早时间戳）；
  `before_trading_start` 同日重启分支 `_rebuild_first_zt_queue()` 登记缺失首触票（排除 ST），
  tick 帧按 `first_zt_rebuild_cap=5` 分批 `_rebuild_first_zt_tick()`。
  ms 优先级：tickdir `first_ts`（>=09:30）→ `get_individual_transaction` 批量回看 → 快照 `hsTimeStamp`；
  失败 30s 重试；记录 `src=restart_rebuild`，幂等不重复补录。
- C 全链路剔除 ST：`skip_st_pool=True`，`_is_st()` 优先 `zt_lianban.is_st`、名单外名称前缀兜底并缓存；
  `_warm_name_map()` 批量预热名称（`get_stock_name` 列表一次 RPC）；
  应用到 `_scan_market/_tick_targets/_tick_seed_cands/_sync_pool_static/_pool/重启重建`；
  持仓 ST 保留在 `pos` 卖出监控。

**新参数**：`state_save_interval=60.0`、`skip_st_pool=True`、`first_zt_rebuild_cap=5`、
`first_zt_rebuild_tx_count=200`、`first_zt_rebuild_retry_sec=30.0`。

**验收口径（下个交易日核对）**
- 日志首行 `buysell_core init version=v0.75`；`[restart-rebuild]` 只在同日重启后出现。
- 重启后上午已触板票的 `first_zt.ms` 能回到上午真实首笔（`src=restart_rebuild`），不再以 200 笔窗口截断。
- `market_scan` / `near_scan` / `_tick_targets` 不含 ST；再次重启 first_zt 不重复补录。
