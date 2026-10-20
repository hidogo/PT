# Ptrade 实盘 L2 行情能力验证

> 验证「Ptrade 自带实盘 L2 数据」这一说法。
> 结论：**平台提供 L2 行情接口，但数据需券商开通 level2 行情才能获取** —— “自带接口、不保证自带数据”。

## 证据（Ptrade 官方 API 文档 / 海星文档中心）

| 接口 | 模块 | L2 相关说明 |
| --- | --- | --- |
| get_individual_entrust（逐笔委托） | 仅交易 | 沪深都有逐笔委托数据；**需开通 level2 行情才能获取到数据，否则无数据返回（None）** |
| get_individual_transaction（逐笔成交） | 仅交易 | 沪深都有逐笔成交数据；**需开通 level2 行情才能获取到数据，否则无数据返回（None）** |
| get_gear_price（档位行情） | 仅交易 | 返回 5 档 bid_grp/offer_grp 的[价格, 委托量, 委托笔数]；**无 L2 行情时委托笔数字段返回 0**（价格/量来自快照，仍可用） |
| tick_data | 仅交易 | data 可含 order/transaction（逐笔）；可用 set_parameters(tick_data_no_l2="1") 关闭；注释“当券商有 l2 行情时配置可提升取速” → 逐笔字段仅在券商有 L2 时有 |
| on_trade_response（成交主推） | 仅交易 | 成交事件回调（tick 级补充） |

## 关键点

- L2 在 Ptrade 语境 = **逐笔委托 + 逐笔成交 + 带委托笔数的五档**；文档中无“十档”接口。
- 档位本身（get_gear_price 的 5 档价格/数量）走行情快照，一般可得；**委托笔数是 L2 专属**。
- 逐笔委托/成交**必须券商开通 level2 行情**才返回数据；未开通则返回 None。是否开通取决于券商与账户资质（常需开通/付费/权限申请）。
- 仅交易（实盘/模拟）模块有 L2；回测模块无 L2（按日/分钟）。
- “自带实盘 L2”应理解为：Ptrade 平台交易环境**内置了 L2 行情接入接口**，一次拿到逐笔与档位，便于打板/封单类策略；但**数据可得需以券商开通 L2 为前提**，并非开通即必有。实盘前须在终端确认账户的 L2 行情权限，并在模拟盘验证 get_individual_* / get_gear_price 是否返回有效数据。

## 对本课题（买卖策略迁移）的含义

- axquant 打板/封单近似依赖的“逐笔/五档/委托笔数”，Ptrade 能用 get_individual_transaction / get_individual_entrust / get_gear_price 承接，**前提是券商开通 L2**。
- 未开通 L2：逐笔/委托笔数不可用，档位价格数量仍可用 → 打板(卖买消化比)、封单衰减只可降级用档位量/现价近似（与前文的可靠性评估一致）。见 docs/18。
- 需在策略初始化前/运行中确认 L2 可用性并做降级路径（try/except + 判断返回值是否为 None / 委托笔数为 0）。

来源：ptrade.wiki 与海星量化 PTrade 文档中心（见 reference/）。配套：docs/16、docs/18、docs/19。

## 实测更新（2026-10-15，见 docs/23）
- 该国金托管-模拟盘实测：get_gear_price 返回十档结构（bid_grp/offer_grp 1..10），继承权盘档位为 0；
- get_individual_transaction / get_individual_entrust 返回真实逐笔，盘后仍能回放当日 15:00 前后逐笔；
- 结论：该账户 Level2 实际可用，无需再默认为“需开通”；既有“五档”描述可更新为“十档”。

## 2026-10-16 实测结论（已确认）
- `[l2] code=601811.XSHG tx=10 entrust=10 gear_bid_cnt=3 -> L2_OK`（盘中 10:31）。
- 交易模块具备 逐笔成交/逐笔委托/十档委托笔数 真实 L2，权限 OK。

## 2026-10-19 总买/总卖量验证（v0.26b）

- **接口结论（docs/06 权威字段表）**：云端交易模块 `get_snapshot` 标准字段直接含总买/总卖量——
  - `total_bidqty` 委买量 / `total_offerqty` 委卖量（str:int，单位手；示例 18900/28900，等于五档合计）。
  - `entrust_diff` 委差 / `entrust_rate` 委比。
  - `bid_grp`/`offer_grp` 委买/委卖档位（第一档含委托队列 `{int:int}` 仅 L2 支持；`get_gear_price` 委托笔数无 L2 时为 0）。
  - 注意：`total_bid_turnover`/`total_offer_turnover`（委买/委卖金额）主推 tick 数据中为 0，仅在线请求支持；**量字段不受此限制**。
- 已加实盘探针（strategy `_l2_probe`）：下一交易日日志应出现
  `[l2] <code> snap total_bidqty=.. total_offerqty=.. entrust_diff=.. entrust_rate=.. bid1_queue_l2=..`（L2 首档队列是否有值）与
  `[l2] <code> gear bid_sum=.. offer_sum=..`（十档买卖量合计）。
- 自测 T60 探针空数据不崩；全量 240 PASS / 0 FAIL；双编译通过。
- 用途（待盘中确认后接线）：封单大减可用 total_bidqty 补充/替代买一档封单；炸板/封死可用 total_offerqty==0 判卖方无挂单；委差/委比可做强弱辅助。
- 接线口径（用户确认 2026-10-19）：
  - 封单大减保持「买一量」口径（`_seal_metrics` 取 bid_grp[1] 挂单金额，不换 total_bidqty）。
  - 封死不排队：`_sealed_at_limit` 用 `total_offerqty==0`（快照总委卖量，单位手）判卖方无挂单，缺失回退 ask_grp 显式空判；
    封死状态需持续 >= `sealed_fresh_secs`(5s) 才生效（防瞬时零卖盘误判不排单）。
  - 新参数：`sealed_fresh_secs=5.0`、`sealed_offerqty_enabled=True`（BLS 可调）。
  - 自测：T12 更新为预置持续 6s 封死 + 新增 T61 八项（total_offerqty==0/持续确认/总委卖量>0/解除清起点/ask 兜底/卖档有量/未触涨停）；全量 248 PASS / 0 FAIL；双编译通过。

