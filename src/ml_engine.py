"""
ML Engine - Predictive Modeling for EigenTrades
Implements Ridge Regression + Random Forest ensemble for price prediction.
Features: Volatility, RSI, MACD, Bollinger Band width, SMA divergence.
Target: 50-55% prediction accuracy on historical stock data.
"""

import pandas as pd
import numpy as np
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, accuracy_score
from sklearn.preprocessing import StandardScaler
import joblib
from indicators import rsi as calculate_rsi, sma, ema, macd, bollinger_bands


class MLEngine:
    """
    Ensemble ML Engine combining Ridge Regression and Random Forest.
    
    Architecture:
    - Primary: Ridge Regression (custom regression model)
    - Secondary: Random Forest for ensemble confidence scoring
    - Features: Volatility, RSI, MACD, BB Width, SMA Divergence
    - Performance target: 50-55% prediction accuracy
    """

    def __init__(self, n_estimators=200, ridge_alpha=1.0):
        # Primary: Ridge Regression (as per portfolio spec)
        self.ridge = RidgeClassifier(alpha=ridge_alpha)
        self.scaler = StandardScaler()

        # Secondary: Random Forest for ensemble confidence
        self.forest = RandomForestClassifier(
            n_estimators=n_estimators,
            min_samples_split=50,
            random_state=42
        )

        # Backward compat: keep self.model pointing to forest for strategy.py usage
        self.model = self.forest

        self.features = ['rsi', 'sma_diff', 'macd', 'bb_width', 'volatility']
        self.is_trained = False
        self.training_metrics = {}
        self.feature_importances = {}

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer technical features from raw OHLCV data."""
        df = df.copy()

        if 'close' not in df.columns:
            raise ValueError("Training data must include a 'close' column")

        # Coerce close to numeric so mixed/string CSV sources do not poison feature engineering.
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close'])

        if len(df) < 30:
            raise ValueError(
                "Not enough valid close-price rows for feature engineering. "
                "Need at least 30 rows with numeric close values."
            )

        # 1. RSI (Relative Strength Index)
        df['rsi'] = calculate_rsi(df['close'], 14)

        # 2. SMA Divergence (% distance from 20-day SMA)
        df['sma_20'] = sma(df['close'], 20)
        df['sma_diff'] = (df['close'] - df['sma_20']) / df['sma_20']

        # 3. MACD Histogram
        macd_line, signal_line, _ = macd(df['close'])
        df['macd'] = macd_line - signal_line

        # 4. Bollinger Band Width (normalized)
        upper, _, lower = bollinger_bands(df['close'])
        df['bb_width'] = (upper - lower) / df['close']

        # 5. Rolling Volatility (20-period)
        df['volatility'] = df['close'].pct_change().rolling(20).std()

        # Target: Price direction in next 5 bars (>1% = BUY)
        future_return = df['close'].shift(-5) / df['close'] - 1
        df['target'] = (future_return > 0.01).astype(int)

        out = df.dropna()
        if out.empty:
            raise ValueError(
                "Feature engineering produced 0 rows. Check data quality and ensure numeric close values "
                "with sufficient history."
            )

        return out

    def train(self, df: pd.DataFrame) -> dict:
        """
        Train Ridge Regression + Random Forest ensemble.
        Uses time-series aware splits (no shuffling).
        """
        start_time = time.time()

        data = self.prepare_features(df)
        X = data[self.features]
        y = data['target']

        if len(X) < 5:
            raise ValueError(
                "Not enough engineered rows to train. Provide a longer dataset with valid close values."
            )

        # Time-series aware split: 80/20 chronological
        train_size = int(len(X) * 0.8)
        if train_size < 1 or (len(X) - train_size) < 1:
            raise ValueError(
                "Training split is empty. Provide more rows so both train and test sets are non-empty."
            )

        X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

        if y_train.nunique() < 2:
            raise ValueError(
                "Training target has only one class after feature engineering. "
                "Use a larger/more varied dataset."
            )

        # Scale features for Ridge
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train Ridge Regression (primary model)
        self.ridge.fit(X_train_scaled, y_train)
        ridge_preds = self.ridge.predict(X_test_scaled)
        ridge_accuracy = accuracy_score(y_test, ridge_preds)
        ridge_precision = precision_score(y_test, ridge_preds, zero_division=0)

        # Train Random Forest (secondary, for confidence/feature importance)
        self.forest.fit(X_train, y_train)
        forest_preds = self.forest.predict(X_test)
        forest_accuracy = accuracy_score(y_test, forest_preds)
        forest_precision = precision_score(y_test, forest_preds, zero_division=0)

        # Ensemble: Average predictions (Ridge + Forest)
        ensemble_preds = ((ridge_preds + forest_preds) >= 1).astype(int)
        ensemble_accuracy = accuracy_score(y_test, ensemble_preds)
        ensemble_precision = precision_score(y_test, ensemble_preds, zero_division=0)

        # Feature importances from Random Forest
        self.feature_importances = dict(zip(self.features, self.forest.feature_importances_))

        train_time = time.time() - start_time
        self.is_trained = True

        self.training_metrics = {
            "ridge_accuracy": ridge_accuracy,
            "ridge_precision": ridge_precision,
            "forest_accuracy": forest_accuracy,
            "forest_precision": forest_precision,
            "ensemble_accuracy": ensemble_accuracy,
            "ensemble_precision": ensemble_precision,
            "accuracy": ensemble_accuracy,
            "precision": ensemble_precision,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "total_rows": len(data),
            "train_time_seconds": round(train_time, 2),
            "feature_importances": self.feature_importances,
            "model_type": "Ridge + RandomForest Ensemble"
        }

        return self.training_metrics

    def predict_signal(self, current_data: dict) -> dict:
        """
        Generate trading signal with confidence score.
        Combines Ridge prediction with Forest probability.
        """
        start_time = time.time()

        df = pd.DataFrame([current_data])
        X = df[self.features]

        # Ridge decision
        X_scaled = self.scaler.transform(X)
        ridge_pred = self.ridge.predict(X_scaled)[0]

        # Forest probability
        forest_prob = self.forest.predict_proba(X)[0][1]

        # Ensemble confidence
        confidence = (float(ridge_pred) * 0.5 + forest_prob * 0.5)
        signal = 1 if confidence > 0.6 else 0

        # Top contributing feature
        top_feature = max(self.feature_importances, key=self.feature_importances.get) if self.feature_importances else self.features[0]

        latency_ms = (time.time() - start_time) * 1000

        return {
            "signal": signal,
            "confidence": round(confidence, 4),
            "top_factor": top_feature,
            "ridge_decision": int(ridge_pred),
            "forest_probability": round(forest_prob, 4),
            "latency_ms": round(latency_ms, 2)
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict signals for an entire dataframe."""
        start_time = time.time()

        data = self.prepare_features(df)
        X = data[self.features]

        X_scaled = self.scaler.transform(X)
        ridge_preds = self.ridge.predict(X_scaled)
        forest_probs = self.forest.predict_proba(X)[:, 1]

        data['confidence'] = (ridge_preds * 0.5 + forest_probs * 0.5)
        data['signal'] = (data['confidence'] > 0.6).astype(int)

        latency = time.time() - start_time
        data['latency_s'] = latency / len(data)

        return data

    def get_model_summary(self) -> dict:
        """Return summary of trained model for UI display."""
        if not self.is_trained:
            return {"status": "Not trained"}

        return {
            "model_type": "Ridge Regression + Random Forest Ensemble",
            "primary_model": "Ridge Regression",
            "secondary_model": f"Random Forest ({self.forest.n_estimators} trees)",
            "features": self.features,
            "feature_importances": self.feature_importances,
            "accuracy": self.training_metrics.get("ensemble_accuracy", 0),
            "precision": self.training_metrics.get("ensemble_precision", 0),
            "train_size": self.training_metrics.get("train_size", 0),
            "is_trained": self.is_trained
        }

    def save(self, path="model.joblib"):
        """Save both models and scaler."""
        joblib.dump({
            'ridge': self.ridge,
            'forest': self.forest,
            'scaler': self.scaler,
            'features': self.features,
            'feature_importances': self.feature_importances,
            'training_metrics': self.training_metrics,
            'is_trained': self.is_trained
        }, path)

    def load(self, path="model.joblib"):
        """Load saved models."""
        data = joblib.load(path)
        self.ridge = data['ridge']
        self.forest = data['forest']
        self.model = self.forest
        self.scaler = data['scaler']
        self.features = data['features']
        self.feature_importances = data.get('feature_importances', {})
        self.training_metrics = data.get('training_metrics', {})
        self.is_trained = data.get('is_trained', True)