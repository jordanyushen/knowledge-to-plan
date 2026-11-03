# Python 列表独立生成评测 run-2

入口：`index.html`。本次按知识目标生成完整中文离线课程，连续3个学习日，每天20分钟；每课3道单选题，共9题，每个选项有独立解析。未约定开始日期，因此不填写计划日期。

## 输入与独立性

- 使用技能：`release/knowledge-to-plan/SKILL.md`，并读取其plan schema、dashboard、STEM规范与界面基线。
- 用户输入：`release/evals/cases/python-lists.json`，预算约束来自该输入独立传入命令行，明确使用`--expected-days 3 --expected-daily-minutes 20`。
- 读取`release/evals/source-manifest.json`及三个本地官方原始HTML的相关节。三个SHA256全部与manifest匹配。
- 未读取`evals/reference`、已有run、`/private/tmp/ktp-eval-python`或其他agent输出。
- 模型ID：`unavailable`，可见上下文未提供可核实模型标识。

## 教学安排与预算

1. 第1课：创建列表、可变性、索引、负索引、len、默认步长切片及边界行为。
2. 第2课：append与extend、修改对象和返回值的区别、默认及指定索引pop；复习第1课。
3. 第3课：别名、copy与全切片、浅拷贝的单层共享边界、整数列表原地sort；复习前两课并综合预测。

每课都有实际中文讲解、原创代码例子、给定练习输入、预期输出、复习补缺提示和三题测验；共一张原创嵌入SVG说明别名及共享子列表关系。基础目标不扩展到复杂嵌套拷贝、循环或其他Python主题。

根据已知变量/整数/print基础和短列表范围，估计讲解、练习、复习与订正合计54–60分钟；预算脚本给出`fits`。最终三课各20分钟：讲解与例子共22分钟、练习14分钟、复习补缺6分钟、测验订正18分钟。额外缓冲为0%，因为全部60分钟已明确分配，复习和订正已包含在估算中；没有把它们重复计算为缓冲，也没有暗中延长天数或每日时间。估算针对这套短代码入门检查，不保证所有初学者同速或获得完整编程能力。

## 保留原稿与修订

`raw-plan.json`一次写入后没有覆写。初次结构校验即通过，无需修订。构建器另行输出`plan.json`，与原稿语义完全一致；HTML内嵌课程也与原稿一致。没有通过修改约束或正确选项规避失败。

原稿SHA256：`c652c349221aa9f4d018502ddaed2dfc46ff1d0abf8db304b5c344d02041a4d7`。

## 实际验证

- `validate_plan.py raw-plan.json --expected-days 3 --expected-daily-minutes 20`退出0，结果为3课、每日20分钟、9题、`valid: true`。该工具明确返回`facts_verified: false`。
- `build_learning_site.py --plan raw-plan.json --output /private/tmp/ktp-eval-python-second --expected-days 3 --expected-daily-minutes 20`退出0，生成独立课程HTML和plan。
- 同一生成者对照已读取来源逐题核查，9题的具体依据、正确项与逐项解析记录在`evidence.json`。执行31组代码检查，覆盖课内例子、练习、复习、全部题目及越界/共享/返回值边界；31组均匹配手写预期输出或预期异常。执行环境是Python 3.9.6，官方资料是Python 3.13；所用基础列表行为未涉及版本新增功能，未在Python 3.13解释器上运行。
- 附带`node scripts/test_runtime.cjs`退出0，测试模板的合成DOM、测验门槛与订正、进度、地图、备份、时间和存储逻辑等。它使用模板合成测试，不代表在真实浏览器完成本课程验收。
- 静态核验：HTML内嵌JSON与原稿一致，构建plan与原稿一致；外部script src为0、外部stylesheet为0，模板占位符已替换。来源链接仍需联网访问。
- 引用图已做关系逻辑核对，并以对象身份断言验证别名、不同外层及共享子列表；未做可视化排版检查。

## 未验证范围与交付边界

按任务要求没有使用浏览器，因此桌面、手机、打印、键盘、真实本地存储和真实文件备份导入导出路径未做浏览器验证。未声称独立内容审核通过；内容核对和代码复算由本次生成者执行。没有云盘、日历、在线发布或对外通信。

离线使用：打开`index.html`，从总览进入课程；选择答案后提交，订正完本课全部题目才记录通过。记录存于当前浏览器，建议导出备份；不同设备或副本不自动同步。不能进行浏览器验证的范围应与这些使用说明一并保留。
