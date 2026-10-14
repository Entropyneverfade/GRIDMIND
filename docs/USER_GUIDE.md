# GRIDMIND 使用说明 / User guide

## 安装与启动 / Install and launch

Windows 用户双击 `GRIDMIND.exe`；若旧版根目录程序仍在运行，可直接双击构建出的 `GRIDMIND_版本号.exe`。源码用户安装 `requirements.txt` 后运行 `python gridmind_app/main.py`。源码动态规划需额外安装 `requirements-gurobi.txt`；EXE已打包求解器 Python 绑定。两种方式都需本机有效 Gurobi 许可，许可文件不随程序发布。绘图控件可选 Origin 原生工程或 Python/Matplotlib；未检测到 Origin 注册时默认 Python，仍生成 PNG/PDF、图源 CSV 与再绘制脚本。The Python option works on computers without Origin and matches the dispatch data, palette, axes and time bounds.

## 输入 / Inputs

1. 选择兼容的年度项目数据库目录与可编辑经济参数 CSV。原始库保持只读；软件创建独立结果目录。Select the input folder and editable cost table; the original files are not overwritten.
2. 选择目标年、种群、代数与随机种子。单年遗传算法使用这些参数。Choose the target year and GA controls.
3. 在“规划方法”切换“遗传算法”“动态规划（双年度）”或“动态规划（全规划年）”。双年度读取目标年前一年和目标年；全规划年读取基年之后至目标年的每个年度库。每年既有有效装机、负荷、外送、风光及水文取本年度源库，终期候选项目设计容量和状态位保持一致。仅某年度出现的非终期计划增量按该年度外生投运、计入年化费用，不占终期候选位。源库曲线是规划输入，不能自动当成历史实测。双年度还可选“系数情景”，用负荷系数（默认0.95）构造前一年负荷并复用目标年天气；全规划年只能使用逐年源库。The full-horizon option reads each annual source; the scaled two-year scenario cannot stand in for multiple annual datasets.
4. 点击“运行所选规划与全年模拟”。“仅模拟基年存量”只计算运行，不搜索新建方案。Click the planning button or run the existing system only.

勾选“生成图件”并在旁边选择绘图后端：Origin 产生原生可编辑工程，Python 较快且不依赖 Origin。交互窗口始终由 Python 读取已归档逐时 CSV；批处理可用 `--batch-figure-backend python`，已有项目结果可用 `--render-project-python 结果目录` 在独立 `figures_python` 文件夹补图。Archived results can be redrawn without recomputing 8,760 hours.

0.2.9起，Origin逐图绘制在后台运行，不应反复显示PowerShell命令窗口；如绘图失败，可查看该图目录的`qa/renderer.log`。用户主动点击“查看8760小时运行图”或“查看规划图”时仍会打开相应图形窗口。Origin command shells are hidden, while requested chart windows remain visible.

动态规划当前最多允许8个候选位，目标年须至少比基年晚2年，贴现率默认7%。每阶段费用使用已投运候选年化费、当年外生计划年化费和全年运行费。超出上限时给出错误，不截断候选集。全规划年会执行“阶段数×2^候选位数”次全年评价，请为计算留出时间。The cap prevents accidental exponential runs and never silently drops projects.

0.2.6起，状态栏在每个规划年内按批次报告“本年已完成/本年总状态、总体已完成/总体总状态（百分比）”。每年最多约16次通知；百分比只表示已完成的8760小时状态评价数量，不是剩余时间预测。Since v0.2.6 the desktop status shows bounded state-evaluation progress across the full horizon; it is a count, not an ETA.

如果曾用 0.2.1 或 0.2.2 的“年度源库”模式生成结果，请用 0.2.3 或更新版本重新运行：前者误用终期既有装机，后者漏掉仅中间年度出现的计划增量。Prior source-mode archives from 0.2.1 and 0.2.2 require rerunning for these distinct annual alignment defects.

Gurobi 在 DP 模式中优化**年度状态路径**并与 Bellman 递推交叉核验；各状态的全年运行费仍由已说明的确定性8760小时运行规则计算。The stage MILP is not a yearlong unit commitment or network power-flow optimization.

## 分区电力流与属性追踪 / Zonal flow and attributes

0.2.8窗口下方的“分区CSV”输入框读取同一文件夹内四张UTF-8 CSV；可点“生成合成输入”得到固定种子四区教学样本，再选择“Gurobi LP”运行，结果按次独立保存在 `GRIDMIND_results/network_时间`。该示例只有连接方向有公开资料依据，线路参数、负荷、成本及排放因子均是虚构值。用户自己的区域数据不会进入公开仓库。The synthetic fixture is a format demonstration, not a model of actual regional operations.

- `zones.csv`: `zone`，每区一行。/ One row per zone.
- `generators.csv`: `name,zone,technology,minimum_mw,maximum_mw,cost_yuan_per_mwh,carbon_t_per_mwh,sulfur_kg_per_mwh,renewable_fraction`。常规技术单列煤、气、常规水电、生物质、核电、光热、燃油、地热；风光在逐时表，抽蓄和电池放电另列。SO₂单位kg/MWh。/ Conventional technologies remain separate in the output.
- `links.csv`: `name,source,target,limit_mw,kind,susceptance_mw_per_rad`。`kind=ac`需提供正电纳且选择Gurobi LP；`dc`为可控通道，限额两向对称。启发式模式只接受`dc`。/ AC uses phase-angle flow; the heuristic handles controllable channels only.
- `hourly.csv`: 每个0—8759小时、每区恰有一行；列为 `hour,zone,demand_mw,wind_available_mw,solar_available_mw,pumped_charge_mw,pumped_discharge_mw,battery_charge_mw,battery_discharge_mw`，以及抽蓄和电池各自的 `carbon_t_per_mwh,sulfur_kg_per_mwh,renewable_fraction` 三个属性字段，分别加 `pumped_`、`battery_` 前缀。有对应放电时三属性必须给定。固定充放电须由输入方先验证SOC，本入口只校核逐时功率与属性守恒。/ Pumped storage and batteries have separate hourly flows and discharge attributes.

存档的 `tables/跨区运行和碳硫属性汇总.xlsx` 含分区年度、机组技术、线路利用与逐时属性四页；同目录CSV可复用。`run_manifest.json` 含输入文件SHA-256、求解方式及最大守恒残差。点击“查看8760小时运行图”选一个分区，可按日/周/月/年或任意小时缩放；图中区外来电为独立供给，洋红线为本地需求加外送，淡紫虚线为本地需求。The viewer reads the saved hourly table and does not rerun optimization.

## 查看与保存 / View and archive

完成后“查看8760小时运行图”弹出单张堆叠图：供给与弃电在正向，抽蓄及电池充电在负向，洋红色线为需求；正常风光为纯色，弃光为黄色密正斜线、弃风为绿色密反斜线。日/周短窗口中少量薄弃电时，图上最多标记两次主要弃电小时及两类实际 MW，标记不放大电量面积。可按日、周、月、年、任意左闭右开小时区间缩放和前后翻页，并将当前图保存为 PNG。项目单区运行中，小容量储能机组按额定放电功率 MW 优先参与削峰；同容量按电站 ID，充电顺序不变。分区 CSV 模式的储能时序仍由输入文件固定给定。The viewer reloads a saved result without recalculation.

在图内按住鼠标左键水平拖拽，松开后弹出可独立关闭的时段统计窗；时间按全年小时序号显示，左闭右开边界对应被框触及的整小时。各类发电、弃风弃光、抽蓄/电池充放、区外来电、外送、本地负荷、总需求及缺供按原始逐时CSV求和，列出时段电量MWh和平均功率MW，并显示平衡残差。选完可继续切日/周/月/年；切图会关闭旧统计窗。工具栏处于平移或缩放模式时先退出该模式再框选。The popover sums stored hourly MW values; curtailment is reported separately from actual generation.

“查看规划图”在 GA 存档中显示费用收敛与种群状态；在 DP 存档中显示年度费用、累计投运状态，以及同口径 GA 可行最优费用相对 DP/Gurobi 下界的收敛曲线。“打开结果存档”展示表格与独立图片文件夹；“载入已有存档”复用先前结果。The planning chart automatically follows the saved algorithm type and displays the paired comparison when available.

单年结果的 `tables/全年规划运行结果汇总.xlsx` 含年度、电站、8760小时、储能逐时、逐日、逐月、GA和口径说明；DP另有 `tables/动态规划阶段汇总.xlsx`，逐年列出状态、费用与同一阶段费用表上的GA/DP对照。“逐年GA与DP”页和 `ga_dp_stage_comparison.csv` 列出两个算法各年的状态、可行性、年度及折现费用；`ga_dp_comparison.csv` 为总目标对照，`multiyear_ga_history.csv` 为GA逐代记录。年度源库出现终期候选位之外的计划项目时，工作簿另有“年度外生计划”页和 `exogenous_projects.csv`，逐年列出容量及年化费用。图与表分目录保存。CSV与 `run_manifest.json` 供复算、恢复和哈希核验。The exogenous-project sheet is present only when needed; deterministic shortage is not probabilistic EENS or LOLE.

## 命令行 / CLI

```powershell
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm ga
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm dp --stage-input-mode source
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm dp --stage-input-mode source --planning-horizon full
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm dp --stage-input-mode scaled --previous-load-factor 0.95
.\GRIDMIND.exe --batch-source <database-folder> --batch-year 2029 --batch-output <result-folder> --batch-algorithm dp --batch-stage-input-mode source --batch-skip-figures
.\GRIDMIND.exe --batch-source <database-folder> --batch-year 2029 --batch-output <result-folder> --batch-algorithm dp --batch-stage-input-mode source --batch-planning-horizon full --batch-population 24 --batch-generations 24 --batch-seed 11 --batch-skip-figures
python gridmind_app/main.py --viewer <result-folder>
python gridmind_app/main.py --export-monthly-views <result-folder> <image-folder>
python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon --origin-figures
python -m examples.verify_dynamic_case --output synthetic_full
python gridmind_app/main.py --export-monthly-views synthetic_full/final_year synthetic_full/figures/monthly_views
python -m unittest discover -s tests -q
```

## 结果解释 / Interpretation

GA和DP对照须同时固定种群、最大代数、随机种子与**初代策略版本**；这些设置连同年度输入指纹写入 `run_manifest.json`。0.2.5的多年度初代标识为 `balanced_by_stage_v2`，使小种群的单项目种子按年均衡覆盖；0.2.4按末年优先排列，在相同数值参数下可给出不同GA路径。旧存档仍按当时EXE版本解释，DP/Gurobi阶段最优不受此初代排序影响。若批处理未显式给出，种群、代数、种子默认分别为12、12、1。The seed alone is insufficient to reproduce a GA run across different search budgets or initial-population policy versions.

缺供、在线备用不足、不可消纳过剩和逐时平衡残差均原样存档。水电按逐月可用电量上界近似；储能内部能量跨日连续。成本是可编辑情景参数，公开合成案例的成本不代表项目报价。The engine is a deterministic single-region planning baseline without line-flow security, forced-outage probability or full reservoir cascade modeling.

公开的[三年度合成GA/DP案例](CASE_STUDY.md)和[12张末年月图](FULL_HORIZON_GALLERY.md)可直接用于练习读取阶段表、比较同口径目标和操作任意时段缩放；案例输入全由固定种子生成，不读取外部项目目录。The synthetic example is a reproducibility exercise, not a regional planning recommendation.
