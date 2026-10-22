# buysell_core - 版本记录

> 变更记录统一存本文件；strategy.py 文件头仅保留「当前版本 / 部署核对」。

## 当前版本
- 当前版本：v0.49（2026-10-22）（前一版 v0.43 存档 1eea218）

## 部署核对
- 部署核对：日志首行 `buysell_core init version=v0.49 ...`（init 打印 STRATEGY_VERSION）
- 每次更新版本号后重传 strategy.py 云端，以日志首行 `buysell_core init version=..` 核对。

## 设计依据
- buysell_core —— Ptrade 托管「高可靠买卖子集」迁移骨架（v0.4）
- 依据：docs/16 + docs/18；AXquant 真实参数取自 D:/PROJ/AXquant/axquant/strategy
- (decision/sell.py, decision/__init__.py, scorer/*, btree/builder.py ma_pullback)
- v0.4 把 score_now 做成真实版（结构等价，数据用 Ptrade 内置接口近似）：
- 分 = clamp(base40 + 静态加分 - 静态扣分 + 攻击加分 - VWAP扣分 + 外内盘, 0..92)
- 兼容国金：run_daily(context,func)+回调单参；log 先 % 拼单字符串；禁用 os。
- 只读安全：DO_ORDER=False 不发真单，仅记 [may-order]。
- v0.15 对齐 AXquant 买卖逻辑核心：1) 一字板封单超预期不参考排单（封死涨停不排队买入）；
- 2) 竞价核卖 P2E：预期已确认 miss/degraded -> 清仓；3) 弹性追高买入价 300/688 前收*1.10 上限（打板豁免）。
- v0.16 节奏：新增 09:25 auction_pre_confirm（重读9:20上传预期文件+竞价终态初步确认超预期->观察，不买）+09:31兜底重读。
- v0.17 供方数据健壮性：A)负基昨日开盘也判高开；B)预期基准缺失/<=0不超预期不误弃(防过触发)；云端1d历史折算昨日开盘与达标基准兜底；C)供方CSV缺失字段输出空串。
- v0.28 涨停池合成过滤 ST（消费 zt_lianban 的 is_st 字段，对齐 AXquant 复盘口径）；盘前一键脚本 run_one_click_premarket.py（生成+校验+上传勾选，docs/39）。
- v0.29 情绪冰点→回暖链（docs/40）：本地生成 sentiment CSV（T 日冰点+连续冰点天数）盘前读入；红盘比恢复判回暖，冰点越久恢复阈值越低（回暖概率增加）。
- v0.30 情绪仓位上限（docs/40 闭环）：连续回暖增加分歧概率；冰点日最大总仓位 40%，回暖日 80%（连续回暖 N 日起递减，分歧保护），买入路径统一拦截。
- v0.14 预期买入两阶段（T+1，side=buy 且预期超预期）：
- 1) 竞价终态初步确认「竞价超预期」-> 观察（不买）；2) 分时确认超预期(两分钟上攻 或 一分钟冲涨停,且不破VWAP) -> 执行买入。
- tick_data 3s 事件触发 + 一次触发持久化去重(exp_fired) + 独立 EXPECT_ORDER 实盘门控。

## 版本记录（新→旧）

### v0.49
- v0.49 炸板应对收紧 + 回封打板（docs/33）：A 炸板卖出改买N档限价(默认买3+0.95下限保护)；
- B 唯一身位连板封单容忍(seal_fail_ratio_unique) + 二次炸板减半(仅唯一身位后排助攻/人气龙头)；
- C 炸板减去早盘触涨停分(+6, 回封复位恢复)；D 回封打板(前排首板/2板 10:00前炸板回封, 大单占比>=10%)

### v0.48
- v0.48 修复 v0.47 实锤问题（docs/33）：A business_amount 单位非'元'——按 shares/lots/yuan 换算元
- (默认股x价)，探针输出最大单笔元值；B tick_board_scan 并入强度前三成员仅限首板窗口
- (_min_age<=first_board_minute) + 成员上限 20->10（午后帧预算归零）

### v0.47
- v0.47 灵敏度收紧（docs/33）：A L2 大单占比加分（逐笔 business_amount 按 trade_index 去重累计，
- >=10% 加分5分/封单豁免）；B 强度前三板块成员并入 tick 目标集 + scan_interval 4->1 + [scan] 探针；
- C 预封扫板=封单下限 或 大单加持 二者满足其一

### v0.46
- v0.46 首板封单下限 + 唯一预判身位统一（docs/33）：_try_first_board_buy 补 first_board_seal_min
- (L2 买一挂单金额, 防假封秒炸)；_dyn_unq_auction_eval 跳过中位股(与 _mid_board_avoid 统一口径)

### v0.45
- v0.45 云 LogEngine 无 .warn 兼容（_warn 封装 warning->warn->info 兜底不抛，
- 修复 qty<=0 skip 分支与 except 二次崩溃导致 tick_data 链路中断）

### v0.44
- v0.44 合成数据消费审计（docs/40）：_warm_cap 显式消费 sentiment.divergence 分歧标志，
- 与 warm_days 双保险触发分歧保护 taper，修复生成侧 divergence 列云端未被消费的脱节

### v0.43
- v0.43 买卖操作理由与灵敏度日志固化（docs/30）：_signal 结构化行补 lag=检测->下单时延 + det=检测源:首触毫秒；
- [may-order]/[exp-order]/order sent 同补 lag；after_trading_end 打 [rt-summary] 日结（按 side/mode）

### v0.42
- v0.42 一字板竞价终态精确判定（docs/29）：真一字=开=涨停价且卖1=0(total_offerqty==0)才标 one_word；
- + 竞价终态封单基准回填(seal_base，_exp_one_word 首帧即判) + 09:30 首帧补标(防 09:25 漏标)；
- 卖1>0 打 [seal] playable(非真一字, 可参与) 日志；1帧内封涨停放行（不扩大拦截）

### v0.41
- v0.41 情绪温度消费统一全市场红盘比口径（_market_red_ratio 全量分片/独立 market 预算）
- + emotion 档位接入仓位上限（冰点/偏冷40%、回暖/发酵80%、高潮/过热taper，冲突取保守）

### v0.40
- v0.40 from-jsonl 自动兜底并入 ShareData 预期源（含可用性闸门防空文件抢占）

### v0.39
- v0.39 预期文件补股票名列（CSV/JSONL 贯通）+ 预期源对接 ShareData 共享目录

### v0.38
- v0.38 盘中动态唯一+跟风确认+竞价唯一扫板（docs/30）：A 动态唯一(首触无更高/并列身位)；
- B 跟风确认(首触300s窗口内 同板块身位更低未封板成员 1m surge>=1.5% 达2家)；
- C 排序加分/CX标注/持有提示；D 竞价唯一(同身位竞品不及预期)+开盘上攻冲板+跟风确认
- +现价<涨停价 -> 涨停价扫板(预算20%, 避免买不到)；已封板/一字不扫。

### v0.37
- v0.37 中位/主动/唯一性稳健性修复（docs/33）：a) 最快拉升判快改逐笔毫秒归一(_first_zt_ms)；
- b) 首板闸门比较宇宙切概念文件口径(_board_member_codes)；c) 板块内涨幅最高批量回填快照；
- d) zt_lianban 追加权威唯一列(unique_high/follower_count, AXquant 同源预计算)云端读列优先。

### v0.36j
- v0.36j 文件头版本号注释 + init 日志打版本（部署核对）

### v0.36i
- v0.36i 统一买卖信号结构化 [signal]（采集器按日入库/对账）

### v0.36h
- v0.36h 待上传根目录只留 *_latest（dated 全移 archive）

### v0.36g
- v0.36g 盘中重启重建涨停池/自选三态（防 expect_buy 45->12 丢失）

### v0.36e
- v0.36e 概念板块口径+灵敏度（合并快照/两段式surge/预算24）
