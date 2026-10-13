"""全年运行结果交互查看窗口：在同一堆叠图浏览出力与储能充放。

启动：python -m power_ga.result_output.viewer --result output
数据直接读取同一结果目录tables内的hourly_dispatch.csv，不重新模拟或改写结果。
"""

import argparse
import csv
import json
import math
from pathlib import Path

from ..common.domain import PLANNING_MONTH_HOURS

# 配色与Origin静态图一致；这里是交互窗口，静态交付仍由Origin原生绘制。
COLORS = {"thermal": "#FF0000", "solar": "#FFFF00", "wind": "#00DD00",
          "storage": "#0000FF", "charge": "#527BFF", "load": "#FF00FF",
          "unserved": "#DDDDDD"}
FIELDS = ("load_mw", "thermal_mw", "wind_mw", "solar_mw", "storage_charge_mw",
          "storage_discharge_mw", "storage_energy_end_mwh", "wind_curtailment_mw",
          "solar_curtailment_mw", "unserved_mw", "overgeneration_mw")
OPTIONAL_FIELDS = ("domestic_load_mw", "export_mw", "coal_mw", "gas_mw", "hydro_mw",
                   "biomass_mw", "pumped_charge_mw", "pumped_discharge_mw",
                   "battery_charge_mw", "battery_discharge_mw", "reserve_shortfall_mw")
MONTH_HOURS = PLANNING_MONTH_HOURS  # 与运行引擎及逐月工作簿相同的365日规划年。


def load_hours(result_dir: Path):
    """读完整8760小时CSV；对缺列、断号和非数值立即报错。"""
    # 表格与图形分目录保存；交互窗口只读表格目录的逐时原始结果。
    path = result_dir / "tables" / "hourly_dispatch.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"hour", *FIELDS}.issubset(reader.fieldnames or []):
            raise ValueError(f"逐时表缺少显示字段: {path}")
        optional = [field for field in OPTIONAL_FIELDS if field in (reader.fieldnames or [])]
        hours = []
        for expected, row in enumerate(reader):
            if int(row["hour"]) != expected:
                raise ValueError(f"逐时数据在第{expected}小时断号")
            hours.append({field: float(row[field]) for field in (*FIELDS, *optional)})
    if len(hours) != 8760:
        raise ValueError(f"查看窗口需要8760小时，实际{len(hours)}小时")
    return hours


def period_bounds(scale: str, number: int):
    """把日/周/月/年序号映射为左闭右开小时区间[start,end)。"""
    if scale == "日":
        if not 1 <= number <= 365:
            raise ValueError("日序号应为1–365")
        start, end = 24 * (number - 1), 24 * number
    elif scale == "周":
        if not 1 <= number <= 53:
            raise ValueError("周序号应为1–53")
        start = 168 * (number - 1)
        end = min(8760, start + 168)
    elif scale == "月":
        if not 1 <= number <= 12:
            raise ValueError("月序号应为1–12")
        start = sum(MONTH_HOURS[:number - 1])
        end = start + MONTH_HOURS[number - 1]
    elif scale == "年":
        start, end = 0, 8760
    else:
        raise ValueError(f"未知查看尺度: {scale}")
    return start, end


def _step(values):
    """每个值保持整整1小时：阶梯右端重复末小时，不线性插值。"""
    return values + [values[-1]]


def month_events(hours, start: int, end: int):
    """选取月内最紧张日及最大弃电日；无缺口时不虚报缺供。"""
    if start % 24 or end % 24 or end <= start:
        raise ValueError("月事件需要完整的日边界")
    days = [hours[t:t + 24] for t in range(start, end, 24)]
    shortage = [sum(h["unserved_mw"] for h in day) for day in days]
    reserve = [sum(h.get("reserve_shortfall_mw", 0.0) for h in day) for day in days]
    net_peak = [max(h["load_mw"] - h["wind_mw"] - h["solar_mw"] for h in day)
                for day in days]
    curtail = [sum(h["wind_curtailment_mw"] + h["solar_curtailment_mw"]
                   for h in day) for day in days]
    if max(shortage) > 1e-6:
        main_values, label, unit = shortage, "最大缺供日", "MWh"
    elif max(reserve) > 1e-6:
        main_values, label, unit = reserve, "最大备用缺口日", "MW·h"
    else:
        main_values, label, unit = net_peak, "净负荷峰值日", "MW"
    main_day = max(range(len(days)), key=main_values.__getitem__)
    events = [{"label": label, "day_of_month": main_day + 1,
               "hour_start": start + main_day * 24, "value": main_values[main_day], "unit": unit}]
    if max(curtail) > 1e-6:
        curtail_day = max(range(len(days)), key=curtail.__getitem__)
        events.append({"label": "最大弃电日", "day_of_month": curtail_day + 1,
                       "hour_start": start + curtail_day * 24,
                       "value": curtail[curtail_day], "unit": "MWh"})
    return events


def draw_view(fig, hours, start: int, end: int, view_label="", mark_month_events=False):
    """一张堆叠图同时展示各类电源、负荷及负向储能充电。"""
    if not 0 <= start < end <= 8760:
        raise ValueError("自定义范围必须满足0≤起点<终点≤8760")
    import matplotlib.pyplot as plt

    part = hours[start:end]
    x = list(range(start, end + 1))
    fig.clear()
    top = fig.subplots(1, 1)
    title = view_label or f"全年第 {start + 1}–{end} 小时"
    figure_name = "源网荷储运行图" if "export_mw" in part[0] else "源荷储运行图"
    fig.suptitle(f"{figure_name}   {title}", fontsize=14, y=0.99)

    # 正向面积按火电→放电→光伏→风电→缺供→弃电堆叠，面积积分=相应电量。
    base = [0.0] * len(part)
    # 项目库保留八类出力；演示算例仍使用原有火电汇总字段。
    if "coal_mw" in part[0]:
        series = (("coal_mw", "煤电", COLORS["thermal"], None),
                  ("gas_mw", "燃气", "#E46C0A", None),
                  ("biomass_mw", "生物质", "#A56A42", None),
                  ("hydro_mw", "常规水电", "#22B8D6", None),
                  ("pumped_discharge_mw", "抽蓄放电", "#154AAB", None),
                  ("battery_discharge_mw", "新型储能放电", "#526CFF", None),
                  ("solar_mw", "光伏", COLORS["solar"], None),
                  ("wind_mw", "风电", COLORS["wind"], None),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], "//"),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], "//"))
    else:
        series = (("thermal_mw", "火电", COLORS["thermal"], None),
                  ("storage_discharge_mw", "储能放电", COLORS["storage"], None),
                  ("solar_mw", "光伏", COLORS["solar"], None),
                  ("wind_mw", "风电", COLORS["wind"], None),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], "//"),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], "//"))
    for field, label, color, hatch in series:
        values = [h[field] for h in part]
        upper = [a + b for a, b in zip(base, values)]
        if max(values) > 1e-8:
            top.fill_between(x, _step(base), _step(upper), step="post", label=label,
                             color=color, linewidth=0.25, edgecolor="black", hatch=hatch)
        base = upper
    charge = [h["storage_charge_mw"] for h in part]
    if max(charge) > 1e-8:
        top.fill_between(x, _step([-v for v in charge]), 0, step="post", label="储能充电（负向）",
                         color=COLORS["charge"], hatch="xx", linewidth=0.3)
    top.step(x, _step([h["load_mw"] for h in part]), where="post", label="原始负荷",
             color=COLORS["load"], linewidth=2.6, zorder=12)
    if "export_mw" in part[0]:
        # 洋红为本地负荷+外送；本地负荷另画虚线，可核对外送贡献。
        top.step(x, _step([h["domestic_load_mw"] for h in part]), where="post",
                 label="本地负荷", color="#803080", linestyle="--", linewidth=0.8)
    ymax = max(20, math.ceil(max(base) / 20) * 20)
    ymin = -math.ceil(max(charge) / 20) * 20
    if ymin == ymax:
        ymin, ymax = 0, 20
    top.set_ylim(ymin, ymax)
    top.set_yticks(list(range(ymin, ymax + 1, 20)))
    top.set_ylabel("功率 / MW")
    top.grid(axis="y", alpha=0.20)
    if mark_month_events:
        # 事件竖线落在完整日中点；图中名称与导出的事件表使用同一计算结果。
        for index, event in enumerate(month_events(hours, start, end)):
            center = event["hour_start"] + 12
            color = "#75407E" if index == 0 else "#996515"
            top.axvline(center, color=color, linestyle="--", linewidth=1.5, zorder=14)
            side = -1 if center > (start + end) / 2 else 1
            top.annotate(f'{event["label"]}·第{event["day_of_month"]}日',
                         xy=(center, ymax * (0.92 - 0.10 * index)),
                         xytext=(center + side * (end - start) * 0.09,
                                 ymax * (0.99 - 0.11 * index)),
                         arrowprops={"arrowstyle": "-", "color": color, "linewidth": 0.8},
                         color=color, fontsize=9, ha="left" if side == 1 else "right",
                         bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
                         zorder=15)
    top.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=5, fontsize=8, frameon=True)

    # 上方同一坐标轴已经把充电画成负面积、放电画成正出力；库存保留在逐时表。
    top.set_xlabel("全年小时序号（小时0为年初）")
    top.set_xlim(start, end)
    # 实际显示区间两端都有向内真实刻度；标签数量随尺度自动减少。
    target_step = 6 if end - start <= 24 else (24 if end - start <= 168 else
                                                168 if end - start <= 744 else 2190)
    ticks = [start] + list(range(((start // target_step) + 1) * target_step, end, target_step)) + [end]
    top.set_xticks(sorted(set(ticks)))
    top.tick_params(direction="in", which="both", top=False, right=False)
    fig.subplots_adjust(left=0.08, right=0.97,
                        top=0.75 if "export_mw" in part[0] else 0.84, bottom=0.10)
    return top


def export_predefined_views(hours, destination: Path):
    """用EXE交互窗口同一个绘图函数，导出日/周/月/年和自定义示例。"""
    from matplotlib.figure import Figure
    import matplotlib

    # 独立导出不创建Tk窗口；字体与可见窗口保持一致，适合后台演示。
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    periods = (("day_182", "日", 182), ("week_27", "周", 27),
               ("month_7", "月", 7), ("year_1", "年", 1))
    manifest = []
    for filename, scale, number in periods:
        # 区间与GUI“应用尺度”按钮共用period_bounds，防止示例与实际窗口错位。
        start, end = period_bounds(scale, number)
        label = f"第{number}{scale}" if scale != "年" else "全年8760小时"
        fig = Figure(figsize=(13, 7), dpi=100)
        draw_view(fig, hours, start, end, label, mark_month_events=scale == "月")
        fig.savefig(destination / f"{filename}.png", dpi=160, facecolor="white")
        manifest.append({"file": f"{filename}.png", "scale": scale,
                         "number": number, "start_hour": start, "end_hour_exclusive": end})
    # 任意区间使用用户可手动输入的相同左闭右开边界。
    start, end = 137, 193
    fig = Figure(figsize=(13, 7), dpi=100)
    draw_view(fig, hours, start, end, f"自定义小时 {start}–{end - 1}")
    fig.savefig(destination / "custom_137_193.png", dpi=160, facecolor="white")
    manifest.append({"file": "custom_137_193.png", "scale": "自定义",
                     "start_hour": start, "end_hour_exclusive": end})
    # 清单仅写入显示区间，不含输入路径或项目元数据。
    (destination / "view_manifest.json").write_text(
        json.dumps({"hours": len(hours), "views": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return manifest


def export_monthly_views(hours, destination: Path):
    """导出12张自然月图及同口径事件CSV，供逐月浏览和公开合成展示。"""
    from matplotlib.figure import Figure
    import matplotlib

    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    event_rows = []
    for month in range(1, 13):
        start, end = period_bounds("月", month)
        fig = Figure(figsize=(13, 7), dpi=100)
        draw_view(fig, hours, start, end, f"第{month}月", mark_month_events=True)
        fig.savefig(destination / f"month_{month:02d}.png", dpi=160, facecolor="white")
        for event in month_events(hours, start, end):
            event_rows.append({"month": month, "start_hour": start,
                               "end_hour_exclusive": end, **event})
    # 事件与逐时功率来自同一合成运行表；日内小时和月边界可复算。
    with (destination / "monthly_events.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("month", "start_hour", "end_hour_exclusive",
                                                    "label", "day_of_month", "hour_start", "value", "unit"))
        writer.writeheader()
        writer.writerows(event_rows)
    return event_rows


def launch(hours, smoke=False):
    """建立用户可见Tk窗口，提供尺度切换、翻页、任意区间和图片导出。"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure

    root = tk.Tk()
    if smoke:
        root.withdraw()  # 后台验证Tk画布，不抢用户前台窗口。
    root.title("源荷储8760小时运行图")
    root.geometry("1380x820")
    controls = ttk.Frame(root, padding=7)
    controls.pack(side="top", fill="x")
    scale = tk.StringVar(value="日")
    number = tk.StringVar(value="1")
    start_text, end_text = tk.StringVar(value="0"), tk.StringVar(value="24")
    status = tk.StringVar(value="数据：8760小时；窗口按小时序号定位")
    ttk.Label(controls, text="尺度").pack(side="left")
    ttk.Combobox(controls, textvariable=scale, values=("日", "周", "月", "年", "自定义"),
                 width=8, state="readonly").pack(side="left", padx=4)
    ttk.Label(controls, text="第几日/周/月").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=number, width=6).pack(side="left", padx=4)
    ttk.Label(controls, text="起始小时").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=start_text, width=7).pack(side="left", padx=4)
    ttk.Label(controls, text="结束小时（不含）").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=end_text, width=7).pack(side="left", padx=4)
    fig = Figure(figsize=(13, 7), dpi=100)
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    toolbar = NavigationToolbar2Tk(canvas, root, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="bottom", fill="x")

    def redraw(a, b):
        """应用左闭右开区间，刷新供给、弃电、充电同图的单张堆叠视图。"""
        try:
            a, b = int(a), int(b)
            view_label = (f"第{number.get()}{scale.get()}" if scale.get() in {"日", "周", "月"}
                          else "全年8760小时" if scale.get() == "年" else f"自定义小时 {a}–{b - 1}")
            draw_view(fig, hours, a, b, view_label, mark_month_events=scale.get() == "月")
            start_text.set(str(a))
            end_text.set(str(b))
            status.set(f"当前窗口：全年小时 {a}–{b - 1}，共 {b - a} 小时")
            canvas.draw_idle()
        except (ValueError, IndexError) as error:
            messagebox.showerror("时间范围错误", str(error), parent=root)

    def apply_scale():
        """尺度按钮按日/周/月序号定位；自定义尺度读取小时边界。"""
        try:
            if scale.get() == "自定义":
                redraw(start_text.get(), end_text.get())
            else:
                redraw(*period_bounds(scale.get(), int(number.get())))
        except ValueError as error:
            messagebox.showerror("序号错误", str(error), parent=root)

    def shift(direction):
        """按当前尺度翻页；自定义区间保持宽度平移，不改变观察小时数。"""
        if scale.get() == "年":
            return
        if scale.get() == "自定义":
            a, b = int(start_text.get()), int(end_text.get())
            width = b - a
            new_a = max(0, min(8760 - width, a + direction * width))
            redraw(new_a, new_a + width)
        else:
            limit = {"日": 365, "周": 53, "月": 12}[scale.get()]
            number.set(str(max(1, min(limit, int(number.get()) + direction))))
            apply_scale()

    def save_picture():
        """只导出当前显示时间窗口；全年原始表和Origin工程不受影响。"""
        path = filedialog.asksaveasfilename(parent=root, title="保存当前视图", defaultextension=".png",
                                            filetypes=[("PNG图片", "*.png")])
        if path:
            fig.savefig(path, dpi=240, facecolor="white")
            status.set("当前视图已保存：" + path)

    ttk.Button(controls, text="应用尺度", command=apply_scale).pack(side="left", padx=4)
    ttk.Button(controls, text="按小时区间显示", command=lambda: (scale.set("自定义"), apply_scale())).pack(side="left", padx=4)
    ttk.Button(controls, text="前一段", command=lambda: shift(-1)).pack(side="left", padx=4)
    ttk.Button(controls, text="后一段", command=lambda: shift(1)).pack(side="left", padx=4)
    ttk.Button(controls, text="导出当前PNG", command=save_picture).pack(side="left", padx=4)
    ttk.Label(root, textvariable=status, padding=6).pack(side="bottom", fill="x")
    redraw(0, 24)
    if smoke:
        root.update_idletasks()
        root.destroy()
        print("Tk窗口控件后台校验通过")
        return
    root.mainloop()


def main():
    """命令行入口；--self-test在后台检查四种尺度与自定义区间。"""
    parser = argparse.ArgumentParser(description="8760小时运行图交互查看窗口")
    parser.add_argument("--result", type=Path, default=Path(__file__).resolve().parents[2] / "output")
    parser.add_argument("--self-test", action="store_true", help="后台绘图校验，不打开窗口")
    parser.add_argument("--gui-smoke", action="store_true", help="后台检查Tk控件初始化后立即关闭")
    args = parser.parse_args()
    hours = load_hours(args.result)
    import matplotlib
    matplotlib.use("Agg" if args.self_test else "TkAgg")
    matplotlib.rcParams["font.sans-serif"] = ["SimSun", "Microsoft YaHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    if args.self_test:
        from matplotlib.figure import Figure
        # 日、周、月、年和不对齐自然时段的区间都应可画；不弹出窗口。
        windows = [period_bounds(s, n) for s, n in (("日", 1), ("周", 2), ("月", 12), ("年", 1))]
        windows.append((137, 193))
        for start, end in windows:
            draw_view(Figure(figsize=(10, 6)), hours, start, end)
        print("查看窗口后台校验通过：日、周、月、年、自定义")
    else:
        launch(hours, smoke=args.gui_smoke)


if __name__ == "__main__":
    main()
