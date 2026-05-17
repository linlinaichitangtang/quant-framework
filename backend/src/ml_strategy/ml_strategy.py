"""
机器学习驱动的A股尾盘选股策略
整合因子抽取、模型预测、选股决策
"""
import pandas as pd
import numpy as np
import joblib
from typing import List, Dict, Optional, Tuple
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from .factor_extractor import FactorExtractor
from .label_constructor import LabelConstructor


class MLStockPicker:
    """机器学习选股器"""
    
    def __init__(self, model_type: str = 'gbm', params: Optional[Dict] = None):
        """
        初始化选股器
        :param model_type: 模型类型 'gbm' 或 'rf'
        :param params: 模型参数
        """
        self.factor_extractor = FactorExtractor()
        self.label_constructor = LabelConstructor()
        self.model_type = model_type
        self.scaler = StandardScaler()
        self.factor_cols: Optional[List[str]] = None
        self.model = self._init_model(model_type, params)
        self.trained = False
    
    def _init_model(self, model_type: str, params: Optional[Dict]) -> object:
        """初始化模型"""
        default_params = {
            'n_estimators': 100,
            'learning_rate': 0.1,
            'max_depth': 3,
            'random_state': 42,
            'min_samples_split': 20,
            'min_samples_leaf': 5,
        }
        
        if params:
            default_params.update(params)
        
        if model_type == 'gbm':
            return GradientBoostingClassifier(**default_params)
        elif model_type == 'rf':
            default_params.pop('learning_rate', None)
            return RandomForestClassifier(**default_params)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def preprocess_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        """
        数据预处理：提取因子和标签
        :param df: 原始行情数据
        :return: (X, y, processed_df)
        """
        # 提取所有因子
        processed_df, factor_cols = self.factor_extractor.extract_all_factors(df)
        self.factor_cols = factor_cols
        
        # 构造标签（用次日最高价是否超过2%）
        processed_df = self.label_constructor.construct_label_with_open(processed_df)
        
        # 获取X和y
        X = processed_df[factor_cols].values
        y = processed_df['y'].values
        
        # 删除NaN
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        X = X[mask]
        y = y[mask]
        processed_df = processed_df[mask].copy()
        
        return X, y, processed_df
    
    def train(self, X: np.ndarray, y: np.ndarray, scale: bool = True) -> Dict:
        """
        训练模型
        :param X: 特征矩阵
        :param y: 标签
        :param scale: 是否标准化
        :return: 训练指标
        """
        if scale:
            X = self.scaler.fit_transform(X)
        else:
            self.scaler.fit(X)
        
        self.model.fit(X, y)
        self.trained = True
        
        # 计算训练集指标
        y_pred = self.model.predict(X)
        y_pred_proba = self.model.predict_proba(X)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, zero_division=0),
            'recall': recall_score(y, y_pred, zero_division=0),
            'f1': f1_score(y, y_pred, zero_division=0),
            'auc': roc_auc_score(y, y_pred_proba) if len(np.unique(y)) > 1 else np.nan
        }
        
        return metrics
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测正样本概率"""
        if not self.trained:
            raise ValueError("Model not trained yet")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)[:, 1]
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测标签"""
        if not self.trained:
            raise ValueError("Model not trained yet")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def select_stocks(self, daily_data: pd.DataFrame, 
                      top_n: int = 3, 
                      min_prob: float = 0.5) -> pd.DataFrame:
        """
        从当日候选股票中选股
        :param daily_data: 当日所有候选股票数据（已经计算好因子）
        :param top_n: 选几只
        :param min_prob: 最小概率要求
        :return: 选中的股票，按概率降序排列
        """
        if not self.trained:
            raise ValueError("Model not trained yet")
        
        # 确保所有因子都存在
        missing_cols = [col for col in self.factor_cols if col not in daily_data.columns]
        if missing_cols:
            raise ValueError(f"Missing factors: {missing_cols}")
        
        # 获取因子矩阵
        X = daily_data[self.factor_cols].values
        # 处理NaN
        X = np.where(np.isnan(X), np.nanmean(X, axis=0, keepdims=True), X)
        
        # 预测概率
        probs = self.predict_proba(X)
        result = daily_data.copy()
        result['up_probability'] = probs
        
        # 筛选概率大于最小值的，按概率降序排列，选top_n
        selected = result[result['up_probability'] >= min_prob].copy()
        selected = selected.sort_values('up_probability', ascending=False)
        
        if len(selected) > top_n:
            selected = selected.head(top_n)
        
        return selected
    
    def get_feature_importance(self) -> Optional[pd.DataFrame]:
        """获取特征重要性"""
        if not self.trained or self.factor_cols is None:
            return None
        
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            fi_df = pd.DataFrame({
                'feature': self.factor_cols,
                'importance': importance
            })
            fi_df = fi_df.sort_values('importance', ascending=False)
            return fi_df
        
        return None
    
    def save_model(self, path: str):
        """保存模型"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'factor_cols': self.factor_cols,
            'model_type': self.model_type,
            'trained': self.trained
        }
        joblib.dump(model_data, path)
    
    @classmethod
    def load_model(cls, path: str) -> 'MLStockPicker':
        """加载模型"""
        model_data = joblib.load(path)
        picker = cls(model_data['model_type'])
        picker.model = model_data['model']
        picker.scaler = model_data['scaler']
        picker.factor_cols = model_data['factor_cols']
        picker.trained = model_data['trained']
        return picker


class Backtester:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 1_000_000, 
                 commission: float = 0.0003, 
                 stamp_tax: float = 0.001,
                 slippage: float = 0.001):
        """
        初始化回测器
        :param initial_capital: 初始资金
        :param commission: 佣金费率 默认万3
        :param stamp_tax: 印花税 卖出收，默认千1
        :param slippage: 滑点 默认千1
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.stamp_tax = stamp_tax
        self.slippage = slippage
        
        # 回测结果
        self.reset()
    
    def reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.holdings: Dict[str, Dict] = {}  # 当前持仓 {code: info}
        self.trade_records: List[Dict] = []
        self.daily_values: List[Dict] = []
    
    def buy(self, date: str, code: str, price: float, 
            max_position_pct: float = 0.2) -> Dict:
        """
        买入
        :param date: 交易日期
        :param code: 股票代码
        :param price: 成交价格
        :param max_position_pct: 最大仓位占比
        :return: 交易信息
        """
        # 计算可买数量（手为单位，1手=100股）
        position_value = self.capital * max_position_pct
        # 考虑滑点，买入价格上浮
        buy_price = price * (1 + self.slippage)
        # 计算手续费
        commission = position_value * self.commission
        shares = int((position_value - commission) / buy_price / 100) * 100
        
        if shares <= 0:
            return {'success': False, 'reason': 'Insufficient capital'}
        
        # 实际花费
        cost = shares * buy_price + commission
        
        self.capital -= cost
        self.holdings[code] = {
            'date_bought': date,
            'price_bought': buy_price,
            'shares': shares,
            'cost_basis': cost
        }
        
        self.trade_records.append({
            'date': date,
            'action': 'buy',
            'code': code,
            'price': buy_price,
            'shares': shares,
            'cost': cost,
            'commission': commission
        })
        
        return {
            'success': True,
            'code': code,
            'shares': shares,
            'price': buy_price,
            'cost': cost
        }
    
    def sell(self, date: str, code: str, price: float) -> Dict:
        """
        卖出持仓
        :param date: 交易日期
        :param code: 股票代码
        :param price: 成交价格
        :return: 交易信息
        """
        if code not in self.holdings:
            return {'success': False, 'reason': 'Not in holdings'}
        
        holding = self.holdings[code]
        # 滑点，卖出价格下浮
        sell_price = price * (1 - self.slippage)
        shares = holding['shares']
        
        # 计算费用：佣金+印花税
        commission = shares * sell_price * self.commission
        stamp_tax = shares * sell_price * self.stamp_tax
        total_fees = commission + stamp_tax
        
        # 实际收入
        proceeds = shares * sell_price - total_fees
        self.capital += proceeds
        
        # 计算盈亏
        pnl = proceeds - holding['cost_basis']
        pnl_pct = pnl / holding['cost_basis']
        
        self.trade_records.append({
            'date': date,
            'action': 'sell',
            'code': code,
            'price': sell_price,
            'shares': shares,
            'proceeds': proceeds,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
        
        del self.holdings[code]
        
        return {
            'success': True,
            'code': code,
            'shares': shares,
            'price': sell_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        }
    
    def sell_all_holdings(self, date: str, price_map: Dict[str, float]) -> List[Dict]:
        """卖出所有持仓"""
        results = []
        codes = list(self.holdings.keys())
        for code in codes:
            if code in price_map:
                result = self.sell(date, code, price_map[code])
                results.append(result)
        return results
    
    def calculate_daily_value(self, date: str, price_map: Dict[str, float]) -> float:
        """计算当日总资产"""
        holdings_value = 0
        for code, holding in self.holdings.items():
            if code in price_map:
                current_price = price_map[code]
                holdings_value += holding['shares'] * current_price
        
        total_value = self.capital + holdings_value
        self.daily_values.append({
            'date': date,
            'cash': self.capital,
            'holdings_value': holdings_value,
            'total_value': total_value
        })
        return total_value
    
    def get_backtest_report(self) -> Dict:
        """生成回测报告"""
        if not self.daily_values:
            return {}
        
        # 转换为DataFrame
        daily_df = pd.DataFrame(self.daily_values)
        trades_df = pd.DataFrame(self.trade_records)
        
        # 总收益计算
        initial_value = self.initial_capital
        final_value = daily_df.iloc[-1]['total_value']
        total_return = (final_value - initial_value) / initial_value
        
        # 年化收益率
        n_days = len(daily_df)
        if n_days > 0:
            annual_return = (1 + total_return) ** (252 / n_days) - 1
        else:
            annual_return = 0
        
        # 每日收益率
        daily_df['daily_return'] = daily_df['total_value'].pct_change().fillna(0)
        
        # 最大回撤
        daily_df['cummax'] = daily_df['total_value'].cummax()
        daily_df['drawdown'] = (daily_df['total_value'] - daily_df['cummax']) / daily_df['cummax']
        max_drawdown = daily_df['drawdown'].min()
        
        # 夏普比率（假设无风险利率0）
        if daily_df['daily_return'].std() != 0:
            sharpe_ratio = np.sqrt(252) * daily_df['daily_return'].mean() / daily_df['daily_return'].std()
        else:
            sharpe_ratio = 0
        
        # 交易统计
        sells = trades_df[trades_df['action'] == 'sell']
        n_trades = len(sells)
        if n_trades > 0:
            win_rate = (sells['pnl'] > 0).sum() / n_trades
            avg_pnl = sells['pnl'].mean()
            avg_pnl_pct = sells['pnl_pct'].mean()
            # 盈亏比
            if (sells['pnl'] <= 0).sum() > 0:
                profit_mean = sells[sells['pnl'] > 0]['pnl'].mean()
                loss_mean = -sells[sells['pnl'] <= 0]['pnl'].mean()
                profit_loss_ratio = profit_mean / loss_mean if loss_mean > 0 else np.inf
            else:
                profit_loss_ratio = np.inf
        else:
            n_trades = 0
            win_rate = 0
            avg_pnl = 0
            avg_pnl_pct = 0
            profit_loss_ratio = 0
        
        report = {
            'initial_capital': initial_value,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'annual_return': annual_return,
            'annual_return_pct': annual_return * 100,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'sharpe_ratio': sharpe_ratio,
            'n_trades': n_trades,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'avg_pnl_pct': avg_pnl_pct * 100,
            'profit_loss_ratio': profit_loss_ratio,
            'daily_df': daily_df,
            'trades_df': trades_df
        }
        
        return report
    
    def print_report(self, report: Optional[Dict] = None):
        """打印回测报告"""
        if report is None:
            report = self.get_backtest_report()
        
        if not report:
            print("No backtest data available")
            return
        
        print("=" * 60)
        print("回测报告")
        print("=" * 60)
        print(f"初始资金: {report['initial_capital']:,.2f}")
        print(f"最终资金: {report['final_value']:,.2f}")
        print(f"总收益率: {report['total_return_pct']:.2f}%")
        print(f"年化收益率: {report['annual_return_pct']:.2f}%")
        print(f"最大回撤: {report['max_drawdown_pct']:.2f}%")
        print(f"夏普比率: {report['sharpe_ratio']:.3f}")
        print(f"总交易次数: {report['n_trades']}")
        if report['n_trades'] > 0:
            print(f"胜率: {report['win_rate']*100:.2f}%")
            print(f"平均单次盈亏: {report['avg_pnl']:.2f} ({report['avg_pnl_pct']:.2f}%)")
            print(f"盈亏比: {report['profit_loss_ratio']:.2f}")
        print("=" * 60)