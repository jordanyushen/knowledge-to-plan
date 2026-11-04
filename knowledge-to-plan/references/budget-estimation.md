# 预算估算与完整课程交付

## 先估任务，再算总时长

先固定用户原始目标、背景、天数和每日分钟，再列出可观察的学习产出。认识定义、独立解题、证明与真实写作/写码不是同一深度。记录先修缺口；背景不明时做小诊断或明确保守假设。

逐目标估算讲解、示例、独立练习、反馈订正、间隔复习和测验的任务数量及单次低/高分钟。依据要定位到资料页/节、实际题量/难度、相近任务或试学记录；页数和授课小时都不能直接换算为掌握时间。没有实测时标记为估计。不要先填一个刚好 fits 的总数，再反向凑任务。

额外缓冲用于未排入表的波动，不能重复计算已有复习/订正；设为零也要说明。工具只能检查算术、记录形状和输入关联，无法判断作者是否编造依据或乐观填时。广泛掌握承诺在短预算内会触发风险复核；项目阈值不是各学科的科学最低学时。

## 作者侧 estimate.json

独立于学习页面 schema；`schema_version: 1`。以下字段必需：

| 字段 | 约定 |
|---|---|
| constraints | `{ "days": 正整数, "daily_minutes": 1至1440的整数 }`，与独立命令参数相同 |
| original_goal / selected_goal / background | 非空原始目标、当前明确范围、背景；后两项与 course.goal/background 完全相同 |
| scope | `mode: full` 时目标不缩减、`excluded: []`；`mode: core` 时列出具体 `excluded`、不同的 selected_goal 与 `change_basis`（用户选择或明确的核心先行边界） |
| prerequisite_basis / prerequisites | 背景依据，以及 `{skill,status,evidence}` 数组；status 为 known/gap/assumed。无学科先修也说明依据，可用空数组 |
| buffer_percent / buffer_reason | 0至不足100，说明额外预留用途或零缓冲原因 |
| goals | 非空数组；每项 `id` 唯一、`outcome` 可观察、`source_ids` 对应课程来源、`basis` 具体定位资料/任务依据，及非空 `tasks` |

每项 task 有 `kind`（learn/example/practice/feedback/review/quiz）、`description`、`basis`、正整数 `count`、有限正数 `minutes_low/minutes_high`。分钟是**单次**估计，工具乘数量再求和。每目标有独立练习与测验预算；全课覆盖六种活动，不靠缓冲替代活动。

原始不足的范围应保留；缩小目标必须明列删减内容，重估任务，不得只调低总小时。`core` 是范围标签，不是允许静默删除用户主线的授权。

## 操作顺序

写课前先保存估算结果（尚不绑定课程）：

```bash
python3 <skill-dir>/scripts/budget_evidence.py \
  --estimate /absolute/path/estimate.json --output /absolute/path/budget-draft.json \
  --expected-days 21 --expected-daily-minutes 30
```

数字从已约定输入传入，不能从待校验 JSON 反抄。状态处理：

- fits：在声明范围内推进，不加确认步骤。
- borderline：说明风险，安排补缺；只可交付明确的核心范围，不承诺完整掌握原目标。
- insufficient：展示可用时间/所需区间及依据，给延长天数、增加每日时长或缩小到具体目标的方案；依赖用户选择的完整课程、日历和云端写入先不执行。

课程写完或分片合并后，绑定最终版本重新计算：

```bash
python3 <skill-dir>/scripts/budget_evidence.py \
  --estimate /absolute/path/estimate.json --plan /absolute/path/plan.json \
  --output /absolute/path/budget.json \
  --expected-days 21 --expected-daily-minutes 30
```

已有输出需检查后明确加 `--overwrite`。记录使用规范化 JSON 的 SHA256；格式空白不影响指纹，内容、范围、依据或约束变化必须重算。写课前的未绑定记录不能充当最终预算。

## 最终门禁

准备 [教学目标映射与复核记录](pedagogy-review.md)，用新入口交付完整课程：

```bash
python3 <skill-dir>/scripts/build_course.py \
  --plan /absolute/path/plan.json --estimate /absolute/path/estimate.json \
  --budget /absolute/path/budget.json --goal-map /absolute/path/goal-map.json \
  --output /absolute/path/delivered-course \
  --expected-days 21 --expected-daily-minutes 30
```

需要精确风险处置或内容发现记录时增加 `--review /absolute/path/review.json`；只有用户要求日历且日期时段齐全才增加 `--calendar`。门禁失败不生成半套课程。输出保留 plan、estimate、budget、goal-map、教学风险报告和交付报告；可直接学习入口仍为 `index.html`。

旧的 `build_learning_site.py` 保留给旧课程和草稿，其结果为 `delivery_status: structure_only`。不得用它绕过完整课程的预算和教学风险门禁。新门禁结果仍为 `generated_pending_content_review`：作者映射有完整定位不能自动证明讲解充分。`budget_arithmetic_verified: true` 只说明记录和算术一致；`facts_verified` 仍为 false，语义完整性、实际耗时和教学效果需要另行复核与试学。

可运行的长课作者工作区位于仓库 `evals/long-course/`；它是固定评测样本，不是安装包内的用户模板或已证明有效的教学承诺。
