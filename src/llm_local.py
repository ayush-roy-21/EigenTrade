"""
LLM Explainer Module for EigenTrades
Generates real-time, human-readable trade justifications.
Target: Sub-2 second interpretation latency.

Supports:
- Mistral API (cloud) for rich explanations
- Local rule-based fallback for offline/fast mode
"""

import os
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger("llm_local")


# ── Rule-based local explainer (always available, sub-100ms) ─────────────────

INDICATOR_EXPLANATIONS = {
    "rsi": {
        "low": "RSI is below 30, indicating the asset is **oversold** — a potential buying opportunity.",
        "high": "RSI is above 70, indicating the asset is **overbought** — a potential selling signal.",
        "neutral": "RSI is in the neutral zone (30-70), showing balanced momentum."
    },
    "macd": {
        "bullish": "MACD histogram is positive, signaling **bullish momentum** as the fast EMA leads the slow EMA.",
        "bearish": "MACD histogram is negative, signaling **bearish momentum** — short-term trend is weakening."
    },
    "sma_diff": {
        "above": "Price is trading **above** the 20-day SMA, confirming an upward trend.",
        "below": "Price is trading **below** the 20-day SMA, suggesting downward pressure."
    },
    "bb_width": {
        "wide": "Bollinger Bands are widening — **volatility is increasing**, expect larger price moves.",
        "narrow": "Bollinger Bands are narrowing — **volatility squeeze** detected, a breakout may be imminent."
    },
    "volatility": {
        "high": "Rolling volatility is elevated — the market is **turbulent**, position sizing should be conservative.",
        "low": "Volatility is low — stable conditions favor **trend-following** strategies."
    }
}


def _classify_indicator(name: str, value: float) -> str:
    """Classify an indicator value into a human-readable category."""
    if name == "rsi":
        if value < 30:
            return "low"
        elif value > 70:
            return "high"
        return "neutral"
    elif name == "macd":
        return "bullish" if value > 0 else "bearish"
    elif name == "sma_diff":
        return "above" if value > 0 else "below"
    elif name == "bb_width":
        return "wide" if value > 0.05 else "narrow"
    elif name == "volatility":
        return "high" if value > 0.02 else "low"
    return "neutral"


class ExplainerModule:
    """
    LLM-based Explainer Module for trade interpretation.
    
    Pipeline:
    1. ML Engine generates prediction (signal + confidence)
    2. Explainer parses the signal into human-readable rationale
    3. Output: "Confidence: 0.85" → "Strong Buy..."
    
    Modes:
    - 'local': Rule-based (instant, no API needed)
    - 'mistral': Mistral API (richer explanations, requires API key)
    """

    def __init__(self, mode: str = "local", eigent_provider: str = "openai",
                 eigent_model: str | None = None, eigent_api_key: str | None = None,
                 eigent_api_url: str | None = None):
        self.mode = mode
        self.claude_client = None
        self.mistral_client = None
        self.mistral_model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        self.eigent_explainer = None

        if mode == "eigent":
            try:
                from eigent_explainer import EigentTradeExplainer, EIGENT_AVAILABLE
                if EIGENT_AVAILABLE:
                    self.eigent_explainer = EigentTradeExplainer(
                        provider=eigent_provider,
                        model_type=eigent_model,
                        api_key=eigent_api_key,
                        api_url=eigent_api_url,
                    )
                    if not self.eigent_explainer.is_ready:
                        logger.warning("Eigent agent failed to initialise — falling back to local")
                        self.eigent_explainer = None
                        self.mode = "local"
                else:
                    logger.warning("Eigent/CAMEL not installed — falling back to local")
                    self.mode = "local"
            except Exception as e:
                logger.warning(f"Eigent import failed: {e} — falling back to local")
                self.mode = "local"
        elif mode == "claude":
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic()
            except (ImportError, Exception):
                self.mode = "local"  # Fallback
        elif mode == "mistral":
            try:
                from openai import OpenAI

                api_key = os.getenv("MISTRAL_API_KEY", "").strip()
                api_url = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1").strip()
                self.mistral_model = os.getenv("MISTRAL_MODEL", self.mistral_model).strip() or self.mistral_model

                if not api_key:
                    logger.warning("MISTRAL_API_KEY is not set — falling back to local mode")
                    self.mode = "local"
                else:
                    self.mistral_client = OpenAI(api_key=api_key, base_url=api_url)
            except (ImportError, Exception) as e:
                logger.warning(f"Mistral client init failed: {e} — falling back to local")
                self.mode = "local"

    def explain_signal(self, signal_data: Dict, features: Dict) -> Dict:
        """
        Generate a human-readable explanation for a trading signal.
        
        Args:
            signal_data: Output from MLEngine.predict_signal()
                {signal, confidence, top_factor, ridge_decision, forest_probability}
            features: Raw feature values
                {rsi, sma_diff, macd, bb_width, volatility}
        
        Returns:
            {explanation: str, latency_ms: float, mode: str}
        """
        start = time.time()

        if self.mode == "eigent" and self.eigent_explainer:
            return self.eigent_explainer.explain_signal(signal_data, features)
        elif self.mode == "mistral" and self.mistral_client:
            explanation = self._explain_with_mistral(signal_data, features)
        elif self.mode == "claude" and self.claude_client:
            explanation = self._explain_with_claude(signal_data, features)
        else:
            explanation = self._explain_local(signal_data, features)

        latency_ms = (time.time() - start) * 1000

        return {
            "explanation": explanation,
            "latency_ms": round(latency_ms, 2),
            "mode": self.mode
        }

    def explain_trade(self, trade_data: Dict, indicators: Dict) -> Dict:
        """
        Explain a completed trade (entry → exit) in plain English.
        
        Args:
            trade_data: {entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct, reason}
            indicators: {rsi, sma_20, price, macd, bb_width, volatility}
        
        Returns:
            {explanation: str, latency_ms: float}
        """
        start = time.time()

        if self.mode == "eigent" and self.eigent_explainer:
            return self.eigent_explainer.explain_trade(trade_data, indicators)
        elif self.mode == "mistral" and self.mistral_client:
            explanation = self._explain_trade_mistral(trade_data, indicators)
        elif self.mode == "claude" and self.claude_client:
            explanation = self._explain_trade_claude(trade_data, indicators)
        else:
            explanation = self._explain_trade_local(trade_data, indicators)

        latency_ms = (time.time() - start) * 1000

        return {
            "explanation": explanation,
            "latency_ms": round(latency_ms, 2),
            "mode": self.mode
        }

    # ── Local Rule-based Engine ──────────────────────────────────────────

    def _explain_local(self, signal_data: Dict, features: Dict) -> str:
        """Generate rule-based explanation for a signal (sub-50ms)."""
        confidence = signal_data.get("confidence", 0)
        signal = signal_data.get("signal", 0)
        top_factor = signal_data.get("top_factor", "rsi")

        # Signal strength label
        if confidence >= 0.8:
            strength = "Strong Buy" if signal == 1 else "Strong Hold"
        elif confidence >= 0.6:
            strength = "Moderate Buy" if signal == 1 else "Moderate Hold"
        else:
            strength = "Weak signal — Hold/Sell"

        # Build rationale from features
        reasons = []
        for feat_name in ['rsi', 'macd', 'sma_diff', 'bb_width', 'volatility']:
            val = features.get(feat_name)
            if val is not None:
                category = _classify_indicator(feat_name, val)
                if feat_name in INDICATOR_EXPLANATIONS and category in INDICATOR_EXPLANATIONS[feat_name]:
                    reasons.append(INDICATOR_EXPLANATIONS[feat_name][category])

        # Compose final explanation
        lines = [
            f"**Signal: {strength}** (Confidence: {confidence:.0%})",
            f"Primary driver: **{top_factor.upper().replace('_', ' ')}**",
            "",
            "**Market Analysis:**"
        ]
        for r in reasons:
            lines.append(f"• {r}")

        # Model consensus - support both legacy (Ridge+Forest) and XGBoost
        model_used = signal_data.get("model_used", "Ridge+Forest Ensemble")
        
        if model_used == "XGBoost":
            xgb_dec = signal_data.get("xgb_decision")
            xgb_prob = signal_data.get("xgb_probability")
            if xgb_dec is not None and xgb_prob is not None:
                lines.append("")
                lines.append("**Model Analysis:**")
                lines.append(f"• XGBoost: {'BUY' if xgb_dec == 1 else 'HOLD/SELL'} ({xgb_prob:.0%} confidence)")
        else:
            # Legacy Ridge + Forest
            ridge_dec = signal_data.get("ridge_decision")
            forest_prob = signal_data.get("forest_probability")
            if ridge_dec is not None and forest_prob is not None:
                lines.append("")
                lines.append("**Model Consensus:**")
                lines.append(f"• Ridge Regression: {'BUY' if ridge_dec == 1 else 'HOLD/SELL'}")
                lines.append(f"• Random Forest: {forest_prob:.0%} buy probability")

        return "\n".join(lines)

    def _explain_trade_local(self, trade_data: Dict, indicators: Dict) -> str:
        """Generate rule-based explanation for a completed trade."""
        entry_price = trade_data.get("entry_price", 0)
        exit_price = trade_data.get("exit_price", 0)
        pnl = trade_data.get("pnl", 0)
        pnl_pct = trade_data.get("pnl_pct", 0)
        reason = trade_data.get("reason", "Technical signal")

        outcome = "profit" if pnl > 0 else "loss"
        rsi_val = indicators.get("rsi")
        sma_val = indicators.get("sma_20")
        price = indicators.get("price", entry_price)

        lines = []

        # Entry rationale
        if rsi_val is not None and rsi_val < 30:
            lines.append(f"The algorithm entered at **${entry_price:.2f}** because RSI dropped to {rsi_val:.1f} (oversold territory below 30).")
        elif rsi_val is not None:
            lines.append(f"The algorithm entered at **${entry_price:.2f}** with RSI at {rsi_val:.1f}.")
        else:
            lines.append(f"The algorithm entered at **${entry_price:.2f}** based on technical signals.")

        if sma_val and price and price > sma_val:
            lines.append(f"Price was above the 20-day moving average (${sma_val:.2f}), confirming uptrend.")

        # Exit rationale
        lines.append(f"It exited at **${exit_price:.2f}** when exit conditions were met ({reason}).")

        # Outcome
        if pnl > 0:
            lines.append(f"**Result:** +${pnl:.2f} ({pnl_pct:+.2f}%) — a profitable trade.")
        else:
            lines.append(f"**Result:** ${pnl:.2f} ({pnl_pct:+.2f}%) — the trade resulted in a loss.")

        return " ".join(lines)

    # ── Claude API Engine ────────────────────────────────────────────────

    def _explain_with_mistral(self, signal_data: Dict, features: Dict) -> str:
        """Use Mistral API for rich signal explanation."""
        try:
            model_info = ""
            model_used = signal_data.get("model_used", "Ridge+Forest Ensemble")
            
            if model_used == "XGBoost":
                model_info = f"""XGBoost decision: {'BUY' if signal_data.get('xgb_decision') == 1 else 'HOLD'}
XGBoost probability: {signal_data.get('xgb_probability', 0):.0%}"""
            else:
                model_info = f"""Ridge Regression says: {'BUY' if signal_data.get('ridge_decision') == 1 else 'HOLD'}
Random Forest probability: {signal_data.get('forest_probability', 0):.0%}"""
            
            prompt = f"""You are a trading analyst. Explain this ML-generated trading signal concisely:

Signal: {'BUY' if signal_data.get('signal') == 1 else 'HOLD/SELL'}
Confidence: {signal_data.get('confidence', 0):.0%}
Top Factor: {signal_data.get('top_factor', 'unknown')}

Feature values:
- RSI: {features.get('rsi', 'N/A'):.2f}
- SMA Divergence: {features.get('sma_diff', 'N/A'):.4f}
- MACD: {features.get('macd', 'N/A'):.4f}
- BB Width: {features.get('bb_width', 'N/A'):.4f}
- Volatility: {features.get('volatility', 'N/A'):.4f}

{model_info}

Explain in 2-3 sentences why this signal was generated. Be specific about market conditions."""

            response = self.mistral_client.chat.completions.create(
                model=self.mistral_model,
                max_tokens=250,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception:
            return self._explain_local(signal_data, features)

    def _explain_trade_mistral(self, trade_data: Dict, indicators: Dict) -> str:
        """Use Mistral API for rich trade explanation."""
        try:
            prompt = f"""A trading algorithm made this trade. Explain in 2-3 sentences:

Entry: ${trade_data.get('entry_price', 0):.2f} on {trade_data.get('entry_date', 'N/A')}
Exit: ${trade_data.get('exit_price', 0):.2f} on {trade_data.get('exit_date', 'N/A')}
P&L: ${trade_data.get('pnl', 0):.2f} ({trade_data.get('pnl_pct', 0):+.2f}%)
Reason: {trade_data.get('reason', 'Technical signal')}

Indicators at entry - RSI: {indicators.get('rsi', 'N/A')}, SMA 20: {indicators.get('sma_20', 'N/A')}, Price: {indicators.get('price', 'N/A')}

Explain in plain English to a non-trader: WHY it entered, WHY it exited, and the result."""

            response = self.mistral_client.chat.completions.create(
                model=self.mistral_model,
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception:
            return self._explain_trade_local(trade_data, indicators)

    def _explain_with_claude(self, signal_data: Dict, features: Dict) -> str:
        """Use Claude API for rich signal explanation."""
        try:
            model_info = ""
            model_used = signal_data.get("model_used", "Ridge+Forest Ensemble")
            
            if model_used == "XGBoost":
                model_info = f"""XGBoost decision: {'BUY' if signal_data.get('xgb_decision') == 1 else 'HOLD'}
XGBoost probability: {signal_data.get('xgb_probability', 0):.0%}"""
            else:
                model_info = f"""Ridge Regression says: {'BUY' if signal_data.get('ridge_decision') == 1 else 'HOLD'}
Random Forest probability: {signal_data.get('forest_probability', 0):.0%}"""
            
            prompt = f"""You are a trading analyst. Explain this ML-generated trading signal concisely:

Signal: {'BUY' if signal_data.get('signal') == 1 else 'HOLD/SELL'}
Confidence: {signal_data.get('confidence', 0):.0%}
Top Factor: {signal_data.get('top_factor', 'unknown')}

Feature values:
- RSI: {features.get('rsi', 'N/A'):.2f}
- SMA Divergence: {features.get('sma_diff', 'N/A'):.4f}
- MACD: {features.get('macd', 'N/A'):.4f}
- BB Width: {features.get('bb_width', 'N/A'):.4f}
- Volatility: {features.get('volatility', 'N/A'):.4f}

{model_info}

Explain in 2-3 sentences why this signal was generated. Be specific about market conditions."""

            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            return self._explain_local(signal_data, features)

    def _explain_trade_claude(self, trade_data: Dict, indicators: Dict) -> str:
        """Use Claude API for rich trade explanation."""
        try:
            prompt = f"""A trading algorithm made this trade. Explain in 2-3 sentences:

Entry: ${trade_data.get('entry_price', 0):.2f} on {trade_data.get('entry_date', 'N/A')}
Exit: ${trade_data.get('exit_price', 0):.2f} on {trade_data.get('exit_date', 'N/A')}
P&L: ${trade_data.get('pnl', 0):.2f} ({trade_data.get('pnl_pct', 0):+.2f}%)
Reason: {trade_data.get('reason', 'Technical signal')}

Indicators at entry - RSI: {indicators.get('rsi', 'N/A')}, SMA 20: {indicators.get('sma_20', 'N/A')}, Price: {indicators.get('price', 'N/A')}

Explain in plain English to a non-trader: WHY it entered, WHY it exited, and the result."""

            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            return self._explain_trade_local(trade_data, indicators)
