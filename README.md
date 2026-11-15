# 数学建模工作台

v0.1.0 · 通用流程预览版 · Windows / Python 3.12+ / XeLaTeX

首次使用：下载本仓库 → 运行setup.ps1 → 配置运行端技能与字体 → 在助手中打开项目 → 提供新题资料路径。完整操作见[启动指引](USER_GUIDE.md)，依赖见[部署说明](DEPLOYMENT.md)。

本项目提供规则、模板和检查工具，需要具备本地读写、代码执行及联网检索能力的AI助手参与。安装脚本不自动完成研究，也不自动安装模型服务、TeX、商业字体或技能。

长期工作采用多案例结构。根目录提供规则、模板和工具，每道新题在 `cases/<案例名>/` 中独立完成。切换活动案例时可以保留其他题的研究记录。

Windows 电脑取得项目后，在项目根目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`，即可创建 Python 环境、安装工作台依赖并运行工具检查。需要预先安装 Python 3.12 或更新版本。论文编译另需 XeLaTeX 和规定字体，审稿与绘图等技能由运行端安装。具体范围见[部署说明](DEPLOYMENT.md)。

使用入口：[操作指南：从新题导入到论文交付](USER_GUIDE.md)。通常提供资料路径并发送启动指令即可，无需自己运行命令。

工作台支持长期保留多个独立案例。活动案例由workspace.json指定，当前研究进度以该案例的STATUS.md为准；此前清理记录属于历史，不代表当前仍待导入。

先读AGENTS.md、README.md、STATUS.md和WORKFLOW.md，再根据workspace.json读取活动案例的competition.md及STATUS.md。根competition.md是待导入模板，不覆盖活动案例配置。

## 工作流总览

![数学建模全流程架构总览](docs/images/workflow.svg)

<details>
<summary><b>查看可编辑 Mermaid 架构源码</b></summary>

```mermaid
flowchart TB
    %% 阶段 I：输入研判与基线规划
    subgraph S1 ["<b>【 阶段 Ⅰ 】赛题研判与基线规划 (Ingestion & Baseline)</b>"]
        direction LR
        P1_1[("🗃️ 原始数据仓<br/><i>只读数据 · 校验指纹</i>")]
        P1_2["📋 赛题规则审计<br/><i>赛事规范 · 格式/页数限制</i>"]
        P1_3[/"📚 学术文献与GitHub调研<br/><i>经典理论 · SOTA对照 · 许可证</i>"/]
        P1_4["📐 逐问解构与基线模型<br/><i>任务拆解矩阵 · 可解释参考基线</i>"]
        P1_1 --> P1_2 --> P1_3 --> P1_4
    end

    %% 阶段 II：逐问研写双轨协同引擎 (天然阶梯双轨并排，杜绝嵌套direction塌缩)
    subgraph S2 ["<b>【 阶段 Ⅱ 】逐问研写双轨协同引擎 (Dual-Track Research & Writing Engine)</b>"]
        direction TB

        %% 双轨节点对齐
        R1["<b>① 机理假设与推导</b><br/><i>量纲分析 · 闭合方程组</i>"] <-->|"推导公式同步"| W1["<b>① 模型段落与符号系统</b><br/><i>公式入稿 · 符号对齐</i>"]
        R1 --> R2[["<b>② 算法实现与小试验证</b><br/><i>先小试跑通 · 显式失败</i>"]]
        W1 --> W2["<b>② 算法说明与实验配置</b><br/><i>参数标定 · 对照基线实刊</i>"]
        R2 <-->|"小试算法落盘"| W2
        R2 --> R3[["<b>③ 正式求解与消融稳健</b><br/><i>全面优化 · 灵敏度分析</i>"]]
        W2 --> W3["<b>③ 科研图谱与机制解释</b><br/><i>矢量级图表 · 拒绝套话</i>"]
        R3 <-->|"图谱机制支撑"| W3

        %% 门禁与迭代
        Gate_Q{{"⚖️ 单问证据完整性检验<br/><i>推导/求解/解释/图表/正文是否全部闭环？</i>"}}
        Gate_All{{"🔄 全部小问推进完成？<br/><i>赛题任务矩阵是否已全部清零</i>"}}

        R3 --> Gate_Q
        W3 --> Gate_Q
        Gate_Q -.->|"存在证据缺口 · 补实验/正文"| R1
        Gate_Q ==>|"本问闭环"| Gate_All
        Gate_All -.->|"推进下一小问"| R1
    end

    %% 阶段 III：初稿硬门禁与独立审稿体系 (规范文案，明确anti-defensive-writing)
    subgraph S3 ["<b>【 阶段 Ⅲ 】初稿硬门禁与同行审稿体系 (Quality & Peer Review)</b>"]
        direction TB

        Gate_Draft{{"🛡️ 完整初稿四要素硬门禁<br/>• 正文页数达标 (官方规则优先, 默认20-30页)<br/>• 真实核准引用 (~20条真实文献, 列必引)<br/>• 丰富科研图谱 (信息丰富, 拒绝装饰图)<br/>• 核心代码实刊 (附录刊载关键模型与算法)"}}

        Rev_AD[["🔍 anti-defensive-writing 专项表述检查<br/><i>学术语调修正：清除过度防御与套话</i>"]]
        Rev_NR[["🎓 nature-reviewer 角色独立模拟审稿<br/><i>诊断模型逻辑漏洞与论证短板</i>"]]
        Rev_Fix["🛠️ 针对性精修与表述复查<br/><i>补齐缺陷实验 · 修订后由 anti-defensive-writing 复查防御性表述</i>"]

        Gate_Draft ==>|"初稿达标 · 准予送审"| Rev_AD
        Rev_AD --> Rev_NR --> Rev_Fix
    end

    %% 阶段 IV：最终编译验收与成果交付 (克制客观用语)
    subgraph S4 ["<b>【 阶段 Ⅳ 】最终编译验收与成果交付 (Verification & Delivery)</b>"]
        direction LR
        Final_Check[["🔬 最终编译验收与排版核查<br/><i>XeLaTeX 编译 · 宋体/Times 规范字体 · 证据链复核</i>"]]
        Final_Gate{{"🏁 交付终审门禁<br/><i>排版无破损 · 图文100%可溯</i>"}}
        Deliver_Pkg(["📦 完整复现与成果交付包<br/><i>LaTeX 源码包 · 矢量 PDF · 核心可复现程序 · 完整支撑材料</i>"])

        Final_Check --> Final_Gate
        Final_Gate -->|"终验合格 · 正式交付"| Deliver_Pkg
    end

    %% 跨阶段主干推进与严密闭环 (端点连接，顺序锁定)
    P1_4 ==>|"基线确立 · 启动研究"| R1
    Gate_All ==>|"全部小问完成 · 全文集成"| Gate_Draft
    Gate_Draft -.->|"初稿缺口 · 补实验/正文"| R1
    Rev_Fix -.->|"审稿质疑 · 补充实验"| R1
    Rev_Fix ==>|"审稿意见完全闭环"| Final_Check
    Final_Gate -.->|"排版或证据不合格返工"| Rev_Fix

    %% 针对暗黑模式与亮色模式深度优化的“高对比宝石调色盘”
    classDef blueCard fill:#0f2744,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef greenCard fill:#063726,stroke:#34d399,stroke-width:2px,color:#f8fafc;
    classDef purpleCard fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#f8fafc;
    classDef amberGate fill:#451a03,stroke:#fbbf24,stroke-width:2.5px,color:#fef3c7;
    classDef deliveryCard fill:#022c22,stroke:#22c55e,stroke-width:2.5px,color:#ecfdf5;

    class P1_1,P1_2,P1_3,P1_4 blueCard;
    class R1,R2,R3,W1,W2,W3 greenCard;
    class Rev_AD,Rev_NR,Rev_Fix purpleCard;
    class Gate_Q,Gate_All,Gate_Draft,Final_Gate amberGate;
    class Final_Check,Deliver_Pkg deliveryCard;

    style S1 fill:#0b192c,stroke:#1e40af,stroke-width:2px;
    style S2 fill:#062319,stroke:#059669,stroke-width:2px;
    style S3 fill:#1e0e38,stroke:#7c3aed,stroke-width:2px;
    style S4 fill:#062227,stroke:#0284c7,stroke-width:2px;
```
</details>

实验记录、结果登记与论文证据表贯穿研究和修改。完整初稿验收同时检查逐问论证、正文页数、整套图谱、引用、字体及实质性附录；缺项时继续补足。关键文献无法获取时会向你索取，其余工作继续推进。详细步骤与验收以 [WORKFLOW.md](WORKFLOW.md) 为准。

## 新题启动

1. 提供新赛题及附件的本机文件夹路径。助手将为新题创建独立案例，并把资料复制到案例内的 `00_inputs/`。
2. 发送“启动这道题的数学建模工作流”。能够从材料核实的信息自行处理，仅方向性缺失信息提问。
3. 先核比赛/题号/规则和全部资料，再逐问拆解、数据审计、近期文献与GitHub调研，形成基线及实验计划。
4. 每问同步完成推导、求解、结果、解释、验证和图表，更新LaTeX正文与证据。

主线：研究与写作同步 → 完整初稿验收 → 防御性表述专项检查 → nature-reviewer独立审稿/修改 → 表述复查与编译核验 → 交付。

正文默认20—30页，赛题特殊说明优先、约20条真实正文引用、丰富而不冗余的科研图、背景/重述、宋体/Times及摘要数值粗体等持续适用，具体规则见AGENTS.md。未达完整性要求统一称阶段研究稿，不把短篇基线稿称完整初稿。官方约束逐题核实。

## 目录与工具

每道题使用 `cases/<案例名>/`。案例内的00_inputs存原始资料，01_problem存拆解、调研和交接，02_models存模型，03_code存实现，04_experiments存运行，05_figures存图，06_paper存LaTeX和核验，07_delivery存交付。根目录的templates和tools提供通用模板和检查器。

当前设备运行入口为`.venv/Scripts/python.exe`，不将现有环境当作新题依赖已锁定。使用方法见tools/README.md。

```powershell
& '.venv/Scripts/python.exe' tools/workbench.py context
& '.venv/Scripts/python.exe' tools/workbench.py paper-style
```

尚未导入赛题时没有main.tex、研究结论或最终论文；论文相关检查应报告缺少输入，不能以空壳文件制造通过。
