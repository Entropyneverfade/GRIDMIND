"""编码与 Gen=0 生成。单年示例：第 i 位为 1 表示建设第 i 个候选电站。"""

import random
from typing import List, Tuple

from ..common.domain import Problem


Chromosome = Tuple[int, ...]


def decode(problem: Problem, chromosome: Chromosome) -> Tuple[str, ...]:
    """把第i位的0/1建设决策映射到候选电站名称，并检查编码合法。"""
    if len(chromosome) != len(problem.candidates) or any(bit not in (0, 1) for bit in chromosome):
        raise ValueError("染色体长度或取值错误")
    return tuple(p.name for bit, p in zip(chromosome, problem.candidates) if bit)


def generate_gen0(problem: Problem, size: int, rng: random.Random) -> List[Chromosome]:
    """含不建、全建两种基准方案，其余随机生成。"""
    n = len(problem.candidates)
    # 基准个体覆盖“全不建”和“全建”；剩余个体每一位独立伯努利采样。
    population = [tuple(0 for _ in range(n)), tuple(1 for _ in range(n))]
    while len(population) < size:
        population.append(tuple(rng.randrange(2) for _ in range(n)))
    return population
