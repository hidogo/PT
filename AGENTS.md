# AGENTS.md — PT 仓库工作规则

## strategy.py 布置版本
- `strategies/buysell_core/strategy.py` 每次更新（版本号变更）后，须同步生成布置版本
  `strategies/buysell_core/strategy_deploy.py`（供云端上传）。
- 布置版本规则：剔除所有注释信息（`#` 注释与文件头说明），保留代码与
  `STRATEGY_VERSION`（部署核对用，日志首行 `buysell_core init version=..`）；
  压缩连续空行；`py_compile` 通过后与源文件一并提交推送。
- 生成方式参考：tokenize 剔除 COMMENT token 后 untokenize 重建（勿手动删，防破坏字符串内 `#`）。
- 云端部署以布置版本为准，日志核对 `STRATEGY_VERSION`；变更记录统一存
  `strategies/buysell_core/README.md`，strategy.py 文件头只保留版本/部署核对（布置版无文件头）。
