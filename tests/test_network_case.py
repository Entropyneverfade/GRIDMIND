"""分区CSV端到端已知答案：电力、碳、SO₂和新能源归属同表核对。"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from power_ga.operation_simulation.network_case import run_network_case


def write_csv(path, columns, rows):
    """构造独立的24小时小算例，不读取项目数据库。"""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


class NetworkCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input"
        self.source.mkdir()
        write_csv(self.source / "zones.csv", ("zone",), (("A",), ("B",)))
        # A区10MW煤+10MW风，A/B各用10MW：两区消费属性均为煤/风各半。
        write_csv(self.source / "generators.csv",
                  ("name", "zone", "technology", "minimum_mw", "maximum_mw", "cost_yuan_per_mwh",
                   "carbon_t_per_mwh", "sulfur_kg_per_mwh", "renewable_fraction"),
                  (("coal", "A", "coal", 10, 10, 200, 1, 2, 0),))
        write_csv(self.source / "links.csv",
                  ("name", "source", "target", "limit_mw", "kind",
                   "susceptance_mw_per_rad"), (("AB", "A", "B", 10, "dc", ""),))
        hourly = []
        for hour in range(24):
            hourly.extend(((hour, "A", 10, 10, 0, 0, 0, 0, 0,
                            "", "", "", "", "", ""),
                           (hour, "B", 10, 0, 0, 0, 0, 0, 0,
                            "", "", "", "", "", "")))
        write_csv(self.source / "hourly.csv",
                  ("hour", "zone", "demand_mw", "wind_available_mw",
                   "solar_available_mw", "pumped_charge_mw", "pumped_discharge_mw",
                   "battery_charge_mw", "battery_discharge_mw",
                   "pumped_carbon_t_per_mwh", "pumped_sulfur_kg_per_mwh",
                   "pumped_renewable_fraction", "battery_carbon_t_per_mwh",
                   "battery_sulfur_kg_per_mwh", "battery_renewable_fraction"), hourly)

    def test_24_hour_known_answer_and_workbook(self):
        for solver in ("heuristic", "gurobi"):
            with self.subTest(solver=solver):
                output = self.root / solver
                audit = run_network_case(self.source, output, solver=solver,
                                         expected_hours=24)
                self.assertLess(audit["max_power_balance_residual_mw"], 1e-9)
                self.assertLess(audit["max_carbon_balance_residual_t"], 1e-9)
                self.assertLess(audit["max_sulfur_balance_residual_kg"], 1e-9)
                self.assertLess(audit["max_renewable_balance_residual_mwh"], 1e-9)
                with (output / "tables" / "zone_summary.csv").open(
                        encoding="utf-8-sig", newline="") as stream:
                    summary = {row["zone"]: row for row in csv.DictReader(stream)}
                for zone in ("A", "B"):
                    self.assertAlmostEqual(float(summary[zone]["demand_mw"]), 240)
                    self.assertAlmostEqual(float(summary[zone]["consumed_carbon_t"]), 120)
                    self.assertAlmostEqual(float(summary[zone]["consumed_sulfur_kg"]), 240)
                    self.assertAlmostEqual(float(summary[zone]["consumed_renewable_mwh"]), 120)
                self.assertAlmostEqual(float(summary["A"]["coal_mw"]), 240)
                self.assertAlmostEqual(float(summary["B"]["coal_mw"]), 0)
                self.assertNotIn("conventional_mw", summary["A"])
                workbook = load_workbook(output / "tables" / "跨区运行和碳硫属性汇总.xlsx",
                                         read_only=True)
                try:
                    # 流式工作簿不写dimension元数据，实际49行仍必须能完整读出。
                    self.assertEqual(sum(1 for _ in workbook["分区逐时与属性"].values), 49)
                finally:
                    workbook.close()
                manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["hours"], 24)
                self.assertNotIn(str(self.root), json.dumps(manifest))
                # 同名结果不能被第二次运行部分覆盖，确保归档可复用。
                with self.assertRaises(FileExistsError):
                    run_network_case(self.source, output, solver=solver, expected_hours=24)

    def test_ac_requires_phase_angle_solver(self):
        write_csv(self.source / "links.csv",
                  ("name", "source", "target", "limit_mw", "kind",
                   "susceptance_mw_per_rad"), (("AB", "A", "B", 10, "ac", 100),))
        with self.assertRaisesRegex(ValueError, "Gurobi LP"):
            run_network_case(self.source, self.root / "invalid", expected_hours=24)
        self.assertFalse((self.root / "invalid").exists())


if __name__ == "__main__":
    unittest.main()
