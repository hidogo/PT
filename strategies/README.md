# strategies/ —— 托管策略源码目录

把要开发的托管策略脚本放在本目录，按「每策略一子目录」组织，便于回测、模拟与实盘复用。

建议结构：

    strategies/
      <策略名>/
        strategy.py       # 策略主脚本（含 initialize / handle_data）
        notes.md          # 策略思路、参数、风控与回测结论
        params.json       # 策略可配置参数（如对应 set_parameters）

说明：
- 上线前务必在模拟盘验证：新建策略 -> 新建回测 -> 新建交易（模拟）。
- 数据/财务/指数见 docs/15，可用三方库见 docs/14，API 速查见 docs/00。
- 文档索引见根目录 README.md。
