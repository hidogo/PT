<!-- 来源：ptrade.wiki PTrade API文档（见 reference/ptrade-wiki-API参考.md）；字段以官方最新版本为准。 -->
<!-- 返回：见 README.md 文档索引 -->

### 交易相关函数

注意：代码精度位为3位小数的类型(后台已保护为3位)，如ETF、国债；代码精度为2位小数类型，需要在传参时限制价格参数的精度，如股票。

### 股票交易函数

#### order-按数量买卖

```
order(security, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于买卖指定数量为amount的股票，同时支持国债逆回购

注意事项：

- 支持交易场景的逆回购交易。委托方向为卖出(amount必须为负数)，逆回购最小申购金额为1000元(10张)，因此本接口amount入参应大于等于10(10张)，否则会导致委托失败。

- 回测场景，amount有最小下单数量校验，股票、ETF、LOF：100股，可转债：10张；交易场景接口不做amount校验，直接报柜台。

- 交易场景如果limit_price字段不入参，系统会默认用行情快照数据最新价报单，假如行情快照获取失败会导致委托失败，系统会在日志中增加提醒。

- 由于下述原因，回测中实际买入或者卖出的股票数量有时候可能与委托设置的不一样，针对上述内容调整，系统会在日志中增加警告信息：

- 根据委托买入数量与价格经计算后的资金数量，大于当前可用资金。

- 委托卖出数量大于当前可用持仓数量。

- 每次交易股票时取整100股，交易可转债时取整10张，但是卖出所有股票时不受此限制。

- 股票停牌、股票未上市或者退市、股票不存在。

- 回测中每天结束时会取消所有未完成交易。

##### 参数

security: 股票代码(str)；

amount: 交易数量，正数表示买入，负数表示卖出(int)；

limit_price：买卖限价(float)；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['600570.SS', '000001.SZ']
    set_universe(g.security)

def handle_data(context, data):
    #以系统最新价委托
    order('600570.SS', 100)
    # 逆回购1000元
    order('131810.SZ', -10)
    #以39块价格下一个限价单
    order('600570.SS', 100, limit_price=39)
```

#### order_target - 指定目标数量买卖

```
order_target(security, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于买卖股票，直到股票最终数量达到指定的amount

注意事项：

- 该函数不支持逆回购交易。

- 该函数在委托股票时取整100股，委托可转债时取整10张。

- 交易场景如果limit_price字段不入参，系统会默认用行情快照数据最新价报单，假如行情快照获取失败会导致委托失败，系统会在日志中增加提醒。

- 该接口的使用有场景限制，回测可以正常使用，交易谨慎使用。回测场景下撮合是引擎计算的，因此成交之后持仓信息的更新是瞬时的，但交易场景下信息的更新依赖于柜台数据的返回，无法做到瞬时同步，可能造成重复下单。具体原因如下：

- 柜台返回持仓数据体现当日变化(由柜台配置决定)：交易场景中持仓信息同步有时滞，一般在6秒左右，假如在这6秒之内连续下单两笔或更多order_target委托，由于持仓数量不会瞬时更新，会造成重复下单。

- 柜台返回持仓数据体现当日变化(由柜台配置决定)：第一笔委托未完全成交，如果不对第一笔做撤单再次order_target相同的委托目标数量，引擎不会计算包括在途的总委托数量，也会造成重复下单。

- 柜台返回持仓数据不体现当日变化(由柜台配置决定)：这种情况下持仓数量只会一天同步一次，必然会造成重复下单。

- 针对以上几种情况，假如要在交易场景使用该接口，首先要确定券商柜台的配置，是否实时更新持仓情况，其次需要增加订单和持仓同步的管理，来配合order_target使用。

##### 参数

security: 股票代码(str)；

amount: 期望的最终数量(int)；

limit_price：买卖限价(float)；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['600570.SS', '000001.SZ']
    set_universe(g.security)

def handle_data(context, data):
    #买卖恒生电子股票数量到100股
    order_target('600570.SS', 100)
    #卖出恒生电子所有股票
    if data['600570.SS']['close'] > 39:
        order_target('600570.SS', 0)
```

#### order_value - 指定目标价值买卖

```
order_value(security, value, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于买卖指定价值为value的股票

注意事项：

- 该函数不支持逆回购交易。

- 该函数在委托股票时取整100股，委托可转债时取整10张。

- 交易场景如果limit_price字段不入参，系统会默认用行情快照数据最新价报单，假如行情快照获取失败会导致委托失败，系统会在日志中增加提醒。

##### 参数

security：股票代码(str)；

value：股票价值(float)

limit_price：买卖限价(float)

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['600570.SS', '000001.SZ']
    set_universe(g.security)

def handle_data(context, data):
    #买入价值为10000元的恒生电子股票
    order_value('600570.SS', 10000)

    if data['600570.SS']['close'] > 39:
        #卖出价值为10000元的恒生电子股票
        order_value('600570.SS', -10000)
```

#### order_target_value - 指定持仓市值买卖

```
order_target_value(security, value, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于调整股票持仓市值到value价值

注意事项：

- 该函数不支持逆回购交易。

- 该函数在委托股票时取整100股，委托可转债时取整10张。

- 交易场景如果limit_price字段不入参，系统会默认用行情快照数据最新价报单，假如行情快照获取失败会导致委托失败， 系统会在日志中增加提醒。

- 该接口的使用有场景限制，回测可以正常使用，交易谨慎使用。回测场景下撮合是引擎计算的，因此成交之后持仓信息的更新是瞬时的，但交易场景下信息的更新依赖于柜台数据的返回，无法做到瞬时同步，可能造成重复下单。具体原因如下：

- 柜台返回持仓数据体现当日变化(由柜台配置决定)：交易场景中持仓信息同步有时滞，一般在6秒左右，假如在这6秒之内连续下单两笔或更多order_target_value委托，由于持仓市值不会瞬时更新，会造成重复下单。

- 柜台返回持仓数据体现当日变化(由柜台配置决定)：第一笔委托未完全成交，如果不对第一笔做撤单再次order_target_value相同的委托目标金额，引擎不会计算包括在途的总委托数量，也会造成重复下单。

- 柜台返回持仓数据不体现当日变化(由柜台配置决定)：这种情况下持仓金额只会一天同步一次，必然会造成重复下单。

针对以上几种情况，假如要在交易场景使用该接口，首先要确定券商柜台的配置，是否实时更新持仓情况，其次需要增加订单和持仓同步的管理，来配合order_target_value使用。

##### 参数

security: 股票代码(str)；

value: 期望的股票最终价值(float)；

limit_price：买卖限价(float)；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['600570.SS', '000001.SZ']
    set_universe(g.security)

def handle_data(context, data):
    #买卖股票到指定价值
    order_target_value('600570.SS', 10000)

    #卖出当前所有恒生电子的股票
    if data['600570.SS']['close'] > 39:
        order_target_value('600570.SS', 0)
```

#### order_market - 按市价进行委托

```
order_market(security, amount, market_type, limit_price=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于使用多种市价类型进行委托

注意事项：

- 支持逆回购交易。委托方向为卖出(amount必须为负数)，逆回购最小申购金额为1000元(10张)，因此本接口amount入参应大于等于10(10张)，否则会导致委托失败。

- 不支持可转债交易。

- 该函数中market_type是必传字段，如不传入参数会出现报错。

- 该函数委托上证股票时limit_price是必传字段，如不传入参数会出现报错。

##### 参数

security：股票代码(str)；

amount：交易数量(int)，正数表示买入，负数表示卖出；

market_type： 市价委托类型 (int)，上证股票支持参数0、1、2、4，深证股票支持参数0、2、3、4、5，必传参数；

limit_price：保护限价(float)，委托上证股票时必传参数；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 以35保护限价按对手方最优价格买入100股
        order_market(g.security, 100, 0, 35)
        # 以35保护限价按最优五档即时成交剩余转限价买入100股
        order_market(g.security, 100, 1, 35)
        # 以35保护限价按本方最优价格买入100股
        order_market(g.security, 100, 2, 35)
        # 以35保护限价按最优五档即时成交剩余撤销买入100股
        order_market(g.security, 100, 4, 35)

        # 按对手方最优价格买入100股
        order_market("000001.SZ", 100, 0)
        # 按本方最优价格买入100股
        order_market("000001.SZ", 100, 2)
        # 按即时成交剩余撤销买入100股
        order_market("000001.SZ", 100, 3)
        # 按最优五档即时成交剩余撤销买入100股
        order_market("000001.SZ", 100, 4)
        # 按全额成交或撤单买入100股
        order_market("000001.SZ", 100, 5)
        g.flag = True
```

#### ipo_stocks_order - 新股一键申购

```
ipo_stocks_order(submarket_type=None, black_stocks=None)
```

##### 使用场景

该函数仅在交易模块可用，对接jz_ufx不支持该函数

##### 接口说明

该接口用于一键申购当日全部新股

注意事项：

- 申购黑名单的股票代码必须为申购代码，代码可以是6位数(不带尾缀)，也可以带尾缀入参,比如：black_stocks='787001'或black_stocks='787001.SS'。

##### 参数

submarket_type： 申购代码所属市场 ，不传时默认申购全部新股(int)；

black_stocks：黑名单股票，可以是单个股票或者股票列表，传入的黑名单股票将不做申购，不传时默认申购全部新股(str/list)；

##### 返回

返回dict类型，包含委托代码、委托编号、委托状态(委托失败为0，委托成功为1)、委托数量等信息(dict[str:dict[str:str,str:int,str:float],...])

```
{'732116.SS': {'entrust_no': '205001', 'entrust_status': 1, 'redemption_amount': 1000}, '732100.SS': {'entrust_no': '205002', 'entrust_status': 1, 'redemption_amount': 2000}}
                            
```

##### 示例

```
import time
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)
    g.flag = False

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 上证普通代码
        log.info("申购上证普通代码：")
        ipo_stocks_order(submarket_type=0)
        time.sleep(5)
        # 上证科创板代码
        log.info("申购上证科创板代码：")
        ipo_stocks_order(submarket_type=1)
        time.sleep(5)
        # 深证普通代码
        log.info("申购深证普通代码：")
        ipo_stocks_order(submarket_type=2)
        time.sleep(5)
        # 深证创业板代码
        log.info("申购深证创业板代码：")
        ipo_stocks_order(submarket_type=3)
        time.sleep(5)
        # 可转债代码
        log.info("申购可转债代码：")
        ipo_stocks_order(submarket_type=4)
        time.sleep(5)
        g.flag = True
```

#### after_trading_order - 盘后固定价委托(股票)

```
after_trading_order(security, amount, entrust_price)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在股票交易模块可用，对接ATP柜台不支持该函数

##### 接口说明

该接口用于盘后固定价委托申报

注意事项：

- entrust_price为必传字段。

##### 参数

security: 股票代码(str)；

amount: 交易数量，正数表示买入，负数表示卖出(int)；

entrust_price：买卖限价(float)；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "300001.SZ"
    set_universe(g.security)
    # 15:00-15:30期间使用run_daily进行盘后固定价委托
    run_daily(context, order_test, time="15:15")
    g.flag = False

def order_test(context):
    snapshot = get_snapshot(g.security)
    if snapshot is not None:
        last_px = snapshot[g.security].get("last_px", 0)
        if last_px > 0:
            after_trading_order(g.security, 200, float(last_px))

def handle_data(context, data):
    if not g.flag:
        snapshot = get_snapshot(g.security)
        if snapshot is not None:
            last_px = snapshot[g.security].get("last_px", 0)
            if last_px > 0:
                after_trading_order(g.security, 200, float(last_px))
                g.flag = True
```

#### after_trading_cancel_order - 盘后固定价委托撤单(股票)

```
after_trading_cancel_order(order_param)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在股票交易模块可用，对接ATP柜台不支持该函数

##### 接口说明

该接口用于盘后固定价委托取消订单，根据Order对象或order_id取消订单。

注意事项：

##### 参数

order_param: Order对象 或者order_id(Order/str)

##### 返回

None(NoneType)

##### 示例

```
import time

def initialize(context):
    g.security = "300001.SZ"
    set_universe(g.security)
    # 15:00-15:30期间使用run_daily进行盘后固定价委托、盘后固定价委托撤单
    run_daily(context, order_test, time="15:15")
    g.flag = False

def order_test(context):
    snapshot = get_snapshot(g.security)
    if snapshot is not None:
        last_px = snapshot[g.security].get("last_px", 0)
        if last_px > 0:
            order_id = after_trading_order(g.security, 200, float(last_px))
            time.sleep(5)
            after_trading_cancel_order(order_id)

def handle_data(context, data):
    if not g.flag:
        snapshot = get_snapshot(g.security)
        if snapshot is not None:
            last_px = snapshot[g.security].get("last_px", 0)
            if last_px > 0:
                order_id = after_trading_order(g.security, 200, float(last_px))
                time.sleep(5)
                after_trading_cancel_order(order_id)
                g.flag = True
```

#### etf_basket_order - ETF成分券篮子下单

```
etf_basket_order(etf_code ,amount, price_style=None, position=True, info=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在股票交易模块可用，对接jz_ufx、ATP、云订柜台不支持该函数

##### 接口说明

该接口用于ETF成分券篮子下单。

注意事项：

##### 参数

etf_code : 单支ETF代码，必传参数(str)

amount : 下单篮子份数, 正数表示买入, 负数表示卖出，必传参数(int)

price_style : 设定委托价位，可传入’B1’、’B2’、’B3’、’B4’、’B5’、’S1’、’S2’、’S3’、’S4’、’S5’、’new’，分别为买一~买五、卖一~卖五、最新价，默认为最新价(str)

position : 取值True和False，仅在篮子买入时使用。申购是否使用持仓替代，True为使用，该情况下篮子股票买入时使用已有的持仓部分；False为不使用。默认使用持仓替代(bool)

info : dict类型，成份股信息。key为成分股代码，values为dict类型，包含的成分股信息字段作为key(Mapping[str, Mapping[str, Union[int, float]]]):

- cash_replace_flag -- 设定现金替代标志，1为替代，0为不替代，仅允许替代状态的标的传入有效，否则无效，如不传入info或不传入该字段信息系统默认为成分股不做现金替代

- position_replace_flag -- 设定持仓替代标志，1为替代，0为不替代，如不传入info或不传入该字段信息按position参数的设定进行计算

- limit_price -- 设定委托价格，如不传入info或不传入该字段信息按price_style参数的设定进行计算

##### 返回

创建订单成功，正常返回一个dict类型字段， key为股票代码，values为Order对象的id，失败则返回空dict，如{}(dict[str:str]))

```
{'600010.SS': '34e6733d26c14056b2096cafdec253b2', '600028.SS': '4299f7ad527842dd89f2a04cef48b935', '600030.SS': '1729b80b107d408d882a39814fef667d', '600031.SS': 'c17f28961d1248f0b914c62f2e44cd13', '600036.SS': 'ea7274a4e06349308f552d60181bbec8', '600048.SS': 'bd69c204a653483e975d2914c5fe5705', '600104.SS': 'ac8a890df68c453fb93333e19f58be91', '600111.SS': '9c9c5f604c2d43d396c811189699f072'}
                            
```

##### 示例

```
def initialize(context):
    g.security = get_Ashares()
    set_universe(g.security)

def handle_data(context, data):
    #ETF成分券篮子下单
    etf_basket_order('510050.SS' ,1, price_style='S3',position=True)
    stock_info = {'600000.SS':{'cash_replace_flag':1,'position_replace_flag':1,'limit_price':12}}
    etf_basket_order('510050.SS' ,1, price_style='S2',position=False, info=stock_info)
```

#### etf_purchase_redemption - ETF基金申赎接口

```
etf_purchase_redemption(etf_code,amount,limit_price=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在股票交易模块可用，对接jz_ufx、ATP、云订柜台不支持该函数

##### 接口说明

该接口用于单只ETF基金申赎。

注意事项：

##### 参数

etf_code : 单支ETF代码，必传参数(str)

amount : 基金申赎数量, 正数表示申购, 负数表示赎回(int)

##### 返回

创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '510050.SS'
    set_universe(g.security)

def handle_data(context, data):
    #ETF申购
    etf_purchase_redemption('510050.SS',900000)
    #ETF赎回
    etf_purchase_redemption('510050.SS',-900000,limit_price = 2.9995)
```

### 公共交易函数

#### order_tick - tick行情触发买卖

```
order_tick(sid, amount, priceGear='1', limit_price=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于在tick_data模块中进行买卖股票下单，可设定价格档位进行委托。

注意事项：

- 该函数只能在tick_data模块中使用。

##### 参数

sid：股票代码(str)；

amount：交易数量，正数表示买入，负数表示卖出(int)

priceGear：盘口档位，level1:1~5买档/-1~-5卖档，level2:1~10买档/-1~-10卖档(str)

limit_price：买卖限价，当输入参数中也包含priceGear时，下单价格以limit_price为主(float)；

##### 返回

返回一个委托流水编号(str)

##### 示例

```
import ast
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def tick_data(context,data):
    security = g.security
    current_price = ast.literal_eval(data[security]['tick']['bid_grp'][0])[1][0]
    if current_price > 56 and current_price < 57:
        # 以买一档下单
        order_tick(g.security, -100, "1")
        # 以卖二档下单
        order_tick(g.security, 100, "-2")
        # 以指定价格下单
        order_tick(g.security, 100, limit_price=56.5)

def handle_data(context, data):
    pass
```

#### cancel_order - 撤单

```
cancel_order(order_param)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于取消订单，根据 Order对象 或order_id取消订单。

注意事项：

##### 参数

order_param: Order对象 或者order_id(Order/str)

##### 返回

None(NoneType)

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    _id = order(g.security, 100)

    cancel_order(_id)
    log.info(get_order(_id))
```

#### cancel_order_ex - 撤单

```
cancel_order_ex(order_param)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于取消订单，根据 get_all_orders 返回列表中的单个字典取消订单。

注意事项：

- 该函数仅可撤 get_all_orders 函数返回的可撤状态订单。

- 账户多个交易运行时调用该函数会撤销其他交易产生的订单，可能对其他正在运行的交易策略产生影响。

##### 参数

order_param: get_all_orders 函数返回列表的单个字典(dict)

##### 返回

None(NoneType)

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)
    g.count = 0

def handle_data(context, data):
    if g.count == 0:
        log.info("当日全部订单为：%s" % get_all_orders())
        # 遍历账户当日全部订单，对已报、部成状态订单进行撤单操作
        for _order in get_all_orders():
            if _order['status'] in ['2', '7']:
                cancel_order_ex(_order)
    if g.count == 1:
        # 查看撤单是否成功
        log.info("当日全部订单为：%s" % get_all_orders())
    g.count += 1
```

#### debt_to_stock_order - 债转股委托

```
debt_to_stock_order(security, amount)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于可转债转股操作。

注意事项：

##### 参数

security: 可转债代码(str)

amount: 委托数量(int)

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.count = 0

def handle_data(context, data):
    if g.count == 0:
        # 对持仓内的国贸转债进行转股操作
        debt_to_stock_order("110033.SS", -1000)
        g.count += 1
    # 查看委托状态
    log.info(get_orders())
    g.count += 1
```

#### get_open_orders - 获取未完成订单

```
get_open_orders(security=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于获取当天所有未完成的订单，或按条件获取指定未完成的订单。

注意事项：

- 该接口仅支持获取本策略内的订单

- 未完成的状态(status(str))包括以下类型: '0' -- "未报" '1' -- "待报" '2' -- "已报" '3' -- "已报待撤" '4' -- "部成待撤" '7' -- "部成"

##### 参数

security：标的代码，如'600570.SS'，不传时默认为获取所有未成交订单(str)；

##### 返回

返回一个list，该list中包含多个 Order对象 (list[Order,...])。

```
[<Order {'id': '52e6a3f8a2b7468e92258c52dfcb6d42', 'dt': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'priceGear': 0, 'limit': 34.1, 'symbol': '600570.XSHG', 'amount': 1000, 'created': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'filled': 0, 'status': '2', 'entrust_no': '3596', 'cancel_entrust_no': None}>]
                            
```

##### 示例

```
def initialize(context):
    g.security = ['600570.SS', '000001.SZ']
    set_universe(g.security)

def handle_data(context, data):
    for _sec in g.security:
        _id = order(_sec, 100, limit_price = 30)
    # 当运行周期为分钟则可获取本周期及之前所有未完成的订单
    dict_list = get_open_orders()
    log.info(dict_list)

# 当运行周期为天，可在after_trading_end中调用此函数获取当天未完成的订单
def after_trading_end(context, data):
    dict_list = get_open_orders()
    log.info(dict_list)
```

#### get_order - 获取指定订单

```
get_order(order_id)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于获取指定编号订单。

注意事项：

获取指定编号订单。

##### 参数

order_id：订单编号(str)

##### 返回

返回一个list，该list中只包含一个 Order对象 (list[Order])。

```
[<Order {'id': '52e6a3f8a2b7468e92258c52dfcb6d42', 'dt': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'priceGear': 0, 'limit': 34.1, 'symbol': '600570.XSHG', 'amount': 1000, 'created': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'filled': 0, 'status': '2', 'entrust_no': '3596', 'cancel_entrust_no': None}>]
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    order_id = order(g.security, 100)
    current_order = get_order(order_id)
    log.info(current_order)
```

#### get_orders - 获取全部订单

```
get_orders(security=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于获取策略内所有订单，或按条件获取指定订单。

注意事项：

##### 参数

security：标的代码，如'600570.SS'，不传时默认为获取所有订单(str)；

##### 返回

返回一个list，该list中包含多个 Order对象 (list[Order,...])。

```
[<Order {'id': '52e6a3f8a2b7468e92258c52dfcb6d42', 'dt': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'priceGear': 0, 'limit': 34.1, 'symbol': '600570.XSHG', 'amount': 1000, 'created': datetime.datetime(2025, 2, 21, 11, 25, 1, 229575), 'filled': 0, 'status': '2', 'entrust_no': '3596', 'cancel_entrust_no': None}>]
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    _id = order(g.security, 100)

    order_obj = get_orders()
    log.info(order_obj)
```

#### get_all_orders - 获取账户当日全部订单

```
get_all_orders(security=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该接口用于获取账户当日所有订单(包含非本交易的订单记录)，或按条件获取指定代码的订单。

注意事项：

- 该函数返回账户当日在柜台的全部委托记录，不能查询策略中待报、未报状态的委托。

- 该函数返回的可撤委托仅可通过 cancel_order_ex 函数进行撤单，且非本交易的委托进行撤单仅可通过本函数查询委托状态更新。

- 股票、两融业务返回的amount字段区分正负值，卖出为负数；期货业务返回的amount字段不区分正负值，均为正数。

- 期权业务返回的amount字段不区分正负值，均为正数。

- 港股通业务返回的amount字段区分正负值，卖出为负数。

##### 参数

security：标的代码，如'600570.SS'，不传时默认为获取所有订单(str)；

##### 返回

返回一个list，该list中包含多条订单记录(list[dict, ...])：

股票、两融返回如下：

[{'symbol': , 'entrust_no': , 'amount': , 'entrust_bs': , 'price': , 'status': , 'filled_amount': , 'entrust_time': },
 ...]

期货返回如下：

[{'symbol': , 'entrust_no': , 'amount': , 'entrust_bs': , 'price': , 'status': , 'filled_amount': , 'entrust_time': ,
 'futures_direction': }, ...]

期权返回如下：

[{'symbol': , 'entrust_no': , 'amount': , 'entrust_bs': , 'price': , 'status': , 'filled_amount': , 'entrust_time': ,
 'option_direction': , 'covered_flag': }, ...]

港股通返回如下：

[{'symbol': , 'entrust_no': , 'amount': , 'entrust_bs': , 'price': , 'status': , 'filled_amount': , 'entrust_time': },
 ...]

- symbol： 股票代码(str)

- entrust_no： 委托编号(str)

- amount： 委托数量(int)

- entrust_bs： 委托方向 (int)；

- price： 委托价格(float)

- status： 委托状态 (str)；

- filled_amount： 成交数量(int)

- entrust_time： 委托时间(str)

- futures_direction： 期货开平仓类型，期货专用(str)

- option_direction： 期权开平仓类型, 期权专用(str)

- covered_flag： 备兑标志，期权专用(str)

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取账户当日委托600570代码的全部订单
    log.info('当日委托600570代码的全部订单：%s' % get_all_orders(g.security))
    # 获取账户当日全部订单
    log.info('当日全部订单：%s' % get_all_orders())
```

#### get_trades - 获取当日成交订单

```
get_trades()
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该接口用于获取策略内当日已成交订单详情。

注意事项：

- 为减小对柜台压力，该函数在股票交易模块中同一分钟内多次调用返回当前分钟首次查询的缓存数据。

- 该接口会返回当日截止到当前时间段内的成交数据。

- 一个订单编号会对应一笔或多笔成交记录。

- 不同品种返回字段不同。

- 股票标的代码尾缀为四位，上证为XSHG，深圳为XSHE，如需对应到代码请做代码尾缀兼容。

- 获取国债逆回购成交详情时，成交价格字段实际为回购利率。

##### 参数

##### 返回

返回数据：

一个订单编号一笔成交：{'订单编号': [[]]} (dict{str: list[list[]]})

一个订单编号多笔成交：{'订单编号': [[], [], ...]} (dict{str: list[list[], list[], ...]})

股票返回字段：{'订单编号': [[成交编号, 委托编号, 标的代码, 买卖类型, 成交数量, 成交价格, 成交金额, 成交时间]]}

期货返回字段：{'订单编号': [[成交编号, 委托编号, 标的代码, 买卖类型, 开平仓类型, 成交数量, 成交价格, 成交金额, 成交时间]]}

期权返回字段：{'订单编号': [[成交编号, 委托编号, 标的代码, 买卖类型, 开平仓类型, 成交数量, 成交价格, 成交金额, 成交时间, 备兑标志]]}

港股通返回字段：{'订单编号': [[成交编号, 委托编号, 标的代码, 买卖类型, 成交数量, 成交价格, 成交金额, 成交时间]]}

- 成交编号：str类型

- 委托编号：str类型

- 标的代码：str类型

- 买卖类型：str类型

- 开平仓类型：开仓、平仓、平今仓，仅支持衍生品业务，str类型

- 成交数量：float类型

- 成交价格：float类型

- 成交金额：float类型

- 成交时间：YYYY-mm-dd HH:MM:SS格式，str类型

- 备兑标志：备兑、非备兑，仅支持期权，str类型

示例如下(股票)：

```
{'ba6a80d9746347a99c050b29069807c7': [['5001', '700001', '600570.XSHG', '买', 100000.0, 86.60, 8660000.0, '2021-08-15 09:32:00']]}
```

##### 示例

```
def initialize(context):
    # 初始化策略
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.count = 0

def handle_data(context, data):
    if g.count == 0:
        # 按照回购利率1.76委托国债逆回购
        order("204001.SS", -1000, 1.76)
        g.count += 1
    log.info(get_trades())
```
