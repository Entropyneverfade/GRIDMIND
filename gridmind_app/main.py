"""GRIDMIND桌面平台：导入项目库、执行规划与模拟、查看图表和结果存档。"""

import argparse
import csv
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

APP_VERSION = "0.2.13"

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


def default_figure_backend():
    """只查 Windows COM 注册表，不启动 Origin；缺少 Origin 时自动选 Python。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Origin.ApplicationSI"):
            return "origin"
    except (OSError, ImportError):
        return "python"


def launch_gui_child(args):
    """启动结果查看器而不附带Windows命令窗口；图形窗口仍正常显示。"""
    # 源码模式使用python.exe时也可能分配控制台；CREATE_NO_WINDOW只抑制控制台。
    hidden_console = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(args, creationflags=hidden_console)


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


def show_dp_window(result_dir):
    """读取阶段归档并展示年度费用和累计投运状态。"""
    import tkinter as tk
    from tkinter import ttk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import matplotlib

    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    with (Path(result_dir) / "tables" / "dynamic_stages.csv").open(
            encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    years = [int(row["规划年"]) for row in rows]
    annual = [float(row["年度费用元"]) / 1e8 for row in rows]
    discounted = [float(row["折现费用元"]) / 1e8 for row in rows]
    states = [int(row["累计状态整数"]) for row in rows]
    window = tk.Tk()
    window.title(f"GRIDMIND {APP_VERSION} · 动态规划阶段结果")
    history_path = Path(result_dir) / "tables" / "multiyear_ga_history.csv"
    has_comparison = history_path.is_file()
    window.geometry("1050x790" if has_comparison else "1050x700")
    figure = Figure(figsize=(10, 6), dpi=100)
    axes = figure.subplots(3 if has_comparison else 2, 1,
                          gridspec_kw={"hspace": 0.45 if has_comparison else 0.32})
    top, bottom = axes[:2]
    top.plot(years, annual, "o-", color="#1D3557", linewidth=2, label="年度费用")
    top.plot(years, discounted, "s--", color="#D96C2B", linewidth=1.5, label="折现费用")
    top.set_ylabel("费用 / 亿元")
    top.legend()
    bottom.step(years, states, where="post", color="#237A57", linewidth=2)
    bottom.scatter(years, states, color="#237A57")
    bottom.set_ylabel("累计投运状态")
    bottom.set_xlabel("规划年份")
    for axis in (top, bottom):
        axis.set_xlim(min(years) - 0.1, max(years) + 0.1)
        axis.set_xticks(years)
        axis.grid(alpha=0.2)
        axis.tick_params(direction="in", which="both")
    if has_comparison:
        # 同一状态费用表上的GA收敛曲线与DP全局下界并排显示；不可行代不冒充最优。
        with history_path.open(encoding="utf-8-sig", newline="") as stream:
            history = list(csv.DictReader(stream))
        generations = [int(row["代"]) for row in history]
        feasible = [row["历代最优可行"].lower() == "true" for row in history]
        values = [float(row["历代最优折现费用元"]) / 1e8 if valid else float("nan")
                  for row, valid in zip(history, feasible)]
        comparison = axes[2]
        comparison.plot(generations, values, color="#1D3557", linewidth=2,
                        marker="o", markersize=2.5, label="GA可行最优")
        audit = json.loads((Path(result_dir) / "dynamic_audit.json").read_text(encoding="utf-8"))
        comparison.axhline(audit["objective_yuan"] / 1e8, color="#D96C2B",
                           linestyle="--", linewidth=1.5, label="DP/Gurobi最优")
        comparison.set_ylabel("折现总费 / 亿元")
        comparison.set_xlabel("遗传代数")
        comparison.grid(alpha=0.2)
        comparison.legend()
        comparison.tick_params(direction="in", which="both")
    figure.suptitle("动态规划年度建设与同口径遗传对照" if has_comparison else
                    "动态规划年度建设与费用", fontsize=14)
    figure.subplots_adjust(left=0.12, right=0.97, top=0.91 if has_comparison else 0.89,
                           bottom=0.09 if has_comparison else 0.11)
    for axis in axes:
        # 显示边界也要有真实内向刻度，边界小刻度无需重复数字标签。
        x_left, x_right = axis.get_xlim()
        y_low, y_high = axis.get_ylim()
        axis.set_xticks((x_left, x_right), minor=True)
        axis.set_yticks((y_low, y_high), minor=True)
        axis.tick_params(which="minor", direction="in", length=4)
        axis.set_xlim(x_left, x_right)
        axis.set_ylim(y_low, y_high)
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
    root.title(f"GRIDMIND {APP_VERSION} · 电源规划与全年运行模拟")
    root.geometry("950x690")
    root.minsize(850, 600)
    icon = resource("gridmind_app/assets/gridmind.ico")
    if icon.exists():
        root.iconbitmap(str(icon))
    if smoke:
        root.withdraw()
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=f"GRIDMIND {APP_VERSION}", font=("Microsoft YaHei UI", 25, "bold"),
              foreground="#17365D").grid(row=0, column=0, sticky="w", columnspan=3)
    ttk.Label(frame, text="全年8760小时 · 多类型电源 · 遗传/动态规划 · 可复用结果存档",
              foreground="#56718A").grid(row=1, column=0, sticky="w", columnspan=3, pady=(0, 22))
    # 最近使用的数据目录仅保存在EXE旁；程序包不携带真实算例路径。
    source_record = user_folder() / "last_source.txt"
    last_source = source_record.read_text(encoding="utf-8").strip() if source_record.exists() else ""
    source = tk.StringVar(value=last_source)
    # 后台窗口预检只读取内置默认参数，不在公开源码目录生成用户数据文件。
    costs = tk.StringVar(value=str(resource("input/project_costs.csv") if smoke else
                             prepare_cost_file()))
    year = tk.StringVar(value="2029")
    population = tk.StringVar(value="12")
    generations = tk.StringVar(value="12")
    seed = tk.StringVar(value="1")
    algorithm = tk.StringVar(value="遗传算法")
    stage_source = tk.StringVar(value="年度源库")
    previous_factor = tk.StringVar(value="0.95")
    figures = tk.BooleanVar(value=True)
    figure_backend = tk.StringVar(value="Origin" if default_figure_backend() == "origin"
                                  else "Python")
    network_case_folder = tk.StringVar()
    network_solver = tk.StringVar(value="Gurobi LP")
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
    ttk.Checkbutton(options, text="生成图件", variable=figures).pack(side="left", padx=6)
    ttk.Label(options, text="绘图后端").pack(side="left", padx=(8, 0))
    ttk.Combobox(options, textvariable=figure_backend, values=("Origin", "Python"),
                 state="readonly", width=8).pack(side="left", padx=5)
    # 动态规划默认取独立年度曲线；系数情景只在用户选中时参与计算。
    method_options = ttk.Frame(frame)
    method_options.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 8))
    ttk.Label(method_options, text="规划方法").pack(side="left")
    ttk.Combobox(method_options, textvariable=algorithm,
                 values=("遗传算法", "动态规划（双年度）", "动态规划（全规划年）"),
                 state="readonly",
                 width=20).pack(side="left", padx=(5, 12))
    ttk.Label(method_options, text="阶段输入").pack(side="left")
    ttk.Combobox(method_options, textvariable=stage_source,
                 values=("年度源库", "系数情景"), state="readonly",
                 width=9).pack(side="left", padx=(5, 12))
    ttk.Label(method_options, text="情景负荷系数").pack(side="left")
    ttk.Entry(method_options, textvariable=previous_factor, width=7).pack(side="left", padx=5)
    controls = ttk.Frame(frame)
    controls.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 14))
    plan_controls = ttk.Frame(controls)
    plan_controls.pack(anchor="w")

    def run(plan):
        """验证路径与代数；计算线程写队列，不直接操作Tk控件。"""
        try:
            src, cost = Path(source.get()), Path(costs.get())
            if not src.is_dir() or not cost.is_file():
                raise ValueError("项目数据库文件夹或经济参数CSV不存在")
            y, pop, gen, random_seed = int(year.get()), int(population.get()), int(generations.get()), int(seed.get())
            factor = float(previous_factor.get())
            if pop < 2 or gen < 1:
                raise ValueError("种群至少2个、最大代数至少1代")
            if (plan and algorithm.get().startswith("动态") and
                    stage_source.get() == "系数情景" and not 0 < factor <= 1):
                raise ValueError("动态规划前一年负荷系数必须在(0,1]内")
            if (plan and "全规划年" in algorithm.get() and
                    stage_source.get() != "年度源库"):
                raise ValueError("全规划年动态规划须读取各年度源库，不能使用单一负荷系数")
        except ValueError as error:
            messagebox.showerror("输入错误", str(error), parent=root)
            return
        # 用户选择通过验证后才更新本地记录，便于下一次启动复用。
        source_record.write_text(str(src.resolve()), encoding="utf-8")
        destination = user_folder().parent / "GRIDMIND_results" / f"scenario_{y}_{datetime.now():%Y%m%d_%H%M%S}"
        start_plan.configure(state="disabled")
        start_sim.configure(state="disabled")
        network_button.configure(state="disabled")
        status.set("正在读取数据…")

        make_figures = bool(figures.get())  # Tk变量只在主线程取值。
        selected_backend = figure_backend.get().lower()
        method = "dp" if algorithm.get().startswith("动态") else "ga"
        stage_mode = "source" if stage_source.get() == "年度源库" else "scaled"
        horizon = "full" if "全规划年" in algorithm.get() else "pair"

        def worker():
            """后台执行GA和全年模拟；Origin也仅在后台独立进程中运行。"""
            try:
                _, result, simulation, folder = execute(src, y, cost, destination,
                    plan=plan, figures=make_figures, population=pop, generations=gen,
                    seed=random_seed, progress=lambda message: messages.put(("status", message)),
                    algorithm=method, previous_load_factor=factor,
                    stage_input_mode=stage_mode, planning_horizon=horizon,
                    figure_backend=selected_backend)
                messages.put(("done", (folder, result, simulation.summary)))
            except Exception as error:
                messages.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    start_plan = ttk.Button(plan_controls, text="运行所选规划与全年模拟", command=lambda: run(True))
    start_plan.pack(side="left", padx=(0, 10))
    start_sim = ttk.Button(plan_controls, text="仅模拟存量系统", command=lambda: run(False))
    start_sim.pack(side="left")

    # 分区CSV是独立试验入口；用户须显式提供线路限额、区域需求及属性因子。
    network_controls = ttk.Frame(controls)
    network_controls.pack(anchor="w", pady=(10, 0))
    ttk.Label(network_controls, text="分区CSV").pack(side="left")
    ttk.Entry(network_controls, textvariable=network_case_folder, width=43).pack(side="left", padx=5)
    ttk.Button(network_controls, text="浏览…", command=lambda: browse(network_case_folder, True)).pack(side="left")
    ttk.Combobox(network_controls, textvariable=network_solver,
                 values=("Gurobi LP", "启发式（可控通道）"), state="readonly",
                 width=18).pack(side="left", padx=6)

    def make_network_demo():
        """仅生成公开固定种子四区教学输入；不读取项目数据库。"""
        from examples.synthetic_network_case import write_case_input

        folder = user_folder() / f"network_demo_{datetime.now():%Y%m%d_%H%M%S}"
        try:
            write_case_input(folder)
            network_case_folder.set(str(folder))
            status.set("已生成合成分区输入；请选择Gurobi LP运行交流示意边")
        except Exception as error:
            messagebox.showerror("演示输入失败", str(error), parent=root)

    def run_network():
        """后台执行8760小时分区流和属性追踪，结果与项目规划分开存档。"""
        from power_ga.operation_simulation.network_case import run_network_case

        source_dir = Path(network_case_folder.get())
        if not source_dir.is_dir():
            messagebox.showerror("输入错误", "请选择包含四个分区CSV的目录", parent=root)
            return
        method = "gurobi" if network_solver.get() == "Gurobi LP" else "heuristic"
        destination = user_folder().parent / "GRIDMIND_results" / f"network_{datetime.now():%Y%m%d_%H%M%S}"
        for button in (start_plan, start_sim, network_button):
            button.configure(state="disabled")
        status.set("正在读取分区CSV…")

        def worker():
            """耗时求解在后台线程；Tk控件只由主线程的poll更新。"""
            try:
                audit = run_network_case(source_dir, destination, solver=method,
                                         progress=lambda note: messages.put(("status", note)))
                messages.put(("network_done", (destination, audit)))
            except Exception as error:
                messages.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(network_controls, text="生成合成输入", command=make_network_demo).pack(side="left")
    network_button = ttk.Button(network_controls, text="运行分区", command=run_network)
    network_button.pack(side="left", padx=6)

    def open_viewer():
        """查看器作为独立窗口打开，可按日周月年或任意小时区间缩放。"""
        if last_result["path"]:
            folder = Path(last_result["path"])
            if (folder / "tables" / "hourly_network.csv").is_file():
                # 分区结果直接打开同一查看器；用户在图内下拉切换全网及各区。
                flag = ["--network-viewer", str(folder), "全网汇总"]
            else:
                flag = ["--viewer", str(folder)]
            args = ([sys.executable, *flag] if getattr(sys, "frozen", False) else
                    [sys.executable, str(Path(__file__).resolve()), *flag])
            launch_gui_child(args)

    def open_ga():
        """按存档类型选择遗传收敛图或动态规划年度图。"""
        if last_result["path"]:
            flag = ("--dp" if (Path(last_result["path"]) / "tables" /
                                "dynamic_stages.csv").is_file() else "--ga")
            args = ([sys.executable, flag, str(last_result["path"])] if getattr(sys, "frozen", False) else
                    [sys.executable, str(Path(__file__).resolve()), flag, str(last_result["path"])])
            launch_gui_child(args)

    def open_folder():
        """使用系统资源管理器打开本次归档目录。"""
        if last_result["path"]:
            os.startfile(last_result["path"])

    def load_saved():
        """重新载入既有存档；只读检查清单和小时表，不重新运行或覆盖结果。"""
        selected = filedialog.askdirectory(parent=root, title="选择已有GRIDMIND结果存档")
        if not selected:
            return
        folder = Path(selected)
        standard = (folder / "tables" / "hourly_dispatch.csv").is_file()
        zonal = (folder / "tables" / "hourly_network.csv").is_file()
        if not (folder / "run_manifest.json").is_file() or not (standard or zonal):
            messagebox.showerror("存档无效", "所选文件夹缺少运行清单或8760小时表", parent=root)
            return
        last_result["path"] = folder
        view_button.configure(state="normal")
        folder_button.configure(state="normal")
        ga_button.configure(state="normal" if ((folder / "tables" / "history.csv").is_file() or
                                           (folder / "tables" / "dynamic_stages.csv").is_file()) else "disabled")
        status.set("已载入存档：" + str(folder))

    result_tools = ttk.Frame(frame)
    result_tools.grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 13))
    view_button = ttk.Button(result_tools, text="查看8760小时运行图", command=open_viewer, state="disabled")
    view_button.pack(side="left", padx=(0, 10))
    ga_button = ttk.Button(result_tools, text="查看规划图", command=open_ga, state="disabled")
    ga_button.pack(side="left", padx=(0, 10))
    folder_button = ttk.Button(result_tools, text="打开结果存档", command=open_folder, state="disabled")
    folder_button.pack(side="left")
    ttk.Button(result_tools, text="载入已有存档", command=load_saved).pack(side="left", padx=(10, 0))
    ttk.Label(frame, textvariable=status, foreground="#235777").grid(
        row=8, column=0, columnspan=3, sticky="w", pady=5)
    log = tk.Text(frame, height=15, state="disabled", wrap="word", font=("Microsoft YaHei UI", 9))
    log.grid(row=9, column=0, columnspan=3, sticky="nsew")
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(9, weight=1)

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
                    network_button.configure(state="normal")
                    view_button.configure(state="normal")
                    folder_button.configure(state="normal")
                    ga_button.configure(state="normal" if ((Path(folder) / "tables" / "history.csv").is_file() or
                                                       (Path(folder) / "tables" / "dynamic_stages.csv").is_file()) else "disabled")
                    status.set(f"完成 · 缺供 {summary['unserved']:.3f} MWh · {folder}")
                elif kind == "network_done":
                    folder, audit = payload
                    last_result["path"] = folder
                    start_plan.configure(state="normal")
                    start_sim.configure(state="normal")
                    network_button.configure(state="normal")
                    view_button.configure(state="normal")
                    ga_button.configure(state="disabled")
                    folder_button.configure(state="normal")
                    status.set(f"分区运行完成 · {audit['hours']}小时 · 最大功率残差"
                               f" {audit['max_power_balance_residual_mw']:.2e} MW · {folder}")
                else:
                    start_plan.configure(state="normal")
                    start_sim.configure(state="normal")
                    network_button.configure(state="normal")
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
    parser.add_argument("--viewer-smoke", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--viewer-switch-smoke", nargs=2, type=Path,
                        metavar=("SINGLE_RESULT", "NETWORK_RESULT"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--network-viewer", nargs=2, metavar=("RESULT_DIR", "ZONE"))
    parser.add_argument("--network-viewer-smoke", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--export-demo-views", nargs=2, type=Path,
                        metavar=("RESULT_DIR", "IMAGE_DIR"),
                        help="用同一窗口绘图函数导出日、周、月、年和自定义时段PNG")
    parser.add_argument("--export-network-views", nargs=3,
                        metavar=("RESULT_DIR", "ZONE", "IMAGE_DIR"),
                        help="按分区导出交互窗口同款日/周/月/年缩放预览")
    parser.add_argument("--export-monthly-views", nargs=2, type=Path,
                        metavar=("RESULT_DIR", "IMAGE_DIR"),
                        help="导出12张自然月图和标志时段事件CSV")
    parser.add_argument("--render-project-python", type=Path,
                        help="从已有项目运行表格在figures_python重绘，无需Origin")
    parser.add_argument("--ga", type=Path)
    parser.add_argument("--dp", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--pdf-fallback", nargs=2, metavar=("PNG", "PDF"), help=argparse.SUPPRESS)
    parser.add_argument("--batch-source", type=Path, help="后台批处理使用的兼容项目数据库目录")
    parser.add_argument("--batch-network-source", type=Path,
                        help="运行四CSV分区案例，含8760小时流量与碳硫属性")
    parser.add_argument("--batch-network-output", type=Path)
    parser.add_argument("--batch-network-solver", choices=("heuristic", "gurobi"),
                        default="gurobi")
    parser.add_argument("--batch-costs", type=Path, help="后台批处理使用的可编辑成本CSV")
    parser.add_argument("--batch-output", type=Path, help="后台批处理结果目录")
    parser.add_argument("--batch-year", type=int, default=2029)
    parser.add_argument("--batch-simulate-only", action="store_true")
    parser.add_argument("--batch-skip-figures", action="store_true")
    parser.add_argument("--batch-figure-backend", choices=("auto", "origin", "python"),
                        default="auto", help="无 Origin 时 auto 自动使用 Python 绘图")
    parser.add_argument("--batch-algorithm", choices=("ga", "dp"), default="ga")
    # 批处理与窗口共用遗传参数；DP模式也用它们执行同阶段费用表上的GA对照。
    parser.add_argument("--batch-population", type=int, default=12)
    parser.add_argument("--batch-generations", type=int, default=12)
    parser.add_argument("--batch-seed", type=int, default=1)
    parser.add_argument("--batch-previous-load-factor", type=float, default=0.95)
    parser.add_argument("--batch-stage-input-mode", choices=("source", "scaled"), default="source")
    parser.add_argument("--batch-planning-horizon", choices=("pair", "full"), default="pair")
    parser.add_argument("--batch-synthetic-dynamic", type=Path,
                        help="用EXE复现公开合成双年度GA/DP对比案例")
    parser.add_argument("--gurobi-check", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pdf_fallback:
        # Origin对高密度年度矢量PDF导出失败时，用其原生600dpi PNG封装PDF。
        # 子命令由打包后的EXE自身执行，不要求用户另装Python解释器。
        from PIL import Image
        png, pdf = map(Path, args.pdf_fallback)
        with Image.open(png) as picture:
            picture.convert("RGB").save(pdf, "PDF", resolution=600)
    elif args.gurobi_check:
        # 快速验证冻结包能载入求解器；无需先评价512个年度状态。
        try:
            from power_ga.dynamic_planning.solver import _gurobi_path
            from types import SimpleNamespace
            table = {0: SimpleNamespace(feasible=True, total_cost_yuan=2.0),
                     1: SimpleNamespace(feasible=True, total_cost_yuan=1.0)}
            path, objective = _gurobi_path((table, table), 0.07, 1)
            if path != (1, 1) or abs(objective - (1 + 1 / 1.07)) > 1e-6:
                raise AssertionError("冻结求解器已载入，但最小状态路径不正确")
        except Exception:
            import traceback
            user_folder().mkdir(parents=True, exist_ok=True)
            (user_folder() / "gurobi_check_error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
    elif args.batch_synthetic_dynamic:
        # 固定合成输入只用于EXE端到端演示；与用户项目库隔离。
        try:
            from examples.synthetic_dynamic_case import execute as run_synthetic_dynamic
            run_synthetic_dynamic(args.batch_synthetic_dynamic)
        except Exception:
            import traceback
            args.batch_synthetic_dynamic.mkdir(parents=True, exist_ok=True)
            (args.batch_synthetic_dynamic / "batch_error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
    elif args.batch_network_source:
        from power_ga.operation_simulation.network_case import run_network_case

        output = (args.batch_network_output or user_folder().parent / "GRIDMIND_results" /
                  f"network_{datetime.now():%Y%m%d_%H%M%S}")
        try:
            run_network_case(args.batch_network_source, output,
                             solver=args.batch_network_solver)
        except Exception as error:
            import traceback
            output.mkdir(parents=True, exist_ok=True)
            # 冻结包缺依赖时保留完整调用栈，便于精确定位而不暴露输入内容。
            (output / "batch_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
    elif args.batch_source:
        # 同一EXE的后台入口用于无人值守复核；计算仍走前后端共享的execute。
        # 失败写入本次结果目录并返回非零状态，不弹出PyInstaller错误窗口。
        from project_main import execute
        output = (args.batch_output or user_folder().parent / "GRIDMIND_results" /
                  f"scenario_{args.batch_year}_{datetime.now():%Y%m%d_%H%M%S}")
        try:
            execute(args.batch_source, args.batch_year,
                    args.batch_costs or prepare_cost_file(), output,
                    plan=not args.batch_simulate_only,
                    figures=not args.batch_skip_figures,
                    algorithm=args.batch_algorithm,
                    population=args.batch_population,
                    generations=args.batch_generations,
                    seed=args.batch_seed,
                    previous_load_factor=args.batch_previous_load_factor,
                    stage_input_mode=args.batch_stage_input_mode,
                    planning_horizon=args.batch_planning_horizon,
                    figure_backend=(default_figure_backend()
                                    if args.batch_figure_backend == "auto" else
                                    args.batch_figure_backend))
        except Exception as error:
            output.mkdir(parents=True, exist_ok=True)
            (output / "batch_error.txt").write_text(str(error), encoding="utf-8")
            raise SystemExit(1)
    elif args.render_project_python:
        from power_ga.result_output.python_plot import render_project_archive_python

        try:
            render_project_archive_python(args.render_project_python,
                                          figure_folder="figures_python")
        except Exception:
            # 无控制台EXE也要把失败原因留下，便于定位缺字体/缺表/冻结导入问题。
            import traceback

            (args.render_project_python / "figure_render_error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
    elif args.export_monthly_views:
        # 月图与交互窗口共用绘制和事件选取，输出表按相同小时边界存档。
        from power_ga.result_output.viewer import export_monthly_views, load_hours

        result_dir, image_dir = args.export_monthly_views
        export_monthly_views(load_hours(result_dir), image_dir)
    elif args.export_network_views:
        from power_ga.result_output.viewer import export_predefined_views, load_network_hours

        result_dir, zone, image_dir = args.export_network_views
        export_predefined_views(load_network_hours(Path(result_dir), zone), Path(image_dir))
    elif args.export_demo_views:
        # 接受任意完整8760小时结果；公开演示仅选用单独生成的合成算例。
        from power_ga.result_output.viewer import export_predefined_views, load_hours

        result_dir, image_dir = args.export_demo_views
        export_predefined_views(load_hours(result_dir), image_dir)
    elif args.network_viewer:
        from power_ga.result_output.viewer import launch, load_network_views

        folder, zone = args.network_viewer
        views = load_network_views(Path(folder))
        launch(views[zone], zone_options=views, initial_zone=zone)
    elif args.network_viewer_smoke:
        # 冻结包后台验收：创建全网图、切到分区并打开框选浮窗。
        from power_ga.result_output.viewer import launch, load_network_views

        views = load_network_views(args.network_viewer_smoke)
        launch(views["全网汇总"], zone_options=views,
               initial_zone="全网汇总", smoke=True)
    elif args.viewer:
        from power_ga.result_output.viewer import launch, load_hours, load_network_views
        import matplotlib
        matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        # 直接调用--viewer时也按存档内容识别分区表；图窗内部始终可更换存档。
        if (args.viewer / "tables" / "hourly_network.csv").is_file():
            views = load_network_views(args.viewer)
            launch(views["全网汇总"], zone_options=views, initial_zone="全网汇总")
        else:
            launch(load_hours(args.viewer), result_dir=args.viewer)
    elif args.viewer_switch_smoke:
        # 后台模拟用户从截图所示单区窗口载入分区存档，再切换区域。
        from power_ga.result_output.viewer import launch, load_hours
        single, network = args.viewer_switch_smoke
        launch(load_hours(single), smoke=True, smoke_network_dir=network,
               result_dir=single)
    elif args.viewer_smoke:
        # 冻结包也要创建真实Tk画布和框选浮窗，再后台销毁，不打扰桌面。
        from power_ga.result_output.viewer import launch, load_hours
        launch(load_hours(args.viewer_smoke), smoke=True,
               result_dir=args.viewer_smoke)
    elif args.ga:
        show_ga_window(args.ga)
    elif args.dp:
        show_dp_window(args.dp)
    else:
        launch_app(args.smoke_test)


if __name__ == "__main__":
    main()
