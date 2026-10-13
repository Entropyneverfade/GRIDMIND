"""GRIDMIND桌面平台：导入项目库、执行规划与模拟、查看图表和结果存档。"""

import argparse
import csv
import os
import queue
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

# 直接运行本文件或单文件EXE时，让窗口入口可导入同级算法包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def resource(name):
    """源码与PyInstaller单文件运行都能找到图标、默认成本参数。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / name


def user_folder():
    """可编辑输入和结果保存在EXE旁边；不会写入临时解包目录。"""
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return root / "GRIDMIND_data"


def prepare_cost_file():
    """首次启动复制默认试算参数，之后保留用户对CSV的编辑。"""
    folder = user_folder()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "project_costs.csv"
    if not target.exists():
        shutil.copy2(resource("input/project_costs.csv"), target)
    return target


def show_ga_window(result_dir):
    """从归档表读代际轨迹，在交互窗口同时展示费用/可行性/方案容量。"""
    import tkinter as tk
    from tkinter import ttk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import matplotlib

    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    path = Path(result_dir) / "tables" / "history.csv"
    if not path.exists():
        raise FileNotFoundError("该存档是仅运行模拟，没有遗传迭代记录")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    x = [int(r["代数"]) for r in rows]
    best = [float(r["历代最优元"]) / 1e8 for r in rows]
    current = [float(r["本代最优元"]) / 1e8 for r in rows]
    average = [float(r["可行种群均值元"]) / 1e8 for r in rows]
    feasible = [int(r["可行个体数"]) for r in rows]
    unique = [int(r["不同染色体数"]) for r in rows]
    window = tk.Tk()
    window.title("GRIDMIND · 遗传规划结果")
    window.geometry("1190x760")
    figure = Figure(figsize=(11, 6.5), dpi=100)
    axes = figure.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.18})
    axes[0].plot(x, best, color="#1D3557", linewidth=2, label="历代最优")
    axes[0].plot(x, current, color="#D96C2B", linewidth=1.2, label="本代最优")
    axes[0].plot(x, average, color="#3186AE", linewidth=1.2, label="可行种群均值")
    axes[0].set_ylabel("年总成本 / 亿元")
    axes[0].legend(loc="best")
    axes[1].plot(x, feasible, color="#237A57", linewidth=1.5, label="可行个体数")
    axes[1].plot(x, unique, color="#8754A1", linewidth=1.5, label="不同染色体数")
    axes[1].set_ylabel("个体数")
    axes[1].set_xlabel("遗传代数")
    axes[1].legend(loc="best")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.tick_params(direction="in", which="both")
        axis.set_xlim(x[0], max(x[-1], 1))
    figure.suptitle("规划收敛与种群状态", fontsize=14)
    figure.subplots_adjust(left=0.10, right=0.97, top=0.91, bottom=0.09)
    canvas = FigureCanvasTkAgg(figure, master=window)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    toolbar = NavigationToolbar2Tk(canvas, window, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(fill="x")
    ttk.Label(window, text=f"存档：{result_dir}", padding=6).pack(fill="x")
    window.mainloop()


def launch_app(smoke=False):
    """主窗口通过后台线程计算，Tk只负责文件选择、进度和查看结果。"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import matplotlib

    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    from project_main import execute

    root = tk.Tk()
    root.title("GRIDMIND · 电源规划与全年运行模拟")
    root.geometry("950x690")
    root.minsize(850, 600)
    icon = resource("gridmind_app/assets/gridmind.ico")
    if icon.exists():
        root.iconbitmap(str(icon))
    if smoke:
        root.withdraw()
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="GRIDMIND", font=("Microsoft YaHei UI", 25, "bold"),
              foreground="#17365D").grid(row=0, column=0, sticky="w", columnspan=3)
    ttk.Label(frame, text="全年8760小时 · 多类型电源 · 遗传规划 · 可复用结果存档",
              foreground="#56718A").grid(row=1, column=0, sticky="w", columnspan=3, pady=(0, 22))
    # 最近使用的数据目录仅保存在EXE旁；程序包不携带真实算例路径。
    source_record = user_folder() / "last_source.txt"
    last_source = source_record.read_text(encoding="utf-8").strip() if source_record.exists() else ""
    source = tk.StringVar(value=last_source)
    costs = tk.StringVar(value=str(prepare_cost_file()))
    year = tk.StringVar(value="2029")
    population = tk.StringVar(value="12")
    generations = tk.StringVar(value="12")
    seed = tk.StringVar(value="1")
    figures = tk.BooleanVar(value=True)
    status = tk.StringVar(value="请选择项目数据库，然后开始计算")
    last_result = {"path": None}
    messages = queue.Queue()

    def browse(var, directory):
        """来源目录和成本CSV均由用户可见控件选取。"""
        selected = (filedialog.askdirectory(parent=root, title="选择项目数据库文件夹") if directory else
                    filedialog.askopenfilename(parent=root, title="选择技术经济参数CSV",
                                               filetypes=[("CSV", "*.csv")]))
        if selected:
            var.set(selected)

    def add_path(row, label, var, directory):
        """同一行使用标签、可编辑输入框和浏览按钮。"""
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=7)
        ttk.Entry(frame, textvariable=var, width=78).grid(row=row, column=1, sticky="ew", pady=7)
        ttk.Button(frame, text="浏览…", command=lambda: browse(var, directory)).grid(row=row, column=2, padx=(8, 0))

    add_path(2, "项目数据库", source, True)
    add_path(3, "经济参数", costs, False)
    options = ttk.Frame(frame)
    options.grid(row=4, column=0, columnspan=3, sticky="w", pady=(17, 10))
    ttk.Label(options, text="目标年").pack(side="left")
    ttk.Combobox(options, textvariable=year, values=[str(x) for x in range(2025, 2030)],
                 state="readonly", width=7).pack(side="left", padx=(5, 22))
    for label, var in (("种群", population), ("最大代数", generations), ("随机种子", seed)):
        ttk.Label(options, text=label).pack(side="left")
        ttk.Entry(options, textvariable=var, width=7).pack(side="left", padx=(5, 17))
    ttk.Checkbutton(options, text="生成Origin图件", variable=figures).pack(side="left", padx=6)
    controls = ttk.Frame(frame)
    controls.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 14))

    def run(plan):
        """验证路径与代数；计算线程写队列，不直接操作Tk控件。"""
        try:
            src, cost = Path(source.get()), Path(costs.get())
            if not src.is_dir() or not cost.is_file():
                raise ValueError("项目数据库文件夹或经济参数CSV不存在")
            y, pop, gen, random_seed = int(year.get()), int(population.get()), int(generations.get()), int(seed.get())
            if pop < 2 or gen < 1:
                raise ValueError("种群至少2个、最大代数至少1代")
        except ValueError as error:
            messagebox.showerror("输入错误", str(error), parent=root)
            return
        # 用户选择通过验证后才更新本地记录，便于下一次启动复用。
        source_record.write_text(str(src.resolve()), encoding="utf-8")
        destination = user_folder().parent / "GRIDMIND_results" / f"scenario_{y}_{datetime.now():%Y%m%d_%H%M%S}"
        start_plan.configure(state="disabled")
        start_sim.configure(state="disabled")
        status.set("正在读取数据…")

        make_figures = bool(figures.get())  # Tk变量只在主线程取值。

        def worker():
            """后台执行GA和全年模拟；Origin也仅在后台独立进程中运行。"""
            try:
                _, result, simulation, folder = execute(src, y, cost, destination,
                    plan=plan, figures=make_figures, population=pop, generations=gen,
                    seed=random_seed, progress=lambda message: messages.put(("status", message)))
                messages.put(("done", (folder, result, simulation.summary)))
            except Exception as error:
                messages.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    start_plan = ttk.Button(controls, text="运行遗传规划与全年模拟", command=lambda: run(True))
    start_plan.pack(side="left", padx=(0, 10))
    start_sim = ttk.Button(controls, text="仅模拟基年存量", command=lambda: run(False))
    start_sim.pack(side="left")

    def open_viewer():
        """查看器作为独立窗口打开，可按日周月年或任意小时区间缩放。"""
        if last_result["path"]:
            args = ([sys.executable, "--viewer", str(last_result["path"])] if getattr(sys, "frozen", False) else
                    [sys.executable, str(Path(__file__).resolve()), "--viewer", str(last_result["path"])])
            subprocess.Popen(args)

    def open_ga():
        """查看遗传收敛和种群状态；只模拟的存档不含GA历史。"""
        if last_result["path"]:
            args = ([sys.executable, "--ga", str(last_result["path"])] if getattr(sys, "frozen", False) else
                    [sys.executable, str(Path(__file__).resolve()), "--ga", str(last_result["path"])])
            subprocess.Popen(args)

    def open_folder():
        """使用系统资源管理器打开本次归档目录。"""
        if last_result["path"]:
            os.startfile(last_result["path"])

    result_tools = ttk.Frame(frame)
    result_tools.grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 13))
    view_button = ttk.Button(result_tools, text="查看8760小时运行图", command=open_viewer, state="disabled")
    view_button.pack(side="left", padx=(0, 10))
    ga_button = ttk.Button(result_tools, text="查看遗传规划图", command=open_ga, state="disabled")
    ga_button.pack(side="left", padx=(0, 10))
    folder_button = ttk.Button(result_tools, text="打开结果存档", command=open_folder, state="disabled")
    folder_button.pack(side="left")
    ttk.Label(frame, textvariable=status, foreground="#235777").grid(
        row=7, column=0, columnspan=3, sticky="w", pady=5)
    log = tk.Text(frame, height=15, state="disabled", wrap="word", font=("Microsoft YaHei UI", 9))
    log.grid(row=8, column=0, columnspan=3, sticky="nsew")
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(8, weight=1)

    def poll():
        """定时取后台消息；完成后开启查看与存档按钮。"""
        try:
            while True:
                kind, payload = messages.get_nowait()
                if kind == "status":
                    status.set(payload)
                    log.configure(state="normal")
                    log.insert("end", payload + "\n")
                    log.see("end")
                    log.configure(state="disabled")
                elif kind == "done":
                    folder, result, summary = payload
                    last_result["path"] = folder
                    start_plan.configure(state="normal")
                    start_sim.configure(state="normal")
                    view_button.configure(state="normal")
                    folder_button.configure(state="normal")
                    ga_button.configure(state="normal" if result else "disabled")
                    status.set(f"完成 · 缺供 {summary['unserved']:.3f} MWh · {folder}")
                else:
                    start_plan.configure(state="normal")
                    start_sim.configure(state="normal")
                    status.set("运行失败：" + payload)
                    messagebox.showerror("计算失败", payload, parent=root)
        except queue.Empty:
            pass
        root.after(150, poll)

    root.after(150, poll)
    if smoke:
        root.update_idletasks()
        root.destroy()
        print("GRIDMIND窗口后台初始化通过")
        return
    root.mainloop()


def main():
    """EXE自身既是主窗口，也可启动独立运行图和遗传图窗口。"""
    parser = argparse.ArgumentParser(description="GRIDMIND桌面应用")
    parser.add_argument("--viewer", type=Path)
    parser.add_argument("--ga", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.viewer:
        from power_ga.result_output.viewer import launch, load_hours
        import matplotlib
        matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        launch(load_hours(args.viewer))
    elif args.ga:
        show_ga_window(args.ga)
    else:
        launch_app(args.smoke_test)


if __name__ == "__main__":
    main()
