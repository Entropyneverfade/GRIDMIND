# Development progress / 开发进度

## 2026-10-14 — Stage 0.2.14 / 站级机组动态约束与默认参数审计

- 单区项目运行新增站级小时爬坡、跨日最短开停、日最大启动次数、月最大/最小出力、月最小开机台数、逐月计划检修及燃气源表启停编码/启动成本。参数缺项使用标明来源的公开试算值；源表占位爬坡1.0不被误用为物理验证。The source parameter takes precedence and every fallback is labeled in the exported snapshot.
- 运行工作簿新增“机组逐时状态”和“机组运行参数”；纯合成单年度 GA 已重跑并发布逐站CSV、综合工作簿及12张月图。Synthetic independent replay checks 43,800 station-hours with zero hourly ramp and monthly-bound residual; maximum power balance residual is approximately $1.42\times10^{-14}$ MW.
- 67项本地合成测试通过，包含先失败后修复的爬坡、跨日最短开停、月最大出力反例。Daily station-level commitment is a conservative heuristic; unit-level, sub-hourly, automatic annual maintenance scheduling and network-coupled planning remain open.

## 2026-10-14 — Stage 0.2.13 / 数据库分区识别与日期滚轮缩放

- 查看器沿结果清单读取兼容输入工作簿的系统、负荷、节点、电站关系，自动列出有负荷或有效电站的分区；根系统和占位系统排除。若本次只有汇总逐时表，分区名标注尚无逐区结果，不能用汇总曲线冒充。The catalog reflects workbook metadata while plots require region-specific archived power data.
- Ctrl+滚轮以指针位置缩放到整数小时区间；横轴在周图标每天零点日期，在宽视图抽稀日期并保留两端向内真实刻度。The synthetic day, week and year previews expose the calendar mapping without project data.

## 2026-10-14 — Stage 0.2.12 / 任意运行图窗内载入并切换分区

- 修复图窗入口不一致：单区结果窗口现在也显示“显示分区”下拉框，旁边可直接“载入分区结果…”。打开有效分区存档后，同一画布可选全网汇总与各区，并保留正在看的小时区间。Every operation window exposes the selector; loading a zonal archive no longer requires closing the chart.
- 后台EXE冒烟从单区图窗载入纯合成四区存档，实际切换分区、框选统计并退出0；无分区逐时表时清楚标注“当前单区结果”。The UI never invents missing zonal data.

## 2026-10-14 — Stage 0.2.11 / 同窗切换各分区8760小时图

- 分区结果查看器增加“全网汇总/各分区”下拉框，切换时保持时间尺度与框选统计；全网图逐小时验证并抵消内部进口和外送，各区图保留本区交换。The selector redraws cached archived curves without another solver run.
- 四张固定种子合成分区全年预览直接嵌入五章报告；图形使用应用的Python/Matplotlib后端，绝非真实省级运行数据。Four region previews document the supported viewer mode.
- 61项本地合成测试通过；四区8760小时加全网图的最大逐时功率残差 $5.68\times10^{-14}$ MW；冻结单文件EXE的分区切换与框选浮窗后台验收退出码0，桌面快捷方式仍指向当前根目录EXE。The packaged viewer passed its hidden-window smoke check.

## 2026-10-14 — Stage 0.2.10 / 框选统计与单一EXE交付

- 交互查看器新增左键横向框选，浮窗按整小时汇总机组发电、风光弃电、抽蓄和电池充放、本地负荷、外送与区外来电，并显示MWh、平均MW和选段平衡残差。The nonmodal popover reads the archived hourly table and survives no stale redraws.
- Windows打包脚本只交付根目录当前版EXE；旧版被占用时新版留在应用子目录，历史EXE转移至本地归档；可选创建桌面快捷方式。The repository documents current verified capabilities and practical advantages without publishing private cases.
- 60项本地合成测试通过；实际四区合成168小时框选的平衡残差为约 $3.64\times10^{-12}$ MWh；冻结EXE的隐藏窗口浮窗验收退出码0，桌面快捷方式指向当前EXE。Sixty local tests and the packaged viewer smoke check passed.

## 2026-10-14 — Stage 0.2.9 / 后台绘图窗口修复

- Origin逐图绘制时，Windows PowerShell子进程以无控制台方式启动，渲染输出仍保存于每图`qa/renderer.log`；启动交互查看器的源码模式同样抑制多余控制台，保留用户所需GUI窗口。Windows rendering and viewer child processes no longer create extra command windows; renderer logs remain archived.
- 58项本地测试通过；独立纯合成输入实际导出两张Origin图，各自PNG、PDF、OPJU及日志齐全；新版单文件EXE启动和归档Python绘图退出码均为0。No dispatch, optimization or figure data changed in this maintenance release.

## 2026-10-14 — Stage 0.2.8 / 分区CSV应用入口与属性归档

- 单区项目运行的削峰放电改为小额定MW储能站先行，同容量按站ID；合成反例验证输入行大站在前仍由小站先供2MW，逐时功率/SOC残差保持容差内。周图的弃风、弃光分别使用密反/正斜线，薄弃电小时加真实MW定位标注；图例及面积均不改写原数据。Small rated-power storage gets peak-shaving priority; dense opposite hatches and value callouts clarify sparse curtailment.
- 交互堆叠图去掉逐小时黑色多边形边框，纵轴限制主刻度数、贴近实际充电负轴，避免旧窗口出现灰色块与左轴黑线；同一合成周窗口经后台实测重画约0.03–0.04秒、全年窗口约0.18秒（本机单次测量，非跨硬件承诺）。The revised viewer keeps full hourly values and redraws only the selected time span.
- 项目运行图增加 Python/Matplotlib 静态后端；无 Origin 的电脑可导出 PNG/PDF、源 CSV、再绘制脚本，Origin 仍可选。水电月预算二分保留原式，数组化使单个合成8760小时运行本机从约0.267秒降至0.102秒；此基准不代表所有项目的总耗时。Python plotting is a selectable, tested fallback.
- 分区综合工作簿改为流式写入以降低8760×分区数的峰值内存；机组技术与抽蓄/电池分开输出。The output keeps four auditable sheets and separate technology columns.

- EXE增加分区CSV选择、公开合成输入生成、启发式或Gurobi LP模式和逐区8760小时缩放查看；输出独立的综合工作簿、逐时CSV、联络线表与输入哈希。The zonal functions now have a desktop and batch input/output path.
- 四区纯合成8760小时案例的电力、碳、SO₂、新能源逐时守恒均通过；24小时两区已知答案同时覆盖启发式与LP，交流边在启发式入口被拒绝。All values and emission factors in the sample are synthetic; connectivity directions alone are public evidence.
- 分区入口仍独立于GA/DP，固定储能计划尚未核对SOC；本阶段未宣称网络约束规划或完整经济MRIO。Network-constrained planning and storage-coupled zonal optimization remain future work.

## 2026-10-14 — Stage 0.2.7 / 风光弃电、分区试验与统一报告

- 项目运行的富余风光按可用份额分摊弃电，三年度纯合成案例重跑、独立物理回算后同时出现弃风和弃光；12张月图、五种缩放图及Origin GA/DP图重新生成。The synthetic GA/DP case and figures were regenerated after the curtailment rule change.
- 新增独立分区小时LP、仅适用可控通道的启发式路径调度、8760小时合成网络试验及碳/SO₂/新能源属性追踪。公开资料仅确定示意连接方向，容量、电纳和需求均为合成假设；这些API尚未接入应用规划入口。Zonal transfer and physical attribute tracing are verified modules, not a production network model.
- 研究报告合并成五章，GitHub数学公式改为$...$/$$...$$，19张新版图直接嵌入。Real project inputs and derived outputs remain local.

## 2026-10-14 — Stage 0.2.6 / 动态规划过程可见性

- 每年度最多约16次状态评价进度通知，显示本年与总体已完成状态数及百分比；后台计算仍通过线程安全队列传回窗口。The long multi-year run now reports bounded, monotone progress within each annual state sweep.
- 费用、运行模型和遗传算子未改动；合成回归核对阶段表、所选路径和逐时物理残差。No planning or dispatch equation changed in this release.

## 2026-10-14 — Stage 0.2.5 / 多年度GA初代均衡

- 多年度GA的单项目Gen=0种子改按规划年交织，任意容量截断前缀的年度种子数最多相差1；旧版末年整块优先排序不再默认。Multi-year single-project seeds are interleaved across years before population truncation, removing a structural late-year preference.
- 在同一三年度合成768状态费用表上重复4组预算×20种子；完整费用表指纹与DP/Gurobi最优未变。旧/新命中次数为1→8、1→8、20→10、20→20；新版34个被选年度状态独立回放8760小时。The before/after comparison exposes the old Gen=0 optimum-seeding artifact without changing hourly costs or feasibility.
- 运行清单及阶段审计新增初代策略标识 `balanced_by_stage_v2`，使相同GA参数跨版本复算时可追溯。Planning archives now record the initial-population policy version.

## 2026-10-14 — Stage 0.2.4 / 全规划年源库阶段

- 在同一三年度合成8760小时状态费用表上增加4组搜索预算×20随机种子的GA敏感性表、独立费用验收与59个所选年度状态物理回放；披露小种群的Gen=0种子截断偏置。Added a transparent 80-run synthetic GA budget check with independent objective verification and physical replay; its seed-order limitation is explicit.
- 加入三年度八类电源完全合成GA/DP同口径算例：768个年度运行状态、独立费用/物理回算、Origin阶段图、末年8760小时表与12张月图；全部示例与外部项目库隔离。Added a fully synthetic three-stage eight-technology comparison with 768 annual states, independent audit, figure and tables.
- 新增双年度/全规划年可选范围；全规划年逐年读取基年之后至终期的年度库，并拒绝用单一负荷系数伪造多年输入。Added an optional full annual-source horizon alongside the existing two-year mode.
- 所有阶段保持终期候选位一致；年度独有计划项目按对应年度列入外生容量和年化费用报表，Bellman、Gurobi与GA共用阶段费用。Exogenous annual commitments are reported by year, with the same stage-cost tables used by all three algorithms.
- 阶段工作簿新增逐年GA/DP状态、可行性及折现费用对照页与CSV，并验证GA逐年费用能加总回其总目标。Added a per-year GA/DP cost comparison table with an objective reconciliation check.
- EXE批处理新增种群、代数和随机种子参数，并将规划所用值写入运行清单；同输入但不同GA设置不能误称为算法随机失效。The packaged batch entry now accepts and records GA controls for reproducible source/EXE comparisons.
- 三阶段已知答案与8760小时合成集成通过；本地多阶段源库通过逐年输入哈希、物理守恒和费用复核。Synthetic known-answer and local annual-stage audits passed; project-derived details remain private.

## 2026-10-14 — Stage 0.2.3 / 中间年度计划增量处理

- 中间年度源库含有终期候选清单之外的计划增量时，按当年外生投运计入供给与年化费用，并在存档中警示；同站容量及最低出力按容量守恒聚合。Source-year-only planned increments are treated as exogenous for that year, charged annualized fixed cost, and explicitly warned; same-station capacity and minimum output are aggregated consistently.
- 新增合成已知答案，检查25 MW外生增量和1000元年费；0.2.1/0.2.2的年度源库模式结果应重算。A synthetic known-answer case verifies physical capacity and fixed cost; prior source-mode outputs must be rerun.
- 年度外生容量及年化费用单列在阶段工作簿和CSV；EXE与源码的输入指纹、规划路径及费用一致，私有试算结果仅留本机。The stage workbook and CSV disclose exogenous commitments, and packaged/source results agree under the same fingerprint; project details remain local.

## 2026-10-14 — Stage 0.2.2 / 年度存量容量修正

- 修正年度源输入模式：前一年既有机组有效装机从前一年源库读取，终期只定义共同候选位与设计容量。Correct annual source-mode dispatch to use that year's existing capacity, while terminal data defines the common optional-project bits.
- 加入“前一年50 MW、终期100 MW、负荷75 MW”的8760小时缺供与功率守恒反例；旧版年度源模式结果需重算。Added a synthetic physical counterexample; prior source-mode results must be rerun.
- 桌面窗口明确显示版本号，便于区分仍在运行的旧版与新版。The desktop title displays its version so an older open window can be identified.

## 2026-10-14 — Stage 0.2.1 / 年度阶段源输入

- 双年度动态规划默认使用前一年与目标年各自的负荷、外送、风光和水文曲线，保留终期共同候选位。Two-year DP now defaults to separate annual input profiles while maintaining a common candidate encoding.
- 保留可选的负荷系数情景，并在阶段表和清单中记录模式及逐时输入指纹。The optional scaled scenario remains available; reports record the input mode and hourly-input hashes.
- 增加年度曲线对齐与缺失曲线拒绝测试。Synthetic tests cover source-profile alignment and missing renewable data.

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
