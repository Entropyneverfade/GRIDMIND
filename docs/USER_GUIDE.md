# 使用说明

本文对应公开功能基线 0.2.14；新版独立档案与工作台以[开发计划](ROADMAP.md)的验收状态为准。

## 1. 安装与启动

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-gurobi.txt
python gridmind_app/main.py
```

第二行用于 Gurobi 模式，并需要有效本机许可。Windows 打包入口为 `gridmind_app/build.ps1`。只有经过相应验收的构建才能作为正式 EXE，仓库文档版本不能替代二进制身份核验。

## 2. 规划输入

选择年度数据库、经济参数和目标年，再设种群、代数及随机种子。规划方法包括单年 GA、双年度 DP 和全规划年 DP。源库模式读取各年度存量、需求、外送、风光与水文；终期候选身份和位序在各年固定。系数情景是显式人为情景，不作为多年度实测输入。

当前 DP 默认最多 8 个候选，完整费用表需进行阶段数乘以候选状态数的年度评价。进度按已评价状态计数，不是剩余时间预测。Gurobi 核对年度状态路径，逐时费用仍由规则运行器计算。

曾使用 0.2.1 或 0.2.2 年度源库模式的结果需按版本记录检查年度装机对齐问题；不要直接视为当前有效结果。

## 3. 命令行复现

```powershell
python main.py --skip-figures
python -m examples.synthetic_full_case --output synthetic_ga
python -m examples.synthetic_dynamic_case --output synthetic_full --full-horizon
python -m examples.verify_dynamic_case --output synthetic_full
python -m examples.synthetic_network_case --output synthetic_network
python -m unittest discover -s tests -q
```

新运行使用当前代码，不会自动复现旧约束版本的历史费用。采用独立结果目录并保存版本与设置；不要覆盖原归档作为“修图”。

## 4. 打开已有结果

```powershell
python gridmind_app/main.py --viewer <结果目录>
```

查看器读取已有逐时表，可选日、周、月、年或任意小时区间。Ctrl 加滚轮以鼠标对应小时为中心缩放，窗口宽度缩小或扩大后限制在 1 至 8760 小时；这是显示操作，不改结果。框选按整小时的左闭右开区间统计电量和平均功率。

图中风光实色是消纳出力，斜线是弃电；充电在零线下。查看器不应重新运行优化。新版独立命名档案、脱离原目录后的离线浏览仍需候选程序实际验收，不能与旧版“重开已有结果目录”混为一项能力。

## 5. 分区 CSV 输入

| 文件 | 主要字段与约束 |
| --- | --- |
| `zones.csv` | `zone`，每区一行，标识唯一 |
| `links.csv` | `name,source,target,limit_mw,kind,susceptance_mw_per_rad`；端点必须存在 |
| `generators.csv` | 机组名称、分区、技术、最小/最大 MW、成本及碳硫和新能源属性 |
| `hourly.csv` | 每小时每区一行，负荷、风光可用量、抽蓄/电池充放电及放电属性 |

`kind=ac` 需正电纳并使用 Gurobi LP；可控通道用 `dc`，双向限额对称。启发式模式只接受可控通道，不能把交流边仅改标签当成同一模型。固定储能时序与属性由输入提供，本入口不优化库存。

四区算例以 A、B、C、D 命名，具体端点见[算例说明](CASE_STUDY.md)。每个分区图只能使用所选档案的逐区结果；没有对应逐时数据时应显示缺失，不复制全网曲线。联络关系必须与同一输入快照一致。

## 6. 结果表与参数

单年工作簿包括年度、逐月、逐日、逐时、电站、储能、站级开停、运行参数和 GA 记录。DP 另有年度状态、阶段费用、贴现费用及同费用表上的算法对照。CSV 用于独立核对；运行清单用于识别输入和版本。

静态图与表分目录保存。已有示例图片使用 Python/Matplotlib 后端，公开报告已注明；Origin 原生工程需另有相应软件与真实工程文件。科研图须保存数据和脚本，不能靠图形美化改变证据。

## 7. 结果解释

缺供、过剩、备用不足和残差原样报告。当前是确定性模型，不能从一次无缺供推导概率充裕度通过。成本与水文参数是试算假设，需按使用场景校准。功能和边界总览见[项目报告](FINAL_STAGE_REPORT.md)。
