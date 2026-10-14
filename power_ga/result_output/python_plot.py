"""无 Origin 的静态绘图后端；沿用交互窗口的阶梯堆叠、配色与时段边界。

每张图独立保存 PNG/PDF、可编辑的源数据及 Python 再绘制脚本。
运行模拟数值直接来自已归档 CSV，绘图不会修改电量或重新调度。
"""

import csv
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无桌面电脑和冻结 EXE 的后台任务也能出图。
from matplotlib.figure import Figure

from .viewer import COLORS, draw_view, load_hours


def _style():
    """统一中文字体、白底与内向刻度，静态图和缩放窗口口径一致。"""
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["figure.facecolor"] = "white"
    matplotlib.rcParams["axes.facecolor"] = "white"


def _save(fig, folder: Path, source: Path, chart: str):
    """一图一目录，PNG/PDF 与源表及可重复执行的脚本同时落盘。"""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source_data").mkdir(exist_ok=True)
    (folder / "scripts").mkdir(exist_ok=True)
    fig.savefig(folder / "figure.png", dpi=180, facecolor="white")
    fig.savefig(folder / "figure.pdf", facecolor="white")
    archived_source = folder / "source_data" / source.name
    if source.resolve() != archived_source.resolve():
        shutil.copyfile(source, archived_source)
    script = ("# 归档源表可用本仓库 power_ga.result_output.python_plot 重绘。\n"
              "# 以标准库读取原始 CSV，再调用 render_archived_figure；不读取私有源库。\n"
              "from pathlib import Path\n"
              "from power_ga.result_output.python_plot import render_archived_figure\n"
              f"render_archived_figure(Path(__file__).resolve().parents[1], {chart!r})\n")
    (folder / "scripts" / "render_python.py").write_text(script, encoding="utf-8")
    (folder / "renderer.json").write_text(json.dumps(
        {"backend": "Python/Matplotlib", "chart": chart,
         "source_csv": source.name, "same_hourly_values_as_origin": True},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _history_chart(folder, source: Path, chart: str):
    """GA 三张图共享真实逐代结果；费用由元转换为百万元仅用于坐标显示。"""
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return
    x = [int(row["代数"]) for row in rows]
    fig = Figure(figsize=(12, 6.5), dpi=100)
    axis = fig.subplots()
    if chart == "ga_convergence":
        for column, title, color, width in (
                ("历代最优元", "历代最优", "#17365D", 2.0),
                ("本代最优元", "本代最优", "#DA6A00", 1.4),
                ("可行种群均值元", "可行种群均值", "#2171B5", 1.4)):
            axis.plot(x, [float(row[column]) / 1e6 for row in rows],
                      label=title, color=color, linewidth=width)
        title, ylabel = "遗传算法最优方案年费用", "年费用 / 百万元"
    elif chart == "ga_population":
        for column, title, color in (
                ("可行个体数", "可行个体", "#237A57"),
                ("不同染色体数", "不同染色体", "#7A3E9D")):
            axis.plot(x, [int(row[column]) for row in rows],
                      label=title, color=color, linewidth=1.8)
        title, ylabel = "遗传种群可行性与多样性", "个体数"
    elif chart == "ga_plan":
        # 容量信息需要候选清单；独立再绘图时从同图源 CSV 读取预先算好的 MW。
        axis.step(x, [float(row["新增容量MW"]) for row in rows], where="post",
                  label="历代最优新增容量", color="#17365D", linewidth=2)
        title, ylabel = "历代最优方案新增装机变化", "新增装机 / MW"
    else:
        raise ValueError(f"未知 GA 图：{chart}")
    axis.set_title(title, fontsize=15, pad=16)
    axis.set_xlabel("遗传代数")
    axis.set_ylabel(ylabel)
    axis.set_xlim(0, max(1, x[-1]))
    axis.grid(axis="y", color="#D7DEE8", linewidth=0.6)
    axis.tick_params(direction="in", which="both", top=False, right=False)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False)
    fig.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.13)
    _save(fig, folder, source, chart)


def _dispatch_chart(folder, source: Path, chart: str):
    """峰荷日及全年图都调用交互窗口的同一堆叠绘图函数。"""
    # 分图源表只有对应时段；再绘图时从附带原始 CSV 的 hour 字段还原年坐标。
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("绘图源 CSV 为空")
    start = int(rows[0]["hour"])
    end = int(rows[-1]["hour"]) + 1
    values = [{key: float(value) for key, value in row.items() if key != "hour"}
              for row in rows]
    # draw_view 接受 8760 长度序列并使用绝对小时切片；外部空位不会绘制。
    hours = [{}] * start + values + [{}] * (8760 - end)
    fig = Figure(figsize=(13, 7), dpi=100)
    label = "全年8760小时" if chart == "dispatch_year" else "峰荷日"
    draw_view(fig, hours, start, end, label)
    _save(fig, folder, source, chart)


def render_archived_figure(folder: Path, chart: str):
    """用单图目录内的源数据重绘，不要求 Origin 或原项目数据库。"""
    _style()
    source_dir = Path(folder) / "source_data"
    sources = list(source_dir.glob("*.csv"))
    if len(sources) != 1:
        raise ValueError("单图目录必须且只能有一个源 CSV")
    if chart.startswith("dispatch_"):
        _dispatch_chart(Path(folder), sources[0], chart)
    else:
        _history_chart(Path(folder), sources[0], chart)


def render_project_archive_python(output_dir: Path, *, figure_folder="figures"):
    """从已有表格重绘，既可新运行出图，也可在无 Origin 的电脑上补图。"""
    _style()
    root = Path(output_dir) / figure_folder
    tables = Path(output_dir) / "tables"
    hourly_source = tables / "hourly_dispatch.csv"
    hours = load_hours(Path(output_dir))
    history = tables / "history.csv"
    generation_rows = []
    if history.exists():
        with history.open(encoding="utf-8-sig", newline="") as stream:
            generation_rows = list(csv.DictReader(stream))
    if generation_rows:
        _history_chart(root / "01_GA收敛", history, "ga_convergence")
        _history_chart(root / "07_GA种群状态", history, "ga_population")
        # 容量是每代历代最优染色体与候选 MW 的内积 Σ_j b_j P_j。
        with (tables / "projects.csv").open(encoding="utf-8-sig", newline="") as stream:
            candidates = [float(row["容量MW"]) for row in csv.DictReader(stream)
                          if row["类别"] == "候选"]
        plan_data = root / "08_GA方案演化" / "source_data" / "plan.csv"
        plan_data.parent.mkdir(parents=True, exist_ok=True)
        with plan_data.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("代数", "新增容量MW"))
            for row in generation_rows:
                bits = [int(bit) for bit in row["历代最优染色体"]]
                if len(bits) != len(candidates):
                    raise ValueError("归档染色体长度与候选项目数不一致")
                writer.writerow((row["代数"],
                                 sum(bit * capacity for bit, capacity in
                                     zip(bits, candidates))))
        _history_chart(root / "08_GA方案演化", plan_data, "ga_plan")
    peak = max(range(8760), key=lambda hour: hours[hour]["load_mw"])
    start = peak // 24 * 24
    for chart, first, end, folder in (
            ("dispatch_peak", start, start + 24, root / "02_峰荷日电力平衡"),
            ("dispatch_year", 0, 8760, root / "05_全年8760电力平衡")):
        source = folder / "source_data" / "hourly.csv"
        source.parent.mkdir(parents=True, exist_ok=True)
        with hourly_source.open(encoding="utf-8-sig", newline="") as inp, source.open(
                "w", encoding="utf-8-sig", newline="") as out:
            reader = csv.DictReader(inp)
            writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(row for row in reader if first <= int(row["hour"]) < end)
        _dispatch_chart(folder, source, chart)


def plot_project_results_python(case, result, simulation, output_dir: Path):
    """项目报告写完表格后，用同一归档重绘入口生成五张静态图。"""
    render_project_archive_python(output_dir)
