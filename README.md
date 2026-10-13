# GRIDMIND

GRIDMIND is a modular research prototype for generation planning and chronological power system operation. GRIDMIND 是模块化的电源规划与全年逐时运行研究原型。桌面入口位于 `gridmind_app/`，算法位于 `power_ga/`，两者通过 `project_main.execute()` 连接。

## Current capabilities / 当前能力

- Binary candidate-project encoding, initial population, selection, crossover, mutation, elitism and convergence records. / 候选项目二元编码、初代、选择、交叉、变异、精英保留及收敛记录。
- Two-year stage-state dynamic programming with Bellman recursion and an independently optimized Gurobi state model; the desktop app can switch planning methods. / 双年度状态动态规划与 Gurobi 独立核验，桌面应用可切换规划方法。
- A deterministic 8,760-hour single-region operation model covering coal, gas, conventional hydro, pumped storage, battery storage, wind, solar PV and biomass. / 单区域全年8760小时确定性运行，覆盖八类机组。
- Storage charge, discharge and internal energy carry continuously across day and month boundaries. / 储能功率与内部库存跨日、跨月连续。
- One workbook for annual, monthly, daily, hourly, project, storage, GA and data-quality tables. Static figures are kept in separate figure folders; the desktop viewer supports day, week, month, year and arbitrary hour ranges. / 一份汇总工作簿，图表分开存档，交互窗口支持日周月年和任意小时区间。

The model is a transparent research baseline. It does not solve full network power flow, probabilistic reliability, hydraulic cascade scheduling or a globally optimal annual unit-commitment problem. 当前是透明可审计的研究基线，尚未提供完整潮流、概率可靠性、梯级水电或全年全局最优机组组合。

## Layout / 目录

```text
gridmind_app/            Desktop UI, icon and EXE build script / 窗口与打包
power_ga/data_collection/     Input mapping and validation / 数据接入
power_ga/initial_population/ Binary encoding / 初代编码
power_ga/operation_simulation/ Chronological simulation / 运行模拟
power_ga/fitness_and_convergence/ Evaluation / 适应度与收敛
power_ga/genetic_iteration/ GA and project evaluator / 遗传迭代
power_ga/dynamic_planning/  Stage-state DP and Gurobi check / 动态规划
power_ga/result_output/ Reports, figures and viewer / 结果输出
input/                   Synthetic teaching input and editable cost assumptions
tests/                   Synthetic regression cases / 合成回归算例
examples/previews/       Synthetic display preview / 合成展示预览
docs/MATHEMATICS.md      Equations and scope / 数学公式与边界
docs/MATHEMATICS_APPENDIX.md  Detailed derivations / 详细推导
docs/CASE_STUDY.md        Complete synthetic GA and DP comparison / 完整合成案例
docs/USER_GUIDE.md        Desktop and CLI manual / 使用说明
docs/ROADMAP.md           Verified boundaries and next steps / 开发计划
```

## Run / 运行

```powershell
python -m pip install -r requirements.txt
python main.py --skip-figures            # Included synthetic teaching case / 合成教学算例
python gridmind_app/main.py --smoke-test  # Headless window initialization / 后台窗口校验
python gridmind_app/main.py               # Desktop application / 桌面窗口
python -m examples.synthetic_eight_type --output synthetic_demo
python -m examples.synthetic_full_case --output synthetic_ga
python -m examples.synthetic_dynamic_case --output synthetic_ga_dp
python gridmind_app/main.py --export-demo-views synthetic_demo synthetic_views
python gridmind_app/main.py --export-monthly-views synthetic_ga synthetic_months
python -m unittest discover -s tests -q
```

On Windows, `gridmind_app/build.ps1` uses PyInstaller to create `GRIDMIND.exe` with the original icon and bundled renderer. Static native Origin figures require a separately installed Origin; turn off the figure option in the desktop app when unavailable. The EXE accepts `--viewer <result-folder>` to open the zoom window, `--export-demo-views` for five scales, and `--export-monthly-views` for twelve event-marked months. A valid local Gurobi installation/license is required for DP; it is not included in this repository. Windows 下可用打包脚本生成带原创图标的 EXE；动态规划依赖本机有效 Gurobi 许可。

## Zoom demonstration / 8760小时缩放演示

The five images below are **fully synthetic** eight-technology 8,760-hour results. The load, wind and PV profiles include reproducible seeded variability. The desktop viewer lets users choose day/week/month/year, page through periods or enter any `[start,end)` hour range. 图中包含八类机组；窗口可选择日周月年、前后翻页及任意小时区间。[图例、边界与复现方法 / Gallery details](docs/PREVIEWS.md)。

| Day / 日 | Week / 周 |
|---|---|
| ![Synthetic day 182](examples/previews/v0.2.0/day_182.png) | ![Synthetic week 27](examples/previews/v0.2.0/week_27.png) |

| Month / 月 | Year / 年 |
|---|---|
| ![Synthetic month 7](examples/previews/v0.2.0/month_7.png) | ![Synthetic full year](examples/previews/v0.2.0/year_1.png) |

See [all twelve event-marked monthly charts / 12 张月图](docs/MONTHLY_GALLERY.md), [complete GA–DP synthetic case / 完整案例与算法对比](docs/CASE_STUDY.md), [user guide / 使用说明](docs/USER_GUIDE.md) and [roadmap / 计划](docs/ROADMAP.md).

Normal wind and PV are solid colors; curtailment uses the matching color with diagonal hatching. Storage charging is shown below zero on the same stack chart, and the magenta load line is deliberately prominent. 正常风光采用纯色，弃风弃光使用同色斜线；储能充电在同一图的零线下方，洋红负荷线加粗。月度未用水量没有逐时弃水解释，因此不绘制逐时弃水色块。

## Data and licensing / 数据与许可

All included hourly profiles are synthetic. The editable technology-cost CSV contains benchmark-derived and explicitly assumed values; it is **not** a validated local project quote. No private regional or national project input, output table, result figure or project-specific metadata is distributed. 本仓库的逐时曲线仅为合成教学数据；成本表是可编辑试算参数，不能作为项目报价。私有项目数据及其结果不公开。

Code and original documentation are provided under the [MIT License](LICENSE). Optional dependencies retain their own licenses. / 代码与原创文档采用 MIT 许可证，第三方依赖遵循各自许可证。

For the verified development checkpoint, see [Stage report / 阶段成果](docs/PROGRESS_2026-10-14.md) and [mathematical appendix / 数学推导](docs/MATHEMATICS_APPENDIX.md). / 当前已验证的开发状态、合成测试和适用边界见阶段报告与推导附录。
