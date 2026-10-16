# Ptrade 托管策略开发指南

本文档与本目录下各分类文档构成 Python（PTrade）托管策略开发的速查资料库。
托管策略 = 把策略上传到券商 PTrade 服务器托管运行，关闭客户端 / 断网后策略仍按计划在服务器上自动执行，盘中可用 run_daily / run_interval 做定时与周期触发。

> 各券商内置版本与可开接口略有差异，实盘前请以本平台终端「帮助 / 示例」为准。

## 1. 托管策略的运行形态

PTrade 托管策略本质是一段 Python 脚本，由平台按生命周期回调驱动，并在关键节点自动持久化。

阶段：回测（历史数据验证，日/分钟线）-> 模拟盘（模拟环境验证下单与风控）-> 实盘托管（上传服务器自动运行，客户端可关闭）。

## 2. 开发到上线的流程

1. 新建策略：终端左上角新建策略，选择业务类型（股票/期货/期权等）并命名。
2. 编写策略：至少实现 initialize 与 handle_data 两个函数。详见 docs/02 与 docs/03。
3. 新建回测：设定开始/结束时间、回测资金、基准、频率，保存后运行回测并查看收益曲线与日志。
4. 新建交易：从策略列表选策略建立交易并上线，在交易列表/详情查看资产、持仓、日志。
5. 托管上线：策略部署到服务器后即为托管运行；重启时框架先执行 initialize 再恢复持久化。

运行周期差异：回测日线为每天 15:00，分钟线为每根 K 线结束；交易支持日线/分钟线/tick（最小约 3 秒），tick_data 仅交易环境可用；盘前 before_trading_start、盘中 handle_data / 定时任务、盘后 after_trading_end（15:30）。详见 docs/01。

## 3. 生命周期与入口函数

initialize(context)    必选：策略启动初始化，设置股票池、参数、注册定时任务。
before_trading_start(context, data)  可选：每日盘前运行一次。
handle_data(context, data)  必选：主循环，读持仓与行情后决策下单。
after_trading_end(context, data)  可选：盘后 15:30 收尾、统计、落盘。
tick_data(context, data)  可选：tick 级快照/逐笔触发，仅交易。
on_order_response(context, order)  可选：委托主推事件。
on_trade_response(context, trade)  可选：成交主推事件。

入门范例见 examples/01；定时任务范例见 examples/02 与 examples/03。

## 4. 定时 / 周期 —— 托管最常用

定时任务需在 initialize 中注册，交易场景均可用：
- run_daily(context, func, time="09:31")：按日周期。time 指定触发时刻，交易场景可设 00:00~23:59；回测分钟级限定 09:31~11:30 与 13:00~15:00，回测日线固定 15:00。
- run_interval(context, func, seconds=10, interval_timer_ranges="09:15-11:30,13:00-15:00")：按秒周期。最小间隔：期货 1 秒、股票等其他 3 秒。

重要约束：
- run_daily 与 run_interval 只能各在 initialize 中注册，且累计不超过 5 个，否则部分任务会因线程堵塞不触发。
- 交易重启后需配合持久化保证状态连贯。
详见 docs/05。

> 国金实测注意（2026-10-15，托管-模拟盘/回测）：
> - run_daily 回调必须定义为单参（func(context)），注册时任一律 run_daily(context, func, time=...)；回测分钟级 time 限定 09:31~11:30 与 13:00~15:00（09:25 之类会不触发）。
> - 本平台 log.info/warn/error 不做 % 占位符替换，务必先拼成单个字符串再传入（log.info("x=%s" % v)），否则日志原样打印 %s。
> 详见 docs/05、docs/23。


## 5. 核心 API 速查

设置（docs/04）：set_universe 股票池、set_benchmark 基准、set_commission 佣金、set_slippage / set_fixed_slippage 滑点、set_volume_ratio 成交比例、set_yesterday_position 底仓、set_parameters 参数、set_email_info 邮件。

数据（docs/06）：
- 行情：get_history、get_price、get_snapshot、get_gear_price、get_trend_data、get_individual_entrust。
- 证券：get_stock_name、get_stock_info、get_stock_status、get_stock_blocks、get_index_stocks、get_industry_stocks、get_fundamentals、前/后复权。
- 持仓资金：get_position / get_positions / get_all_positions、context.portfolio、get_orders / get_trades。
- 交易日：get_trading_day、get_trade_days、get_all_trades_days。

下单（docs/07）：order 按数量、order_target 目标数量、order_value 目标市值、order_target_value、order_market 市价、cancel_order 撤单，以及新股申购、ETF 篮子等。
下单前按标的小数位校验价格：股票 2 位、可转债/ETF/LOF 3 位、股指期货 1 位、期权 4 位。

其他品种（docs/08）：两融、期货、期权、港股通专用函数。
对象与数据字典（docs/10）：g 全局、Context、BarData、Portfolio、Position、Order，以及各委托/成交状态枚举。
技术指标（docs/09）：get_MACD、get_KDJ、get_RSI、get_CCI。

## 6. 托管策略必须注意

- 股票池约束：所有交易只能针对 set_universe 设定的池内标的。
- 持久化：框架在 before_trading_start / handle_data / after_trading_end 后自动保存；g 中以 __ 开头的私有变量不持久化，不可序列化对象（IO、类实例）不保存。需跨重启保持状态时可用 pickle 存到 get_research_path()。
- 异常处理：托管中数据缺失等异常会终止策略，关键逻辑务必 try/except 包裹并记日志。
- 线程限制：定时任务不超过 5 个；run_interval 遵循 1 秒 / 3 秒最小间隔。
- 限价小数位：不同标的小数位不同，限价单需先对价格取整到对应精度。
- 模拟盘先行：实盘需券商开通对应业务权限，先模拟验证再上实盘。

## 7. 下一步工作建议

1. 通读 docs/01、docs/02、docs/03 建立整体认知。
2. 用 examples/ 下三份范例在模拟盘跑通「编写 - 回测 - 模拟 - 托管」链路。
3. 确定策略方向后把脚本放入 strategies/，按其中 README 组织。
4. 数据 / 财务 / 指数见 docs/15，可用三方库见 docs/14。

---
完整文档索引见根目录 README.md。
