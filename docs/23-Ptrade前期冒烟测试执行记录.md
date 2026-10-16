# Ptrade 前期必要测试执行记录（首轮冒烟）

> 环境：国金 PTrade 托管-模拟盘 · 主策略单文件回调 · 云端服务端 Py3.11.4
> 运行：2026-10-15 20:44 · 盘后吊起 · 只读（DO_ORDER=False，无任何真实委托）

## 一、体检结果总表

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 生命周期 initialize/before_trading_start | OK | 盘后吊起即执行探针，无需等盘中 bar |
| context.portfolio.cash（可用资金） | OK 15773.12 | Ptrade 正确字段为 cash（非聚宽 available_cash） |
| context.portfolio.portfolio_value（总资产） | OK 17454.12 | |
| get_positions（持仓） | OK 3 只 601188/603258/603528 | 含 enable_amount/cost_basis 等 |
| get_history(1d) | OK 5 日收盘 | |
| get_price(1m) | OK | 20:53 复测通过，正确返回最近分钟 OHLC；本版签名无 rsp_type，已修 |
| get_snapshot | OK 全字段 | 含 business_count/business_amount（逐笔相关） |
| get_stock_name / get_stock_info / get_stock_status | OK | 恒生电子 600570.SS |
| get_stock_blocks | OK | 概念/地域/证监会行业等大量板块 |
| get_index_stocks | OK | 可拉指数成分 |
| get_fundamentals | OK | 资产负债表 total_assets 等 |
| check_limit | OK 0 | 非涨停 |
| 持久化 persistence(pickle) | OK | get_research_path() 写读正常 |
| 结果文件 | OK | /home/fly/notebook/precheck_result_2026-10-15.txt |

## 二、L2 重要发现（与 docs/21 的默认假设不同）

- get_gear_price：返回 十档 bid_grp/offer_grp（1..10），结构完整；盘后档位全 0。
- get_individual_transaction（逐笔成交）：返回真实逐笔数据（盘后仍能回放当日 15:00 前后逐笔）。
- get_individual_entrust（逐笔委托）：同样返回真实逐笔（含 business_direction/trans_kind）。
- 结论：该国金账户 Level2 实际可用。对原策略（封单量对比/逐笔/打板量能）在托管内的复刻是重大利好（见 docs/16 原判定可据此上调 L2 类逻辑可行性评级）。
- 注意：盘后档位（数量/笔数）为 0、接口在盘后仅回放当日数据；盘中（tick）才是实时。

## 三、已修复项

- 策略与研究脚本中 get_price 误传 rsp_type，已改为 get_price(s, start_date=None, end_date=None, count=5, frequency="1m")，两脚本已更新且通过 Py3.7 编译。

## 四、遗留待验证

1. 跨文件 import 自建 .py 模块是否可用（见 mylib 探针），不可用则需部署前打平单文件。
2. 盘中 tick 档位非零值、逐笔实时值（交易时段复测一次）。
3. 长期：研究页无运行按钮、上传裸 .py 被 BadZipFile（QTV 要求 zip）、quant_server_id 为空 → 归到券商量化/研究服务；不影响托管-模拟盘主链路。

## 五、下一步

按 docs/16「高可靠」买卖子集（竞价/低吸/止损止盈/分数/预期三态规则段）迁移到 strategies/，分批在模拟盘复测。

> 2026-10-15 20:53 复测：get_price 已正常，**十八项全部通过**。

## 六、两则可复用陷阱（国金实测）
- run_daily：注册任加 context 首参、回调单参 func(context)；回测分钟 time 限 09:31~11:30 / 13:00~15:00。
- log.info/warn/error：不做 % 替换，先拼成单字符串传入。
