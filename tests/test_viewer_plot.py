"""图形样式使用合成逐时数据，核查刻度密度和界限。"""

import unittest
import csv
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

from power_ga.result_output.viewer import (
    aggregate_network_zones, draw_view, load_network_zones,
    selected_hour_bounds, summarize_selected_hours)
from power_ga.result_output.origin_plot import _render
from gridmind_app.main import launch_gui_child


class ViewerPlotTests(unittest.TestCase):
    def test_network_aggregate_cancels_internal_exchange_and_keeps_zone_curves(self):
        """两区纯合成交换在全网抵消；分区图仍分别保留不同机组与外送。"""
        base = {f"{kind}_mw": 0.0 for kind in
                ("coal", "gas", "nuclear", "hydro", "biomass", "csp",
                 "oil", "geothermal", "solar", "wind")}
        base.update({"pumped_discharge_mw": 0.0, "battery_discharge_mw": 0.0,
                     "pumped_charge_mw": 0.0, "battery_charge_mw": 0.0,
                     "storage_discharge_mw": 0.0, "storage_charge_mw": 0.0,
                     "storage_energy_end_mwh": 0.0, "wind_curtailment_mw": 0.0,
                     "solar_curtailment_mw": 0.0, "unserved_mw": 0.0,
                     "overgeneration_mw": 0.0})
        exporter = {**base, "coal_mw": 10.0, "imports_mw": 0.0,
                    "export_mw": 2.0, "domestic_load_mw": 8.0, "load_mw": 10.0}
        importer = {**base, "hydro_mw": 2.0, "imports_mw": 2.0,
                    "export_mw": 0.0, "domestic_load_mw": 4.0, "load_mw": 4.0}
        zones = {"甲区": [exporter, exporter], "乙区": [importer, importer]}
        total = aggregate_network_zones(zones)
        self.assertEqual(total[0]["load_mw"], 12.0)
        self.assertEqual(total[0]["imports_mw"], 0.0)
        self.assertEqual(total[0]["export_mw"], 0.0)
        self.assertEqual(dict(summarize_selected_hours(zones["甲区"], 0, 2)["transfer"])["外送"],
                         4.0)
        self.assertEqual(summarize_selected_hours(total, 0, 2)["balance_residual_mwh"], 0.0)
        a = draw_view(Figure(figsize=(8, 5)), zones["甲区"], 0, 2)
        b = draw_view(Figure(figsize=(8, 5)), zones["乙区"], 0, 2)
        self.assertIn("煤电", [item.get_label() for item in a.collections])
        self.assertIn("常规水电", [item.get_label() for item in b.collections])
        with self.assertRaisesRegex(ValueError, "交换不守恒"):
            aggregate_network_zones({"甲区": [exporter],
                                     "乙区": [{**importer, "imports_mw": 1.0}]})
        with tempfile.TemporaryDirectory() as temporary:
            tables = Path(temporary) / "tables"
            tables.mkdir()
            keys = ("hour", "zone", "demand_mw", "coal_mw", "gas_mw", "hydro_mw",
                    "biomass_mw", "nuclear_mw", "csp_mw", "oil_mw", "geothermal_mw",
                    "wind_mw", "solar_mw", "imports_mw", "exports_mw",
                    "pumped_charge_mw", "pumped_discharge_mw", "battery_charge_mw",
                    "battery_discharge_mw", "wind_curtailment_mw",
                    "solar_curtailment_mw", "unserved_mw", "spill_mw")
            with (tables / "hourly_network.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=keys)
                writer.writeheader()
                for hour in range(2):
                    for zone, values in (("甲区", exporter), ("乙区", importer)):
                        original = {"hour": hour, "zone": zone,
                                    "demand_mw": values["domestic_load_mw"],
                                    "exports_mw": values["export_mw"],
                                    "spill_mw": values["overgeneration_mw"]}
                        writer.writerow({field: original.get(field, values.get(field, 0.0))
                                         for field in keys})
            parsed = load_network_zones(Path(temporary), expected_hours=2)
            self.assertEqual(tuple(parsed), ("甲区", "乙区"))
            self.assertEqual(parsed["甲区"][1]["export_mw"], 2.0)
            self.assertEqual(parsed["乙区"][1]["imports_mw"], 2.0)

    def test_drag_selection_uses_intersected_integer_hours(self):
        """正反向拖拽都收纳被框触及的整小时，并截在当前周窗口内。"""
        self.assertEqual(selected_hour_bounds(20.2, 23.1, 0, 24), (20, 24))
        self.assertEqual(selected_hour_bounds(2034.8, 2022.3, 2016, 2184),
                         (2022, 2035))

    def test_selected_interval_sums_generation_curtailment_storage_and_export(self):
        """两小时的电量由原始MW逐项积分，外送不重复计入本地负荷。"""
        first = {"coal_mw": 8.0, "gas_mw": 0.0, "hydro_mw": 0.0,
                 "biomass_mw": 0.0, "wind_mw": 3.0, "solar_mw": 0.0,
                 "pumped_discharge_mw": 0.0, "battery_discharge_mw": 0.0,
                 "pumped_charge_mw": 1.0, "battery_charge_mw": 0.0,
                 "storage_discharge_mw": 0.0, "storage_charge_mw": 1.0,
                 "domestic_load_mw": 8.0, "export_mw": 2.0, "load_mw": 10.0,
                 "wind_curtailment_mw": 2.0, "solar_curtailment_mw": 1.0,
                 "unserved_mw": 0.0, "overgeneration_mw": 0.0}
        second = {**first, "coal_mw": 7.0, "wind_mw": 2.0,
                  "pumped_charge_mw": 0.0, "storage_charge_mw": 0.0,
                  "pumped_discharge_mw": 1.0, "storage_discharge_mw": 1.0,
                  "wind_curtailment_mw": 0.0, "solar_curtailment_mw": 0.0}
        report = summarize_selected_hours([first, second], 0, 2)
        self.assertEqual(report["hours"], 2)
        self.assertEqual(dict(report["generation"])["煤电"], 15.0)
        self.assertEqual(dict(report["curtailment"])["弃风"], 2.0)
        self.assertEqual(dict(report["storage"])["抽蓄充电"], 1.0)
        self.assertEqual(dict(report["storage"])["抽蓄放电"], 1.0)
        self.assertEqual(dict(report["transfer"])["外送"], 4.0)
        self.assertEqual(dict(report["demand"])["本地负荷"], 16.0)
        self.assertEqual(report["balance_residual_mwh"], 0.0)

    def test_week_axis_is_readable_and_storage_is_visible(self):
        """周图可见两端真刻度、纵轴不形成黑线，充电仍在堆叠图负半轴。"""
        hour = {"load_mw": 95.0, "thermal_mw": 70.0,
                "wind_mw": 20.0, "solar_mw": 5.0,
                "storage_charge_mw": 2.0, "storage_discharge_mw": 0.0,
                "unserved_mw": 0.0, "solar_curtailment_mw": 0.0,
                "wind_curtailment_mw": 0.0}
        fig = Figure(figsize=(12, 6))
        axes = draw_view(fig, [hour] * 8760, 0, 168, "第1周")
        self.assertLessEqual(len(axes.get_yticks()), 8)
        self.assertEqual((axes.get_xticks()[0], axes.get_xticks()[-1]), (0, 168))
        self.assertLess(axes.get_ylim()[0], 0)
        self.assertEqual(axes.get_yticks()[0], axes.get_ylim()[0])
        self.assertEqual(axes.get_yticks()[-1], axes.get_ylim()[1])

    def test_small_wind_and_solar_curtailment_has_dense_hatching_and_true_annotation(self):
        """一小时薄弃电仍用反向密斜线，并以真实MW标注供缩略图辨认。"""
        hour = {"load_mw": 100.0, "thermal_mw": 55.0,
                "wind_mw": 35.0, "solar_mw": 10.0,
                "storage_charge_mw": 0.0, "storage_discharge_mw": 0.0,
                "unserved_mw": 0.0, "solar_curtailment_mw": 0.0,
                "wind_curtailment_mw": 0.0}
        hours = [hour] * 8760
        hours[20] = {**hour, "wind_curtailment_mw": 1.25,
                     "solar_curtailment_mw": 2.75}
        axes = draw_view(Figure(figsize=(12, 6)), hours, 0, 168, "第1周")
        polygons = {artist.get_label(): artist for artist in axes.collections}
        self.assertIn("弃风", polygons)
        self.assertIn("弃光", polygons)
        self.assertNotEqual(polygons["弃风"].get_hatch()[0],
                            polygons["弃光"].get_hatch()[0])
        self.assertGreaterEqual(len(polygons["弃风"].get_hatch()), 8)
        self.assertGreaterEqual(len(polygons["弃光"].get_hatch()), 8)
        labels = [artist.get_text() for artist in axes.texts]
        self.assertTrue(any("弃风 1.25 MW" in label and "弃光 2.75 MW" in label
                            for label in labels))

    def test_origin_renderer_hides_console_and_keeps_log(self):
        """Origin后台子进程不弹控制台；绘图日志仍写入一图一目录。"""
        with tempfile.TemporaryDirectory() as temporary, patch(
                "power_ga.result_output.origin_plot.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, b"rendered", b"")) as run:
            folder = Path(temporary) / "figure"
            _render(folder, {"hour": [0, 1]}, [], {"name": "smoke"}, [[0], [1]], ["hour"])
            self.assertTrue(folder.joinpath("qa", "renderer.log").is_file())
            self.assertIn("rendered", folder.joinpath("qa", "renderer.log").read_text())
            self.assertEqual(run.call_args.kwargs["creationflags"],
                             getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_gui_child_hides_console_without_hiding_window(self):
        """结果查看器保持独立GUI进程，只抑制多余的命令窗口。"""
        with patch("gridmind_app.main.subprocess.Popen") as start:
            launch_gui_child(["python", "viewer.py"])
            self.assertEqual(start.call_args.kwargs["creationflags"],
                             getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    unittest.main()
