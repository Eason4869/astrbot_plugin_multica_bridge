# 1.2.1 日志审核修复与验证

日期：2026-10-20。基线为 v1.2.0 / main `52c7d1a`。

## 审核阻断项

收到的审核意见要求日志只能从 `astrbot.api` 导入。修复范围：

- main.py、web_api.py：将 `from astrbot import logger` 改为 `from astrbot.api import logger`。
- work_mode.py：移除内置 logging 与 getLogger 回退，实例日志使用从公开 API 导入的 logger。
- reply_worker.py：移除内置 logging，轮询失败诊断使用公开 API logger。
- Main 的实例日志也直接使用公开 API logger，避免混用 Star 属性来源。

诊断日志保留阶段、异常类型和延迟等字段，回复同步日志不写入异常正文或 Token。测试替身中的 logging 仅用于模拟框架，不属于安装包运行代码。

## 非阻断管线路由建议

本次保留 WorkModeRouter，未修改 AstrBot 核心源码文件。原因是原生消息监听器的优先级只作用于监听器执行；其他插件的命令过滤和缺参数提示可能在进入监听器前发生。直接替换会破坏“工作模式下其他插件及默认模型不回复”的既定要求。

现有 `tests/test_upstream_pipeline.py` 对两个未修改的 AstrBot 源码版本提供负对照与集成验证：普通管线先触发其他插件参数提示；兼容入口接管后，选定工作消息不进入这些过滤器，但保留全局白名单、会话启停、限流、安全及权限检查；退出、卸载后恢复原管线。签名或安全阶段不兼容时禁止进入工作模式。

若后续 AstrBot 提供覆盖命令过滤前阶段的公开事件接口，再评估替换该兼容层。本次不以牺牲隔离行为来回避非阻断提示。

## 验证

- Python 3.10.21、3.12.10 各 201 项回归，Ruff lint 和格式检查。
- 新增 AST 检查，扫描打包清单中全部运行 Python 模块，拒绝内置 logging 和非 `astrbot.api` 的 logger 导入。
- 验证四个日志模块使用公开 API，Main/WorkMode 使用导入的 logger，回复同步异常确实写入该 logger 且不泄露异常原始正文。
- 继续执行旧 URL/Token 升级、工作区选择、上下文竞态、路由权限、卸载还原及两个 AstrBot 源码版本集成测试。
- 构建安装包并扫描包内 Python AST；包中不含 tests、.validation、配置文件或部署数据。

本次仅变更日志来源及版本/文档，UI 交互沿用 1.2.0 已有浏览器验证，未重新宣称真实 QQ 或 Multica 联调。测试结果也不代表插件市场已经重新审核通过。

## 复现

按仓库 CI 下载 AstrBot v4.27.2 与固定 4.29.1 源码快照后：

```powershell
$env:REQUIRE_UPSTREAM_TESTS = '1'
python -m pytest -o addopts= --basetemp=.validation/logger-check --tb=short -q
python -m ruff check .
python -m ruff format --check .
python scripts/build_package.py
```

提交顺序为 dev → CI → main PR；旧 v1.2.0 标签与已发布附件不覆盖。
