"""
SHAP特征重要性分析模块
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import shap
from typing import Optional, List
from .ml_strategy import MLStockPicker


class SHAPAnalyzer:
    """SHAP分析器"""
    
    def __init__(self, model: MLStockPicker):
        """
        初始化SHAP分析器
        :param model: 训练好的ML选股模型
        """
        self.model = model
        self.explainer = None
        self.shap_values = None
        self.X = None
        
        # 设置中文显示
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'WenQuanYi Micro Hei']
        plt.rcParams['axes.unicode_minus'] = False
    
    def fit(self, X: np.ndarray, background_samples: int = 100):
        """
        拟合SHAP解释器
        :param X: 特征数据
        :param background_samples: 背景样本数量
        """
        self.X = X
        
        # 获取模型和scaler
        model = self.model.model
        scaler = self.model.scaler
        
        # 标准化
        X_scaled = scaler.transform(X)
        
        # 取背景样本
        if len(X_scaled) > background_samples:
            background = X_scaled[np.random.choice(len(X_scaled), background_samples, replace=False)]
        else:
            background = X_scaled
        
        # 创建解释器
        if hasattr(model, 'predict_proba'):
            self.explainer = shap.TreeExplainer(model, background)
            self.shap_values = self.explainer.shap_values(X_scaled)
            
            # 对于二分类，shap返回[class0, class1]，我们只需要class1
            if isinstance(self.shap_values, list) and len(self.shap_values) == 2:
                self.shap_values = self.shap_values[1]
        
        else:
            raise ValueError("Model doesn't have predict_proba method")
    
    def summary_plot(self, output_path: str = 'shap_summary.png', 
                     max_display: int = 20,
                     show: bool = False):
        """
        绘制SHAP汇总图
        :param output_path: 输出文件路径
        :param max_display: 最大显示特征数
        :param show: 是否显示
        """
        if self.explainer is None or self.shap_values is None:
            raise ValueError("Call fit first")
        
        feature_names = self.model.factor_cols
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(self.X.shape[1])]
        
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            self.shap_values, 
            self.X,
            feature_names=feature_names,
            max_display=max_display,
            show=False
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        
        print(f"SHAP汇总图已保存至: {output_path}")
    
    def force_plot(self, idx: int, output_path: str = 'shap_force.png', show: bool = False):
        """
        绘制单个样本的力图
        :param idx: 样本索引
        :param output_path: 输出文件路径
        :param show: 是否显示
        """
        if self.explainer is None or self.shap_values is None:
            raise ValueError("Call fit first")
        
        feature_names = self.model.factor_cols
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(self.X.shape[1])]
        
        plt.figure(figsize=(12, 4))
        shap.force_plot(
            self.explainer.expected_value,
            self.shap_values[idx],
            features=self.X[idx],
            feature_names=feature_names,
            matplotlib=True,
            show=False
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
    
    def feature_importance_plot(self, output_path: str = 'shap_importance.png', 
                                max_display: int = 20,
                                show: bool = False):
        """
        绘制特征重要性图
        :param output_path: 输出文件路径
        :param max_display: 最大显示特征数
        :param show: 是否显示
        """
        if self.shap_values is None:
            raise ValueError("Call fit first")
        
        feature_names = self.model.factor_cols
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(self.X.shape[1])]
        
        # 计算每个特征的平均绝对SHAP值作为重要性
        importance = np.abs(self.shap_values).mean(axis=0)
        fi_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importance
        })
        fi_df = fi_df.sort_values('importance', ascending=False).head(max_display)
        
        plt.figure(figsize=(10, 8))
        plt.barh(fi_df['feature'][::-1], fi_df['importance'][::-1])
        plt.xlabel('平均绝对SHAP值 (特征重要性)')
        plt.ylabel('特征名称')
        plt.title('SHAP特征重要性排序')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        
        print(f"SHAP特征重要性图已保存至: {output_path}")
        return fi_df
    
    def dependence_plot(self, feature_name: str, output_path: str = 'shap_dependence.png', 
                        show: bool = False):
        """
        绘制特征依赖图
        :param feature_name: 特征名称
        :param output_path: 输出文件路径
        :param show: 是否显示
        """
        if self.shap_values is None:
            raise ValueError("Call fit first")
        
        feature_names = self.model.factor_cols
        if feature_names is None:
            raise ValueError("Feature names not available")
        
        if feature_name not in feature_names:
            raise ValueError(f"Feature {feature_name} not found")
        
        idx = feature_names.index(feature_name)
        
        plt.figure(figsize=(10, 6))
        shap.dependence_plot(
            idx,
            self.shap_values,
            self.X,
            feature_names=feature_names,
            show=False
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        
        print(f"SHAP依赖图已保存至: {output_path}")
    
    def get_feature_importance(self) -> pd.DataFrame:
        """获取特征重要性DataFrame"""
        if self.shap_values is None:
            raise ValueError("Call fit first")
        
        feature_names = self.model.factor_cols
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(self.X.shape[1])]
        
        importance = np.abs(self.shap_values).mean(axis=0)
        fi_df = pd.DataFrame({
            'feature': feature_names,
            'shap_importance': importance
        })
        fi_df = fi_df.sort_values('shap_importance', ascending=False)
        return fi_df
