# SI 基础课程独立前向生成报告

本次是课程生成者的前向试用记录，不是课程内容的独立验收报告。模型 ID 在当前接口中不可见，记为 `unavailable`，未猜测具体型号。

## 输入与隔离

- 技能：`/Users/damoo/Documents/ChatGPT/优化/knowledge-to-plan-update/release/knowledge-to-plan/SKILL.md`，并读取该技能的 plan-schema、stem-content-standard、dashboard-standard。
- 输入：`evals/cases/si-basics.json`，以及 source-manifest 中映射的三份 NIST 来源摘记。摘记只作来源清点，不等于原始网页正文。
- 未读取 `evals/reference`，未读取其他任务的课程输出；正式内容未借用 baseline/stem-example 教学内容。仅使用技能随附学习站模板与生成/校验脚本。
- 所有写入均在 `/private/tmp/ktp-eval-si`。未改仓库代码、技能文件、云端或日历；未启动浏览器。

## 实际来源读取范围与定位

以下来源通过 web 工具实际访问；记录的行号是工具当次返回的网页文本定位，可能随页面更新变化。没有把任一整部出版物声称为已读完。

1. [NIST Metric (SI) Prefixes](https://www.nist.gov/pml/owm/metric-si-prefixes)：读取正文 Prefixes 表，工具文本行202–233，使用 c = 10⁻² 与 milli 的符号 m = 10⁻³；也看到表的上下文。未使用前缀历史或完整 SI 定义。
2. [NIST Guide to the SI Chapter 4](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes)：读取 §4.1 Table 1 的长度 m、时间 s，以及 §4.2 Table 2 的面积 m²、速率 m/s，工具文本行138–165；还查看 §4.3 前缀段落/表所在位置，未据此教授其余 SI 派生量。
3. [NIST SI rules checklist](https://physics.nist.gov/cuu/Units/checklist.html)：读取规则2、3、5、12、15、17，分别支持标准符号、符号不加复数、单位乘除记法、数值对应的单位明确、数值与单位留空格、量方程和数值方程区分。规则6及周边文字也被工具返回；未把全部规则列为已完成课程内容。
4. 补充一手教材：[OpenStax Physics §2.2 Speed and Velocity](https://openstax.org/books/physics/pages/2-2-speed-and-velocity)：实际读取 Speed 部分，重点工具文本行56–78；以平均速率定义和不等时段直接平均两速率的反例补足 NIST 单位表未提供的定义依据。工具也返回了后续内容，但本课程不采用向量、瞬时量或原教材例题数值。

中文讲解、例题、练习、九道测验及两幅 SVG 为本次原创；面积换算由长度等量关系和长方形面积推导。不存在原文或原图的大段复制。所有题给数值按精确教学值处理，不另引入测量误差和有效数字要求。

## 时间评估与覆盖边界

约定为三个连续学习日，每天20分钟，总共60分钟；没有指定开始日期，因此不创建计划日期或日历。

根据“已经会小数乘除但没有物理基础”的输入，核心内容估计48–54分钟：热身复习6分钟，讲解及看图18–21分钟，手算10–12分钟，九题自测订正14–15分钟。另保留6分钟不确定性余量（每天最后2分钟），供卡住的换算或订正使用；没有把已经计入的热身复习再次计为必需余量。无补缺需要时可用该余量口述总结。

`assess_budget.py --days 3 --minutes 20 --estimated-hours-low 0.8 --estimated-hours-high 0.9 --buffer-percent 10 --pretty` 返回 `fits`，可用1.0小时、预留后0.9小时。时间是生成者的教学估算，并非真实学习者计时或完成保证。

每日活动均为2 + 7 + 4 + 5 + 2 = 20分钟；每课三道单选题且逐选项解释。顺序为长度比例→面积的两个方向→总路程与同一区间总时间。若学习者超出订正时间仍未掌握，应保留未通过状态，在下次热身/补缺时段先处理；没有自动延长每日时长或伪造通过。

## 原始生成、修正与构建

`raw-plan.json` 是首次写出的完整课程，未改写。首次结构校验与首次构建均返回错误：第二、三课的 `review_of` 使用了此前课次的字符串 ID，校验器要求此前课次的整数序号。技能 schema 只写“引用此前课次”，没有在该字段处明确列出类型。

只在 `course/plan.json` 将这两个字段机械改为 `[1]` 和 `[1,2]`。通过程序比较确认，原稿和构建版除这两个引用类型外完全相同；未改教学内容、答案或题目。

随后实际运行：

```text
python3 <skill>/scripts/validate_plan.py /private/tmp/ktp-eval-si/course/plan.json --expected-days 3 --expected-daily-minutes 20
→ valid=true; days=3; daily_minutes=20; questions=9; facts_verified=false

python3 <skill>/scripts/build_learning_site.py --plan /private/tmp/ktp-eval-si/course/plan.json --output /private/tmp/ktp-eval-si/course --expected-days 3 --expected-daily-minutes 20 --overwrite
→ index.html + plan.json; calendar=null; offline_dependencies=none
```

`--expected-days 3` 和 `--expected-daily-minutes 20` 独立取自 case 输入，没有从待校验 JSON 反抄。`--overwrite` 只覆盖已检查的本任务构建版文件；原始生成保持不变。

## 已执行检查及其限度

- 对九道题分别用有理数计算重算正解，记录计算步骤、单位、题目条件、正确索引及全部干扰项解释；另对25条例题/练习计算复算。详细记录见 `evidence.json`。这是同一生成过程中的计算检查，不能称为独立内容审阅。
- 五个公式条目均有条件、变量及单位（纯单位数值等量关系无变量），平均速率采用结构化 MathML 分式；两个原创 SVG 均能按 XML 解析。用源数据检查了面积图的100格×100 cm²和路程图四个点与段时间的一致性。
- 静态打包检查：实际 HTML 中两个脚本都为内联，样式内联；未发现外部脚本、样式表、字体导入、网络图片或 iframe 依赖。外部原文链接仍需网络。未执行真实断网浏览器验收。
- `node <skill>/scripts/test_runtime.cjs` 通过。它是模板的合成状态测试，覆盖测验门槛、订正、持久化、备份、dashboard、打卡、时区、异常时间及理工科渲染回退等，不能代表本课程的真实浏览器视觉验收。
- 另将实际生成 HTML 的内嵌课程数据和脚本载入内存合成 DOM，确认零进度与默认 dashboard、未选不能提交、错答后重试、九题订正后通过、同日三课/九道唯一题/60计划分钟/一个活动日、模拟刷新保存和备份导出导入。首次自建测试的模拟时钟在“刷新”时倒退，导致未来时间记录按设计被隔离，断言失败；修正测试时钟为单调前进后通过。没有为通过测试修改课程或运行时代码。

## 未验收事项

未启动浏览器，因此桌面、手机和打印的实际布局、MathML 原生显示、SVG 标签裁切/缩放、键盘实际操作、真实 localStorage/file 协议表现与真实离线断网均未验收。未做真实学习者20分钟计时、外部独立学科审阅或独立题目判分评审；不能称为教学内容已独立验证。未生成云端副本、在线网站或日历。

## 产物与使用

唯一学习入口：`/private/tmp/ktp-eval-si/course/index.html`。打开后从学习总览进入第一课；每题提交后查看逐项解析，错题订正到正确才能通过。进度保存在浏览器本地，可以导出/导入；不同设备和副本不自动同步。打开来源链接需联网。

其余审阅文件：`raw-plan.json`、`course/plan.json`、`budget.json`、`evidence.json`、本报告。原稿及构建产物的字节数和 SHA-256 见 evidence。实际运行环境为 Python 3.9.6、Node v26.0.0。
