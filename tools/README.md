# 工作台通用工具

## Excel数值模板导出

`python tools/export_excel.py manifest.json`仅用Python标准库将有限数值写入既有XLSX模板单元格。清单含template、output（相对清单目录）及updates（工作表名→单元格地址→数值）。保留未改ZIP部件和目标单元格样式、逐格回读、输出指纹，拒绝覆盖、未知表/格、非有限数及带公式模板；不承担公式重算或优化求解，也不声称支持所有Excel编辑功能。模板必须已经包含待填单元格。

可选number_format只改变目标格的数字显示，复制原样式并保留字体/边框/对齐，存储数值不舍入。数字显示格式由各题要求决定。测试可用`python -S -m unittest discover -s tools -p test_export_excel.py`验证核心不依赖第三方运行库。图片预览仍可使用可选渲染工具，但不进入导出部署依赖。

各题适配层负责稳定业务键映射、重复键/漏项、单位和约束检查，不将具体年度、地块或作物位置固化进通用工具。模板读取及独立回读可使用已锁定openpyxl；实际写入由通用导出器完成，保留未改的工作簿部件。专用渲染可选，不属于生产导出依赖。

## 显式清单打包

`build_delivery.py --case 案例目录 --config 清单JSON --output 案例内07_delivery/新版本`按配置中的packages映射（包名到相对glob列表）生成ZIP及逐文件MANIFEST.json。新版本目录必须不存在；排除运行库和目录链接目标，完成ZIP读取与文件指纹回读。配置示例见templates/package_config.json。打包后必须另行解压验证编译、必要数据重建及结果读取；记录实际验证所用的环境和依赖。

workspace.json的active_case指定活动案例；context返回实际启动文档和资料位置。请以该配置的当前值为准，不在通用指引中固定某一道题或等待状态。不存在活动论文时返回null，不以空main.tex制造完成状态。

```powershell
& '.venv/Scripts/python.exe' tools/workbench.py context
& '.venv/Scripts/python.exe' tools/workbench.py summarize
& '.venv/Scripts/python.exe' tools/workbench.py summarize --verify
& '.venv/Scripts/python.exe' tools/workbench.py research-check
& '.venv/Scripts/python.exe' tools/workbench.py paper-plan
& '.venv/Scripts/python.exe' tools/workbench.py paper-style
& '.venv/Scripts/python.exe' tools/workbench.py preflight --final
& '.venv/Scripts/python.exe' -m unittest discover -s tools -p 'test_*.py'
```

检查其他独立目录使用子命令之前的`--case cases/目录`或`--root 绝对目录`，两者互斥；无效活动路径报错，不静默回退。没有新题时，论文/研究命令报告缺少输入是正确行为，不创建伪结果。

## 新题初始化

```powershell
& '.venv/Scripts/python.exe' tools/initialize_case.py --source '新题资料文件夹绝对路径' --name '新案例目录名'
```

只复制新原始资料、通用规则/模板/工具和质量配置，初始化空运行/采用登记并核对输入指纹，不复制旧题结果；不自动切换活动入口。读题核对后更新workspace.json的active_case。源目录不能包含目标目录，目标已存在则拒绝覆盖。原始输入只读，外部代码另行许可核查。

## 研究与结果

summarize按04_experiments/RESULTS_GUIDE.md核查登记与证据文件，成功/失败/未验证分开；生成.sources.json内容指纹。summarize --verify只读核对时效，不重算模型，也不证明结果为真或比较公平。

research-check读取02_models/research_contract.json，核查显式声明的目标量、验证单位、信息时刻和形状约束等；不从任意程序自动恢复模型，不能替代科学审查。

adopted_results.json定义成功运行的采用别名和产品依赖，生成脚本通过EvidenceGraph.path(alias)读取。evidence-snapshot --output保存不可覆盖的依赖指纹；impact --baseline或--changed指出受影响产品，不自动重算或认证研究结论。未声明依赖仍需核查。

## 写作与表述检查

paper-plan读取manuscript_plan.json与references_verified.json，检查逐节证据、引用对应和预计篇幅；计划页数不代表实际正文页数，元数据存在不证明引用语义正确。

paper-style默认检查活动main.tex并递归读取静态input/include，写06_paper/checks/paper_style_candidates.json。候选包括重复辩解、空泛免责、自我评价、过度限定以及英文对应表达，附文件/行号/上下文、重复计数和候选密度。忽略普通注释和常见代码展示区，不展开任意宏。以实际上下文审阅templates/paper_style_review.md；关键词命中不自动认定不当，零命中也不证明观感合格。不会自动改正文，必要假设、失败与不确定性必须保留。返回0指扫描完成、仍需审阅；输入/输出错误返回2。

阶段研究稿先补逐问研究，完整初稿验收后执行表述专项检查，再冻结nature-reviewer送审快照。审稿修改后再次扫描和实际审阅。正文或包含文件变化后旧表述报告过期，须对修改范围复核。

活动稿可用06_paper/active.json声明main和stage；无指针使用06_paper/latex/main.tex。换题不复制旧指针。完整论文仍需当届规则、正文默认20—30页，赛题特殊说明优先、约20真实正文引用、丰富科研图、字体/摘要数字粗体及审稿修改等联合验收。

## 静态预检与PDF

preflight递归检查静态TeX资源、引用、标签、占位符与可选日志；配置存在时叠加背景/重述、引用数量及对应、摘要数值粗体和正文页数。草稿缺口为警告，--final升级错误；不执行编译或科学/视觉/语言审阅。

正文页数需要真实PDF和06_paper/checks/body_pages.json：schema_version=1、reviewed=true、pdf_sha256、tex_sha256（扫描TeX相对主文件路径及指纹）、body_pages（1起物理页码）和boundary_evidence。摘要、目录、文献和附录不计，混合边界页保守排除。

静态解析不展开宏/条件分支，不能证明当前日志对应当前源。必须实际编译、核嵌入字体、摘要字重、逐页查看、数字语义、引用实质支持、表述检查和独立审稿。误报依据真实证据解释，不关闭要求使稿件通过。

工具测试仅使用合成临时工件，位于tools/.test_tmp并清理；不得将其当赛题数据或论文来源。

页数配置：默认minimum_body_pages=20、maximum_body_pages=30；已核实的赛题特殊规定直接更新案例配置，并在competition.md记录原文来源、页数范围及适用对象。只有上限时可将正文最低设为1，明确覆盖用户默认下限；总页数限制仍须单独核验。require_appendix检查入口，templates/appendix_review.md记录内容实质审查，两者均不能代替PDF逐页核对。
