# AXquant 策略迁移到 Ptrade 托管：可行性评估

> 对象：D:/PROJ/AXquant（AXquant 量化交易系统）
> 目标：Ptrade（恒生）托管策略，在券商服务器上自动运行。
> 结论：整体不能一键迁移；需按「托管内」与「自有服务器旁路」两层拆分，其中纯策略规则可在 Ptrade 内实现，LLM/外部数据/交易桥/基础设施多数需改造或外置。

## 1. AXquant 是什么

涨停/打板博弈型 agent 策略，主路径为行为树：数据 → 选股池 → 三维标签 → 多维打分 → 多场景买卖 → 风控 → 执行，盘中叠加 LLM/Agent 决策门禁（NanoJev 模型 + DeepSeek/Kimi/豆包/ARK 大模型 BUFF）与次日三态预期跟踪。

- 策略逻辑: axquant/strategy（pool/tagger/scorer/decision/risk/btree/expectation）
- 数据层: axquant/data/source（QMT/大QMT桥、HiThink 同花顺、TDX、腾讯、东财、Wencai/AkShare、DuckDB 热存储）
- 模型层: axquant/strategy/model/nano_jev.py（torch），配置 llm.*（外部大模型 API）
- 交易层: axquant/trading（QMT 文件桥 / BigQMT / miniQMT / mock），axquant/qmt_bridge HTTP 服务
- 基础设施: dashboard(FastAPI/uvicorn) + WebSocket + Windows 计划任务守护 + 微信推送 + 日志

## 2. Ptrade 托管的环境约束（决定可行性的前提）

| 约束 | Ptrade 托管实际 |
| --- | --- |
| 运行模型 | 单文件回调：initialize / before_trading_start / handle_data / after_trading_end / tick_data / on_order_response / on_trade_response |
| 定时 | run_daily（日）与 run_interval（秒），只能在 initialize 注册，累计 ≤5 个 |
| 最小频率 | tick 约 3 秒（股票），期货 run_interval 最小 1 秒；无亚秒 0.2s 能力 |
| 数据 | 仅 Ptrade 内置 API（get_history/get_price/get_snapshot/get_gear_price/get_fundamentals/get_index_stocks/get_Ashares/check_limit 等），一般无外网 |
| 第三方库 | 券商白名单（见 docs/14），无 torch/transformers/duckdb/httpx 等 |
| 交易 | order / order_target / order_value / order_target_value / order_market / cancel_order 等 |
| 持久化 | 框架在 before/handle/after 后自动保存，g 全局 + 可选 pickle |
| 服务/推送 | 无自有 HTTP 服务/守护进程；可用 send_email / send_qywx（券商开通） |

## 3. 分级可行性结论

### 3.1 可实现（可在 Ptrade 托管内重写执行）

| AXquant 模块 | 迁移方案（Ptrade 对等） | 说明 |
| --- | --- | --- |
| 阶段门控 / 行为树编排 | initialize + handle_data 内按时间阶段分支，run_daily 定节拍 | 纯编排逻辑，直接改写 |
| 选股入池（强度扫描、开盘脉冲） | run_interval(3s) / tick_data + get_Ashares/get_snapshot 扫描入池 | 规则可移植；节奏由 0.2s 降为 3s，min_chg 阈值需重标定 |
| 三维标签 / 多维打分 | get_history（连板/百日新高/量比）+ get_stock_blocks/get_industry_stocks + get_fundamentals | 纯计算逻辑可移植；财务/板块取 Ptrade 数据 |
| 买入/卖出多场景决策 | order 系列 + 状态机 + on_order_response/on_trade_response 闭环 | 下单能力对等，部分 tick 级判定降级 |
| 风控（每日 N 支、涨停价保护、price_cage、回撤） | 托管内维护当日计数 + check_limit 涨跌停判断 + order 限价取整 | 可完整实现 |
| 次日三态预期（规则部分） | 用 g + pickle 跨日持久化，盘中按竞价/2根1m/VWAP 规则判定 | 规则口径可复刻 |
| 全市场情绪（涨跌家数） | get_Ashares + get_snapshot 或近端定时快照估算 | 有对等能力，精度取决于批量快照上限 |

### 3.2 受限 / 需改造（部分可行，功能有缺口或要降级）

| AXquant 能力 | Ptrade 情况 | 对策 |
| --- | --- | --- |
| 逐笔 / 五档 / 档位封单 | 有 get_individual_transaction/get_gear_price（档位），无“封单量”标准接口 | 用档位价量近似；一字板封单比丁非对等，可能要券商扩展接口 |
| 集合竞价细粒度 | 有 get_trend_data（集中竞价）、竞价数据 | 可用，但逐笔委托/成交（get_individual_entrust/get_individual_transaction）权限按券商 |
| 盘中实时行情节奏 | tick ≥3s，且无 0.2s hot_ticks | 打板“快速封板”判定降级为秒级，需重调休整参数 |
| 龙头/连板/板块映射 | get_stock_blocks/get_index_stocks/get_industry_stocks 可做，但“同花顺天梯/龙虎/涨停池精确名单”无对等接口 | 改用 Ptrade 板块与涨跌停，或外置生成名单 |
| 撤单与订单闭环 | cancel_order / on_order_response 有；但 QMT passorder 细节（如亚秒响应、部分成交语义）不同 | 改走 Ptrade 委托主推闭环，异步语义重写 |

### 3.3 不可行（Ptrade 托管环境内无法运行，需外置/拆分）

| AXquant 能力 | 原因 | 建议架构 |
| --- | --- | --- |
| NanoJev 模型推理（torch） | 托管无 torch/transformers、无法加载 4.7GB 权重 | 推理放到自有机器；Ptrade 端只做规则执行 + 可选信号执行 |
| 大模型 BUFF（DeepSeek/Kimi/豆包/ARK 进程） | 托管一般无外网、无 requests/httpx 白名单、且不允许跑常驻进程 | 决策外置：自有服务器运行 agent，Ptrade 用 run_interval 轮询官方数据做规则化放行（无法读自定义文件） |
| QMT 文件桥 / BigQMT / miniQMT 交易链路 | 托管下单走 Ptrade order API，无 QMT 沙盒 | 交易桥整体移除，改 Ptrade 交易接口 |
| akshare / wencai / TDX / 东财 / HiThink(同花顺) 数据源 | 托管无外网、库受限 | 数据统一改 Ptrade 内置 API；外源仅在有外连券商时保留为旁路 |
| DuckDB / HotStore 热存储 | 托管无 duckdb、且不自建本地库 | 用框架持久化（g + pickle）与回测/交易界面替代 |
| Dashboard / HTTP 服务 / WebSocket | 托管不能跑 FastAPI/uvicorn，无法开放端口 | 撤掉；改 s end_email / send_qywx 推送与平台自带界面 |
| Windows 计划任务 / 守护进程 / 复盘脚本 | 托管部署在券商服务器，无自定义计划任务 | 复盘/守护外置到自有机器，或改 Ptrade after_trading_end 盘后逻辑 |
| 亚秒 0.2s 行情 / 秒级内快速封板 | Ptrade 无该颗粒度 | 降级为秒级轮询，重标定阈值 |

## 4. 推荐的落地架构（混合拆分）

    【自有服务器 / 本机 AXquant】            【Ptrade 托管策略】
    数据挖掘/涨停池/复盘/AI 决策/NanoJev     薄策略：纯规则执行
         │  (决策→信号文件/接口, 若有外连HTTP)       │
         └────────────────► 信号可执行 ─────────────┘
    结果为：资产/持仓/成交回传（Ptrade 日志/对账）

实现优先级：
1. 先把「策略规则引擎」按 Ptrade 回调重写为可回测版本（回测验证逻辑正确）。
2. 在模拟盘跑通「编写→回测→模拟→托管」链路。
3. 决定信号来源：完全规则化（推荐、自包含）还是外置 AI 旁路（需券商外连 + 自有服务）。
4. NanoJev/LLM 仅保留在自有机器做离线研究/复查，不进托管。

## 5. 结论一句话

- 可实现：规则型选股/标签/打分/买卖/风控/次日预期、模拟回测、Ptrade 下单闭环。
- 不可行：LLM/NanoJev 推理、QMT 交易链路、外部数据源、Dashboard/守护进程、亚秒行情 —— 这些要么外置、要么降级改造。
- 建议：不要把 axquant 整体“搬”进 Ptrade；而是把一个“薄策略执行器”放 Ptrade，把重计算与 AI 决策留在自有环境。

---
参考：本目录 docs/00–docs/15；Ptrade 数据/下单能力以各券商终版为准。

## 6. 实测更新（2026-10-15，见 docs/23）
放多注：托管-模拟盘实测 L2 逐笔/十档可用、账户/行情/财务/板块/持久化全通；
“逐笔/档位封单”与“集合竞价细粒度”两行受限评级可上调（用 get_individual_transaction/get_gear_price 十档近似封单）。
打板/封单微观仍受 3s 节拍限制，需重标定参数（评级维持）。
