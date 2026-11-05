# 实验结果统一登记

`results_manifest.json` 是结果文件的索引，不代替实验日志。新题将 `runs` 初始化为空列表，不继承任何旧题运行，也不填入示例成绩。

每次运行将结果保存为 `04_experiments/<run_id>/result.json`，把该文件相对项目根的路径加入 manifest 的 `runs` 数组。失败运行也登记。运行数据生成过程由实际模型代码完成，汇总工具不会运行或补造结果。

## result.json 的结构

顶层是 JSON 对象，字段如下（非可直接冒充实验结果的示例）：

| 字段 | 类型与要求 |
|---|---|
| `schema_version` | 整数 1 |
| `run_id` | 非空字符串，全项目唯一 |
| `question`、`model_id` | 非空字符串，对应题目拆解和模型卡 |
| `status` | `success` / `failed` / `unverified` |
| `recorded_at` | 带时区的 ISO 日期时间 |
| `command` | 实际运行命令，非空字符串 |
| `code_version` | commit 或明确的代码快照标识，非空字符串 |
| `code_files` | 非空文件路径列表，指向本次实际代码或快照，用于内容指纹核验 |
| `seed` | 整数；确定性算法使用 null，并在实验卡说明 |
| `inputs` | 输入文件路径列表，可为空（无外部输入的解析模型需在实验卡解释） |
| `artifacts` | 输出文件路径列表；成功运行至少有一项 |
| `experiment_card` | 实验卡文件路径 |
| `config` | 本次参数配置文件路径 |
| `environment` | 环境及依赖记录文件路径 |
| `log` | 运行日志路径 |
| `metrics` | 指标对象；成功运行至少有一项 |
| `failure_reason` | 失败或未验证时必填非空字符串 |

所有文件路径均相对项目根；必须位于项目内并且存在。目录、URL 不能替代结果证据文件。代码快照内容、输入版本、资源条件和日志真实性仍须按实验卡核验。

每个指标是对象，包含 `value`（有限数值）、`unit`（非空字符串，无量纲使用 `1`）、`direction`（`min` / `max` / `target` / `report`）、`definition`（指标定义，含汇总口径）。布尔值、NaN、Infinity 不作为数值接受。重复实验的次数、均值/中位数、波动与原始样本应在定义及产物中明确。

## 汇总与冻结

从项目根运行 `python tools/workbench.py summarize`，输出 `04_experiments/RESULTS_SUMMARY.md`。任何记录缺失或格式不合法都会报错，禁止生成不完整的新汇总覆盖旧汇总；失败和未验证记录单独列出，不进入成功指标表。旧汇总在源记录变化后不再可信，写论文前必须重跑并检查退出状态。

汇总同时生成 `RESULTS_SUMMARY.sources.json`，记录 manifest、结果记录、代码、输入、配置、日志及产物的 SHA-256 指纹。运行 `python tools/workbench.py summarize --verify` 可只读检查当前汇总是否仍对应这些文件；文件变化、缺失或汇总被修改时返回错误。自定义汇总文件的指纹文件在同目录、同名 `.sources.json`。摘要及指纹都属于生成文件，不能替代不可变的实验快照；更新代码时应新建运行编号，而不是覆盖旧运行的证据。

工具不会自动比较不同数据划分、指标定义和实验条件，也不会自动选出“最佳模型”。最终选定实验由人工/代理基于证据决定，写入 `06_paper/evidence.md`，再冻结源结果与代码快照。论文只使用已核验成功运行的结果，并保留舍入方式、单位与实验编号。
