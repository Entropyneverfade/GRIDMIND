# GRIDMIND

**请先阅读[五章完整研究报告 / Complete five-chapter report](docs/FINAL_STAGE_REPORT.md)：** 概述、GA与DP、运行规则、纯合成算例参数、结果及全部25张内嵌图片均在同一页面；公式使用GitHub可渲染的数学格式。分区传输与碳/SO₂/新能源属性已提供独立CSV应用入口，尚未接入真实项目GA/DP适应度。The single report contains all current synthetic figures and equations.

**0.2.7 弃电规则 / Curtailment:** 项目运行改为按当时风光可用出力份额分摊弃电，重跑三年度合成算例后同时出现弃风和弃光。An explicitly parameterized network prototype and a physical attribute tracing layer are included as separate modules.

**0.2.8 分区输入 / Zonal input:** EXE可读取四张CSV做8760小时分区流量和电力部门碳、SO₂、新能源物理属性追踪，输出综合工作簿并按区缩放查看。This is a separate operational analysis mode; network-constrained GA/DP remains future work.

**0.2.9 后台窗口 / Background windows:** 逐图调用Origin时不再弹出PowerShell命令窗口，错误输出继续保存在每张图的`qa/renderer.log`；交互查看器仍按需打开。Origin rendering runs without repeated command windows while the requested chart windows remain available.

**0.2.10 框选统计 / Drag-to-inspect:** 在8760小时查看器内按左键框选时段，浮窗直接汇总各类发电、弃电、储能充放、负荷及外送，显示MWh、平均MW与平衡残差。The popover integrates archived hourly power at 1 h resolution; it does not rerun the solver.

**0.2.11 分区同窗切换 / Zonal viewer:** 分区CSV结果在一张查看器窗口内选择全网汇总或各分区，保留当前小时尺度与框选统计。全网图先验证进口等于出口，再抵消内部交换；各分区仍显示真实的本区进口和外送。The published [four full-year zonal views](docs/FINAL_STAGE_REPORT.md) use fixed synthetic data.

GRIDMIND is a modular research prototype for generation planning and chronological power system operation. GRIDMIND 是模块化的电源规划与全年逐时运行研究原型。桌面入口位于 `gridmind_app/`，算法位于 `power_ga/`，两者通过 `project_main.execute()` 连接。

**0.2.3 修正 / Correction:** 0.2.1 的“年度源库”模式误用终期既有装机；0.2.2 虽修正容量，却遗漏仅中间年度出现的非终期计划项目。使用过这两个版本的年度源库结果请用 0.2.3 或更新版本重算。The source-input mode in 0.2.1 reused terminal existing capacity, while 0.2.2 omitted source-year-only planned projects. Rerun those results with 0.2.3 or newer. The controlled synthetic scaled case is unaffected by these annual alignment issues.

**0.2.5 GA初代 / GA seeding:** 多年度比较中的单项目初代改为按规划年交织，并在运行清单中记录策略版本；旧0.2.4的预算实验保留作历史对照。The annual stage costs and Bellman/Gurobi solution are unchanged; see the [paired seed-policy comparison](docs/CASE_STUDY.md).

**0.2.6 计算进度 / Planning progress:** 多年度动态规划按年度状态批次显示总体完成比例；状态费用和GA/DP决策不变。The desktop window now updates progress during each annual state sweep instead of waiting for a whole year to finish.

## Current capabilities / 当前能力

- Binary candidate-project encoding, initial population, selection, crossover, mutation, elitism and convergence records. / 候选项目二元编码、初代、选择、交叉、变异、精英保留及收敛记录。
- Stage-balanced single-project seeds for the multi-year GA comparison, with the policy version saved in result archives. / 多年度GA按规划年均衡放入单项目初代种子，并把策略版本写入存档。
- Two-year or full annual-source stage-state dynamic programming with Bellman recursion and an independently optimized Gurobi state model; the desktop app can switch planning methods. / 双年度或完整年度源库的状态动态规划与 Gurobi 独立核验，桌面应用可切换规划方法。
- Bounded per-stage and overall progress updates during long dynamic-planning runs. / 长时动态规划按状态批次显示年度与总体进度。
- A deterministic 8,760-hour single-region operation model covering coal, gas, conventional hydro, pumped storage, battery storage, wind, solar PV and biomass. / 单区域全年8760小时确定性运行，覆盖八类机组。
- Storage charge, discharge and internal energy carry continuously across day and month boundaries. / 储能功率与内部库存跨日、跨月连续。
- One workbook for annual, monthly, daily, hourly, project, storage, GA and data-quality tables. Static figures are kept in separate figure folders; the desktop viewer supports day, week, month, year and arbitrary hour ranges. / 一份汇总工作簿，图表分开存档，交互窗口支持日周月年和任意小时区间。
- A separate four-CSV zonal mode solves 8,760 hourly power balances and traces physical carbon, SO₂ and renewable attributes to served demand. / 独立分区入口读取四张CSV、输出潮流与碳硫属性综合表，支持逐区缩放。
- One zonal viewer switches among the full network and every region without reloading the CSV or resetting the current hour range. / 同一窗口切换全网与各分区8760小时图，保留当前时间范围。
- Left-button drag selection in the viewer opens an hour-accurate, nonmodal summary of generation, curtailment, storage charge/discharge, imports/exports, load and balance residual. / 查看器可框选整小时并弹出分类电量与平均功率统计。

## Practical advantages / 当前优势

- The same archived hourly CSV drives the workbook, interactive viewer, selected-period summary and repeat plotting, making displayed values independently checkable. / 表格、图形和框选统计共用一份逐时存档，便于复核。
- Native Origin figures are editable where Origin is installed; the selectable Python backend exports PNG/PDF without Origin. / 同一绘图口径支持可编辑Origin工程与无需Origin的Python后端。
- Input hashes, stage tables and numerical residuals are saved with each run; synthetic tests cover hourly power, storage and regional attribute balances. / 输入指纹、阶段表和物理残差留档，合成算例可复算。
- The desktop EXE can run locally; public examples use fixed synthetic inputs, and the repository excludes private project databases and derived project output. / Windows本地运行，公开仓库仅含纯合成资料。

The planning model is a transparent single-region research baseline; the separate zonal mode uses a lossless linear active-power approximation. Neither provides full AC power flow, probabilistic reliability, hydraulic cascade scheduling or a globally optimal annual unit-commitment problem. 当前主规划仍为单区域，分区模式也只计算无损线性有功近似，尚未提供完整交流潮流、概率可靠性、梯级水电或全年全局最优机组组合。

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
docs/FULL_HORIZON_GALLERY.md  Twelve final-year monthly charts / 三年度末年月图
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
python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon
python -m examples.verify_dynamic_case --output synthetic_full
python -m examples.synthetic_ga_sensitivity --output synthetic_ga_sensitivity
python -m examples.verify_ga_sensitivity --output synthetic_ga_sensitivity --reference-states synthetic_full/tables/all_stage_states.csv
python gridmind_app/main.py --export-demo-views synthetic_demo synthetic_views
python gridmind_app/main.py --export-monthly-views synthetic_ga synthetic_months
python -m unittest discover -s tests -q
```

On Windows, `gridmind_app/build.ps1` uses PyInstaller to create one current `GRIDMIND.exe` with the original icon and bundled renderer. If that file is open, the new binary stays in `gridmind_app/dist/` until the old window closes; `-CreateDesktopShortcut` points a desktop shortcut to the runnable build. Static native Origin figures require a separately installed Origin; the Python backend remains available without it. The EXE accepts `--viewer <result-folder>` to open the zoom window, `--export-demo-views` for five scales, and `--export-monthly-views` for twelve event-marked months. A valid local Gurobi installation/license is required for DP; it is not included in this repository. Windows 下可生成带原创图标的单一当前EXE，动态规划依赖本机有效Gurobi许可。

## Complete results / 完整结果

日、周、月、年和任意区间的新版缩放图、12张月图、GA/DP图、分区图、公式、参数和工作簿链接都直接放在[五章报告](docs/FINAL_STAGE_REPORT.md)中。The report is the single reading entry; the [user guide](docs/USER_GUIDE.md) describes the controls and CSV format.

Normal wind and PV are solid colors; curtailed PV uses dense yellow forward slashes, curtailed wind dense green backslashes. Sparse events in day/week views receive callouts with the actual MW; the areas are not inflated. Small rated-MW storage plants discharge first for peak shaving in the single-region project model. 储能充电在同一图的零线下方，洋红负荷线加粗；弃电文字只用于定位，不改变面积。月度未用水量没有逐时弃水解释，因此不绘制逐时弃水色块。

## Data and licensing / 数据与许可

All included hourly profiles are synthetic. The editable technology-cost CSV contains benchmark-derived and explicitly assumed values; it is **not** a validated local project quote. No private regional or national project input, output table, result figure or project-specific metadata is distributed. 本仓库的逐时曲线仅为合成教学数据；成本表是可编辑试算参数，不能作为项目报价。私有项目数据及其结果不公开。

Code and original documentation are provided under the [MIT License](LICENSE). Optional dependencies retain their own licenses. / 代码与原创文档采用 MIT 许可证，第三方依赖遵循各自许可证。

For the verified delivery overview, see [Final stage report / 阶段成果总览](docs/FINAL_STAGE_REPORT.md), [development checkpoint / 开发检查点](docs/PROGRESS_2026-10-14.md) and [mathematical appendix / 数学推导](docs/MATHEMATICS_APPENDIX.md). / 阶段成果、可复核进度与推导附录分别列示。
