# 未来开发计划 / Development roadmap

## 已完成并验证 / Verified

- 八类电源的 8,760 小时确定性运行、抽蓄与电池逐站库存、月水电预算上界。Eight resource classes, hourly balance, storage continuity and monthly hydro bounds.
- 单年二元遗传规划、双年度或完整年度序列的阶段状态动态规划，以及Gurobi状态路径独立核验。Single-year GA and two-year or full annual-sequence DP with Gurobi validation.
- 完整年度序列可逐年读取负荷、外送、风光及水文曲线；候选项目采用终期统一编码。Each annual stage uses its own operating profiles while preserving common project bits.
- 各年度已有机组按各自年度库的有效容量运行，候选项目仍按统一状态位投运。Existing units use year-specific effective capacity; optional projects retain common state bits.
- 仅中间年度出现的计划项目可作为该年度外生容量与年化费用输入，并单列审计。Source-year-only planned projects enter that year's supply and annualized cost as separately audited exogenous inputs.
- 原创图标 Windows EXE、规划算法切换、日周月年及任意区间窗口、图表分开存档。Windows application, algorithm selector, zoom viewer and separate table/figure archives.
- 公开合成 GA/DP 案例、两种算法同口径对比、12 张月图及完整公式。Synthetic case, comparison, monthly gallery and mathematical derivations.

## 下一阶段 / Next stage

1. 将中间年度独有项目的建设和退役也纳入内生状态转移，并加入最早可投运年份与建设工期。全规划年选项当前仍将它们作为对应年度的外生给定。Make temporary projects, commissioning and retirement endogenous; the full-horizon mode currently treats them as annual exogenous commitments.
2. DP 状态压缩、支配剪枝与可行上界，扩展超过 8 个候选位时的计算能力；对照全枚举正确性。Reduce exponential state enumeration while retaining exact checks on small cases.
3. 更完整的机组运行约束：爬坡、最小开停机、检修、启停成本、水电库容与梯级联动。Add ramping, commitment duration, maintenance, startup cost and reservoir cascade constraints.
4. 分区和线路约束、N−1 安全校验及外送交易；按节点核对功率平衡。Add network and contingency constraints with nodal audits.
5. 多天气年与故障情景的概率可靠性指标、ELCC 与投资不确定性；明确区分确定性 ENS 和概率 EENS/LOLE。Extend scenario-based adequacy and ELCC.
6. 真实数据导入模板、经济参数来源版本化、自动图像 QA 与更细的用户错误提示。Strengthen ingestion, provenance, visual QA and error reporting.

每项新能力需先有合成已知答案、守恒残差、再进入项目试算。Every feature must pass a reproducible synthetic known-answer test and physical invariant check before being reported as complete.
