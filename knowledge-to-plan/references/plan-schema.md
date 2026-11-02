# 课程JSON约定

用于可复现的本地教学页面和可选ICS。字段采用UTF-8；分钟用整数，天数指学习日数，不把整个资料自动视为已经掌握。

## 顶层

- `schema_version`: 固定为1。
- `course`: `id`（稳定标识，用于区分浏览器进度）、`title`、`goal`、`background`、`days`（正整数）、`daily_minutes`（正整数）、`timezone`（IANA名称，例如Asia/Hong_Kong）。可选`start_date`（YYYY-MM-DD）、`study_time`（HH:MM）、`study_dates`（恰好days个递增且不重复的YYYY-MM-DD；指定时覆盖连续日期生成）。`study_time`为每天开始时间，不是时长。
- `sources`: 来源对象数组，每项`id`、`title`及至少一种定位方式`url`/`path`/`locator`。`url`只允许http(s)，本地文件用`path`；`locator`可描述用户粘贴的原文段落。避免把个人文件路径当作公网可访问链接。
- `lessons`: 恰好days项，`day`连续1…days，每个`id`唯一，顺序与学习日一致。

## 每日条目

必填：`id`、`day`、`title`、`objectives`（至少1项）、`activities`（至少1项，每项`kind`和正整数`minutes`）、`sections`（至少1项，每项`title`和非空实际讲解`body`）、`takeaways`（至少1项）、`questions`（至少1道）、`source_ids`（至少1个存在的来源ID）。

`activities`分钟总和不超过`course.daily_minutes`，涵盖阅读、练习、复习和测验，`kind`为可读标签（如learn/practice/review/quiz）。可选`sections[].example`、`practice`、`review_of`（只能引用此前课次）。项目或复习条目同样提供教学内容和可判断的知识检查，不填“待完善”。

每题：`id`（在该课内唯一）、`prompt`、`options`（至少2个不同非空字符串）、`correct_index`（从0计数的整数；不是字母或布尔值）、`explanations`（与选项数相同，每个选项都解释为什么对/错）。默认每课3题4选项，但不是模板硬限制。

## 可选公式与示意图

理工科内容及任何含公式的课程遵循 [公式与示意图标准](stem-content-standard.md)。在相应的 `sections[]` 内添加以下可选数组；不改变 `schema_version: 1`，普通课程可省略。

- `formulas[]`：每项必填 `title`、`expression`（正确、无歧义的可读数学表达）、`explanation`、`conditions`（适用条件或定义域）；`variables` 必须为数组，每项包含非空 `symbol`、`meaning`、`unit`，无量纲量写“无量纲”，确实没有变量的数值关系可为空数组。可选 `mathml` 为完整的 `<math xmlns="http://www.w3.org/1998/Math/MathML">…</math>`，用于分式、上下标、根式等结构化排版。简单式可用正确 Unicode；复杂式提供 MathML，避免线性文本歧义，`expression` 仍保留作文字说明。
- `diagrams[]`：每项必填 `title`、`svg`（完整、自包含的静态 SVG）、`alt`（表达关键结构、方向或关系的替代文字）、`caption`（图示含义、对应推理和必要假设）。按教学需要添加，不能以装饰图替代必要关系图。
- 两者均可选 `source_ids`；提供时为非空、无重复的来源ID数组，且必须属于该课 `source_ids`。未提供时沿用本课来源。公式与图中具体事实仍需定位到对应来源或注明原创推导。

MathML 与 SVG 使用生成器支持的静态子集，不含脚本、事件处理、外部文件或联网字体。字段和标记校验只能发现结构问题，不能替代公式正确性、单位、适用条件及图文一致性的核验。正文、例题、练习和题目中的公式也要按同一标准审阅，不把未渲染的 LaTeX 当作已完成的数学排版。

完整例子见 [assets/stem-example/plan.json](../assets/stem-example/plan.json)。

## 最小课程示例

以下是结构和脚本冒烟测试用的小例子，正式课程应补足与目标相称的教学深度：

```json
{
  "schema_version": 1,
  "course": {
    "id": "length-unit-basics",
    "title": "长度单位入门",
    "goal": "正确完成毫米和米的换算",
    "background": "零基础",
    "days": 1,
    "daily_minutes": 10,
    "timezone": "Asia/Hong_Kong",
    "start_date": "2026-11-02",
    "study_time": "14:30"
  },
  "sources": [{"id": "input-1", "title": "用户给定知识", "locator": "原文第1段：1米等于1000毫米。"}],
  "lessons": [{
    "id": "day-001", "day": 1, "title": "毫米与米",
    "objectives": ["说明两个单位的数量关系"],
    "activities": [{"kind": "learn", "minutes": 4}, {"kind": "practice", "minutes": 3}, {"kind": "quiz", "minutes": 3}],
    "sections": [{"title": "先确定比例", "body": "米和毫米都表示长度。1米等于1000毫米，所以从毫米换算成米需要除以1000，反方向需要乘以1000。换算改变数值和单位，不改变实际长度。", "example": "500毫米÷1000=0.5米。"}],
    "practice": "先计算250毫米等于多少米，再用乘法反算。",
    "takeaways": ["1米等于1000毫米", "毫米变成米时除以1000"],
    "questions": [{"id": "q1", "prompt": "500毫米等于多少米？", "options": ["0.5米", "500米", "500000米"], "correct_index": 0, "explanations": ["毫米换成米需除以1000，因此是0.5米。", "只改单位而保持数字，会把实际长度放大1000倍。", "这里应该除以1000，不能把换算方向倒过来。"]}],
    "source_ids": ["input-1"]
  }]
}
```

当课程内容修订时保持course.id，题目内容指纹变化会使对应题的旧通过记录失效。课程目标完全不同时使用新ID。不要通过修改天数、日预算或题目正确项绕过真实的计划不可行问题。

## Dashboard与运行时记录

完整HTML遵循 [dashboard与打卡地图标准](dashboard-standard.md)。dashboard从课程和当前有效学习记录计算指标，无需作者在课程JSON中填写完成率、打卡历史或示例成绩。侧栏课程目录使用`lessons`的真实顺序；已通过课次的计划时长为这些课次`activities[].minutes`之和，不代表实际学习计时。

`course.timezone`用于实际学习日期、今日打卡和连续天数。`start_date`/`study_dates`仅用于已约定的计划日期；没有它们仍可生成dashboard和实际打卡地图，不假造课程开始日期。课程JSON保持`schema_version: 1`，用户答案、笔记与打卡属于浏览器进度及其备份，不写回教学内容。

每日学习量同样从有效作答历史计算，不新增课程输入字段：每课所有题首次正确时间的最大值为首次通过时间，归入课程时区当天；当天答题数按不同题目去重，对应计划分钟合计当天新通过课次的活动预算。一日可学多课，实际完成量不受`daily_minutes`封顶；该预算仍约束原课程安排。缺少有效历史时间时不猜测或均摊学习量。演示参考中的课程ID、内容与种子记录不能进入正式新课程。
