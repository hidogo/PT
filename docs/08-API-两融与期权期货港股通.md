<!-- 来源：ptrade.wiki PTrade API文档（见 reference/ptrade-wiki-API参考.md）；字段以官方最新版本为准。 -->
<!-- 返回：见 README.md 文档索引 -->

### 融资融券专用函数

### 融资融券交易类函数

#### margin_trade - 担保品买卖

```
margin_trade(security, amount, limit_price=None, market_type=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融回测、两融交易模块可用。

##### 接口说明

该接口用于担保品买卖。

注意事项：

- 限价和市价委托类型都不传时默认取当前最新价进行限价委托，限价和市价委托类型都传入时以limit_price为委托限价进行市价委托。

- 当market_type传入且委托上证股票时，limit_price为保护限价字段，必传字段。

##### 参数

security：股票代码(str)；

amount：交易数量(int)，正数表示买入，负数表示卖出；

limit_price：买卖限价/保护限价(float)；

market_type： 市价委托类型 (int)，上证股票支持参数0、1、2、4，深证股票支持参数0、2、3、4、5；

##### 返回

Order对象中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 以系统最新价委托
        margin_trade(g.security, 100)
        # 以46块价格下一个限价单
        margin_trade(g.security, 100, limit_price=46)

        # 以46保护限价按最优五档即时成交剩余转限价买入100股
        margin_trade(g.security, 100, limit_price=46, market_type=1)
        # 按全额成交或撤单买入100股
        margin_trade("000001.SZ", 100, market_type=5)
        g.flag = True
```

#### margincash_open - 融资买入

```
margincash_open(security, amount, limit_price=None, market_type=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于融资买入。

注意事项：

- 限价和市价委托类型都不传时默认取当前最新价进行限价委托，限价和市价委托类型都传入时以limit_price为委托限价进行市价委托。

- 当market_type传入且委托上证股票时，limit_price为保护限价字段，必传字段。

##### 参数

security：股票代码(str)；

amount：交易数量，输入正数(int)；

limit_price：买卖限价(float)；

market_type： 市价委托类型 (int)，上证股票支持参数0、1、2、4，深证股票支持参数0、2、3、4、5；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

Order对象中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 以系统最新价委托
        margincash_open(g.security, 100)
        # 以46块价格下一个限价单
        margincash_open(g.security, 100, limit_price=46)

        # 以46保护限价按最优五档即时成交剩余转限价买入100股
        margincash_open(g.security, 100, limit_price=46, market_type=1)
        # 按全额成交或撤单买入100股
        margincash_open("000001.SZ", 100, market_type=5)
        g.flag = True
```

#### margincash_close - 卖券还款

```
margincash_close(security, amount, limit_price=None, market_type=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于卖券还款。

注意事项：

- 限价和市价委托类型都不传时默认取当前最新价进行限价委托，限价和市价委托类型都传入时以limit_price为委托限价进行市价委托。

- 当market_type传入且委托上证股票时，limit_price为保护限价字段，必传字段。

##### 参数

security：股票代码(str)；

amount：交易数量，输入正数(int)；

limit_price：买卖限价(float)；

market_type： 市价委托类型 (int)，上证股票支持参数0、1、2、4，深证股票支持参数0、2、3、4、5；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

Order对象中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600570.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 以系统最新价委托
        margincash_close(g.security, 100)
        # 以46块价格下一个限价单
        margincash_close(g.security, 100, limit_price=46)

        # 以46保护限价按最优五档即时成交剩余转限价卖100股还款
        margincash_close(g.security, 100, limit_price=46, market_type=1)
        # 按全额成交或撤单卖100股还款
        margincash_close("000001.SZ", 100, market_type=5)
        g.flag = True
```

#### margincash_direct_refund - 直接还款

```
margincash_direct_refund(value, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于直接还款。

注意事项：

##### 参数

value：还款金额(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取负债总额
    fin_compact_balance = get_margin_asset().get('fin_compact_balance')
    # 还款
    margincash_direct_refund(fin_compact_balance)
```

#### marginsec_open - 融券卖出

```
marginsec_open(security, amount, limit_price=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于融券卖出。

注意事项：

##### 参数

security：股票代码(str)；

amount：交易数量，输入正数(int)；

limit_price：买卖限价(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

Order对象中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '600030.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 融券卖出100股
    marginsec_open(security, 100)
```

#### marginsec_close - 买券还券

```
marginsec_close(security, amount, limit_price=None, market_type=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于买券还券。

注意事项：

- 限价和市价委托类型都不传时默认取当前最新价进行限价委托，限价和市价委托类型都传入时以limit_price为委托限价进行市价委托。

- 当market_type传入且委托上证股票时，limit_price为保护限价字段，必传字段。

##### 参数

security：股票代码(str)；

amount：交易数量，输入正数(int)；

limit_price：买卖限价(float)；

market_type： 市价委托类型 (int)，上证股票支持参数0、1、2、4，深证股票支持参数0、2、3、4、5；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

Order对象中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = "600030.SS"
    set_universe(g.security)

def before_trading_start(context, data):
    g.flag = False

def handle_data(context, data):
    if not g.flag:
        # 以系统最新价委托
        marginsec_close(g.security, 100)
        # 以46块价格下一个限价单
        marginsec_close(g.security, 100, limit_price=46)

        # 以46保护限价按最优五档即时成交剩余转限价买100股还券
        marginsec_close(g.security, 100, limit_price=46, market_type=1)
        # 按全额成交或撤单买100股还券
        marginsec_close("000001.SZ", 100, market_type=5)
        g.flag = True
```

#### marginsec_direct_refund - 直接还券

```
marginsec_direct_refund(security, amount, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于直接还券。

注意事项：

##### 参数

security：股票代码(str)；

amount：交易数量，输入正数(int)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = '600030.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    #买100股
    marginsec_direct_refund(security, 100)
```

### 融资融券查询类函数

#### get_margincash_stocks - 获取融资标的列表

```
get_margincash_stocks()
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用，对接顶点HTS柜台暂不支持该函数。

##### 接口说明

该接口用于获取融资标的。

注意事项：

##### 参数

##### 返回

返回上交所、深交所最近一次披露的的可融资标的列表的list(list[str,...])

```
['000002.SZ', '000519.SZ', '600570.SS', '600519.SS']
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取最新的融资标的列表
    margincash_stocks = get_margincash_stocks()
    log.info(margincash_stocks)
```

#### get_marginsec_stocks - 获取融券标的列表

```
get_marginsec_stocks()
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用，对接顶点HTS柜台暂不支持该函数。

##### 接口说明

该接口用于获取融券标的。

注意事项：

##### 参数

##### 返回

返回上交所、深交所最近一次披露的的可融券标的列表的list(list[str,...])

```
['000002.SZ', '000519.SZ', '600570.SS', '600519.SS']
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取最新的融券标的列表
    marginsec_stocks = get_marginsec_stocks()
    log.info(marginsec_stocks)
```

#### get_margin_contract - 合约查询

```
get_margin_contract(compact_source=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于合约查询。

注意事项：

##### 参数

compact_source：合约来源(int)，0为普通头寸，1为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个DataFrame类型字段，columns为每个合约所包含的信息(相应字段无数据时返回None)，异常返回None(NoneType)

合约包含以下信息：

- open_date:开户日期(str:int)；

- compact_id:合约编号(str:str)；

- stock_code:证券代码(str:str)；

- entrust_no:委托编号(str:str)；

- entrust_price:委托价格(str:float)；

- entrust_amount:委托数量(str:float)；

- business_amount:成交数量(str:float)；

- business_balance:成交金额(str:float)；

- compact_type: 合约类别 (str:str)；

- compact_source:合约来源(str:str)；

- compact_status: 合约状态 (str:str)；

- repaid_interest:已还利息(str:float)；

- repaid_amount:已还数量(str:float)；

- repaid_balance:已还金额(str:float)；

- used_bail_balance:已用保证金(str:float)；

- ret_end_date:归还截止日(str:int)；

- date_clear:清算日期(str:int)；

- fin_income:融资合约盈亏(str:float)；

- slo_income:融券合约盈亏(str:float)；

- total_debit:负债总额(str:float)；

- compact_interest:合约利息金额(str:float)；

- real_compact_interest:日间实时利息金额(str:float)；

- real_compact_balance:日间实时合约金额(str:float)；

- real_compact_amount:日间实时合约数量(str:float)；

```

    open_date   compact_id   stock_code   ...   real_compact_balance   real_compact_amount
0   20250218   20250131234567   600570.SS   ...   103235.31   2800
1   20250219   20250131232321   000002.SZ   ...	  532581.10   72130
2   20250220   20250131232131   600519.SS   ...	  444000.00   300
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取最新合约
    df = get_margin_contract()
    log.info(df)
```

#### get_margin_contractreal - 实时合约流水查询

```
get_margin_contractreal()
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用，对接金证集中，金证快订、云订柜台暂不支持该函数。

##### 接口说明

该接口用于实时合约流水查询。

注意事项：

##### 参数

##### 返回

正常返回一个DataFrame类型字段，columns为每个合约所包含的信息(相应字段无数据时返回None)，异常返回None

实时合约流水包含以下信息：

- init_date:交易日期(str:int)；

- compact_id:合约编号(str:str)；

- client_id:客户编号(str:str)；

- money_type:币种类别(str:str)；

- exchange_type: 交易类别 ，仅包含1和2(str:str)；

- entrust_no:委托编号(str:str)；

- compact_type: 合约类别 (str:str)；

- stock_code:证券代码(str:str)；

- business_flag:业务标志(str:int)；

- occur_balance:发生金额(str:float)；

- post_balance:后资金额(str:float)；

- occur_amount:发生数量(str:float)；

- post_amount:后证券额(str:float)；

- occur_fare:发生费用(str:float)；

- post_fare:后余费用(str:float)；

- occur_interest:发生利息(str:float)；

- post_interest:后余利息(str:float)；

- remark:备注(str:str)；

```

    init_date   compact_id   client_id   ...   post_interest   remark
0   20250218   20250131234567   339200779   ...	  58.2   利息
1   20250219   20250131232321   339200779   ...	  61.3   利息
2   20250220   20250131232131   339200779   ...	  77.1   利息
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取实时流水
    df = get_margin_contractreal()
    log.info(df)
```

#### get_margin_asset - 信用资产查询

```
get_margin_asset()
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于信用资产查询。

注意事项：

##### 参数

##### 返回

正常返回一个dict类型字段，包含所有信用资产信息。异常返回空dict，如{}(dict[str:float,...])

信用资产包含以下信息(相应字段无数据时返回None)：

- assure_asset:担保资产(str:float)；

- total_debit:负债总额(str:float)；

- enable_bail_balance:可用保证金(str:float)；

- assure_enbuy_balance:买担保品可用资金(str:float)；

- fin_enrepaid_balance:现金还款可用资金(str:float)；

- fin_max_quota:融资额度上限(str:float)；

- fin_enable_quota:融资可用额度(str:float)；

- fin_used_quota:融资已用额度(str:float)；

- fin_compact_balance:融资合约金额(str:float)；

- fin_compact_fare:融资合约费用(str:float)；

- fin_compact_interest:融资合约利息(str:float)；

- slo_enable_quota:融券可用额度(str:float)；

- slo_compact_fare:融券合约费用(str:float)；

- slo_compact_interest:融券合约利息(str:float)；

```
{'slo_compact_fare': 0.0, 'assure_asset': 22647586233.8, 'fin_compact_interest': 0.0, 'fin_used_quota': 424057.23, 'slo_compact_interest': 0.59, 'fin_enable_quota': 575942.77, 'assure_enbuy_balance': 15796927.64, 'fin_enrepaid_balance': 15796927.64, 'total_debit': 288878.59, 'fin_compact_fare': 0.0, 'slo_enable_quota': 751589.0, 'enable_bail_balance': 16638502122.05, 'fin_max_quota': 1000000.0, 'fin_compact_balance': 156078.0}
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取信用账户资产信息
    margin_asset = get_margin_asset()
    log.info(margin_asset)
```

#### get_assure_security_list - 担保券查询

```
get_assure_security_list()
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用，对接顶点HTS柜台暂不支持该函数。

##### 接口说明

该接口用于担保券查询。

注意事项：

##### 参数

##### 返回

返回上交所、深交所最近一次披露的担保券列表的list(list[str,...])

```
['000002.SZ', '000519.SZ', '600570.SS', '600519.SS']
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取最新的担保券列表
    assure_security = get_assure_security_list()
    log.info(assure_security)
```

#### get_margincash_open_amount - 融资标的最大可买数量查询

```
get_margincash_open_amount(security, price=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于融资标的最大可买数量查询。

注意事项：

##### 参数

security：股票代码(str)；

price：限定价格(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为最大数量。异常返回空dict，如{}(dict[str:int])

```
{'600570.SS': 1900}
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 查询恒生电子最大可融资买入数量
    margincash_open_dict = get_margincash_open_amount(security)
    if margincash_open_dict is not None:
        log.info(margincash_open_dict.get(security))
```

#### get_margincash_close_amount - 卖券还款标的最大可卖数量查询

```
get_margincash_close_amount(security, price=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于卖券还款标的最大可卖数量查询。

注意事项：

##### 参数

security：股票代码(str)；

price：限定价格(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为最大数量。异常返回空dict，如{}(dict[str:int])

```
{'600570.SS': 1500}
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 查询恒生电子最大可卖券还款数量
    margincash_close_dict = get_margincash_close_amount(security)
    if margincash_close_dict is not None:
        log.info(margincash_close_dict.get(security))
```

#### get_marginsec_open_amount - 融券标的最大可卖数量查询

```
get_marginsec_open_amount(security, price=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于融券标的最大可卖数量查询。

注意事项：

##### 参数

security：股票代码(str)；

price：限定价格(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为最大数量。异常返回空dict，如{}(dict[str:int])

```
{'600570.SS': 2500}
```

##### 示例

```
def initialize(context):
    g.security = '600030.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 查询中信证券最大可融券卖出数量
    marginsec_open_dict = get_marginsec_open_amount(security)
    if marginsec_open_dict is not None:
        log.info(marginsec_open_dict.get(security))
```

#### get_marginsec_close_amount - 买券还券标的最大可买数量查询

```
get_marginsec_close_amount(security, price=None, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于买券还券标的最大可买数量查询。

注意事项：

##### 参数

security：股票代码(str)；

price：限定价格(float)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为最大数量。异常返回空dict，如{}(dict[str:int])

```
{'600570.SS': 3000}
```

##### 示例

```
def initialize(context):
    g.security = '600030.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 查询中信证券最大可买券还券数量
    marginsec_close_dict = get_marginsec_close_amount(security)
    if marginsec_close_dict is not None:
        log.info(marginsec_close_dict.get(security))
```

#### get_margin_entrans_amount - 现券还券数量查询

```
get_margin_entrans_amount(security, cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于现券还券数量查询。

注意事项：

##### 参数

security：股票代码(str)；

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为最大数量。异常返回空dict，如{}(dict[str:int])

```
{'600570.SS': 1300}
```

##### 示例

```
def initialize(context):
    g.security = '600030.SS'
    set_universe(g.security)

def handle_data(context, data):
    security = g.security
    # 查询中信证券最大可现券还券数量
    margin_entrans_dict = get_margin_entrans_amount(security)
    if margin_entrans_dict is not None:
        log.info(margin_entrans_dict.get(security))
```

#### get_enslo_security_info - 融券信息查询

```
get_enslo_security_info(cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于获取融券信息。

注意事项：

##### 参数

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为dict，包含返回的相关字段信息，如(dict[{}, {}])。异常返回None(NoneType)。

包含以下信息(相应字段无数据时返回None)：

- exchange_type: 交易类别 ， 仅包含1和2(str)；

- slo_ratio: 融券保证金比例(float)；

- enable_amount: 可用数量(int)；

- real_buy_amount: 回报买入数量(int)；

- real_sell_amount: 回报卖出数量(int)；

- slo_status: 融券状态，包括"0":正常，"1":暂停，"2":作废(str)；

- cashgroup_prop: 两融头寸性质，包括"1":普通，"2":专项(str)；

```
{'688001.SS': {'slo_status': '0', 'real_buy_amount': 0, 'cashgroup_prop': '1', 'enable_amount': 100000000000000, 'slo_ratio': 0.6, 'real_sell_amount': 0, 'exchange_type': '1'}, '010303.SS': {'slo_status': '0', 'real_buy_amount': 0, 'cashgroup_prop': '1', 'enable_amount': 100000000000000, 'slo_ratio': 0.6, 'real_sell_amount': 0, 'exchange_type': '1'}, '810004': {'slo_status': '0', 'real_buy_amount': 0, 'cashgroup_prop': '1', 'enable_amount': 10000, 'slo_ratio': 0.6, 'real_sell_amount': 0, 'exchange_type': '9'}}
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取最新的融券信息
    h = get_enslo_security_info()
    log.info(h)
```

#### get_crdt_fund - 可融资金信息查询

```
get_crdt_fund(cash_group=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用，仅在两融交易模块可用。

##### 接口说明

该接口用于获取可融资金信息查询。

注意事项：

##### 参数

cash_group： 两融头寸性质 (int)，1为普通头寸，2为专项头寸，该字段不入参默认表示普通头寸；

##### 返回

正常返回一个dict类型对象，key为股票代码，values为dict，包含返回的相关字段信息，如(dict[{}, {}])。异常返回None(NoneType)。

包含以下信息(相应字段无数据时返回None)：

- enable_balance: 可用资金(float)；

- real_buy_balance: 回报买入金额(float)；

- real_sell_balance: 回报卖出金额(float)；

```
{'enable_balance': 68258.96, 'real_sell_balance': 446720.12, 'real_buy_balance': 491809.45}
                            
```

##### 示例

```
def initialize(context):
    g.security = '600570.SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取可融资金信息
    h = get_crdt_fund()
    log.info(h)
```

### 期货专用函数

### 期货交易类函数

#### buy_open - 多开

```
buy_open(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

买入开仓

注意：

不同期货品种每一跳的价格变动都不一样，limit_price入参的时候要参考对应品种的价格变动规则，如limit_price不做入参则会以交易的行情快照最新价或者回测的分钟最新价进行报单；

根据交易所规则，每天结束时会取消所有未完成交易；

##### 参数

contract：期货合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['IF2312.CCFX']
    set_universe(g.security)

def handle_data(context, data):
    #买入开仓
    buy_open('IF2312.CCFX', 1)
```

#### sell_close - 多平

```
sell_close(contract, amount, limit_price=None, close_today=False)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

卖出平仓

注意：

不同期货品种每一跳的价格变动都不一样，limit_price入参的时候要参考对应品种的价格变动规则，如limit_price不做入参则会以交易的行情快照最新价或者回测的分钟最新价进行报单；

根据交易所规则，每天结束时会取消所有未完成交易；

##### 参数

contract：期货合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

close_today：平仓方式。close_today=False为优先平昨仓，不足部分再平今仓；close_today=True为仅平今仓，委托数量若大于今仓系统会调整为今仓数量。close_today=True仅对上海期货交易所生效，其他交易所无需入参close_today字段，若设置为True系统会警告，并强行转换为close_today=False。

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['IF2312.CCFX']
    set_universe(g.security)

def handle_data(context, data):
    #卖出平仓
    sell_close('IF2312.CCFX', 1)
```

#### sell_open - 空开

```
sell_open(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

卖出开仓

注意：

不同期货品种每一跳的价格变动都不一样，limit_price入参的时候要参考对应品种的价格变动规则，如limit_price不做入参则会以交易的行情快照最新价或者回测的分钟最新价进行报单；

根据交易所规则，每天结束时会取消所有未完成交易；

##### 参数

contract：期货合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['IF2312.CCFX']
    set_universe(g.security)

def handle_data(context, data):
    #卖出开仓
    sell_open('IF2312.CCFX', 1)
```

#### buy_close - 空平

```
buy_close(contract, amount, limit_price=None, close_today=False)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

买入平仓

注意：

不同期货品种每一跳的价格变动都不一样，limit_price入参的时候要参考对应品种的价格变动规则，如limit_price不做入参则会以交易的行情快照最新价或者回测的分钟最新价进行报单；

根据交易所规则，每天结束时会取消所有未完成交易；

##### 参数

contract：期货合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

close_today：平仓方式。close_today=False为优先平昨仓，不足部分再平今仓；close_today=True为仅平今仓，委托数量若大于今仓系统会调整为今仓数量。close_today=True仅对上海期货交易所生效，其他交易所无需入参close_today字段，若设置为True系统会警告，并强行转换为close_today=False。

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = ['IF2312.CCFX']
    set_universe(g.security)

def handle_data(context, data):
    #买入平仓
    buy_close('IF2312.CCFX', 1)
```

### 期货查询类函数

#### get_margin_rate- 获取用户设置的保证金比例

```
get_margin_rate(transaction_code)
```

##### 使用场景

该函数仅在回测模块可用

##### 接口说明

获取用户设置的保证金比例

注意事项：

##### 参数

transaction_code：期货合约的交易代码，str类型，如沪铜2112("CU2112")的交易代码为"CU"；

##### 返回

用户设置的保证金比例，float浮点型数据，默认返回交易所设定的保证金比例；

##### 示例

```
def initialize(context):
    g.security = "IF2312.CCFX"
    set_universe(g.security)
    # 设置沪深300指数的保证金比例为8%
    set_margin_rate("IF", 0.08)

def before_trading_start(context, data):
    # 获取沪深300指数的保证金比例
    margin_rate = get_margin_rate("IF")
    log.info(margin_rate)
    # 获取5年期国债的保证金比例
    margin_rate = get_margin_rate("TF")
    log.info(margin_rate)

def handle_data(context, data):
    pass
```

#### get_instruments- 获取合约信息

```
get_instruments(contract)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

获取合约的上市的具体信息

注意事项：

- 期货实盘模块中，由于行情源的限制，涨跌幅目前暂无法提供。

- 此API依靠期货资料详情数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空dict。

##### 参数

contract：字符串，期货的合约代码，str类型；

##### 返回

FutureParams对象，dict类型，key为字段名，value为字段值，主要返回的字段为:

- contract_code -- 合约代码，str类型；

- contract_name -- 合约名称，str类型；

- exchange -- 交易所：大商所、郑商所、上期所、中金所，str类型；

- trade_unit -- 交易单位，int类型；

- contract_multiplier -- 合约乘数，float类型；

- delivery_date -- 交割日期，str类型；

- listing_date -- 上市日期，str类型；

- trade_code -- 交易代码，str类型；

- margin_rate -- 保证金比例，float类型；

- changepct_limit -- 每日涨跌幅度，str类型(连续合约为空值)；

- littlest_changeunit -- 最小变动价位，str类型(连续合约为空值)；

##### 示例

```
def initialize(context):
    g.security = ["IF2312.CCFX"]
    set_universe(g.security)

def before_trading_start(context, data):
    # 获取股票池代码合约信息
    for security in g.security:
        info = get_instruments(security)
        log.info(info)

def handle_data(context, data):
    pass
```

#### get_dominant_contract- 获取主力合约代码

```
get_dominant_contract(contract, date=None)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

获取连续合约的主力合约代码

注意事项：

- 此API依靠期货主力合约与对应月合约数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空dict。

##### 参数

contract：字符串，期货的连续合约代码，str类型；

date：查询日期，不入参默认为当前日期，入参查询历史日期时支持datetime类型和str类型(仅支持'YYYY-mm-dd'和'YYYYmmdd'格式)；

##### 返回

期货连续合约对应的主力合约相关信息，dict类型，key为主力合约，value为dict类型，包含以下字段；

- corr_month_code -- 主力合约代码，str类型；

- trade_date -- 交易日期，str类型，如:"2024-02-01"；

- month_contract_name -- 主力合约名称，str类型；

##### 示例

```
def initialize(context):
    g.security = "IF2312.CCFX"
    set_universe(g.security)

def handle_data(context, data):
    # 获取2023年1月3日的IF主力合约代码
    main_code_info = get_dominant_contract("IF888.CCFX",date='2023-01-03')
    log.info(main_code_info)
    # 获取当前交易日的IF主力合约代码
    main_code = get_dominant_contract("IF888.CCFX")["IF888.CCFX"]['corr_month_code']
    log.info(main_code)
```

### 期货设置类函数

#### set_future_commission - 设置期货手续费

```
set_future_commission(transaction_code, commission)
```

##### 使用场景

该函数仅在回测模块可用

##### 接口说明

设置期货手续费，手续费是按照交易代码进行设置的

注意事项：

- 期货回测的手续费分为按交易金额比例收取和按交易手数收取两种方式，当前支持的股指期货是按金额比例收取的，国债期货是按手数收取的。

##### 参数

transaction_code：期货合约的交易代码，str类型，如沪铜2112("CU2112")的交易代码为"CU"；

commission：手续费，浮点型，设置说明：

- 当交易时的手续费是按手数收取时，则这里应当设置为每手收取的金额，例如：将期货的手续费设置为2元/手，此处应填写2；

- 当交易时的手续费是按总成交额收取时，则这里应当设置为总成交额的比例，例如：将期货的手续费费率设置为0.4/万，此处应填写0.00004；

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = "IF2312.CCFX"
    set_universe(g.security)
    # 设置沪深300指数的手续费，0.4/万
    set_future_commission("IF", 0.00004)

def handle_data(context, data):
    # 买入指数2312
    buy_open(g.security, 2)
```

#### set_margin_rate - 设置期货保证金比例

```
set_margin_rate(transaction_code, margin_rate)
```

##### 使用场景

该函数仅在回测模块可用

##### 接口说明

设置期货收取的保证金比例，保证金比例是按照交易代码进行设置的

注意事项：

##### 参数

transaction_code：期货合约的交易代码，str类型，如沪铜2112("CU2112")的交易代码为"CU"；

margin_rate：保证金比例，浮点型，将对应期货的保证金比例设置为5%则输入0.05；

##### 返回

None

##### 示例

```
def initialize(context):
    g.security = "IF2312.CCFX"
    set_universe(g.security)
    # 设置沪深300指数收取的保证金比例设置为5%
    set_margin_rate("IF", 0.05)

def handle_data(context, data):
    # 买入指数2312
    buy_open(g.security, 10)
```

### 期权专用函数

### 期权查询类函数

#### get_opt_objects - 获取期权标的列表

```
get_opt_objects(date=None)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

用于获取某日期的ETF期权标的，默认返回当前交易日的期权标的

注意事项：

- 此API依靠期权基础信息数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空list。

##### 参数

date：查询日期，str类型，仅支持YYYYmmdd或者YYYY-mm-dd格式；

##### 返回

期权标的列表，list类型，调用异常返回[]。

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取2022年07月03日的所有ETF期权标的列表
    get_opt_objects(date='20220703')
```

```
生成的列表：['510050.SS', '510300.SS', '159919.SZ']
```

#### get_opt_last_dates - 获取期权标的到期日列表

```
get_opt_last_dates(security, date=None)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

用于获取某日期的ETF期权标的到期日，默认返回当前交易日的到期日

注意事项：

- 此API依靠期权基础信息数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空list。

##### 参数

security：查询标的，str类型，如'510050.SS'；

date：查询日期，str类型，仅支持YYYYmmdd或者YYYY-mm-dd格式；

##### 返回

期权标的到期日列表，list类型，调用异常返回[]。

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取2022年07月03日的所有50ETF期权标的到期日列表
    get_opt_last_dates('510050.SS', date='20220703')
```

```
生成的列表：['2022-07-27', '2022-09-28', '2022-12-28']
```

#### get_opt_contracts - 获取期权标的对应合约列表

```
get_opt_contracts(security, date=None)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

用于获取某期权标的某交易日处于挂牌期间的合约列表

注意事项：

- 此API依靠期权基础信息数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空list。

##### 参数

security：查询标的，str类型，如'510050.SS'；

date：查询日期，str类型，仅支持YYYYmmdd或者YYYY-mm-dd格式；

##### 返回

期权标的合约列表，list类型，调用异常返回[]。

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取2022年07月03日50ETF期权标的对应的挂牌期合约列表
    get_opt_contracts('510050.SS', date='20220703')
```

```
生成的列表：['10003975.XSHO', '10003976.XSHO', '10003977.XSHO', '10003978.XSHO', '10003979.XSHO', '10003980.XSHO', '10003981.XSHO', ... , '10004332.XSHO', '10004337.XSHO', '10004338.XSHO', '10004339.XSHO', '10004340.XSHO']
```

#### get_contract_info - 获取期权合约信息

```
get_contract_info(contract)
```

##### 使用场景

该函数在研究、回测、交易模块可用

##### 接口说明

用于获取期权合约信息

注意事项：

- 此API依靠期权基础信息数据权限，使用前请与券商确认是否有此权限，无权限时调用返回空dict。

##### 参数

contract：合约编号，str类型，如上证期权'10003975.XSHO'、深圳期权'90000961.XSZO'；

##### 返回

字典类型，主要返回的字段为:

- contract_code -- 合约代码，str类型；

- contract_name -- 合约名称，str类型；

- exchange -- 交易所：上交所、深交所，str类型；

- warrant_way -- 期权类型，10-欧式，20-美式，30-百慕大式，str类型；

- contract_multiplier -- 合约乘数，float类型；

- expiration_date -- 到期日，str类型；

- listing_date -- 上市日期，str类型；

- option_type -- 期权属性 ，str类型；

- trade_code -- 交易代码，str类型；

- littlest_changeunit -- 最小价格变动单位，float类型；

- exercise_price -- 行权价格，float类型；

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取'10003975.XSHO'合约的详细信息
    get_contract_info('10003975.XSHO')
```

```
生成的字典：{'exercise_price': 2.85, 'contract_name': '50ETF购9月2850', 'contract_code': '10003975.ZSHO', 'exchange': '上交所', 'warrant_way': '10', 'trade_code': '510050C2209M02850', 'listing_date': '2022-01-27', 'expiration_date': '2022-09-28', 'contract_multiplier': 10000.0, 'littlest_changeunit': 0.0001, 'option_type': 'C'}
```

#### get_covered_lock_amount - 获取期权标的允许备兑锁定数量

```
get_covered_lock_amount(code)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

获取期权标的允许备兑锁定数量

注意事项：

- 从现货账号中获取标的数量。

- 仅支持上交所ETF期权标的。

##### 参数

code：期权标的代码，str类型，如50ETF：'510050.SS'；

##### 返回

允许备兑锁定数量: int类型:

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取'510050.SS'允许备兑锁定数量
    get_covered_lock_amount('510050.SS')
```

#### get_covered_unlock_amount - 获取期权标的允许备兑解锁数量

```
get_covered_unlock_amount(code)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

获取期权标的允许备兑解锁数量

注意事项：

- 从现货账号中获取标的数量。

- 仅支持上交所ETF期权标的。

##### 参数

code：期权标的代码，str类型，如50ETF：'510050.SS'；

##### 返回

允许备兑解锁数量: int类型:

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取'510050.SS'允许备兑解锁数量
    get_covered_unlock_amount('510050.SS')
```

### 期权交易类函数

#### option_buy_open - 权利仓开仓

```
option_buy_open(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

权利仓开仓

注意事项：

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 权利仓开仓
    option_buy_open(g.security, 1)

    # 权利仓开仓(限定价格0.0501)
    option_buy_open(g.security, 1, limit_price=0.0501)
```

#### option_sell_close - 义务仓平仓

```
option_sell_close(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

权利仓平仓

注意事项：

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 权利仓平仓
    option_sell_close(g.security, 1)
    # 权利仓平仓(限定价格为0.0499)
    option_sell_close (g.security, 1, limit_price=0.0499)
```

#### option_sell_open - 义务仓开仓

```
option_sell_open(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

义务仓开仓

注意事项：

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 义务仓开仓
    option_sell_open(g.security, 1)

    # 义务仓开仓(限定价格为0.0501)
    option_sell_open (g.security, 1, limit_price=0.0501)
```

#### option_buy_close - 义务仓平仓

```
option_buy_close(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

义务仓平仓

注意事项：

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 义务仓平仓
    option_buy_close(g.security, 1)
    # 义务仓平仓(限定价格为0.0499)
    option_buy_close (g.security, 1, limit_price=0.0499)
```

#### open_prepared - 备兑开仓

```
open_prepared(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

备兑开仓

注意事项：

- 仅支持上交所ETF期权标的。

- 仅支持认购类型期权。

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 备兑开仓
    open_prepared(g.security, 1)
    # 备兑开仓(限定价格为0.0501)
    open_prepared(g.security, 1, limit_price=0.0501)
```

#### close_prepared - 备兑平仓

```
close_prepared(contract, amount, limit_price=None)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

备兑平仓

注意事项：

- 仅支持上交所ETF期权标的。

- 仅支持认购类型期权。

##### 参数

contract：期权合约代码；

amount：交易数量，正数；

limit_price：买卖限价；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 备兑平仓
    close_prepared(g.security, 1)
    # 备兑平仓(限定价格为0.0499)
    close_prepared(g.security, 1, limit_price=0.0499)
```

#### option_exercise - 行权

```
option_exercise(contract, amount)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

合约在行权日支持行权

注意事项：

- 按合约行权价行权。

##### 参数

contract：期货合约代码；

amount：交易数量，正数；

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 行权
    option_exercise(g.security, 1)
```

### 期权其他函数

#### option_covered_lock - 期权标的备兑锁定

```
option_covered_lock(code, amount)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

期权标的备兑锁定，锁定现货账户标的；

注意事项：

- 仅支持上交所ETF期权标的。

##### 参数

code：期权标的代码；

amount：交易数量，正数；

##### 返回

返回None。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 510050.SS备兑锁定
    option_covered_lock('510050.SS', 1000)
```

#### option_covered_unlock - 期权标的备兑解锁

```
option_covered_unlock(code, amount)
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

期权标的备兑解锁，解锁现货账户标的；

注意事项：

- 仅支持上交所ETF期权标的。

##### 参数

code：期权标的代码；

amount：交易数量，正数；

##### 返回

返回None。

##### 示例

```
def initialize(context):
    g.security = '10004335.XSHO'
    set_universe(g.security)

def handle_data(context, data):
    # 510050.SS备兑解锁
    option_covered_unlock('510050.SS', 1000)
```

### 港股通专用函数

### 港股通查询类函数

#### get_hks_list - 获取港股通代码

```
get_hks_list(market)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在港股通交易模块可用

##### 接口说明

该接口用于获取行情返回的港股通代码列表

注意事项：

- market仅支持XHKG-SS和XHKG-SZ两个市场，不支持获取其他市场代码。

- 为减小对行情服务压力，该函数在交易模块中同一分钟内多次调用返回当前分钟首次查询的缓存数据。

##### 参数

market：不输入默认获取XHKG-SS和XHKG-SZ两个市场代码，或输入XHKG-SS;XHKG-SZ也可以获取两个市场代码。(str)

##### 返回

正常返回一个list类型对象，包含所有港股通代码。异常返回空list，如[](list[str,...])。

```
['02800.XHKG-SS', '02828.XHKG-SS','03033.XHKG-SS','03067.XHKG-SS', '08328.XHKG-SS', '00001.XHKG-SS', '00002.XHKG-SS', '00003.XHKG-SS', '00004.XHKG-SS', '00005.XHKG-SS', '00006.XHKG-SS', '00008.XHKG-SS',
'00010.XHKG-SS', '00011.XHKG-SS','00012.XHKG-SS', '00013.XHKG-SS', '00014.XHKG-SS', '00016.XHKG-SS', '00017.XHKG-SS', '00019.XHKG-SS', '00020.XHKG-SS', '00023.XHKG-SS', '00027.XHKG-SS', '00038.XHKG-SS',
'00041.XHKG-SS', '00045.XHKG-SS','00066.XHKG-SS', '00069.XHKG-SS', '00081.XHKG-SS', '00083.XHKG-SS', '00086.XHKG-SS', '00087.XHKG-SS', '00101.XHKG-SS', '00107.XHKG-SS', '00119.XHKG-SS', '00123.XHKG-SS',
'00127.XHKG-SS', '00135.XHKG-SS','00136.XHKG-SS', '00142.XHKG-SS', '00144.XHKG-SS', '00148.XHKG-SS', ...]
```

##### 示例

```
def initialize(context):
    g.security = '02899.XHKG-SS'
    set_universe(g.security)

def handle_data(context, data):
    #港股通代码列表
    hks_code_list = get_hks_list()
    log.info('港股通列表为%s' % hks_code_list)
```

#### get_hks_price_gap - 港股通价差查询

```
get_hks_price_gap()
```

##### 使用场景

该函数在交易模块可用

##### 接口说明

港股不同价格股票的最小价格变动幅度是不同的，该接口用于获取港股通业务的价差信息。

注意事项：

##### 参数

##### 返回

dataframe类型，主要返回的字段为:

- begin_price -- 分段起始价格，float类型；

- end_price -- 分段结束价格，float类型；

- step_price -- 最小价差，float类型；

- spread_type -- 市场类型，str类型；

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取港股通价差信息
    h = get_hks_price_gap()
    log.info(h)
```

#### get_hks_unit_amount - 获取港股通标的委托单位数量

```
get_hks_unit_amount(security, trade_type)
```

##### 使用场景

该函数在交易模块可用

##### 接口说明

港股每个标的的最小交易单位是不同的，比如有的为500股一手，有的为2000股一手，交易前需要通过该接口进行查询获取。

注意事项：

##### 参数

security：股票代码，支持单个或多个股票查询，多个股票入参用list类型。(str/list)

trade_type：交易方式，非零股交易入参'1'，零股交易入参'2'。(str)

##### 返回

dict类型，key为股票代码，value也是一个dict，包含以下字段信息:

- buy_unit_amount -- 买入最小交易股数，int类型；

- sell_unit_amount -- 卖出最小交易股数，int类型；

##### 示例

```
def initialize(context):
    pass

def handle_data(context, data):
    # 获取02899.XHKG-SS的限价交易的最小交易单位信息
    h = get_hks_unit_amount('02899.XHKG-SS', '1')
    log.info(h)
```

```
返回的信息：{'02333.XHKG-SS': {'buy_unit_amount': 500, 'sell_unit_amount': 500}}
```

### 港股通交易类函数

#### hks_order - 港股通买卖

```
hks_order(security, amount, limit_price=None, style=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在港股通交易模块可用

##### 接口说明

该接口用于港股通标的委托

注意事项：

- 该接口用于非零股类型的港股通交易。

- 该接口仅支持限价交易，limit_price不入参时量化引擎会按照行情最新价报单。

- 港股通的委托数量必须要按照标的的最小交易数量的N倍进行入参，因此要先通过get_hks_unit_amount接口进行查询。

- 港股通的委托价格必须要按照港股通价差标准进行入参，因此要先通过get_hks_price_gap接口进行查询标的所对应的最小价差。

- 港股通在集合竞价阶段用竞价限价委托，连续竞价阶段用增强限价委托，通过style参数控制。

##### 参数

security：股票代码。(str)

amount：委托数量，买入为正数，卖出为负数。(int)

limit_price：委托价格。(float)

style：委托类型，'1'为增强限价委托，'2'为竞价限价委托，不入参默认按增强限价委托处理。(str)

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '02899.XHKG-SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取02899.XHKG-SS用最新价以竞价限价委托方式买入
    order_id = hks_order(g.security, 2000, limit_price=None, style='2')
    log.info(order_id)
    # 获取02899.XHKG-SS用7.79元价格以增强限价委托方式买入
    order_id = hks_order(g.security, 2000, limit_price=7.79, style='1')
    log.info(order_id)
```

#### hks_odd_lot_order - 港股通零股卖出

```
hks_odd_lot_order(security, amount, limit_price=None)
```

##### 使用场景

该函数仅支持PTrade客户端可用、仅在港股通交易模块可用

##### 接口说明

该接口用于港股通标的委托

注意事项：

- 该接口仅用于零股类型的港股通卖出，amount只能为负数。

- 该接口仅支持限价交易，limit_price不入参时量化引擎会按照行情最新价报单。

- 港股通的委托价格必须要按照港股通价差标准进行入参，因此要先通过get_hks_price_gap接口进行查询标的所对应的最小价差。

##### 参数

security：股票代码。(str)

amount：委托数量，仅为负数。(int)

limit_price：委托价格。(float)

##### 返回

Order对象 中的id或者None。如果创建订单成功，则返回Order对象的id(str)，失败则返回None(NoneType)。

##### 示例

```
def initialize(context):
    g.security = '02899.XHKG-SS'
    set_universe(g.security)

def handle_data(context, data):
    # 获取02899.XHKG-SS用7.79元价格卖出
    order_id = hks_odd_lot_order(g.security, -500, limit_price=7.79)
    log.info(order_id)
```
