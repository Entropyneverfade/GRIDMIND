"""编码与 Gen=0 生成。单年示例：第 i 位为 1 表示建设第 i 个候选电站。"""

import random
from typing import List, Tuple

from ..common.domain import Problem


Chromosome = Tuple[int, ...]
# 对外存档的策略标识；同一随机种子跨版本重跑时可辨认初代排序改变。
STAGE_SEED_POLICY = "balanced_by_stage_v2"


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


def stage_single_project_seeds(candidate_count: int, stage_count: int,
                               seed: int) -> Tuple[Chromosome, ...]:
    """为多年建设编码生成单项目Gen=0种子，并在容量截断前均衡覆盖各年份。"""
    if candidate_count < 1 or stage_count < 1:
        raise ValueError("候选项目数和规划年数必须为正")
    rng = random.Random(seed)
    stages = list(range(stage_count))
    rng.shuffle(stages)
    # 各年的候选项目分别打乱，同一随机种子可完整复现；每轮每年各取1个。
    candidates_by_stage = []
    for _ in stages:
        candidates = list(range(candidate_count))
        rng.shuffle(candidates)
        candidates_by_stage.append(candidates)
    chromosomes = []
    for offset in range(candidate_count):
        for position, stage in enumerate(stages):
            bits = [0] * (candidate_count * stage_count)
            # gene[t*n+i]=1 表示候选i在规划年t建设；本种子只有这一位为1。
            bits[stage * candidate_count + candidates_by_stage[position][offset]] = 1
            chromosomes.append(tuple(bits))
    return tuple(chromosomes)
