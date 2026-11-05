# Windows 部署

将项目下载或克隆到任意本地目录，安装 Python 3.12 或更新版本后，在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

如默认 Python 指向商店入口，可指定已安装解释器：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Python 'C:\实际路径\python.exe'
```

脚本安装锁定的工作台依赖并执行回归测试。首次安装依赖需要能访问 Python 包源。论文编译需安装带 XeLaTeX 的 TeX 环境及指定字体。论文审稿和科研绘图使用的技能需要在家用电脑的运行端配置。每道题的建模依赖按案例锁定。

Excel数值模板导出使用tools/export_excel.py，核心只依赖Python标准库；题目模板读取/回读的openpyxl随setup安装。不需要Microsoft Excel、Node或artifact-tool。带公式的模板需要另配重算引擎，当前导出器明确拒绝，避免返回过期公式缓存。最终表述验收还需安装anti-defensive-writing技能。工具本地测试与独立目录导出不等于另一台电脑首次部署已通过。

首次导入新题按 [操作指南](USER_GUIDE.md) 提供资料路径。所有赛题、附件、论文与结果由本机 `cases/` 管理。Git 忽略案例、活动入口 `workspace.json` 和本机 Python 环境。跨电脑续做已有题目时，另行复制整个案例目录并在目标电脑重新选择活动案例。

公开发布前应检查拟提交文件，确认仅包含通用框架及有权分发的内容，并在另一台电脑或全新环境验证首次安装、案例导入、论文编译和审稿环节。

## 运行端技能与字体

本仓库不包含第三方技能源码。运行端需能加载nature-writing、nature-polishing、nature-figure、nature-academic-search、nature-reviewer及anti-defensive-writing；PDF读写/渲染也需相应能力。按研究实际需要启用其他技能，不要求全部安装后才读题。提供技能的安装路径或其有权分发的来源，由运行端核验SKILL.md；缺少必需技能时明确记录，不能假称已经执行。

anti-defensive-writing来源：https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill 。其他nature技能须从你拥有的安装源配置，不因名称相同就视为同一实现。技能规则服从项目事实与证据要求。

中文论文需SimSun与Times New Roman，英文稿需Times New Roman；数学符号字体按兼容性单独配置并记录。字体未随仓库分发，缺失时不能静默替换。

## 更新与本机案例

更新框架前停止当前运行，保存案例。Git不跟踪cases，框架更新不自动同步案例中的规则副本；由助手判断适用范围并迁移。新题用initialize_case创建，默认不改活动入口，由助手核对后更新workspace.json。

## 首版发布

仓库版本见VERSION。公开代码使用MIT许可证；不包含第三方技能、字体、TeX、Python环境或题目资料的授权。发布前运行通用测试和context，再核对Git提交清单。
