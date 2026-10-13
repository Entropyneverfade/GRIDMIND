# GRIDMIND 数学公式 / Mathematical model

这里给出当前程序实际执行的关系，符号均按单区域、1 小时步长定义。These equations describe the implemented deterministic single-region model at a one-hour time step.

## 0. 8760小时规划年 / Planning-year time base

全年固定为365日×24小时，月小时数为 \((744,672,744,720,744,720,744,744,720,744,720,744)\)，总和8760。闰年兼容曲线省略2月29日，导入时核对日期标签；水电月预算、逐月汇总和交互窗口共用这一边界。The model uses a 365-day planning year even when the input year is a leap year: February 29 is omitted and daily labels are checked. This is an input convention, not a simulation of the omitted calendar day.

## 1. 候选项目与目标 / Candidate projects and objective

对候选项目 \(j\)，\(x_j\in\{0,1\}\) 表示是否建设，\(a_j\) 是年化固定费用，\(g_{k,t}\) 是技术 \(k\) 在小时 \(t\) 的实际发电量，\(c_k\) 是变动费用：

\[
\min_x C(x)=\sum_j a_jx_j+\sum_{t=0}^{8759}\sum_k c_k g_{k,t}(x)\Delta t,
\qquad \Delta t=1\,\mathrm{h}.
\]

The GA uses feasibility-first ranking: feasible chromosomes are ordered by \(C\); infeasible chromosomes are ordered by normalized constraint violation, then by \(C\). GA 的选择、交叉、变异和精英保留只搜索建设染色体，运行模拟负责逐时评价。

## 2. 逐时功率平衡 / Hourly power balance

\[
P_t^{\mathrm{coal}}+P_t^{\mathrm{gas}}+P_t^{\mathrm{hydro}}+
P_t^{\mathrm{bio}}+P_t^{\mathrm{wind}}+P_t^{\mathrm{PV}}+
P_t^{\mathrm{dis}}+P_t^{\mathrm{ENS}}
=D_t^{\mathrm{domestic}}+D_t^{\mathrm{export}}+P_t^{\mathrm{ch}}+
P_t^{\mathrm{excess}}.
\]

风光实际出力满足 \(P_t^{r}=A_t^{r}-Q_t^{r}\)，其中 \(A\) 是容量与单位值曲线的乘积，\(Q\) 是弃电。Curtailment is recorded separately and never counted as delivered generation. 报表保留每小时平衡残差；数值容差仅用于可行性判断。

## 3. 储能库存 / Storage state

储能 \(s\) 的内部电量为 \(E_{s,t}\)，功率容量为 \(\overline P_s\)，时长为 \(H_s\)，往返效率为 \(\eta_s^{RT}\)。输入只有往返效率时，当前规则明确采用对称拆分 \(\eta_s^{ch}=\eta_s^{dis}=\sqrt{\eta_s^{RT}}\)：

\[
E_{s,t+1}=E_{s,t}+\eta_s^{ch}P_{s,t}^{ch}\Delta t
-\frac{P_{s,t}^{dis}\Delta t}{\eta_s^{dis}},
\quad 0\le E_{s,t}\le \overline P_sH_s.
\]

\[
0\le P_{s,t}^{ch}\le \overline P_s^{ch},\quad
0\le P_{s,t}^{dis}\le \overline P_s^{dis},\quad
P_{s,t}^{ch}P_{s,t}^{dis}=0.
\]

The state is never reset at midnight or month boundaries. 年初按零库存开始，避免凭空获得初始电量；年末库存如实报告。

## 4. 常规水电月水量近似 / Monthly hydro budget

当没有逐库来水和水头数据时，按月小时数 \(H_m\)、试算利用率 \(u_h=0.42\) 与输入月系数 \(f_m\) 设置预算 \(B_m=\overline P_h H_m u_h f_m\)，按小时正净负荷 \(w_t=\max(0,D_t-A_t^{wind}-A_t^{PV})\) 分配：

\[
h_t^{target}=\min(\overline P_h,\lambda_m w_t),\qquad
\sum_{t\in m} h_t^{target}\le\min(B_m,\overline P_h|m|).
\]

程序以二分法求 \(\lambda_m\)，若正净负荷时段不足以消纳月预算，差额作为未用预算报告；整月 \(w_t=0\) 时 \(h_t^{target}=0\)，不强制耗尽水量。实际出力同时受小时容量和月剩余预算限制。The monthly budget is an upper bound: if positive net demand cannot use it, the remainder is reported as unused water rather than forced generation. This transparent allocation is not a hydraulic cascade optimization.

## 5. 规划可行性 / Planning feasibility

当前项目评价要求年度缺供、物理过剩、在线备用不足分别不超过数值容差，并要求常规可信装机满足输入的规划备用率：

\[
\sum_t P_t^{ENS}\Delta t\le\epsilon_E,\quad
\sum_t P_t^{excess}\Delta t\le\epsilon_E,\quad
\sum_t \max(0,r_{op}D_t^{total}-R_t^{online})\Delta t\le\epsilon_E,\quad
F(x)\ge (1+r)\max_t D_t^{domestic}-\epsilon_P.
\]

For this baseline, \(F\) counts coal, gas, conventional hydro and biomass rated MW; this proxy may overstate hydro's actual dependable capacity. Wind, PV and storage receive zero planning firm capacity until an independent capacity-credit study is supplied. This is **not** a probabilistic EENS, LOLE or ELCC calculation. \(R_t^{online}\) 由已开机常规机组剩余能力与当时可持续1小时的储能备用组成，在线备用不足同时报告为诊断量。

日前开机以次日 \(\max_t[(D_t-A_t^{wind}-A_t^{PV})+r_{op}D_t]\) 为需求；常规水电只按次日各小时可用上限的最小值计入开机容量。储能向上备用在非充电小时为 \(R_{s,t}=\min(\overline P_s-P_{s,t}^{dis},E_{s,t+1}\eta_s^{dis}/1\mathrm h)\)，充电小时计零，避免同一功率同时承担充电和放电备用。These are conservative operational rules, not a full unit-commitment solution.

## 6. 试算成本 / Benchmark cost assumptions

年化资本费采用资本回收系数 \(CRF=r(1+r)^n/((1+r)^n-1)\)，再加固定运维；\(r\) 为折现率，\(n\) 为寿命。公开默认参数参考 [NLR Annual Technology Baseline 2025](https://atb.nlr.gov/electricity/2025/technologies)，汇率、燃料与部分技术值另列可编辑假设。This is a transparent benchmark, not a local procurement quote.

## 7. 边界 / Limitations

逐日开机与逐时经济顺序是规则近似；外送目前作为固定逐时需求，内部线路潮流未求解。The optional separate rolling optimization module is a finite-window model and must not be described as an annual global optimum. All cost parameters and hydrology utilization assumptions require local calibration before decision use.
