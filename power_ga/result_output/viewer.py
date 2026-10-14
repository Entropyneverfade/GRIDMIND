"""全年运行结果交互查看窗口：在同一堆叠图浏览出力与储能充放。

启动：python -m power_ga.result_output.viewer --result output
数据直接读取结果目录tables内的hourly_dispatch.csv或hourly_network.csv，
可在同一窗口换用另一份分区存档，不重新模拟或改写结果。
"""

import argparse
import csv
import json
import math
import re
from pathlib import Path

from ..common.domain import PLANNING_MONTH_HOURS
from ..data_collection.project_case import database_regions

# 配色与Origin静态图共用主色；交互窗口及无Origin的静态后端均用Python绘制。
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
ALL_ZONES_LABEL = "全网汇总"
SINGLE_ZONE_LABEL = "当前单区结果"
PENDING_ZONE_SUFFIX = "（未生成分区逐时结果）"

# 框选统计只列数据实际包含的字段；分区案例的附加机组类型也逐项显示。
GENERATION_LABELS = (("coal_mw", "煤电"), ("gas_mw", "燃气"),
                     ("nuclear_mw", "核电"), ("hydro_mw", "常规水电"),
                     ("biomass_mw", "生物质"), ("csp_mw", "光热"),
                     ("oil_mw", "燃油"), ("geothermal_mw", "地热"),
                     ("solar_mw", "光伏"), ("wind_mw", "风电"))


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


def archive_database_regions(result_dir: Path):
    """沿运行清单回读输入库的系统表；缺源时不猜测数据库分区。"""
    manifest_path = Path(result_dir) / "run_manifest.json"
    if not manifest_path.is_file():
        return ()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    source = manifest.get("source_folder")
    if not isinstance(source, str) or not source:
        return ()
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = manifest_path.parent / source_path
    if not source_path.exists():
        return ()
    return database_regions(source_path, manifest.get("target_year"))


def load_network_zones(result_dir: Path, *, selected=None, expected_hours=8760):
    """一次读取分区逐时存档；每个分区保留独立的8760小时曲线。"""
    path = Path(result_dir) / "tables" / "hourly_network.csv"
    technologies = ("coal", "gas", "hydro", "biomass", "nuclear", "csp",
                    "oil", "geothermal")
    required = ("hour", "zone", "demand_mw",
                *(f"{technology}_mw" for technology in technologies),
                "wind_mw", "solar_mw", "imports_mw", "exports_mw",
                "pumped_charge_mw", "pumped_discharge_mw", "battery_charge_mw",
                "battery_discharge_mw", "wind_curtailment_mw",
                "solar_curtailment_mw", "unserved_mw", "spill_mw")
    zones = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(required).issubset(reader.fieldnames or ()):
            raise ValueError("分区逐时表缺少运行图字段")
        for row in reader:
            zone_name = row["zone"]
            if selected is not None and zone_name != selected:
                continue
            hours = zones.setdefault(zone_name, [])
            if int(row["hour"]) != len(hours):
                raise ValueError(f"分区{zone_name}逐时序列断号或重复")
            demand, outgoing = float(row["demand_mw"]), float(row["exports_mw"])
            pumped_charge, battery_charge = (float(row["pumped_charge_mw"]),
                                               float(row["battery_charge_mw"]))
            pumped_discharge, battery_discharge = (float(row["pumped_discharge_mw"]),
                                                     float(row["battery_discharge_mw"]))
            hours.append({"load_mw": demand + outgoing,
                          "domestic_load_mw": demand, "export_mw": outgoing,
                          **{f"{technology}_mw": float(row[f"{technology}_mw"])
                             for technology in technologies},
                          "imports_mw": float(row["imports_mw"]),
                          "wind_mw": float(row["wind_mw"]),
                          "solar_mw": float(row["solar_mw"]),
                          "pumped_charge_mw": pumped_charge,
                          "pumped_discharge_mw": pumped_discharge,
                          "battery_charge_mw": battery_charge,
                          "battery_discharge_mw": battery_discharge,
                          "storage_charge_mw": pumped_charge + battery_charge,
                          "storage_discharge_mw": pumped_discharge + battery_discharge,
                          "storage_energy_end_mwh": 0.0,
                          "wind_curtailment_mw": float(row["wind_curtailment_mw"]),
                          "solar_curtailment_mw": float(row["solar_curtailment_mw"]),
                          "unserved_mw": float(row["unserved_mw"]),
                          "overgeneration_mw": float(row["spill_mw"])})
    if not zones:
        raise ValueError(f"分区逐时表没有找到分区：{selected or path}")
    for zone_name, hours in zones.items():
        if len(hours) != expected_hours:
            raise ValueError(f"分区查看窗口需要{expected_hours}小时，{zone_name}只有{len(hours)}小时")
    return zones


def load_network_hours(result_dir: Path, zone_name: str):
    """兼容单区静态图入口，只读取指定分区的逐时数据。"""
    return load_network_zones(result_dir, selected=zone_name)[zone_name]


def aggregate_network_zones(zones):
    """将区域图合成全网图；区内互济在全网边界处相互抵消。"""
    if not zones:
        raise ValueError("全网汇总至少需要一个分区")
    lengths = {len(hours) for hours in zones.values()}
    if len(lengths) != 1:
        raise ValueError("分区小时数不一致，不能汇总")
    size = lengths.pop()
    fields = tuple(next(iter(zones.values()))[0])
    aggregate = []
    for hour in range(size):
        parts = [rows[hour] for rows in zones.values()]
        incoming = sum(part["imports_mw"] for part in parts)
        outgoing = sum(part["export_mw"] for part in parts)
        if abs(incoming - outgoing) > 1e-5:
            raise ValueError(f"第{hour}小时全网交换不守恒，不能绘制汇总图")
        # 全网内部联络交换两端相抵：总需求只取Σ本地负荷，进口/出口都归零。
        total = {field: sum(part[field] for part in parts) for field in fields}
        total["load_mw"] = total["domestic_load_mw"]
        total["imports_mw"] = total["export_mw"] = 0.0
        aggregate.append(total)
    return aggregate


def load_network_views(result_dir: Path):
    """为单窗口准备全网和各分区曲线，切换时无需重复读取CSV。"""
    zones = load_network_zones(result_dir)
    if ALL_ZONES_LABEL in zones:
        raise ValueError("分区名称“全网汇总”为查看器保留名称")
    return {ALL_ZONES_LABEL: aggregate_network_zones(zones), **zones}


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


def planning_date_label(hour: int, *, with_time=False):
    """把小时序号映射为365日规划年的月/日；闰年也不插入2月29日。"""
    if not 0 <= hour <= 8760:
        raise ValueError("日期刻度必须位于全年小时0–8760")
    if hour == 8760:
        return "翌年1/1 00:00" if with_time else "翌年1/1"
    day, clock = divmod(hour, 24)
    for month, month_hours in enumerate(MONTH_HOURS, 1):
        days = month_hours // 24
        if day < days:
            label = f"{month}/{day + 1}"
            return f"{label} {clock:02d}:00" if with_time else label
        day -= days
    raise AssertionError("规划年月小时数未合计8760")


def date_axis_ticks(start: int, end: int):
    """每天零点提供日期刻度；宽窗口抽稀文字，显示端点仍有真刻度。"""
    if not 0 <= start < end <= 8760:
        raise ValueError("日期横轴小时范围必须位于0–8760")
    span = end - start
    if span <= 24:
        # 单日图保留6小时细分；午夜标日期，其余刻度标时刻。
        inner = range(((start // 6) + 1) * 6, end, 6)
    elif span >= 180 * 24:
        # 半年及全年图采用自然月首日，避免“每30天”在月界漂移。
        month_starts = [sum(MONTH_HOURS[:index]) for index in range(13)]
        inner = (hour for hour in month_starts if start < hour < end)
    else:
        days = span / 24
        stride = 1 if days <= 10 else max(1, math.ceil(days / 12))
        inner = range(((start // 24 // stride) + 1) * stride * 24,
                      end, stride * 24)
    ticks = sorted({start, end, *inner})
    labels = []
    for hour in ticks:
        if hour % 24 == 0:
            labels.append(planning_date_label(hour, with_time=span <= 24))
        elif span <= 24 and hour not in (start, end):
            labels.append(f"{hour % 24:02d}:00")
        else:
            labels.append(planning_date_label(hour, with_time=True))
    return ticks, labels


def zoom_hour_bounds(start: int, end: int, center: float, wheel_steps: float):
    """Ctrl滚轮以鼠标位置为锚点缩放，边界限定在全年并保留整数小时。"""
    if not 0 <= start < end <= 8760 or not math.isfinite(center):
        raise ValueError("缩放中心或当前小时范围无效")
    span = end - start
    factor = 0.75 ** max(-4.0, min(4.0, wheel_steps))
    width = max(1, min(8760, int(round(span * factor))))
    anchor = max(0.0, min(1.0, (center - start) / span))
    left = max(0, min(8760 - width, int(round(center - anchor * width))))
    return left, left + width


def selected_hour_bounds(xmin: float, xmax: float, visible_start: int, visible_end: int):
    """把鼠标拖拽的连续x坐标映射到与所覆盖小时相交的左闭右开区间。"""
    if not math.isfinite(xmin) or not math.isfinite(xmax):
        raise ValueError("框选坐标必须为有限小时数")
    # 小时h代表[h,h+1)；拖到边界两侧时用floor/ceil收纳所有被框触及的小时。
    start = max(visible_start, min(visible_end - 1, math.floor(min(xmin, xmax))))
    end = max(start + 1, min(visible_end, math.ceil(max(xmin, xmax))))
    return start, end


def summarize_selected_hours(hours, start: int, end: int):
    """从已存档逐时值计算框选电量，输出按供给、弃电、储能、需求分组的表行。"""
    if not 0 <= start < end <= len(hours):
        raise ValueError("框选小时区间超出逐时数据")
    part, count = hours[start:end], end - start
    sample = part[0]

    def total(field):
        # 时间步长固定1h：E[MWh]=Σ_t P_t[MW]×1h；平均功率=E/框选小时数。
        return sum(row[field] for row in part)

    generation = []
    if "coal_mw" not in sample and "thermal_mw" in sample:
        generation.append(("火电", total("thermal_mw")))
    generation.extend((label, total(field)) for field, label in GENERATION_LABELS
                      if field in sample)
    if "pumped_discharge_mw" in sample:
        discharge = [("抽蓄放电", total("pumped_discharge_mw")),
                     ("电池放电", total("battery_discharge_mw"))]
        charge = [("抽蓄充电", total("pumped_charge_mw")),
                  ("电池充电", total("battery_charge_mw"))]
    else:
        discharge = [("储能放电", total("storage_discharge_mw"))]
        charge = [("储能充电", total("storage_charge_mw"))]
    # 进口属于供给但不是本区发电，故单独列在“跨区”而不并入发电小计。
    transfer = [("区外来电", total("imports_mw"))] if "imports_mw" in sample else []
    if "export_mw" in sample:
        transfer.append(("外送", total("export_mw")))
    demand = ([('本地负荷', total('domestic_load_mw'))]
              if 'domestic_load_mw' in sample else [])
    demand.append(("总需求（含外送）", total("load_mw")))
    curtailment = [("弃风", total("wind_curtailment_mw")),
                   ("弃光", total("solar_curtailment_mw"))]
    other = [("缺供", total("unserved_mw")),
             ("未消纳过剩", total("overgeneration_mw"))]
    # 用归档值独立核对选段电量平衡；弃电是未发出的可用量，不参加供需相加。
    residual = (sum(value for _, value in generation + discharge) +
                sum(value for label, value in transfer if label == "区外来电") +
                total("unserved_mw") - total("load_mw") -
                sum(value for _, value in charge) - total("overgeneration_mw"))
    return {"start": start, "end": end, "hours": count, "generation": generation,
            "curtailment": curtailment, "storage": discharge + charge,
            "transfer": transfer, "demand": demand, "other": other,
            "balance_residual_mwh": residual}


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
    if "imports_mw" in part[0]:
        # 分区平衡把进口作为独立供给，出口并入洋红总需求线。
        series = (("coal_mw", "煤电", COLORS["thermal"], None),
                  ("gas_mw", "燃气", "#E46C0A", None),
                  ("nuclear_mw", "核电", "#9966CC", None),
                  ("hydro_mw", "常规水电", "#22B8D6", None),
                  ("biomass_mw", "生物质", "#A56A42", None),
                  ("csp_mw", "光热", "#D7A31A", None),
                  ("oil_mw", "燃油", "#7F7F7F", None),
                  ("geothermal_mw", "地热", "#7C9A4B", None),
                  ("pumped_discharge_mw", "抽蓄放电", "#154AAB", None),
                  ("battery_discharge_mw", "电池放电", "#526CFF", None),
                  ("imports_mw", "区外来电", "#8064A2", None),
                  ("solar_mw", "光伏", COLORS["solar"], None),
                  ("wind_mw", "风电", COLORS["wind"], None),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], "//"),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], "\\\\"))
    elif "coal_mw" in part[0]:
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
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], "\\\\"))
    else:
        series = (("thermal_mw", "火电", COLORS["thermal"], None),
                  ("storage_discharge_mw", "储能放电", COLORS["storage"], None),
                  ("solar_mw", "光伏", COLORS["solar"], None),
                  ("wind_mw", "风电", COLORS["wind"], None),
                  ("unserved_mw", "缺供", COLORS["unserved"], "xx"),
                  ("solar_curtailment_mw", "弃光", COLORS["solar"], "//"),
                  ("wind_curtailment_mw", "弃风", COLORS["wind"], "\\\\"))
    for field, label, color, hatch in series:
        values = [h[field] for h in part]
        upper = [a + b for a, b in zip(base, values)]
        if max(values) > 1e-8:
            # 普通电源不画每小时多边形黑边；黑边叠加会把高密度堆叠图压成灰色。
            # 弃电才保留与其电源同色的纹理，小时数据并未降采样。
            hatch_color = ("#005D00" if field == "wind_curtailment_mw" else
                           "#806A00" if field == "solar_curtailment_mw" else "#555555")
            # 风、光分别用反向密斜线；8条基纹比先前4条在缩略图更容易辨别。
            style = ({"edgecolor": hatch_color, "linewidth": 0.65, "hatch": hatch * 4}
                     if hatch else {"edgecolor": "none", "linewidth": 0.0})
            patch = top.fill_between(x, _step(base), _step(upper), step="post", label=label,
                                     facecolor=color, alpha=1.0, **style)
            if hatch and hasattr(patch, "set_hatch_linewidth"):
                # 描线加粗只改变视觉纹理，不扩大真实弃电功率面积。
                patch.set_hatch_linewidth(1.25)
        base = upper
    charge = [h["storage_charge_mw"] for h in part]
    if "pumped_charge_mw" in part[0]:
        # 负向充电也逐技术堆叠，抽蓄和电池不混合为一条色块。
        negative_base = [0.0] * len(part)
        for field, label, color in (("pumped_charge_mw", "抽蓄充电（负向）", "#154AAB"),
                                    ("battery_charge_mw", "电池充电（负向）", "#526CFF")):
            values = [h[field] for h in part]
            lower = [base - value for base, value in zip(negative_base, values)]
            if max(values) > 1e-8:
                top.fill_between(x, _step(lower), _step(negative_base), step="post",
                                 label=label, facecolor=color, edgecolor="none", linewidth=0)
            negative_base = lower
    elif max(charge) > 1e-8:
        top.fill_between(x, _step([-v for v in charge]), 0, step="post", label="储能充电（负向）",
                         facecolor=COLORS["charge"], edgecolor="none", linewidth=0)
    top.step(x, _step([h["load_mw"] for h in part]), where="post", label="原始负荷",
             color=COLORS["load"], linewidth=2.6, zorder=12)
    if "export_mw" in part[0]:
        # 洋红为本地负荷+外送；本地负荷另画虚线，可核对外送贡献。
        top.step(x, _step([h["domestic_load_mw"] for h in part]), where="post",
                 label="本地负荷", color="#803080", linestyle="--", linewidth=0.8)
    # 只保留约6个纵轴主刻度；先计算可见上界，再固定Locator以阻止旧窗口的刻度累积。
    from matplotlib.ticker import FixedLocator, FuncFormatter
    raw_span = max(max(base), max(h["load_mw"] for h in part)) + max(charge)
    target_step = max(1.0, raw_span / 6.0)
    magnitude = 10 ** math.floor(math.log10(target_step))
    tick_step = next(multiplier * magnitude for multiplier in (1, 2, 5, 10)
                     if multiplier * magnitude >= target_step)
    ymax = max(tick_step, math.ceil(max(max(base), max(h["load_mw"] for h in part)) / tick_step) * tick_step)
    # 充电通常远小于总出力；负轴按实际充电量留边，不向下空出整档主刻度。
    ymin = (-max(5.0, math.ceil(max(charge) * 1.15 / 5.0) * 5.0)
            if max(charge) > 1e-8 else 0.0)
    top.set_ylim(ymin, ymax)
    y_ticks = ([ymin] if ymin < 0 else []) + [index * tick_step
               for index in range(int(round(ymax / tick_step)) + 1)]
    top.yaxis.set_major_locator(FixedLocator(y_ticks))
    top.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    top.minorticks_off()
    top.set_ylabel("功率 / MW")
    top.grid(axis="y", color="#D7DEE8", alpha=0.65, linewidth=0.6)
    if end - start <= 168:
        # 周及更短窗口内，1小时弃电面积可能仅占数个像素；标注最多两次主要
        # 弃电小时的真实MW，文字只是定位提示，不改变面积或纵轴数量尺度。
        active = sorted((i for i, hour in enumerate(part)
                         if hour["wind_curtailment_mw"] + hour["solar_curtailment_mw"] > 1e-6),
                        key=lambda i: part[i]["wind_curtailment_mw"] +
                        part[i]["solar_curtailment_mw"], reverse=True)
        marked = []
        for i in active:
            if len(marked) >= 2:
                break
            if all(abs(i - earlier) >= 12 for earlier in marked):
                hour = part[i]
                label = (f'弃风 {hour["wind_curtailment_mw"]:.2f} MW\n'
                         f'弃光 {hour["solar_curtailment_mw"]:.2f} MW')
                top.annotate(label, xy=(start + i + 0.5, base[i]),
                             xytext=(start + i + 0.5, ymax * 0.94),
                             ha="center", va="top", fontsize=8.5, color="#303846",
                             arrowprops={"arrowstyle": "-", "color": "#303846",
                                         "linewidth": 0.75},
                             bbox={"facecolor": "white", "alpha": 0.92,
                                   "edgecolor": "#C3CBD5", "boxstyle": "round,pad=0.25"},
                             zorder=16)
                marked.append(i)
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
    top.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=6, fontsize=8,
               frameon=False, handlelength=1.8, columnspacing=1.2)

    # 上方同一坐标轴已经把充电画成负面积、放电画成正出力；库存保留在逐时表。
    top.set_xlabel("日期 / 时间（365日规划年）")
    top.set_xlim(start, end)
    # 日期位置锚定每天00:00；日图显示时刻，宽窗口减少日期文字以免重叠。
    ticks, labels = date_axis_ticks(start, end)
    top.set_xticks(ticks, labels=labels)
    top.tick_params(direction="in", which="both", top=False, right=False,
                    length=5, width=0.8, colors="#303846")
    top.spines[["top", "right"]].set_visible(False)
    top.spines[["left", "bottom"]].set_color("#303846")
    fig.subplots_adjust(left=0.10, right=0.975,
                        top=0.81 if "export_mw" in part[0] else 0.84, bottom=0.10)
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


def launch(hours, smoke=False, zone_options=None, initial_zone=None,
           smoke_network_dir=None, result_dir=None):
    """建立交互窗口；任何结果都可在此窗口载入分区存档并切换区域。"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import matplotlib
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    from matplotlib.widgets import SpanSelector

    # 独立EXE子窗口也设置中文字体，避免分区名称和图例显示为方框。
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    # 先把单区存档也包装为一个可选视图：图窗始终展示分区控件。
    # 单区逐时表没有其他分区，必须由用户载入含hourly_network.csv的存档。
    network_mode = zone_options is not None
    catalog_error = ""
    try:
        catalog = archive_database_regions(result_dir) if not network_mode and result_dir else ()
    except (OSError, ValueError, KeyError) as error:
        # 元数据错误不阻断现有8760曲线；图窗仍可手动选择有效分区存档。
        catalog, catalog_error = (), f"数据库分区读取失败：{error}"
    single_name = catalog[0] if len(catalog) == 1 else SINGLE_ZONE_LABEL
    views = dict(zone_options) if network_mode else {single_name: hours}
    # 多区输入却只有汇总小时表时展示区域名称，但不冒用汇总曲线充当区内曲线。
    pending_names = tuple(f"{name}{PENDING_ZONE_SUFFIX}" for name in catalog)
    if not network_mode and len(catalog) <= 1:
        pending_names = ()
    if not views:
        raise ValueError("查看窗口至少需要一组逐时曲线")
    initial_zone = initial_zone or next(iter(views))
    if initial_zone not in views:
        raise ValueError(f"查看器没有分区：{initial_zone}")
    hours = views[initial_zone]
    root = tk.Tk()
    if smoke:
        root.withdraw()  # 后台验证Tk画布，不抢用户前台窗口。
    root.title("源网荷储8760小时运行图" if network_mode else "源荷储8760小时运行图")
    root.geometry("1380x820")
    zone_choice = tk.StringVar(value=initial_zone or "")
    last_valid_zone = initial_zone
    # 分区控件放在图窗顶部；单区结果也能直接载入另一份分区存档，不返回主窗口。
    zone_bar = ttk.Frame(root, padding=(7, 7, 7, 0))
    zone_bar.pack(side="top", fill="x")
    ttk.Label(zone_bar, text="显示分区").pack(side="left")
    zone_select = ttk.Combobox(zone_bar, textvariable=zone_choice,
                               values=(*views, *pending_names), state="readonly", width=30)
    zone_select.pack(side="left", padx=(5, 12))
    zone_note = tk.StringVar(value=("选择分区可查看逐时互济；全网汇总抵消内部交换"
                                    if network_mode else
                                    f"数据库识别{len(catalog)}区；本次只有汇总逐时结果"
                                    if pending_names else
                                    "已按数据库系统表自动识别单区；可载入其他分区结果"
                                    if catalog else catalog_error or
                                    "当前存档只有单区逐时表；可在这里载入分区结果"))
    ttk.Label(zone_bar, textvariable=zone_note, foreground="#46556A").pack(side="left", padx=8)
    controls = ttk.Frame(root, padding=7)
    controls.pack(side="top", fill="x")
    scale = tk.StringVar(value="日")
    number = tk.StringVar(value="1")
    start_text, end_text = tk.StringVar(value="0"), tk.StringVar(value="24")
    status = tk.StringVar(value="数据：8760小时；窗口按小时序号定位")
    displayed = None  # 相同窗口不重建上万个面积顶点，减少重复点击引起的卡顿。
    selector = None  # Matplotlib选择器须保持引用，切图时解绑旧坐标轴事件。
    selection_popup = None
    selection_patch = None
    ttk.Label(controls, text="尺度").pack(side="left")
    ttk.Combobox(controls, textvariable=scale, values=("日", "周", "月", "年", "自定义"),
                 width=8, state="readonly").pack(side="left", padx=4)
    ttk.Label(controls, text="第几日/周/月").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=number, width=6).pack(side="left", padx=4)
    ttk.Label(controls, text="起始小时").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=start_text, width=7).pack(side="left", padx=4)
    ttk.Label(controls, text="结束小时（不含）").pack(side="left", padx=(10, 0))
    ttk.Entry(controls, textvariable=end_text, width=7).pack(side="left", padx=4)
    ttk.Label(controls, text="左键框选统计 · Ctrl+滚轮缩放").pack(side="left", padx=(12, 0))
    fig = Figure(figsize=(13, 7), dpi=100)
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    toolbar = NavigationToolbar2Tk(canvas, root, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="bottom", fill="x")

    def close_selection_popup():
        """切图或关闭统计窗时释放旧窗口，避免堆积遮挡主图。"""
        nonlocal selection_popup
        if selection_popup is not None and selection_popup.winfo_exists():
            selection_popup.destroy()
        selection_popup = None

    def show_selection(xmin, xmax):
        """鼠标松开后按整数小时汇总，并在指针附近显示非模态统计浮窗。"""
        nonlocal selection_popup, selection_patch
        if toolbar.mode or displayed is None:
            return  # 工具栏平移/缩放优先，避免同一次鼠标动作触发两种模式。
        first, last = selected_hour_bounds(xmin, xmax, displayed[0], displayed[1])
        report = summarize_selected_hours(hours, first, last)
        close_selection_popup()
        if selection_patch is not None:
            selection_patch.remove()
        # 淡蓝色范围只用于定位；数值始终来自原始逐时表而不是图上像素。
        selection_patch = fig.axes[0].axvspan(first, last, color="#2466B3",
                                              alpha=0.13, zorder=10)
        canvas.draw_idle()
        popup = tk.Toplevel(root)
        selection_popup = popup
        popup.title(f"{zone_choice.get()} · 时段统计 · 小时 {first}–{last - 1}")
        popup.transient(root)
        popup.protocol("WM_DELETE_WINDOW", close_selection_popup)
        if smoke:
            popup.withdraw()  # 后台GUI验收不抢占用户前台窗口。
        heading = ttk.Frame(popup, padding=(12, 10))
        heading.pack(fill="x")
        ttk.Label(heading, text=f"{zone_choice.get()} · 全年小时 {first}–{last - 1}  ·  共 {report['hours']} 小时",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(heading, text="电量 = 逐小时功率 × 1 h；平均功率 = 时段电量 ÷ 小时数",
                  foreground="#46556A").pack(anchor="w", pady=(3, 0))
        table_frame = ttk.Frame(popup, padding=(12, 0, 12, 7))
        table_frame.pack(fill="both", expand=True)
        table = ttk.Treeview(table_frame, columns=("energy", "average"), show="tree headings",
                             height=20)
        table.heading("#0", text="项目")
        table.heading("energy", text="时段电量 / MWh")
        table.heading("average", text="平均功率 / MW")
        table.column("#0", width=185, stretch=True)
        table.column("energy", width=135, anchor="e", stretch=False)
        table.column("average", width=125, anchor="e", stretch=False)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for key, title in (("generation", "各类机组发电"),
                           ("curtailment", "弃电"), ("storage", "储能充放电"),
                           ("transfer", "跨区交换"), ("demand", "负荷"),
                           ("other", "缺供与过剩")):
            rows = report[key]
            if not rows:
                continue
            parent = table.insert("", "end", text=title, open=True)
            for label, energy in rows:
                table.insert(parent, "end", text=label,
                             values=(f"{energy:,.3f}", f"{energy / report['hours']:,.3f}"))
        ttk.Label(popup, text=f"时段功率平衡残差：{report['balance_residual_mwh']:.6g} MWh",
                  padding=(12, 0, 12, 10), foreground="#46556A").pack(anchor="w")
        popup.update_idletasks()
        width, height = 510, min(690, popup.winfo_reqheight())
        x = min(root.winfo_pointerx() + 18, root.winfo_screenwidth() - width - 12)
        y = min(root.winfo_pointery() + 18, root.winfo_screenheight() - height - 50)
        popup.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        if not smoke:
            popup.lift(root)
        status.set(f"已框选全年小时 {first}–{last - 1}，共 {report['hours']} 小时；详见统计浮窗")

    def redraw(a, b):
        """应用左闭右开区间，刷新供给、弃电、充电同图的单张堆叠视图。"""
        nonlocal displayed, selector, selection_patch
        try:
            a, b = int(a), int(b)
            period_label = (f"第{number.get()}{scale.get()}" if scale.get() in {"日", "周", "月"}
                            else "全年8760小时" if scale.get() == "年" else f"自定义小时 {a}–{b - 1}")
            view_label = (f"{zone_choice.get()} · {period_label}"
                          if network_mode or catalog else period_label)
            state = (a, b, view_label, scale.get() == "月")
            if state != displayed:
                close_selection_popup()
                if selector is not None:
                    selector.disconnect_events()
                draw_view(fig, hours, a, b, view_label, mark_month_events=state[3])
                selection_patch = None
                # 每次切图后的Axes是新对象；选择器须绑定新Axes并保持引用。
                selector = SpanSelector(fig.axes[0], show_selection, "horizontal",
                                        useblit=True, button=1, minspan=0.05,
                                        props={"facecolor": "#2466B3", "alpha": 0.25})
                displayed = state
                canvas.draw_idle()
            start_text.set(str(a))
            end_text.set(str(b))
            region = f"{zone_choice.get()}；"
            status.set(f"当前窗口：{region}全年小时 {a}–{b - 1}，共 {b - a} 小时")
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

    def switch_region(_event=None):
        """保留当前小时区间，在缓存曲线中换区并重建选择器和图例。"""
        nonlocal hours, last_valid_zone
        name = zone_choice.get()
        if name not in views:
            zone_choice.set(last_valid_zone)
            messagebox.showinfo("尚无该区运行曲线",
                                "数据库系统表定义了该分区，但本次单区存档没有该区8760小时出力。"
                                "请先生成分区运行结果；程序不会复制全网曲线冒充分区数据。",
                                parent=root)
            return
        last_valid_zone = name
        hours = views[name]
        if displayed is not None:
            redraw(displayed[0], displayed[1])

    def activate_network_result(folder):
        """在当前图窗替换为另一份分区逐时存档，沿用已选的小时边界。"""
        nonlocal views, hours, network_mode, pending_names, last_valid_zone
        new_views = load_network_views(Path(folder))
        views, network_mode, pending_names = new_views, True, ()
        zone_select.configure(values=tuple(views))
        zone_choice.set(ALL_ZONES_LABEL)
        last_valid_zone = ALL_ZONES_LABEL
        hours = views[ALL_ZONES_LABEL]
        root.title("源网荷储8760小时运行图")
        zone_note.set("选择分区可查看逐时互济；全网汇总抵消内部交换")
        if displayed is not None:
            redraw(displayed[0], displayed[1])

    def choose_network_result():
        """让用户在同一图窗载入含分区8760小时表的结果目录。"""
        folder = filedialog.askdirectory(parent=root, title="选择分区运行结果存档")
        if folder:
            try:
                activate_network_result(folder)
            except (OSError, ValueError, KeyError) as error:
                messagebox.showerror("分区存档无法打开", str(error), parent=root)

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
        name = re.sub(r'[<>:"/\\|?*]', "_", zone_choice.get())
        a, b = displayed[:2]
        path = filedialog.asksaveasfilename(parent=root, title="保存当前视图", defaultextension=".png",
                                            initialfile=f"{name}_hour_{a}_{b - 1}.png",
                                            filetypes=[("PNG图片", "*.png")])
        if path:
            fig.savefig(path, dpi=240, facecolor="white")
            status.set("当前视图已保存：" + path)

    def scroll_zoom(event):
        """仅Ctrl+滚轮缩放鼠标所在小时；普通滚轮和工具栏模式保持原行为。"""
        key = str(getattr(event, "key", "") or "").lower()
        native = getattr(event, "guiEvent", None)
        control_down = ("control" in key or "ctrl" in key or
                        bool(getattr(native, "state", 0) & 0x0004))
        if not control_down or toolbar.mode or displayed is None or event.inaxes not in fig.axes:
            return
        first, last = displayed[:2]
        center = event.xdata if event.xdata is not None else (first + last) / 2
        new_first, new_last = zoom_hour_bounds(first, last, center, event.step)
        if (new_first, new_last) != (first, last):
            scale.set("自定义")
            redraw(new_first, new_last)

    ttk.Button(zone_bar, text="载入分区结果…", command=choose_network_result).pack(side="left", padx=4)
    ttk.Button(controls, text="应用尺度", command=apply_scale).pack(side="left", padx=4)
    ttk.Button(controls, text="按小时区间显示", command=lambda: (scale.set("自定义"), apply_scale())).pack(side="left", padx=4)
    ttk.Button(controls, text="前一段", command=lambda: shift(-1)).pack(side="left", padx=4)
    ttk.Button(controls, text="后一段", command=lambda: shift(1)).pack(side="left", padx=4)
    ttk.Button(controls, text="导出当前PNG", command=save_picture).pack(side="left", padx=4)
    zone_select.bind("<<ComboboxSelected>>", switch_region)
    canvas.mpl_connect("scroll_event", scroll_zoom)
    ttk.Label(root, textvariable=status, padding=6).pack(side="bottom", fill="x")
    redraw(0, 24)
    if smoke:
        if catalog and len(catalog) == 1 and zone_choice.get() != catalog[0]:
            raise AssertionError("单区存档未按数据库系统表自动命名")
        if len(zone_select.cget("values")) != len(views) + len(pending_names):
            raise AssertionError("数据库分区目录未自动载入下拉框")
        if smoke_network_dir is not None:
            # 从单区窗口直接载入分区存档，验收用户指出的同窗入口。
            scale.set("自定义")
            redraw(137, 193)
            activate_network_result(smoke_network_dir)
            if displayed[:2] != (137, 193) or len(views) < 2:
                raise AssertionError("同窗载入分区结果后未保留小时范围或分区选项")
        if len(views) > 1:
            # 冻结EXE后台验收要真实切换另一分区，而不只检查初始汇总图。
            zone_choice.set(next(name for name in views if name != zone_choice.get()))
            switch_region()
            if zone_choice.get() not in displayed[2]:
                raise AssertionError("切换分区后图题未随所选分区更新")
        # 无需真实鼠标即可验收组合键、缩放锚点与日历刻度。
        from types import SimpleNamespace
        before = displayed[:2]
        middle = (before[0] + before[1]) / 2
        scroll_zoom(SimpleNamespace(key="", guiEvent=None, inaxes=fig.axes[0],
                                    xdata=middle, step=1))
        if displayed[:2] != before:
            raise AssertionError("普通滚轮不应缩放运行图")
        scroll_zoom(SimpleNamespace(key="control", guiEvent=None, inaxes=fig.axes[0],
                                    xdata=middle, step=1))
        if displayed[1] - displayed[0] >= before[1] - before[0]:
            raise AssertionError("Ctrl+滚轮未缩小显示小时区间")
        # 选中半小时至第三小时，验证统计浮窗、整数边界和Tk控件能后台创建。
        show_selection(0.5, 2.2)
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
        launch(hours, smoke=args.gui_smoke, result_dir=args.result)


if __name__ == "__main__":
    main()
