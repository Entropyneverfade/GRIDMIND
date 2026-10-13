"""全年运行结果交互查看窗口：同步浏览电力平衡、储能充放与库存。

启动：python -m power_ga.result_output.viewer --result output
数据直接读取同一结果目录tables内的hourly_dispatch.csv，不重新模拟或改写结果。
"""

import argparse
import csv
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
                   "battery_charge_mw", "battery_discharge_mw")
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


def draw_view(fig, hours, start: int, end: int, view_label=""):
    """上下两图共用时间轴：上为源荷平衡，下为储能充放和内部库存。"""
    if not 0 <= start < end <= 8760:
        raise ValueError("自定义范围必须满足0≤起点<终点≤8760")
    import matplotlib.pyplot as plt

    part = hours[start:end]
    x = list(range(start, end + 1))
    fig.clear()
    top, bottom = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.6, 1], "hspace": 0.12})
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
                  ("solar_mw", "光伏", COLORS["solar"], "//"),
                  ("wind_mw", "风电", COLORS["wind"], "//"),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], ".."),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], ".."))
    else:
        series = (("thermal_mw", "火电", COLORS["thermal"], None),
                  ("storage_discharge_mw", "储能放电", COLORS["storage"], None),
                  ("solar_mw", "光伏", COLORS["solar"], "//"),
                  ("wind_mw", "风电", COLORS["wind"], "//"),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], ".."),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], ".."))
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
             color=COLORS["load"], linewidth=1.1)
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
    top.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=5, fontsize=8, frameon=True)

    # 充电画负值、放电画正值；内部能量E_t不是网侧累计放电量。
    discharge = [h["storage_discharge_mw"] for h in part]
    bottom.step(x, _step(discharge), where="post", color=COLORS["storage"], label="放电 / MW", linewidth=1)
    bottom.step(x, _step([-v for v in charge]), where="post", color=COLORS["charge"],
                label="充电 / MW（负向）", linewidth=1)
    bottom.axhline(0, color="#555555", linewidth=0.5)
    power_max = max(10, math.ceil(max(max(discharge), max(charge)) / 10) * 10)
    bottom.set_ylim(-power_max, power_max)
    bottom.set_yticks([-power_max, 0, power_max])
    bottom.set_ylabel("充放电 / MW")
    stock = bottom.twinx()
    stock.step(x, _step([h["storage_energy_end_mwh"] for h in part]), where="post",
               color="#193276", label="内部库存 / MWh", linewidth=0.8, alpha=0.8)
    energy_max = max(20, math.ceil(max(h["storage_energy_end_mwh"] for h in hours) / 20) * 20)
    stock.set_ylim(0, energy_max)
    stock.set_yticks([0, energy_max / 2, energy_max])
    stock.set_ylabel("内部库存 / MWh")
    bottom.legend(loc="upper left", ncol=2, fontsize=8)
    stock.legend(loc="upper right", fontsize=8)
    bottom.set_xlabel("全年小时序号（小时0为年初）")
    bottom.set_xlim(start, end)
    # 实际显示区间两端都有向内真实刻度；标签数量随尺度自动减少。
    target_step = 6 if end - start <= 24 else (24 if end - start <= 168 else
                                                168 if end - start <= 744 else 2190)
    ticks = [start] + list(range(((start // target_step) + 1) * target_step, end, target_step)) + [end]
    bottom.set_xticks(sorted(set(ticks)))
    for axis in (top, bottom):
        axis.tick_params(direction="in", which="both", top=False, right=False)
    # 库存纵轴在右侧，端点真实刻度也必须朝绘图区内侧。
    stock.tick_params(direction="in", which="both", right=True, left=False)
    fig.subplots_adjust(left=0.08, right=0.90,
                        top=0.75 if "export_mw" in part[0] else 0.84, bottom=0.10)
    return top, bottom


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
        """应用左闭右开区间，并同步刷新两张共享时间轴的图。"""
        try:
            a, b = int(a), int(b)
            view_label = (f"第{number.get()}{scale.get()}" if scale.get() in {"日", "周", "月"}
                          else "全年8760小时" if scale.get() == "年" else f"自定义小时 {a}–{b - 1}")
            draw_view(fig, hours, a, b, view_label)
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
