from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"


class JevError(RuntimeError):
    pass


@dataclass(slots=True)
class JevClient:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "JevClient":
        api_key = os.getenv("TYPESAFE_API_KEY", "").strip()
        if not api_key:
            raise JevError("TYPESAFE_API_KEY is not set")
        return cls(
            api_key=api_key,
            model=os.getenv("JEV_MODEL", DEFAULT_MODEL),
            base_url=os.getenv("TYPESAFE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        )

    def evaluate(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        payload = {"state": state, "model": self.model, "questions": questions}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/systemone",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "shadow-wik/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise JevError(f"Jev HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise JevError(f"Jev connection error: {exc.reason}") from exc


def build_questions() -> dict[str, Any]:
    return {
        "breakout_next_window": {
            "type": "noul",
            "instructions": "Given only the supplied market state, is a clean break above the current intraday prior high more likely to occur before a material rejection in the next observation window?",
            "criteria": {
                "true": "Break and hold above resistance before a material rejection.",
                "false": "Reject, stall, or return materially below resistance before a clean break-and-hold.",
            },
        },
        "next_scenario": {
            "type": "choice",
            "instructions": "Choose the most likely next market scenario inside the supplied observation horizon.",
            "criteria": {
                "breakout_and_hold": "Price breaks the intraday prior high/resistance and remains accepted above it.",
                "false_break_return_range": "Price briefly breaks resistance but returns into the prior range.",
                "rejection_before_breakout": "Price materially rejects before achieving a clean breakout.",
                "reflexive_overshoot": "Positioning feedback such as short covering or momentum chasing causes an outsized extension beyond a normal breakout.",
            },
        },
        "range_regime_ending": {
            "type": "noul",
            "instructions": "Does the evidence indicate that the current range regime is ending rather than showing a temporary excursion?",
            "criteria": {
                "true": "Multiple independent price, flow, breadth, persistence, or information signals support regime transition.",
                "false": "Evidence is consistent with a temporary range excursion or insufficient confirmation.",
            },
        },
        "catalyst_type": {
            "type": "choice",
            "instructions": "Which catalyst class best explains the current move? Prefer unknown when evidence is insufficient.",
            "criteria": {
                "visible_news": "A public news, filing, scheduled event, or clearly observable information catalyst explains the move.",
                "hidden_flow": "Persistent large flow or microstructure evidence exists without a sufficient visible public catalyst.",
                "reflexive_positioning": "Existing positioning, stops, short covering, hedging, or momentum feedback best explains the move.",
                "unknown": "The available evidence is insufficient to assign a cause responsibly.",
            },
        },
        "dominant_persona": {
            "type": "choice",
            "instructions": "Which participant persona is most likely to exert the next meaningful order-flow pressure?",
            "criteria": {
                "momentum_breakout_buyers": "New or waiting buyers chasing a confirmed break.",
                "early_long_profit_takers": "Existing profitable longs supplying stock near resistance.",
                "short_cover_buyers": "Shorts buying to reduce or close losing positions.",
                "mean_reversion_traders": "Range traders fading the move back toward the range.",
                "institutional_hidden_flow": "Persistent larger-scale flow not fully explained by visible news.",
                "mixed_or_unknown": "No single persona has enough evidence to dominate.",
            },
        },
        "news_risk_level": {
            "type": "score",
            "instructions": "Rate how much current or imminent news can destabilize the present position structure.",
            "criteria": [
                "Low: little scheduled or unscheduled information risk and low sensitivity.",
                "Moderate: some event or rumor sensitivity but limited expected position disruption.",
                "High: meaningful scheduled/unscheduled catalyst risk or vulnerable crowding.",
                "Extreme: imminent/high-impact information can rapidly reorder participant positions and price.",
            ],
        },
        "same_position_bias_risk": {
            "type": "score",
            "instructions": "Rate the risk that participants sharing the supplied position are being biased by recent price, recent evidence, or repeated narratives.",
            "criteria": [
                "Low: thesis predates recent moves and has independent counterevidence checks.",
                "Moderate: some recent reinforcement but balanced evidence remains.",
                "High: recent price/news and position ownership materially reinforce the thesis.",
                "Extreme: the thesis is highly recent, crowded, repetitive, and weakly falsifiable.",
            ],
        },
    }
