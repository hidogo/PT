# -*- coding: utf-8 -*-
"""mylib.py - 用于验证 Ptrade 托管/研究能否 import 研究目录里的自建 .py 模块。
放到研究目录（get_research_path() 根下），再在策略里 import mylib 调用。"""

PROBE_OK = 'MYLIB_IMPORT_OK'


def hello(sec):
    return 'mylib.hello -> ' + str(sec)
