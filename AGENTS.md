# AGENTS.md — PT 仓库工作规则

## strategy.py 布置版本
- `strategies/buysell_core/strategy.py` 每次更新（版本号变更）后，须同步生成布置版本
  `strategies/buysell_core/strategy_deploy.py`（供云端上传）。
- 本地部署版同步是版本变更的完成标准之一：`strategy.py` 改完后立即用现有生成脚本
  （`scripts/tmp/tmp_YYYYMMDD_gen_deploy.py`，tokenize 剔除 COMMENT）重新生成
  `strategy_deploy.py`，脚本内置 AST 一致性校验通过，并核对
  `STRATEGY_VERSION` 与新增关键符号已进入布置版；未同步前不得汇报“实施完成”。
- 布置版本规则：剔除所有注释信息（`#` 注释与文件头说明），保留代码与
  `STRATEGY_VERSION`（部署核对用，日志首行 `buysell_core init version=..`）；
  压缩连续空行；`py_compile` 通过后与源文件一并提交推送。
- 生成方式参考：tokenize 剔除 COMMENT token 后 untokenize 重建（勿手动删，防破坏字符串内 `#`）。
- 云端部署以布置版本为准，日志核对 `STRATEGY_VERSION`；变更记录统一存
  `strategies/buysell_core/README.md`，strategy.py 文件头只保留版本/部署核对（布置版无文件头）。
