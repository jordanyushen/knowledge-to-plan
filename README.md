# KnowledgeToPlan

将资料或知识目标转为可执行的学习计划与自包含离线课程，结合学习基础、学习日数及每日时间预算评估是否可行。

课程包含知识讲解、练习笔记、带逐项解析的单选测验、错题回顾和进度备份。首页展示学习进度和近 13 周学习量地图；一天可以完成多课，点击日期可查看课程清单、唯一答题数和对应计划分钟。计划分钟不代表实际计时。

页面使用轻量动效，支持减少动态效果、手机布局和键盘操作。无需账户或外部字体、脚本；进度保存在当前浏览器，跨设备通过导出、导入接续。日历、云盘和在线发布按需连接。

当前验证较充分的是短篇概念与 STEM 课程。长课新增分片、预算依据和教学风险检查，但尚未证明零基础学习者的实际耗时或学习效果；人文论述、编程实作不以单选通过代替能力验收。

| 能力 | 当前状态 |
|---|---|
| 自包含离线 HTML、进度备份、MathML/SVG 公式图示块 | 已实现；行内正文/选项仍为纯文本，复杂公式应使用结构化块 |
| 本地 ICS | 已实现；不会自动写入账户，手动导入前需检查冲突与重复 |
| 原生日历、云盘、在线发布 | 依赖宿主可用连接器与对应授权；技能不内置云连接器 |
| PWA 网页缓存、页内代码执行器、论述自动评分 | 未实现 |

涉及公式的内容须核对来源、符号、单位、适用条件、计算结果和实际排版；需要表达连接、方向、结构或流程时，配套必要示意图。模板支持原生 MathML、符号单位表和内嵌 SVG，标准见 [stem-content-standard.md](knowledge-to-plan/references/stem-content-standard.md)。

## 安装

已发布稳定版为 [v0.2.0 打包文件](https://github.com/jordanyushen/knowledge-to-plan/releases/download/v0.2.0/knowledge-to-plan-2026-11-04.zip)。本分支新增的预算/长课功能尚未发布，不包含在该旧附件中。解压后将整个 `knowledge-to-plan` 文件夹放入 Codex 的 skills 目录（默认 `~/.codex/skills/`）。已有同名 skill 时先备份再替换。根目录的许可证和安装目录内的许可证保持一致。

也可以从本仓库安装 `knowledge-to-plan/` 子目录。在 Codex 中调用 `$knowledge-to-plan`，提供资料、目标、已有基础、学习天数与每天可用时间。

生成端要求 **Python 3.9+ 与可用的 IANA 时区数据**。3.9 是兼容下限，新安装请选仍受官方维护的 Python。建议在虚拟环境中先安装依赖：

```bash
python3 -m pip install -r knowledge-to-plan/requirements.txt
```

Windows 可相应使用 `python -m pip`。`tzdata` 提供系统缺少的时区数据；即使不生成 ICS，课程校验也需要它或系统数据库。错误信息会区分环境缺库与名称查找失败，且不会自动替换用户时区。详见 [运行环境说明](knowledge-to-plan/references/runtime-requirements.md) 和 [Python 官方说明](https://docs.python.org/3/library/zoneinfo.html#data-sources)。

学习者只需浏览器打开生成的 HTML，无需 Python、Node、依赖安装或服务器。进度需要定期导出；在线、离线和不同设备之间不自动同步。

## 查看演示

以下画面来自独立交互测试课程的真实 Chrome HTTP 验收，不是学习效果证明：

![桌面学习总览](docs/screenshots/desktop-dashboard.jpg)

<details>
<summary>查看手机测验布局</summary>

![390px手机测验](docs/screenshots/mobile-quiz.jpg)

</details>

下载或克隆仓库后，用浏览器打开 `knowledge-to-plan/assets/baseline/index.html`。演示含明确标注的示例数据和独立的空白试用；它们不会进入正式课程的生成流程。

公式与电路图示例位于 `knowledge-to-plan/assets/stem-example/index.html`；示例用于验证表达与图文对应，正式课程使用自己的资料与课程ID。

## 生成课程

先按 [估时规程](knowledge-to-plan/references/budget-estimation.md) 保存逐目标任务估算及写课前预算，再根据实际资料编写课程 JSON。结构见 [plan-schema.md](knowledge-to-plan/references/plan-schema.md)，界面规则见 [dashboard-standard.md](knowledge-to-plan/references/dashboard-standard.md)。长课按 [分片规范](knowledge-to-plan/references/long-course-authoring.md) 每批编写检查最多5课，再合并。目标过大或预算不足时先展示具体方案，不静默改变用户约束。

最终课程准备 [目标映射和复核记录](knowledge-to-plan/references/pedagogy-review.md)，重新绑定预算并生成：

```bash
python3 knowledge-to-plan/scripts/budget_evidence.py \
  --estimate /absolute/path/estimate.json \
  --plan /absolute/path/plan.json \
  --output /absolute/path/budget.json \
  --expected-days 30 --expected-daily-minutes 30
python3 knowledge-to-plan/scripts/build_course.py \
  --plan /absolute/path/plan.json \
  --estimate /absolute/path/estimate.json \
  --budget /absolute/path/budget.json \
  --goal-map /absolute/path/goal-map.json \
  --output /absolute/path/output \
  --expected-days 30 \
  --expected-daily-minutes 30
```

把天数与分钟替换为事先约定的独立输入。输出保留 `index.html`、`plan.json`、估算、预算、目标映射和分层检查报告，HTML 可直接离线打开。存在已确认错误时通过 `--review` 提供对应记录，未解决内容缺陷必须阻断。通过只表示作者提供的结构、覆盖定位、算术和风险检查通过；交付状态明确为 `generated_pending_content_review`，语义完整性、事实、实际耗时与学习效果仍须按范围复核。外部原文链接仍需网络。

旧 `build_learning_site.py` 继续兼容旧课程和草稿，输出明确为 `structure_only`；不能用来绕过完整课程门禁。课程内容发生变化后，预算、映射和审阅指纹须重新核对。

重建演示：

```bash
python3 knowledge-to-plan/scripts/build_baseline.py
```

## 检查

生成器使用 Python 标准库与时区数据。Node.js 只用于开发测试：运行时测试与当前 Playwright 开发包以 Node 20+ 为兼容目标，建议新装仍受维护的 Node；学习页面没有 npm 运行依赖。完整环境与未验证范围见 [验证记录](docs/verification.md)。

```bash
python3 -m unittest discover -s knowledge-to-plan/scripts -p 'test_*.py'
node knowledge-to-plan/scripts/test_runtime.cjs
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/check_examples.py
# 克隆源码不包含新ZIP；先构建，后校验。
python3 tools/build_release.py
python3 tools/verify_release.py
```

测试覆盖预算与课程校验、测验通过规则、刷新恢复、旧备份兼容、课程时区与跨日、同日多课、题数去重、进度导入导出，以及动效与学习记录的隔离。测试不能代替教学内容与正确答案的事实核对。

新增的长课、负向风险与预算门禁记录见 [本地实施记录](docs/teaching-quality-status.md)。评测作者工作区位于 [evals/long-course](evals/long-course)，不随技能安装包分发。

压缩包校验值见 [SHA256SUMS](dist/SHA256SUMS)。

真实浏览器测试分别覆盖 HTTP、`file://`、桌面和 390px，运行方式与本机浏览器限制见 [E2E说明](tests/e2e/README.md)。配置了 CI 不代表 CI 已经执行成功；实际记录见上述验证记录。

## 教学内容评测

[evals](evals/README.md) 固定真实资料、学习目标、预算和参考核算，再让独立代理生成课程。原始输出保留，机械修订另存；程序校验、来源和答案复核、真人试学分别记录。未完成真人试学时，时间可行性仍是估计，不能报告教学效果已经通过。

首轮两个主题各生成两次，共36题；独立手写核算103项通过，已审范围未发现关键事实或答案错误。SI首次生成有一处复习引用类型错误，原稿与修订版分别保留。详细范围和限制见 [内容审阅报告](docs/content-review.md)，进度见 [实施状态](docs/implementation-status.md)。

已收到一名熟悉相关内容的试学者对两门课程的正常体验反馈，用时少于20分钟；这不证明零基础学习者的耗时或教学效果。每天分钟数是预算上限，提前完成不必刻意延长学习。

## 发布与许可

原创代码、技能说明与原创示例采用 [MIT](LICENSE)；第三方原始资料保留自己的许可。不会因为引用某个网页就把其原文、图片或商标重新授权。离线安装包不包含评测原始网页或开发测试依赖。

版本与变更见 [CHANGELOG](CHANGELOG.md)。可用 [发布工具](tools/README.md) 重建确定性 ZIP，检查源码清单、示例、manifest 和校验值。安装包通过 [GitHub Releases](https://github.com/jordanyushen/knowledge-to-plan/releases) 分发；源码目录不再保留过期 ZIP，Git 历史中的旧包不改写。开发者克隆后**先构建 ZIP，再校验**，CI校对已提交的manifest和校验值。源码变更后的本地候选包与既有稳定版附件分开管理，不代表已经发布。
