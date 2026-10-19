# 1.2.0 验证记录

日期：2026-10-19。基于 main 的 1.1.0 合并提交 `6be4fcb`，保留其权限、仅开启者转发、自然语言确认及上下文保护。

## 范围与结果

- Python 3.10.21、3.12.10 完整回归各 194 项通过；Ruff 及 diff 空白检查通过。
- 新增连接测试回归：一次查询返回全部工作区的 id/name/slug，不包含 Token 或远端私有字段；区分连接有效和需要选择工作区，不自动使用第一项，不写回配置。
- 覆盖已有选择、失效 ID、多工作区未选择、单工作区自动解析及请求失败；旧 URL/Token 升级与安装包覆盖测试继续通过。
- 新增 Issue列表回复测试：实际结果、空态、错误均使用新名称；新旧名称保留查询数量与状态参数，命令树验证新增别名。
- Edge 使用真实插件配置 API 和本地 Multica 样例服务，覆盖测试按钮位置、自动加载两个工作区、选择第二项并重载保留、项目清理、Token 保留、读取失败不清除原 ID、迟到响应抑制。
- 浏览器完整回归还覆盖 UID/UMO 保存、智能体选择器、工作会话状态、自动保存竞态、Token 清除竞态、主题及语言；1440px、390px、320px 无横向溢出。
- README PowerShell 示例经过语法解析；未使用真实 Token 执行查询。

测试使用本地 HTTP、模拟 QQ 事件、模型响应和两个 AstrBot 版本源码集成，未启动完整 AstrBot 宿主或连接真实 QQ/Multica 服务，不等同于线上联调验收。上游源码快照沿用 4.27.2 与 4.29.1，详情见仓库 CI。

## 复现

安装项目依赖和 `pytest pyyaml aiohttp ruff`，并按 CI 下载两个 AstrBot 源码快照：

```powershell
$env:REQUIRE_UPSTREAM_TESTS = '1'
python -m pytest -o addopts= --basetemp=.validation/test-1.2 --tb=short -q
python -m ruff check .
python scripts/build_package.py
```

浏览器另需 Node.js、Playwright 与 Edge。先在一个终端启动样例服务：

```powershell
python tests/browser/serve.py
```

然后在另一个终端顺序运行：

```powershell
# PLAYWRIGHT_MODULE 可指定已有 playwright 模块路径。
node tests/browser/check.cjs
node tests/browser/agent-picker.cjs
node tests/browser/workspace-picker.cjs
node tests/browser/races.cjs
```

重复完整检查前重启样例服务以恢复初始会话。服务仅监听 `127.0.0.1:18764`；配置及截图写入 `.validation`，不含用户实际部署数据。

## 提交范围

本次按要求推送至 dev 并创建指向 main 的 PR。未合并该 PR，未创建 v1.2.0 标签或 Release；远程 CI 状态以对应 PR 和提交的 GitHub Actions 记录为准。
