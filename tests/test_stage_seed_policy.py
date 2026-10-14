"""多年度GA的Gen=0单项目种子须均衡覆盖规划年份。"""

import unittest

from power_ga.initial_population.encoding import stage_single_project_seeds


class StageSeedPolicyTests(unittest.TestCase):
    def test_small_population_cannot_exclude_earlier_years_by_order(self):
        """种群8只容纳6个单项目种子时，三个年份应各获两个位置。"""
        seeds = stage_single_project_seeds(candidate_count=8, stage_count=3, seed=11)
        self.assertEqual(24, len(seeds))
        self.assertEqual(24, len(set(seeds)))
        self.assertEqual(24, len(seeds[0]))
        self.assertTrue(all(sum(chromosome) == 1 for chromosome in seeds))
        first_six = seeds[:6]  # 全不建、全建占另外两个种群位置。
        annual_counts = [sum(any(bits[t * 8:(t + 1) * 8]) for bits in first_six)
                         for t in range(3)]
        self.assertEqual([2, 2, 2], annual_counts)
        # 全24个种子必须一一覆盖每个“候选项目×可建设年份”。
        self.assertEqual({(t, i) for t in range(3) for i in range(8)},
                         {(index // 8, index % 8)
                          for bits in seeds for index, value in enumerate(bits) if value})

    def test_seed_order_is_reproducible_and_prefix_balanced(self):
        """相同随机种子给相同排序；任何种群容量前缀的年份计数最多相差1。"""
        first = stage_single_project_seeds(8, 3, 19)
        self.assertEqual(first, stage_single_project_seeds(8, 3, 19))
        self.assertNotEqual(first[:6], stage_single_project_seeds(8, 3, 11)[:6])
        for length in range(1, 25):
            counts = [sum(any(bits[t * 8:(t + 1) * 8]) for bits in first[:length])
                      for t in range(3)]
            self.assertLessEqual(max(counts) - min(counts), 1)


if __name__ == "__main__":
    unittest.main()
