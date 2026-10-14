# GRIDMIND

**电源规划、逐时运行与结果复核工具。** 用同一套年度运行评价支撑遗传算法（GA）和动态规划（DP），并保存可检查的费用、状态和运行表。

当前公开功能基线为 **0.2.14**。本次更新重写报告、核对算例并整理展示；1.0 集成候选仍在验收，1.1 闭环是开发目标。

## 从这里开始

| 想了解什么 | 阅读入口 |
| --- | --- |
| 已实现能力、算例结果和边界 | [项目报告](docs/FINAL_STAGE_REPORT.md) |
| 方程、单位与代码对应 | [数学模型](docs/MATHEMATICS.md) · [推导附录](docs/MATHEMATICS_APPENDIX.md) |
| 图表来自哪次计算 | [算例与证据](docs/CASE_STUDY.md) |
| 安装、计算与重开历史结果 | [使用说明](docs/USER_GUIDE.md) |
| 1.0 验收与 1.1 集成路线 | [开发计划](docs/ROADMAP.md) |

## 当前能做什么

- 单年度 GA 搜索候选建设组合；多年度 DP 求解有限年度状态的建设路径，使用 Gurobi 独立核对路径目标。
- 单区确定性逐时运行：煤、气、水、风、光、生物质、抽蓄和电池；包含站级启停、小时爬坡、月检修边界及连续储能库存。
- 独立的分区 CSV 模式：线性有功潮流和物理属性追踪；目前未成为主规划每个状态的网络约束。
- 从已有结果表重绘日、周及任意区间；图、表共用原始逐时数据。

Gurobi 是当前主要优化工具。ZYO 将作为可选后端，先承担已支持的子问题。神经网络充裕度估计及蒙特卡洛验证属于集成开发路线；私有模型与数据不随本仓库发布。

## 一张可核对的运行图

下图来自 0.2.14 单年度合成算例，使用已有 Python/Matplotlib 查看器导出。正向斜线区域为弃电，不能计入实际供电；充电画在零线下方。完整数值见[同次运行工作簿](examples/results/v0.2.14/ga_annual_summary.xlsx)。

![单年度算例第182日运行图](examples/previews/v0.2.14/day_182.png)

全年 8760 小时数据仍保留在结果表中；报告用短时段图片及数值表呈现，避免把全年曲线压缩成不可读的色块。

## 运行

```powershell
python -m pip install -r requirements.txt
python main.py --skip-figures
python -m pip install -r requirements-gurobi.txt
python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon
python -m examples.verify_dynamic_case --output synthetic_full
```

DP 与分区 Gurobi 模式需要有效的本机许可。桌面入口、离线重绘和输入格式见[使用说明](docs/USER_GUIDE.md)。

## 结果如何解释

DP 最优性只针对给定候选集、年度运行规则和完整状态费用表。主运行器采用站级规则调度，尚不提供全年全局最优机组组合、完整交流潮流、N−1 安全校验或概率充裕度结论。算例均为合成数据，成本参数是可编辑假设。

代码与原创文档采用 [MIT 许可证](LICENSE)，第三方依赖保留各自许可。变更见[版本记录](CHANGELOG.md)。
