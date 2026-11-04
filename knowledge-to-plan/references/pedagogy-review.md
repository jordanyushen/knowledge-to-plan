# 教学风险检查与内容复核

`validate_plan.py` 的 `valid:true` 只表示结构通过；`lint_pedagogy.py` 的 `passed:true` 只表示没有未解决的教学风险阻断项。两者都保留 `facts_verified:false`，不认证公式、图文、事实或教学效果。

## 运行与报告

```bash
python3 <skill-dir>/scripts/lint_pedagogy.py /absolute/path/plan.json \
  --goal-map /absolute/path/goal-map.json \
  --review /absolute/path/review.json \
  --output /absolute/path/pedagogy-report.json
```

没有相应文件时可以省略可选参数。退出码 0 表示没有未解决的阻断项；2 表示存在阻断项或文件错误。报告中的每项包含 `code`、`severity`（error/warning）、`location`、`message`、`suggestion`、`waivable`、`reviewed` 与 `resolved`。后两项同时为真表示有精确匹配的风险审阅记录；原始风险仍保留。

第一版规则是项目约定，可调整 `--min-questions`（默认8）、`--review-window`（默认5课）与 `--scope-review-hours`（默认12小时），调整依据应保存在作者记录。阈值不是统计认证或学科学时下限。

- 同选项数量题目达到阈值且答案全在同一位置：阻断风险。答案偏斜或长串相同位置：提示。修复时同步重排选项、索引与解析，再逐题核对，不能只修改正确索引。
- 长课没有早期复习、复习间隔过长、缺目标映射：提示。默认长课从8课起；精确的核心目标复习依据目标映射检查。
- 完整掌握类承诺与总时间不超过12小时同时出现：阻断风险，需要缩小范围重新估算，或以该学习者、范围和任务的具体依据逐项复核。更长预算不会自动证明完整掌握。
- 可能缺图、复杂线性公式、疑似占位与未知英文活动名称：提示。不是每个公式都必须有图，也不能靠关键词判断公式真伪。
- 提供了目标映射时，缺少实际教学、练习或测验定位、引用无效及版本过期：不可豁免的阻断项。
- 已确认的公式、单位、答案、事实或图文错误：不可豁免的阻断项，需要修正内容后重新复核。

## 目标映射

目标映射属于作者侧资料，不进入课程 schema 或浏览器成绩。使用当前课程的内容指纹，逐目标填写实际定位：

```json
{
  "plan_sha256": "当前课程规范化JSON的SHA256",
  "goals": [{
    "id": "length-conversion",
    "description": "完成毫米到米的换算并检查换算方向",
    "core": true,
    "taught_in": ["day-001"],
    "practiced_in": ["day-001"],
    "assessed_by": [{"lesson_id": "day-002", "question_id": "q1"}],
    "reviewed_in": ["day-004"]
  }]
}
```

课次使用稳定 `id`，不使用标题或整数 `day`。`practiced_in` 指向有实际 `practice` 的课次，`assessed_by` 指向存在的题目；检查不能先于该目标首次教学。核心目标在结课前有足够后续课次时，默认在首次教学后5课内复习。`reviewed_in` 只定位复习内容，仍需人工核实是否真的在检索或迁移该目标；添加空洞的 `review_of` 引用不会证明有复习。

课程内容、选项、目标或顺序改动后重新核对映射与指纹。指纹由脚本的 `plan_sha256(data)` 计算：JSON对象键排序，UTF-8，`ensure_ascii=False`，分隔符 `(',', ':')`；忽略排版空白但保留数组顺序和全部内容。

## 逐项审阅与已确认内容缺陷

```json
{
  "plan_sha256": "当前课程规范化JSON的SHA256",
  "resolutions": [{
    "code": "diagram_need_review",
    "location": "$.lessons[0].sections[0]",
    "rationale": "该节只辨识坐标名称，不推导曲线关系；已检查练习无需读图。",
    "evidence": ["review/lesson-001.md#diagram-decision"]
  }],
  "content_findings": [{
    "kind": "formula",
    "location": "$.lessons[0].sections[0].body",
    "message": "面积公式漏掉二分之一，底4高3的独立复算应为6。",
    "evidence": ["review/area.md#triangle-check"],
    "status": "open"
  }]
}
```

`resolutions` 必须逐项精确匹配当前报告的规则和位置，带非空理由与可定位证据。没有通配符、全局忽略或单一“已审核全部”开关；重复条目、过期指纹或尝试豁免不可豁免错误均失败。证据路径只是可追溯定位，脚本不声称已经读取、证实这些证据；交付者仍须实际复核。

`content_findings` 的 `kind` 支持 formula/diagram/answer/fact/unit；`location` 必须指向当前课程中存在的明确 JSON 路径。`open` 表示已确认尚未修正，必定阻断；`resolved` 保留复核记录。修正后需要绑定新课程指纹，不能只把已知错误标为忽略。脚本保留 `content_review_status:findings_recorded` 或 `not_performed`，有发现记录不等于整门课程已经审完。

## 内容复核的实际工作

全量检查计分题的唯一正确项与每个选项解析，独立复算高风险例题、公式、单位和图中关系；记录页/节、计算过程与版本。公式与SVG标记合法不代表数学或物理正确。图若标出切线、曲线点、拐点或比例，逐项检查实际几何关系；“示意、不按比例”不能豁免这些关系错误。

为每种检查保留负向样本。`test_pedagogy.py` 故意包含错误面积文字：启发式可能仍通过，但 `facts_verified` 必须保持 false；输入有定位依据的已确认内容发现后必须阻断。这一行为明确揭示自动化的边界，而不是弱化内容检查。

时间与学习效果另外评估。记录目标背景学习者实际耗时、订正、帮助需求和迁移任务表现；未试学时保持估时与效果未验证，不用程序通过替代。
