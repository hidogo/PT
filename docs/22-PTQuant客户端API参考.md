# PTQuant 客户端 API 参考（外部桥接口）

> 来源：D:/gjzq/ptrade/Libs/Python/api/PTQuantAPI.pdf（国金 PTrade 客户端内置文档）。
> 定位：PTrade **客户端侧 Python 策略工具 API**，与「托管策略沙盒」的 initialize/handle_data 是两套接口。可作为 axquant 等外部程序连接 PTrade 的下单/查持仓/订阅行情通道。

## 1. 运行依赖

- PTQuant 依赖 **Python3.7**。
- 使用前须先启动 PTrade 客户端（本地）并连接服务端。
- 客户端版本：PTrade1.0-ClientV202308.00.00。
- 入口：PTradeQuantApi.py + PTradeQuantCore.cp37-win_amd64.pyd；get_engine() 负责建连（断线 60s 重试）。

## 2. 账户查询接口

| 函数 | 参数 | 返回 |
| --- | --- | --- |
| get_portfolio() | 无 | Portfolio 对象或 None（None=查询失败） |
| get_order(order_id) | order_id：委托id | 含单个 Order 的 list；无数据返回空 list |
| get_orders(security=None) | security：代码（可选） | 当日全部委托，list[Order]；无数据空 list |
| get_trades(order_id=None) | 委托编号（可选） | dict，key=委托编号，value=list[[成交编号,委托编号,标的代码,买卖类型,成交数量(买正卖负),成交价格,成交金额,成交时间]]；无数据空 dict |
| get_position(security) | 标的代码 | dict，key=代码，value=Position；无数据空 dict |
| get_positions() | 无 | 全部持仓 dict，key=代码，value=Position |

## 3. 操作接口（订阅 / 下单 / 撤单）

| 函数 | 参数 | 返回 |
| --- | --- | --- |
| stocks_subscribe(security_list) | 单标 str / 多标 list | None；订阅行情快照（注意见下"数据接口"备注） |
| stocks_unsubscribe(security_list) | 同上 | None；取消订阅 |
| order(security, amount, limit_price) | security 代码；amount 正买负卖(int)；limit_price 限价(float) | 委托编号 str，形如 '31&2'（31=柜台委托号，2=市场编号：上海1/深圳2）。同步 |
| async_order(security, amount, limit_price) | 同上 | 委托序号 str，如 '100001'（服务端虚拟编号）；配合 on_order_async_response 得到对应柜台委托号'31&2' |
| cancel_order(order_id) | 柜台委托编号 str | 撤单委托编号 str（同步） |
| cancel_async_order(order_id) | 柜台委托编号 str（不能传异步委托序号） | 撤单委托序号 str |

## 4. 数据接口

### 4.1 获取标的快照 get_snapshot(security_list)

返回 dict：key=标的代码，value=dict，含字段：

| 字段 | 含义 | 字段 | 含义 |
| --- | --- | --- | --- |
| offer_grp | 委卖档位（价格/手/笔） | bid_grp | 委买档位（价格/手/笔） |
| business_amount | 总成交量(int) | business_amount_in | 内盘成交量(int) |
| business_amount_out | 外盘成交量(int) | business_balance | 总成交额(float) |
| business_count | 成交笔数(int) | circulation_amount | 流通股本(int) |
| current_amount | 现手，单位手(int) | down_px | 跌停价(float) |
| entrust_diff | 委差(float) | entrust_rate | 委比%(float) |
| high_px | 最高价 | low_px | 最低价 |
| open_px | 今开 | preclose_px | 昨收 |
| last_px | 最新价 | wavg_px | 加权均价(盘中均价) |
| px_change_rate | 涨跌幅 | vol_ratio | 量比 |
| turnover_ratio | 换手率% | trade_mins | 交易分钟数(int) |
| trade_status | 交易状态(str) | up_px | 涨停价(float) |
| hsTimeStamp | 时间戳(float) | pe_rate | 动态市盈率 |
| pb_rate | 市净率 | total_bidqty / total_offerqty | 委买/委卖量(手) |

备注：快照是**服务端主推到进程**，get_snapshot 从内存变量读。订阅后到收到主推有延迟（一般 >3s）；建议盘前/分钟级逻辑做订阅，tick 级只取数；一进程订阅、另一进程接收也有延迟。

### 4.2 获取当日分钟 K 线 get_history(count, frequency='1m', field=..., security_list=...)

- count：K线根数(int)；frequency：仅支持 '1m'；field：open/high/low/close/volume/money/preclose。
- 返回 dict：key=代码，value=df（index=时间，columns=字段）；超过当日最大数量时仅返回当日最大数量。

## 5. 回调注册

| 注册函数 | 回调 | 说明 |
| --- | --- | --- |
| register_response_function(func) | on_order_response(res) | 委托回报主推，dict：business_amount(成交数量)、order_id、order_time、entrust_prop(委托类型)、status(委托状态)、price、entrust_no(委托编号)、error_info、amount(委托数量)、stock_code、entrust_type(委托类型)。异步委托回报偶现重复主推，用 business_amount 过滤 |
| （异步） | on_order_async_response(res) | dict：key=异步委托序号，value=柜台委托编号，如 {'100001':'31&2'} |
| （异步） | on_async_error_response(res) | dict：key=异步委托/撤单序号，value=错误信息，如 {'100019':{362201:'委托状态错误不能撤单…'}} |

entrust_prop 取值：0 买卖 / 1 配股 / 3 申购 / 7 转股 / 9 股息 / N ETF申赎 / Q 对手方最优 / R 最优五档即时成交剩余转限价 / S 本方最优 / T 即时成交剩余撤销 / U 最优五档即时成交剩余撤销 / b 定价 / c 确认 / d 限价。
entrust_type 取值：0 委托 / 2 撤单 / 4 确认 / 6 信用融资 / 7 信用融券 / 9 信用交易。

## 6. 数据结构与数据字典

- Portfolio：cash 资金、positions_value 总市值、portfolio_value 总资产（float）。
- Order：id 委托id、dt 委托时间、limit 委托价格、symbol 代码、amount 委托数量(int)、filled 成交数量(int)、entrust_no 委托编号、status 委托状态(str)。
- Position：symbol 代码、enable_amount 可用数量(int)、amount 持仓数量(int)、last_sale_price 最新价(float)、cost_basis 成本价(float)。
- 标的尾缀：XSHG=上海市场，XSHE=深圳市场。
- 委托状态 status：'0'未报 / '1'待报 / '2'已报 / '3'已报待撤 / '4'部成待撤 / '5'部撤 / '6'已撤 / '7'部成 / '8'已成 / '9'废单 / 'V'已确认。

## 7. 对 axquant 外部旁路的用法建议

- 这是**外部连接通道**：适合把 axquant 跑在自有机器，用 PTradeQuantApi 对 Ptrade 做「持仓/资金查询、限价下单、撤单、订阅行情快照、取 1m K 线、注册委托回报」。
- 快照延迟一般 >3s、分钟 K 仅 1m → 高频打板用该通道不理想；更适合做**外置决策 + 低频执行**（竞价/日级/持仓管理）。
- 与策略沙盒 API（initialize/handle_data，docs/02–10）职责不同：托管沙盒在服务器内跑规则；PTQuant 是外部侧对交易账户的驱动接口。
- 前提：PTrade 客户端本机登录并连接服务端（get_engine 断线 60s 重连）。

来源：D:/gjzq/ptrade/.../PTQuantAPI.pdf。配套：docs/16、docs/18、docs/19、docs/21。


> 2026-10-19 验证补充：PTQuant 无 L2 逐笔订阅接口（PTradeQuantApi.py 全方法清单 + PTQuantAPI.pdf 均无）；stocks_subscribe 仅快照且延迟>3s。完整验证矩阵见 docs/37。
