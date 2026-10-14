# 数学模型与代码对应

本文对应公开版 0.2.14 的项目运行器。$`h`$ 表示小时，$`t`$ 表示规划年，$`\Delta t=1\,\mathrm h`$。完整年度为 8760 步。以下数学记号与代码字段的英文名称可同时保留，正文采用中文。

## 1. 年度费用

令 $`x_j(S)`$ 表示状态 $`S`$ 是否包含候选 $`j`$，$`a_{j,t}`$ 为候选已年化费，$`a^{\mathrm{exo}}_{i,t}`$ 为已并入该年存量记录的外生计划年化费。

```math
K_t(S)=\sum_j x_j(S)a_{j,t}+\sum_i a^{\mathrm{exo}}_{i,t}.
```

```math
C_t(S)=K_t(S)+\sum_h\Delta t\sum_{i\in\mathcal P_t}c_i p_{i,h}
+\sum_{g,h}\kappa_g\max(0,u_{g,h}-u_{g,h-1}).
```

$`\mathcal P_t`$ 中每个技术对象只出现一次：常规和风光取实际发电，储能取放电。启动费按次计入 `variable_cost`；年初 $`u_{g,-1}=0`$。成本 CSV 已给年化值，评价时不重复做资本回收。实现：[年度评价](../power_ga/genetic_iteration/project_solver.py)、[运行费用](../power_ga/operation_simulation/project_engine.py)。

## 2. 功率与风光分摊

```math
\sum_g p_{g,h}+p_{w,h}+p_{v,h}+\sum_s p^{\mathrm{dis}}_{s,h}+q_h^{\mathrm{short}}
=L_h^{\mathrm{dom}}+L_h^{\mathrm{exp}}+\sum_s p^{\mathrm{ch}}_{s,h}+q_h^{\mathrm{excess}}.
```

风光可用功率为容量乘容量因子，实际消纳为 $`p_{r,h}=A_{r,h}-q_{r,h}^{\mathrm{curt}}`$。剩余弃电按同小时风光可用量比例分摊；同技术实际消纳再按各站可用量占比分配。可用总量为零时该类出力和弃电都为零。斜线弃电不计入已供电量。

## 3. 储能连续库存

```math
E_{s,h+1}=E_{s,h}+\eta_s^{\mathrm{ch}}p_{s,h}^{\mathrm{ch}}\Delta t
-\frac{p_{s,h}^{\mathrm{dis}}\Delta t}{\eta_s^{\mathrm{dis}}},\qquad
0\le E_{s,h}\le\bar P_s T_s.
```

```math
0\le p_{s,h}^{\mathrm{ch}}\le\bar P_s\rho_s^{\mathrm{ch}},\qquad
0\le p_{s,h}^{\mathrm{dis}}\le\bar P_s,\qquad
p_{s,h}^{\mathrm{ch}}p_{s,h}^{\mathrm{dis}}=0.
```

只有往返效率时采用 $`\eta^{\mathrm{ch}}=\eta^{\mathrm{dis}}=\sqrt{\eta^{\mathrm{RT}}}`$。年初库存为零，日月边界连续，年末库存如实报告；当前年度之间没有库存结转。放电按额定 MW 和站号排序，是规则削峰而非全时域套利优化。

## 4. 水电月电量上限

```math
B_{g,m}=\bar P_g H_m u_h f_{g,m},\qquad
\widehat p_{g,h}=\min(\bar P_g,\lambda_m N_h),\qquad
N_h=\max(0,L_h-A_{w,h}-A_{v,h}).
```

$`H_m`$ 为月小时数，输入缺乏完整水文模型时以利用率和月系数构造试算预算。二分参数使分配接近可用上限；若正净负荷小时不足或全为零，不强制耗尽预算。实际发电还受月剩余预算、机组可用容量和小时爬坡限制。没有库容—水头—级联方程。

## 5. 站级开停、爬坡与月边界

令 $`a_{g,m}`$ 为扣除月检修台数后的可用比例，$`\mu_g`$ 和 $`\mu_{g,m}^{\min/\max}`$ 为技术及月出力比例。

```math
u_{g,h}a_{g,m}\bar P_g\max(\mu_g,\mu_{g,m}^{\min})
\le p_{g,h}\le u_{g,h}a_{g,m}\bar P_g\mu_{g,m}^{\max},
```

```math
|p_{g,h}-p_{g,h-1}|\le r_g\bar P_g,\qquad p_{g,-1}=0.
```

当前只在日首决定开停；同时检查最短开/停时长及日最大启动次数。水电另受小时分配上限。上下界矛盾时拒绝输入；供需不足或过剩通过诊断量保留。试算默认值、输入生效值和来源见[参数表](../examples/results/v0.2.14/operating_parameters.csv)，不把默认值视为实测技术保证。

## 6. 两类备用与可行性

在线需求为 $`R_h^{\mathrm{req}}=\rho L_h`$。常规备用按小时剩余可增发能力与小时爬坡能力取较小值；非充电储能还须有一小时可持续库存。

```math
R_h^{\mathrm{av}}=\sum_{g\in\mathcal O_h}\min(\bar p_{g,h}-p_{g,h},r_g\bar P_g)
+\sum_{s:p^{\mathrm{ch}}_{s,h}\lt10^{-9}}
\min\left(\max(0,\bar P_s-p^{\mathrm{dis}}_{s,h}),
\frac{E_{s,h+1}\eta_s^{\mathrm{dis}}}{1\,\mathrm h}\right).
```

这里 $`\bar p_{g,h}`$ 是已受当前小时物理边界限制的上限，$`\mathcal O_h`$ 是在线集合。储能是否充电的代码判断使用微小浮点阈值。

年度缺供 $`U_t`$、过剩 $`X_t`$、在线备用不足 $`M_t`$ 均按逐时 MW 乘 $`\Delta t`$ 积分。规划备用另用常规额定 MW 与本地负荷峰值求容量缺口 $`G_t`$。可行性门为：

```math
U_t,X_t,M_t\le10^{-4}\,\mathrm{MWh},\qquad G_t\le10^{-6}\,\mathrm{MW}.
```

不可行方案辅助违反量为：

```math
v_t=\frac{U_t+X_t+M_t}{\max(\sum_hL_{t,h}^{\mathrm{dom}}\Delta t,1\,\mathrm{MWh})}
+\frac{G_t}{\max(\max_h L_{t,h}^{\mathrm{dom}},1\,\mathrm{MW})}.
```

此量无量纲，只用于排序；它不是优化目标，也不是概率风险。可行性键与轮盘赌推导见[附录](MATHEMATICS_APPENDIX.md)。

## 7. 多年度目标

```math
\min_{S_1,\ldots,S_T}\sum_{t=1}^T\frac{C_t(S_t)}{(1+r)^{t-1}},\qquad
S_{t-1}\subseteq S_t,\quad S_t\in\mathcal F_t.
```

每年费用取自身输入和同一运行规则。DP 与 Gurobi 的等价有限状态模型及归档数值示例见[推导附录](MATHEMATICS_APPENDIX.md)。最新 ZYO 接入及概率充裕度路线另见[开发计划](ROADMAP.md)，不改变本页已发布模型的定义。
