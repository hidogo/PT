<!-- 来源：ptrade.wiki PTrade API文档（见 reference/ptrade-wiki-API参考.md）；字段以官方最新版本为准。 -->
<!-- 返回：见 README.md 文档索引 -->

### 计算函数

### 技术指标计算函数

#### get_MACD - 异同移动平均线

```
get_MACD(close, short=12, long=26, m=9)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

获取异同移动平均线MACD指标的计算结果

注意事项：

##### 参数

close：价格的时间序列数据, numpy.ndarray类型；

short: 短周期, int类型；

long: 长周期, int类型；

m: 移动平均线的周期, int类型；

##### 返回

MACD指标dif值的时间序列, numpy.ndarray类型

MACD指标dea值的时间序列, numpy.ndarray类型

MACD指标macd值的时间序列, numpy.ndarray类型

##### 示例

```
def initialize(context):
    g.security = "600570.XSHG"
    set_universe(g.security)

def handle_data(context, data):
    h = get_history(100, '1d', ['close','high','low'], security_list=g.security)
    close_data = h['close'].values
    macdDIF_data, macdDEA_data, macd_data = get_MACD(close_data, 12, 26, 9)
    dif = macdDIF_data[-1]
    dea = macdDEA_data[-1]
    macd = macd_data[-1]
```

#### get_KDJ - 随机指标

```
get_KDJ(high, low, close, n=9, m1=3, m2=3)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

获取KDJ指标的计算结果，KDJ指标（随机指标）是一种动量指标，主要用于识别金融资产（如股票、期货等）的超买超卖状态、潜在趋势转折点及价格波动强度。它由三条曲线组成：K线（快速线）、D线（慢速线）和J线（方向敏感线），通过价格波动的统计计算反映市场短期动能。

注意事项：

##### 参数

high：最高价的时间序列数据, numpy.ndarray类型；

low：最低价的时间序列数据, numpy.ndarray类型；

close：收盘价的时间序列数据, numpy.ndarray类型；

n: 周期参数，用来计算未成熟随机值（RSV）的周期长度（RSV是计算KDJ的过程变量），决定指标对价格波动的敏感度。周期越短（如N=5），指标反应越灵敏；周期越长（如N=14），信号越平滑但可能滞后。默认为9天, int类型；

m1: K值的平滑周期，对RSV进行指数移动平均（EMA）处理，进一步平滑K值曲线，默认为3天, int类型；

m2: D值的平滑周期，对RSV进行指数移动平均（EMA）处理，进一步平滑D值曲线，默认为3天, int类型；

##### 返回

KDJ指标k值的时间序列, numpy.ndarray类型

KDJ指标d值的时间序列, numpy.ndarray类型

KDJ指标j值的时间序列, numpy.ndarray类型

##### 示例

```
def initialize(context):
    g.security = "600570.XSHG"
    set_universe(g.security)

def handle_data(context, data):
    h = get_history(100, '1d', ['close','high','low'], security_list=g.security)
    high_data = h['high'].values
    low_data = h['low'].values
    close_data = h['close'].values
    k_data, d_data, j_data = get_KDJ(high_data, low_data, close_data, 9, 3, 3)
    k = k_data[-1]
    d = d_data[-1]
    j = j_data[-1]
```

#### get_RSI - 相对强弱指标

```
get_RSI(close, n=6)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

获取相对强弱指标RSI指标的计算结果

注意事项：

##### 参数

close：价格的时间序列数据, numpy.ndarray类型；

n: 周期, int类型；

##### 返回

RSI指标rsi值的时间序列, numpy.ndarray类型

##### 示例

```
def initialize(context):
    g.security = "600570.XSHG"
    set_universe(g.security)

def handle_data(context, data):
    h = get_history(100, '1d', ['close','high','low'], security_list=g.security)
    close_data = h['close'].values
    rsi_data = get_RSI(close_data, 6)
    rsi = rsi_data[-1]
```

#### get_CCI - 顺势指标

```
get_CCI(close, n=14)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

获取顺势指标CCI指标的计算结果

注意事项：

##### 参数

high：最高价的时间序列数据, numpy.ndarray类型；

low：最低价的时间序列数据, numpy.ndarray类型；

close：收盘价的时间序列数据, numpy.ndarray类型；

n: 周期, int类型；

##### 返回

CCI指标cci值的时间序列, numpy.ndarray类型

##### 示例

```
def initialize(context):
    g.security = "600570.XSHG"
    set_universe(g.security)

def handle_data(context, data):
    h = get_history(100, '1d', ['close','high','low'], security_list=g.security)
    high_data = h['high'].values
    low_data = h['low'].values
    close_data = h['close'].values
    cci_data = get_CCI(high_data, low_data, close_data, 14)
    cci = cci_data[-1]
```

### 其他函数

#### log-日志记录

```
log(content)
```

##### 使用场景

该函数仅在回测、交易模块可用。

##### 接口说明

该接口用于打印日志。

支持如下场景的日志记录：

```
log.debug("debug")
log.info("info")
log.warning("warning")
log.error("error")
log.critical("critical")
```

与python的logging模块用法一致

注意事项：

##### 参数

参数可以是字符串、对象等。

##### 返回

None

##### 示例

```
# 打印出一个格式化后的字符串
g.security='600570.SS'
log.info("Selling %s, amount=%s" % (g.security, 10000)) 
```

#### is_trade-业务代码场景判断

```
is_trade()
```

##### 使用场景

该函数仅在回测、交易模块可用。

##### 接口说明

该接口用于提供业务代码执行场景判断依据，明确标识当前业务代码运行场景为回测还是交易。因部分函数仅限回测或交易场景使用，该函数可以协助区分对应场景，以便限制函数可以在一套策略代码同时兼容回测与交易场景。

注意事项：

##### 参数

##### 返回

布尔类型，当前代码在交易中运行返回True，当前代码在回测中运行返回False(bool)。

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    _id = order(g.security, 100)

    if is_trade():
        log.info("当前运行场景：交易")
    else:
        log.info("当前运行场景：回测")
```

#### check_limit - 代码涨跌停状态判断

```
check_limit(security, query_date=None)
```

##### 使用场景

该函数在研究、回测、交易模块可用。

##### 接口说明

该接口用于标识股票的涨跌停情况。

注意事项：

- 入参的query_date仅支持YYYYmmdd格式的传参，当query_date入参为None或传入当日日期时，返回的结果是以实时最新价判断涨跌停状态；当query_date入参为历史交易日期，则均以交易日收盘价判断涨跌停状态。

##### 参数

security：单只股票代码或者多只股票代码组成的列表，必填字段(list[str]/str)；

query_date：查询日期，查询指定日期股票代码的涨跌停状态，回测不传默认是回测当日时间，交易和研究不传默认是执行当日时间，非必填字段(str)；

##### 返回

正常返回一个dict类型数据，包含每只股票代码的涨停状态。多只股票代码查询时其中部分股票代码查询异常则该代码返回既不涨停也不跌停状态0。(dict[str:int])

涨跌停状态说明：

- 2：触板涨停(已经是涨停价格，但还有卖盘)(仅支持交易研究查询当日)；

- 1：涨停；

- 0：既不涨停也不跌停；

- -1：跌停；

- -2：触板跌停(已经是跌停价格，但还有买盘)(仅支持交易研究查询当日)；

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 代码涨跌停状态
    stock_flag = check_limit(g.security)[g.security]
    log.info(stock_flag)
```

#### send_email - 发送邮箱信息

```
send_email(send_email_info, get_email_info, smtp_code, info='', path='', subject='')
```

##### 使用场景

该函数仅在交易模块可用。

##### 接口说明

该接口用于通过QQ邮箱发送邮件内容。

注意事项：

- 该接口需要服务端连通外网，是否开通由所在券商决定。

- 是否允许发送附件(即path参数)，由所在券商的配置管理决定。

- 邮件中接受到的附件为文件名而非附件路径。

##### 参数

send_email_info：发送方的邮箱地址，必填字段，如:50xxx00@qq.com(str)；

get_email_info：接收方的邮箱地址，必填字段，如:[50xxx00@qq.com, 1xxx10@126.com](list[str]/str)；

smtp_code：邮箱的smtp授权码，注意，不是邮箱密码，必填字段(str)；

info：发送内容，选填字段，默认空字符串(str)；

path：附件路径，选填字段，如:get_research_path() + 'stock.csv'，默认空字符串(str)；

subject：邮件主题，默认空字符串(str)；

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    #发送文字信息
    send_email('53xxxxxx7@qq.com', ['53xxxxx7@qq.com', 'Kxxxxn@126.com'], 'phfxxxxxxxxxxcd', info='今天的股票池信息')
```

#### send_qywx - 发送企业微信信息

```
send_qywx(corp_id, secret, agent_id, info='', path='', toparty='', touser= '', totag= '')
```

##### 使用场景

该函数仅在交易模块可用。

##### 接口说明

该接口用于通过企业微信发送内容，使用方法请查看 企业微信功能使用手册 。

注意事项：

- 该接口需要服务端连通外网，是否开通由所在券商决定。

- 是否允许发送文件(即path参数)，由所在券商的配置管理决定。

- 企业微信不能同时发送文字和文件，当同时入参info和path的时候，默认发送文件。

- 企业微信接受到的文件为文件名而非文件路径。

- 2022年6月20日之后创建的应用由于需要配置企业可信ip(企业微信官方升级)导致企业微信功能不可用，该日期之前创建的应用仍可以正常使用。

##### 参数

corp_id：企业ID，必填字段(str)；

secret：企业微信应用的密码，必填字段(str)；

agent_id：企业微信应用的ID，必填字段(str)；

info：发送内容，选填字段，默认空字符串(str)；

path：发送文件，选填字段，如:get_research_path() + 'stock.csv'，默认空字符串(str)；

toparty：发送对象为部门，选填字段，默认空字符串(str)，多个对象之间用 '|' 符号分割；

touser：发送内容为个人，选填字段，默认空字符串(str)，多个对象之间用 '|' 符号分割；

totag：发送内容为分组，选填字段，默认空字符串(str)，多个对象之间用 '|' 符号分割；

注意：toparty、touser、totag如果都不传入，接口默认发送至应用中设定的第一个toparty

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    #发送文字信息
    send_qywx('wwxxxxxxxxxxxxf9', 'hixxxxxxxxxxxxxxxxxxxBX8', '10xxxx3', info='已触发委托买入', toparty='1|2')
```

#### permission_test-权限校验

```
permission_test(account=None, end_date=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于账号和有效期的权限校验，用户可以在接口中入参指定账号和指定有效期截止日，策略运行时会校验运行策略的账户与指定账户是否相符，以及运行当日日期是否超过指定的有效期截止日，任一条件校验失败，接口都会返回False，两者同时校验成功则返回True。校验失败会在策略日志中提示原因。

注意事项：

- 如果需要使用授权模式下载功能，不要在接口中入参，策略编码时候直接调用permission_test()，授权工具会把需要授权的账号和有效期信息放到策略文件中。

- 该函数仅在initialize、before_trading_start、after_trading_end模块中支持调用。

##### 参数

account：授权账号，选填字段，如果不填就代表不需要验证账号(str)；

end_date：授权有效期截止日，选题字段，如果不填就代表不需要验证有效期(str)，日期格式必须为'YYYYmmdd'的8位日期格式，如'20200101'；

##### 返回

布尔类型，校验成功返回True，校验失败返回False(bool)。

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
def handle_data(context, data):
    pass
def after_trading_end(context, data):
    # 需要用授权模式下载功能的情况下不用入参
    flag = permission_test()
    if not flag:
        raise RuntimeError('授权不通过，终止程序，抛出异常')
    # 不需要用授权模式下载功能的情况下通过入参来进行授权校验
    flag = permission_test(account='10110922',end_date='20220101')
    if not flag:
        raise RuntimeError('授权不通过，终止程序，抛出异常')
```

#### create_dir-创建文件路径

```
create_dir(user_path)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

由于PTrade量化引擎禁用了os模块，因此用户无法在策略中通过编写代码实现子目录创建。用户可以通过此接口来创建文件的子目录路径。

注意事项：

- 创建文件的根路径为研究界面根路径。

##### 参数

user_path(str)：待创建目录相对路径，必传字段。

比如user_path='download'，会在研究界面生成download的目录；

比如user_path='download/2022'，会在研究界面生成download/2022的目录；

##### 返回

是否创建成功(True/False)(bool)。

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    # 在研究界面创建600570.SS目录
    create_dir(g.security)
def handle_data(context, data):
    pass
```

#### get_frequency-获取当前业务代码的周期

```
get_frequency()
```

##### 使用场景

该函数在回测、交易模块可用

##### 接口说明

该接口用于返回当前业务代码的周期，如在周期为分钟的情况下执行回测或交易，该函数返回minute；在周期为每日的情况下执行回测或交易，该函数返回daily。

注意事项：

##### 参数

##### 返回

周期为分钟返回minute，周期为每日返回daily(str)

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    log.info(get_frequency())
def handle_data(context, data):
    pass
```

#### get_business_type - 获取当前策略的业务类型

```
get_business_type()
```

##### 使用场景

该函数在回测、交易模块可用

##### 接口说明

该接口用于返回当前策略的业务类型。

注意事项：

##### 参数

##### 返回

策略业务类型(str)：

- stock -- 股票

- rzrq -- 融资融券

- future -- 期货

- option -- 期权

- hks -- 港股通

##### 示例

```
def initialize(context):
    # 初始化策略
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False
    g.business_type = get_business_type()
    log.info("当前策略的业务类型为：%s" % g.business_type)

def handle_data(context, data):
    if g.flag is False:
        if g.business_type == "stock":
            order("600570.SS", 100)
        elif g.business_type == "future":
            buy_open("IF2309.CCFX", 1, 3816.0)
        g.flag = True
```

#### get_current_kline_count-获取股票业务当前时间的分钟bar数量

```
get_current_kline_count()
```

##### 使用场景

该函数在回测、交易、研究模块可用

##### 接口说明

该接口获取当前时间股票的k线根数。

注意事项：

- 回测中返回回测日当前时间的分钟bar数量。

- 研究中返回最新交易日当前时间的分钟bar数量，非交易日执行均返回0。

- 交易中返回最新交易日当前时间的分钟bar数量。

##### 参数

##### 返回

当前时间的分钟bar数量(int)

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
def handle_data(context, data):
    log.info(get_current_kline_count())
```

#### filter_stock_by_status-过滤指定状态的股票代码

```
filter_stock_by_status(stocks, filter_type=["ST", "HALT", "DELISTING"], query_date=None)
```

##### 使用场景

该函数在回测、交易、研究模块可用

##### 接口说明

该接口用于过滤指定状态的股票代码。

注意事项：

仅支持before_trading_start模块调用

##### 参数

stocks: 例如 ['000001.SZ','000003.SZ']。该字段必须输入。(list[str]/str)；

filter_type: 支持以下四种类型属性的过滤条件，默认为["ST", "HALT", "DELISTING"](str/list)

具体支持输入的字段包括 ：

- 'ST' - 查询是否属于ST股票

- 'HALT' - 查询是否停牌

- 'DELISTING' - 查询是否退市

- 'DELISTING_SORTING' - 查询是否退市整理期(只过滤交易当日数据)

query_date: 格式为YYYYmmdd，默认为None,表示当前日期(回测为回测当前周期，研究与交易则取系统当前时间)(str)；

##### 返回

股票列表（该列表已剔除符合任一指定状态的标的）(list)

##### 示例

```
def initialize(context):
    g.security = ['123002.SZ',"688500.SS","000001.SZ", "603997.SS", '123181.SZ']
    set_universe(g.security)

def before_trading_start(context, data):
    filter_stock = filter_stock_by_status(g.security, ["ST", "HALT", "DELISTING"])
    log.info(filter_stock)

def handle_data(context, data):
    pass
```

#### check_strategy-检查策略内容

```
check_strategy(strategy_content=None, strategy_path=None)
```

##### 使用场景

该函数在研究模块可用

##### 接口说明

该接口用于检查策略内容是否涉及升级过程中变动的API和Python库。

注意事项：

- 每次版本升级后应当将使用的策略内容统一检查一遍。

- strategy_content和strategy_path都传入时仅对strategy_content入参内容进行检查。

- 如果传入strategy_path，需要将对应策略文件上传至研究，且必须是utf-8编码的文本文件。

- 如果日志打印策略内容涉及升级过程变动，需根据告警信息参考API接口说明调整策略内容。

##### 参数

strategy_content: 策略内容(str)。

strategy_path: 策略路径(str)。

##### 返回

策略内容涉及升级过程中变动的API和Python库信息(list)。

##### 接收到的数据如下：

```
{
"api_change_list": [
    "margincash_open",
    "get_history",
    "get_fundamentals",
    "get_etf_info",
    "get_individual_transaction",
    "get_individual_transcation",
    "check_limit",
    "get_price",
    "get_snapshot",
    "on_trade_response",
    "set_parameters",
    "set_yesterday_position",
    "marginsec_open",
    "order_market",
    "margin_trade",
    "get_user_name",
    "debt_to_stock_order",
    "get_instruments",
    "get_margincash_open_amount",
    "get_all_orders",
    "run_interval",
    "get_trades",
    "margincash_close",
    "marginsec_close",
    "get_margin_assert",
    "ipo_stocks_order",
    "get_enslo_security_info",
    "get_hks_unit_amount",
    "get_individual_entrust",
    "get_tick_direction",
    "get_margin_contractreal",
    "get_gear_price",
    "get_stock_status"],
"package_change_list": [
    "walrus",
    "keras",
    "pykalman",
    "arch",
    "cvxopt",
    "pulp"]，
}
                        
```

##### 示例

```
check_strategy(strategy_content="""
import arch
import cvxopt
import keras
import pulp
import pykalman
import tensorflow
import walrus

def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)
    pos={}
    pos["sid"] = "600570.SS"
    pos["amount"] = "1000"
    pos["enable_amount"] = "600"
    pos["cost_basis"] = "55"
    set_yesterday_position([pos])
    run_interval(context, interval_handle, seconds=10)

def interval_handle(context):
    pass

def before_trading_start(context, data):
    get_history(100, frequency="1d", field=["close"], security_list=g.security)
    get_fundamentals(g.security, "balance_statement", "total_assets")
    get_etf_info("510020.SS")
    get_individual_transaction()
    get_individual_transcation()
    check_limit(g.security)
    get_price(g.security, start_date="20150101", end_date="20150131", frequency="1d")
    get_snapshot(g.security)
    set_parameters(holiday_not_do_before="1")
    get_user_name(False)
    get_instruments(g.security)
    get_all_orders()
    get_trades()
    get_margin_assert()
    get_enslo_security_info()
    get_hks_unit_amount("02899.XHKG-SS", "1")
    get_individual_entrust()
    get_tick_direction([g.security])
    get_margin_contractreal()
    get_gear_price(g.security)
    get_stock_status([g.security], "ST")

def on_trade_response(context, trade_list):
    pass

def handle_data(context, data):
    margincash_open(g.security, 100)
    marginsec_open(g.security, 100)
    order_market(g.security, 100, 0, 35)
    margin_trade(g.security, 100)
    get_margincash_open_amount(g.security)
    debt_to_stock_order("110033.SS", -1000)
    margincash_close(g.security, 100)
    marginsec_close(g.security, 100)
    ipo_stocks_order(submarket_type=0)
""")
```

```
check_strategy(strategy_path="./strategy.txt")
```

### fund_transfer-资金调拨

```
fund_transfer(trans_direction, occur_balance, exchange_type="1")
```

#### 使用场景

该函数仅在股票交易模块可用

#### 接口说明

用于UF20柜台与极速柜台、UF20柜台与极速柜台双中心资金调拨。

注意事项：

- 如要使用该函数，需咨询券商当前柜台是否支持。

- 当前仅支持UF20柜台与ATP柜台、UF20柜台与ATP柜台双中心资金调拨。

- 如果是UF20与ATP柜台，exchange_type可不传。

- 如果是UF20与ATP柜台双中心，exchange_type为必传字段。

#### 参数

trans_direction(str)：调拨方向，0为转入极速、1为转出极速。

occur_balance(float)：发生金额(单位：元，最小精度：0.01元)。

exchange_type(str)：交易类别，1为上海、2为深圳。

#### 返回

返回调拨是否成功True/False(bool)。

#### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def before_trading_start(context, data):
    # 转出深A极速柜台100000元
    fund_transfer('1', 100000, exchange_type='2')

def handle_data(context, data):
            pass
```

### market_fund_transfer-市场间资金调拨

```
market_fund_transfer(exchange_type, occur_balance)
```

#### 使用场景

该函数仅在股票交易模块可用

#### 接口说明

用于极速柜台双中心之间资金调拨。

注意事项：

- 如要使用该函数，需咨询券商当前柜台是否支持。

- 当前仅支持ATP柜台双中心之间资金调拨。

#### 参数

exchange_type(str)：交易类别，1为上海、2为深圳。

occur_balance(float)：发生金额(单位：元，最小精度：0.01元)。

#### 返回

返回调拨是否成功True/False(bool)。

#### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def before_trading_start(context, data):
    # 转入沪A极速柜台100000元
    market_fund_transfer('1', 100000)

def handle_data(context, data):
    pass
```
