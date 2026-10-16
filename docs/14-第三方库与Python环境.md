<!-- 第三方库与 Python 环境（整理自 海星量化 PTrade 文档中心：data/pip_list / pip_list_py311，详见 reference/ 对应文档） -->
<!-- 返回：见 README.md 文档索引 -->


> PTrade 编写托管策略时可导入的第三方库。不同券商的 PTrade 版本 Python 环境可能不同（常见 Python3.5 / Python3.11），以实际终端「帮助」确认。

## Python 3.5 支持的三方库



| 序号 | 三方库名称 | Python3.5三方库版本号 | 开源协议 | 开源协议地址 | 简介 |
|---|---|---|---|---|---|
|  | APScheduler | 3.3.1 | MIT License | https://github.com/agronholm/apscheduler/blob/master/LICENSE.txt | 任务调度库 |
|  | baostock | 0.8.9 | BSD License | https://spdx.org/licenses/BSD-1-Clause.html | 一个免费开源的证券数据平台库 |
|  | bcolz | 1.2.1 | BSD License | https://github.com/Blosc/bcolz/blob/master/CODE_OF_CONDUCT.md | 一个高效的列式数据存储和压缩库 |
|  | beautifulsoup4 | 4.6.0 | MIT License | https://git.launchpad.net/beautifulsoup/tree/LICENSE | HTML/XML解析库 |
|  | bleach | 1.5.0 | Apache Software License | https://github.com/mozilla/bleach/blob/main/LICENSE | HTML过滤库 |
|  | boto | 2.43.0 | MIT License | https://github.com/boto/boto/blob/develop/LICENSE | 用于与 AWS 服务交互的 Python SDK |
|  | Bottleneck | 1.0.0 | BSD License | https://github.com/pydata/bottleneck/blob/master/LICENSE | NumPy数组性能优化库 |
|  | bz2file | 0.98 | Apache Software License | https://spdx.org/licenses/Apache-2.0.html | bz2压缩文件读写 |
|  | cachetools | 3.1.0 | MIT License | https://github.com/tkem/cachetools/blob/master/LICENSE | 缓存字典和LRU缓存实现 |
|  | click | 4.0 | BSD License | https://github.com/pallets/click/blob/main/LICENSE.txt | 命令行参数解析库 |
|  | contextlib2 | 0.4.0 | Apache Software License | https://github.com/jazzband/contextlib2/blob/master/LICENSE.txt | 上下文管理器 |
|  | crypto | 1.4.1 | MIT License | https://github.com/chrissimpkins/crypto/blob/master/LICENSE | 提供加密算法和协议的 Python 库集合 |
|  | cx-Oracle | 8.0.1 | BSD License | https://github.com/oracle/python-cx_Oracle/blob/main/LICENSE.txt | 用于连接 Oracle 数据库的 Python 库 |
|  | cycler | 0.10.0 | BSD License | https://github.com/matplotlib/cycler/blob/main/LICENSE | matplotlib颜色循环库 |
|  | cyordereddict | 0.2.2 | BSD License | https://github.com/shoyer/cyordereddict/blob/master/LICENSE.txt | 提供排序字典实现的 Cython 扩展模块 |
|  | Cython | 0.22.1 | Apache Software License | https://github.com/cython/cython/blob/master/LICENSE.txt | 将Python转换为C扩展的编译器 |
|  | decorator | 4.0.10 | BSD License | https://github.com/micheles/decorator/blob/master/LICENSE.txt | 函数装饰器模块 |
|  | entrypoints | 0.2.2 | MIT License | https://github.com/takluyver/entrypoints/blob/master/LICENSE | 发现和加载Python软件包中的入口点 |
|  | fastcache | 1.0.2 | MIT License | https://github.com/pbrady/fastcache/blob/master/LICENSE | 快速且pythonic的缓存装饰器 |
|  | flameprof | 0.4 | MIT License | https://github.com/baverman/flameprof/blob/master/LICENSE | Python性能分析库 |
|  | gensim | 0.13.3 | LGPL-2.1-only | https://github.com/piskvorky/gensim/blob/develop/COPYING | 自然语言处理库 |
|  | gmssl | 3.2.2 | BSD License | https://github.com/py-gmssl/py-gmssl/blob/master/License | 国密算法加密库 |
|  | h5py | 2.6.0 | BSD License | https://github.com/h5py/h5py/blob/master/LICENSE | HDF5文件接口库 |
|  | hmmlearn | 0.2.0 | BSD License | https://github.com/hmmlearn/hmmlearn/blob/main/LICENSE.txt | 隐马尔可夫模型库 |
|  | hs-udata | 0.3.6 | MIT License | https://spdx.org/licenses/MIT.html | 用户数据收集库 |
|  | html5lib | 0.9999999 | MIT License | https://github.com/html5lib/html5lib-python/blob/master/LICENSE | HTML解析库 |
|  | ipykernel | 4.5.0 | BSD License | https://github.com/ipython/ipykernel/blob/main/LICENSE | Jupyter内核库 |
|  | ipython | 5.1.0 | BSD License | https://github.com/ipython/ipython/blob/main/./LICENSE | 交互式Python Shell |
|  | ipython-genutils | 0.1.0 | BSD License | https://github.com/ipython/ipython_genutils/blob/master/COPYING.md | IPython实用功能库 |
|  | ipywidgets | 5.2.2 | BSD License | https://github.com/jupyter-widgets/ipywidgets/blob/main/LICENSE | Jupyter交互式小部件 |
|  | jieba | 0.38 | MIT License | https://github.com/fxsjy/jieba/blob/master/LICENSE | 中文文本分词库 |
|  | Jinja2 | 2.8 | BSD License | https://github.com/pallets/jinja/blob/main/LICENSE.txt | 模板引擎库 |
|  | jsonpickle | 1.0 | BSD License | https://github.com/jsonpickle/jsonpickle/blob/main/LICENSE | Python对象与JSON相互转换的序列化/反序列化库 |
|  | jsonschema | 2.5.1 | MIT License | https://github.com/python-jsonschema/jsonschema/blob/main/COPYING | JSON模式验证库 |
|  | jupyter | 1.0.0 | BSD License | https://github.com/jupyter/jupyter/blob/master/LICENSE | Jupyter项目工具集 |
|  | jupyter-client | 4.4.0 | BSD License | https://github.com/jupyter/jupyter_client/blob/main/LICENSE | Jupyter客户端库 |
|  | jupyter-console | 5.0.0 | BSD License | https://github.com/jupyter/jupyter_console/blob/main/LICENSE | Jupyter终端控制台 |
|  | jupyter-core | 4.2.0 | BSD License | https://github.com/jupyter/jupyter_core/blob/main/LICENSE | Jupyter核心软件包 |
|  | jupyter-kernel-gateway | 1.1.1 | BSD License | https://github.com/jupyter-server/kernel_gateway/blob/main/LICENSE.md | Jupyter 内核的独立 API 网关 |
|  | Keras | 2.3.1 | Apache Software License | https://github.com/keras-team/keras/blob/master/LICENSE | 深度学习高级API库 |
|  | Keras-Applications | 1.0.8 | MIT License | https://github.com/keras-team/keras-applications/blob/master/LICENSE | Keras 的预训练模型组件 |
|  | Keras-Preprocessing | 1.1.0 | MIT License | https://github.com/keras-team/keras-preprocessing/blob/master/LICENSE | Keras 的数据预处理工具集 |
|  | line-profiler | 2.1.2 | BSD License | https://github.com/pyutils/line_profiler/blob/main/LICENSE.txt | 逐行分析 Python 代码性能的工具 |
|  | Logbook | 1.4.3 | BSD License | https://github.com/getlogbook/logbook/blob/develop/LICENSE | 日志记录库 |
|  | lxml | 4.5.0 | BSD License | https://github.com/lxml/lxml/blob/master/LICENSE.txt | XML处理库 |
|  | Markdown | 2.2.0 | BSD License | https://github.com/Python-Markdown/markdown/blob/master/LICENSE.md | Markdown解析库 |
|  | MarkupSafe | 0.23 | BSD License | https://github.com/pallets/markupsafe/blob/main/LICENSE.txt | 文本标记转义库 |
|  | matplotlib | 1.5.3 | Python Software Foundation License | https://github.com/matplotlib/matplotlib/tree/main/LICENSE | 二维绘图库 |
|  | memory_profiler | 0.61.0 | BSD License | https://github.com/pythonprofilers/memory_profiler/blob/master/COPYING | 内存性能分析库 |
|  | mistune | 0.7.3 | BSD License | https://github.com/lepture/mistune/blob/main/LICENSE | Markdown解析库 |
|  | Naked | 0.1.31 | MIT License | https://github.com/chrissimpkins/naked/blob/master/README.md | 清洁、轻量的Python包装 |
|  | nbconvert | 4.2.0 | BSD License | https://github.com/jupyter/nbconvert/blob/main/LICENSE | Jupyter Notebook转换工具 |
|  | nbformat | 4.1.0 | BSD License | https://github.com/jupyter/nbformat/blob/main/LICENSE | Jupyter Notebook文档格式 |
|  | networkx | 1.9.1 | BSD License | https://github.com/networkx/networkx/blob/main/LICENSE.txt | 网络分析库 |
|  | nose | 1.3.6 | GNU Library or Lesser General Public License (LGPL) | https://github.com/nose-devs/nose/blob/master/setup.py | 单元测试框架 |
|  | notebook | 4.2.3 | BSD License | https://github.com/jupyter/notebook/blob/main/LICENSE | Jupyter交互式计算笔记本 |
|  | numexpr | 2.6.1 | MIT License | https://github.com/pydata/numexpr/blob/master/LICENSE.txt | 高性能数组表达式评估库 |
|  | numpy | 1.11.2 | BSD License | https://github.com/numpy/numpy/blob/main/LICENSE.txt | 科学计算基础库 |
|  | pandas | 0.23.4 | BSD License | https://github.com/pandas-dev/pandas/blob/main/LICENSE | 数据分析库 |
|  | patsy | 0.4.0 | BSD License | https://github.com/pydata/patsy/blob/master/LICENSE.txt | 描述统计模型公式的Python包 |
|  | pexpect | 4.2.1 | ISC License (ISCL) | https://github.com/pexpect/pexpect/blob/master/LICENSE | 控制和自动化交互程序 |
|  | pickleshare | 0.7.4 | MIT License | https://github.com/ipython/pickleshare/blob/master/LICENSE | 小型快速的键值对数据库 |
|  | pip | 9.0.1 | MIT License | https://github.com/pypa/pip/blob/main/LICENSE.txt | Python包管理工具 |
|  | pkgconfig | 1.0.0 | MIT License | https://github.com/matze/pkgconfig/blob/master/LICENSE | 解析pkg-config文件 |
|  | prompt-toolkit | 1.0.8 | BSD License | https://github.com/prompt-toolkit/python-prompt-toolkit/blob/main/LICENSE | 命令行界面应用框架 |
|  | protobuf | 3.3.0 | 3-Clause BSD License | https://github.com/protocolbuffers/protobuf/blob/main/LICENSE | Protocol Buffers序列化库 |
|  | psutil | 5.9.5 | BSD License | https://github.com/giampaolo/psutil/blob/master/LICENSE | 系统监控和系统资源信息 |
|  | psycopg2-binary | 2.8.6 | GNU Library or Lesser General Public License (LGPL) | https://github.com/psycopg/psycopg2/blob/master/LICENSE | PostgreSQL数据库适配器 |
|  | ptvsd | 2.2.0 | Eclipse Public License 2.0 (EPL-2.0) | https://github.com/microsoft/ptvsd/blob/master/LICENSE | Python调试器后端 |
|  | ptyprocess | 0.5.1 | ISC License (ISCL) | https://github.com/pexpect/ptyprocess/blob/master/LICENSE | 伪终端进程工具 |
|  | PuLP | 2.7.0 | BSD License | https://github.com/coin-or/pulp/blob/master/LICENSE | 线性编程模型库 |
|  | PyBrain | 0.3 | BSD License | https://github.com/pybrain/pybrain/blob/master/LICENSE | 机器学习库 |
|  | pycrypto | 2.6.1 | Public domain | https://github.com/pycrypto/pycrypto?tab=License-1-ov-file | 提供加密和解密功能的 Python 库 |
|  | Pygments | 2.1.3 | BSD License | https://github.com/pygments/pygments/blob/master/LICENSE | 通用语法高亮库 |
|  | pykalman | 0.9.5 | BSD License | https://github.com/pykalman/pykalman/blob/main/LICENSE | 卡尔曼滤波器实现 |
|  | PyMySQL | 0.9.3 | MIT License | https://github.com/PyMySQL/PyMySQL/blob/main/LICENSE | 一个用于与MySQL数据库交互的库 |
|  | pyparsing | 2.1.10 | MIT License | https://github.com/pyparsing/pyparsing/blob/master/LICENSE | 通用解析器组件库 |
|  | pypinyin | 0.50.0 | MIT License | https://github.com/mozillazg/python-pinyin/blob/master/LICENSE.txt | 汉字拼音转换模块/工具 |
|  | python-dateutil | 2.7.5 | Apache Software License | https://github.com/dateutil/dateutil/blob/master/LICENSE | 日期时间处理库 |
|  | pytz | 2015.4 | MIT License | https://github.com/stub42/pytz/blob/master/LICENSE.txt | 时区数据库和时间操作库 |
|  | PyWavelets | 0.4.0 | MIT License | https://github.com/PyWavelets/pywt/blob/main/LICENSE | 小波变换和数字信号处理 |
|  | PyYAML | 3.13 | MIT License | https://github.com/yaml/pyyaml/blob/main/LICENSE | YAML解析器和发射器 |
|  | pyzmq | 16.1.0.dev0 | BSD License | https://github.com/zeromq/pyzmq/blob/main/LICENSE.md | ZeroMQ的Python绑定 |
|  | qtconsole | 4.2.1 | BSD License | https://github.com/spyder-ide/qtconsole/blob/main/LICENSE | Jupyter Qt控制台 |
|  | requests | 2.7.0 | Apache Software License | https://github.com/psf/requests/blob/main/LICENSE | HTTP请求库 |
|  | retrying | 1.3.3 | Apache Software License | https://github.com/groodt/retrying/blob/main/LICENSE.txt | 函数调用重试库 |
|  | scikit-learn | 0.18 | BSD License | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING | 机器学习Python工具包 |
|  | scipy | 0.18.0 | BSD License | https://github.com/scipy/scipy/blob/main/LICENSE.txt | 科学计算基础库 |
|  | seaborn | 0.7.1 | BSD License | https://github.com/mwaskom/seaborn/blob/master/LICENSE.md | 数据可视化库 |
|  | setuptools | 28.7.1 | MIT License | https://github.com/pypa/setuptools/blob/main/LICENSE | Python包管理工具 |
|  | setuptools-scm | 3.1.0 | MIT License | https://github.com/pypa/setuptools-scm/blob/main/LICENSE | setuptools的SCM扩展 |
|  | shellescape | 3.4.1 | MIT License | https://github.com/chrissimpkins/shellescape/blob/master/docs/LICENSE | Shell参数转义 |
|  | simplegeneric | 0.8.1 | Zope Public License | https://github.com/conda-forge-admin/python-simplegeneric-feedstock/blob/master/LICENSE | 简单的泛函数装饰器 |
|  | simplejson | 3.17.0 | MIT License | https://github.com/simplejson/simplejson/blob/master/LICENSE.txt | JSON编码/解码器 |
|  | six | 1.10.0 | MIT License | https://github.com/benjaminp/six/blob/main/LICENSE | Python 2和3兼容性工具 |
|  | sklearn | 0.0 | BSD License | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING | 机器学习和数据挖掘的 Python 库(scikit-learn) |
|  | smart-open | 1.3.5 | MIT License | https://github.com/piskvorky/smart_open/blob/develop/LICENSE | 流式传输大型文件 |
|  | SQLAlchemy | 1.0.8 | MIT License | https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE | SQL工具包和对象关系映射器 |
|  | statsmodels | 0.10.2 | BSD License | https://github.com/statsmodels/statsmodels/blob/main/LICENSE.txt | 统计建模和计量经济学 |
|  | sxsc-tushare | 20240927 | BSD License | UNKNOWN | 股票数据处理工具包 |
|  | tables | 3.3.0 | BSD License | https://github.com/PyTables/PyTables/blob/master/LICENSE.txt | 管理结构化和非结构化数据的层次数据库 |
|  | tabulate | 0.7.5 | MIT License | https://github.com/astanin/python-tabulate/blob/master/LICENSE | 格式化数据为表格形式的 Python 库 |
|  | TA-Lib | 0.4.10 | BSD License | https://github.com/TA-Lib/ta-lib-python/blob/master/LICENSE | 技术分析库 |
|  | tensorflow | 1.3.0rc1 | Apache Software License | https://github.com/tensorflow/tensorflow/blob/master/LICENSE | 机器学习平台 |
|  | tensorflow-tensorboard | 0.1.2 | Apache Software License | https://github.com/tensorflow/tensorboard/blob/master/LICENSE | TensorFlow的可视化工具 |
|  | terminado | 0.6 | BSD License | https://github.com/jupyter/terminado/blob/main/LICENSE | Tornado终端仿真 |
|  | Theano | 0.8.2 | BSD License | https://github.com/Theano/Theano/blob/master/doc/LICENSE.txt | 深度学习和数值计算的 Python 库 |
|  | toolz | 0.7.4 | BSD License | https://github.com/pytoolz/toolz/blob/master/LICENSE.txt | 高性能函数式工具 |
|  | tornado | 4.4.2 | Apache Software License | https://github.com/tornadoweb/tornado/blob/master/LICENSE | Web框架和异步网络库 |
|  | traitlets | 4.3.1 | BSD License | https://github.com/ipython/traitlets/blob/main/LICENSE | 配置和应用选项的轻量级trait系统 |
|  | tushare | 1.2.48 | BSD License | https://github.com/waditu/tushare/blob/master/LICENSE | 股票数据接口库 |
|  | tzlocal | 1.3 | MIT License | https://github.com/regebro/tzlocal/blob/master/LICENSE.txt | 获取本地时区 |
|  | walrus | 0.9.3 | MIT License | https://github.com/coleifer/walrus/blob/master/LICENSE | 一个用于与Redis数据库交互的库 |
|  | wcwidth | 0.1.7 | MIT License | https://github.com/jquast/wcwidth/blob/master/LICENSE | 计算字符或字符串宽度的模块 |
|  | websocket-client | 0.57.0 | BSD License | https://github.com/websocket-client/websocket-client/blob/master/LICENSE | WebSocket客户端库 |
|  | Werkzeug | 0.12.2 | BSD License | https://github.com/pallets/werkzeug/blob/main/LICENSE.txt | WSGI应用工具集 |
|  | wheel | 0.29.0 | MIT License | https://github.com/pypa/wheel/blob/main/LICENSE.txt | Python分发的打包格式 |
|  | widgetsnbextension | 1.2.6 | BSD License | https://github.com/jupyter-widgets/ipywidgets/blob/main/python/widgetsnbextension/LICENSE | IPython HTML widgets |
|  | xcsc-tushare | 1.0.0 | BSD License | UNKNOWN | 股票数据处理工具包 |
|  | xgboost | 0.6a2 | Apache Software License | https://github.com/dmlc/xgboost/blob/master/LICENSE | 提升框架用于大规模机器学习 |
|  | xlrd | 1.1.0 | BSD License | https://github.com/python-excel/xlrd/blob/master/LICENSE | Excel文件读取库 |
|  | xlwt | 1.3.0 | BSD License | https://github.com/python-excel/xlwt/blob/master/LICENSE | Excel文件写入库 |



---

## Python 3.11 支持的三方库



| 序号 | 三方库名称 | Python3.11三方库版本号 | 开源协议 | 开源协议地址 | 简介 |
|---|---|---|---|---|---|
|  | absl-py | 1.4.0 | Apache Software License | https://github.com/abseil/abseil-py/blob/main/LICENSE | Google的Abseil Python通用库 |
|  | aiohttp | 3.8.5 | Apache Software License | https://github.com/aio-libs/aiohttp/blob/master/LICENSE.txt | 基于asyncio的HTTP客户端/服务器框架 |
|  | aiosignal | 1.3.1 | Apache Software License | https://github.com/aio-libs/aiosignal/blob/master/LICENSE | asyncio优化的信号模块 |
|  | alembic | 1.11.1 | MIT License | https://github.com/sqlalchemy/alembic/blob/main/LICENSE | 数据库迁移工具 |
|  | anyio | 3.7.1 | MIT License | https://github.com/agronholm/anyio/blob/master/LICENSE | 异步IO库 |
|  | APScheduler | 3.10.0 | MIT License | https://github.com/agronholm/apscheduler/blob/master/LICENSE.txt | 任务调度库 |
|  | argon2-cffi | 21.3.0 | MIT License | https://github.com/hynek/argon2-cffi/blob/main/LICENSE | Argon2密码哈希算法的CFFI绑定 |
|  | argon2-cffi-bindings | 21.2.0 | MIT License | https://github.com/hynek/argon2-cffi-bindings/blob/main/LICENSE | Argon2密码哈希算法的Python绑定 |
|  | arrow | 1.2.3 | Apache Software License | https://github.com/arrow-py/arrow/blob/master/LICENSE | 日期时间操作库 |
|  | asttokens | 2.2.1 | Apache 2.0 | https://github.com/gristlabs/asttokens/blob/master/LICENSE | 抽象语法树操作库 |
|  | astunparse | 1.6.3 | BSD License | https://github.com/simonpercivall/astunparse/blob/main/LICENSE | 抽象语法树转换为python代码库 |
|  | asyncache | 0.3.1 | MIT License | https://github.com/hephex/asyncache/blob/master/LICENSE | 异步缓存支持库 |
|  | async-generator | 1.10 | Apache Software License | https://github.com/python-trio/async_generator/blob/master/LICENSE | 异步生成器工具库 |
|  | async-lru | 2.0.4 | MIT License | https://github.com/aio-libs/async-lru/blob/master/LICENSE | 一个用于asyncio的LRU缓存装饰器 |
|  | async-timeout | 4.0.2 | Apache Software License | https://github.com/aio-libs/async-timeout/blob/master/LICENSE | 异步操作超时处理库 |
|  | attrs | 23.1.0 | MIT License | https://github.com/python-attrs/attrs/blob/main/LICENSE | 类属性管理库 |
|  | Babel | 2.12.1 | BSD License | https://github.com/python-babel/babel/blob/master/LICENSE | JavaScript编译器,可将ES6+代码转换为向后兼容的JavaScript |
|  | backcall | 0.2.0 | BSD License | https://github.com/takluyver/backcall/blob/master/LICENSE | IPython内省和自动补全库 |
|  | baostock | 0.8.9 | BSD License | https://spdx.org/licenses/BSD-1-Clause.html | 一个免费开源的证券数据平台库 |
|  | bcrypt | 4.0.1 | Apache Software License | https://github.com/pyca/bcrypt/blob/main/LICENSE | 一个跨平台的密码哈希库 |
|  | beautifulsoup4 | 4.11.2 | MIT License | https://git.launchpad.net/beautifulsoup/tree/LICENSE | HTML/XML解析库 |
|  | bleach | 6.0.0 | Apache Software License | https://github.com/mozilla/bleach/blob/main/LICENSE | HTML过滤库 |
|  | blinker | 1.6.2 | MIT License | https://github.com/pallets-eco/blinker/blob/main/LICENSE.txt | 一个用于实现简单的发布-订阅模式的库 |
|  | blosc2 | 2.0.0 | BSD License | https://github.com/Blosc/python-blosc2/blob/main/LICENSE.txt | 压缩库 |
|  | Bottleneck | 1.3.7 | BSD License | https://github.com/pydata/bottleneck/blob/master/LICENSE | NumPy数组性能优化库 |
|  | bs4 | 0.0.2 | MIT License | https://git.launchpad.net/beautifulsoup/tree/LICENSE | beautifulsoup4的缩写 |
|  | bz2file | 0.98 | Apache Software License | https://spdx.org/licenses/Apache-2.0.html | bz2压缩文件读写 |
|  | cachetools | 5.3.0 | MIT License | https://github.com/tkem/cachetools/blob/master/LICENSE | 缓存字典和LRU缓存实现 |
|  | certifi | 2023.5.7 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi/blob/master/LICENSE | 提供Mozilla可信CA证书捆绑 |
|  | certipy | 0.1.3 | BSD License | https://github.com/LLNL/certipy/blob/main/LICENSE | 加密证书处理库 |
|  | cffi | 1.15.1 | MIT License | https://github.com/python-cffi/cffi/blob/main/LICENSE | 调用C代码的外部函数接口库 |
|  | charset-normalizer | 3.2.0 | MIT License | https://github.com/jawah/charset_normalizer/blob/master/LICENSE | 字符编码识别库 |
|  | clarabel | 0.6.0 | Apache-2.0 | https://github.com/oxfordcontrol/Clarabel.rs/blob/main/LICENSE.md | 一个用于处理日期和时间的库 |
|  | click | 8.1.3 | BSD License | https://github.com/pallets/click/blob/main/LICENSE.txt | 命令行参数解析库 |
|  | clr-loader | 0.2.5 | MIT License | https://github.com/pythonnet/clr-loader/blob/master/LICENSE | 一个用于加载.NET程序集的库 |
|  | comm | 0.1.3 | BSD License | https://github.com/ipython/comm/blob/main/LICENSE | 通信才苏库 |
|  | contextlib2 | 21.6.0 | Apache Software License | https://github.com/jazzband/contextlib2/blob/master/LICENSE.txt | 上下文管理器 |
|  | contourpy | 1.1.0 | BSD License | https://github.com/contourpy/contourpy/blob/main/LICENSE | 计算库 |
|  | cryptography | 41.0.2 | Apache Software License | https://github.com/pyca/cryptography/blob/main/./LICENSE | 加密库 |
|  | cvxpy | 1.4.1 | Apache License, Version 2.0 | https://github.com/cvxpy/cvxpy/blob/master/LICENSE | 一个用于凸优化的库 |
|  | cx_Oracle | 8.3.0 | BSD License | https://github.com/oracle/python-cx_Oracle/blob/main/LICENSE.txt | 用于连接 Oracle 数据库的 Python 库 |
|  | cycler | 0.11.0 | BSD License | https://github.com/matplotlib/cycler/blob/main/LICENSE | matplotlib颜色循环库 |
|  | Cython | 3.0.2 | Apache Software License | https://github.com/cython/cython/blob/master/LICENSE.txt | 将Python转换为C扩展的编译器 |
|  | debugpy | 1.6.7 | Eclipse Public License 2.0 (EPL-2.0) | https://github.com/microsoft/debugpy/blob/main/LICENSE | Python调试器后端 |
|  | decorator | 5.1.1 | BSD License | https://github.com/micheles/decorator/blob/master/LICENSE.txt | 函数装饰器模块 |
|  | defusedxml | 0.7.1 | Python Software Foundation License | https://github.com/tiran/defusedxml/blob/main/LICENSE | XML操作库 |
|  | docker | 6.1.3 | Apache Software License | https://github.com/docker/docker-py/blob/main/LICENSE | 用于与 Docker 引擎交互的 Python 库 |
|  | dockerspawner | 12.1.0 | BSD License | https://github.com/jupyterhub/dockerspawner/blob/main/LICENSE | Jupyter Notebook 的 Docker 容器启动器 |
|  | dtaidistance | 2.3.13 | Apache-2.0 | https://github.com/wannesm/dtaidistance/blob/master/LICENSE | 探索时间序列分析的利器 |
|  | ecos | 2.0.12 | GPLv3 | https://github.com/embotech/ecos/blob/develop/COPYING | 一个用于二次优化的库 |
|  | empyrical | 0.5.5 | Apache Software License | https://github.com/quantopian/empyrical/blob/master/LICENSE | 一个用于金融分析的库 |
|  | entrypoints | 0.4 | MIT License | https://github.com/takluyver/entrypoints/blob/master/LICENSE | 发现和加载Python软件包中的入口点 |
|  | escapism | 1.0.1 | MIT License | https://github.com/minrk/escapism/blob/main/LICENSE | 用于转义不安全的文件名和路径 |
|  | et-xmlfile | 1.1.0 | MIT License | https://foss.heptapod.net/openpyxl/et_xmlfile/-/blob/branch/1.1/LICENCE.rst | 用于编辑Excel XML格式文件的库 |
|  | executing | 1.2.0 | MIT License | https://github.com/alexmojaki/executing/blob/master/LICENSE.txt | 正在执行代码的栈跟踪 |
|  | fastapi | 0.100.0 | MIT License | https://github.com/fastapi/fastapi/blob/master/LICENSE | 一个高性能 Web 框架，用于构建 API |
|  | fastcache | 1.1.0 | MIT License | https://github.com/pbrady/fastcache/blob/master/LICENSE | 快速且pythonic的缓存装饰器 |
|  | fastjsonschema | 2.17.1 | BSD License | https://github.com/horejsek/python-fastjsonschema/blob/master/LICENSE | JSON schema验证库 |
|  | flameprof | 0.4 | MIT License | https://github.com/baverman/flameprof/blob/master/LICENSE | Python性能分析库 |
|  | Flask | 2.3.2 | BSD License | https://github.com/pallets/flask/blob/main/LICENSE.txt | 一个流行的 Python 微型 Web 框架 |
|  | flatbuffers | 23.5.26 | Apache Software License | https://github.com/google/flatbuffers/blob/master/LICENSE | 跨平台序列化库 |
|  | fonttools | 4.41.0 | MIT License | https://github.com/fonttools/fonttools/blob/main/./LICENSE | 字体处理库 |
|  | fqdn | 1.5.1 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/ypcrts/fqdn/blob/develop/LICENSE | 获取系统全限定域名 |
|  | frozenlist | 1.4.0 | Apache Software License | https://github.com/aio-libs/frozenlist/blob/master/LICENSE | 一个不可变的Python列表 |
|  | fst-pso | 1.8.1 | GNU Lesser General Public License v3.0 | https://github.com/aresio/fst-pso/blob/master/LICENSE | 粒子群优化算法库 |
|  | funcsigs | 1.0.2 | Apache Software License | https://github.com/aliles/funcsigs/blob/master/LICENSE | 一个用于处理函数签名的库 |
|  | gast | 0.4.0 | BSD License | https://github.com/serge-sans-paille/gast/blob/master/LICENSE | Python AST解析库 |
|  | gensim | 4.3.3 | LGPL-2.1-only | https://github.com/piskvorky/gensim/blob/develop/COPYING | 自然语言处理库 |
|  | gmssl | 3.2.2 | BSD License | https://github.com/py-gmssl/py-gmssl/blob/master/License | 国密算法加密库 |
|  | google-auth | 2.22.0 | Apache Software License | https://github.com/googleapis/google-auth-library-python/blob/main/LICENSE | Google Auth库 |
|  | google-auth-oauthlib | 1.0.0 | Apache Software License | https://github.com/googleapis/google-auth-library-python-oauthlib/blob/main/LICENSE | Google Auth Oauthlib库 |
|  | google-pasta | 0.2.0 | Apache Software License | https://github.com/google/pasta/blob/master/LICENSE | Python AST解析库 |
|  | gqdata | 0.1.5 | UNKNOWN | UNKNOWN | 一个用于处理图数据库的库 |
|  | graphviz | 0.20.1 | MIT License | https://github.com/xflr6/graphviz/blob/master/LICENSE.txt | 图可视化库 |
|  | greenlet | 2.0.2 | MIT License | https://github.com/python-greenlet/greenlet/blob/master/./LICENSE | 协程库 |
|  | grpcio | 1.56.0 | Apache Software License | https://github.com/grpc/grpc/blob/master/LICENSE | gRPC库 |
|  | h11 | 0.14.0 | MIT License | https://github.com/python-hyper/h11/blob/master/LICENSE.txt | 纯 Python 实现的 HTTP/1.1 协议库 |
|  | h5py | 3.8.0 | BSD License | https://github.com/h5py/h5py/blob/master/LICENSE | HDF5文件接口库 |
|  | hmmlearn | 0.3.0 | BSD License | https://github.com/hmmlearn/hmmlearn/blob/main/LICENSE.txt | 隐马尔可夫模型库 |
|  | hs-udata | 0.3.8 | MIT License | https://spdx.org/licenses/MIT.html | 用户数据收集库 |
|  | html5lib | 1.1 | MIT License | https://github.com/html5lib/html5lib-python/blob/master/LICENSE | HTML解析库 |
|  | idna | 3.4 | BSD License | https://github.com/kjd/idna/blob/master/LICENSE.md | 国际化域名转换库 |
|  | ipykernel | 6.21.2 | BSD License | https://github.com/ipython/ipykernel/blob/main/LICENSE | Jupyter内核库 |
|  | ipython | 8.10.0 | BSD License | https://github.com/ipython/ipython/blob/main/./LICENSE | 交互式Python Shell |
|  | ipython-genutils | 0.2.0 | BSD License | https://github.com/ipython/ipython_genutils/blob/master/COPYING.md | IPython实用功能库 |
|  | ipywidgets | 8.0.4 | BSD License | https://github.com/jupyter-widgets/ipywidgets/blob/main/LICENSE | Jupyter交互式小部件 |
|  | isoduration | 20.11.0 | ISC License (ISCL) | https://github.com/bolsote/isoduration/blob/master/LICENSE | ISO8601时间段解析库 |
|  | itsdangerous | 2.1.2 | BSD License | https://github.com/pallets/itsdangerous/blob/main/LICENSE.txt | 用于生成和验证签名的数据序列化库 |
|  | jax | 0.4.18 | Apache-2.0 | https://github.com/jax-ml/jax/blob/main/LICENSE | 数值计算和机器学习库 |
|  | jaxlib | 0.4.18 | Apache-2.0 | https://github.com/jax-ml/jax/blob/main/LICENSE | 一个用于自动微分的库 |
|  | jedi | 0.18.2 | MIT License | https://github.com/davidhalter/jedi/blob/master/LICENSE.txt | Python自动补全库 |
|  | jieba | 0.42.1 | MIT License | https://github.com/fxsjy/jieba/blob/master/LICENSE | 中文文本分词库 |
|  | Jinja2 | 3.1.2 | BSD License | https://github.com/pallets/jinja/blob/main/LICENSE.txt | 模板引擎库 |
|  | joblib | 1.3.1 | BSD License | https://github.com/joblib/joblib/blob/main/LICENSE.txt | 机器学习任务工具库 |
|  | json5 | 0.9.14 | Apache Software License | https://github.com/dpranke/pyjson5/blob/main/LICENSE | JSON的超集,支持更多数据类型 |
|  | jsonpickle | 3.0.2 | BSD License | https://github.com/jsonpickle/jsonpickle/blob/main/LICENSE | Python对象与JSON相互转换的序列化/反序列化库 |
|  | jsonpointer | 2.4 | BSD License | https://github.com/stefankoegl/python-json-pointer/blob/master/LICENSE.txt | JSON指针实现库 |
|  | jsonschema | 4.17.3 | MIT License | https://github.com/python-jsonschema/jsonschema/blob/main/COPYING | JSON模式验证库 |
|  | jupyter | 1.0.0 | BSD License | https://github.com/jupyter/jupyter/blob/master/LICENSE | Jupyter项目工具集 |
|  | jupyter-console | 6.5.1 | BSD License | https://github.com/jupyter/jupyter_console/blob/main/LICENSE | Jupyter终端控制台 |
|  | jupyter-events | 0.6.3 | BSD License | https://github.com/jupyter/jupyter_events/blob/main/LICENSE | Jupyter事件处理库 |
|  | jupyter-lsp | 2.2.0 | BSD License | https://github.com/jupyter-lsp/jupyterlab-lsp/blob/main/LICENSE | Jupyter Notebook的语言服务器协议集成 |
|  | jupyter-telemetry | 0.1.0 | BSD License | https://github.com/jupyter/telemetry/blob/master/LICENSE | Jupyter遥测库 |
|  | jupyter_client | 7.4.9 | BSD License | https://github.com/jupyter/jupyter_client/blob/main/LICENSE | Jupyter客户端库 |
|  | jupyter_core | 5.2.0 | BSD License | https://github.com/jupyter/jupyter_core/blob/main/LICENSE | Jupyter核心软件包 |
|  | jupyter_server | 2.7.0 | BSD License | https://github.com/jupyter-server/jupyter_server/blob/main/LICENSE | Jupyter服务的核心组件 |
|  | jupyter_server_terminals | 0.4.4 | BSD License | https://github.com/jupyter-server/jupyter_server_terminals/blob/main/LICENSE | Jupyter服务器终端 |
|  | jupyterhub | 4.0.1 | BSD License | https://github.com/jupyterhub/jupyterhub/blob/main/LICENSE | 多用户Jupyter服务器 |
|  | jupyterlab | 4.0.5 | BSD License | https://github.com/jupyterlab/jupyterlab/blob/main/LICENSE | Jupyter Notebook的下一代Web界面 |
|  | jupyterlab-language-pack-zh-CN | 4.0.post2 | BSD License | https://github.com/jupyterlab/language-packs/blob/main/LICENSE.txt | 一个用于JupyterLab的中文语言包 |
|  | jupyterlab-pygments | 0.2.2 | BSD License | https://github.com/jupyterlab/jupyterlab_pygments/blob/main/LICENSE | JupyterLab代码高亮 |
|  | jupyterlab-widgets | 3.0.8 | BSD License | https://github.com/jupyter-widgets/ipywidgets/blob/main/LICENSE | JupyterLab交互式小部件 |
|  | jupyterlab_server | 2.24.0 | BSD License | https://github.com/jupyterlab/jupyterlab_server/blob/main/LICENSE | JupyterLab的服务器组件 |
|  | keras | 2.13.1 | Apache Software License | https://github.com/keras-team/keras/blob/master/LICENSE | 深度学习高级API库 |
|  | kiwisolver | 1.4.4 | BSD License | https://github.com/nucleic/kiwi/blob/main/LICENSE | 数学方程求解器 |
|  | libclang | 16.0.6 | Apache Software License | https://github.com/sighingnow/libclang/blob/master/LICENSE.TXT | C语言静态分析库 |
|  | line_profiler | 4.1.3 | BSD License | https://github.com/pyutils/line_profiler/blob/main/LICENSE.txt | 逐行分析 Python 代码性能的工具 |
|  | Logbook | 1.5.3 | BSD License | https://github.com/getlogbook/logbook/blob/develop/LICENSE | 日志记录库 |
|  | loguru | 0.7.0 | MIT License | https://github.com/Delgan/loguru/blob/master/LICENSE | 优雅日志记录库 |
|  | lxml | 4.9.2 | BSD License | https://github.com/lxml/lxml/blob/master/LICENSE.txt | XML处理库 |
|  | Mako | 1.2.4 | MIT License | https://github.com/sqlalchemy/mako/blob/main/LICENSE | 模板库 |
|  | Markdown | 3.4.1 | BSD License | https://github.com/Python-Markdown/markdown/blob/master/LICENSE.md | Markdown解析库 |
|  | markdown-it-py | 3.0.0 | MIT License | https://github.com/executablebooks/markdown-it-py/blob/master/./LICENSE | Markdown解析库 |
|  | MarkupSafe | 2.1.2 | BSD License | https://github.com/pallets/markupsafe/blob/main/LICENSE.txt | 文本标记转义库 |
|  | matplotlib | 3.7.0 | Python Software Foundation License | https://github.com/matplotlib/matplotlib/tree/main/LICENSE | 二维绘图库 |
|  | matplotlib-inline | 0.1.6 | BSD 3-Clause | https://github.com/ipython/matplotlib-inline/blob/main/LICENSE | Jupyter Notebook中的matplotlib内联支持 |
|  | mdurl | 0.1.2 | MIT License | https://github.com/executablebooks/mdurl/blob/master/LICENSE | Markdown URL处理库 |
|  | memory-profiler | 0.61.0 | BSD License | https://github.com/pythonprofilers/memory_profiler/blob/master/COPYING | 内存性能分析库 |
|  | miniful | 0.0.6 | GNU Lesser General Public License v3.0 | https://github.com/aresio/miniful/blob/master/LICENSE | 轻量级GUI库 |
|  | mistune | 2.0.5 | BSD License | https://github.com/lepture/mistune/blob/main/LICENSE | Markdown解析库 |
|  | ml-dtypes | 0.2.0 | Apache Software License | https://github.com/jax-ml/ml_dtypes/blob/main/./LICENSE | 机器学习数据类型 |
|  | mplfinance | 0.12.10b0 | BSD License | https://github.com/matplotlib/mplfinance/blob/master/LICENSE | 一个用于金融数据可视化的库 |
|  | msgpack | 1.0.5 | Apache Software License | https://github.com/msgpack/msgpack-python/blob/main/COPYING | 序列化库 |
|  | multidict | 6.0.4 | Apache Software License | https://github.com/aio-libs/multidict/blob/master/LICENSE | 一个dict的子类,可存储多个值 |
|  | Naked | 0.1.32 | MIT License | https://github.com/chrissimpkins/naked/blob/master/README.md | 清洁、轻量的Python包装 |
|  | nbclassic | 1.0.0 | BSD License | https://github.com/jupyter/nbclassic/blob/main/LICENSE | Jupyter Notebook服务 |
|  | nbclient | 0.8.0 | BSD License | https://github.com/jupyter/nbclient/blob/main/LICENSE | Jupyter Notebook客户端库 |
|  | nbconvert | 7.2.9 | BSD License | https://github.com/jupyter/nbconvert/blob/main/LICENSE | Jupyter Notebook转换工具 |
|  | nbformat | 5.7.3 | BSD License | https://github.com/jupyter/nbformat/blob/main/LICENSE | Jupyter Notebook文档格式 |
|  | nest-asyncio | 1.5.6 | BSD License | https://github.com/erdewit/nest_asyncio/blob/master/LICENSE | 嵌套的asyncio事件循环 |
|  | networkx | 3.0 | BSD License | https://github.com/networkx/networkx/blob/main/LICENSE.txt | 网络分析库 |
|  | nose | 1.3.7 | GNU Library or Lesser General Public License (LGPL) | https://github.com/nose-devs/nose/blob/master/setup.py | 单元测试框架 |
|  | notebook | 7.0.2 | BSD License | https://github.com/jupyter/notebook/blob/main/LICENSE | Jupyter交互式计算笔记本 |
|  | notebook_shim | 0.2.3 | BSD License | https://github.com/jupyter/notebook_shim/blob/main/LICENSE | Shim库,保留notebook前向兼容性 |
|  | numexpr | 2.8.4 | MIT License | https://github.com/pydata/numexpr/blob/master/LICENSE.txt | 高性能数组表达式评估库 |
|  | numpy | 1.23.5 | BSD License | https://github.com/numpy/numpy/blob/main/LICENSE.txt | 科学计算基础库 |
|  | oauthlib | 3.2.2 | BSD License | https://github.com/oauthlib/oauthlib/blob/master/LICENSE | OAuth请求签名逻辑 |
|  | objgraph | 3.5.0 | MIT License | https://github.com/mgedmin/objgraph/blob/master/LICENSE | Python对象图可视化 |
|  | openai | 0.27.9 | MIT License | https://github.com/openai/openai-python/blob/main/LICENSE | OpenAI API的Python客户端库 |
|  | openpyxl | 3.1.2 | MIT License | https://foss.heptapod.net/openpyxl/openpyxl/-/blob/branch/default/LICENCE.rst | 读写Excel 2010 xlsx/xlsm/xltx/xltm文件的库 |
|  | opt-einsum | 3.3.0 | MIT License | https://github.com/dgasmith/opt_einsum/blob/main/LICENSE | 优化的Einstein求和约定 |
|  | orjson | 3.9.7 | Apache Software License | https://github.com/ijl/orjson/blob/master/LICENSE-APACHE | 一个用于JSON编解码的库 |
|  | osqp | 0.6.3 | Apache 2.0 | https://github.com/osqp/osqp/blob/master/LICENSE | 一个用于二次优化的库 |
|  | overrides | 7.3.1 | Apache License, Version 2.0 | https://github.com/mkorpela/overrides/blob/main/LICENSE | 检查类是否覆盖其超类方法装饰器 |
|  | packaging | 23.1 | Apache Software License | https://github.com/pypa/packaging/blob/main/./LICENSE | Core utilities for Python packages |
|  | pamela | 1.1.0 | MIT License | https://github.com/minrk/pamela/blob/main/COPYING | PAM接口模块 |
|  | pandas | 1.5.3 | BSD License | https://github.com/pandas-dev/pandas/blob/main/LICENSE | 数据分析库 |
|  | pandas-datareader | 0.10.0 | BSD License | https://github.com/pydata/pandas-datareader/blob/main/LICENSE.md | 一个用于从各种数据源获取金融数据的库 |
|  | pandas_ta | 0.3.14b0 | MIT License | https://www.pandas-ta.dev/legal/license/ | 一个用于金融技术分析的库 |
|  | pandocfilters | 1.5.0 | BSD License | https://github.com/jgm/pandocfilters/blob/master/LICENSE | Pandoc过滤器工具集 |
|  | paramiko | 3.3.1 | GNU Library or Lesser General Public License (LGPL) | https://github.com/paramiko/paramiko/blob/main/LICENSE | 一个 Python SSHv2 协议库 |
|  | parso | 0.8.3 | MIT License | https://github.com/davidhalter/parso/blob/master/LICENSE.txt | Python解析库 |
|  | patsy | 0.5.3 | BSD License | https://github.com/pydata/patsy/blob/master/LICENSE.txt | 描述统计模型公式的Python包 |
|  | pexpect | 4.8.0 | ISC License (ISCL) | https://github.com/pexpect/pexpect/blob/master/LICENSE | 控制和自动化交互程序 |
|  | pickleshare | 0.7.5 | MIT License | https://github.com/ipython/pickleshare/blob/master/LICENSE | 小型快速的键值对数据库 |
|  | pika | 1.3.2 | BSD License | https://github.com/pika/pika/blob/main/LICENSE | 一个用于与RabbitMQ通信的库 |
|  | Pillow | 10.0.0 | HPND | https://github.com/python-pillow/Pillow/blob/main/LICENSE | 图像处理库 |
|  | pip | 23.3 | MIT License | https://github.com/pypa/pip/blob/main/LICENSE.txt | Python包管理工具 |
|  | pipdeptree | 2.3.3 | MIT License | https://github.com/tox-dev/pipdeptree/blob/main/README.md#pipdeptree/blob/main/LICENSE | 查看Python依赖关系树 |
|  | pkgconfig | 1.5.5 | MIT License | https://github.com/matze/pkgconfig/blob/master/LICENSE | 解析pkg-config文件 |
|  | platformdirs | 3.9.1 | MIT License | https://github.com/tox-dev/platformdirs/blob/main/LICENSE | 跨平台目录访问抽象层 |
|  | prometheus-client | 0.17.1 | Apache Software License | https://github.com/prometheus/client_python/blob/master/LICENSE | Prometheus监控指标暴露库 |
|  | prompt-toolkit | 3.0.36 | BSD License | https://github.com/prompt-toolkit/python-prompt-toolkit/blob/main/LICENSE | 命令行界面应用框架 |
|  | protobuf | 4.22.0 | 3-Clause BSD License | https://github.com/protocolbuffers/protobuf/blob/main/LICENSE | Protocol Buffers序列化库 |
|  | psutil | 5.9.4 | BSD License | https://github.com/giampaolo/psutil/blob/master/LICENSE | 系统监控和系统资源信息 |
|  | psycopg2-binary | 2.9.11 | GNU Library or Lesser General Public License (LGPL) | https://github.com/psycopg/psycopg2/blob/master/LICENSE | PostgreSQL数据库适配器 |
|  | ptvsd | 4.3.2 | Eclipse Public License 2.0 (EPL-2.0) | https://github.com/microsoft/ptvsd/blob/master/LICENSE | Python调试器后端 |
|  | ptyprocess | 0.7.0 | ISC License (ISCL) | https://github.com/pexpect/ptyprocess/blob/master/LICENSE | 伪终端进程工具 |
|  | PuLP | 2.7.0 | BSD License | https://github.com/coin-or/pulp/blob/master/LICENSE | 线性编程模型库 |
|  | pure-eval | 0.2.2 | MIT License | https://github.com/alexmojaki/pure_eval/blob/master/LICENSE.txt | 受限Python求值环境 |
|  | pyasn1 | 0.5.0 | BSD License | https://github.com/pyasn1/pyasn1/blob/main/LICENSE.rst | ASN.1类型和编码库 |
|  | pyasn1-modules | 0.3.0 | BSD License | https://github.com/etingof/pyasn1-modules/blob/master/LICENSE.txt | ASN.1数据结构和编码模块集合 |
|  | pybind11 | 2.10.3 | BSD License | https://github.com/pybind/pybind11/blob/master/LICENSE | C++和Python互操作库 |
|  | PyBrain | 0.3.1 | BSD License | https://github.com/pybrain/pybrain/blob/master/LICENSE | 机器学习库 |
|  | pycparser | 2.21 | BSD License | https://github.com/eliben/pycparser/blob/main/LICENSE | C解析器 |
|  | py-cpuinfo | 9.0.0 | MIT License | https://github.com/workhorsy/py-cpuinfo/blob/master/LICENSE | 获取CPU info库 |
|  | pycryptodome | 3.18.0 | Apache Software License | https://github.com/Legrandin/pycryptodome/blob/master/LICENSE.rst | 提供加密和解密功能的 Python 库 |
|  | pydantic | 1.10.7 | MIT License | https://github.com/pydantic/pydantic/blob/main/LICENSE | 用于数据验证和数据模型管理的 Python 库 |
|  | pyflakes | 3.1.0 | MIT License | https://github.com/PyCQA/pyflakes/blob/main/LICENSE | 检查Python代码错误的工具 |
|  | pyfolio | 0.9.2 | Apache Software License | https://github.com/quantopian/pyfolio/blob/master/LICENSE | 一个用于金融投资组合分析的库 |
|  | pyFUME | 0.2.25 | GNU General Public License (GPL) | https://github.com/CaroFuchs/pyFUME/blob/master/LICENSE | 模糊匹配引擎 |
|  | Pygments | 2.14.0 | BSD License | https://github.com/pygments/pygments/blob/master/LICENSE | 通用语法高亮库 |
|  | pykalman | 0.9.5 | BSD License | https://github.com/pykalman/pykalman/blob/main/LICENSE | 卡尔曼滤波器实现 |
|  | PyMySQL | 1.1.0 | MIT License | https://github.com/PyMySQL/PyMySQL/blob/main/LICENSE | 一个用于与MySQL数据库交互的库 |
|  | PyNaCl | 1.5.0 | Apache License 2.0 | https://github.com/pyca/pynacl/blob/main/LICENSE | 加密库,支持网络和密码学安全性 |
|  | pyOpenSSL | 23.2.0 | Apache Software License | https://github.com/pyca/pyopenssl/blob/main/LICENSE | Python OpenSSL工具集 |
|  | pyparsing | 3.0.9 | MIT License | https://github.com/pyparsing/pyparsing/blob/master/LICENSE | 通用解析器组件库 |
|  | pypinyin | 0.50.0 | MIT License | https://github.com/mozillazg/python-pinyin/blob/master/LICENSE.txt | 汉字拼音转换模块/工具 |
|  | pyrsistent | 0.19.3 | MIT License | https://github.com/tobgu/pyrsistent/blob/master/LICENSE.mit | 持久数据结构库 |
|  | pysqlite3 | 0.5.0 | zlib License | https://github.com/coleifer/pysqlite3/blob/master/LICENSE | SQLite3数据库接口 |
|  | python-dateutil | 2.8.2 | Apache Software License | https://github.com/dateutil/dateutil/blob/master/LICENSE | 日期时间处理库 |
|  | python-json-logger | 2.0.7 | BSD License | https://github.com/madzak/python-json-logger/blob/master/LICENSE | 标准Python日志对象到json的Formatter |
|  | pythonnet | 3.0.1 | MIT License | https://github.com/pythonnet/pythonnet/blob/master/LICENSE | 一个用于在Python中调用.NET代码的库 |
|  | pytz | 2022.7.1 | MIT License | https://github.com/stub42/pytz/blob/master/LICENSE.txt | 时区数据库和时间操作库 |
|  | pytz-deprecation-shim | 0.1.0.post0 | Apache Software License | https://github.com/pganssle/pytz-deprecation-shim/blob/master/LICENSE | pytz移除后向兼容shim |
|  | PyWavelets | 1.4.1 | MIT License | https://github.com/PyWavelets/pywt/blob/main/LICENSE | 小波变换和数字信号处理 |
|  | PyYAML | 6.0 | MIT License | https://github.com/yaml/pyyaml/blob/main/LICENSE | YAML解析器和发射器 |
|  | pyzmq | 25.0.0 | BSD License | https://github.com/zeromq/pyzmq/blob/main/LICENSE.md | ZeroMQ的Python绑定 |
|  | qdldl | 0.1.7.post4 | Apache 2.0 | https://github.com/osqp/qdldl-python/blob/master/LICENSE | 一个用于凸优化的库 |
|  | qtconsole | 5.4.0 | BSD License | https://github.com/spyder-ide/qtconsole/blob/main/LICENSE | Jupyter Qt控制台 |
|  | QtPy | 2.3.1 | MIT License | https://github.com/spyder-ide/qtpy/blob/master/LICENSE.txt | PyQt绑定库 |
|  | redis | 4.5.1 | MIT License | https://github.com/redis/redis-py/blob/master/LICENSE | Redis数据库连接库 |
|  | requests | 2.28.2 | Apache Software License | https://github.com/psf/requests/blob/main/LICENSE | HTTP请求库 |
|  | requests-oauthlib | 1.3.1 | BSD License | https://github.com/requests/requests-oauthlib/blob/master/LICENSE | OAuth认证接口 |
|  | retrying | 1.3.4 | Apache Software License | https://github.com/groodt/retrying/blob/main/LICENSE.txt | 函数调用重试库 |
|  | rfc3339-validator | 0.1.4 | MIT License | https://github.com/naimetti/rfc3339-validator/blob/master/LICENSE | RFC3339日期时间验证器 |
|  | rfc3986-validator | 0.1.1 | MIT License | https://github.com/naimetti/rfc3986-validator/blob/master/LICENSE | RFC3986 URI验证器 |
|  | rich | 13.4.2 | MIT License | https://github.com/Textualize/rich/blob/master/LICENSE | Render rich text和精美格式化在终端上 |
|  | rsa | 4.9 | Apache Software License | https://github.com/sybrenstuvel/python-rsa/blob/main/LICENSE | RSA加密算法库 |
|  | ruamel.yaml | 0.17.32 | MIT License | https://sourceforge.net/p/ruamel-yaml/code/ci/default/tree/LICENSE | YAML解析和序列化 |
|  | ruamel.yaml.clib | 0.2.7 | MIT License | https://sourceforge.net/p/ruamel-yaml/code/ci/default/tree/LICENSE | 一个用于YAML文件处理的库 |
|  | scikit-learn | 1.2.1 | BSD License | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING | 机器学习Python工具包 |
|  | scipy | 1.10.0 | BSD License | https://github.com/scipy/scipy/blob/main/LICENSE.txt | 科学计算基础库 |
|  | scs | 3.2.3 | MIT License | https://github.com/cvxgrp/scs/blob/master/LICENSE.txt | 一个用于凸优化的库 |
|  | seaborn | 0.12.2 | BSD License | https://github.com/mwaskom/seaborn/blob/master/LICENSE.md | 数据可视化库 |
|  | Send2Trash | 1.8.2 | BSD License | https://github.com/arsenetar/send2trash/blob/master/LICENSE | 发送文件到垃圾箱而不是永久删除 |
|  | setuptools | 67.8.0 | MIT License | https://github.com/pypa/setuptools/blob/main/LICENSE | Python包管理工具 |
|  | setuptools-scm | 7.1.0 | MIT License | https://github.com/pypa/setuptools-scm/blob/main/LICENSE | setuptools的SCM扩展 |
|  | shellescape | 3.8.1 | MIT License | https://github.com/chrissimpkins/shellescape/blob/master/docs/LICENSE | Shell参数转义 |
|  | simpful | 2.11.0 | GNU General Public License v3.0 | https://github.com/aresio/simpful/blob/master/LICENSE | 基于Pyomo的建模和模拟框架 |
|  | simplegeneric | 0.8.1 | Zope Public License | https://github.com/conda-forge-admin/python-simplegeneric-feedstock/blob/master/LICENSE | 简单的泛函数装饰器 |
|  | simplejson | 3.18.3 | MIT License | https://github.com/simplejson/simplejson/blob/master/LICENSE.txt | JSON编码/解码器 |
|  | six | 1.16.0 | MIT License | https://github.com/benjaminp/six/blob/main/LICENSE | Python 2和3兼容性工具 |
|  | smart-open | 6.3.0 | MIT License | https://github.com/piskvorky/smart_open/blob/develop/LICENSE | 流式传输大型文件 |
|  | sniffio | 1.3.0 | Apache Software License | https://github.com/python-trio/sniffio/blob/master/./LICENSE | Sniff出异步I/O库 |
|  | soupsieve | 2.4.1 | MIT License | https://github.com/facelessuser/soupsieve/blob/main/LICENSE.md | 一个纯Python CSS选择器实现 |
|  | SQLAlchemy | 2.0.1 | MIT License | https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE | SQL工具包和对象关系映射器 |
|  | stack-data | 0.6.2 | MIT License | https://github.com/alexmojaki/stack_data/blob/master/LICENSE.txt | Stack Exchange数据访问库 |
|  | starlette | 0.27.0 | BSD License | https://github.com/Kludex/starlette/blob/main/LICENSE.md | 轻量级异步Web框架 |
|  | statsmodels | 0.13.5 | BSD License | https://github.com/statsmodels/statsmodels/blob/main/LICENSE.txt | 统计建模和计量经济学 |
|  | sxsc-tushare | 20240927 | BSD License | UNKNOWN | 股票数据处理工具包 |
|  | tables | 3.8.0 | BSD License | https://github.com/PyTables/PyTables/blob/master/LICENSE.txt | 管理结构化和非结构化数据的层次数据库 |
|  | TA-Lib | 0.4.31 | BSD License | https://github.com/TA-Lib/ta-lib-python/blob/master/LICENSE | 技术分析库 |
|  | tensorboard | 2.13.0 | Apache Software License | https://github.com/tensorflow/tensorboard/blob/master/LICENSE | TensorFlow的可视化工具 |
|  | tensorboard-data-server | 0.7.1 | Apache Software License | https://github.com/tensorflow/tensorboard/blob/master/LICENSE | TensorBoard插件的数据服务 |
|  | tensorflow | 2.13.0 | Apache Software License | https://github.com/tensorflow/tensorflow/blob/master/LICENSE | 机器学习平台 |
|  | tensorflow-estimator | 2.13.0 | Apache Software License | https://github.com/tensorflow/estimator/blob/master/LICENSE | TensorFlow Estimators |
|  | tensorflow-io-gcs-filesystem | 0.32.0 | Apache Software License | https://github.com/tensorflow/io/blob/master/LICENSE | TensorFlow的Google Cloud Storage文件系统实现 |
|  | termcolor | 2.3.0 | MIT License | https://github.com/termcolor/termcolor/blob/main/COPYING.txt | 在终端着色字体 |
|  | terminado | 0.17.1 | BSD License | https://github.com/jupyter/terminado/blob/main/LICENSE | Tornado终端仿真 |
|  | threadpoolctl | 3.2.0 | BSD License | https://github.com/joblib/threadpoolctl/blob/master/LICENSE | 线程池控制 |
|  | tinycss2 | 1.2.1 | BSD License | https://github.com/Kozea/tinycss2/blob/main/LICENSE | 低级CSS解析器 |
|  | toolz | 0.12.0 | BSD License | https://github.com/pytoolz/toolz/blob/master/LICENSE.txt | 高性能函数式工具 |
|  | tornado | 6.2 | Apache Software License | https://github.com/tornadoweb/tornado/blob/master/LICENSE | Web框架和异步网络库 |
|  | tqdm | 4.66.1 | MIT License | https://github.com/tqdm/tqdm/blob/master/LICENCE | 显示进度条的Python模块 |
|  | traitlets | 5.9.0 | BSD License | https://github.com/ipython/traitlets/blob/main/LICENSE | 配置和应用选项的轻量级trait系统 |
|  | tushare | 1.2.89 | BSD License | https://github.com/waditu/tushare/blob/master/LICENSE | 股票数据接口库 |
|  | typing_extensions | 4.5.0 | Python Software Foundation License | https://github.com/python/typing_extensions/blob/main/LICENSE | 打字标注扩展 |
|  | tzdata | 2023.3 | Apache Software License | https://github.com/python/tzdata/blob/master/LICENSE | IANA时区数据库 |
|  | tzlocal | 4.2 | MIT License | https://github.com/regebro/tzlocal/blob/master/LICENSE.txt | 获取本地时区 |
|  | uri-template | 1.3.0 | MIT License | https://github.com/plinss/uri-template/blob/main/LICENSE | URI模板处理 |
|  | urllib3 | 1.26.16 | MIT License | https://github.com/urllib3/urllib3/blob/main/LICENSE.txt | HTTP库 |
|  | uvicorn | 0.30.6 | BSD-3-Clause license | https://github.com/Kludex/uvicorn/blob/main/LICENSE.md | 轻量快速的 Python ASGI 框架 |
|  | vprof | 0.38 | BSD License | https://github.com/nvdv/vprof/blob/master/LICENSE | Python性能分析工具 |
|  | walrus | 0.9.3 | MIT License | https://github.com/coleifer/walrus/blob/master/LICENSE | 一个用于与Redis数据库交互的库 |
|  | wcwidth | 0.2.6 | MIT License | https://github.com/jquast/wcwidth/blob/master/LICENSE | 计算字符或字符串宽度的模块 |
|  | webcolors | 1.13 | BSD License | https://github.com/ubernostrum/webcolors/blob/trunk/LICENSE | CSS颜色名称和值的转换库 |
|  | webencodings | 0.5.1 | BSD License | https://github.com/gsnedders/python-webencodings/blob/master/LICENSE | 字符编码别名注册表 |
|  | websocket-client | 0.57.0 | BSD License | https://github.com/websocket-client/websocket-client/blob/master/LICENSE | WebSocket客户端库 |
|  | Werkzeug | 2.3.6 | BSD License | https://github.com/pallets/werkzeug/blob/main/LICENSE.txt | WSGI应用工具集 |
|  | wheel | 0.38.4 | MIT License | https://github.com/pypa/wheel/blob/main/LICENSE.txt | Python分发的打包格式 |
|  | widgetsnbextension | 4.0.5 | BSD License | https://github.com/jupyter-widgets/ipywidgets/blob/main/python/widgetsnbextension/LICENSE | IPython HTML widgets |
|  | wrapt | 1.15.0 | BSD License | https://github.com/GrahamDumpleton/wrapt/blob/develop/LICENSE | 装饰器工具库 |
|  | xcsc-tushare | 1.0.0 | BSD License | UNKNOWN | 股票数据处理工具包 |
|  | xgboost | 1.7.4 | Apache Software License | https://github.com/dmlc/xgboost/blob/master/LICENSE | 提升框架用于大规模机器学习 |
|  | xlrd | 2.0.1 | BSD License | https://github.com/python-excel/xlrd/blob/master/LICENSE | Excel文件读取库 |
|  | xlwt | 1.3.0 | BSD License | https://github.com/python-excel/xlwt/blob/master/LICENSE | Excel文件写入库 |
|  | yarl | 1.9.2 | Apache Software License | https://github.com/aio-libs/yarl/blob/master/LICENSE | 处理URL的库 |

