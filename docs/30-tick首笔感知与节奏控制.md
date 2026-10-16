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
