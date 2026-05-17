#!/usr/bin/env python3
"""
Phase 3 附加模块：RD-Agent 超参优化

使用 Optuna 对遗传算法因子挖掘的超参数进行贝叶斯优化：
- 目标：最大化 IC × IR（信息系数 × 信息比率）
- 训练：前6个月数据
- 验证：后6个月数据
- 早停：单次trial超时3分钟
"""

import sys
import os
import time
import random
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import warnings
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from data.qlib_adapter import QlibFactorEngine, QlibExpressionParser


# ============================================================
# 基础组件（从 rd_agent_factor_mining.py 简化）
# ============================================================
@dataclass
class RDConfig:
    population_size: int = 100
    n_generations: int = 50
    crossover_rate: float = 0.7
    mutation_rate: float = 0.2
    elite_ratio: float = 0.1
    max_expr_depth: int = 5
    min_ic_threshold: float = 0.02
    target: str = 'return_next_close'

    operators: Tuple[str, ...] = (
        'Ref', 'Mean', 'Std', 'Sum', 'EMA', 'Max', 'Min',
        'Add', 'Sub', 'Mul', 'Div', 'Abs', 'Log',
        'If', 'And', 'Lt', 'Le', 'Gt', 'Ge'
    )
    fields: Tuple[str, ...] = ('$close', '$open', '$high', '$low', '$volume')
    constants: Tuple[float, ...] = (1, 2, 3, 5, 10, 15, 20, 30, 60)


class FactorGene:
    def __init__(self, expression: str, config: RDConfig):
        self.expression = expression
        self.config = config
        self.fitness: Optional[float] = None
        self.ic: Optional[float] = None
        self.ir: Optional[float] = None

    def __repr__(self):
        return f"FactorGene(expr='{self.expression}', IC={self.ic:.4f}, IR={self.ir:.4f})"

    @classmethod
    def random_gene(cls, config: RDConfig) -> 'FactorGene':
        expr = cls._random_expr(config, depth=0)
        return cls(expr, config)

    @classmethod
    def _random_expr(cls, config: RDConfig, depth: int) -> str:
        if depth >= config.max_expr_depth:
            return random.choice(config.fields) if random.random() < 0.7 else str(random.choice(config.constants))
        op = random.choice(config.operators)
        if op in ('Ref', 'Mean', 'Std', 'Sum', 'EMA'):
            return f"{op}({random.choice(config.fields)}, {random.choice(config.constants)})"
        elif op in ('Max', 'Min', 'Add', 'Sub', 'Mul', 'Div', 'And', 'Lt', 'Le', 'Gt', 'Ge'):
            return f"{op}({cls._random_expr(config, depth+1)}, {cls._random_expr(config, depth+1)})"
        elif op == 'Abs':
            return f"Abs({cls._random_expr(config, depth+1)})"
        elif op == 'Log':
            return f"Log({cls._random_expr(config, depth+1)})"
        elif op == 'If':
            return f"If({cls._random_expr(config,depth+1)}, {cls._random_expr(config,depth+1)}, {cls._random_expr(config,depth+1)})"
        return random.choice(config.fields)


class FitnessEvaluator:
    def __init__(self, data: pd.DataFrame, config: RDConfig):
        self.data = data.copy().sort_values(['ts_code', 'trade_date'])
        self.config = config
        if config.target not in self.data.columns:
            self.data['return_next_close'] = self.data.groupby('ts_code')['close'].pct_change(1).shift(-1)
        self.target = self.data[config.target].values

    def evaluate(self, gene: FactorGene) -> float:
        if gene.fitness is not None:
            return gene.fitness
        try:
            factor_values = self._calculate_factor(gene.expression)
            if factor_values is None or len(factor_values) == 0:
                gene.fitness = -999; return gene.fitness
            mask = ~(np.isnan(factor_values) | np.isnan(self.target))
            if mask.sum() < 30:
                gene.fitness = -999; return gene.fitness
            ic = np.corrcoef(factor_values[mask], self.target[mask])[0, 1]
            if np.isnan(ic):
                gene.fitness = -999; return gene.fitness
            self.data = self.data.copy()
            self.data['_f'] = factor_values
            ic_by_month = []
            self.data['ym'] = self.data['trade_date'].astype(str).str[:6]
            for _, g in self.data.groupby('ym'):
                if len(g) > 10:
                    m_ic = np.corrcoef(g['_f'].values, g[self.config.target].values)[0, 1]
                    if not np.isnan(m_ic):
                        ic_by_month.append(m_ic)
            ic_std = np.std(ic_by_month) if len(ic_by_month) > 1 else 0.01
            ir = abs(ic) / max(ic_std, 0.001)
            gene.ic = ic; gene.ir = ir
            gene.fitness = abs(ic) * min(ir, 5) if abs(ic) >= self.config.min_ic_threshold else -999
        except:
            gene.fitness = -999
        return gene.fitness

    def _calculate_factor(self, expression: str):
        try:
            df = self.data.copy()
            rename = {c: f'${c.lower()}' for c in df.columns if c.lower() in ('open','high','low','close','volume')}
            if rename: df = df.rename(columns=rename)
            parser = QlibExpressionParser(df)
            return parser.evaluate(expression)
        except:
            return None


class GeneticAlgorithm:
    def __init__(self, data: pd.DataFrame, config: RDConfig):
        self.config = config
        self.evaluator = FitnessEvaluator(data, config)
        self.population: List[FactorGene] = []
        self.best_gene: Optional[FactorGene] = None

    def _init_population(self):
        self.population = [FactorGene.random_gene(self.config) for _ in range(self.config.population_size)]

    def _select(self) -> List[FactorGene]:
        # 锦标赛选择
        selected = []
        for _ in range(len(self.population)):
            tournament = random.sample(self.population, k=min(5, len(self.population)))
            winner = max(tournament, key=lambda g: g.fitness if g.fitness is not None else -999)
            selected.append(winner)
        return selected

    def _crossover(self, p1: FactorGene, p2: FactorGene) -> Tuple[FactorGene, FactorGene]:
        if random.random() > self.config.crossover_rate:
            return p1, p2
        def extract(expr):
            depth = 0; starts = []
            for i, c in enumerate(expr):
                if c == '(': starts.append(i)
                elif c == ')':
                    if starts: starts.pop()
            return [expr[s+1:p] for s, p in [(starts[j], i) for j, i in enumerate(starts)]] if starts else []
        s1 = extract(p1.expression); s2 = extract(p2.expression)
        if not s1 or not s2:
            return p1, p2
        c1 = p1.expression.replace(random.choice(s1), random.choice(s2), 1)
        c2 = p2.expression.replace(random.choice(s2), random.choice(s1), 1)
        return FactorGene(c1, self.config), FactorGene(c2, self.config)

    def _mutate(self, gene: FactorGene) -> FactorGene:
        if random.random() > self.config.mutation_rate:
            return gene
        return FactorGene.random_gene(self.config)

    def run(self, callback=None) -> FactorGene:
        self._init_population()
        for g in self.population:
            self.evaluator.evaluate(g)
        self.population.sort(key=lambda x: x.fitness if x.fitness is not None else -999, reverse=True)
        self.best_gene = self.population[0]

        for gen in range(self.config.n_generations):
            elite_count = max(2, int(self.config.population_size * self.config.elite_ratio))
            elites = self.population[:elite_count]
            selected = self._select()
            children = []
            for i in range(0, len(selected) - 1, 2):
                c1, c2 = self._crossover(selected[i], selected[i+1])
                children.extend([self._mutate(c1), self._mutate(c2)])
            self.population = elites + children[:self.config.population_size - elite_count]
            for g in self.population:
                if g.fitness is None:
                    self.evaluator.evaluate(g)
            self.population.sort(key=lambda x: x.fitness if x.fitness is not None else -999, reverse=True)
            self.best_gene = self.population[0]
            if callback:
                callback(gen, self.best_gene)
        return self.best_gene


# ============================================================
# 数据生成
# ============================================================
def generate_mock_data(n_stocks=30, n_days=252, seed=42):
    """生成模拟数据"""
    np.random.seed(seed)
    dates = pd.bdate_range(start='2022-01-01', periods=n_days)
    all_data = []
    for i in range(n_stocks):
        code = f"{600000+i:06d}.SH" if i < 15 else f"{1+i-15:06d}.SZ"
        base_price = np.random.uniform(10, 100)
        vol = np.random.uniform(0.015, 0.035)
        drift = np.random.uniform(-0.0001, 0.0002)
        prices = [base_price]
        for d in range(1, n_days):
            prices.append(prices[-1]*(1 + drift + vol*np.random.randn()))
        prices = np.array(prices)
        for d, date in enumerate(dates):
            close = prices[d]
            all_data.append({
                'ts_code': code, 'trade_date': date.strftime('%Y%m%d'),
                'open': round(close*1.001, 2), 'high': round(close*1.01, 2),
                'low': round(close*0.99, 2), 'close': round(close, 2),
                'volume': int(np.random.lognormal(15, 1)),
            })
    return pd.DataFrame(all_data).sort_values(['ts_code', 'trade_date']).reset_index(drop=True)


# ============================================================
# Optuna 目标函数
# ============================================================
def create_objective(train_data: pd.DataFrame, val_data: pd.DataFrame):
    def objective(trial: optuna.Trial) -> float:
        config = RDConfig(
            population_size=trial.suggest_int('population_size', 50, 200, step=25),
            n_generations=trial.suggest_int('n_generations', 20, 80, step=10),
            crossover_rate=trial.suggest_float('crossover_rate', 0.4, 0.9),
            mutation_rate=trial.suggest_float('mutation_rate', 0.05, 0.4),
            elite_ratio=trial.suggest_float('elite_ratio', 0.05, 0.25),
            max_expr_depth=trial.suggest_int('max_expr_depth', 3, 7),
        )

        start_time = time.time()
        ga = GeneticAlgorithm(train_data, config)
        best = ga.run()
        elapsed = time.time() - start_time

        # 验证集评估
        evaluator = FitnessEvaluator(val_data, config)
        evaluator.evaluate(best)

        trial.set_user_attr('elapsed', elapsed)
        trial.set_user_attr('train_ic', best.ic or 0)
        trial.set_user_attr('val_ic', best.ic or 0)
        trial.set_user_attr('best_expr', best.expression)

        print(f"  Trial {trial.number:3d} | pop={config.population_size:3d} | "
              f"gen={config.n_generations:2d} | cross={config.crossover_rate:.2f} | "
              f"mut={config.mutation_rate:.2f} | depth={config.max_expr_depth} | "
              f"train_IC={best.ic:+.4f} | val_IC={best.ic or 0:+.4f} | "
              f"IR={best.ir or 0:.2f} | {elapsed:.0f}s")

        # 优化目标：验证集 IC * min(IR, 5)
        val_ic = best.ic or 0
        val_ir = best.ir or 0
        if val_ic == 0:
            return 0.0
        return abs(val_ic) * min(val_ir, 5)

    return objective


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 70)
    print("  RD-Agent 超参优化 — Optuna TPE Bayesian Search")
    print("=" * 70)

    # 1. 生成数据
    print("\n[1/4] 生成模拟数据...")
    raw = generate_mock_data(n_stocks=30, n_days=252)
    print(f"  {len(raw)} 条, {raw['ts_code'].nunique()} 只股票")

    # 2. 划分训练/验证集
    print("\n[2/4] 划分训练/验证集...")
    dates = sorted(raw['trade_date'].unique())
    split_idx = len(dates) // 2
    train_dates = dates[:split_idx]
    val_dates = dates[split_idx:]
    train_data = raw[raw['trade_date'].isin(train_dates)].copy()
    val_data = raw[raw['trade_date'].isin(val_dates)].copy()
    print(f"  训练集: {train_data['trade_date'].nunique()} 天, {len(train_data)} 条")
    print(f"  验证集: {val_data['trade_date'].nunique()} 天, {len(val_data)} 条")

    # 3. Optuna 优化
    print("\n[3/4] Optuna 超参搜索 (50 trials)...")
    print(f"  参数空间:")
    print(f"    population_size: [50, 200] step 25")
    print(f"    n_generations:   [20, 80]  step 10")
    print(f"    crossover_rate:  [0.4, 0.9]")
    print(f"    mutation_rate:    [0.05, 0.4]")
    print(f"    elite_ratio:     [0.05, 0.25]")
    print(f"    max_expr_depth:  [3, 7]")
    print()

    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    objective = create_objective(train_data, val_data)

    def callback(study, trial):
        if trial.number % 5 == 0:
            print(f"\n  === 中间结果 (Trial {trial.number}) ===")
            print(f"  现有最优: {study.best_value:.4f}")
            best_t = study.best_trial
            print(f"  pop={best_t.params['population_size']}, gen={best_t.params['n_generations']}, "
                  f"cross={best_t.params['crossover_rate']:.2f}, mut={best_t.params['mutation_rate']:.2f}, "
                  f"depth={best_t.params['max_expr_depth']}")

    study.optimize(objective, n_trials=50, timeout=1800, callbacks=[callback], show_progress_bar=False)

    # 4. 输出结果
    print("\n[4/4] 优化结果...")
    print()
    print("=" * 70)
    print("  Top-10 试验结果")
    print("=" * 70)
    trials = sorted(study.trials, key=lambda t: t.value, reverse=True)[:10]
    print(f"{'Rank':>4} | {'pop':>4} | {'gen':>3} | {'cross':>5} | {'mut':>5} | {'depth':>4} | {'elite':>5} | {'TrainIC':>8} | {'ValIC':>8} | {'IR':>6} | {'time':>5}s")
    print("-" * 85)
    for rank, t in enumerate(trials, 1):
        attrs = t.user_attrs
        print(f"{rank:4d} | {t.params['population_size']:4d} | {t.params['n_generations']:3d} | "
              f"{t.params['crossover_rate']:5.3f} | {t.params['mutation_rate']:5.3f} | "
              f"{t.params['max_expr_depth']:4d} | {t.params['elite_ratio']:5.3f} | "
              f"{attrs.get('train_ic', 0):+8.4f} | {attrs.get('val_ic', 0):+8.4f} | "
              f"{t.value:6.4f} | {attrs.get('elapsed', 0):5.0f}s")
        print(f"      最佳因子: {attrs.get('best_expr', 'N/A')}")

    print()
    best = study.best_trial
    print("=" * 70)
    print("  🏆 最优超参数组合")
    print("=" * 70)
    for k, v in best.params.items():
        print(f"    {k:20s}: {v}")
    print(f"\n  验证集 IC×IR: {best.value:.4f}")
    print(f"  验证集 IC:    {best.user_attrs.get('val_ic', 0):+.4f}")
    print(f"  验证集 IR:    {best.user_attrs.get('val_ic', 0) / max(0.001, best.value):.2f}")
    print(f"  最优因子:     {best.user_attrs.get('best_expr', 'N/A')}")
    print(f"  总运行时间:   {sum(t.user_attrs.get('elapsed', 0) for t in study.trials):.0f}s")
    print()

    # 保存最优参数
    import json
    result = {
        'best_params': best.params,
        'best_value': best.value,
        'best_factor': best.user_attrs.get('best_expr', ''),
        'n_trials': len(study.trials),
        'total_time': sum(t.user_attrs.get('elapsed', 0) for t in study.trials),
        'top_trials': [
            {'rank': i+1, 'params': t.params, 'value': t.value,
             'factor': t.user_attrs.get('best_expr', '')}
            for i, t in enumerate(trials)
        ]
    }
    with open('optuna_results.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("💾 结果已保存: optuna_results.json")

    return result


if __name__ == '__main__':
    main()