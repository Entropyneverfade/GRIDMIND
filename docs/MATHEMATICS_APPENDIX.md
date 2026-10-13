# GRIDMIND 推导附录 / Derivation appendix

本附录只说明公开代码当前实施的确定性、单区域规划与运行规则。所有例子均为人工合成，不对应任何实际项目。This appendix derives the rules implemented in the public code. Every numerical example is synthetic.

## 1. 时间、单位与建设变量 / Time, units and build variables

令 \(t=0,\ldots,8759\)，\(\Delta t=1\,\mathrm h\)。功率用 MW，能量用 MWh，费用用元。365 日规划年按自然月分段；闰年输入在导入时删除 2 月 29 日。Let \(J\) be candidate projects, and let \(x_j\in\{0,1\}\) indicate whether project \(j\) is built. Existing capacity is always included; selected incremental capacity is added by station ID:

\[
\overline P_i(x)=\overline P_i^{\rm existing}
+\sum_{j:\,s(j)=i}x_j\Delta P_j.
\]

同站新增容量只合并额定功率，逐站技术参数仍由输入记录解释。A chromosome is a candidate build plan, not an hourly dispatch vector.

## 2. 年化目标与成本 / Annualized objective and costs

\[
C(x)=C_{\rm fixed}(x)+C_{\rm variable}(x),\qquad
C_{\rm fixed}(x)=\sum_{j\in J}x_j a_j,
\]

\[
C_{\rm variable}(x)=\sum_t\Delta t\left[
\sum_{i\in\mathcal D}c_i p_{i,t}
+\sum_{i\in\mathcal R}c_i p_{i,t}^{\rm delivered}
+\sum_{s\in\mathcal S}c_s p_{s,t}^{\rm dis}\right].
\]

\(\mathcal D\) includes coal, gas, biomass and conventional hydro; \(\mathcal R\) includes wind and PV; \(\mathcal S\) includes pumped and battery storage. 弃电不计为已交付发电，储能只对放电量计输入表中的单位变动费。年化固定费以资本回收系数 \(CRF=r(1+r)^n/[(1+r)^n-1]\) 建立可编辑试算值；输入成本不是项目报价。

## 3. 逐站可再生能源与弃电 / Station-level renewable availability

对风、光电站 \(i\)，单位值曲线 \(0\le u_{i,t}\le1\) 给出可用功率
\(A_{i,t}=\overline P_i u_{i,t}\)。技术汇总 \(A_{k,t}=\sum_{i\in k}A_{i,t}\)，实际交付功率 \(p_{k,t}=A_{k,t}-q_{k,t}\)，其中 \(q_{k,t}\ge0\) 为弃风或弃光。The dispatch rule first charges storage with surplus, then curtails PV, then wind. When multiple stations share one technology, delivered output and variable cost are apportioned in proportion to each station's available MW.

该弃电顺序是可复现的规则假设，不是价格或电网约束优化的结论。The curtailment order is a documented rule, not an optimized market outcome.

## 4. 电力平衡及诊断残差 / Balance and audit residual

定义总需求 \(D_t=D_t^{\rm domestic}+D_t^{\rm export}\)。每小时满足

\[
\sum_{i\in\mathcal D}p_{i,t}+p_{w,t}+p_{pv,t}
+\sum_s p^{\rm dis}_{s,t}+ENS_t
=D_t+\sum_s p^{\rm ch}_{s,t}+X_t,
\]

其中 \(ENS_t\) 是缺供 MW，\(X_t\) 是物理过剩 MW；两者作为诊断量原样报告。The saved residual is left side minus right side. Since \(\Delta t=1\) h, an hourly MW value has the same numerical value as its MWh contribution, but the units remain distinct. The annual energy sum is \(\sum_t p_t\Delta t\).

**合成手算 / Synthetic check:** 需求 100 MW，常规出力 60 MW、风 25 MW、光 10 MW、储能放电 5 MW、充电 0 MW，则 \(60+25+10+5=100\)，残差为 0 MW。The example is purely illustrative.

## 5. 日前开机与逐时经济顺序 / Day-ahead commitment and hourly dispatch

设净需求 \(N_t=\max(0,D_t-A_{w,t}-A_{pv,t})\)，在线备用比率 \(r_{op}\)。每个 24 小时块的开机容量目标为

\[
K_d=\max_{t\in d}\{N_t+r_{op}D_t\}.
\]

程序按变动费、站号排序常规机组，逐台开机直到累计可信开机容量达到 \(K_d\) 或机组耗尽。煤、气、生物质按额定 MW；水电按该日逐时水电计划上限的最小值计入，避免无水小时虚报全天容量。It then applies each online plant's minimum output \(m_i\overline P_i\), and fills remaining demand in the same merit order up to its hourly maximum. This is a deterministic commitment heuristic; start-up cost, minimum on/off time and ramp constraints are not solved here.

## 6. 水电月预算与二分分配 / Monthly hydro budget and bisection

对每座常规水电站 \(i\) 与月 \(m\)，月可用电量上限为

\[
B_{i,m}=\overline P_i H_m u_h f_{i,m},\qquad u_h=0.42,
\]

其中 \(H_m\) 是月小时数，\(f_{i,m}\) 是输入月系数。令 \(w_t=\max(0,D_t-A_{w,t}-A_{pv,t})\)，计划曲线是

\[
\widehat p_{i,t}=\min(\overline P_i,\lambda_m w_t),\qquad
F_m(\lambda)=\sum_{t\in m}\widehat p_{i,t}\Delta t.
\]

\(F_m(\lambda)\) 单调不减；二分 \(\lambda_m\) 使 \(F_m\) 接近但不超过 \(\min(B_{i,m},\overline P_iH_m)\)。程序运行时再以月剩余预算和计划值限制实际出力。If all \(w_t=0\), the target is zero and the unused budget is reported. The monthly budget is an upper bound, not a must-generate energy contract; this approximation does not model reservoir state, inflow or cascades.

## 7. 两类储能的连续状态 / Continuous storage state

抽蓄和电池分别按站维护状态。输入仅给往返效率 \(\eta^{RT}\) 时，明确取 \(\eta^{ch}=\eta^{dis}=\sqrt{\eta^{RT}}\)，故二者乘积是所给效率。For each storage asset \(s\):

\[
E_{s,t+1}=E_{s,t}+\eta_s^{ch}p^{ch}_{s,t}\Delta t
-p^{dis}_{s,t}\Delta t/\eta_s^{dis},
\quad 0\le E_{s,t}\le\overline P_s T_s.
\]

\[
0\le p_{s,t}^{ch}\le \overline P_s\rho_s^{ch},\qquad
0\le p_{s,t}^{dis}\le\overline P_s,\qquad
p_{s,t}^{ch}p_{s,t}^{dis}=0.
\]

\(T_s\) 为额定小时数，\(\rho_s^{ch}\) 为充电功率比例。年初 \(E_{s,0}=0\)，日、月边界不重置，年末库存按实值报告。Charging first absorbs surplus from online minimum output and available renewables. Discharging is requested when the residual exceeds the mean renewable-adjusted demand in the next up-to-24-hour lookahead or exceeds online conventional capacity, subject to available energy and power. This is an operating rule, not a globally optimal arbitrage schedule.

**合成手算 / Synthetic check:** \(\eta^{RT}=0.81\)，则 \(\eta^{ch}=\eta^{dis}=0.9\)。从零库存充电 10 MW 一小时，\(E=9\) MWh；下一小时最多从这笔电向电网放出 \(9\times0.9=8.1\) MWh, matching the 81% round trip.

## 8. 在线备用与规划备用 / Online and planning reserves

在线备用需求 \(R_t^{req}=r_{op}D_t\)，常规在线机组剩余上限为 \(\sum_{i\in online}(\overline p_{i,t}-p_{i,t})\)。非充电储能只能用尚未放电的功率和可持续一小时的库存参与：

\[
R_{s,t}^{up}=\min\!\left(\max(0,\overline P_s-p_{s,t}^{dis}),
E_{s,t+1}\eta_s^{dis}/1\,\mathrm h\right),
\]

\[
R_t^{available}=\sum_{i\in online}(\overline p_{i,t}-p_{i,t})
+\sum_{s:p^{ch}_{s,t}=0}R_{s,t}^{up},\quad
G_t^{op}=\max(0,R_t^{req}-R_t^{available}).
\]

规划备用另算 \(F(x)=\sum_{i\in\{coal,gas,hydro,biomass\}}\overline P_i(x)\)，要求 \(F(x)\ge(1+r)\max_t D_t^{domestic}\)。风光与储能在本基线的规划容量信用为零；水电按额定值计入的简化可能高估可信容量。These two reserve tests answer different questions and are both enforced. They are not LOLE, EENS or ELCC.

## 9. 可行性、违反量与遗传适应度 / Feasibility, violation and GA fitness

项目算例的硬约束为 \(ENS^{yr},X^{yr},G^{op,yr}\le10^{-4}\,\mathrm{MWh}\) 和规划容量缺口 \(G^{firm}\le10^{-6}\,\mathrm{MW}\)。数值容差处理浮点残差，不放宽物理问题。The nonnegative normalized violation used **only to order infeasible candidates** is

\[
v(x)=\frac{ENS^{yr}+X^{yr}+G^{op,yr}}{\max(\sum_tD_t^{domestic}\Delta t,1)}
+\frac{G^{firm}}{\max(\max_tD_t^{domestic},1)}.
\]

比较键为可行方案 \((0,C)\)；不可行方案 \((1,v,C)\)。Thus any feasible plan outranks every infeasible plan. For parent selection, at least two feasible chromosomes cause a feasible-only roulette pool. Otherwise, infeasible entries receive the selection-only adjusted cost \(C'_i=C_i+100C_{max}(1+v_i)\); this penalty does **not** change the reported objective or feasibility.

若候选父代池有 \(N\ge2\) 个正费用 \(C'_i\)，所用轮盘赌概率为 PPT 对应的归一化式：

\[
\pi_i=\frac{\sum_{k=1}^{N}C'_k-C'_i}
{(N-1)\sum_{k=1}^{N}C'_k},\qquad
\sum_i\pi_i=1.
\]

低成本获得更高抽取概率，但不是必然被选中。With synthetic costs \((100,200,300)\), probabilities are \((5/12,1/3,1/4)\).

## 10. 初代、交叉、变异与停止 / Population and convergence

Gen=0 包含全不建、全建及由固定随机种子生成的 Bernoulli 个体。父代按 \(\pi_i\) 有放回抽取；单点交叉在 \(1\ldots |J|-1\) 之间选切点，两个子代交换尾段；每位以变异概率 \(p_m\) 执行 \(b'=1-b\)。The best ranked \(e\) chromosomes are copied unchanged into the next generation (elitism). Identical chromosomes reuse their deterministic 8,760-hour evaluation through a cache.

只有找到可行方案、达到最小代数且历代最优连续指定代数未改善时才提前停止；否则运行至最大代数。The history stores current and all-time best cost, feasible population count, mean/median cost, chromosome diversity and stop reason. A flat cost trace without feasibility is never reported as successful convergence.

## 11. 可复核守恒量与适用边界 / Reproducible invariants and scope

每小时核对电力平衡残差 \(\varepsilon_t^{bal}\)；每站储能核对
\(\varepsilon_{s,t}^{E}=E_{s,t+1}-E_{s,t}-\eta^{ch}p^{ch}_{s,t}\Delta t+p^{dis}_{s,t}\Delta t/\eta^{dis}\)。月水电实际电量不得超过 \(B_{i,m}\)，储能状态须在 \([0,\overline P_sT_s]\)。These audits test consistency of the implemented rule. They do not validate forecast uncertainty, network security, dynamic stability or market behavior.

Current scope: one region, deterministic hourly profiles, fixed hourly exports, rule-based commitment, no branch power flow, no N-1 contingency, no probabilistic reliability, no reservoir cascade. Optional finite-window Gurobi runs must be identified as finite-window optimization, not a globally optimal yearlong plan.

## 12. 多年度动态规划 / Multi-year dynamic programming

与单年度 \(x_i\in\{0,1\}\) 不同，多年度状态 \(s_t\in\{0,1\}^{|J|}\) 表示第 \(t\) 个规划年末已投运候选集合。阶段建设决策 \(u_t=s_t-s_{t-1}\ge0\) 按位理解，已投运机组不会在此简化模型中退役。The first state starts from no optional projects, and each transition may add projects but not remove them.

阶段 \(t\) 对每个状态运行自身的 8,760 小时负荷、电源及储能模拟，得到实际发电变动费 \(C_t^{op}(s)\)。已投运项目的年化建设费为 \(C_t^{ann}(s)=\sum_i s_i A_i\)，其中 \(A_i\) 是元/年的等年值。因此阶段费 \(c_t(s)=C_t^{ann}(s)+C_t^{op}(s)\)，并只让满足缺供、备用、过剩和容量硬约束的状态参加递推。Every annual scenario has its own feasible-state set \(\mathcal F_t\).

以首个规划年为基准、贴现率 \(r\)，顺序 Bellman 递推写为

\[
F_0(0)=0,\quad F_0(s\ne0)=+\infty,\qquad
F_t(s)=\frac{c_t(s)}{(1+r)^{t-1}}
+\min_{p\subseteq s}F_{t-1}(p),\quad s\in\mathcal F_t.
\]

前驱集合 \(p\subseteq s\) 正是“不拆除既有候选项目”的状态转移条件。回溯最小末状态得到每年建设位。With \(n\) candidates, a full stage has \(2^n\) states; naive predecessor enumeration scales as \(3^n\) per transition, so the desktop version currently caps \(n\le8\).

Gurobi 独立解 0/1 状态模型：\(z_{t,s}=1\) 表示阶段 \(t\) 取状态 \(s\)。目标与 DP 一致；约束为每阶段一个状态、逐项目累计投运位不下降：

\[
\min_z\sum_t\sum_{s\in\mathcal F_t}
\frac{c_t(s)}{(1+r)^{t-1}}z_{t,s},\quad
\sum_{s\in\mathcal F_t}z_{t,s}=1,\quad
\sum_{s\in\mathcal F_{t-1}}s_i z_{t-1,s}
\le\sum_{s\in\mathcal F_t}s_i z_{t,s},\quad z_{t,s}\in\{0,1\}.
\]

逐年只选一个状态使单个位不下降的约束等价于合法建设路径。DP 与 Gurobi 目标必须在 0.01 元或 \(10^{-8}\) 相对误差内一致；最终路径各年重新运行 8,760 小时并核验最大功率平衡残差不超过 \(10^{-6}\) MW。This cross-check certifies the finite enumerated path under the stated deterministic operation model, not the physical completeness of that model.

同口径多年度 GA 把每年的新建决策按 \(t\times |J|+i\) 编码，重复建设位按最早投运年归并；累计状态和费用表与 DP 共用。其相对差距为 \((C^{GA}-C^{DP})/C^{DP}\)，只对该有限合成案例解释，不推广为算法性能定律。For the complete numerical audit, see [synthetic case and comparison](CASE_STUDY.md).
