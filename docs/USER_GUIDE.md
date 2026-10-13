# GRIDMIND 使用说明 / User guide

## 安装与启动 / Install and launch

Windows 用户双击 `GRIDMIND.exe`；若旧版根目录程序仍在运行，可直接双击构建出的 `GRIDMIND_版本号.exe`。源码用户安装 `requirements.txt` 后运行 `python gridmind_app/main.py`。源码动态规划需额外安装 `requirements-gurobi.txt`；EXE已打包求解器 Python 绑定。两种方式都需本机有效 Gurobi 许可，许可文件不随程序发布。Static native figures require Origin, while the interactive viewer uses Matplotlib. If Origin is unavailable, uncheck “生成Origin图件”.

## 输入 / Inputs

1. 选择兼容的年度项目数据库目录与可编辑经济参数 CSV。原始库保持只读；软件创建独立结果目录。Select the input folder and editable cost table; the original files are not overwritten.
2. 选择目标年、种群、代数与随机种子。单年遗传算法使用这些参数。Choose the target year and GA controls.
3. 在“规划方法”切换“遗传算法”或“动态规划（双年度）”。DP 默认选“年度源库”：分别读取两个年度的既有机组有效装机、负荷、外送、风光及水文曲线，同时保持终期候选项目设计容量和状态位一致。仅在前一年出现的非终期计划增量按该年度外生投运，计入年化费用，不占终期候选位。源库曲线是规划输入，不能自动当成历史实测。也可选“系数情景”，用界面中的负荷系数（默认 0.95）构造前一年负荷，并复用目标年天气。The source mode uses year-specific existing capacities and treats source-year-only projects as exogenous commitments for that year; the optional scaled scenario reuses target-year weather.
4. 点击“运行所选规划与全年模拟”。“仅模拟基年存量”只计算运行，不搜索新建方案。Click the planning button or run the existing system only.

动态规划当前最多允许 8 个候选位，目标年须至少比基年晚 2 年，贴现率默认 7%。阶段费用使用年化建设费加全年运行费。超出上限时给出错误，不截断候选集。The cap prevents accidental exponential runs and never silently drops projects.

如果曾用 0.2.1 或 0.2.2 的“年度源库”模式生成结果，请用 0.2.3 或更新版本重新运行：前者误用终期既有装机，后者漏掉仅中间年度出现的计划增量。Prior source-mode archives from 0.2.1 and 0.2.2 require rerunning for these distinct annual alignment defects.

Gurobi 在 DP 模式中优化**年度状态路径**并与 Bellman 递推交叉核验；各状态的全年运行费仍由已说明的确定性8760小时运行规则计算。The stage MILP is not a yearlong unit commitment or network power-flow optimization.

## 查看与保存 / View and archive

完成后“查看8760小时运行图”弹出单张堆叠图：供给与弃电在正向，抽蓄及电池充电在负向，洋红色线为需求；正常风光为纯色，弃风光为同色斜线。可按日、周、月、年、任意左闭右开小时区间缩放和前后翻页，并将当前图保存为 PNG。The viewer reloads a saved result without recalculation.

“查看规划图”在 GA 存档中显示费用收敛与种群状态；在 DP 存档中显示年度费用、累计投运状态，以及同口径 GA 可行最优费用相对 DP/Gurobi 下界的收敛曲线。“打开结果存档”展示表格与独立图片文件夹；“载入已有存档”复用先前结果。The planning chart automatically follows the saved algorithm type and displays the paired comparison when available.

单年结果的 `tables/全年规划运行结果汇总.xlsx` 含年度、电站、8760 小时、储能逐时、逐日、逐月、GA 和口径说明；DP 另有 `tables/动态规划阶段汇总.xlsx`，其中包括同一双年度费用表上的 GA/DP 对照。年度源库出现终期候选位之外的计划项目时，工作簿另有“年度外生计划”页，并生成 `exogenous_projects.csv`，列出容量和年化费用。`ga_dp_comparison.csv` 与 `multiyear_ga_history.csv` 保存算法对比和GA逐代记录。图与表分目录保存。CSV 与 `run_manifest.json` 供复算、恢复和哈希核验。The exogenous-project sheet is present only when such source-year projects exist; deterministic shortage is not probabilistic EENS or LOLE.

## 命令行 / CLI

```powershell
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm ga
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm dp --stage-input-mode source
python project_main.py --source <database-folder> --year 2029 --costs <cost.csv> --output <result-folder> --algorithm dp --stage-input-mode scaled --previous-load-factor 0.95
.\GRIDMIND.exe --batch-source <database-folder> --batch-year 2029 --batch-output <result-folder> --batch-algorithm dp --batch-stage-input-mode source --batch-skip-figures
python gridmind_app/main.py --viewer <result-folder>
python gridmind_app/main.py --export-monthly-views <result-folder> <image-folder>
python -m unittest discover -s tests -q
```

## 结果解释 / Interpretation

缺供、在线备用不足、不可消纳过剩和逐时平衡残差均原样存档。水电按逐月可用电量上界近似；储能内部能量跨日连续。成本是可编辑情景参数，公开合成案例的成本不代表项目报价。The engine is a deterministic single-region planning baseline without line-flow security, forced-outage probability or full reservoir cascade modeling.
