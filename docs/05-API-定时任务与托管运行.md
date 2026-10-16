<!-- 来源：ptrade.wiki PTrade API文档（见 reference/ptrade-wiki-API参考.md）；字段以官方最新版本为准。 -->
<!-- 返回：见 README.md 文档索引 -->

### 定时周期性函数

#### run_daily-按日周期处理

```
run_daily(context, func, time='9:31')
```

##### 使用场景

该函数仅在回测、交易模块可用

##### 接口说明

该函数用于以日为单位周期性运行指定函数，可对运行触发时间进行指定。

注意事项：

- 该函数只能在初始化阶段initialize函数中调用。

- 该函数可以在initialize中多次调用，以实现多个定时任务。 但需要注意的是交易中定时任务线程数限制为5且累计的任务不执行，即run_daily和run_interval累计调用超过5次时， 将会因堵塞导致部分定时任务不触发。

- 股票策略回测中，当回测周期为分钟时，time的取值指定在09:31~11:30与13:00~15:00之间，当回测周期为日时， 无论设定值是多少都只会在15:00执行；交易中不受此时间限制。

##### 参数

context: Context对象 ，存放有当前的账户及持仓信息(Context)；

func：自定义函数名称，此函数必须以context作为参数(Callable[[Context], None])；

time：指定周期运行具体触发运行时间点，默认为9:31分(str)，交易场景可设置范围：00:00~23:59。

##### 返回

None

##### 示例

```
# 定义一个财务数据获取函数，每天执行一次
def initialize(context):
    run_daily(context, get_finance)
    g.security = '600570.SS'
    set_universe(g.security)

def get_finance(context):
    re = get_fundamentals(g.security,'balance_statement','total_assets')
    log.info(re)

def handle_data(context, data):
    pass
```

#### run_interval - 按设定周期处理

```
run_interval(context, func, seconds=10, interval_timer_ranges="")
```

##### 使用场景

该函数仅在交易模块可用

##### 接口说明

该函数用于以设定时间间隔(单位为秒)周期性运行指定函数，可对运行触发时间间隔进行指定。

注意事项：

- 该函数只能在初始化阶段initialize函数中调用。

- 可通过 interval_timer_ranges 参数设置运行的时间段。

- 该函数可以在initialize中多次调用，以实现多个定时任务。但需要注意的是交易中定时任务线程数限制为5且累计的任务不执行，即run_daily和run_interval累计调用超过5次时，
 将会因堵塞导致部分定时任务不触发。

- 最小运行时间间隔seconds的设置规则：期货策略为1秒（用户设置值若小于1秒，系统仍当做1秒处理），股票等其他类型策略为3秒。

##### 参数

context: Context对象 ，存放有当前的账户及持仓信息(Context)；

func：自定义函数名称，此函数必须以context作为参数(Callable[[Context], None])；

seconds：设定时间间隔(单位为秒)，取值为正整数(int)。

interval_timer_ranges：用于设置指定函数运行的时间范围(str)。

- 每个时间段使用 HH:MM-HH:MM
 格式，多个时间段之间用英文逗号分隔。例如："09:15-11:30,13:00-15:00"表示从上午9点15分到11点半和下午1点到3点的时间范围。

- 当前时间大于等于时间段范围的开始时间、小于时间段范围的结束时间时触发 run_interval
 内设置的函数。

- 时间是以24小时制表示的，确保统一格式。

- 如果未定义此参数，系统将默认使用券商配置时间范围进行处理。

- 如果时间段在数据更新范围外，可能会导致获取到未更新的历史数据，建议设置当前业务可交易的时间范围。

##### 返回

None

##### 示例

```
# 定义一个周期处理函数，每10秒执行一次
def initialize(context):
    # 设置 interval_handle 函数在9:15~11:30与13:00~15:00时间段内执行
    run_interval(context, interval_handle, seconds=10, interval_timer_ranges="09:15-11:30,13:00-15:00")
    g.security = "600570.SS"
    set_universe(g.security)

def interval_handle(context):
    snapshot = get_snapshot(g.security)
    log.info(snapshot)

def handle_data(context, data):
    pass
```

#### 国金实测运行注意（2026-10-15）
- run_daily 回调函数签名必须为单参 func(context)，注册格式 run_daily(context, func, time=...)（context 是第一个位置参数）。
- 回测分钟周期 time 限定 09:31~11:30 与 13:00~15:00；日线固定 15:00；交易不限。
- log.info/warn/error 不做 % 占位替换，应先拼成单字符串：log.info("x=%s" % v)。

