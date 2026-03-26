"""
Eigent AI Trade Explainer — Multi-Agent Integration
Inspired by the Eigent (CAMEL) multi-agent framework's structured prompt
engineering and multi-provider architecture.

Supports: OpenAI, Anthropic (Claude), Ollama, any OpenAI-compatible API,
          Azure OpenAI, OpenRouter — via direct HTTP calls (no camel-ai needed).

Works on any Python 3.10+ with just `openai` and/or `anthropic` packages.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("eigent_explainer")

# ── Check available API clients ──────────────────────────────────────────────
_HAS_OPENAI = False
_HAS_ANTHROPIC = False

try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    pass

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    pass

# Always available — uses openai or anthropic SDK directly
EIGENT_AVAILABLE = _HAS_OPENAI or _HAS_ANTHROPIC
if EIGENT_AVAILABLE:
    logger.info(f"Eigent explainer ready (openai={_HAS_OPENAI}, anthropic={_HAS_ANTHROPIC})")
else:
    logger.warning("Neither openai nor anthropic SDK found. pip install openai anthropic")

# ── Trade Analysis System Prompt (eigent-style structured prompt) ────────────
TRADE_ANALYSIS_SYSTEM_PROMPT = """\
<role>
You are a Senior Quantitative Trade Analyst embedded in the EigenTrades
automated trading platform. Your job is to explain algorithmic trades to
both expert quants and beginner investors in clear, precise language.
</role>

<expertise>
- Technical Analysis: RSI, MACD, SMA/EMA crossovers, Bollinger Bands, ATR
- Statistical Models: Ridge Regression, Random Forest ensemble signals
- Risk Management: Drawdown analysis, Sharpe ratio, position sizing
- Market Microstructure: Volatility regimes, mean reversion, momentum
</expertise>

<output_rules>
- Be concise: 3-5 sentences for trade explanations, 4-8 for signal analysis
- Use **bold** for key numbers and signal names
- Start with the conclusion (buy/sell/hold) then justify with evidence
- Reference specific indicator values — never be vague
- If the trade was a loss, explain what likely went wrong and what the
  algorithm could watch for next time
- Speak in plain English first, then add technical detail
- Do NOT use markdown tables — use bullet points or inline text
</output_rules>

<context>
Platform: EigenTrades — AI-Powered Algorithmic Trading System
Pipeline: Data Ingestion → Indicator Calculation → ML Prediction → LLM Interpretation
Models: Ridge Regression + Random Forest ensemble
Instruments: Indian equity index futures (NIFTY, BANKNIFTY, FINNIFTY)
</context>
"""

# ── Supported model presets ──────────────────────────────────────────────────
MODEL_PRESETS = {
    "openai": {
        "platform": "openai",
        "model_type": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "claude": {
        "platform": "anthropic",
        "model_type": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "ollama": {
        "platform": "ollama",
        "model_type": "llama3.1:8b",
        "env_key": None,  # Local, no key needed
        "url": "http://localhost:11434/v1",
    },
    "openai-compatible": {
        "platform": "openai-compatible-model",
        "model_type": "default",
        "env_key": "OPENAI_COMPATIBLE_API_KEY",
        "url_env": "OPENAI_COMPATIBLE_API_URL",
    },
    "azure": {
        "platform": "azure",
        "model_type": "gpt-4o-mini",
        "env_key": "AZURE_OPENAI_API_KEY",
        "url_env": "AZURE_API_BASE_URL",
    },
    "openrouter": {
        "platform": "openrouter",
        "model_type": "anthropic/claude-sonnet-4-20250514",
        "env_key": "OPENROUTER_API_KEY",
    },
}


class EigentTradeExplainer:
    """
    Trade explainer powered by the Eigent-inspired multi-provider architecture.

    Uses direct OpenAI/Anthropic SDK calls with eigent-style structured
    system prompts for rich trade explanations. No camel-ai dependency.
    """

    def __init__(
        self,
        provider: str = "openai",
        model_type: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
    ):
        self.provider = provider
        self._ready = False
        self._client = None
        self._model = None
        self._use_anthropic = False

        if not EIGENT_AVAILABLE:
            logger.error("No LLM SDK available")
            return

        try:
            self._init_client(provider, model_type, api_key, api_url)
            self._ready = True
        except Exception as e:
            logger.error(f"Failed to initialise Eigent explainer: {e}", exc_info=True)

    def _init_client(
        self,
        provider: str,
        model_type: str | None,
        api_key: str | None,
        api_url: str | None,
    ):
        preset = MODEL_PRESETS.get(provider, {})
        self._model = model_type or preset.get("model_type", "gpt-4o-mini")

        # Resolve API key
        if api_key is None and preset.get("env_key"):
            api_key = os.environ.get(preset["env_key"], "")

        # Resolve URL
        if api_url is None:
            if "url" in preset:
                api_url = preset["url"]
            elif "url_env" in preset:
                api_url = os.environ.get(preset["url_env"])

        # Anthropic-native provider uses anthropic SDK
        if provider == "claude" and _HAS_ANTHROPIC:
            self._use_anthropic = True
            self._client = anthropic.Anthropic(api_key=api_key or None)
            logger.info(f"Eigent explainer ready — Anthropic SDK, model={self._model}")
        elif _HAS_OPENAI:
            # Everything else uses OpenAI SDK (works with Ollama, Azure, OpenRouter, etc.)
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if api_url:
                kwargs["base_url"] = api_url
            self._client = openai.OpenAI(**kwargs)
            logger.info(f"Eigent explainer ready — OpenAI SDK, provider={provider}, model={self._model}")
        elif _HAS_ANTHROPIC:
            # Fallback to anthropic if openai not installed
            self._use_anthropic = True
            self._client = anthropic.Anthropic(api_key=api_key or None)
            logger.info(f"Eigent explainer ready — Anthropic fallback, model={self._model}")
        else:
            raise RuntimeError("No LLM SDK available")

    # ── Public API (matches ExplainerModule interface) ───────────────────

    @property
    def is_ready(self) -> bool:
        return self._ready and self.agent is not None

    def explain_signal(self, signal_data: Dict, features: Dict) -> Dict:
        """Explain a real-time ML trading signal."""
        start = time.time()

        prompt = self._build_signal_prompt(signal_data, features)
        explanation = self._query_agent(prompt)

        return {
            "explanation": explanation,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "mode": f"eigent/{self.provider}",
        }

    def explain_trade(self, trade_data: Dict, indicators: Dict) -> Dict:
        """Explain a completed trade (entry → exit) in plain English."""
        start = time.time()

        prompt = self._build_trade_prompt(trade_data, indicators)
        explanation = self._query_agent(prompt)

        return {
            "explanation": explanation,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "mode": f"eigent/{self.provider}",
        }

    # ── Internal helpers ─────────────────────────────────────────────────

    def _query_agent(self, user_prompt: str) -> str:
        """Send a query using the appropriate SDK and return the text response."""
        if not self.is_ready:
            return "⚠️ Eigent agent is not available. Check your API key and provider configuration."

        try:
            if self._use_anthropic:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=512,
                    system=TRADE_ANALYSIS_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return response.content[0].text
            else:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=512,
                    temperature=0.3,
                    messages=[
                        {"role": "system", "content": TRADE_ANALYSIS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Eigent query failed: {e}", exc_info=True)
            return f"⚠️ Agent error: {str(e)}"

    def _build_signal_prompt(self, signal_data: Dict, features: Dict) -> str:
        signal = signal_data.get("signal", 0)
        confidence = signal_data.get("confidence", 0)
        top_factor = signal_data.get("top_factor", "unknown")
        ridge = signal_data.get("ridge_decision")
        forest = signal_data.get("forest_probability")

        return f"""Explain this ML-generated trading signal:

**Signal**: {"BUY" if signal == 1 else "HOLD/SELL"}
**Confidence**: {confidence:.0%}
**Top Factor**: {top_factor}

**Indicator Values**:
• RSI: {features.get('rsi', 'N/A')}
• SMA Divergence: {features.get('sma_diff', 'N/A')}
• MACD: {features.get('macd', 'N/A')}
• Bollinger Band Width: {features.get('bb_width', 'N/A')}
• Rolling Volatility: {features.get('volatility', 'N/A')}

**Model Consensus**:
• Ridge Regression: {"BUY" if ridge == 1 else "HOLD/SELL" if ridge is not None else "N/A"}
• Random Forest Buy Probability: {f"{forest:.0%}" if forest is not None else "N/A"}

Explain in 3-5 sentences why this signal was generated. Be specific about
the market conditions each indicator reveals and whether the models agree."""

    def _build_trade_prompt(self, trade_data: Dict, indicators: Dict) -> str:
        entry_price = trade_data.get("entry_price", 0)
        exit_price = trade_data.get("exit_price", 0)
        pnl = trade_data.get("pnl", 0)
        pnl_pct = trade_data.get("pnl_pct", 0)
        reason = trade_data.get("reason", "Technical signal")

        return f"""Explain this completed algorithmic trade to a non-technical investor:

**Entry**: ₹{entry_price:,.2f} on {trade_data.get('entry_date', 'N/A')}
**Exit**: ₹{exit_price:,.2f} on {trade_data.get('exit_date', 'N/A')}
**P&L**: ₹{pnl:,.2f} ({pnl_pct:+.2f}%)
**Exit Reason**: {reason}

**Indicators at Entry**:
• RSI: {indicators.get('rsi', 'N/A')}
• 20-day SMA: {indicators.get('sma_20', 'N/A')}
• Price: {indicators.get('price', entry_price)}

Explain in plain English:
1. WHY the algorithm entered the trade (what the indicators showed)
2. WHY it exited (what triggered the exit)
3. The outcome — was this a good trade? What could be improved?"""


def get_available_providers() -> list[str]:
    """Return list of provider names that have API keys configured."""
    available = []
    for name, preset in MODEL_PRESETS.items():
        env_key = preset.get("env_key")
        if env_key is None:  # e.g. ollama — always available
            available.append(name)
        elif os.environ.get(env_key):
            available.append(name)
    return available


def create_eigent_explainer(
    provider: str = "openai",
    model_type: str | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
) -> Optional["EigentTradeExplainer"]:
    """Factory function — returns None if no LLM SDK is available."""
    if not EIGENT_AVAILABLE:
        return None
    return EigentTradeExplainer(
        provider=provider,
        model_type=model_type,
        api_key=api_key,
        api_url=api_url,
    )
