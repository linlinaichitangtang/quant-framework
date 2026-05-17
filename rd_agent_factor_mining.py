#!/usr/bin/env python3
"""
Phase 3: RD-Agent 自动化因子挖掘框架
基于遗传算法 + qlib表达式引擎的自动因子发现

核心思路：
1. 基因编码：qlib表达式字符串
2. 适应度：IC/IR值（信息系数）
3. 遗传操作：交叉、变异、选择
4. 结果输出：高IC因子表达式 + 回测验证
"""

import sys
import os
import random
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# ── 项目路径 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from data.qlib_adapter import QlibFactorEngine, QlibExpressionParser


# ============================================================
# 配置参数
# ============================================================
@dataclass
class RDConfig:
    """RD-Agent配置"""
    population_size: int = 100          # 种群大小
    n_generations: int = 50             # 迭代代数
    crossover_rate: float = 0.7         # 交叉概率
    mutation_rate: float = 0.2          # 变异概率
    elite_ratio: float = 0.1            # 精英保留比例
    max_expr_depth: int = 5             # 最大表达式深度
    min_ic_threshold: float = 0.02      # 最小IC阈值
    target: str = 'return_next_close'   # 预测目标
    
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
        return f"FactorGene(expr='{self.expression}', IC={self.ic:.4f}, IR={self.ir:.4f})"
    
    @classmethod
    def random_gene(cls, config: RDConfig) -> 'FactorGene':
        """随机生成基因"""
        expr = cls._random_expr(config, depth=0)
        return cls(expr, config)
    
    @classmethod
    def _random_expr(cls, config: RDConfig, depth: int) -> str:
        """递归生成随机表达式"""
        if depth >= config.max_expr_depth:
            # 叶子节点：字段或常数
            if random.random() < 0.7:
                return random.choice(config.fields)
            else:
                return str(random.choice(config.constants))
        
        # 内部节点：运算符
        op = random.choice(config.operators)
        
        if op in ('Ref', 'Mean', 'Std', 'Sum', 'EMA'):
            # 二元：字段 + 常数
            field = random.choice(config.fields)
            const = random.choice(config.constants)
            return f"{op}({field}, {const})"
        
        elif op in ('Max', 'Min', 'Add', 'Sub', 'Mul', 'Div', 'And', 'Lt', 'Le', 'Gt', 'Ge'):
            # 二元：递归生成两个子表达式
            left = cls._random_expr(config, depth + 1)
            right = cls._random_expr(config, depth + 1)
            return f"{op}({left}, {right})"
        
        elif op == 'Abs':
            inner = cls._random_expr(config, depth + 1)
            return f"Abs({inner})"
        
        elif op == 'Log':
            inner = cls._random_expr(config, depth + 1)
            return f"Log({inner})"
        
        elif op == 'If':
            cond = cls._random_expr(config, depth + 1)
            true_branch = cls._random_expr(config, depth + 1)
            false_branch = cls._random_expr(config, depth + 1)
            return f"If({cond}, {true_branch}, {false_branch})"
        
        else:
            return random.choice(config.fields)


# ============================================================
# 适应度评估
# ============================================================
class FitnessEvaluator:
    """适应度评估器"""
    
    def __init__(self, data: pd.DataFrame, config: RDConfig):
        self.data = data.copy()
        self.config = config
        self.engine = QlibFactorEngine()
        
        # 预计算目标收益率
        if config.target not in self.data.columns:
            # 计算次日收益率
            self.data = self.data.sort_values(['ts_code', 'trade_date'])
            self.data['return_next_close'] = self.data.groupby('ts_code')['close'].pct_change(1).shift(-1)
        
        self.target = self.data[config.target].values
    
    def evaluate(self, gene: FactorGene) -> float:
        """评估基因适应度"""
        if gene.fitness is not None:
            return gene.fitness
        
        try:
            # 计算因子值
            factor_values = self._calculate_factor(gene.expression)
            
            if factor_values is None or len(factor_values) == 0:
                gene.fitness = -999
                return gene.fitness
            
            # 计算IC (Pearson相关系数)
            mask = ~(np.isnan(factor_values) | np.isnan(self.target))
            if mask.sum() < 30:
                gene.fitness = -999
                return gene.fitness
            
            ic = np.corrcoef(factor_values[mask], self.target[mask])[0, 1]
            
            if np.isnan(ic):
                gene.fitness = -999
                return gene.fitness
            
            # 计算Rank IC (Spearman相关系数)
            from scipy.stats import spearmanr
            rank_ic, _ = spearmanr(factor_values[mask], self.target[mask])
            
            # 计算IR (IC / IC标准差)
            # 按月分组计算IC稳定性
            ic_by_month = []
            self.data['factor'] = factor_values
            self.data['yearmonth'] = self.data['trade_date'].astype(str).str[:6]
            for _, group in self.data.groupby('yearmonth'):
                if len(group) > 10:
                    m_ic = np.corrcoef(group['factor'].values, group[self.config.target].values)[0, 1]
                    if not np.isnan(m_ic):
                        ic_by_month.append(m_ic)
            
            ic_std = np.std(ic_by_month) if len(ic_by_month) > 1 else 0.01
            ir = abs(ic) / max(ic_std, 0.001)
            
            # 稳定性：IC均值 / IC标准差
            stability = abs(np.mean(ic_by_month)) / max(ic_std, 0.001) if len(ic_by_month) > 1 else 0
            
            # 综合适应度
            gene.ic = ic
            gene.rank_ic = rank_ic
            gene.ir = ir
            gene.stability = stability
            
            # 适应度 = |IC| * IR * stability (多维度综合)
            if abs(ic) < self.config.min_ic_threshold:
                gene.fitness = -999  # 淘汰低IC因子
            else:
                gene.fitness = abs(ic) * min(ir, 5) * min(stability, 3)
            
            gene.n_evaluated = 1
            
        except Exception as e:
            gene.fitness = -999
        
        return gene.fitness
    
    def _calculate_factor(self, expression: str) -> Optional[np.ndarray]:
        """计算因子值"""
        try:
            # 标准化列名
            df = self.data.copy()
            rename = {}
            for c in df.columns:
                if c.lower() in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                    rename[c] = f'${c.lower()}'
            if rename:
                df = df.rename(columns=rename)
            
            parser = QlibExpressionParser(df)
            return parser.evaluate(expression)
        except:
            return None


# ============================================================
# 遗传操作
# ============================================================
class GeneticOperator:
    """遗传算子"""
    
    def __init__(self, config: RDConfig):
        self.config = config
    
    def crossover(self, parent1: FactorGene, parent2: FactorGene) -> Tuple[FactorGene, FactorGene]:
        """交叉操作：交换子树"""
        if random.random() > self.config.crossover_rate:
            return parent1, parent2
        
        # 解析表达式树（简化版：按逗号分割交换子表达式）
        expr1 = parent1.expression
        expr2 = parent2.expression
        
        # 找到可交换的子表达式
        sub_exprs1 = self._extract_sub_exprs(expr1)
        sub_exprs2 = self._extract_sub_exprs(expr2)
        
        if not sub_exprs1 or not sub_exprs2:
            return parent1, parent2
        
        # 随机选择子表达式交换
        sub1 = random.choice(sub_exprs1)
        sub2 = random.choice(sub_exprs2)
        
        child1_expr = expr1.replace(sub1, sub2, 1)
        child2_expr = expr2.replace(sub2, sub1, 1)
        
        child1 = FactorGene(child1_expr, self.config)
        child2 = FactorGene(child2_expr, self.config)
        
        return child1, child2
    
    def mutate(self, gene: FactorGene) -> FactorGene:
        """变异操作：替换子树"""
        if random.random() > self.config.mutation_rate:
            return gene
        
        expr = gene.expression
        sub_exprs = self._extract_sub_exprs(expr)
        
        if not sub_exprs:
            # 完全重新生成
            return FactorGene.random_gene(self.config)
        
        # 随机替换一个子表达式
        target = random.choice(sub_exprs)
        replacement = FactorGene._random_expr(self.config, depth=0)
        new_expr = expr.replace(target, replacement, 1)
        
        return FactorGene(new_expr, self.config)
    
    def _extract_sub_exprs(self, expr: str) -> List[str]:
        """提取子表达式列表"""
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
        
        # 如果没有找到子表达式，返回整个表达式
        if not sub_exprs:
            sub_exprs = [expr]
        
        return sub_exprs


# ============================================================
# RD-Agent主引擎
# ============================================================
class RDAgent:
    """
    RD-Agent: R&D Agent for Automated Factor Mining
    自动化因子挖掘智能体
    """
    
    def __init__(self, data: pd.DataFrame, config: Optional[RDConfig] = None):
        self.config = config or RDConfig()
        self.evaluator = FitnessEvaluator(data, self.config)
        self.genetic = GeneticOperator(self.config)
        self.population: List[FactorGene] = []
        self.generation_history: List[Dict] = []
        self.best_factors: List[FactorGene] = []
    
    def initialize_population(self):
        """初始化种群"""
        print(f"🌱 初始化种群 (size={self.config.population_size})...")
        self.population = []
        for i in range(self.config.population_size):
            gene = FactorGene.random_gene(self.config)
            self.population.append(gene)
            if (i + 1) % 20 == 0:
                print(f"  已生成 {i+1}/{self.config.population_size} 个基因")
    
    def evolve(self) -> List[FactorGene]:
        """进化主循环"""
        self.initialize_population()
        
        for gen in range(self.config.n_generations):
            print(f"\n🧬 第 {gen+1}/{self.config.n_generations} 代进化...")
            
            # 评估适应度
            fitness_scores = []
            for i, gene in enumerate(self.population):
                score = self.evaluator.evaluate(gene)
                fitness_scores.append(score)
                if (i + 1) % 20 == 0:
                    print(f"  已评估 {i+1}/{len(self.population)} 个基因")
            
            # 排序
            sorted_indices = np.argsort(fitness_scores)[::-1]
            self.population = [self.population[i] for i in sorted_indices]
            
            # 记录统计
            valid_scores = [s for s in fitness_scores if s > -900]
            stats = {
                'generation': gen + 1,
                'best_fitness': fitness_scores[sorted_indices[0]],
                'mean_fitness': np.mean(valid_scores) if valid_scores else -999,
                'median_fitness': np.median(valid_scores) if valid_scores else -999,
                'best_ic': self.population[0].ic,
                'best_ir': self.population[0].ir,
                'best_expr': self.population[0].expression,
                'n_valid': len(valid_scores),
            }
            self.generation_history.append(stats)
            
            print(f"  最佳适应度: {stats['best_fitness']:.4f} | "
                  f"IC={stats['best_ic']:.4f} | IR={stats['best_ir']:.4f}")
            print(f"  平均适应度: {stats['mean_fitness']:.4f} | 有效基因: {stats['n_valid']}/{len(self.population)}")
            print(f"  最佳表达式: {stats['best_expr'][:80]}...")
            
            # 精英保留
            n_elite = int(self.config.elite_ratio * self.config.population_size)
            elites = self.population[:n_elite]
            
            # 生成新一代
            new_population = elites.copy()
            
            while len(new_population) < self.config.population_size:
                # 锦标赛选择
                parent1 = self._tournament_select()
                parent2 = self._tournament_select()
                
                # 交叉
                child1, child2 = self.genetic.crossover(parent1, parent2)
                
                # 变异
                child1 = self.genetic.mutate(child1)
                child2 = self.genetic.mutate(child2)
                
                new_population.extend([child1, child2])
            
            self.population = new_population[:self.config.population_size]
            
            # 保存最佳因子
            if stats['best_ic'] and abs(stats['best_ic']) > 0.03:
                self.best_factors.append(FactorGene(stats['best_expr'], self.config))
        
        # 最终评估
        print("\n🏆 最终评估最佳因子...")
        final_scores = []
        for gene in self.population:
            score = self.evaluator.evaluate(gene)
            final_scores.append(score)
        
        sorted_indices = np.argsort(final_scores)[::-1]
        self.population = [self.population[i] for i in sorted_indices]
        
        return self.population[:10]  # 返回Top10
    
    def _tournament_select(self, tournament_size: int = 3) -> FactorGene:
        """锦标赛选择"""
        contestants = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(contestants, key=lambda g: g.fitness if g.fitness is not None else -999)
    
    def report(self, top_n: int = 10):
        """输出挖掘报告"""
        print("\n" + "=" * 80)
        print("  RD-Agent 自动化因子挖掘报告")
        print("=" * 80)
        
        print(f"\n📊 进化统计:")
        print(f"  总代数: {self.config.n_generations}")
        print(f"  种群大小: {self.config.population_size}")
        print(f"  交叉率: {self.config.crossover_rate}")
        print(f"  变异率: {self.config.mutation_rate}")
        
        print(f"\n🏆 Top {top_n} 因子:")
        print(f"  {'排名':>4} | {'IC':>8} | {'RankIC':>8} | {'IR':>8} | {'表达式'}")
        print("  " + "-" * 75)
        
        for i, gene in enumerate(self.population[:top_n]):
            ic = gene.ic if gene.ic else 0
            rank_ic = gene.rank_ic if gene.rank_ic else 0
            ir = gene.ir if gene.ir else 0
            expr = gene.expression[:60] + "..." if len(gene.expression) > 60 else gene.expression
            print(f"  {i+1:>4} | {ic:>+7.4f} | {rank_ic:>+7.4f} | {ir:>7.2f} | {expr}")
        
        # 进化曲线
        print(f"\n📈 进化曲线:")
        print(f"  {'代数':>4} | {'最佳适应度':>12} | {'平均适应度':>12} | {'最佳IC':>8}")
        print("  " + "-" * 50)
        for stats in self.generation_history[::5]:  # 每5代显示
            print(f"  {stats['generation']:>4} | {stats['best_fitness']:>11.4f} | "
                  f"{stats['mean_fitness']:>11.4f} | {stats['best_ic'] or 0:>+7.4f}")
        
        print("\n" + "=" * 80)


# ============================================================
# 数据加载
# ============================================================
def load_data_for_mining() -> pd.DataFrame:
    """加载用于因子挖掘的数据"""
    try:
        token = os.environ.get('TUSHARE_TOKEN')
        if token:
            from ml_strategy.data_fetcher import TushareDataFetcher
            fetcher = TushareDataFetcher(token)
            codes = ['000001.SZ', '000002.SZ', '600519.SH', '601318.SH', '600036.SH']
            stock_data = fetcher.get_all_stock_daily(
                codes, '20220101', '20241231', cache_dir='./cache'
            )
            all_rows = []
            for code, sdf in stock_data.items():
                sdf = sdf.copy()
                sdf['ts_code'] = code
                all_rows.append(sdf)
            df = pd.concat(all_rows, ignore_index=True)
            print(f"✅ 加载真实数据: {len(df)} 条记录")
            return df
    except Exception as e:
        print(f"⚠️ 真实数据加载失败: {e}")
    
    # 模拟数据
    print("⚠️ 使用模拟数据")
    from run_backtest_compare_v2 import generate_mock_stock_data
    return generate_mock_stock_data(n_stocks=30, start_date='2022-01-01', end_date='2024-12-31')


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 80)
    print("Phase 3: RD-Agent 自动化因子挖掘")
    print("=" * 80)
    
    # 1. 加载数据
    print("\n[1/3] 加载数据...")
    data = load_data_for_mining()
    
    # 2. 配置
    config = RDConfig(
        population_size=50,      # 小规模快速演示
        n_generations=20,
        min_ic_threshold=0.01,
    )
    
    # 3. 创建Agent并进化
    print("[2/3] 启动RD-Agent进化...")
    agent = RDAgent(data, config)
    top_factors = agent.evolve()
    
    # 4. 输出报告
    print("[3/3] 生成报告...")
    agent.report(top_n=10)
    
    # 5. 保存结果
    results = []
    for i, gene in enumerate(top_factors):
        results.append({
            'rank': i + 1,
            'expression': gene.expression,
            'ic': gene.ic,
            'rank_ic': gene.rank_ic,
            'ir': gene.ir,
            'stability': gene.stability,
            'fitness': gene.fitness,
        })
    
    df_results = pd.DataFrame(results)
    df_results.to_csv('rd_agent_factors.csv', index=False)
    print(f"\n💾 结果已保存至 rd_agent_factors.csv")
    
    print("\n" + "=" * 80)
    print("  RD-Agent 因子挖掘完成!")
    print("  下一步建议:")
    print("  1. 对Top因子进行回测验证")
    print("  2. 分析因子相关性，去除冗余")
    print("  3. 组合多个因子构建复合信号")
    print("=" * 80)


if __name__ == '__main__':
    main()
