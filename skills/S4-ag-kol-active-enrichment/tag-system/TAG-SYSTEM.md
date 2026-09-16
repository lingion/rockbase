# S4 Tag System

本目录承载 `S4` 阶段的标签系统本体。

职责边界：

- `S4` 负责生产与标准化
- `S5` 只负责消费与匹配

当前文件分工：

- `../S4-WF_Tag-System-Generation.md`
  `S4` 阶段生成 `账号类目标签` 与 `tag_*` 的正式 workflow，包含子 agent 并行建议
- `account_category_label_standard.md`
  `账号类目标签` 的正式标签池、中文显示规则、以及 `tag_topics -> 账号类目标签` 映射规则
- `master_field_standardization_spec.md`
  `tag_*` 各字段的口径、字段标准化规范、以及标签字段使用边界
- `kol_master_matching_system_design.md`
  整体分面标签系统、matching 逻辑、以及标签框架设计背景

使用建议：

1. 真正执行 `账号类目标签` 与 `tag_*` 生成时，先读 `../S4-WF_Tag-System-Generation.md`
2. 处理 `账号类目标签` 时，先读 `account_category_label_standard.md`
3. 处理 `tag_*` 字段体系时，再读 `master_field_standardization_spec.md`
4. 需要理解整套 taxonomy 与 matching 框架时，再读 `kol_master_matching_system_design.md`
