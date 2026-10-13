"""遗传迭代：PPT 第 31 页适应度、轮盘赌选择、单点交叉、位变异、精英保留。"""

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..common.domain import GASettings, Problem
from ..initial_population.encoding import Chromosome, generate_gen0
from ..fitness_and_convergence.evaluation import Evaluation, evaluate, ppt_fitness, should_stop


@dataclass(frozen=True)
class HistoryRow:
    """记录代内分布和历代最优，供收敛、可行性及种群多样性图复核。"""
    generation: int
    best_cost_yuan: float
    best_feasible: bool
    feasible_count: int
    best_violation: float
    generation_best_cost_yuan: float = 0.0
    mean_cost_yuan: float = 0.0
    median_cost_yuan: float = 0.0
    unique_count: int = 0
    best_chromosome: Tuple[int, ...] = ()


@dataclass(frozen=True)
class GAResult:
    """GA交给结果模块的只读记录，包含最优方案及停止理由。"""
    best: Evaluation
    history: Tuple[HistoryRow, ...]
    stop_reason: str
    evaluations: int


def _parent_pool(scored: List[Evaluation]) -> Tuple[List[Evaluation], List[float]]:
    """有足够可行解时仅从可行方案中轮盘赌；否则用违约惩罚保留探索。"""
    feasible = [item for item in scored if item.feasible]
    pool = feasible if len(feasible) >= 2 else scored
    if pool is feasible:
        # PPT适应度需要正费用，原始费用越低则父代概率越高。
        costs = [item.total_cost_yuan for item in pool]
    else:
        # 无足够可行个体时给约束违反量加惩罚，用于选择；最终最优判别仍严格可行优先。
        scale = max(item.total_cost_yuan for item in pool)
        costs = [item.total_cost_yuan + (100 * scale * (1 + item.violation)
                 if not item.feasible else 0) for item in pool]
    return pool, ppt_fitness(costs)


def _cross(a: Chromosome, b: Chromosome, rng: random.Random, rate: float):
    """单点交叉：子代=(父A前cut位,父B后段)及对称组合。"""
    if len(a) < 2 or rng.random() >= rate:
        return a, b
    cut = rng.randrange(1, len(a))
    return a[:cut] + b[cut:], b[:cut] + a[cut:]


def _mutate(chromosome: Chromosome, rng: random.Random, rate: float) -> Chromosome:
    """位变异：每基因以rate概率执行b'=1−b，保持探索能力。"""
    return tuple(1 - bit if rng.random() < rate else bit for bit in chromosome)


def optimize(problem: Problem, settings: GASettings, evaluator=None, progress=None,
             seed_population=None) -> GAResult:
    """从Gen=0迭代；可注入真实算例评价函数，遗传算子保持一致。"""
    evaluator = evaluator or evaluate
    rng = random.Random(settings.seed)
    population = generate_gen0(problem, settings.population_size, rng)
    if seed_population:
        # 多阶段编码可以把有物理意义的候选建设年方案放入Gen=0。
        # 校验后替换随机尾部，保留全不建与全建两个基准方案。
        seeds = [tuple(bits) for bits in seed_population]
        if any(len(bits) != len(problem.candidates) or
               any(bit not in (0, 1) for bit in bits) for bits in seeds):
            raise ValueError("Gen=0种子染色体长度或取值错误")
        for index, bits in enumerate(seeds[:max(0, settings.population_size - 2)], 2):
            population[index] = bits
    # 同一确定性方案结果不变，缓存避免重复执行8760小时运行模拟。
    cache: Dict[Chromosome, Evaluation] = {}
    history = []
    best = None
    stalled = 0
    stop_reason = "达到最大代数"

    for generation in range(settings.max_generations + 1):
        for chromosome in population:
            if chromosome not in cache:
                cache[chromosome] = evaluator(problem, chromosome)
        # 适应度决定父代抽样概率；sort_key负责严格的可行性与最优比较。
        scored = sorted((cache[item] for item in population), key=lambda item: item.sort_key())
        generation_best = scored[0]
        if best is None or generation_best.sort_key() < best.sort_key():
            best = generation_best
            stalled = 0
        else:
            stalled += 1
        # 平均/中位数只在可行个体集合上计算；无可行解时用全种群费用，
        # 并由可行个体数=0显式标识，避免把不可行低价误认为收敛。
        costs = sorted(item.total_cost_yuan for item in scored if item.feasible)
        if not costs:
            costs = sorted(item.total_cost_yuan for item in scored)
        middle = len(costs) // 2
        median = (costs[middle] if len(costs) % 2 else
                  (costs[middle - 1] + costs[middle]) / 2)
        history.append(HistoryRow(generation, best.total_cost_yuan, best.feasible,
                                  sum(item.feasible for item in scored), best.violation,
                                  generation_best.total_cost_yuan,
                                  sum(costs) / len(costs), median,
                                  len(set(population)), best.chromosome))
        if progress is not None:
            # GUI回调只传小型代际摘要，不跨线程传8760行结果对象。
            progress(history[-1], settings.max_generations)
        # 可行最优方案连续停滞达到阈值才提前终止，否则最多迭代到上限。
        if should_stop(best.feasible, generation, stalled, settings):
            stop_reason = "连续若干代无改进"
            break
        if generation == settings.max_generations:
            break

        pool, weights = _parent_pool(scored)
        # 精英直接进入下一代，避免交叉或变异破坏已找到的优良方案。
        next_population = [item.chromosome for item in scored[:settings.elite_count]]
        while len(next_population) < settings.population_size:
            parent_a, parent_b = rng.choices(pool, weights=weights, k=2)
            child_a, child_b = _cross(parent_a.chromosome, parent_b.chromosome,
                                     rng, settings.crossover_rate)
            next_population.append(_mutate(child_a, rng, settings.mutation_rate))
            if len(next_population) < settings.population_size:
                next_population.append(_mutate(child_b, rng, settings.mutation_rate))
        population = next_population
    return GAResult(best, tuple(history), stop_reason, len(cache))
