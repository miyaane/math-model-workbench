# 发布到 GitHub

目标仓库：`miyaane/math-model-workbench`，首版 `v0.1.0`。

Git Bash 可以提交和推送；新建远端仓库需要 GitHub 网页或 GitHub CLI，Git 本身不提供新建 GitHub 仓库的功能。

如果自动发布因登录或网络中断：登录 GitHub，在账号 miyaane 下新建公开的 math-model-workbench 仓库，不勾选自动生成 README、许可证和 gitignore。然后在项目目录打开 Git Bash：

```bash
git remote -v
# 仅当尚无 origin 时添加：
git remote add origin https://github.com/miyaane/math-model-workbench.git
git push -u origin main
git push origin v0.1.0
```

按 Git Credential Manager 提示在浏览器登录。不需要把密码或令牌发给助手。推送后查看仓库文件及 Actions 检查；远端标签存在才算版本已发布。

如果 origin 已存在，先核对地址，不重复添加。已有非空远端不得强制推送覆盖；先核对差异。GitHub Release 可在 v0.1.0 标签上创建，直接使用 CHANGELOG.md 的版本说明。

仓库只跟踪通用文件。cases、workspace.json、虚拟环境、本机清理回执及dist发布包均排除。用户题目数据不随推送上传。
