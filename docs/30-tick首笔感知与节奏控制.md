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
