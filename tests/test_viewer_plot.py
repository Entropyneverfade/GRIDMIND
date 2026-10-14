"""图形样式使用合成逐时数据，核查刻度密度和界限。"""

import unittest

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

from power_ga.result_output.viewer import draw_view


class ViewerPlotTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
