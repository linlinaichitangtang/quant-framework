"""
LSTM / Transformer 时序价格预测模型 - V2.2 深度学习策略引擎

包含:
- LSTMModel: 带注意力机制的 LSTM 分类模型
- TransformerTimeSeriesModel: Transformer 时序预测模型
- PricePredictor: 训练和推理服务封装
"""
import numpy as np
import pandas as pd
import logging
from typing import Optional, Tuple, Dict
from pathlib import Path
import math
import json
import joblib

from .feature_engineering import FeatureEngineer

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    class _DummyNN:
        class Module: pass
        class Linear: pass
        class LSTM: pass
        class Dropout: pass
        class Sequential: pass
        class MultiheadAttention: pass
        class LayerNorm: pass
    nn = _DummyNN()  # type: ignore
    class _DummyTorch:
        Tensor = type("Tensor", (), {})
    torch = _DummyTorch()  # type: ignore

logger = logging.getLogger(__name__)


class PositionalEncoding(nn.Module):
    """正弦位置编码"""

    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, d_model)
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class LSTMModel(nn.Module):
    """LSTM 时序价格预测模型 (带注意力机制)"""

    def __init__(self, input_size: int, hidden_size: int = 128,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
            nn.Softmax(dim=1)
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 3)  # 3-class: up / flat / down
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden)

        # Attention mechanism
        attn_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
        context = torch.sum(attn_weights * lstm_out, dim=1)  # (batch, hidden)

        output = self.fc(context)  # (batch, 3)
        return output


class TransformerTimeSeriesModel(nn.Module):
    """Transformer 时序预测模型"""

    def __init__(self, input_size: int, d_model: int = 128,
                 nhead: int = 8, num_layers: int = 3, dropout: float = 0.1):
        super().__init__()
        self.input_proj = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model, dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=d_model * 4,
            dropout=dropout, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)
        self.fc = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 3)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        x = self.pos_encoder(x)
        x = self.transformer(x)
        x = x[:, -1, :]  # Take last token
        return self.fc(x)


class PricePredictor:
    """价格预测服务 - 封装训练和推理"""

    def __init__(self, model_type: str = "lstm", device: str = "cpu"):
        self.model_type = model_type
        self.device = torch.device(device)
        self.model: Optional[nn.Module] = None
        self.feature_engineer = FeatureEngineer()

    def _create_model(self, input_size: int) -> nn.Module:
        """创建模型实例"""
        if self.model_type == "lstm":
            return LSTMModel(input_size=input_size).to(self.device)
        elif self.model_type == "transformer":
            return TransformerTimeSeriesModel(input_size=input_size).to(self.device)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train(self, df: pd.DataFrame, config: dict) -> dict:
        """训练模型

        Args:
            df: OHLCV DataFrame
            config: {epochs, batch_size, learning_rate, seq_length, val_split}

        Returns:
            Training metrics dict
        """
        epochs = config.get('epochs', 100)
        batch_size = config.get('batch_size', 32)
        learning_rate = config.get('learning_rate', 0.001)
        seq_length = config.get('seq_length', 60)
        val_split = config.get('val_split', 0.2)
        patience = config.get('patience', 10)

        logger.info(f"开始训练 {self.model_type} 模型, epochs={epochs}, batch_size={batch_size}")

        # 1. Build features
        df = self.feature_engineer.build_features(df)

        # 2. Normalize (fit on full data for simplicity)
        df = self.feature_engineer.normalize(df, fit=True)

        # 3. Create sequences
        X, y = self.feature_engineer.create_sequences(df, seq_length)
        if len(X) == 0:
            raise ValueError("数据量不足，无法创建训练序列")

        # 4. Split train/val
        val_size = int(len(X) * val_split)
        X_train, X_val = X[:-val_size], X[-val_size:]
        y_train, y_val = y[:-val_size], y[-val_size:]

        logger.info(f"训练集: {len(X_train)} 样本, 验证集: {len(X_val)} 样本")

        # 5. Create DataLoader
        train_dataset = TensorDataset(
            torch.from_numpy(X_train), torch.from_numpy(y_train)
        )
        val_dataset = TensorDataset(
            torch.from_numpy(X_val), torch.from_numpy(y_val)
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # 6. Create model
        input_size = X_train.shape[2]
        self.model = self._create_model(input_size)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        # 7. Training loop with early stopping
        train_losses = []
        val_losses = []
        val_accuracies = []
        best_val_loss = float('inf')
        best_model_state = None
        no_improve_count = 0
        actual_epochs = 0

        for epoch in range(epochs):
            actual_epochs = epoch + 1
            # Train
            self.model.train()
            epoch_loss = 0
            correct = 0
            total = 0
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item() * batch_x.size(0)
                _, predicted = torch.max(outputs, 1)
                total += batch_y.size(0)
                correct += (predicted == batch_y).sum().item()

            train_loss = epoch_loss / total
            train_acc = correct / total
            train_losses.append(train_loss)

            # Validate
            self.model.eval()
            val_loss = 0
            val_correct = 0
            val_total = 0
            with torch.no_grad():
                for batch_x, batch_y in val_loader:
                    batch_x = batch_x.to(self.device)
                    batch_y = batch_y.to(self.device)
                    outputs = self.model(batch_x)
                    loss = criterion(outputs, batch_y)
                    val_loss += loss.item() * batch_x.size(0)
                    _, predicted = torch.max(outputs, 1)
                    val_total += batch_y.size(0)
                    val_correct += (predicted == batch_y).sum().item()

            val_loss = val_loss / val_total
            val_acc = val_correct / val_total
            val_losses.append(val_loss)
            val_accuracies.append(val_acc)

            scheduler.step(val_loss)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_model_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                no_improve_count = 0
            else:
                no_improve_count += 1

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch + 1}/{epochs} - "
                    f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f} - "
                    f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}"
                )

            if no_improve_count >= patience:
                logger.info(f"Early stopping at epoch {epoch + 1}")
                break

        # 8. Load best model
        if best_model_state is not None:
            self.model.load_state_dict(best_model_state)

        metrics = {
            'train_loss': train_losses,
            'val_loss': val_losses,
            'val_accuracy': val_accuracies,
            'epochs': actual_epochs,
            'best_val_loss': best_val_loss,
            'best_val_accuracy': max(val_accuracies) if val_accuracies else 0,
            'input_size': input_size,
            'seq_length': seq_length,
            'model_type': self.model_type,
        }

        logger.info(f"训练完成, 最佳验证准确率: {metrics['best_val_accuracy']:.4f}")
        return metrics

    def predict(self, df: pd.DataFrame, seq_length: int = 60) -> dict:
        """预测未来价格走势

        Args:
            df: OHLCV DataFrame (at least seq_length + 1 rows)
            seq_length: Sequence length

        Returns:
            {direction: "up"/"down"/"flat", confidence: 0.75,
             predicted_return: 0.023, probabilities: [0.1, 0.15, 0.75]}
        """
        if self.model is None:
            raise ValueError("模型未加载，请先调用 load_model() 或 train()")

        self.model.eval()

        # Build features
        df = self.feature_engineer.build_features(df)

        # Normalize
        df = self.feature_engineer.normalize(df, fit=False)

        # Get last sequence
        feature_cols = [c for c in self.feature_engineer.feature_names if c in df.columns]
        data = df[feature_cols].values

        # Drop NaN
        valid_mask = ~np.isnan(data).any(axis=1)
        data = data[valid_mask]

        if len(data) < seq_length:
            raise ValueError(f"数据量不足，需要至少 {seq_length} 行有效数据，当前 {len(data)} 行")

        last_seq = data[-seq_length:]
        x = torch.from_numpy(last_seq.astype(np.float32)).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

        labels = ['down', 'flat', 'up']
        predicted_idx = int(np.argmax(probs))
        direction = labels[predicted_idx]
        confidence = float(probs[predicted_idx])

        # Estimate predicted return from features
        last_return = data[-1, 0] if len(data) > 0 else 0  # returns_1d
        predicted_return = float(last_return * confidence)

        return {
            'direction': direction,
            'confidence': confidence,
            'predicted_return': predicted_return,
            'probabilities': probs.tolist(),
        }

    def save_model(self, path: str):
        """Save model and feature engineer state"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save PyTorch model
        torch.save({
            'model_type': self.model_type,
            'model_state_dict': self.model.state_dict(),
            'model_class': self.model.__class__.__name__,
        }, str(path / 'model.pt'))

        # Save scaler
        if self.feature_engineer.scaler is not None:
            joblib.dump(self.feature_engineer.scaler, str(path / 'scaler.pkl'))

        # Save metadata
        metadata = {
            'model_type': self.model_type,
            'feature_names': self.feature_engineer.feature_names,
        }
        with open(str(path / 'metadata.json'), 'w') as f:
            json.dump(metadata, f)

        logger.info(f"模型已保存到 {path}")

    def load_model(self, path: str):
        """Load model and feature engineer state"""
        path = Path(path)

        # Load metadata
        with open(str(path / 'metadata.json'), 'r') as f:
            metadata = json.load(f)

        self.model_type = metadata['model_type']
        self.feature_engineer.feature_names = metadata['feature_names']

        # Load scaler
        scaler_path = path / 'scaler.pkl'
        if scaler_path.exists():
            self.feature_engineer.scaler = joblib.load(str(scaler_path))

        # Load model
        checkpoint = torch.load(str(path / 'model.pt'), map_location=self.device, weights_only=False)
        input_size = len(self.feature_engineer.feature_names)
        self.model = self._create_model(input_size)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

        logger.info(f"模型已从 {path} 加载")
