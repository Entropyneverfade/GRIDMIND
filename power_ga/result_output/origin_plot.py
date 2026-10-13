"""结果输出子模块：Origin原生绘图适配器。

Python只把结果转换为阶梯边界和数据表；真正的曲线、填色、图例、
导出和OPJU工程由Origin执行。每张图有独立目录，便于别人修改和复现。
"""

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

"""结果输出共用的图形身份：同一种电源在所有图中使用同一种颜色。

RGB参考说明书图5.3-8、图6.2-30的视觉配色；PDF截图有压缩，不能
据此宣称这些数值是原软件内部的RGB定义。这里采用对应的纯色编码。
"""

COLORS = {
    "thermal": "#FF0000",  # 火电：红色，底部堆叠
    "solar": "#FFFF00",    # 光伏：黄色
    "wind": "#00FF00",     # 风电：绿色
    "load": "#FF00FF",     # 原始负荷：洋红色阶梯线
    "storage": "#0000FF",  # 储能：放电正向、充电负向，并独立画状态曲线
    "unserved": "#DDDDDD", # 缺供：灰色交叉纹理，不计入发电量
    "cost": "#333333",     # GA费用是另一种物理量，使用中性深灰
}

# 求解器小于1e-6MW的残差保留在原始表中，图中不建立误导性的“缺供”图例。
DISPLAY_POWER_TOL_MW = 1e-6
# Origin原生填充索引19已在导出的弃电窗口图中目视确认为点阵纹理。
CURTAILMENT_DOT_PATTERN = 19



def _step(values):
    """第i小时表示区间[i,i+1)，不使用线性插值改变逐时数据含义。"""
    return [value for value in values for _ in range(2)]


def _render(folder: Path, columns, plots, spec, source_rows, source_header):
    """准备一图一目录，并调用后台Origin。失败时保留数据与命令日志。"""
    for part in ("images", "source_data", "scripts", "qa"):
        (folder / part).mkdir(parents=True, exist_ok=True)
    data_path = folder / "source_data" / "plot_coordinates.csv"
    length = max(len(values) for values in columns.values())
    with data_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows([values[i] if i < len(values) else ""
                         for values in columns.values()] for i in range(length))
    with (folder / "source_data" / "original_data.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(source_header)
        writer.writerows(source_rows)
    spec.update({"folder": str(folder.resolve()), "data": str(data_path.resolve()),
                 "python_executable": sys.executable,
                 "frozen_executable": bool(getattr(sys, "frozen", False)),
                 "columns": list(columns), "plots": plots})
    spec_path = folder / "scripts" / "figure_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    # 把渲染脚本放进每张图目录，工程可随文件夹移动，不依赖临时文件。
    renderer = folder / "scripts" / "render_origin.ps1"
    renderer.write_text(Path(__file__).with_name("render_origin.ps1").read_text(encoding="utf-8"),
                        encoding="utf-8-sig")  # Windows PowerShell 5用BOM识别中文源码。
    # 全年复杂点阵若无法导出矢量PDF，仅把Origin的600dpi PNG封装为PDF。
    # 小脚本随一图一文件夹保存，避免PowerShell向Python传递带引号代码时丢失引号。
    (folder / "scripts" / "pdf_fallback.py").write_text(
        "from PIL import Image\nimport sys\n"
        "with Image.open(sys.argv[1]) as image:\n"
        "    image.convert('RGB').save(sys.argv[2], 'PDF', resolution=600)\n",
        encoding="utf-8")
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(renderer), "-SpecPath", str(spec_path)]
    # 全年阶梯图保留每个小时的真实点位，后台Origin读写更多单元格。
    completed = subprocess.run(command, capture_output=True, timeout=240)
    log = completed.stdout.decode("utf-8", errors="replace") + completed.stderr.decode("utf-8", errors="replace")
    (folder / "qa" / "renderer.log").write_text(log, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Origin绘图失败，参见 {folder / 'qa' / 'renderer.log'}")


def plot_convergence(result, root: Path):
    """同图画历代最优、本代最优及可行种群均值，识别早熟收敛。"""
    folder = root / "01_GA收敛"
    x = [row.generation for row in result.history]
    y = [row.best_cost_yuan / 1e6 for row in result.history]
    current = [row.generation_best_cost_yuan / 1e6 for row in result.history]
    average = [row.mean_cost_yuan / 1e6 for row in result.history]
    # 代际费用若已在Gen=0收敛仍画真实水平线；用十进制整刻度避免
    # Origin把259.604...等浮点端点显示成17位长串。
    all_costs = y + current + average
    spread = max(all_costs) - min(all_costs)
    step = max(0.1, math.ceil(spread / 4 * 10) / 10)
    pad = max(step, spread * 0.08)
    low = math.floor((min(all_costs) - pad) / step) * step
    high = math.ceil((max(all_costs) + pad) / step) * step
    yticks = [round(low + i * step, 3) for i in range(int(round((high - low) / step)) + 1)]
    spec = {"name": "convergence", "title": "遗传算法最优方案年费用",
            "x_label": r"\f:SimSun(遗传代数)",
            "y_label": r"\f:SimSun(年费用) / \f:Times New Roman(百万元)",
            "x_min": 0, "x_max": max(1, x[-1]), "y_min": low, "y_max": high,
            "x_ticks": sorted({0, x[-1], x[-1] // 4, x[-1] // 2, x[-1] * 3 // 4}),
            "y_ticks": yticks,
            "zero_once": False, "caption": "费用轴采用非零下界；数值取自本次遗传迭代记录"}
    _render(folder, {"x": x, "best": y, "generation": current, "mean": average},
            [{"column": 2, "label": "历代最优", "color": COLORS["cost"],
              "fill": False, "pattern": 0, "width": 1.5},
             {"column": 3, "label": "本代最优", "color": "#DA6A00",
              "fill": False, "pattern": 0, "width": 0.9},
             {"column": 4, "label": "可行种群均值", "color": "#2171B5",
              "fill": False, "pattern": 0, "width": 0.9}], spec,
            ([r.generation, r.best_cost_yuan, r.generation_best_cost_yuan,
              r.mean_cost_yuan, r.feasible_count] for r in result.history),
            ["代数", "历代最优元", "本代最优元", "均值元", "可行个体数"])


def plot_ga_population(result, root: Path):
    """展示每代可行方案与不同染色体数；后者为遗传多样性诊断。"""
    rows = result.history
    x = [row.generation for row in rows]
    feasible = [row.feasible_count for row in rows]
    unique = [row.unique_count for row in rows]
    upper = max(max(feasible), max(unique), 1)
    spec = {"name": "population", "title": "遗传种群可行性与多样性",
            "x_label": r"\f:SimSun(遗传代数)",
            "y_label": r"\f:SimSun(个体数)",
            "x_min": 0, "x_max": max(1, x[-1]), "y_min": 0, "y_max": upper,
            "x_ticks": sorted({0, x[-1], x[-1] // 4, x[-1] // 2, x[-1] * 3 // 4}),
            "y_ticks": sorted({0, upper, round(upper / 2)}),
            "zero_once": True,
            "caption": "可行个体数与唯一染色体数均按每代实际种群计数"}
    _render(root / "07_GA种群状态", {"x": x, "feasible": feasible, "unique": unique},
            [{"column": 2, "label": "可行个体", "color": "#237A57",
              "fill": False, "pattern": 0, "width": 1.2},
             {"column": 3, "label": "不同染色体", "color": "#7A3E9D",
              "fill": False, "pattern": 0, "width": 1.2}], spec,
            ([r.generation, r.feasible_count, r.unique_count] for r in rows),
            ["代数", "可行个体数", "不同染色体数"])


def plot_ga_plan(problem, result, root: Path):
    """以代际阶梯线显示最终保留方案的装机容量及选址数量变化。"""
    x = [row.generation for row in result.history]
    capacity = [sum(bit * plant.capacity_mw for bit, plant in
                    zip(row.best_chromosome, problem.candidates)) for row in result.history]
    maximum = max(capacity) if capacity else 0.0
    upper = max(1, math.ceil(maximum / max(1, 10 ** math.floor(math.log10(max(maximum, 1))))) *
                max(1, 10 ** math.floor(math.log10(max(maximum, 1)))))
    spec = {"name": "plan", "title": "历代最优方案新增装机变化",
            "x_label": r"\f:SimSun(遗传代数)",
            "y_label": r"\f:SimSun(新增装机) / \f:Times New Roman(MW)",
            "x_min": 0, "x_max": max(1, x[-1]), "y_min": 0, "y_max": upper,
            "x_ticks": sorted({0, x[-1], x[-1] // 4, x[-1] // 2, x[-1] * 3 // 4}),
            "y_ticks": sorted({0, upper, round(upper / 2, 3)}),
            "zero_once": True,
            "caption": "容量随最优染色体更新；每个候选项目的0/1状态见遗传迭代表"}
    _render(root / "08_GA方案演化", {"x": x, "capacity": capacity},
            [{"column": 2, "label": "历代最优新增容量", "color": "#17365D",
              "fill": False, "pattern": 0, "width": 1.4}], spec,
            ([row.generation, cap, "".join(map(str, row.best_chromosome))]
             for row, cap in zip(result.history, capacity)),
            ["代数", "新增容量MW", "最优染色体"])


def plot_dispatch(hourly, first: int, duration: int, root: Path, dirname: str, caption: str):
    """按说明书电力平衡图组织实际发电堆叠、负荷线和上方弃电纹理。"""
    folder = root / dirname
    window = hourly[first:first + duration]
    n = len(window)
    step_x = [value for i in range(n) for value in (i, i + 1)]
    # 封闭多边形由“上边界向前 + 下边界向后”构成；面积为真实逐时电量。
    polygon_x = step_x + list(reversed(step_x)) + [step_x[0]]
    columns = {"x": polygon_x}
    plots = []
    charge_values = [h.storage_charge_mw for h in window]
    if max(charge_values) > 1e-9:
        top, bottom = _step([0.0] * n), _step([-v for v in charge_values])
        columns["charge_negative"] = top + list(reversed(bottom)) + [0.0]
        plots.append({"column": len(columns), "label": "储能充电(负向)", "color": COLORS["storage"],
                      "fill": True, "pattern": 7, "width": 0.3})
    lower = [0.0] * n
    bands = [("thermal", "火电发电", [h.thermal_mw for h in window], COLORS["thermal"], 0),
             ("discharge", "储能放电", [h.storage_discharge_mw for h in window], COLORS["storage"], 0),
             ("solar", "光伏发电", [h.solar_mw for h in window], COLORS["solar"], 6),
             ("wind", "风电发电", [h.wind_mw for h in window], COLORS["wind"], 6),
             ("unserved", "缺供功率", [h.unserved_mw for h in window], COLORS["unserved"], 9),
             # 弃电与所属电源同色；点阵纹理与实际发电的斜线纹理区分。
             ("solar_curt", "光伏弃电", [h.solar_curtailment_mw for h in window], COLORS["solar"], CURTAILMENT_DOT_PATTERN),
             ("wind_curt", "风电弃电", [h.wind_curtailment_mw for h in window], COLORS["wind"], CURTAILMENT_DOT_PATTERN)]
    for key, label, values, color, pattern in bands:
        upper = [base + value for base, value in zip(lower, values)]
        if max(values) > DISPLAY_POWER_TOL_MW:  # 小于显示容差的浮点残差仍留在逐时表。
            top, bottom = _step(upper), _step(lower)
            columns[key] = top + list(reversed(bottom)) + [top[0]]
            plots.append({"column": len(columns), "label": label, "color": color,
                          "fill": True, "pattern": pattern, "width": 0.3})
        lower = upper
    columns["load"] = _step([h.load_mw for h in window])
    plots.append({"column": len(columns), "label": "原始负荷", "color": COLORS["load"],
                  "fill": False, "pattern": 0, "width": 1.1, "end_row": 2 * n})
    ymax = math.ceil(max(lower) / 20) * 20
    ymin = -math.ceil(max(charge_values) / 20) * 20
    # 全年图只稀疏标注轴标签，但所有8760个小时均进入Origin原生工作表。
    xticks = ([0, 2190, 4380, 6570, 8760] if n == 8760 else
              list(range(0, n + 1, 6 if n <= 24 else 24)))
    spec = {"name": "dispatch", "title": "全年8760小时电力平衡" if n == 8760 else "系统电力平衡与电源工作位置",
            "x_label": r"\f:SimSun(相对起始时刻) / \f:Times New Roman(h)",
            "y_label": r"\f:SimSun(功率) / \f:Times New Roman(MW)",
            "x_min": 0, "x_max": n, "y_min": ymin, "y_max": ymax,
            "x_ticks": xticks,
            "y_ticks": list(range(ymin, ymax + 1, 20)), "zero_once": ymin == 0,
            "caption": caption + "；演示数据；正向供给含充电需求，弃电不计发电"}
    _render(folder, columns, plots, spec,
            ([h.hour, h.load_mw, h.thermal_mw, h.solar_mw, h.wind_mw,
              h.solar_curtailment_mw, h.wind_curtailment_mw, h.unserved_mw,
              h.storage_charge_mw, h.storage_discharge_mw, h.storage_energy_end_mwh] for h in window),
            ["全年小时", "负荷MW", "火电MW", "光伏实际MW", "风电实际MW", "弃光MW", "弃风MW", "缺供MW",
             "储能充电MW", "储能放电MW", "小时末存储能量MWh"])


def plot_storage_state(simulation, first: int, root: Path, duration=72,
                       dirname="04_储能连续状态"):
    """绘制连续储能内部能量；72h详图和全年图复用同一物理量。"""
    window = simulation.hourly[first:first + duration]
    energies = [window[0].storage_energy_start_mwh] + [h.storage_energy_end_mwh for h in window]
    x = list(range(len(energies)))
    ymax = max(20, math.ceil(max(energies) / 20) * 20)
    xticks = [0, 2190, 4380, 6570, 8760] if duration == 8760 else [0, 24, 48, 72]
    spec = {"name": "storage_state", "title": "全年8760小时储能连续存储能量" if duration == 8760 else "储能跨日连续存储能量",
            "x_label": r"\f:SimSun(相对起始时刻) / \f:Times New Roman(h)",
            "y_label": r"\f:SimSun(内部存储能量) / \f:Times New Roman(MWh)",
            "x_min": 0, "x_max": len(window), "y_min": 0, "y_max": ymax,
            "x_ticks": xticks, "y_ticks": list(range(0, ymax + 1, 20)),
            "zero_once": True, "caption": "合成演示数据；逐小时状态更新；跨日不复位"}
    _render(root / dirname, {"x": x, "energy": energies},
            [{"column": 2, "label": "内部存储能量", "color": COLORS["storage"],
              "fill": False, "pattern": 0, "width": 1.2}], spec,
            zip(x, energies), ["相对小时", "内部存储能量MWh"])


def plot_results(result, simulation, output_dir: Path, problem=None):
    """生成GA、典型日、全年8760小时及储能连续状态图。"""
    root = output_dir / "figures"
    if result.history:
        plot_convergence(result, root)
        plot_ga_population(result, root)
        if problem is not None:
            plot_ga_plan(problem, result, root)
    hourly = simulation.hourly
    peak = max(range(len(hourly)), key=lambda i: hourly[i].load_mw)
    first_peak = peak // 24 * 24
    plot_dispatch(hourly, first_peak, 24, root, "02_峰荷日电力平衡",
                  f"第{first_peak // 24 + 1}日峰荷日，全年小时{first_peak}–{first_peak + 23}")
    # 窗口选择规则公开，图中时刻仍来自原结果，不人为放大弃电。
    daily_curtailment = [sum(h.wind_curtailment_mw + h.solar_curtailment_mw
                             for h in hourly[d:d + 24]) for d in range(0, len(hourly), 24)]
    max_day = max(range(len(daily_curtailment)), key=daily_curtailment.__getitem__)
    first = min(max(0, (max_day - 1) * 24), len(hourly) - 72)
    plot_dispatch(hourly, first, 72, root, "03_弃电窗口电力平衡",
                  f"最大弃电日周边3日，第{first // 24 + 1}–{first // 24 + 3}日")
    if simulation.storage_hourly:
        # 选取储能充电最大日，以真实运行轨迹展示充放与跨日状态。
        peak_charge = max(range(len(hourly)), key=lambda i: hourly[i].storage_charge_mw)
        state_first = min(max(0, (peak_charge // 24 - 1) * 24), len(hourly) - 72)
        plot_storage_state(simulation, state_first, root)
    plot_dispatch(hourly, 0, len(hourly), root, "05_全年8760电力平衡", "全年逐小时，不降采样")
    if simulation.storage_hourly:
        plot_storage_state(simulation, 0, root, len(hourly), "06_全年8760储能状态")


def plot_project_dispatch(hourly, first, count, folder: Path, year: int):
    """八类机组同图堆叠；抽蓄/电池充电在负向，弃风光使用本色点阵。"""
    window = hourly[first:first + count]
    n = len(window)
    x = [value for i in range(n) for value in (i, i + 1)]
    polygon_x = x + list(reversed(x)) + [x[0]]
    columns = {"x": polygon_x}
    plots = []
    charge = [h.storage_charge_mw for h in window]
    if max(charge) > DISPLAY_POWER_TOL_MW:
        columns["storage_charge"] = [0.0] * (2 * n) + list(reversed(_step([-v for v in charge]))) + [0.0]
        plots.append({"column": len(columns), "label": "储能充电(负向)", "color": COLORS["storage"],
                      "fill": True, "pattern": 7, "width": 0.3})
    bands = (("coal_mw", "煤电", "#FF0000", 0),
             ("gas_mw", "燃气", "#E46C0A", 0),
             ("biomass_mw", "生物质", "#A56A42", 0),
             ("hydro_mw", "常规水电", "#22B8D6", 0),
             ("pumped_discharge_mw", "抽蓄放电", "#154AAB", 0),
             ("battery_discharge_mw", "新型储能放电", "#526CFF", 0),
             ("solar_mw", "光伏", COLORS["solar"], 6),
             ("wind_mw", "风电", COLORS["wind"], 6),
             ("solar_curtailment_mw", "弃光", COLORS["solar"], CURTAILMENT_DOT_PATTERN),
             ("wind_curtailment_mw", "弃风", COLORS["wind"], CURTAILMENT_DOT_PATTERN))
    lower = [0.0] * n
    for field, label, color, pattern in bands:
        values = [getattr(h, field) for h in window]
        upper = [a + b for a, b in zip(lower, values)]
        if max(values) > DISPLAY_POWER_TOL_MW:
            top, bottom = _step(upper), _step(lower)
            columns[field] = top + list(reversed(bottom)) + [top[0]]
            plots.append({"column": len(columns), "label": label, "color": color,
                          "fill": True, "pattern": pattern, "width": 0.3})
        lower = upper
    columns["load"] = _step([h.load_mw for h in window])
    plots.append({"column": len(columns), "label": "负荷+外送", "color": COLORS["load"],
                  "fill": False, "pattern": 0, "width": 1.1, "end_row": 2 * n})
    high = max(max(lower), max(h.load_mw for h in window), 1.0)
    unit = 10 ** math.floor(math.log10(high / 5))
    step = max(unit, math.ceil(high / 5 / unit) * unit)
    ymax = math.ceil(high / step) * step
    ymin = -math.ceil(max(charge) / step) * step
    spec = {"name": "project_dispatch", "title": f"{year}年源网荷储电力平衡" if n == 8760 else f"{year}年典型时段电力平衡",
            "x_label": r"\f:SimSun(相对起始时刻) / \f:Times New Roman(h)",
            "y_label": r"\f:SimSun(功率) / \f:Times New Roman(MW)",
            "x_min": 0, "x_max": n, "y_min": ymin, "y_max": ymax,
            "x_ticks": ([0, 2190, 4380, 6570, 8760] if n == 8760 else
                        [0, n // 4, n // 2, n * 3 // 4, n]),
            "y_ticks": [ymin + i * step for i in range(int(round((ymax - ymin) / step)) + 1)],
            "zero_once": ymin == 0,
            "caption": "真实项目曲线；外送作为固定需求；弃电同电源颜色并以点阵标识"}
    _render(folder, columns, plots, spec,
            ([h.hour, h.domestic_load_mw, h.export_mw, h.load_mw, h.coal_mw,
              h.gas_mw, h.hydro_mw, h.biomass_mw, h.wind_mw, h.solar_mw,
              h.storage_charge_mw, h.storage_discharge_mw, h.unserved_mw]
             for h in window),
            ["小时", "本地负荷MW", "固定外送MW", "总需求MW", "煤电MW", "燃气MW",
             "水电MW", "生物质MW", "风电MW", "光伏MW", "储能充电MW", "储能放电MW", "缺供MW"])


def plot_project_results(case, result, simulation, output_dir: Path):
    """真实项目静态交付包含GA三图、峰荷日和全年8760小时图。"""
    root = output_dir / "figures"
    if result is not None and result.history:
        plot_convergence(result, root)
        plot_ga_population(result, root)
        plot_ga_plan(case, result, root)
    hourly = simulation.hourly
    peak = max(range(len(hourly)), key=lambda i: hourly[i].load_mw)
    first = peak // 24 * 24
    plot_project_dispatch(hourly, first, 24, root / "02_峰荷日电力平衡", case.target_year)
    plot_project_dispatch(hourly, 0, 8760, root / "05_全年8760电力平衡", case.target_year)
