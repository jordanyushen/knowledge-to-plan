# 长课分批编写与合并

长课先固定目标、先修关系、复习节点与预算依据，再逐批编写真实教学内容。每批最多5课；该限制控制作者的检查范围，不限制课程总长度。正式课程仍是现有 schema_version 1 的单个 plan.json，学习者不需要认识分片。

## 作者工作区

```text
my-course/
  course.json               # 直接保存现有course对象，不加course包装键
  sources.json              # 共享来源数组，ID保持唯一
  estimate.json             # 逐目标估算依据；格式见预算规程
  budget.json               # 预算核算与关联内容指纹
  lessons/
    001-005.json             # 第1–5课的对象数组
    006-010.json             # 第6–10课的对象数组
    011-012.json             # 最后一批可以不足5课
  review/                   # 按分片/目标保存来源、计算和内容复核记录
  merged/
    plan.json
    merge-report.json
```

先把全课设计留在作者记录中，不用虚假课文填满尚未编写的分片。每批完成后检查实际讲解、例子、练习输入/产出、题目答案及来源定位；公式与图按理工科标准复核。中断时保留已经完成的分片，续写下一批即可，不必重生成整份大JSON。

`course.json` 是 [plan-schema.md](plan-schema.md) 所述的 `course` 对象；`sources.json` 是顶层 `sources` 数组；每个分片仅为 `lessons` 条目数组，不能夹带另一份课程约束或来源。文件名必须与其中连续课次完全一致，编号至少三位。每批为1–5课；课次ID稳定、全课唯一；题目ID在课内唯一。

`review_of` 沿用全课整数课次，跨片时也不改成局部序号或字符串ID。例如第6课回顾第2、5课写 `[2, 5]`。来源统一引用 `sources.json` 中的ID。合并器不会自动修补错误引用、覆盖同名ID或重编号。

## 合并完整课程

天数和分钟必须从用户原约定独立传入，不能为通过检查从待合并JSON反抄：

```bash
python3 <skill-dir>/scripts/merge_plan.py \
  --workspace /absolute/path/my-course \
  --output /absolute/path/my-course/merged/plan.json \
  --report /absolute/path/my-course/merged/merge-report.json \
  --expected-days 12 \
  --expected-daily-minutes 30
```

先检查输出目录，确需替换自己的合并产物时加 `--overwrite`。合并器不修改输入分片；输出不能覆盖课程/来源/预算输入或写入 `lessons/`。

合并器按文件名中的数值范围稳定排序，检查文件名与课次顺序、缺课、重叠、重复ID、未知来源、未来复习引用和冲突元数据，再调用完整课程校验。非约定文件会报错，Finder自动产生的 `.DS_Store` 除外。重复JSON键也会失败，避免后一个值静默覆盖前一个值。

未完成所有课次时，合并明确失败，已有分片不会丢失。需要预览一批时另建明确标为草稿的临时课程，不把局部片段或待生成目录称为完整交付。

可选报告保存输入文件SHA256、合并后课程的语义指纹和检查边界。续写或修订后重新合并，用报告找出变化的分片；预算、来源或题目内容变化后，重做对应预算/教学复核。报告只记录 `estimate.json`/`budget.json` 的内容指纹，不把其中自填的 `fits` 当成可信预算结论。

## 合并之后

合并通过只代表现有课程结构完整。继续执行预算依据与关联检查、教学风险检查、来源/答案/图文复核，再构建离线页面。`budget_verified: false`、`facts_verified: false` 明确保留；合并器不会判断是否真正学会，也不会把单选通过等同于独立写码或论述能力。

已有单文件 `plan.json` 仍可沿用原来的校验与构建路径；不为升级作者工具拆散旧课程。不要为了变更分片结构改动课程ID或静默重写学习者成绩。
