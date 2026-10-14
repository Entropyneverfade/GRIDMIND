"""项目数据库接入：保留原库，映射机组、电站、曲线和外送约束。"""

import csv
import math
from calendar import isleap
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Tuple

from openpyxl import load_workbook


# 编码来自源表“电站表.类型”；机组表.类型在本库均为0，不能据此分类。
TECHNOLOGIES = {300: "coal", 320: "gas", 373: "hydro", 380: "pumped",
                385: "battery", 390: "wind", 391: "solar", 393: "biomass"}
TECH_LABELS = {"coal": "煤电", "gas": "燃气", "hydro": "常规水电", "pumped": "抽水蓄能",
               "battery": "新型储能", "wind": "风电", "solar": "光伏", "biomass": "生物质"}

# 无有效爬坡/启停字段时使用公开技术基准的试算值；单位为额定MW每小时。
# 2%/min煤电=1.2额定MW/h，5%/min燃气联合循环=3.0额定MW/h。
# 生物质参照常规蒸汽机组仅作试算；水电小时级暂取1.0额定MW/h。
OPERATING_DEFAULTS = {"coal": (1.2, 24, 12), "gas": (3.0, 6, 8),
                      "biomass": (1.2, 24, 12), "hydro": (1.0, 0, 0)}


@dataclass(frozen=True)
class CasePlant:
    """电站级容量，储能时长是 h；曲线是逐小时单位值。"""
    station_id: int
    name: str
    technology: str
    capacity_mw: float
    min_fraction: float
    variable_cost_yuan_per_mwh: float
    annual_cost_yuan: float
    profile: Tuple[float, ...] = ()
    storage_hours: float = 0.0
    charge_ratio: float = 1.0
    roundtrip_efficiency: float = 1.0
    hydro_monthly_factor: Tuple[float, ...] = (1.0,) * 12
    # 以下参数控制常规机组逐时可行域；缺项由导入器写入试算默认值。
    ramp_fraction_per_hour: float = 1.0
    min_up_hours: int = 0
    min_down_hours: int = 0
    max_daily_starts: int = 24
    startup_cost_yuan: float = 0.0
    monthly_max_fraction: Tuple[float, ...] = (1.0,) * 12
    monthly_min_fraction: Tuple[float, ...] = (0.0,) * 12
    monthly_min_online_units: Tuple[int, ...] = (0,) * 12
    planned_maintenance_units: Tuple[int, ...] = (0,) * 12
    unit_count: int = 1
    parameter_source: str = "合成显式参数"


@dataclass(frozen=True)
class ProjectCase:
    """2025存量对比目标年增量的单年规划问题；小时序号0..8759。"""
    base_year: int
    target_year: int
    existing: Tuple[CasePlant, ...]
    candidates: Tuple[CasePlant, ...]
    domestic_load_mw: Tuple[float, ...]
    export_mw: Tuple[float, ...]
    reserve_margin: float
    annual_energy_forecast_gwh: float
    warnings: Tuple[str, ...]
    source_folder: str
    cost_file: str

    @property
    def hours(self):
        """向通用遗传编码器提供候选数量；运行引擎使用原生逐时数组。"""
        return self.domestic_load_mw


def _records(book, sheet):
    """返回非空数据行；该库有重复表头，字段均按已审计列序读取。"""
    return [r for r in list(book[sheet].values)[1:] if r[0] is not None]


def database_regions(source_folder: Path, target_year=None):
    """从原始工作簿的系统/负荷/节点/电站关系识别有实际业务的分区。

    系统0是汇总根；无正负荷也无有效电站的占位系统不作为可选区。
    这里只读取元数据，不把全网逐时曲线复制给每一个分区。
    """
    source = Path(source_folder)
    if source.is_file():
        books = [source] if source.suffix.lower() == ".xlsx" else []
    else:
        year = str(target_year) if target_year is not None else ""
        exact = source / year / f"{year}.xlsx" if year else None
        books = [exact] if exact is not None and exact.is_file() else sorted(source.glob("*.xlsx"))
    if not books:
        return ()
    catalogs = []
    for path in books:
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            required = {"系统表", "负荷表", "节点表", "电站表"}
            if not required.issubset(book.sheetnames):
                raise ValueError(f"输入工作簿缺少分区关系表：{path.name}")

            def records(sheet, columns):
                """按表头而非固定列序抽取字段，兼容同格式工作簿的列位调整。"""
                iterator = book[sheet].iter_rows(values_only=True)
                headers = next(iterator)
                positions = {str(value).strip(): index for index, value in enumerate(headers)
                             if value is not None}
                if not set(columns).issubset(positions):
                    raise ValueError(f"{sheet}缺少分区关联字段")
                for row in iterator:
                    if row and row[0] is not None:
                        yield {name: row[positions[name]] for name in columns}

            systems = [(int(row["系统ID"]), str(row["名称"]).strip())
                       for row in records("系统表", ("系统ID", "名称"))]
            positive_load = {int(row["系统ID"])
                             for row in records("负荷表", ("系统ID", "年Pmax"))
                             if float(row["年Pmax"] or 0) > 0}
            node_system = {int(row["节点ID"]): int(row["系统ID"])
                           for row in records("节点表", ("节点ID", "系统ID"))}
            plant_system = {node_system[int(row["节点ID"])]
                            for row in records("电站表", ("节点ID", "有效性"))
                            if int(row["有效性"] or 0) == 1 and
                            int(row["节点ID"]) in node_system}
            active = positive_load | plant_system
            names = tuple(name for identifier, name in systems
                          if identifier != 0 and identifier in active and name)
            if len(set(names)) != len(names):
                raise ValueError("系统表中有效分区名称重复")
            catalogs.append(names)
        finally:
            book.close()  # 只读句柄及时释放，避免图窗多开时积压工作簿锁。
    if any(names != catalogs[0] for names in catalogs[1:]):
        raise ValueError("同一数据库目录内多个工作簿的分区定义不一致，请指定工作簿")
    return catalogs[0]


def _read_curve(year_folder: Path, name: str, cache: dict):
    """365日×24h展平，禁用插值；闰年校核2月29日是否已省略。"""
    if name in cache:
        return cache[name]
    path = year_folder / "CURVE" / (name + ".xlsx")
    if not path.exists():
        raise FileNotFoundError(f"缺少逐时曲线：{path}")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(book.worksheets[0].values)[1:]
    finally:
        book.close()  # 即使数据无效，也及时释放只读工作簿句柄。
    if year_folder.name.isdecimal() and isleap(int(year_folder.name)):
        year = int(year_folder.name)
        expected = date(year, 1, 1)
        for day, row in enumerate(rows, 1):
            if expected.month == 2 and expected.day == 29:
                expected += timedelta(days=1)  # 8760小时规划年没有闰日。
            label = row[0]
            try:
                if isinstance(label, datetime):
                    actual = label.date()
                elif isinstance(label, date):
                    actual = label
                else:
                    actual = date.fromisoformat(str(label).replace("/", "-"))
            except ValueError as error:
                raise ValueError(f"闰年曲线第{day}日日期标签无效：{path}") from error
            if actual != expected:
                raise ValueError(f"闰年曲线第{day}日应为{expected}，实际为{actual}：{path}")
            expected += timedelta(days=1)
    points = tuple(float(v) for row in rows for v in row[1:25])
    # 负荷、风光、联络线均按“额定MW×逐时单位值”解释；超出1会突破额定功率。
    if len(points) != 8760 or any(not math.isfinite(v) or not 0 <= v <= 1 + 1e-9
                                   for v in points):
        raise ValueError(f"曲线应为8760个0–1范围内的有限单位值：{path}")
    cache[name] = points
    return points


def read_costs(path: Path):
    """核对8类技术费用且拒绝重复行；资本费已年化，不在运行费中重计。"""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"technology", "annual_capital_yuan_per_mw", "variable_yuan_per_mwh"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"成本参数缺少必要列：{sorted(required - set(reader.fieldnames or []))}")
        data = {}
        for line, row in enumerate(reader, 2):
            key = (row["technology"] or "").strip()
            if key not in TECH_LABELS:
                raise ValueError(f"成本参数第{line}行技术类型未知：{key}")
            if key in data:
                raise ValueError(f"成本参数存在重复技术：{key}，第{line}行")
            data[key] = row
    missing = set(TECH_LABELS) - set(data)
    if missing:
        raise ValueError(f"成本参数缺少技术：{sorted(missing)}")
    for key, row in data.items():
        for field in ("annual_capital_yuan_per_mw", "variable_yuan_per_mwh"):
            value = float(row[field])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"成本参数越界：{key}.{field}")
    return data


def _station_units(book):
    """按电站ID连接电站表与机组表，装机=单机容量×有效台数。"""
    stations = {int(r[0]): r for r in _records(book, "电站表")}
    result = {}
    for unit in _records(book, "机组表"):
        station_id = int(unit[3])
        if station_id not in stations or int(unit[2] or 0) != 1:
            continue
        station = stations[station_id]
        if int(station[2] or 0) != 1:
            continue
        kind = int(station[4])
        if kind not in TECHNOLOGIES:
            raise ValueError(f"未映射电站类型 {kind}，电站ID={station_id}")
        mw = float(unit[4] or 0) * float(unit[5] or 0)
        if mw <= 0:
            continue
        if station_id in result:
            raise ValueError(f"电站ID={station_id}存在多个有效机组记录，需补充聚合规则")
        result[station_id] = (station, unit, mw)
    return result


def _hydro_factors(book):
    """水文表中多个情景先取有效、情景编号0；M1..M12是月相对系数。"""
    factors = {}
    for row in _records(book, "水文表"):
        station_id = int(row[3] or 0)
        if int(row[2] or 0) == 1 and int(row[6] or 0) == 0 and station_id not in factors:
            factors[station_id] = tuple(float(x or 0) for x in row[7:19])
    return factors


def _year_applies(encoded, year):
    """有效年份=起始年×100+持续年数；0表示所有年份有效。"""
    value = int(encoded or 0)
    if value == 0:
        return True
    first, count = divmod(value, 100)
    return first <= year < first + count


def _operating_records(book, year):
    """按机组ID收集有效月约束/检修及特性；源表优先于试算默认值。"""
    feature = {int(row[0]): row for row in _records(book, "特性表")}
    limits, maintenance = {}, {}
    for row in _records(book, "机组约束"):
        if int(row[2] or 0) != 1 or not _year_applies(row[4], year):
            continue
        key = (int(row[3]), int(row[5]))
        if key in limits:
            raise ValueError(f"机组{key[0]}月约束类型{key[1]}存在重复有效记录")
        limits[key] = tuple(float(value or 0) for value in row[6:18])
    for row in _records(book, "检修表"):
        if int(row[2] or 0) != 1 or not _year_applies(row[4], year):
            continue
        unit_id = int(row[3])
        if unit_id in maintenance:
            raise ValueError(f"机组{unit_id}存在重复有效检修计划")
        maintenance[unit_id] = tuple(int(value or 0) for value in row[6:18])
    return feature, limits, maintenance


def _make_plant(station_id, record, mw, year_folder, curves, costs, hydro_factors, candidate,
                operating=None):
    """只在储能类型读取效率/时长；风光的“储能比率”是另一物理含义。"""
    station, unit, _ = record
    kind = TECHNOLOGIES[int(station[4])]
    curve_name = station[15]
    profile = _read_curve(year_folder, str(curve_name), curves) if kind in {"wind", "solar"} else ()
    if kind in {"wind", "solar"} and not curve_name:
        raise ValueError(f"风光电站缺少逐时出力曲线：{station[1]}")
    storage_hours = float(unit[8] or 0) if kind in {"pumped", "battery"} else 0.0
    if kind in {"pumped", "battery"} and storage_hours <= 0:
        raise ValueError(f"储能时长必须大于零：{station[1]}")
    efficiency = float(station[8] or 0) if storage_hours else 1.0
    if not 0 < efficiency <= 1:
        raise ValueError(f"储能往返效率越界：{station[1]}")
    charge_ratio = float(station[7]) if storage_hours and station[7] is not None else 1.0
    if not math.isfinite(charge_ratio) or charge_ratio <= 0:
        raise ValueError(f"储能充电功率倍率必须大于零：{station[1]}")
    min_fraction = float(unit[7] or 0) if kind in {"coal", "gas", "biomass"} else 0.0
    if not math.isfinite(min_fraction) or not 0 <= min_fraction <= 1:
        raise ValueError(f"常规机组最小出力比例越界：{station[1]}")
    row = costs[kind]
    plant = CasePlant(station_id, str(station[1]), kind, mw,
                     min_fraction,
                     float(row["variable_yuan_per_mwh"]),
                     mw * float(row["annual_capital_yuan_per_mw"]) if candidate else 0.0,
                     profile, storage_hours,
                     charge_ratio,
                     efficiency, hydro_factors.get(station_id, (1.0,) * 12))
    if kind not in OPERATING_DEFAULTS:
        return plant
    default_ramp, default_up, default_down = OPERATING_DEFAULTS[kind]
    unit_id = int(unit[0] or 0)
    per_unit_mw = float(unit[4] or mw)
    exact_count = mw / per_unit_mw
    count = round(exact_count)
    if count < 1 or abs(exact_count - count) > 1e-7:
        raise ValueError(f"电站{station_id}装机分段不是完整机组台数，不能保证启停可行")
    features, monthly, maintenance = operating or ({}, {}, {})
    source_notes = ["公开技术基准试算"]
    raw_ramp = float(unit[23] or 0) if len(unit) > 23 else 0.0
    # 输入表1.0/min是原软件的“无约束”占位值；有效的0<r<1转换成每小时。
    if 0 < raw_ramp < 1:
        ramp = 60 * raw_ramp
        source_notes.append("机组表有效爬坡率")
    elif raw_ramp in (0, 1):
        ramp = default_ramp
        source_notes.append("爬坡缺项或占位时采用试算默认值")
    else:
        raise ValueError(f"电站{station_id}爬坡率应在[0,1]内")
    up, down, max_starts, startup_cost = default_up, default_down, 1, 0.0
    feature_id = int(unit[10] or 0) if len(unit) > 10 else 0
    if kind == "gas" and feature_id in features:
        row = features[feature_id]
        encoded = int(row[4] or 0)
        if encoded:
            max_starts, rest = divmod(encoded, 10000)
            down, up = divmod(rest, 100)
            if max_starts < 1 or up + down > 24:
                raise ValueError(f"机组{unit_id}启停编码无效")
            source_notes.append("特性表启停时长/次数")
        startup_cost = float(row[5] or 0) * 10000 * count  # 万元/台次→元/站次。
    max_month = monthly.get((unit_id, 0), (1.0,) * 12)
    min_month = monthly.get((unit_id, 1), (0.0,) * 12)
    online_month = monthly.get((unit_id, 2), (0.0,) * 12)
    repair_month = maintenance.get(unit_id, (0,) * 12)
    if any(not 0 <= lo <= hi <= 1 for lo, hi in zip(min_month, max_month)):
        raise ValueError(f"机组{unit_id}逐月最大/最小出力率冲突")
    if any(value < 0 or value > count for value in repair_month):
        raise ValueError(f"机组{unit_id}检修台数越界")
    if any(value < 0 or value > count or value != int(value) for value in online_month):
        raise ValueError(f"机组{unit_id}月最小开机台数越界")
    if (unit_id, 0) in monthly or (unit_id, 1) in monthly or (unit_id, 2) in monthly:
        source_notes.append("机组约束逐月值")
    if unit_id in maintenance:
        source_notes.append("检修表逐月台数")
    return replace(plant, ramp_fraction_per_hour=ramp, min_up_hours=up,
                   min_down_hours=down, max_daily_starts=max_starts,
                   startup_cost_yuan=startup_cost,
                   monthly_max_fraction=tuple(max_month), monthly_min_fraction=tuple(min_month),
                   monthly_min_online_units=tuple(map(int, online_month)),
                   planned_maintenance_units=tuple(repair_month), unit_count=count,
                   parameter_source="；".join(source_notes))


def load_project_case(source_folder: Path, target_year: int, cost_path: Path) -> ProjectCase:
    """读取五年项目库，基年有效容量为存量，目标年差额构成GA候选。"""
    source_folder, cost_path = source_folder.resolve(), cost_path.resolve()
    base_year = 2025
    if target_year not in range(2025, 2030):
        raise ValueError("当前项目数据库仅覆盖2025–2029")
    costs = read_costs(cost_path)
    base_path = source_folder / str(base_year) / f"{base_year}.xlsx"
    target_folder = source_folder / str(target_year)
    target_path = target_folder / f"{target_year}.xlsx"
    base_book = load_workbook(base_path, read_only=True, data_only=True)
    target_book = load_workbook(target_path, read_only=True, data_only=True)
    base = _station_units(base_book)
    target = _station_units(target_book)
    hydro = _hydro_factors(target_book)
    operating = _operating_records(target_book, target_year)
    curves, existing, candidates, warnings = {}, [], [], []
    for station_id, record in sorted(target.items()):
        base_mw = base.get(station_id, (None, None, 0))[2]
        target_mw = record[2]
        if base_mw > target_mw + 1e-6:
            warnings.append(f"电站{station_id}目标年容量低于基年；存量按目标年容量截取")
        keep = min(base_mw, target_mw)
        # 先解析目标年完整机组组，再按真实整台机组分割存量/候选；月检修台数
        # 先分配给存量，剩余再分配候选，避免同一台检修在两个容量段重复扣减。
        whole = _make_plant(station_id, record, target_mw, target_folder, curves,
                            costs, hydro, True, operating)
        unit_mw = float(record[1][4])
        keep_units = round(keep / unit_mw)
        added_units = round((target_mw - keep) / unit_mw)
        if abs(keep / unit_mw - keep_units) > 1e-7 or \
                abs((target_mw - keep) / unit_mw - added_units) > 1e-7:
            raise ValueError(f"电站{station_id}基年/目标年容量差不是完整机组台数")
        if keep > 0:
            existing.append(replace(
                whole, capacity_mw=keep, annual_cost_yuan=0.0, unit_count=keep_units,
                startup_cost_yuan=whole.startup_cost_yuan * keep_units / whole.unit_count,
                planned_maintenance_units=tuple(min(v, keep_units)
                                                for v in whole.planned_maintenance_units),
                monthly_min_online_units=tuple(min(v, keep_units)
                                               for v in whole.monthly_min_online_units)))
        increment = max(0.0, target_mw - keep)
        if increment > 0:
            candidates.append(replace(
                whole, capacity_mw=increment,
                annual_cost_yuan=whole.annual_cost_yuan * increment / target_mw,
                unit_count=added_units,
                startup_cost_yuan=whole.startup_cost_yuan * added_units / whole.unit_count,
                planned_maintenance_units=tuple(max(0, v - min(v, keep_units))
                                                for v in whole.planned_maintenance_units),
                monthly_min_online_units=tuple(max(0, v - min(v, keep_units))
                                               for v in whole.monthly_min_online_units)))
    # 按有效电站所属系统ID选择当前单区域；外部系统也可能自带负荷曲线。
    # 单区域引擎不会把其他系统的曲线误并入本地区负荷，更不推断网架潮流。
    system_ids = {int(record[0][2]) for record in target.values()}
    if len(system_ids) != 1:
        raise ValueError("当前单区域模型要求有效电站属于同一个系统ID")
    system_id = system_ids.pop()
    system = next(r for r in _records(target_book, "系统表")
                  if int(r[0]) == system_id and r[14])
    # 一个系统可列多条水平年记录，优先取最接近目标年的非零负荷。
    matching_loads = [r for r in _records(target_book, "负荷表")
                      if int(r[2]) == system_id and float(r[3] or 0) > 0]
    load_row = min(matching_loads,
                   key=lambda r: (abs(int(r[1]) - target_year), int(r[1]) > target_year))
    peak = float(load_row[3])
    annual_forecast = float(load_row[4])
    load_curve = _read_curve(target_folder, str(system[14]), curves)
    domestic = tuple(peak * value for value in load_curve)
    if int(load_row[1]) != target_year:
        warnings.append(f"目标文件为{target_year}，负荷表水平年标签为{load_row[1]}；使用文件年份曲线与该行预测值")
    calculated_gwh = sum(domestic) / 1000
    if abs(calculated_gwh - annual_forecast) / max(annual_forecast, 1) > 0.01:
        warnings.append(f"峰值×负荷曲线得到{calculated_gwh:.1f}GWh，与表内预测{annual_forecast:.1f}GWh不一致；保留峰值及曲线原值")
    lines = {int(r[0]): r for r in _records(target_book, "线路表")}
    export = [0.0] * 8760
    for tie in _records(target_book, "联络表"):
        if int(tie[2] or 0) != 1 or int(tie[5]) != 1 or int(tie[6]) != 0 or not tie[15]:
            continue
        line = lines.get(int(tie[4]))
        if line is None:
            raise ValueError(f"联络线缺少线路ID={tie[4]}")
        # 线路表第9列为额定输送MW，逐时外送=额定MW×联络表曲线单位值。
        rated_mw = float(line[8] or 0)
        profile = _read_curve(target_folder, str(tie[15]), curves)
        export = [a + rated_mw * b for a, b in zip(export, profile)]
    if not candidates:
        warnings.append("目标年相对2025没有新增容量；只执行基线运行模拟")
    base_book.close()
    target_book.close()
    return ProjectCase(base_year, target_year, tuple(existing), tuple(candidates),
                       domestic, tuple(export), float(load_row[5] or 0), annual_forecast,
                       tuple(warnings), str(source_folder), str(cost_path))


def align_stage_case(final_case: ProjectCase, year_case: ProjectCase) -> ProjectCase:
    """逐年存量按年度库，候选项目按终期统一位序和设计容量对齐。"""
    if year_case.target_year >= final_case.target_year or year_case.base_year != final_case.base_year:
        raise ValueError("阶段源数据年份必须在共同基年之后、终期目标年之前")
    # 阶段存量采用当年库的基年已有有效容量，包含年度退役/扩容变化。
    # 当年库中与终期候选同ID的新增容量仍属可选建设，不能提前并入固定存量；
    # 终期候选位、项目容量和投资参数继续以终期设计统一编码。
    annual_plants = {plant.station_id: plant
                     for plant in year_case.existing + year_case.candidates}
    warnings = list(year_case.warnings)
    terminal_ids = {plant.station_id for plant in final_case.candidates}
    existing_by_id = {plant.station_id: plant for plant in year_case.existing}
    source_only = [plant for plant in year_case.candidates
                   if plant.station_id not in terminal_ids]
    for plant in source_only:
        # 仅中间年度出现的计划增量无法用终期0/1位选择；按该年源库计划
        # 作为外生投运，并保留其等年值费用，下一年度不自动继承。
        old = existing_by_id.get(plant.station_id)
        if old is None:
            existing_by_id[plant.station_id] = plant
            continue
        if old.technology != plant.technology:
            raise ValueError(f"年度电站{plant.station_id}的存量与外生增量技术不一致")
        if old.technology in {"pumped", "battery"} and (
                old.storage_hours != plant.storage_hours or
                old.roundtrip_efficiency != plant.roundtrip_efficiency or
                old.charge_ratio != plant.charge_ratio):
            raise ValueError(f"储能电站{plant.station_id}的存量与外生增量参数不一致，不能聚合")
        if old.technology in {"wind", "solar"} and old.profile != plant.profile:
            raise ValueError(f"可再生电站{plant.station_id}的存量与外生增量曲线不一致")
        if old.technology == "hydro" and old.hydro_monthly_factor != plant.hydro_monthly_factor:
            raise ValueError(f"水电站{plant.station_id}的存量与外生增量月来水因子不一致")
        capacity = old.capacity_mw + plant.capacity_mw
        # 聚合后最低出力MW守恒：P总×r总=P旧×r旧+P增×r增。
        minimum = ((old.capacity_mw * old.min_fraction +
                    plant.capacity_mw * plant.min_fraction) / capacity)
        existing_by_id[plant.station_id] = replace(
            old, capacity_mw=capacity, min_fraction=minimum,
            annual_cost_yuan=old.annual_cost_yuan + plant.annual_cost_yuan,
            unit_count=old.unit_count + plant.unit_count,
            startup_cost_yuan=old.startup_cost_yuan + plant.startup_cost_yuan,
            planned_maintenance_units=tuple(a + b for a, b in zip(
                old.planned_maintenance_units, plant.planned_maintenance_units)),
            monthly_min_online_units=tuple(a + b for a, b in zip(
                old.monthly_min_online_units, plant.monthly_min_online_units)))
    if source_only:
        warnings.append(f"{year_case.target_year}年度有{len(source_only)}个非终期候选增量；"
                        "按当年源库计划外生投运并计入年化费用，不属于终期可选状态位")

    def use_year_profile(plant: CasePlant) -> CasePlant:
        """相同电站按年度替换天气/来水；缺少可再生曲线时拒绝猜测。"""
        source = annual_plants.get(plant.station_id)
        if source is None:
            if plant.technology in {"wind", "solar", "hydro"}:
                raise ValueError(f"{year_case.target_year}阶段缺少电站{plant.station_id}的年度曲线")
            warnings.append(f"{year_case.target_year}阶段未列电站{plant.station_id}；沿用终期机组技术参数")
            return plant
        if source.technology != plant.technology:
            raise ValueError(f"电站{plant.station_id}在年度库和终期库的技术类型不一致")
        if plant.technology in {"wind", "solar"}:
            if len(source.profile) != 8760:
                raise ValueError(f"电站{plant.station_id}年度可再生曲线不是8760小时")
            return replace(plant, profile=source.profile)
        if plant.technology == "hydro":
            return replace(plant, hydro_monthly_factor=source.hydro_monthly_factor)
        return plant

    return replace(final_case, target_year=year_case.target_year,
                   existing=tuple(existing_by_id[key] for key in sorted(existing_by_id)),
                   candidates=tuple(map(use_year_profile, final_case.candidates)),
                   domestic_load_mw=year_case.domestic_load_mw,
                   export_mw=year_case.export_mw,
                   reserve_margin=year_case.reserve_margin,
                   annual_energy_forecast_gwh=year_case.annual_energy_forecast_gwh,
                   warnings=tuple(warnings))
