# Ptrade 持久化（缓存）方案与“预期三态”实现评估

> 回答两个问题：1) Ptrade 托管可用的缓存/持久化方案有哪些；2) axquant 的“次日三态预期”逻辑能否在 Ptrade 托管内完整实现。

## 一、Ptrade 可用缓存 / 持久化方案

| 方案 | 适用 | 说明与注意事项 |
| --- | --- | --- |
| 1) 框架自动持久化（全局对象 g） | 交易/回测 | 框架在 before_trading_start（隔日）、handle_data、after_trading_end 之后自动保存 g 中**可序列化**对象（含账户、订单、股票池）。重启顺序：先执行 initialize 再恢复持久化，恢复值会覆盖 initialize 的初值。g 中不能序列化（IO、类实例）的对象不保存；以 __ 开头的私有变量不保存。 |
| 2) 手动 pickle 到研究路径 | 交易/回测 | 用 get_research_path() 获取研究根目录，pickle.dump/load 自定义文件（如 hold_days.pkl）保存任意跨日状态；建目录用 create_dir。文件是否跨交易重启保留取决于券商对“研究目录”的持久化策略，需在模拟盘验证；框架自动持久化是保底。 |
| 3) 底仓设置 set_yesterday_position | 仅回测 | 设置回测初始底仓（股票/两融）；convert_position_from_csv(path) 从 csv 读底仓参数列表（仅回测）。用于回测初始化，不是交易持久化。 |
| 4) 账户/订单侧重建 | 交易 | get_orders / get_all_orders / get_trades / get_positions / get_all_positions 从券商侧重建当日订单与持仓；跨日由方案1的 g 恢复。适合崩溃后对账恢复。 |
| 5) 历史交割/资金核对 | 交易（盘前/盘后） | get_deliver（历史交割单）、get_fundjour（历史资金流水）仅在 before_trading_start / after_trading_end 可调，仅普通账户且按柜台支持；get_trades_file 获取对账数据文件（仅回测，路径有非法字符限制）。 |
| 6) 外部文件/HTTP（非常规） | 极少数券商 | 若券商开放外网，可 HTTP 读写自定义文件；否则不作为通用缓存。 |

> 结论：托管内做“跨日 + 跨重启”状态，最稳妥的是“方案1（g 自动持久化）为主 + 方案2（pickle 到 get_research_path）为辅”，再用方案4做对账兜底。

## 二、“次日三态预期”能否完整实现

axquant 预期三态链路（T日开仓理由 → T日盘后复盘档案 → T+1竞价确认 → T+1盘中确认 → 卖出分支）：
- 超预期 = 竞价涨幅高于上一日、盘中 2 根 1m K 线突破开盘价 1% 以上，或首个 1m 内直接涨停；
- 不及预期 = 绿开或跌破 VWAP 并反绿；
- 一字板按次日封单量相对 T 日是否增大 20% 区分超预期/符合预期；一字板中间开板即降级。

### 可完整实现的部分
| 环节 | Ptrade 对等实现 |
| --- | --- |
| 状态机（T/T+1、pending/meet/miss/confirmed/degraded）与卖出分支 | handle_data/before_after_trading_end/run_daily 内状态机；P2E（expectation_miss）编入卖出链，命中 CLEAR_STOCK |
| 跨日状态与档案 | 方案1 g 自动持久化 + 方案2 pickle 写/读档案（T日盘后 after_trading_end 写，T+1 before_trading_start / run_daily 读） |
| T+1 竞价确认（09:15-09:25） | run_daily time 可设 09:1x/09:2x（交易场景支持 00:00-23:59 盘前时段）；竞价/开盘涨幅用 get_trend_data（集中竞价）+ 开盘价 |
| 盘中超预期/不及预期判定 | get_history(period='1m') 取 2 根 1m 突破；实时价 vs 前收/VWAP 判反绿与绿开；VWAP 由成交量额累加 |
| 涨停判断与开板降级 | check_limit 涨跌停；开板用档位/实时价 vs 涨停价近似 |
| 卖出触发节奏与优先级 | run_interval（09:30-09:45@3s、09:45-10:00@5s、之后10s，interval_timer_ranges 限定时段）+ 卖出优先级链 |

### 无法按 axquant 原口径完全复刻的缺口
| 缺口 | 原因 | 对策 |
| --- | --- | --- |
| 一字板“封单量增大 20%” | Ptrade 无标准“封单量”接口（仅有 get_gear_price 档位量） | 用档位量近似“封单强度”，或由券商扩展接口提供封单量；严格“增大20%”无法精确实现 |
| 2 秒刷新节奏 | Ptrade 股票 run_interval 最小 3 秒 | 09:30-09:45 段从 2s 放宽到 3s，整体判定节拍略粗 |
| LLM/复盘派生字段 | role_detail、junk_follower、expectation_weight、board_role_evidence、sell_policy_hint 由 axquant 盘后复盘（write_review + 大模型）生成，托管内无 LLM/外网 | 用简单规则替代（板块角色、连板高度、涨停次数、封单近似等），或外置生成后经“券商开外网”注入（非常规） |

### 结论
- “预期三态”的**状态机、竞价/盘中规则判定、跨日持久化、卖出分支**可以在 Ptrade 托管内较完整实现。
- 三处**不能按 axquant 原口径完整复刻**：① 一字板封单量精确对比（需券商接口或近似）；② LLM 派生字段（需简化/外置）；③ 2 秒节奏（降为 3 秒）。
- 若“完整”仅指规则口径与链路，则**可实现**；若要求与 axquant 的 LLM 透视与封单口径完全一致，则**不能完整实现**，需近似或混合架构。

---
配合文档：docs/02（持久化）、docs/05（定时/托管）、docs/06（数据接口）、docs/16（axquant 迁移评估）。
