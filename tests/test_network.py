"""跨区传输的已知答案测试：分区平衡、联络线上限和交流环流。"""

import unittest

from power_ga.operation_simulation.network import (
    Generator, Link, Zone, solve_network_hour, solve_network_hour_heuristic,
    solve_network_timeseries)


class NetworkDispatchTests(unittest.TestCase):
    def test_transfer_bottleneck_and_both_renewables_curtail(self):
        # A区100 MW风光仅能本地消纳10 MW并外送20 MW；两类各弃35 MW。
        result = solve_network_hour(
            (Zone("A", 10, wind_available_mw=50, solar_available_mw=50),
             Zone("B", 50)),
            (Generator("B煤电", "B", 0, 20, 200),),
            (Link("A到B", "A", "B", 20),))
        self.assertAlmostEqual(result.flows_mw["A到B"], 20)
        self.assertAlmostEqual(result.generation_mw["B煤电"], 20)
        self.assertAlmostEqual(result.zones["B"]["unserved_mw"], 10)
        self.assertAlmostEqual(result.zones["A"]["wind_curtailment_mw"], 35)
        self.assertAlmostEqual(result.zones["A"]["solar_curtailment_mw"], 35)
        self.assertLess(result.max_balance_residual_mw, 1e-8)

    def test_ac_loop_obeys_angle_flow_not_free_routing(self):
        # 等电纳三角网中直连线承受总传输的2/3；30 MW直连限额使总传输至多45 MW。
        result = solve_network_hour(
            (Zone("A", 0, wind_available_mw=100), Zone("B", 0), Zone("C", 100)),
            (),
            (Link("AB", "A", "B", 100, "ac", 100),
             Link("BC", "B", "C", 100, "ac", 100),
             Link("AC", "A", "C", 30, "ac", 100)))
        self.assertAlmostEqual(result.flows_mw["AC"], 30, places=6)
        self.assertAlmostEqual(result.flows_mw["AB"], 15, places=6)
        self.assertAlmostEqual(result.flows_mw["BC"], 15, places=6)
        self.assertAlmostEqual(result.zones["C"]["unserved_mw"], 55, places=6)
        self.assertLess(result.max_balance_residual_mw, 1e-8)

    def test_bad_or_missing_line_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            solve_network_hour((Zone("A", 0), Zone("B", 0)), (),
                               (Link("AB", "A", "B", 20, "ac"),))
        with self.assertRaises(ValueError):
            solve_network_hour((Zone("A", 0), Zone("B", 0)), (),
                               (Link("AB", "A", "B", -1),))

    def test_timeseries_energy_and_balance(self):
        # 同一已知答案重复24小时，电量应为小时功率×24且每小时分区守恒。
        zones = [(Zone("A", 10, wind_available_mw=50, solar_available_mw=50),
                  Zone("B", 50)) for _ in range(24)]
        generators = [(Generator("B煤电", "B", 0, 20, 200),) for _ in range(24)]
        result = solve_network_timeseries(zones, generators,
                                          (Link("A到B", "A", "B", 20),))
        self.assertEqual(len(result.hourly), 24)
        self.assertAlmostEqual(result.total_wind_curtailment_mwh, 35 * 24)
        self.assertAlmostEqual(result.total_solar_curtailment_mwh, 35 * 24)
        self.assertAlmostEqual(result.total_unserved_mwh, 10 * 24)
        self.assertLess(result.max_balance_residual_mw, 1e-8)

    def test_heuristic_multihop_and_ac_guard(self):
        # A→B→C 两级可控通道传20 MW；C余下10 MW由当地机组补齐。
        zones = (Zone("A", 0, wind_available_mw=20, solar_available_mw=20),
                 Zone("B", 0), Zone("C", 30))
        generators = (Generator("C气", "C", 0, 20, 400),)
        links = (Link("AB", "A", "B", 20), Link("BC", "B", "C", 20))
        result = solve_network_hour_heuristic(zones, generators, links)
        self.assertAlmostEqual(result.flows_mw["AB"], 20)
        self.assertAlmostEqual(result.flows_mw["BC"], 20)
        self.assertAlmostEqual(result.generation_mw["C气"], 10)
        self.assertAlmostEqual(result.zones["A"]["wind_curtailment_mw"], 10)
        self.assertAlmostEqual(result.zones["A"]["solar_curtailment_mw"], 10)
        self.assertLess(result.max_balance_residual_mw, 1e-8)
        with self.assertRaises(ValueError):
            solve_network_hour_heuristic(zones, generators,
                                         (Link("AC", "A", "C", 20, "ac", 100),))


if __name__ == "__main__":
    unittest.main()
