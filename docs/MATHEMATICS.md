# GRIDMIND 数学公式 / Mathematical model

这里给出当前程序实际执行的关系，符号均按单区域、1 小时步长定义。These equations describe the implemented deterministic single-region model at a one-hour time step.

逐项推导、合成手算、遗传算子和守恒校验见 [推导附录 / Detailed derivation](MATHEMATICS_APPENDIX.md)。

## 0. 8760小时规划年 / Planning-year time base

全年固定为365日×24小时，月小时数为 $`(744,672,744,720,744,720,744,744,720,744,720,744)`$，总和8760。闰年兼容曲线省略2月29日，导入时核对日期标签；水电月预算、逐月汇总和交互窗口共用这一边界。The model uses a 365-day planning year even when the input year is a leap year: February 29 is omitted and daily labels are checked. This is an input convention, not a simulation of the omitted calendar day.

## 1. 候选项目与目标 / Candidate projects and objective

对候选项目 $`j`$，$`x_j\in\{0,1\}`$ 表示是否建设，$`a_j`$ 是年化固定费用。令 $`\mathcal P(x)`$ 为实际投运电站集合，$`g_{i,t}`$ 为电站实际交付功率（储能取放电功率，单位 MW），$`c_i`$ 为其单位变动费；$`\mathcal D(x)`$ 为常规机组集合，$`\kappa_i`$ 为站级每次启动费：

```math
\begin{aligned}
\min_x C(x)&=\sum_{i\in I}a_i^{\mathrm{existing}}+\sum_j a_jx_j
+\sum_{t=0}^{8759}\sum_{i\in\mathcal P(x)}c_i g_{i,t}(x)\Delta t\\[2pt]
&\quad+\sum_{t=0}^{8759}\sum_{i\in\mathcal D(x)}
\kappa_i\max(0,u_{i,t}-u_{i,t-1}),\\[2pt]
\Delta t&=1\,\mathrm h,\qquad u_{i,-1}=0.
\end{aligned}
```

启动费按事件计入，代码将其累计到 `variable_cost`。输入的年化费用已完成年化，不在评价时重复折算。该目标对应给定运行规则下的建设方案搜索。

$`I`$ 为本年度既有记录；其基年存量年化费为零，只有并入年度源库的外生计划增量可能带来非零等年值。The existing-record term is zero for the base stock and carries any annual exogenous commitment that was merged into that year's records. The GA uses feasibility-first ranking: feasible chromosomes are ordered by $`C`$; infeasible chromosomes are ordered by normalized constraint violation, then by $`C`$. GA 的选择、交叉、变异和精英保留只搜索建设染色体，运行模拟负责逐时评价。

## 2. 逐时功率平衡 / Hourly power balance

```math
P_t^{\mathrm{coal}}+P_t^{\mathrm{gas}}+P_t^{\mathrm{hydro}}+
P_t^{\mathrm{bio}}+P_t^{\mathrm{wind}}+P_t^{\mathrm{PV}}+
P_t^{\mathrm{dis}}+P_t^{\mathrm{ENS}}
=D_t^{\mathrm{domestic}}+D_t^{\mathrm{export}}+P_t^{\mathrm{ch}}+
P_t^{\mathrm{excess}}.
```

风光实际出力满足 $`P_t^{r}=A_t^{r}-Q_t^{r}`$，其中 $`A`$ 是容量与单位值曲线的乘积，$`Q`$ 是弃电。Curtailment is recorded separately and never counted as delivered generation. 报表保留每小时平衡残差；数值容差仅用于可行性判断。

## 3. 储能库存 / Storage state

储能 $`s`$ 的内部电量为 $`E_{s,t}`$，功率容量为 $`\overline P_s`$，时长为 $`H_s`$，往返效率为 $`\eta_s^{RT}`$。输入只有往返效率时，当前规则明确采用对称拆分 $`\eta_s^{ch}=\eta_s^{dis}=\sqrt{\eta_s^{RT}}`$：

```math
E_{s,t+1}=E_{s,t}+\eta_s^{ch}P_{s,t}^{ch}\Delta t
-\frac{P_{s,t}^{dis}\Delta t}{\eta_s^{dis}},
\quad 0\le E_{s,t}\le \overline P_sH_s.
```

```math
0\le P_{s,t}^{ch}\le \overline P_s^{ch},\quad
0\le P_{s,t}^{dis}\le \overline P_s^{dis},\quad
P_{s,t}^{ch}P_{s,t}^{dis}=0.
```

The state is never reset at midnight or month boundaries. 年初按零库存开始，避免凭空获得初始电量；年末库存如实报告。

## 4. 常规水电月水量近似 / Monthly hydro budget

当没有逐库来水和水头数据时，按月小时数 $`H_m`$、试算利用率 $`u_h=0.42`$ 与输入月系数 $`f_m`$ 设置预算 $`B_m=\overline P_h H_m u_h f_m`$，按小时正净负荷 $`w_t=\max(0,D_t-A_t^{wind}-A_t^{PV})`$ 分配：

```math
h_t^{target}=\min(\overline P_h,\lambda_m w_t),\qquad
\sum_{t\in m} h_t^{target}\le\min(B_m,\overline P_h|m|).
```

程序以二分法求 $`\lambda_m`$，若正净负荷时段不足以消纳月预算，差额作为未用预算报告；整月 $`w_t=0`$ 时 $`h_t^{target}=0`$，不强制耗尽水量。实际出力同时受小时容量和月剩余预算限制。The monthly budget is an upper bound: if positive net demand cannot use it, the remainder is reported as unused water rather than forced generation. This transparent allocation is not a hydraulic cascade optimization.

## 4a. 常规机组启停与爬坡 / Conventional-unit chronology

令 $`u_{g,t}\in\{0,1\}`$ 表示站级聚合开机状态，$`p_{g,t}`$ 为该站逐小时平均 MW，$`\bar P_g`$ 为额定 MW，$`a_{g,m}=(n_g-v_{g,m})/n_g`$ 为扣除月计划检修台数 $`v`$ 后的可用比例，$`m(t)`$ 是小时所属月。在线下界与上界为

```math
u_{g,t}\,a_{g,m}\bar P_g\max(\mu_g,\mu_{g,m}^{min})
\le p_{g,t}\le
u_{g,t}\,a_{g,m}\bar P_g\mu_{g,m}^{max}.
```

与上一小时的出力变化还要满足

```math
-r_g\bar P_g\le p_{g,t}-p_{g,t-1}\le r_g\bar P_g,
\qquad p_{g,-1}=0.
```

若 $`u`$ 从1变0，先前连续开机时长须不少于 $`T_g^{up}`$；从0变1，先前连续停机时长须不少于 $`T_g^{down}`$。日内启动次数 $`\sum_{t\in d}\max(0,u_{g,t}-u_{g,t-1})\le N_g^{start}`$。当前调度只在日初改变 $`u`$，所以这是一条保守的站级可行规则，不是逐台机组组合优化。若最小出力、月容量、检修和爬坡相互矛盾，输入被拒绝；若供需不足或过剩，功率平衡用缺供/过剩显式记录并使规划状态不可行。The archived per-station hourly table permits an independent residual check.

源表爬坡率有效值 $`0\lt r^{minute}\lt 1`$ 按 $`r_g=60r^{minute}`$ 换算；无有效值时公开试算取煤电 $`r_g=1.2`$、$`T^{up/down}=24/12`$ h，燃气联合循环 $`r_g=3.0`$、$`6/8`$ h，依据[美国能源部技术能力表A-1](https://www.energy.gov/sites/prod/files/2017/01/f34/Principles%20for%20Increasing%20the%20Accessibility%20and%20Transparency%20of%20Power%20System%20Planning.pdf)。这些数值是跨地区技术基准，不能代替本地机组实测；生物质与常规水电的缺项另列类比假设。All effective values and their source labels are exported in the operating-parameter snapshot.

## 5. 规划可行性 / Planning feasibility

当前项目评价要求年度缺供、物理过剩、在线备用不足分别不超过数值容差，并要求常规可信装机满足输入的规划备用率：

```math
\sum_t P_t^{ENS}\Delta t\le\epsilon_E,\quad
\sum_t P_t^{excess}\Delta t\le\epsilon_E,\quad
\sum_t \max(0,r_{op}D_t^{total}-R_t^{online})\Delta t\le\epsilon_E,\quad
F(x)\ge (1+r)\max_t D_t^{domestic}-\epsilon_P.
```

For this baseline, $`F`$ counts coal, gas, conventional hydro and biomass rated MW; this proxy may overstate hydro's actual dependable capacity. Wind, PV and storage receive zero planning firm capacity until an independent capacity-credit study is supplied. This is **not** a probabilistic EENS, LOLE or ELCC calculation. $`R_t^{online}`$ 由已开机常规机组剩余能力与当时可持续1小时的储能备用组成，在线备用不足同时报告为诊断量。

日前开机以次日 $`\max_t[(D_t-A_t^{wind}-A_t^{PV})+r_{op}D_t]`$ 为需求；常规水电只按次日各小时可用上限的最小值计入开机容量。储能向上备用在非充电小时为 $`R_{s,t}=\min(\overline P_s-P_{s,t}^{dis},E_{s,t+1}\eta_s^{dis}/1\mathrm h)`$，充电小时计零，避免同一功率同时承担充电和放电备用。These are conservative operational rules, not a full unit-commitment solution.

## 6. 试算成本 / Benchmark cost assumptions

年化资本费采用资本回收系数 $`CRF=r(1+r)^n/((1+r)^n-1)`$，再加固定运维；$`r`$ 为折现率，$`n`$ 为寿命。公开默认参数参考 [NLR Annual Technology Baseline 2025](https://atb.nlr.gov/electricity/2025/technologies)，汇率、燃料与部分技术值另列可编辑假设。This is a transparent benchmark, not a local procurement quote.

## 7. 边界 / Limitations

逐日开机与逐时经济顺序是规则近似；外送目前作为固定逐时需求，内部线路潮流未求解。The optional separate rolling optimization module is a finite-window model and must not be described as an annual global optimum. All cost parameters and hydrology utilization assumptions require local calibration before decision use.

## 8. 年度动态规划 / Annual dynamic programming

候选投运状态 $`s_t`$ 只能按位从 0 转为 1；每一状态由同一8760小时运行引擎算出阶段年费用 $`c_t(s)`$。贴现后顺序递推为

```math
F_t(s)=\frac{c_t(s)}{(1+r)^{t-1}}+\min_{p\subseteq s}F_{t-1}(p).
```

Gurobi 用每年一个可行状态的0/1模型独立校验递推最优值。年度源库模式以各年度存量装机及曲线计算供给；仅中间年度出现、终期候选位之外的计划项目作为该年外生容量，年化费用加入 $`c_t(s)`$。The state cost includes annualized candidate and exogenous costs plus actual hourly variable cost; physical feasibility is enforced before a state enters the recursion. See the [complete derivation](MATHEMATICS_APPENDIX.md#12-多年度动态规划--multi-year-dynamic-programming) and [synthetic comparison](CASE_STUDY.md).

默认取相邻双年度；全规划年选项取基年之后至终期的每个年度源库，两个选项共用同一递推式。For $`T`$ annual stages and $`n`$ candidate bits, the engine evaluates $`T2^n`$ annual operating states before path optimization.
