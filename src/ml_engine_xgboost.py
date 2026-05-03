"""
ML Engine with XGBoost - Enhanced Predictive Modeling for EigenTrades
Implements XGBoost classifier with optional ensemble against Ridge Regression + Random Forest.
Features: Volatility, RSI, MACD, Bollinger Band width, SMA divergence.
Target: Improved prediction accuracy (65%+ on historical stock data).

XGBoost Features:
- Gradient boosting with adaptive learning
- Built-in feature importance
- Faster training and inference vs Random Forest
- Handles non-linear relationships better
- Reduced overfitting with regularization parameters
"""

import pandas as pd
import numpy as np
import time
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, accuracy_score
from sklearn.preprocessing import StandardScaler
import joblib
from indicators import rsi as calculate_rsi, sma, ema, macd, bollinger_bands


class MLEngineXGBoost:
    """
    Enhanced ML Engine with XGBoost as primary model.
    
    Architecture:
    - Primary: XGBoost Classifier (gradient boosting ensemble)
    - Secondary (optional): Ridge Regression + Random Forest for comparison
    - Features: Volatility, RSI, MACD, BB Width, SMA Divergence
    - Performance target: 65%+ prediction accuracy
    
    XGBoost Advantages:
    - Handles non-linear patterns in market data
    - Faster inference than Random Forest
    - Built-in feature importance ranking
    - Regularization reduces overfitting
    - Better generalization on unseen data
    """

    def __init__(self, model_type="xgboost", xgb_params=None, 
                 n_estimators=200, ridge_alpha=1.0,
                 enable_legacy_models=True):
        """
        Initialize ML Engine with selectable model backend.
        
        Args:
            model_type: "xgboost", "ridge_forest", or "ensemble_all"
            xgb_params: Custom XGBoost parameters dict
            n_estimators: Number of estimators for Forest
            ridge_alpha: Ridge regularization strength
            enable_legacy_models: Keep Ridge + Forest for comparison
        """
        self.model_type = model_type
        self.enable_legacy_models = enable_legacy_models
        
        # Primary: XGBoost
        xgb_defaults = {
            'n_estimators': 100,
            'max_depth': 5,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 1,
            'gamma': 0,
            'reg_alpha': 0.0,
            'reg_lambda': 1.0,
            'random_state': 42,
            'eval_metric': 'logloss',
            'verbosity': 0
        }
        
        if xgb_params:
            xgb_defaults.update(xgb_params)
        
        self.xgb = XGBClassifier(**xgb_defaults)
        
        # Legacy models (optional)
        if enable_legacy_models:
            self.ridge = RidgeClassifier(alpha=ridge_alpha)
            self.forest = RandomForestClassifier(
                n_estimators=n_estimators,
                min_samples_split=50,
                random_state=42
            )
        else:
            self.ridge = None
            self.forest = None
        
        self.scaler = StandardScaler()
        
        # For backward compatibility
        self.model = self.xgb
        
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
        Train XGBoost + optional legacy models ensemble.
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

        # Train XGBoost (primary model)
        self.xgb.fit(X_train, y_train, verbose=False)
        xgb_preds = self.xgb.predict(X_test)
        xgb_accuracy = accuracy_score(y_test, xgb_preds)
        xgb_precision = precision_score(y_test, xgb_preds, zero_division=0)
        
        # XGBoost probabilities for ensemble
        xgb_probs = self.xgb.predict_proba(X_test)[:, 1]
        
        # Feature importances from XGBoost
        self.feature_importances = dict(zip(self.features, self.xgb.feature_importances_))

        # Initialize metrics dictionary
        self.training_metrics = {
            "xgb_accuracy": xgb_accuracy,
            "xgb_precision": xgb_precision,
            "accuracy": xgb_accuracy,  # Primary metric
            "precision": xgb_precision,  # Primary metric
            "train_size": len(X_train),
            "test_size": len(X_test),
            "total_rows": len(data),
            "feature_importances": self.feature_importances,
            "model_type": "XGBoost Classifier"
        }

        # Train legacy models if enabled (for comparison)
        if self.enable_legacy_models:
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Ridge
            self.ridge.fit(X_train_scaled, y_train)
            ridge_preds = self.ridge.predict(X_test_scaled)
            ridge_accuracy = accuracy_score(y_test, ridge_preds)
            ridge_precision = precision_score(y_test, ridge_preds, zero_division=0)
            
            # Random Forest
            self.forest.fit(X_train, y_train)
            forest_preds = self.forest.predict(X_test)
            forest_accuracy = accuracy_score(y_test, forest_preds)
            forest_precision = precision_score(y_test, forest_preds, zero_division=0)
            
            # Add legacy metrics to results
            self.training_metrics.update({
                "ridge_accuracy": ridge_accuracy,
                "ridge_precision": ridge_precision,
                "forest_accuracy": forest_accuracy,
                "forest_precision": forest_precision,
            })
            
            # Ensemble: Average all three models
            if self.model_type == "ensemble_all":
                ensemble_preds = ((xgb_preds + ridge_preds + forest_preds) >= 2).astype(int)
                ensemble_accuracy = accuracy_score(y_test, ensemble_preds)
                ensemble_precision = precision_score(y_test, ensemble_preds, zero_division=0)
                self.training_metrics.update({
                    "ensemble_accuracy": ensemble_accuracy,
                    "ensemble_precision": ensemble_precision,
                })

        train_time = time.time() - start_time
        self.is_trained = True
        self.training_metrics.update({
            "train_time_seconds": round(train_time, 2)
        })

        return self.training_metrics

    def predict_signal(self, current_data: dict) -> dict:
        """
        Generate trading signal with confidence score.
        Primary: XGBoost prediction and probability
        Optional: Legacy model predictions for comparison
        """
        start_time = time.time()

        df = pd.DataFrame([current_data])
        X = df[self.features]

        # XGBoost prediction and probability
        xgb_pred = self.xgb.predict(X)[0]
        xgb_prob = self.xgb.predict_proba(X)[0][1]
        
        # Ensemble confidence (prioritize XGBoost)
        confidence = float(xgb_prob)
        signal = 1 if confidence > 0.6 else 0

        # Top contributing feature
        top_feature = max(self.feature_importances, key=self.feature_importances.get) if self.feature_importances else self.features[0]

        latency_ms = (time.time() - start_time) * 1000

        result = {
            "signal": signal,
            "confidence": round(confidence, 4),
            "top_factor": top_feature,
            "xgb_decision": int(xgb_pred),
            "xgb_probability": round(xgb_prob, 4),
            "latency_ms": round(latency_ms, 2),
            "model_used": "XGBoost"
        }
        
        # Add legacy model outputs if enabled
        if self.enable_legacy_models:
            X_scaled = self.scaler.transform(X)
            ridge_pred = self.ridge.predict(X_scaled)[0]
            forest_prob = self.forest.predict_proba(X)[0][1]
            
            result.update({
                "ridge_decision": int(ridge_pred),
                "forest_probability": round(forest_prob, 4),
            })

        return result

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict signals for an entire dataframe."""
        start_time = time.time()

        data = self.prepare_features(df)
        X = data[self.features]

        xgb_probs = self.xgb.predict_proba(X)[:, 1]

        data['confidence'] = xgb_probs
        data['signal'] = (data['confidence'] > 0.6).astype(int)

        latency = time.time() - start_time
        data['latency_s'] = latency / len(data)

        return data

    def get_model_summary(self) -> dict:
        """Return summary of trained model for UI display."""
        if not self.is_trained:
            return {"status": "Not trained"}

        summary = {
            "model_type": "XGBoost Classifier",
            "primary_model": "XGBoost",
            "xgb_trees": self.xgb.n_estimators,
            "xgb_max_depth": self.xgb.max_depth,
            "features": self.features,
            "feature_importances": self.feature_importances,
            "accuracy": self.training_metrics.get("xgb_accuracy", 0),
            "precision": self.training_metrics.get("xgb_precision", 0),
            "train_size": self.training_metrics.get("train_size", 0),
            "is_trained": self.is_trained
        }
        
        if self.enable_legacy_models:
            summary["legacy_models"] = {
                "ridge_accuracy": self.training_metrics.get("ridge_accuracy", 0),
                "forest_accuracy": self.training_metrics.get("forest_accuracy", 0),
            }
        
        return summary

    def save(self, path="model_xgboost.joblib"):
        """Save XGBoost model and optional legacy models."""
        save_data = {
            'xgb': self.xgb,
            'scaler': self.scaler,
            'features': self.features,
            'feature_importances': self.feature_importances,
            'training_metrics': self.training_metrics,
            'is_trained': self.is_trained,
            'model_type': self.model_type,
            'enable_legacy_models': self.enable_legacy_models
        }
        
        if self.enable_legacy_models:
            save_data['ridge'] = self.ridge
            save_data['forest'] = self.forest
        
        joblib.dump(save_data, path)

    def load(self, path="model_xgboost.joblib"):
        """Load XGBoost model and optional legacy models."""
        data = joblib.load(path)
        self.xgb = data['xgb']
        self.scaler = data['scaler']
        self.model = self.xgb
        self.features = data['features']
        self.feature_importances = data.get('feature_importances', {})
        self.training_metrics = data.get('training_metrics', {})
        self.is_trained = data.get('is_trained', True)
        self.model_type = data.get('model_type', 'xgboost')
        self.enable_legacy_models = data.get('enable_legacy_models', True)
        
        if self.enable_legacy_models and 'ridge' in data:
            self.ridge = data['ridge']
            self.forest = data['forest']
