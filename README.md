# PTrade 托管策略研究目录

本仓库用于 **Ptrade 托管策略** 的开发研究。目标是把官方/社区 PTrade 文档整理成一套可检索、可直接指导开发的资料库，并作为后续策略开发的代码地基。

「托管」即把策略上传到券商 PTrade 服务器，由服务器按计划自动运行（定时任务 run_daily / 秒级周期 run_interval），关闭客户端后策略仍可持续执行。

## 目录结构

    .
    ├─ docs/            整理后的开发文档（按主题拆分，建议从这里入手）
    ├─ reference/       离线原始文档（网页原文 + 转换后的 Markdown 参考）
    ├─ research/scripts/ 文档抓取与格式转换脚本
    ├─ examples/        可直接在模拟盘跑通的策略示例
    ├─ strategies/      你的托管策略源码目录（每策略一子目录）
    └─ README.md        本索引

## 文档索引

先读：**[docs/00 - Ptrade 托管策略开发指南](docs/00-Ptrade托管策略开发指南.md)**（总览 + 工作流 + API 速查 + 注意事项）

| 文档 | 内容 |
| --- | --- |
| [docs/01](docs/01-使用说明-策略构建回测交易流程.md) | 新建策略/回测/交易流程，运行周期与运行时间 |
| [docs/02](docs/02-开始写策略与代码模板.md) | 从零写策略、持久化、代码尾缀、异常与限价注意事项 |
| [docs/03](docs/03-策略引擎与运行生命周期.md) | 生命周期回调（initialize/handle_data/事件主推） |
| [docs/04](docs/04-API-设置函数.md) | set_universe、基准、佣金、滑点等设置类 API |
| [docs/05](docs/05-API-定时任务与托管运行.md) | run_daily / run_interval 托管定时细节 |
| [docs/06](docs/06-API-获取信息.md) | 行情、证券、持仓资金、交易日等数据 API |
| [docs/07](docs/07-API-交易下单.md) | order 系列、撤单、订单/成交查询 |
| [docs/08](docs/08-API-两融与期权期货港股通.md) | 融资融券、期货、期权、港股通专用函数 |
| [docs/09](docs/09-API-技术指标与计算.md) | MACD/KDJ/RSI/CCI 等技术指标与其他函数 |
| [docs/10](docs/10-公共对象与数据字典.md) | g、Context、BarData、Portfolio、Position、Order 与状态枚举 |
| [docs/11](docs/11-策略示例合集.md) | 平台策略示例 |
| [docs/12](docs/12-常见问题FAQ.md) | 常见问题与注意事项 |
| [docs/13](docs/13-三方库与接口版本.md) | 三方库清单与接口版本变动 |
| [docs/14](docs/14-第三方库与Python环境.md) | Python3.5 / 3.11 可用第三方库 |
| [docs/15](docs/15-数据文档-财务指数行业.md) | 财务数据、指数数据、行业概念分类 |

## 策略示例

- [examples/01](examples/01_handle_data_每日主循环策略.py)：handle_data 主循环 + 5 日均线突破
- [examples/02](examples/02_run_daily_定时任务策略.py)：run_daily 每日定时任务
- [examples/03](examples/03_run_interval_秒级周期策略.py)：run_interval 秒级周期

上线前务必先在模拟盘跑通「编写 -> 回测 -> 模拟」链路。

## 资料来源

- ptrade.wiki：PTrade API 官方文档整理站（离线单页，已转 Markdown）
- ptrade.hxquant.com：海星量化 PTrade 文档中心（API、策略示例、常见问题、数据、三方库）
- 原始抓取 HTML 存于 reference/sources/，抓取与转换脚本见 research/scripts/

> 各券商内置版本与可开接口略有差异，开发与实盘前请以本平台终端「帮助 / 示例」为准。

## 下一步

1. 通读 docs/00 - docs/03 建立整体认知。
2. 运行 examples/ 三份示例，在模拟盘验证托管链路。
3. 在 strategies/ 下建立第一个策略目录，开始正式策略开发。
