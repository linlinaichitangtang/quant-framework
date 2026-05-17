#!/usr/bin/env python3
"""
RD-Agent 自动化因子挖掘 — 真实市场数据版
基于遗传算法 + qlib表达式引擎 + FutuOpenD真实行情

核心改动：
1. 使用 FutuQuoteFetcher 获取50+只A股日K（252天/1年）
2. 使用HPO最优参数：population_size=75, n_generations=40, crossover_rate=0.538, mutation_rate=0.317, elite_ratio=0.198, max_expr_depth=7
3. 输出Top10因子表达式 + IC/IR/Stability指标
4. 保存结果到 factors_real_top10.csv
"""

import sys
import os
import random
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

# ── 项目路径 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from data.qlib_adapter import QlibFactorEngine, QlibExpressionParser

# ── Futu SDK ──
try:
    from futu.quote.open_quote_context import OpenQuoteContext
    from futu.quote.quote_query import KLType, KL_FIELD
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False
    print("[警告] futu SDK 不可用")

FUTU_HOST = '127.0.0.1'
FUTU_PORT = 11111

# ── 股票池（50只沪深代表性股票）──
STOCK_POOL = [
    # 沪市主板 - 银行
    'SH.600000', 'SH.601398', 'SH.601288', 'SH.601166', 'SH.600036',
    # 沪市主板 - 消费/白酒
    'SH.600519', 'SH.600887', 'SH.603369', 'SH.600809',
    # 沪市主板 - 保险/证券
    'SH.601318', 'SH.601336', 'SH.600030', 'SH.601688',
    # 沪市主板 - 能源/石化
    'SH.600028', 'SH.601857', 'SH.601088', 'SH.600188',
    # 沪市主板 - 医药
    'SH.600276', 'SH.603259', 'SH.600196', 'SH.600436',
    # 沪市主板 - 其他蓝筹
    'SH.601888', 'SH.600900', 'SH.600585', 'SH.600309', 'SH.600886',
    # 沪市 - 科技/制造
    'SH.688981', 'SH.600570', 'SH.601012', 'SH.600745', 'SH.600588',
    # 深市主板
    'SZ.000858', 'SZ.000333', 'SZ.000651', 'SZ.000725', 'SZ.000002',
    'SZ.000001', 'SZ.002714', 'SZ.000568', 'SZ.002304', 'SZ.002415',
    # 深市创业板
    'SZ.300750', 'SZ.300059', 'SZ.300015', 'SZ.300760', 'SZ.300122',
    'SZ.300274', 'SZ.300014', 'SZ.002594', 'SZ.002352', 'SZ.002475',
]

print(f"📊 股票池: {len(STOCK_POOL)} 只A股")


# ============================================================
# 配置参数（HPO最优值）
# ============================================================
@dataclass
class RDConfig:
    """RD-Agent配置（Optuna HPO最优参数）"""
    population_size: int = 75
    n_generations: int = 40
    crossover_rate: float = 0.538
    mutation_rate: float = 0.317
    elite_ratio: float = 0.198
    max_expr_depth: int = 7
    min_ic_threshold: float = 0.02
    target: str = 'return_next_close'
    
    # 算子池
    operators: Tuple[str, ...] = (
        'Ref', 'Mean', 'Std', 'Sum', 'EMA', 'Max', 'Min',
        'Add', 'Sub', 'Mul', 'Div', 'Abs', 'Log',
        'If', 'And', 'Lt', 'Le', 'Gt', 'Ge'
    )
    
    # 字段池
    fields: Tuple[str, ...] = ('$close', '$open', '$high', '$low', '$volume')
    
    # 常数池
    constants: Tuple[float, ...] = (1, 2, 3, 5, 10, 15, 20, 30, 60)


# ============================================================
# Futu 真实数据获取
# ============================================================
class FutuDataFetcher:
    """从 FutuOpenD 获取真实日K数据"""
    
    def __init__(self, host: str = FUTU_HOST, port: int = FUTU_PORT):
        self.host = host
        self.port = port
        self._ctx: Optional[OpenQuoteContext] = None
    
    def connect(self) -> bool:
        if not FUTU_AVAILABLE:
            print("[FutuDataFetcher] ❌ Futu SDK 不可用")
            return False
        try:
            self._ctx = OpenQuoteContext(self.host, self.port)
            ret, data = self._ctx.get_user_info()
            if ret != 0:
                print(f"[FutuDataFetcher] ❌ 连接失败: {data}")
                return False
            print(f"[FutuDataFetcher] ✅ 连接成功 UID={data.get('user_id', '?')}")
            return True
        except Exception as e:
            print(f"[FutuDataFetcher] ❌ 连接异常: {e}")
            return False
    
    def fetch_history_kline(self, code: str, days: int = 252) -> Optional[pd.DataFrame]:
        """获取单只股票历史日K（自动分页）"""
        if not self._ctx:
            return None
        
        all_data = []
        page_req_key = None
        
        while True:
            try:
                if page_req_key is None:
                    ret, data, page_req_key = self._ctx.request_history_kline(
                        code, ktype='K_DAY', max_count=min(days, 1000), autype='qfq'
                    )
                else:
                    ret, data, page_req_key = self._ctx.request_history_kline(
                        code, ktype='K_DAY', max_count=min(days, 1000),
                        autype='qfq', page_req_key=page_req_key
                    )
                
                if ret != 0 or data is None or len(data) == 0:
                    break
                
                all_data.append(data)
                
                if page_req_key is None or page_req_key == '':
                    break
                
            except Exception as e:
                print(f"  ⚠️  {code} 异常: {e}")
                break
        
        if not all_data:
            return None
        
        df = pd.concat(all_data, ignore_index=True)
        df = df.drop_duplicates(subset=['time_key'])
        df = df.sort_values('time_key').tail(days).reset_index(drop=True)
        return df
    
    def fetch_all_stocks(self, codes: List[str], days: int = 252,
                         batch_sleep: float = 0.3) -> pd.DataFrame:
        """批量获取多只股票数据，合并为qlib格式DataFrame"""
        all_rows = []
        success_count = 0
        
        for i, code in enumerate(codes):
            print(f"  [{i+1}/{len(codes)}] 拉取 {code} ...", end=" ", flush=True)
            
            try:
                df = self.fetch_history_kline(code, days=days)
                if df is None or len(df) < 60:
                    print(f"跳过（数据不足: {len(df) if df is not None else 0}条）")
                    continue
                
                # 转换为qlib格式
                df_clean = pd.DataFrame({
                    'ts_code': code,
                    'trade_date': df['time_key'].astype(str).str.replace('-', ''),
                    'open': df['open'].astype(float),
                    'high': df['high'].astype(float),
                    'low': df['low'].astype(float),
                    'close': df['close'].astype(float),
                    'volume': df['volume'].astype(float),
                })
                
                all_rows.append(df_clean)
                success_count += 1
                print(f"✅ {len(df_clean)}条")
                
            except Exception as e:
                print(f"❌ {e}")
            
            # 避免请求过快
            time.sleep(batch_sleep)
        
        if not all_rows:
            raise RuntimeError("未能获取任何股票数据！请检查 FutuOpenD 是否运行。")
        
        result = pd.concat(all_rows, ignore_index=True)
        print(f"\n✅ 成功获取 {success_count}/{len(codes)} 只股票, 共 {len(result)} 条记录")
        return result
    
    def close(self):
        if self._ctx:
            self._ctx.close()
            self._ctx = None


# ============================================================
# 基因编码：qlib表达式
# ============================================================
class FactorGene:
    """因子基因"""
    
    def __init__(self, expression: str, config: RDConfig):
        self.expression = expression
        self.config = config
        self.fitness: Optional[float] = None
        self.ic: Optional[float] = None
        self.ir: Optional[float] = None
        self.rank_ic: Optional[float] = None
        self.stability: Optional[float] = None
        self.n_evaluated: int = 0
    
    def __repr__(self):
        return f"FactorGene(expr='{self.expression[:50]}', IC={self.ic:.4f}, IR={self.ir:.4f})"
    
    @classmethod
    def random_gene(cls, config: RDConfig) -> 'FactorGene':
        expr = cls._random_expr(config, depth=0)
        return cls(expr, config)
    
    @classmethod
    def _random_expr(cls, config: RDConfig, depth: int) -> str:
        if depth >= config.max_expr_depth:
            if random.random() < 0.7:
                return random.choice(config.fields)
            else:
                return str(random.choice(config.constants))
        
        op = random.choice(config.operators)
        
        if op in ('Ref', 'Mean', 'Std', 'Sum', 'EMA'):
            field = random.choice(config.fields)
            const = random.choice(config.constants)
            return f"{op}({field}, {const})"
        
        elif op in ('Max', 'Min', 'Add', 'Sub', 'Mul', 'Div', 'And', 'Lt', 'Le', 'Gt', 'Ge'):
            left = cls._random_expr(config, depth + 1)
            right = cls._random_expr(config, depth + 1)
            return f"{op}({left}, {right})"
        
        elif op == 'Abs':
            return f"Abs({cls._random_expr(config, depth + 1)})"
        elif op == 'Log':
            return f"Log({cls._random_expr(config, depth + 1)})"
        elif op == 'If':
            cond = cls._random_expr(config, depth + 1)
            true_b = cls._random_expr(config, depth + 1)
            false_b = cls._random_expr(config, depth + 1)
            return f"If({cond}, {true_b}, {false_b})"
        else:
            return random.choice(config.fields)


# ============================================================
# 适应度评估（跨截面IC + 时序IR）
# ============================================================
class FitnessEvaluator:
    """适应度评估器 — 跨截面IC + 时序IR + Rank IC"""
    
    def __init__(self, data: pd.DataFrame, config: RDConfig):
        self.data = data.copy().sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
        self.config = config
        
        # 预计算目标：次日收益率
        self.data['return_next_close'] = (
            self.data.groupby('ts_code')['close']
            .pct_change(1)
            .shift(-1)
        )
        
        # 标准化列名
        rename = {}
        for c in self.data.columns:
            if c.lower() in ('open', 'high', 'low', 'close', 'volume'):
                rename[c] = f'${c.lower()}'
        if rename:
            self.data = self.data.rename(columns=rename)
    
    def evaluate(self, gene: FactorGene) -> float:
        if gene.fitness is not None:
            return gene.fitness
        
        try:
            factor_values = self._calculate_factor(gene.expression)
            
            if factor_values is None:
                gene.fitness = -999
                return gene.fitness
            
            target = self.data['return_next_close'].values
            mask = ~(np.isnan(factor_values) | np.isnan(target) | np.isinf(factor_values) | np.isinf(target))
            
            if mask.sum() < 100:
                gene.fitness = -999
                return gene.fitness
            
            # ── Pearson IC（跨截面平均）──
            ic_by_date = []
            self.data['__factor__'] = factor_values
            
            for _, grp in self.data[mask].groupby('trade_date'):
                if len(grp) < 5:
                    continue
                fv = grp['__factor__'].values
                tv = grp[self.config.target].values
                if np.std(fv) < 1e-10 or np.std(tv) < 1e-10:
                    continue
                day_ic = np.corrcoef(fv, tv)[0, 1]
                if not np.isnan(day_ic) and not np.isinf(day_ic):
                    ic_by_date.append(day_ic)
            
            if len(ic_by_date) < 10:
                gene.fitness = -999
                return gene.fitness
            
            ic_mean = np.mean(ic_by_date)
            
            if abs(ic_mean) < self.config.min_ic_threshold:
                gene.fitness = -999
                return gene.fitness
            
            # ── Rank IC（Spearman）──
            from scipy.stats import spearmanr, rankdata
            # 取最后可用的截面
            last_date = self.data[mask]['trade_date'].max()
            last_grp = self.data[(self.data['trade_date'] == last_date) & mask]
            if len(last_grp) >= 5:
                rank_ic, _ = spearmanr(last_grp['__factor__'].values,
                                        last_grp[self.config.target].values)
                if np.isnan(rank_ic):
                    rank_ic = 0.0
            else:
                rank_ic = 0.0
            
            # ── IR = IC_mean / IC_std ──
            ic_std = np.std(ic_by_date) if len(ic_by_date) > 1 else 0.001
            ir = abs(ic_mean) / max(ic_std, 0.001)
            
            # ── 稳定性 ──
            stability = abs(ic_mean) / max(ic_std, 0.001)
            
            gene.ic = ic_mean
            gene.rank_ic = rank_ic
            gene.ir = ir
            gene.stability = stability
            gene.n_evaluated = 1
            
            # 综合适应度 = |IC| × IR × stability
            gene.fitness = abs(ic_mean) * min(ir, 5) * min(stability, 3)
            
        except Exception as e:
            gene.fitness = -999
        
        return gene.fitness
    
    def _calculate_factor(self, expression: str) -> Optional[np.ndarray]:
        try:
            parser = QlibExpressionParser(self.data)
            return parser.evaluate(expression)
        except:
            return None


# ============================================================
# 遗传操作
# ============================================================
class GeneticOperator:
    def __init__(self, config: RDConfig):
        self.config = config
    
    def crossover(self, p1: FactorGene, p2: FactorGene) -> Tuple[FactorGene, FactorGene]:
        if random.random() > self.config.crossover_rate:
            return FactorGene.random_gene(self.config), FactorGene.random_gene(self.config)
        
        sub1 = self._extract_sub_exprs(p1.expression)
        sub2 = self._extract_sub_exprs(p2.expression)
        
        if not sub1 or not sub2:
            return FactorGene.random_gene(self.config), FactorGene.random_gene(self.config)
        
        s1 = random.choice(sub1)
        s2 = random.choice(sub2)
        
        c1_expr = p1.expression.replace(s1, s2, 1)
        c2_expr = p2.expression.replace(s2, s1, 1)
        
        # 如果交叉后表达式没变或重复，强制变异一个
        if c1_expr == p1.expression or c1_expr == p2.expression:
            c1_expr = FactorGene._random_expr(self.config, depth=0)
        if c2_expr == p1.expression or c2_expr == p2.expression:
            c2_expr = FactorGene._random_expr(self.config, depth=0)
        
        return FactorGene(c1_expr, self.config), FactorGene(c2_expr, self.config)
    
    def mutate(self, gene: FactorGene) -> FactorGene:
        if random.random() > self.config.mutation_rate:
            return gene
        
        sub_exprs = self._extract_sub_exprs(gene.expression)
        if not sub_exprs:
            return FactorGene.random_gene(self.config)
        
        target = random.choice(sub_exprs)
        replacement = FactorGene._random_expr(self.config, depth=0)
        new_expr = gene.expression.replace(target, replacement, 1)
        return FactorGene(new_expr, self.config)
    
    def _extract_sub_exprs(self, expr: str) -> List[str]:
        sub_exprs = []
        depth = 0
        start = 0
        for i, c in enumerate(expr):
            if c == '(':
                if depth == 0:
                    start = i
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    sub_exprs.append(expr[start:i+1])
        return sub_exprs or [expr]


# ============================================================
# RD-Agent 主引擎
# ============================================================
class RDAgent:
    def __init__(self, data: pd.DataFrame, config: Optional[RDConfig] = None):
        self.config = config or RDConfig()
        self.evaluator = FitnessEvaluator(data, self.config)
        self.genetic = GeneticOperator(self.config)
        self.population: List[FactorGene] = []
        self.generation_history: List[Dict] = []
    
    def initialize_population(self):
        print(f"🌱 初始化种群 (size={self.config.population_size})...")
        self.population = [FactorGene.random_gene(self.config)
                           for _ in range(self.config.population_size)]
    
    def evolve(self) -> List[FactorGene]:
        self.initialize_population()
        
        for gen in range(self.config.n_generations):
            print(f"\n🧬 第 {gen+1}/{self.config.n_generations} 代进化...")
            
            fitness_scores = []
            for i, gene in enumerate(self.population):
                score = self.evaluator.evaluate(gene)
                fitness_scores.append(score)
            
            sorted_idx = np.argsort(fitness_scores)[::-1]
            self.population = [self.population[i] for i in sorted_idx]
            
            valid = [s for s in fitness_scores if s > -900]
            best = self.population[0]
            
            # 统计多样性
            unique_exprs = len(set(g.expression for g in self.population))
            
            stats = {
                'generation': gen + 1,
                'best_fitness': best.fitness or -999,
                'mean_fitness': np.mean(valid) if valid else -999,
                'best_ic': best.ic,
                'best_ir': best.ir,
                'best_expr': best.expression,
                'n_valid': len(valid),
            }
            self.generation_history.append(stats)
            
            ic_str = f"{best.ic:+.4f}" if best.ic is not None else "N/A"
            ir_str = f"{best.ir:.2f}" if best.ir is not None else "N/A"
            print(f"  最佳适应度: {stats['best_fitness']:.4f} | IC={ic_str} | IR={ir_str} | 多样性:{unique_exprs}/{len(self.population)}")
            print(f"  平均适应度: {stats['mean_fitness']:.4f} | 有效: {stats['n_valid']}/{len(self.population)}")
            print(f"  最佳表达式: {stats['best_expr'][:80]}...")
            
            # 精英保留（去重）
            n_elite = max(2, int(self.config.elite_ratio * self.config.population_size))
            elites = []
            seen = set()
            for g in self.population:
                if g.expression not in seen and len(elites) < n_elite:
                    elites.append(g)
                    seen.add(g.expression)
            
            # 注入随机基因保持多样性
            while len(elites) < n_elite:
                elites.append(FactorGene.random_gene(self.config))
            
            # 新一代
            new_pop = elites.copy()
            while len(new_pop) < self.config.population_size:
                p1 = self._tournament_select()
                p2 = self._tournament_select()
                c1, c2 = self.genetic.crossover(p1, p2)
                c1 = self.genetic.mutate(c1)
                c2 = self.genetic.mutate(c2)
                new_pop.extend([c1, c2])
            
            self.population = new_pop[:self.config.population_size]
        
        # 最终评估
        print("\n🏆 最终评估...")
        for gene in self.population:
            self.evaluator.evaluate(gene)
        
        sorted_idx = np.argsort([g.fitness or -999 for g in self.population])[::-1]
        self.population = [self.population[i] for i in sorted_idx]
        
        return self.population[:10]
    
    def _tournament_select(self, tournament_size: int = 3) -> FactorGene:
        contestants = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(contestants, key=lambda g: g.fitness if g.fitness is not None else -999)
    
    def report(self, top_n: int = 10):
        print("\n" + "=" * 90)
        print("  🏆 RD-Agent 真实数据因子挖掘报告")
        print("=" * 90)
        
        print(f"\n📊 配置参数（HPO最优）:")
        print(f"  population_size={self.config.population_size} | n_generations={self.config.n_generations}")
        print(f"  crossover_rate={self.config.crossover_rate} | mutation_rate={self.config.mutation_rate}")
        print(f"  elite_ratio={self.config.elite_ratio} | max_expr_depth={self.config.max_expr_depth}")
        
        print(f"\n🏆 Top {top_n} 因子:")
        print(f"  {'排名':>4} | {'IC':>8} | {'RankIC':>8} | {'IR':>8} | {'Stability':>9} | {'表达式'}")
        print("  " + "-" * 85)
        
        for i, gene in enumerate(self.population[:top_n]):
            ic = f"{gene.ic:+.4f}" if gene.ic is not None else "N/A"
            ric = f"{gene.rank_ic:+.4f}" if gene.rank_ic is not None else "N/A"
            ir = f"{gene.ir:.4f}" if gene.ir is not None else "N/A"
            st = f"{gene.stability:.4f}" if gene.stability is not None else "N/A"
            expr = gene.expression[:55] + "..." if len(gene.expression) > 55 else gene.expression
            print(f"  {i+1:>4} | {ic:>8} | {ric:>8} | {ir:>8} | {st:>9} | {expr}")
        
        print(f"\n📈 进化曲线（每5代）:")
        print(f"  {'代数':>4} | {'最佳适应度':>12} | {'平均适应度':>12} | {'最佳IC':>8}")
        print("  " + "-" * 50)
        for s in self.generation_history[::5]:
            print(f"  {s['generation']:>4} | {s['best_fitness']:>11.4f} | "
                  f"{s['mean_fitness']:>11.4f} | {s['best_ic'] or 0:>+7.4f}")
        
        print("\n" + "=" * 90)


# ============================================================
# 主入口
# ============================================================
def main():
    random.seed(42)
    np.random.seed(42)
    
    print("=" * 90)
    print("  RD-Agent 自动化因子挖掘 — 真实市场数据版")
    print("=" * 90)
    
    # ── 1. 获取真实数据 ──
    print("\n📡 [1/4] 连接 FutuOpenD 获取真实日K数据...")
    fetcher = FutuDataFetcher()
    
    if not fetcher.connect():
        print("❌ 无法连接 FutuOpenD，退出。请确保 FutuOpenD 运行在 127.0.0.1:11111")
        sys.exit(1)
    
    try:
        data = fetcher.fetch_all_stocks(STOCK_POOL, days=252, batch_sleep=0.3)
    finally:
        fetcher.close()
    
    print(f"\n📊 数据概览:")
    print(f"  股票数: {data['ts_code'].nunique()}")
    print(f"  日期范围: {data['trade_date'].min()} ~ {data['trade_date'].max()}")
    print(f"  总记录数: {len(data)}")
    
    # ── 2. HPO最优参数 ──
    config = RDConfig(
        population_size=75,
        n_generations=40,
        crossover_rate=0.538,
        mutation_rate=0.317,
        elite_ratio=0.198,
        max_expr_depth=7,
    )
    
    print(f"\n🔧 [2/4] 配置参数（Optuna HPO最优）:")
    print(f"  population_size={config.population_size}")
    print(f"  n_generations={config.n_generations}")
    print(f"  crossover_rate={config.crossover_rate}")
    print(f"  mutation_rate={config.mutation_rate}")
    print(f"  elite_ratio={config.elite_ratio}")
    print(f"  max_expr_depth={config.max_expr_depth}")
    
    # ── 3. 启动进化 ──
    print(f"\n🧬 [3/4] 启动RD-Agent遗传算法进化（{config.n_generations}代 × {config.population_size}个体）...")
    agent = RDAgent(data, config)
    top_factors = agent.evolve()
    
    # ── 4. 报告 & 保存 ──
    print(f"\n📋 [4/4] 生成报告并保存...")
    agent.report(top_n=10)
    
    results = []
    for i, gene in enumerate(top_factors):
        results.append({
            'rank': i + 1,
            'expression': gene.expression,
            'ic': round(gene.ic, 6) if gene.ic else None,
            'rank_ic': round(gene.rank_ic, 6) if gene.rank_ic else None,
            'ir': round(gene.ir, 6) if gene.ir else None,
            'stability': round(gene.stability, 6) if gene.stability else None,
            'fitness': round(gene.fitness, 6) if gene.fitness else None,
        })
    
    df_results = pd.DataFrame(results)
    output_path = os.path.join(PROJECT_ROOT, 'factors_real_top10.csv')
    df_results.to_csv(output_path, index=False)
    print(f"\n💾 结果已保存至 {output_path}")
    
    # 打印最终Top10
    print("\n" + "=" * 90)
    print("  🎯 Top 10 因子（真实数据挖掘结果）")
    print("=" * 90)
    for r in results:
        ic_s = f"{r['ic']:+.4f}" if r['ic'] is not None else "N/A"
        ric_s = f"{r['rank_ic']:+.4f}" if r['rank_ic'] is not None else "N/A"
        ir_s = f"{r['ir']:.4f}" if r['ir'] is not None else "N/A"
        print(f"  #{r['rank']:>2} | IC={ic_s} | RankIC={ric_s} | IR={ir_s} | {r['expression'][:70]}")
    print("=" * 90)
    print("\n✅ RD-Agent 真实数据因子挖掘完成！")


if __name__ == '__main__':
    main()
