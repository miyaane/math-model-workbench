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

```mermaid
flowchart TD
    %% 阶段一：研判与探索
    subgraph P1 ["阶段 I · 输入研判与规划 (Problem Framing & Baseline)"]
        direction LR
        A["<b>赛题与附件导入</b><br/>多源数据 · 赛题规则 · 官方模板"] --> B["<b>题目拆解与调研</b><br/>关键词拆解 · 文献研读 · GitHub 对照"]
        B --> C["<b>数据审计与基线</b><br/>清洗与探查 · 可解释基线 · 实验/图谱规划"]
    end

    %% 阶段二：逐问研写双轨闭环
    subgraph P2 ["阶段 II · 逐问研写双轨推进 (Iterative Research & Writing)"]
        direction TB
        subgraph Loop ["<b>单问研究与正文同步六环</b> (各小问独立推进)"]
            direction LR
            D["① 假设与机理推导<br/><i>同步方法草稿</i>"] --> E["② 算法实现与小试<br/><i>小规模可运行验证</i>"]
            E --> F["③ 正式实验与求解<br/><i>全面参数与优化</i>"]
            F --> G["④ 对照验证与分析<br/><i>消融与稳健性</i>"]
            G --> H["⑤ 科研级图谱生成<br/><i>证据链对齐</i>"]
            H --> I["⑥ LaTeX 正文同步更新<br/><i>推导/结果/解释</i>"]
        end
        QGate{"单问证据完整？<br/>(结果/机制/验证/图文)"}
        AllDone{"全部小问完成？<br/>(逐问矩阵清零)"}

        Loop --> QGate
        QGate -.->|"补充研究/修正"| Loop
        QGate -->|"本问通过"| AllDone
        AllDone -.->|"推进下一小问"| Loop
    end

    %% 阶段三：初稿集成与规范门禁
    subgraph P3 ["阶段 III · 完整初稿集成与规范门禁 (Draft Assembly & Gate)"]
        direction TB
        Draft["<b>全文结构与内容集成</b><br/>整合各问研究 · 核心推导 · 结构化附录"]
        GateAll{"<b>完整初稿验收门禁</b><br/>• 正文页数达标 (官方规则优先，默认20-30页)<br/>• 真实核准引用 (~20条真实文献，列必引)<br/>• 精美科研图谱 (无冗余装饰，证据可溯)<br/>• 核心复现代码 (算法与求解实刊附录)"}
        Draft --> GateAll
    end

    %% 阶段四：专项检查与独立审稿
    subgraph P4 ["阶段 IV · 专项审查与独立同行评议 (Dual Review & Polishing)"]
        direction TB
        AntiDef["<b>表述专项检查</b><br/>anti-defensive-writing<br/>清理套话与过度防御辩解"]
        NatRev["<b>独立模拟审稿</b><br/>nature-reviewer 角色盲审<br/>诊断模型漏洞与论证短板"]
        Refine["<b>针对性精修与补算</b><br/>补齐缺陷实验 · 修正机理推导"]
        PostCheck["<b>审稿后表述复查</b><br/>anti-defensive-writing<br/>确保修改未引入新防御辩解"]

        AntiDef --> NatRev --> Refine --> PostCheck
    end

    %% 阶段五：终审逐页核验与成果交付
    subgraph P5 ["阶段 V · 终验核查与交付归档 (Verification & Delivery)"]
        direction TB
        Verify["<b>证据复核与排版逐页核验</b><br/>证据链一致性 · XeLaTeX 编译 · SimSun/Times New Roman 字体核查"]
        FinalGate{"<b>最终交付验收？</b><br/>(排版无错/图文对齐/无缺口)"}
        Deliver(["<b>最终交付物归档</b><br/>LaTeX 源码包 · 高清无损 PDF · 核心可复现代码 · 支撑材料"])

        Verify --> FinalGate
        FinalGate -->|"通过"| Deliver
    end

    %% 跨阶段主干连接与流转
    P1 ==> Loop
    AllDone ==>|"全部完成 · 进入全文集成"| Draft
    GateAll -.->|"尚存缺口 (补实验/扩充正文)"| Loop
    GateAll ==>|"初稿全部达标"| AntiDef
    Refine -.->|"需补充实验数据"| Loop
    PostCheck ==> Verify
    FinalGate -.->|"未通过 · 存在排版或证据缺口"| Refine

    %% 样式与配色定义 (现代学术与工程配色体系)
    classDef prepStyle fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#0f172a;
    classDef researchStyle fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#14532d;
    classDef gateStyle fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#78350f;
    classDef reviewStyle fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#581c87;
    classDef deliveryStyle fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e3a8a;

    class A,B,C prepStyle;
    class D,E,F,G,H,I researchStyle;
    class QGate,AllDone,GateAll,FinalGate gateStyle;
    class AntiDef,NatRev,Refine,PostCheck reviewStyle;
    class Verify,Deliver deliveryStyle;

    style P1 fill:#f8fafc,stroke:#94a3b8,stroke-width:1.5px,stroke-dasharray: 4 4;
    style P2 fill:#f0fdf4,stroke:#4ade80,stroke-width:1.5px,stroke-dasharray: 4 4;
    style Loop fill:#ffffff,stroke:#86efac,stroke-width:1px;
    style P3 fill:#fffdf5,stroke:#fcd34d,stroke-width:1.5px,stroke-dasharray: 4 4;
    style P4 fill:#faf5ff,stroke:#c084fc,stroke-width:1.5px,stroke-dasharray: 4 4;
    style P5 fill:#f0f9ff,stroke:#60a5fa,stroke-width:1.5px,stroke-dasharray: 4 4;
```

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
