# KnowledgeToPlan

将资料或知识目标转为可执行的学习计划与自包含离线课程，结合学习基础、学习日数及每日时间预算评估是否可行。

课程包含知识讲解、练习笔记、带逐项解析的单选测验、错题回顾和进度备份。首页展示学习进度和近 13 周学习量地图；一天可以完成多课，点击日期可查看课程清单、唯一答题数和对应计划分钟。计划分钟不代表实际计时。

页面使用轻量动效，支持减少动态效果、手机布局和键盘操作。无需账户或外部字体、脚本；进度保存在当前浏览器，跨设备通过导出、导入接续。日历、云盘和在线发布按需连接。

## 安装

下载 [打包文件](dist/knowledge-to-plan-2026-11-02.zip)，解压后将整个 `knowledge-to-plan` 文件夹放入 Codex 的 skills 目录（默认 `~/.codex/skills/`）。已有同名 skill 时先备份再替换。

也可以从本仓库安装 `knowledge-to-plan/` 子目录。在 Codex 中调用 `$knowledge-to-plan`，提供资料、目标、已有基础、学习天数与每天可用时间。

## 查看演示

下载或克隆仓库后，用浏览器打开 `knowledge-to-plan/assets/baseline/index.html`。演示含明确标注的示例数据和独立的空白试用；它们不会进入正式课程的生成流程。

## 生成课程

先根据真实资料编写课程 JSON，结构见 [plan-schema.md](knowledge-to-plan/references/plan-schema.md)，界面和统计规则见 [dashboard-standard.md](knowledge-to-plan/references/dashboard-standard.md)。

```bash
python3 knowledge-to-plan/scripts/build_learning_site.py \
  --plan /absolute/path/plan.json \
  --output /absolute/path/output \
  --expected-days 30 \
  --expected-daily-minutes 30
```

把示例中的天数与分钟替换为事先约定的约束。生成结果为 `index.html` 和 `plan.json`，HTML 可直接离线打开。外部原文链接仍需网络。

重建演示：

```bash
python3 knowledge-to-plan/scripts/build_baseline.py
```

## 检查

生成器使用 Python 标准库，运行时检查使用 Node.js，无需安装前端依赖。

```bash
python3 -m unittest discover -s knowledge-to-plan/scripts -p 'test_*.py'
node knowledge-to-plan/scripts/test_runtime.cjs
```

测试覆盖预算与课程校验、测验通过规则、刷新恢复、旧备份兼容、课程时区与跨日、同日多课、题数去重、进度导入导出，以及动效与学习记录的隔离。测试不能代替教学内容与正确答案的事实核对。

压缩包校验值见 [SHA256SUMS](dist/SHA256SUMS)。
