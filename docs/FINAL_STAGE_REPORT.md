# GRIDMIND 阶段成果总览 / GRIDMIND stage delivery

本报告汇总截至 0.2.6 的**已验收能力**。公开的算例数值、曲线、图片和工作簿均来自仓库内固定种子合成案例；测试数量与发布状态则来自本地验收记录。本地项目输入、项目派生结果、逐时表、图片、路径及输入指纹没有进入公开仓库。This report covers verified v0.2.6 capabilities. Published case artifacts are synthetic; project-derived material stays local.

## 1. 程序与架构 / Application and architecture

Windows 单文件应用有原创图标，前端 `gridmind_app/` 与算法 `power_ga/` 分开维护。数据采集、Gen=0、全年运行、适应度与收敛、遗传迭代、动态规划、输出各有模块目录；关键函数旁保留中文作用、单位与公式注释。应用支持单年 GA、双年度 DP、完整年度序列 DP、仅运行存量系统，并能重开历史结果。The desktop app and algorithm modules share one calculation entry point and archive runs for reuse.

运行图以一张堆叠图呈现八类电源、储能充放电、弃风弃光与醒目的负荷线；窗口可按日、周、月、年和任意小时区间缩放。表格与图片分目录存档；[五种合成缩放视图](PREVIEWS.md)及[12 张末年月图](FULL_HORIZON_GALLERY.md)可直接预览。The viewer uses one stack chart, while numerical tables and figure files remain separate.

## 2. 运行与规划方法 / Operation and planning methods

全年运行按 365×24 小时单区域功率平衡计算，覆盖煤电、燃气、常规水电、抽水蓄能、电池、风电、光伏和生物质。抽蓄与电池的内部能量跨日、跨月递推；常规水电使用月可用电量上界。单年 GA 包含编码、初代、选择、交叉、变异、精英保留和停滞判断。多年度 DP 以累计投运项目集合为状态，Bellman 递推求阶段路径，Gurobi 对相同已评价状态费用作独立 0/1 路径核验；同口径 GA 查询同一费用表。The Gurobi state model verifies construction timing over precomputed hourly state costs.

0.2.5 修正小种群 Gen=0 按末年整块排序的偏置，改用可复现的年度交织种子；0.2.6 在每个年度内部按批次显示状态计算进度。新进度只按已完成状态数计数，不预测剩余时间，也不改变目标函数。公式、费用口径与约束见[数学推导](MATHEMATICS_APPENDIX.md)。The seed policy is versioned in result archives; progress reporting leaves dispatch and optimization equations unchanged.

## 3. 完整公开合成案例 / Complete public synthetic case

三年度八类电源案例有三个合成年份、八个候选项目，共 \(3\times2^8=768\) 个年度状态；每个状态评价 8760 小时。Bellman、Gurobi 与固定种子同表 GA 均选择累计状态 `(0,2,2)`，折现目标约 **369,286,121.94 元**。独立回放所选年度的逐时功率、储能与月水电约束；最大功率残差 **2.84×10⁻¹⁴ MW**，最大储能状态残差 **3.55×10⁻¹⁵ MWh**，月水电预算超额 **0 MWh**。末年八类电源均有正的实际出力或放电量。[完整案例与合并工作簿](CASE_STUDY.md)分别说明 GA、DP 与比较口径。These numbers describe a seeded teaching case, not a regional planning recommendation.

同一 768 行状态费用表上，旧/新初代策略在四组“种群/最多代数”预算、各 20 种子中的最优命中分别为 `1→8`、`1→8`、`20→10`、`20→20`。种群和代数同时变化，且旧版种群 12 曾在初代直接含有本例最优路径，因此这些频数不能外推为一般成功率或速度结论。[逐种子表及推导](CASE_STUDY.md#有限搜索预算与随机种子--limited-budget-seed-sensitivity)保留正反两面的观察。The comparison isolates a seed-order policy change on one fixed synthetic state table.

## 4. 验收与交付 / Verification and delivery

0.2.6 的本地 **45 项**（含发布门测试）、独立公开仓库 **40 项**测试通过。三年度合成案例在 0.2.6 下重跑，完整状态表、GA 历史、终期逐时与逐站储能 CSV 均与 0.2.5 **逐字节相同**，并再次通过物理独立验收。0.2.6 版本化 EXE 的后台启动、Gurobi 可用性、五种缩放图导出通过。**本地完整逐年源库的源码与 EXE 精确对照使用 0.2.5 版**：路径、费用及逐时输出一致，终期和所有较早阶段均通过独立物理与费用核验；0.2.6 仅修改进度通知，未重新执行该私有全量对照。这些项目验收细节只存本机。The private source-versus-EXE audit belongs to v0.2.5; v0.2.6 has full synthetic numerical parity and packaged smoke checks.

公开发布从独立目录按精确文件清单导出，先扫描候选源文件，再复制并复扫文本、XLSX 内部 XML 和图片元数据；MIT、文件 SHA-256 清单、相对链接、提交变更清单与远端提交均核对。0.2.6 [源代码提交](https://github.com/Entropyneverfade/GRIDMIND/commit/4f58b121715174901328af5bc926bcbf0b8b11d4)、[使用说明](USER_GUIDE.md)、[持续进度](PROGRESS_2026-10-14.md)和[开发计划](ROADMAP.md)可直接查看。The Windows EXE is delivered locally; the public repository contains source, architecture, synthetic exhibits and derivations.

## 5. 适用边界与后续 / Limits and next steps

当前是确定性单区域研究原型。尚未实现线路潮流与 N−1、概率 EENS/LOLE、完整水库级联、机组最小开停机与全年全局最优机组组合；真实成本仍需项目报价校准，不能以试算参数作投资结论。下一阶段优先按[开发计划](ROADMAP.md)加入建设工期与退役状态、网络约束、多天气年/故障情景及更完整的水电和机组运行约束；每项仍需先有合成已知答案和守恒残差验收。The current outputs support transparent method testing and do not establish network security or probabilistic adequacy.
