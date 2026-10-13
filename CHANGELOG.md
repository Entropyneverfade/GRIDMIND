# Development progress / 开发进度

## 2026-10-14 — Stage 0.2.0 / 完整合成遗传规划与双年度动态规划

- Added a complete eight-candidate GA case with 8,760-hour operation, one consolidated workbook, native static figures and exhaustive 256-plan verification. / 增加八候选位遗传规划完整合成算例、全年表图及256方案穷举校验。
- Added a two-year Bellman state recursion, an independently optimized Gurobi state model, and a same-cost-table GA comparison. / 增加双年度Bellman递推、Gurobi独立核验与同费用表GA对比。
- Added twelve natural-month dispatch charts with event markers. The zero-shortage case uses actual peak net-load days rather than claiming shortage events. / 增加12张自然月图及真实事件标志；无缺口时标净负荷峰值日。
- The desktop source now offers GA/DP selection, a DP stage visualization and archived stage workbook. / 桌面源码增加算法切换、DP阶段图与阶段工作簿。
- Added a complete bilingual case report, user guide, roadmap and DP mathematical derivation. / 增加中英双语案例、说明书、开发计划与动态规划推导。

## 2026-10-14 — Stage 0.1.6 / 八类合成缩放演示与推导

- The Windows EXE now exports predefined day, week, month, year and arbitrary-hour PNGs through the interactive viewer's own range and drawing functions. / 单文件EXE通过交互窗口同一范围及绘图函数导出日、周、月、年和自定义时段图。
- Replaced the two-panel viewer with one full-height dispatch stack: storage charging stays below zero, delivered wind/PV are solid, matching-color curtailment is diagonally hatched, and the magenta load line is thicker. / 窗口改为单张堆叠图，储能充电在零线下，正常风光纯色，弃电同色斜线，负荷线加粗。
- Added a seed-reproducible synthetic 8,760-hour example containing coal, gas, conventional hydro, biomass, pumped storage, battery, wind and PV; load and weather have independent variability. / 加入负荷与风光均有固定种子扰动的八类机组合成算例。
- Added a detailed bilingual derivation appendix and five EXE-generated synthetic preview PNGs. No external project input or output is used in the gallery. / 加入中英双语详细推导及五张由EXE导出的合成示意图。
- Input validation now rejects out-of-range per-unit curves, duplicate cost technologies and invalid storage charge ratios. Twenty-three synthetic tests pass; the synthetic 8,760-hour example has a maximum balance residual below `3e-14 MW`. / 输入校验更严格；23项合成测试通过，合成全年最大平衡残差低于`3e-14 MW`。

## 2026-10-14 — Stage 0.1.5 / 闰年8760小时口径

- Unified hydro budgets, monthly tables and the viewer on one 365-day planning calendar. Leap-year curves must omit February 29 and pass daily-label checks. / 水电预算、逐月表和窗口统一使用365日规划年；闰年曲线需省略2月29日并通过日期校核。
- Added synthetic leap-year operation, workbook and misaligned-label counterexamples; 19 synthetic tests pass. / 加入闰年运行、工作簿及错位日期合成反例，19项测试通过。
- An independent local physical-residual audit passed; no external dataset metadata, values or outputs are published. / 独立的本机物理残差复核已通过；外部数据集元数据、数值和结果均不公开。

## 2026-10-14 — Stage 0.1.4 / 水电月预算边界修正

- Monthly hydro water is an energy upper bound. A month with no positive net load schedules zero hydro instead of forcing water through the turbine. / 月水量作为电量上限；整月没有正净负荷时不强制水电发电。
- Added a synthetic cross-month regression case and checked the annual physical-balance suite again. / 增加跨月合成反例，并重新核验全年物理平衡测试。
- Public equations now state the unused-water rule explicitly; external project data and outputs remain local. / 公开公式明确未用水量口径，外部项目数据和结果继续仅存本地。
- The Windows build script now has a UTF-8 signature so Windows PowerShell 5.1 can parse its Chinese comments and strings; both PowerShell 5.1 and 7 built the EXE locally. / 打包脚本增加UTF-8签名，Windows PowerShell 5.1 与 7 均已在本机完成构建。

## 2026-10-14 — Stage 0.1.3 / 单文件应用验收

- Bundled the Origin renderer in the Windows build and made dense annual PDF fallback run inside the EXE. / 将Origin脚本纳入打包，年度PDF备用封装不再依赖外部Python。
- Added a headless batch route to the same EXE for reproducible end-to-end checks. / 同一EXE可后台批量执行兼容项目流程。
- Verified EXE startup, embedded icon, PDF fallback, complete 8,760-hour simulation, workbook, native Origin projects and exports on a local compatible dataset. No project inputs or outputs are published. / 已在本机核验EXE完整流程、图标、PDF备用路径、8760小时表与Origin工程，项目数据和结果仍不公开。

## 2026-10-13 — Stage 0.1.2 / 阶段修正

- Fixed daily commitment credit for hydro energy-limited hours and excluded charging storage or already-used discharge MW from online reserve. / 修正缺水水电和储能备用重复计数。
- Made annual online reserve shortfall an explicit project-planning feasibility gate; added three synthetic regression cases. / 将年度在线备用不足纳入规划硬约束，增加三个合成反例测试。
- Added a desktop action to reopen archived runs without recomputing them. / 桌面窗口可重新载入已有结果存档。
- All 16 synthetic tests pass; the current private annual result was regenerated and independently audited. / 16项合成测试通过，私有年度结果已重新生成并独立复核。

## 2026-10-13 — Stage 0.1.1 / 阶段版本

- The Windows EXE was rebuilt with its original icon; a hidden-window startup check passed. / 带原创图标的Windows应用已重打包，后台窗口启动检查通过。
- Added an independent 8,760-hour energy-balance and storage-state audit for local runs. No local result or database is published. / 加入本地完整年度输出的独立守恒复核，公开仓库不含项目数据或结果。
- Added a fully synthetic two-bit project-GA case and checked its selected solution against all four feasible/infeasible combinations; 13 regression tests pass. / 新增完全合成的两位建设方案穷举对照，13项回归测试通过。
- Expanded the mathematical model, benchmark-cost explanation and research-method notes. Ten journal records were verified and archived in a dedicated local Zotero collection. / 补充公式、试算成本口径及研究依据，十篇期刊题录已在本地专题收藏夹核对归档。
- Scope remains deterministic single-region dispatch with approximate hydro and daily commitment. / 当前边界仍为确定性单区运行、水电月预算近似与逐日开机规则。

See [the stage report](docs/PROGRESS_2026-10-13.md) for reproducibility and limits. / 可复核进度见阶段报告。

## 2026-10-13 — Initial public prototype / 首次公开研究原型

- Added the separated desktop application and algorithm modules, plus an original Windows icon. / 分离桌面窗口与算法代码，加入原创图标。
- Added 8,760-hour single-region dispatch for eight technology classes, continuous pumped/battery storage states and a monthly hydro energy approximation. / 加入八类技术、抽蓄与电池连续库存及月水量近似。
- Added GA convergence and population diagnostics, a time-range viewer, one consolidated workbook and synthetic display figures. / 加入遗传可视化、时段缩放窗口、汇总工作簿与合成展示图。
- Added synthetic regression tests and a screened public export. / 加入合成回归测试与公开筛选流程。

Next research tasks: validated network constraints, better hydro and thermal chronology, independent capacity-credit evaluation and multi-scenario adequacy. / 后续研究包括网架约束、水火电时序、独立容量信用评价和多场景充裕性；这些能力当前未宣称完成。
