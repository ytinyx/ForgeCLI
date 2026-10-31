# 参与开发

使用 Python 3.11 或更新版本、uv 和 Git，在仓库根目录运行：

```shell
uv sync --locked --dev
uv run --locked pytest -q
uv build
uv run --locked python scripts/check_dist.py
```

测试使用模拟模型和临时目录，不需要配置模型密钥。请保持 `FORGECLI_TEST_API_KEY` 未设置，避免启用真实模型集成测试。受限执行环境若不允许 Git 操作系统临时目录，可使用 `uv run --locked pytest -q --basetemp=.pytest_cache/validation`；pytest 会清空该专用目录，请勿存放个人文件。

修改依赖时运行 `uv lock` 并同时提交 `pyproject.toml` 与 `uv.lock`。CI 使用 `--locked` 拒绝过期锁文件。自动检查的配置参考 [uv 官方 GitHub Actions 指南](https://docs.astral.sh/uv/guides/integration/github/)。

变量使用 `snake_case`，提交信息使用英文。修复行为缺陷时补充能重现问题的测试；文档修改无需添加重复测试。Pull Request 中说明问题、修改后的行为和实际运行的验证命令。

提交前运行 `git diff --check`、`git diff --stat` 和 `git status --short`，检查即将提交的文件。不要提交本地配置、API 密钥、会话、日志或生成的安装包。`.gitignore` 不会移除已经被跟踪的文件；发现泄露时先撤销凭据，再处理历史。

发布安装包时保留根目录的 MIT 许可证。`scripts/check_dist.py` 检查归档中的资源、许可证和本地状态文件，再在独立环境用锁定依赖验证命令入口与模块入口。源码包通过明确的路径列表选择内容，配置方式见 [Hatch 构建文档](https://hatch.pypa.io/latest/config/build/)。
