"""
Qlib 因子引擎适配层
将 qlib 的因子表达式算子与 quant-framework 的 TushareDataFetcher 对接

支持：qlib 标准表达式 + infix 数学运算符（+ - * /）
"""
import pandas as pd
import numpy as np
from typing import Dict


class QlibFactorEngine:
    """
    Qlib 因子表达式引擎

    使用示例：
        fe = QlibFactorEngine()
        fe.register_factor("ma5", "Ref($close, 5) / $close - 1")
        fe.register_factor("volume_ratio", "$volume / Mean($volume, 20)")
        df = fe.calculate_factors(history_df)
    """

    def __init__(self):
        self._factor_exprs: Dict[str, str] = {}

    def register_factor(self, name: str, expression: str):
        """
        注册因子表达式（qlib标准语法，支持 infix 运算符）

        支持的函数调用形式：
          Ref($field, N)    — N日前值
          Mean($field, N)    — N日均值
          Std($field, N)     — N日标准差
          Sum($field, N)     — N日求和
          EMA($field, N)     — N日指数移动平均
          Max(A, B), Min(A, B)
          Div/Add/Sub/Mul(A, B)
          Abs(A), Log(A)
          Lt/Le/Gt/Ge/Eq/Ne(A, B)
          If(Cond, A, B)

        支持的 infix 运算符（自动转换）：
          A + B, A - B, A * B, A / B
        """
        self._factor_exprs[name] = expression

    def calculate_factors(self, df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
        """
        计算所有注册因子的因子值

        Args:
            df: 含 trade_date/open/high/low/close/volume 列的 DataFrame
            inplace: 是否在原DataFrame上修改

        Returns:
            添加了因子列的 DataFrame
        """
        if not inplace:
            df = df.copy()
        df = self._standardize_columns(df)
        parser = QlibExpressionParser(df)

        for name, expr in self._factor_exprs.items():
            try:
                df[name] = parser.evaluate(expr)
            except Exception as e:
                print(f"[QlibFactorEngine] Factor '{name}' failed: {e}")
                df[name] = np.nan
        return df

    @staticmethod
    def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
        # 创建临时 $field 别名用于表达式查找，但保留原始列名
        rename = {}
        for c in df.columns:
            if c.lower() in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                rename[c] = f'${c.lower()}'
        if rename:
            df = df.rename(columns=rename)
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)
        return df

    def batch_calculate(self, history: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        return {code: self.calculate_factors(df)
                for code, df in history.items()}


# ─── 表达式解析 ───────────────────────────────────────────────────────────────

class QlibExpressionParser:
    """
    将 qlib 表达式字符串解析为 numpy 数组

    处理流程：
      1. infix 中缀运算符（+ - * /）递归转换为函数形式
      2. 函数形式由对应 _eval_* 方法执行
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def evaluate(self, expr: str) -> np.ndarray:
        """主入口"""
        # 提取所有 infix 运算符（忽略函数调用参数内的）
        tokenized = self._tokenize_infix(expr.strip())
        if self._has_infix_ops(tokenized):
            func_form = self._infix_to_func(tokenized)
            return self._eval_func_call(func_form)
        return self._eval_func_call(expr.strip())

    # ── 算子优先级解析 ─────────────────────────────────────────────────────────

    def _has_infix_ops(self, tokens: list) -> bool:
        depth = 0
        for t in tokens:
            if t == '(':
                depth += 1
            elif t == ')':
                depth -= 1
            elif t in ('+', '-', '*', '/') and depth == 0:
                return True
        return False

    def _infix_to_func(self, tokens: list) -> str:
        """
        将中缀tokens递归转换为 qlib 函数字符串
        按优先级：先处理低优先级 (+ -)，再处理高优先级 (* /)
        同优先级从左到右
        """
        # 找最低优先级的运算符（depth=0）
        prec = {'+': 1, '-': 1, '*': 2, '/': 2}
        min_prec = 99
        split = -1
        for i, t in enumerate(tokens):
            if t in prec and prec[t] <= min_prec:
                min_prec = prec[t]
                split = i

        if split <= 0 or split >= len(tokens) - 1:
            # 只有一个token，直接返回
            raw = ''.join(tokens).strip()
            if not raw:
                raise ValueError(f"[QlibExpressionParser] Empty expression")
            return raw

        left_tokens = tokens[:split]
        op = tokens[split]
        right_tokens = tokens[split + 1:]

        op_map = {'+': 'Add', '-': 'Sub', '*': 'Mul', '/': 'Div'}
        left_str = self._infix_to_func(left_tokens) if len(left_tokens) > 1 else self._join_tokens(left_tokens)
        right_str = self._infix_to_func(right_tokens) if len(right_tokens) > 1 else self._join_tokens(right_tokens)

        return f"{op_map[op]}({left_str}, {right_str})"

    def _join_tokens(self, tokens: list) -> str:
        """将tokens重新拼接为字符串（保留函数调用格式）"""
        return ''.join(tokens)

    def _tokenize_infix(self, expr: str) -> list:
        """
        中缀表达式分词（depth-aware：括号内运算符不分割）
        "Ref($close, 5) / $close - 1"
        → ["Ref($close, 5)", "/", "$close", "-", "1"]
        "Add(Max($a, $b), Sub($c, 1))"
        → ["Add(Max($a, $b), Sub($c, 1))"]
        "Max(Min($a, $b), Div($c, 2))"
        → ["Max(Min($a, $b), Div($c, 2))"]
        """
        tokens = []
        current = ''
        depth = 0
        i = 0
        n = len(expr)

        while i < n:
            c = expr[i]

            if c == '(':
                depth += 1
                current += c
            elif c == ')':
                depth -= 1
                current += c
            elif c in '+-*/^' and depth == 0:
                # 顶级运算符：分割token
                if current.strip():
                    tokens.append(current.strip())
                tokens.append(c)
                current = ''
            elif c == ' ' and depth == 0:
                # 顶级空格：跳过，作为token分隔符
                if current.strip():
                    tokens.append(current.strip())
                current = ''
            else:
                current += c
            i += 1

        if current.strip():
            tokens.append(current.strip())
        return tokens

    # ── 函数求值 ───────────────────────────────────────────────────────────────

    def _eval_func_call(self, expr: str) -> np.ndarray:
        """
        解析并求值 qlib 函数调用表达式
        入口：已处理完 infix 的纯函数形式字符串
        """
        expr = expr.strip()

        # 字段访问 $field
        if expr.startswith('$'):
            return self._eval_field(expr)

        for name, method in [
            ("Ref", self._eval_Ref), ("Mean", self._eval_Mean),
            ("Std", self._eval_Std), ("Sum", self._eval_Sum),
            ("EMA", self._eval_EMA), ("Max", self._eval_Max),
            ("Min", self._eval_Min), ("Div", self._eval_Div),
            ("Add", self._eval_Add), ("Sub", self._eval_Sub),
            ("Mul", self._eval_Mul), ("If", self._eval_If),
            ("Abs", self._eval_Abs), ("Log", self._eval_Log),
            ("And", self._eval_And),
            ("Lt", self._eval_Lt), ("Le", self._eval_Le),
            ("Gt", self._eval_Gt), ("Ge", self._eval_Ge),
            ("Eq", self._eval_Eq), ("Ne", self._eval_Ne),
        ]:
            if expr.startswith(f"{name}("):
                return method(expr)

        # 数值字面量
        try:
            val = float(expr)
            n = len(self.df)
            return np.full(n, val)
        except ValueError:
            pass

        raise ValueError(f"[QlibExpressionParser] Unsupported: '{expr}'")

    def _eval_field(self, expr: str) -> np.ndarray:
        col = expr.lstrip('$')
        if col not in self.df.columns:
            for c in self.df.columns:
                if c.lstrip('$') == col:
                    col = c
                    break
        if col not in self.df.columns:
            raise KeyError(f"[QlibExpressionParser] Unknown field: {expr}")
        return self.df[col].values

    @staticmethod
    def _split_args(s: str):
        """按顶层逗号分割参数"""
        depth = 0
        for i, c in enumerate(s):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == ',' and depth == 0:
                return s[:i].strip(), s[i+1:].strip()
        return s.strip(), ""

    def _eval_Ref(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        f_str, n_str = self._split_args(rest)
        vals = self._eval_func_call(f_str.strip())
        return pd.Series(vals).shift(int(n_str)).values

    def _eval_Mean(self, expr: str) -> np.ndarray:
        rest = expr[5:-1]
        f_str, n_str = self._split_args(rest)
        return pd.Series(self._eval_func_call(f_str)).rolling(int(n_str)).mean().values

    def _eval_Std(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        f_str, n_str = self._split_args(rest)
        return pd.Series(self._eval_func_call(f_str)).rolling(int(n_str)).std().values

    def _eval_Sum(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        f_str, n_str = self._split_args(rest)
        return pd.Series(self._eval_func_call(f_str)).rolling(int(n_str)).sum().values

    def _eval_EMA(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        f_str, n_str = self._split_args(rest)
        return pd.Series(self._eval_func_call(f_str)).ewm(span=int(n_str), adjust=False).mean().values

    def _eval_Max(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return np.maximum(self._eval_func_call(a), self._eval_func_call(b))

    def _eval_Min(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return np.minimum(self._eval_func_call(a), self._eval_func_call(b))

    def _eval_Div(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(self._eval_func_call(b) != 0,
                            self._eval_func_call(a) / self._eval_func_call(b),
                            np.nan)

    def _eval_Add(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return self._eval_func_call(a) + self._eval_func_call(b)

    def _eval_Sub(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return self._eval_func_call(a) - self._eval_func_call(b)

    def _eval_Mul(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return self._eval_func_call(a) * self._eval_func_call(b)

    def _eval_If(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        parts = self._split_comma3(rest)
        cond = self._eval_func_call(parts[0])
        a = self._eval_func_call(parts[1])
        b = self._eval_func_call(parts[2])
        return np.where(cond > 0, a, b)

    def _eval_Abs(self, expr: str) -> np.ndarray:
        return np.abs(self._eval_func_call(expr[4:-1]))

    def _eval_Log(self, expr: str) -> np.ndarray:
        vals = self._eval_func_call(expr[4:-1])
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.log(np.where(vals > 0, vals, np.nan))

    def _eval_And(self, expr: str) -> np.ndarray:
        rest = expr[4:-1]
        a, b = self._split_args(rest)
        return np.logical_and(
            self._eval_func_call(a) > 0,
            self._eval_func_call(b) > 0
        ).astype(float)

    def _eval_Lt(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) < self._eval_func_call(b)).astype(float)

    def _eval_Le(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) <= self._eval_func_call(b)).astype(float)

    def _eval_Gt(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) > self._eval_func_call(b)).astype(float)

    def _eval_Ge(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) >= self._eval_func_call(b)).astype(float)

    def _eval_Eq(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) == self._eval_func_call(b)).astype(float)

    def _eval_Ne(self, expr: str) -> np.ndarray:
        rest = expr[3:-1]
        a, b = self._split_args(rest)
        return (self._eval_func_call(a) != self._eval_func_call(b)).astype(float)

    @staticmethod
    def _split_comma3(s: str) -> list:
        parts = []
        depth = 0
        start = 0
        for i, c in enumerate(s):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == ',' and depth == 0:
                parts.append(s[start:i].strip())
                start = i + 1
        parts.append(s[start:].strip())
        while len(parts) < 3:
            parts.append("")
        return parts[:3]


# ─── 单元测试 ────────────────────────────────────────────────────────────────

def test_factor_engine():
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(60) * 2)
    volume = np.random.randint(1e6, 5e6, 60)

    df = pd.DataFrame({
        "trade_date": dates,
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": volume
    })

    fe = QlibFactorEngine()
    fe.register_factor("ret_5d", "Ref($close, 5) / $close - 1")
    fe.register_factor("ma10", "Mean($close, 10)")
    fe.register_factor("vol_ratio", "$volume / Mean($volume, 20)")
    fe.register_factor("ema12", "EMA($close, 12)")
    fe.register_factor("price_relative", "Ref($close, 5) / $close - 1 + 0.01")

    result = fe.calculate_factors(df)
    print("Factor calculation test:")
    print(result[["trade_date", "$close", "ret_5d", "ma10", "vol_ratio", "ema12"]].tail(10))
    print("\n✅ QlibFactorEngine test passed")


if __name__ == "__main__":
    test_factor_engine()
