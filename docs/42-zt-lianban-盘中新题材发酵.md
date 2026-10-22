# zt_lianban 盘中新题材发酵识别与消费（v0.56）

> 状态：v0.56 已实施（2026-10-22）；v0.57 已按审查修复 1/3/4/5（tick 零 API、冷缓存闸门、seal_min 生效、temp 桶合并）。
> 数据契约见 docs/33；本篇解决「今日新发酵题材 + 首板助攻 + 前排」的盘中识别与消费。

## 1. 问题边界

v0.55 的 `_dyn_theme_status` 只遍历 T-1 涨停池成员（`g.zt_theme`），只能做存量题材修正：
续板、炸板、龙头转授。今日新首板（T-1 不在涨停池）对这套动态层不可见，也没有权威题材标签。
本篇补齐这一层：把「新首板助攻」按题材归组，识别哪些题材在盘中新发酵，并消费到前排/助攻分层。

## 2. 识别层

### 2.1 新首板事件
- 事件源：tick `g.first_zt` 首触（ms 归一，`_first_zt_ms`）+ `_today_zt` 封板确认。
- 过滤：`_is_first_board`（T-1 不在涨停池 / board_cnt<1）；一字板排除（对齐 `_board_first_zt`）。

### 2.2 THS -> 题材桶桥接
- 新代码无 AXquant 权威题材列，用 `_concept_boards_of` 取 THS 概念；
  概念成员与 T-1 `g.zt_theme` 桶成员做交集（≥1）归并到权威题材桶；
  无交集时建临时桶 `THS:<概念名>` 并标记 temp（收盘复盘回填权威桶）。
- 缓存：`g.zt_new_cache` 15s 节流（与动态题材状态同 TTL）。

### 2.3 发酵状态机
- 窗内（默认 25 分钟）新首板助攻家数 ≥ 2 且存在存活前排 -> `confirmed`；
- 助攻家数 ≥ 5 -> `hot`（高潮）；其余 `watch`。
- 强度参与排序与观察，不直接放大追高（沿用 docs/41 §3.4 纪律）。

### 2.4 前排定义
- 存量题材：`_dyn_theme_status` 的动态唯一龙头仍为前排（今日续板/存活）。
- 全新题材（无 T-1 锚）：最早触板（`_first_zt_ms` 最小）且仍封板的存活者；并列取封单大者。
- 存量龙头炸板后：身位转授给该题材最高身位唯一存活者（含新首板）。

## 3. 消费层

| 函数 | 改动 |
|---|---|
| `_new_themes_of(sec)` | 新增：THS 概念 -> 题材桶桥接 + 临时桶 |
| `_dyn_theme_ferment()` | 新增：15s 缓存发酵状态机（assist_count / confirmed / stage / front） |
| `_dyn_theme_leader(sec)` | 扩展：确认/高潮发酵题材的存活前排视为动态龙头 |
| `_ferment_front_gate(sec)` | 新增：首板打板闸门，助攻非前排跳过 |
| `_try_first_board_buy` | 接入闸门：存量题材助攻不抢前排；全新题材前排走原闸门 |
| `_zt_theme_sort_bonus(code)` | 扩展：确认题材成员 + 前排排序加分（仅排序） |

纪律：首板助攻只做「前排唯一身位」或「全新题材前排」；中位跟风与助攻后排一律回避，
与复盘纪律「次日板块后排无溢价、严禁追高」一致。

## 4. BLS 参数

- `zt_theme_ferment_enabled=True` 总开关
- `zt_theme_ferment_window_min=25` 发酵确认时间窗（分钟）
- `zt_theme_ferment_assist_min=2` 窗内最少助攻家数
- `zt_theme_ferment_hot_assist=5` 高潮助攻家数阈值
- `zt_theme_ferment_front_bonus=0.8` 确认题材前排排序加分
- `zt_theme_ferment_sort_bonus=0.5` 确认题材成员排序加分
- `zt_theme_ferment_seal_min=50000.0` 前排封单下限（0=关闭；无 L2 数据不拦截）

## 5. 验证

- selftest T92i：THS 桥接 + 发酵确认 + 存量龙头仍前排 + 助攻闸门拦截 + 全新题材前排放行
  + 高潮档位 + 窗口超限不确认 + 排序加分。
- 全量回归 ALL DONE / 0 FAIL；PT3.7 与 veighna 双 py_compile。

## 6. 风险与纪律

- THS 概念与 AXquant theme.buckets 命名有漂移，交集桥接只对已有成员的桶有效；
  全新题材只能临时桶，不得按临时桶重仓。
- 发酵分是盘中噪声：15s 节流，只影响排序，不允许直接放大买入。
- 20cm/30cm 阈值按 `_limit_threshold` 处理；首板助攻可能「首板即高位」，容量/弹性属性单独标注。
