# GRIDMIND 研究报告 / Research report

本报告数值、图像及工作簿仅来自固定种子的**公开合成案例**。项目库与其派生结果只留在使用者本机。图像均直接嵌入此报告，并附同一文件的原图链接。All published case artifacts are synthetic.

## 第一章：概述 / 1. Overview

### 1.1 研究对象、可检验结论和实现边界

GRIDMIND 的目标是可更换输入、费用和搜索策略的电力系统规划研究平台。本报告只陈述**当前代码已经实现**的确定性模型及其合成算例结果，不把某个算例的最优建设方案视为普适规划结论。主流程以目标年电站库、逐站风光曲线、本地负荷、计划外送和成本表为输入；单年遗传算法（GA）搜索新增项目组合，多年度动态规划（DP）搜索投运年份；每个被评价的方案都由同一个逐时运行器计算全年费用与约束。模块调用次序为“读取与校验 → 形成候选位 → 生成 Gen=0 或枚举年度状态 → 8760 小时运行 → 硬约束判别与费用计算 → 搜索/递推 → 复算中选方案 → 输出表格、审计清单和图像”。相应入口见 [`project_main.py`](../project_main.py)、[`project_case.py`](../power_ga/data_collection/project_case.py)、[`project_engine.py`](../power_ga/operation_simulation/project_engine.py)、[`project_solver.py`](../power_ga/genetic_iteration/project_solver.py) 和 [`solver.py`](../power_ga/dynamic_planning/solver.py)。桌面应用与命令行调用同一计算逻辑，存档的完整逐时表可重新打开并按日、周、月、年或任意小时区间查看。

主规划流程目前是**单区域、逐小时、确定性功率平衡**：外送作为本区已给定的逐时需求相加，不从线路阻抗或受端负荷反推；逐日机组开机及逐时经济序位是规则，不是全年全局最优机组组合。另有独立的分区 CSV 运行入口：可控通道可做确定性路径启发式调度，交流等值边可做相角约束的无损线性有功潮流，随后追踪碳、SO₂ 和物理新能源属性；它尚未进入主流程 GA/DP 的适应度。因此本报告的 DP “全局最优”仅指**给定已实现的年度运行规则、候选集合和全部预计算年度状态费用表后的最优建设路径**，并不证明全年运行调度或含网架规划的全局最优。

### 1.2 输入、时间及量纲约定

单区项目读入器以 2025 年为基年，将目标年有效电站容量与基年有效容量按电站 ID 对比：保留容量构成存量，正增量构成候选；同 ID 的存量与中选增量在运行前合并为一个电站对象。技术类型由**电站表**类型码映射为煤、气、常规水电、抽蓄、电池、风、光、生物质八类；装机由有效机组的单机容量乘有效台数得到。负荷与外送分别由额定 MW 乘 0–1 曲线生成，逐站风光出力由装机 MW 乘各自容量因子生成；不对缺失小时插值。成本 CSV 的 `annual_capital_yuan_per_mw` 是**已年化**的单位容量费，`variable_yuan_per_mwh` 是实际发/放电的边际费，不再重复做资本回收系数计算。真实项目数据留在本机，公开报告只使用固定种子合成输入。

所有年度固定为 365 日、$H=8760$ 小时，$h=0,\ldots,8759$，$\Delta t=1\,\mathrm h$；2028 等闰年输入也须省略 2 月 29 日并核对日期标签。功率用 MW，单小时电量是 $P_h\Delta t$（MWh），内部储能库存用 MWh，年度费用用元/年，贴现后多年度目标用元。$L^{\rm dom}_{t,h}$ 是本地负荷，$L^{\rm exp}_{t,h}$ 是外送义务，运行器实际满足 $L_{t,h}=L^{\rm dom}_{t,h}+L^{\rm exp}_{t,h}$；规划额定容量备用校验只用本地负荷峰值，逐时在线备用要求则按上述总负荷计算。这两个备用指标定义不同，不能互相替代。

### 1.3 可复现链条及适用范围

公开合成案例由 [`synthetic_eight_type.py`](../examples/synthetic_eight_type.py) 用固定随机种子生成八类电站与 8760 小时曲线；[`synthetic_dynamic_case.py`](../examples/synthetic_dynamic_case.py) 组成连续年份并导出每年全部状态费用、建设路径、GA 历史和审计 JSON；[`verify_dynamic_case.py`](../examples/verify_dynamic_case.py) 从合成输入独立复算被选状态，检查费用、逐时功率、储能状态及月水量上限。分区示例的四张 CSV 和相应输出由 [`synthetic_network_case.py`](../examples/synthetic_network_case.py) 生成，正式 CSV 读取与守恒校验在 [`network_case.py`](../power_ga/operation_simulation/network_case.py)。运行步骤见 3.7 节及[使用指南](USER_GUIDE.md)。同一结果应记录输入文件/数值曲线指纹、软件版本、GA 随机种子与代数设置、求解器许可和输出路径；真实项目的 `run_manifest.json` 保存相关源工作簿及阶段输入 SHA-256，合成分区运行清单保存四张 CSV 的 SHA-256。

本研究边界仍包括：没有完整非线性交流潮流和电压无功约束，没有随机停运抽样得到的 EENS/LOLE，没有库容—水头—上下游耦合的梯级水电调度，没有全年全局最优机组组合、启停爬坡及 N−1 校验。它们是平台后续研究任务，不能由现有确定性缺供量、额定备用或分区线性有功潮流推断。The platform exposes auditable methods and inputs; the published case artifacts are synthetic.

## 第二章：GA算法和动态规划算法 / 2. GA and DP

### 2.1 从项目数据构成二进制决策

令 $J=\{0,\ldots,n-1\}$ 为按读入顺序固定的候选增量，$t=1,\ldots,T$ 为连续规划年。单年染色体 $b=(b_0,\ldots,b_{n-1})$，$b_j=1$ 表示该目标年建设候选 $j$。多年度用**累计**投运位 $x_{j,t}\in\{0,1\}$，初始 $x_{j,0}=0$，且 $x_{j,t-1}\le x_{j,t}$，即建成后不退出；当年新增位是 $d_{j,t}=x_{j,t}-x_{j,t-1}\in\{0,1\}$。代码以整数掩码 $S_t=\sum_j2^jx_{j,t}$ 存状态，因此“前一年是本年子集”可直接检查 $S_{t-1}\mathbin{\&}S_t=S_{t-1}$，新增位掩码为 $S_t\mathbin{\&}\mathord{\sim}S_{t-1}$。例如两项目时，$S=2$ 即第二项目已投运，允许的后继为 $2$ 或 $3$，不允许回到 $0$ 或 $1$。

终期候选的身份、技术、增量容量和位序在各年必须相同。读取真实年度库时，每年的存量、负荷、外送、风光曲线与来水因子可变化；中间年出现而终期候选位不存在的增量按当年**外生计划**并入存量及该年年化费用，下一年不凭空继承。完整年度序列读取各年源库；相邻双年度也可由用户显式选择“终期负荷乘前一年系数”情景。不同阶段一旦候选身份或连续年份不一致，求解器拒绝运行，防止同一位在不同年指向不同电站。实现见 [`align_stage_case`](../power_ga/data_collection/project_case.py) 和 [`_validate_cases`](../power_ga/dynamic_planning/solver.py)。

### 2.2 先运行、再计费、最后判断可行

对确定的年度状态 $S$，先把存量和已投运候选按电站 ID 合并，再执行第三章的 8760 小时规则运行。令 $K_{j,t}^{\rm ann}$ 为候选增量已年化固定费，$K_{e,t}^{\rm ann}$ 为少数中间年外生增量的已年化费，$p_{g,t,h}$ 为常规机组实际发电或储能实际放电，$p_{r,j,t,h}$ 为风光电站实际消纳发电，则实际代码的费用分解为

$$F_t(S)=\sum_{j\in J}x_j(S)K_{j,t}^{\rm ann}+\sum_{e\in\mathcal E_t}K_{e,t}^{\rm ann},$$

$$O_t(S)=\Delta t\sum_{h=0}^{8759}\left[\sum_{g\in\mathcal G_t(S)}c_{g,t}p_{g,t,h}+\sum_{s\in\mathcal S_t(S)}c_{s,t}p^{\rm dis}_{s,t,h}+\sum_{r\in\{w,\odot\}}\sum_{j\in\mathcal R_{r,t}(S)}c_{j,t}p_{j,t,h}\right],\qquad C_t(S)=F_t(S)+O_t(S).$$

存量的基年固定费为零；没有对充电、弃电或缺供另加目标惩罚，因为缺供与过剩通过下面的**硬约束**拒绝。风光按各站可用功率占同类总可用功率的份额，将聚合消纳出力分回站级计费。此式中的 $p$ 必须来自实际运行轨迹，不能用额定装机或可用风光量替代。对应实现为 [`simulate_project`](../power_ga/operation_simulation/project_engine.py) 和 [`evaluate_project`](../power_ga/genetic_iteration/project_solver.py)。

设年度缺供 $U_t=\sum_hu_{t,h}\Delta t$、无法消纳的物理过剩 $O_t^{\rm spill}=\sum_ho_{t,h}\Delta t$、在线备用不足 $R_t^{\rm miss}=\sum_h\max(0,R^{\rm req}_{t,h}-R^{\rm av}_{t,h})\Delta t$。当前规划容量备用代理只计煤、气、常规水电、生物质的额定 MW：$P_t^{\rm firm}=\sum_{g\in\{\rm coal,gas,hydro,biomass\}}\bar P_g$；风光和储能在这里取零可信容量，尚未通过 ELCC 或随机可靠性评估。规定 $P_t^{\rm req}=(1+m_t)\max_hL^{\rm dom}_{t,h}$，$G_t^{\rm firm}=\max(0,P_t^{\rm req}-P_t^{\rm firm})$。年度状态可行当且仅当

$$U_t\le10^{-4}\,\mathrm{MWh},\qquad O_t^{\rm spill}\le10^{-4}\,\mathrm{MWh},\qquad R_t^{\rm miss}\le10^{-4}\,\mathrm{MWh},\qquad G_t^{\rm firm}\le10^{-6}\,\mathrm{MW}.$$

这些小量是浮点验收容差，不是允许的政策性缺供指标。不可行解的排序辅助量 $v_t=(U_t+O_t^{\rm spill}+R_t^{\rm miss})/\max(\sum_hL^{\rm dom}_{t,h},1)+G_t^{\rm firm}/\max(\max_hL^{\rm dom}_{t,h},1)$ 无量纲；**只有可行状态**能成为 DP 路径或 GA 的有效答案。单年 `Evaluation.sort_key` 按“可行优先 → 可行费用低优先；不可行违约量低优先”排序。多年度评价按各年的上述条件逐年求逻辑与，费用和违约量再贴现/累计。

### 2.3 单年 GA：初代、适应度和终止条件

单年 Gen=0 首先放入全不建和全建两种基准染色体，其余每位用带固定种子的独立 0/1 抽样生成。对种群中的每个不同染色体，运行并缓存一次年度评价；相同染色体重复出现时读缓存。每代先按上面的可行性排序保留 $e$ 个精英，再从父代池抽样、做单点交叉和逐位翻转变异直到补足种群。父代池中至少有两个可行个体时只用可行个体；不足两个时保留全种群探索，但给不可行个体的选择成本加 $100C_{\max}(1+v)$ 的惩罚。对池中 $N\ge2$ 个**正的**选择成本 $\widetilde C_i$，代码沿用课件适应度并直接作为轮盘赌权重：

$$w_i=\frac{\sum_{k=1}^{N}\widetilde C_k-\widetilde C_i}{(N-1)\sum_{k=1}^{N}\widetilde C_k},\qquad\sum_iw_i=1.$$

分母来自直接求和：$\sum_i(\sum_k\widetilde C_k-\widetilde C_i)=(N-1)\sum_k\widetilde C_k$，所以 $\sum_iw_i=1$，可以直接送入随机轮盘赌。费用越低，抽中概率越高；权重只控制父代选择，**不会**把不可行方案转成可行解。两亲本在 $c\in\{1,\ldots,n-1\}$ 处交叉，以概率 $p_c$ 交换后缀；每个子代位以概率 $p_m$ 作 $b'_j=1-b_j$，新一代开头复制精英。仅当已找到可行历代最优、达到最小代数且最优排序连续 `stall_generations` 代不改进时提前停止；否则运行到代数上限，Gen=0 记作第 0 代。存档记录历代最优、本代最优、可行个体数、不同染色体数及实际不同方案评价次数。有限种群与有限代数只给启发式结果，不能据“曲线平坦”宣称最优。算法细节见 [`encoding.py`](../power_ga/initial_population/encoding.py)、[`evaluation.py`](../power_ga/fitness_and_convergence/evaluation.py)、[`genetic_iteration/solver.py`](../power_ga/genetic_iteration/solver.py)。

### 2.4 多年 GA 与 DP 的同口径比较

多年度 GA 染色体按年份顺序连接 $Tn$ 个**建设位** $y_{j,t}$。解码时执行 $x_{j,t}=\max_{\tau\le t}y_{j,\tau}$；若同一项目多次置 1，只按最早置位年投运并持续。Gen=0 保留全 0、全 1，并把“只在某年建设某一个项目”的种子按年份交织；每年先随机打乱候选顺序，再轮流取一个，避免小种群截断时只留下某一个年份的种子。该策略标识为 `balanced_by_stage_v2`。多年 GA 不重新定义成本：对解码后的每个 $S_t$，直接读取 DP 已计算的 `tables[t][S_t]`；按第 $t$ 年贴现因子 $\delta_t=(1+r)^{-(t-1)}$ 合计费用：

$$J(S_1,\ldots,S_T)=\sum_{t=1}^{T}\delta_t C_t(S_t),\qquad S_{t-1}\subseteq S_t,\quad S_t\text{ 逐年可行}.$$

DP 先对每个年度枚举 $2^n$ 个状态，每个状态**恰运行一次** 8760 小时并存下费用和可行性。初态 $V_0(0)=0$，其余初态不可达；对每个可行 $S$，枚举所有子集 $P\subseteq S$，作 Bellman 递推

$$V_t(S)=\delta_tC_t(S)+\min_{P\subseteq S,\,P\text{ 在 }t-1\text{ 可达}}V_{t-1}(P).$$

这条递推可从总目标逐步推出：固定第 $t$ 年末状态 $S$ 后，第 $t$ 年费用 $\delta_tC_t(S)$ 与过去采用哪条合法路径无关；任何合法前态只能是 $S$ 的子集。若抵达某个前态 $P$ 的前 $t-1$ 年路径不是费用最小路径，就可以用更便宜的同终态前缀替换它而不改变第 $t$ 年可行性，故整体最优路径的前缀必为 $V_{t-1}(P)$。再在所有可达子集里取最小值，便得到上式，而非只比较上一年“当前最便宜”的单一状态。不可行状态及不可达转移赋 $+\infty$。例如 $n=2$ 且当前 $S=3$ 时，前态只需依次检查 $3,2,1,0$；当前 $S=2$ 时只能检查 $2,0$。每次存储达到最小值的父状态，末年从 $\arg\min_SV_T(S)$ 反向追溯，得到逐年累计状态及新增掩码。代码对相等费用沿枚举顺序保留先出现的父状态，终态用 `(费用, 状态整数)` 排序确定，故固定输入下路径可重复。年度评价数量为 $T2^n$，朴素子集递推最坏约 $O(T3^n)$，当前入口默认最多 8 个候选位；超过这一规模不能直接把枚举法称作可扩展规划算法。

为交叉核验，Gurobi 路径模型只为每年可行状态建立二元变量 $z_{t,S}$：$\sum_{S\in\mathcal F_t}z_{t,S}=1$；对每个候选 $j$ 约束 $\sum_{S:j\in S}z_{t-1,S}\le\sum_{S:j\in S}z_{t,S}$；目标为 $\min\sum_{t,S}\delta_tC_t(S)z_{t,S}$。由于每年恰选一个状态，这组逐位单调式等价于不撤销建设。Gurobi 与 Bellman 读取**同一已评价状态费用表**，目标容差为相对 $10^{-8}$ 或绝对 0.01 元；两者一致校验的是建设路径求解及账本，不独立证明逐时规则本身最优。中选 DP 状态再以 `keep_hourly=True` 复算完整 8760 行，并要求最大功率平衡残差不超过 $10^{-6}$ MW。GA 相对差距按 $(J_{\rm GA}-J_{\rm DP})/J_{\rm DP}$ 报告，必须同时核查 GA 路径各年可行。实现见 [`dynamic_planning/solver.py`](../power_ga/dynamic_planning/solver.py)。

## 第三章：运行模拟规则 / 3. Operation and attribute tracing

### 3.1 年度主运行器的状态初始化

给定一个年、一个候选状态后，运行器将同 ID 存量与中选增量的 MW 容量相加，得到电站集合。对每站风/光使用其各自 8760 长度的容量因子，不以一条代表曲线代替全站；聚合可用功率为 $A_{w,h}=\sum_{j\in W}\bar P_jcf_{j,h}$、$A_{s,h}=\sum_{j\in S}\bar P_jcf_{j,h}$，其中 $0\le cf_{j,h}\le1$。对每小时令 $L_h=L_h^{\rm dom}+L_h^{\rm exp}$，预先计算非负净负荷 $N_h=\max(0,L_h-A_{w,h}-A_{s,h})$。煤、气、常规水电、生物质按 `(变动费, 电站ID)` 升序排成确定的供电序位；抽蓄和电池按电站输入顺序分别保存内部库存，年初 $E_{s,0}=0$，窗口切换时不清零。输入曲线及月索引共用 365 日分段。以下规则按 $h=0$ 至 $8759$ 顺序执行；**小时之间耦合的是储能库存和剩余月水量**。

### 3.2 常规水电月水量上限与日前开机

对常规水电站 $g$、月份 $m$，令月小时数为 $H_m$，用户设置的水电利用率为 $u=0.42$，年度库的月相对水文因子为 $f_{g,m}$。初始月发电预算为 $B_{g,m}=\bar P_gH_mu f_{g,m}$ MWh；实际预分配时用 $\widehat B_{g,m}=\min(B_{g,m},\bar P_gH_m)$。在该月各小时置权重 $w_h=N_h$。若预算或所有权重为零，预定出力全为零；否则找 $\lambda\ge0$ 使

$$p^{\rm hyd,plan}_{g,h}=\min(\bar P_g,\lambda w_h),\qquad \sum_{h\in m}p^{\rm hyd,plan}_{g,h}\Delta t=\widehat B_{g,m}.$$

左式对 $\lambda$ 单调，代码以能够使正权重小时达到额定功率的上界开始，二分 60 次；水量是**可用上限**，零净负荷下允许未用水。运行到小时 $h$ 时还取 $\bar p_{g,h}=\min(\bar P_g,B^{\rm remain}_{g,m},p^{\rm hyd,plan}_{g,h})$，发电后从该月剩余预算扣除实际 MWh。因此不会因后续日窗口改变而超出月预算；这只是按净负荷形状分水的规则，没有水库库容、流量、水头、上下游时滞和级联约束。

每个 24 小时日首重算一次在线机组集合。令在线备用比例 $\rho=0.03$，该日需要覆盖的功率为 $D_d^{\rm commit}=\max_{h\in d}(N_h+\rho L_h)$。从费用升序表依次选机组，直到其容量信用之和达到 $D_d^{\rm commit}$ 或已经无机组可选。煤、气、生物质信用用额定 MW；水电只用本日预定出力的**最小小时值** $\min_{h\in d}p^{\rm hyd,plan}_{g,h}$，不能把无水可发的额定 MW 当作全天备用。代码不求解二元启停优化，也未施加最短开停机时间、爬坡或启动费用。小时内在线常规站的出力上界是上述 $\bar p_{g,h}$（非水电用额定 MW），下界是 $\underline p_{g,h}=\min(\bar p_{g,h},\bar P_g\mu_g)$，$\mu_g$ 为最小出力比例；$M_h=\sum_{g\in\text{在线}}\underline p_{g,h}$ 为必发出力。

### 3.3 储能、弃风弃光、放电与常规机组增发的严格顺序

储能站 $s$ 的额定放电功率为 $\bar P_s$、充电功率为 $\bar P_s a_s$、时长为 $H_s$、能量上限为 $E_s^{\max}=\bar P_sH_s$。读入的单一往返效率 $\eta_s^{\rm rt}$ 按对称效率解释：$\eta_s^{\rm ch}=\eta_s^{\rm dis}=\sqrt{\eta_s^{\rm rt}}$，故 $\eta_s^{\rm ch}\eta_s^{\rm dis}=\eta_s^{\rm rt}$，不能把往返效率在充放电两侧各乘一次。各小时先计算 $X_h=\max(0,M_h+A_{w,h}+A_{s,h}-L_h)$，按储能输入顺序充电，每站实际充电功率取

$$p^{\rm ch}_{s,h}=\min\left(X_h^{\rm remain},\bar P_sa_s,\frac{E_s^{\max}-E_{s,h}}{\eta_s^{\rm ch}\Delta t}\right),\quad E'_{s,h}=E_{s,h}+\eta_s^{\rm ch}p^{\rm ch}_{s,h}\Delta t.$$

扣减本小时剩余富余后，若仍需弃电，令 $Q_h=\min\{\max(0,M_h+A_{w,h}+A_{s,h}-L_h-\sum_sp^{\rm ch}_{s,h}),\,A_{w,h}+A_{s,h}\}$；当 $A_{w,h}+A_{s,h}>0$ 时按可用份额分配 $Q_{w,h}=Q_hA_{w,h}/(A_{w,h}+A_{s,h})$、$Q_{s,h}=Q_h-Q_{w,h}$，并得实际风、光 $W_h=A_{w,h}-Q_{w,h}$、$S_h=A_{s,h}-Q_{s,h}$；分母为零时两类弃电均为零。例如 $M=35$、风可用 30、光可用 20、负荷 65、已充电 5 MW，则 $Q=15$ MW，弃风 9、弃光 6，风光实发为 21 和 14 MW，$35+21+14=65+5$。这是中性分摊假设，不能解释为真实电网的弃电优先级；可参阅[Applied Energy 2024 电力碳核算综述](https://www.sciencedirect.com/science/article/pii/S0306261924000643)与[Applied Energy 2025 储能和投入产出耦合研究](https://www.sciencedirect.com/science/article/pii/S0306261924023183)对时间边界和储能核算的讨论。

令 $B_h=L_h+\sum_sp^{\rm ch}_{s,h}-W_h-S_h$ 为风光后的剩余需求，$\bar P_h^{\rm on}=\sum_{g\in\text{在线}}\bar p_{g,h}$。从本小时起最多 24 小时的预先计算净负荷均值为 $T_h=(\sum_{\tau=h}^{\min(h+24,8760)-1}N_\tau)/(\min(h+24,8760)-h)$。代码要求放电量不高于“剩余需求超过必发出力”，并用超过未来均值或在线容量的需求触发放电，故总请求为

$$D_h^{\rm ask}=\min\!\left(\max\{0,B_h-T_h,B_h-\bar P_h^{\rm on}\},\ \max\{0,B_h-M_h\}\right).$$

本小时如实际充电总量达到 $10^{-9}$ MW，则不放电；否则**先按额定放电功率 $\bar P_s$ 从小到大、同功率按电站 ID 排序**，逐站分配削峰请求。对该顺序中的每站取 $p^{\rm dis}_{s,h}=\min\{D_h^{\rm remain},\bar P_s,E'_{s,h}\eta_s^{\rm dis}/\Delta t\}$，并更新 $E_{s,h+1}=E'_{s,h}-p^{\rm dis}_{s,h}\Delta t/\eta_s^{\rm dis}$。充电仍按输入顺序；该规则表达“小容量储能先进入削峰”，不改变同小时充放电互斥，也不声称运行成本最优。若一小时只需 2 MW 且 5 MW 与 20 MW 两站均有电，5 MW 站先承担 2 MW，20 MW 站待机。**小容量的口径是额定放电功率 MW，并非能量容量 MWh。** 因此始终有 $0\le E_{s,h+1}\le E_s^{\max}$，逐时状态守恒残差

$$\epsilon^{E}_{s,h}=E_{s,h+1}-E_{s,h}-\eta_s^{\rm ch}p^{\rm ch}_{s,h}\Delta t+\frac{p^{\rm dis}_{s,h}\Delta t}{\eta_s^{\rm dis}}$$

应接近零。例如往返效率 0.81、初态 0、充电 5 MW 一小时后内能为 4.5 MWh；下一小时如放电 3 MW，内能变为 $4.5-3/0.9=1.166\overline6$ MWh。随后令待常规机组增发功率 $Y_h=\max(0,B_h-\sum_sp^{\rm dis}_{s,h}-M_h)$，在线站先取各自下界，再按费用序位逐站增加 $\min(Y_h^{\rm remain},\bar p_{g,h}-\underline p_{g,h})$；仍未满足的量记缺供 $u_h$。代码对发电中的水电从月剩余预算扣实际出力。详见 [`project_engine.py`](../power_ga/operation_simulation/project_engine.py)。

### 3.4 逐时备用、功率平衡及年度验收

逐小时在线备用需求 $R_h^{\rm req}=\rho L_h$。在线常规机组可用备用是 $\sum_g(\bar p_{g,h}-p_{g,h})$；未充电储能仅计仍可持续**一小时**的未用放电能力 $\min\{\bar P_s-p^{\rm dis}_{s,h},E_{s,h+1}\eta_s^{\rm dis}/\Delta t\}$。两者相加得到 $R_h^{\rm av}$，在线备用不足为 $r_h=\max(0,R_h^{\rm req}-R_h^{\rm av})$。储能正在充电时不给放电备用，防止同一 MW 双计。计划备用缺口仍按 2.2 节峰值可信容量单独核对。

所有小时都核对以下实物账：

$$\sum_{g\in\rm conventional}p_{g,h}+W_h+S_h+\sum_sp^{\rm dis}_{s,h}+u_h=L_h+\sum_sp^{\rm ch}_{s,h}+o_h,\qquad \epsilon_h^{P}=\text{左侧}-\text{右侧}.$$

$o_h=\max(0,\text{缺供计入后的供给}-L_h-\sum_sp^{\rm ch}_{s,h})$ 是风光已经完全弃尽后仍因必发出力而无法消纳的过剩，与弃风弃光 $Q_h$ **不是一回事**。全年各项电量用 $\sum_hP_h\Delta t$ 汇总；最大功率残差为 $\max_h|\epsilon_h^P|$，储能残差按上式逐站逐时核对。运行器返回缺供 MWh、缺供小时数、在线备用不足 MWh、物理过剩 MWh、剩余水量预算和年末储能库存。评价器依 2.2 节条件判定状态可行，不能因为代数收敛或总体电量平衡就忽略逐时短缺。

### 3.5 独立分区运行：两种传输计算

分区 CSV 模式按小时独立读入各区域负荷 $D_i$、风光可用量 $A_i^w,A_i^s$、**外部给定**储能充放电，及机组上下界 $[\underline P_g,\bar P_g]$、成本和线路方向/限额。以线路录入方向为正，$F_\ell$ 可正可负，$|F_\ell|\le\bar F_\ell$；对区 $i$ 的精确平衡为

$$\sum_{g\in i}p_g+R_i+p_i^{\rm dis}+u_i+\sum_{\ell:\,\mathrm{target}=i}F_\ell-\sum_{\ell:\,\mathrm{source}=i}F_\ell=D_i+p_i^{\rm ch}+o_i,$$

其中 $0\le R_i\le A_i^w+A_i^s$ 是聚合风光消纳，$u_i$ 是缺供，$o_i$ 是不可消纳过剩；求解后按可用份额把 $A_i^w+A_i^s-R_i$ 拆为弃风和弃光。含交流等值边时调用 Gurobi 线性规划，增加 $F_\ell=b_\ell(\theta_{\rm source}-\theta_{\rm target})$，每个交流连通分量定一个 $\theta=0$ 参考；直流边的 $F_\ell$ 独立可控。单小时目标函数为

$$\min\ \sum_gc_gp_g+10^6\sum_iu_i+10^4\sum_io_i+0.01\sum_i(A_i^w+A_i^s-R_i)+10^{-4}\sum_\ell|F_\ell|,$$

绝对值通过辅助变量线性化。罚价是当前代码的算法参数（元/MWh），不是某地区实测电价。由于只有线性有功关系，它没有电压、无功、损耗、N−1 或完整 AC 潮流。全 DC/可控通道时也可选择不依赖求解器的启发式：从最低出力和风光可用量开始，以广度优先搜索当前线路剩余容量上的路径，将富余先送到缺额区；再按机组费用升序增发、先供本区后沿路径供其他区；最后把未满足量记缺供、富余按风光份额弃电，余量记溢出。路径每次增广 $\delta=\min(\text{源富余},\text{受端缺额},\text{路径剩余限额})$。此法返回可行平衡，**不保证费用最优**，交流环网不能用它冒充相角潮流。见 [`network.py`](../power_ga/operation_simulation/network.py)。

分区8760小时查看器对每区保留 $L_{i,t}=D_{i,t}+X_{i,t}$（本地需求加外送）与独立进口 $I_{i,t}$；全网总览只在每小时 $|\sum_iI_{i,t}-\sum_iX_{i,t}|\le10^{-5}$ MW 后抵消内部交换，显示 $D_t^{\rm all}=\sum_iD_{i,t}$。因此分区图能看见互济，全网图不会把同一内部电量重复记为发电和需求。切换视图仅重绘已归档数据，不重新运行模型。The regional selector preserves the chosen hour range and popover statistics.

### 3.6 碳、SO₂ 与物理新能源属性的比例追踪

先由 3.5 节求得同一小时的机组出力和联络线有向实流量，再对每条负流量反转其实际方向，记 $F_{ji}\ge0$ 为从 $j$ 进入 $i$ 的 MW。对属性 $k\in\{\mathrm{CO_2},\mathrm{SO_2},\mathrm{RE}\}$，区 $i$ 的本地直接注入属性为 $e_i^k=\sum_{g\in i}p_ga_g^k+p_i^{\rm dis}a_{i,\rm dis}^k+e_{i,\rm wind/solar}^k$；风光在 RE 属性上按实际消纳 MW 计 1，在碳/SO₂ 本模块的直接发电端计 0。碳因子单位 tCO₂/MWh，硫因子 kgSO₂/MWh，RE 因子为 $[0,1]$ 的物理份额。储能放电若大于零，必须显式给出继承的充电来源属性，否则拒绝计算；程序尚不跨小时跟踪储能属性库存。

把进入区 $i$ 的本地发电（含风光与储能放电）和进口相加，得混合吞吐 $P_i^{\rm mix}=G_i^{\rm local}+p_i^{\rm dis}+\sum_jF_{ji}$。假定每区同小时完全混合，出口、终端负荷、储能充电和溢出具有相同属性强度 $q_i^k$。属性守恒从“本地直接注入 + 进口携带 = 本区全部外流及消费携带”得到

$$e_i^k+\sum_jF_{ji}q_j^k=P_i^{\rm mix}q_i^k,\qquad M_{ii}=P_i^{\rm mix},\quad M_{ij}=-F_{ji}\ (i\ne j),\quad\mathbf M\mathbf q^k=\mathbf e^k.$$

每个属性各解一次同一个系数矩阵；孤立且零吞吐节点规定强度为零，奇异的无终端消纳闭环则报错。实际服务负荷为 $D_i^{\rm served}=D_i-u_i$，消费端归属 $E_{i,\rm load}^k=D_i^{\rm served}q_i^k\Delta t$。把各区方程求和，区间传输内部抵消，得到可核对的源用守恒式

$$\sum_i e_i^k\Delta t=\sum_iq_i^k(D_i^{\rm served}+p_i^{\rm ch}+o_i)\Delta t.$$

例如 A 区 10 MW 煤电（碳因子 0.8 t/MWh）与 10 MW 风电，A 本地消费 10 MW、向 B 输送 10 MW，B 消费 10 MW；则 $P_A^{\rm mix}=20$、$e_A^{\rm CO_2}=8$，故 $q_A^{\rm CO_2}=0.4$ t/MWh、$q_A^{\rm RE}=0.5$；B 的方程是 $10q_B=10q_A$，故 B 得相同强度。两区各归属 4 tCO₂ 和 5 MWh 物理新能源属性，总和分别回到源端 8 tCO₂ 和 10 MWh。这里的“投入产出式”只指**电力部门物理电量混合与跨区传递**，不含绿证所有权、产业上游排放或 SO₂ 大气扩散；相关方法边界可参阅[Energy Policy 2026 跨省电力投入产出研究](https://www.sciencedirect.com/science/article/pii/S0301421525004148)及[Applied Energy 2019 SO₂ 多区域研究](https://www.sciencedirect.com/science/article/abs/pii/S0306261919301370)。实现见 [`attributes.py`](../power_ga/operation_simulation/attributes.py)。

### 3.7 从输入到审计文件的复现步骤

交互查看器允许在日、周、月、年或自定义视图内用鼠标框选整数小时 $[a,b)$。浮窗对每类已归档功率 $P_{k,t}$ 使用相同的1小时步长计算电量与平均功率：

$$E_k[a,b)=\sum_{t=a}^{b-1}P_{k,t}\times1\mathrm{h},\qquad \bar P_k[a,b)=\frac{E_k[a,b)}{b-a}. $$

发电、进口、储能放电和缺供与总需求、储能充电、未消纳过剩组成选段平衡；弃风弃光是未发出的可用量，仅独立列示，不重复加到供给侧。外送已计入总需求，同时单列以便查看。本功能只读取逐时结果存档，不改变规划或运行解。The popover reports archived period energy and average power with no additional dispatch.

在仓库根目录按 [`requirements.txt`](../requirements.txt) 安装基础依赖；DP 与含交流边的分区 LP 还需安装 [`requirements-gurobi.txt`](../requirements-gurobi.txt) 并具备有效本机 Gurobi 许可。公开三年合成规划的完整复现命令为：

```powershell
python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon
python -m examples.verify_dynamic_case --output synthetic_full
```

第一条生成 `tables/all_stage_states.csv`（$3\times2^8=768$ 行状态账本）、`stage_comparison.csv`、`ga_history.csv`、`summary.csv`、阶段工作簿、终期 8760 小时存档和 `synthetic_dynamic_audit.json`；第二条从固定种子输入重算中选路径，验收各年费用、状态不退出、功率和储能状态残差、月水量预算以及最终年八类实际出力，并写 `synthetic_dynamic_verification.json`。核验应见 `status: PASS`；状态表与脚本输出以未舍入 CSV 为准，不从截图反推小数。合成规划设置为 2026/2027/2028 年负荷倍率 0.82/1/1.08、折现率 0.07，多年 GA 使用种群 64、最大 80 代、最少 12 代、停滞 20 代、精英 2、交叉率 0.85、变异率 0.045、种子 19；两算法复用相同逐站合成气象。

分区模式将 `zones.csv`、`generators.csv`、`links.csv`、`hourly.csv` 放在同一输入文件夹；名称与区域引用须唯一且可对应，小时索引从 0 到 8759，每个小时必须恰有每个区域一行，所有必需数值应有限且非负。机组表必须单列技术类型；风光可用量在逐时表，抽蓄与电池的充放电及各自放电属性也分别在逐时表；含交流边必须选择 `gurobi`，全可控边可选择 `heuristic`。公开四区合成 CSV 可在仓库根目录直接运行 `python -m examples.synthetic_network_case --output synthetic_network --csv-platform-case` 生成并计算；输出位于 `synthetic_network/result`。函数入口 `run_network_case(input_dir, output_dir, solver="gurobi")` 每小时对功率残差以及碳、SO₂、RE 源用残差分别要求不超过 $10^{-6}$（各用其物理单位），输出 `tables/hourly_network.csv`、`zone_summary.csv`、`technology_summary.csv`、`link_summary.csv`、四页汇总工作簿及带输入 SHA-256 的 `run_manifest.json`。接口调用和列名以[使用指南](USER_GUIDE.md)、[`synthetic_network_case.py`](../examples/synthetic_network_case.py)及 [`network_case.py`](../power_ga/operation_simulation/network_case.py) 为准。此入口的储能充放电时序与放电属性是**外部固定输入**，目前不审查 SOC、也不优化跨时段充放电。

## 第四章：算例设计和参数介绍 / 4. Case design and parameters

公开规划案例有2026—2028三个合成年份、8个候选项目、每年8760小时，共 $3\times2^8=768$ 个年度状态。八类机组均参与；年度负荷系数依次0.82、1.00、1.08，折现率7%。各年复用同一合成气象种子，避免将天气重抽样混入GA与DP比较。成本CSV为**可编辑试算假设**，不代表真实项目报价。The complete synthetic inputs are generated by the included fixed-seed scripts.

| 候选技术 / Candidate | 新增MW | 假设年化资本费 元/MW·年 | 变动费 元/MWh |
|---|---:|---:|---:|
| 煤电 / Coal | 20 | 2,800,000 | 240 |
| 燃气 / Gas | 15 | 1,000,000 | 470 |
| 常规水电 / Hydro | 10 | 5,900,000 | 30 |
| 生物质 / Biomass | 8 | 4,000,000 | 180 |
| 抽蓄 / Pumped storage | 10 | 1,700,000 | 8 |
| 电池 / Battery | 10 | 1,400,000 | 8 |
| 风电 / Wind | 20 | 1,300,000 | 0 |
| 光伏 / Solar | 20 | 850,000 | 0 |

另有独立四区8760小时**纯合成**网络试验，区域名为山西、华北、华中、江苏。[国家能源局2024答复](https://zfxxgk.nea.gov.cn/2024-06/11/c_1212388601.htm)说明山西500 kV网架“三纵四横”及向京津冀鲁、华中、江苏的交流、直流和500 kV外送联系；[江苏监管办公室记录](https://jsb.nea.gov.cn/dtyw/jgdt/202309/t20230910_28887.html)证实晋北—南京直流工程。因此只将**连接方向**作为公开依据。示意限额22、16、12 MW、交流电纳120、100 MW/rad，以及负荷、机组、风光、直接碳/SO₂因子全部为脚本生成的任意教学参数，**不是实际线路、实测潮流、地区排放清单或全国库参数**。完整可编辑[四张输入CSV](../examples/inputs/v0.2.8/network/)由同仓库固定种子脚本生成。The four-zone fixture tests methods without reconstructing any real grid.

## 第五章：结果分析 / 5. Results and prior comparison

更新后的公开三年度算例里，Bellman、Gurobi及固定种子GA均选择累计状态 $(0,2,2)$，折现总费用约 **368.565 百万元**。768个状态各评价8760小时；对选中方案再独立回放，最大功率平衡残差 $2.84\times10^{-14}$ MW、储能状态残差 $3.55\times10^{-15}$ MWh，月水电预算超额0 MWh。本次同解不代表有限预算GA普遍可找到全局最优。The final year has positive output or discharge from all eight technology groups.

末年本地负荷829,822.658 MWh、缺供0；风电实际112,305.782 MWh、弃风2,040.106 MWh；光伏实际123,961.086 MWh、弃光6,947.400 MWh。新规则重算后**弃风与弃光同时出现**。公开合成结果的工作簿、阶段对照和独立验收文件见[结果目录](../examples/results/v0.2.8/)。The updated curtailment values and figures come from one hourly archive.

下方GA与DP图由Origin原生工程从新版结果CSV绘制；GA曲线平直是因为本次Gen=0已含最终最优路径，图不虚构继续改进。运行图由应用的交互绘图后端导出，正常风光纯色、弃风弃光同色斜线、储能充电在零线以下，负荷线加粗。Every image below is embedded directly in this report.

GA逐代费用 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/ga_history.png)

![公开合成GA逐代费用](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/ga_history.png)

DP阶段费用 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/dp_stage_cost.png)

![公开合成DP阶段费用](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/dp_stage_cost.png)

第182日 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/day_182.png)

![公开合成第182日](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/day_182.png)

第27周 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/week_27.png)

![公开合成第27周](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/week_27.png)

第7月缩放 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_7.png)

![公开合成第7月缩放](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_7.png)

全年8760小时 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/year_1.png)

![公开合成全年8760小时](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/year_1.png)

任意时段137—193小时 / View：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/custom_137_193.png)

![公开合成任意时段137—193小时](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/custom_137_193.png)

1月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_01.png)

![公开合成1月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_01.png)

2月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_02.png)

![公开合成2月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_02.png)

3月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_03.png)

![公开合成3月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_03.png)

4月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_04.png)

![公开合成4月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_04.png)

5月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_05.png)

![公开合成5月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_05.png)

6月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_06.png)

![公开合成6月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_06.png)

7月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_07.png)

![公开合成7月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_07.png)

8月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_08.png)

![公开合成8月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_08.png)

9月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_09.png)

![公开合成9月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_09.png)

10月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_10.png)

![公开合成10月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_10.png)

11月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_11.png)

![公开合成11月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_11.png)

12月 / Monthly view：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_12.png)

![公开合成12月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/month_12.png)

独立四区合成网络试验得到弃风245.986 MWh、弃光315.664 MWh、缺供0、最大分区功率残差 $2.84\times10^{-14}$ MW。两区碳、SO₂及新能源属性的已知答案测试通过：10 MW煤电与10 MW风电混合后，本区与外区每MWh均继承一半风电属性；储能放电无属性输入则报错。These are synthetic verification results, not regional forecasts.

同一四区合成输入经过新版EXE同接口的8760小时潮流和属性追踪，四区本地需求合计1,515,387.396 MWh，区间进口/出口合计均353,559.022 MWh（两个方向统计在全网求和时相等），终端消费端碳属性504,614.752 tCO₂、SO₂属性149,760.456 kg、物理新能源属性738,264.460 MWh。弃风245.986 MWh、弃光315.664 MWh；二者均来自分区约束和中性分摊规则。每小时最大功率残差 $3.55\times10^{-14}$ MW、碳残差 $2.84\times10^{-14}$ t、SO₂残差 $1.42\times10^{-14}$ kg、新能源残差 $4.26\times10^{-14}$ MWh；这是**合成因子下的计算属性**，绝非实际省际排放核算。[综合工作簿](../examples/results/v0.2.8/network_summary.xlsx)、[分区年度表](../examples/results/v0.2.8/zone_summary.csv)、[机组类型表](../examples/results/v0.2.8/technology_summary.csv)、[联络线表](../examples/results/v0.2.8/link_summary.csv)和[审计清单](../examples/results/v0.2.8/network_audit.json)均可复核。The zonal figures use the application viewer backend.

四区示例山西聚合区7月缩放 / Synthetic zonal July：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/network_month_07.png)

![公开合成分区运行7月](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/network_month_07.png)

交互窗口对同一合成分区运行的第27周直接绘制：去掉每小时色块黑边，纵轴固定为有限主刻度，储能充电按实际量显示在零线下，日/周/月/年切换只重新绘制当前窗口。弃光黄色正斜线、弃风绿色反斜线均加密加粗；该周仅两小时有弃电，图中用真实MW文字标记其位置，色块面积和保存的8760行原值不变。The Python backend also exports the same data and palette on computers without Origin.

![公开合成分区运行第27周，改进后的窗口配色与坐标轴](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.8/network_week_27_ui.png)

同一四区纯合成8760小时运行存档可在一张窗口内切换全网及每个分区；下列四张图直接取同一逐时表的各区原值，由Python/Matplotlib查看器绘制。全网内部进口与出口逐小时相抵，各区图仍显示自身的进口、外送和不同机组组合；这些图是程序导出的全年总览，交互窗口内可继续缩放到日、周、月或任意区间。Four regional views come from one fixed-seed synthetic hourly archive, not measured provincial operations.

山西聚合区全年 / Synthetic Shanxi zone：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/shanxi_year.png)

![纯合成山西聚合区8760小时图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/shanxi_year.png)

华北聚合区全年 / Synthetic North zone：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/north_year.png)

![纯合成华北聚合区8760小时图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/north_year.png)

华中聚合区全年 / Synthetic Central zone：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/central_year.png)

![纯合成华中聚合区8760小时图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/central_year.png)

江苏聚合区全年 / Synthetic Jiangsu zone：[原图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/jiangsu_year.png)

![纯合成江苏聚合区8760小时图](https://raw.githubusercontent.com/Entropyneverfade/GRIDMIND/main/examples/previews/v0.2.11/jiangsu_year.png)

**与先验结果比较。** 本机对照表逐项检查负荷、外送、机组发电、储能及弃电。先验场景与项目库原始负荷不同，因此先做固定GA建设方案、只替换先验8760小时本地负荷及外送的控制实验；该方案出现缺供。随后将目标年全部候选装机投运，在相同逐时需求下，全年风光可用总电量与先验表吻合，但发电、弃电、水电及储能仍有差异。差异可与运行规则有关，仍需核对逐日/逐站风光曲线、水文、机组组合和储能初态后才可定量归因。本报告不公布真实项目数值、图片或可还原元数据。The comparison aligns demand and annual renewable availability, while the remaining technical assumptions still require audit.

复现公开案例：`python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon`，然后 `python -m examples.verify_dynamic_case --output synthetic_full`；分区试验：`python -m examples.synthetic_network_case --output synthetic_network`。使用说明见[USER_GUIDE](USER_GUIDE.md)。尚未实现真实分区参数接入GA/DP、跨时段储能属性库存、概率EENS/LOLE、N−1、完整水电级联和机组启停。The verified boundaries are part of the result.
