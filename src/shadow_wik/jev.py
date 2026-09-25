from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .envfile import read_env_key

from .scalp_patterns import SCALP_PATTERNS

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
        key_file = os.getenv("TYPESAFE_KEY_FILE", "").strip()
        if not api_key and key_file:
            try:
                api_key = read_env_key(key_file, "TYPESAFE_API_KEY")
            except ValueError as exc:
                raise JevError(f"jev.py: TYPESAFE_KEY_FILE: {exc}") from None
        if not api_key:
            raise JevError("jev.py: set TYPESAFE_API_KEY or TYPESAFE_KEY_FILE")
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
                "User-Agent": "shadow-wik/0.2",
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


def build_exit_questions() -> dict[str, Any]:
    return {
        "position_continue_to_horizon": {
            "type": "noul",
            "instructions": "Given the supplied live market state and the precommitted trade horizon/event deadline, is continuing to hold the remaining position more favorable than fully exiting now for the rest of that horizon?",
            "criteria": {
                "true": "The original edge remains intact enough that holding through more of the remaining horizon is preferable to exiting now.",
                "false": "Time pressure, event resolution, structure failure, adverse flow, news risk, or diminished upside makes exiting now preferable.",
            },
        },
        "original_trade_thesis_intact": {
            "type": "noul",
            "instructions": "Is the original trade thesis still intact for the remaining precommitted horizon, rather than merely being defended because the position is already owned?",
            "criteria": {
                "true": "Current independent evidence still supports the original thesis inside the remaining horizon.",
                "false": "The thesis is invalidated, materially weakened, expired, or mainly sustained by position ownership/recent narrative reinforcement.",
            },
        },
        "exit_driver": {
            "type": "choice",
            "instructions": "Which single factor should dominate the current sell-side decision? Prefer unknown when evidence is mixed.",
            "criteria": {
                "time_window": "The precommitted holding window is ending or already expired.",
                "target_reached": "The planned economic objective is substantially realized and remaining upside is inferior to exit risk.",
                "thesis_invalidated": "Price/flow/regime evidence invalidates the original reason for entry.",
                "event_resolved": "An earnings release, scheduled news, or other planned catalyst has occurred and the trade's event edge is spent.",
                "risk_spike": "News, liquidity, crowding, or adverse flow risk has risen enough to dominate.",
                "opportunity_cost": "The remaining edge is too weak relative to capital/time tied up in the position.",
                "thesis_intact": "The planned thesis remains intact and the current evidence does not justify exit yet.",
                "unknown": "No single sell driver has enough evidence to dominate.",
            },
        },
        "sell_urgency": {
            "type": "score",
            "instructions": "Rate the urgency of reducing or exiting the position now, considering remaining horizon, event timing, live market structure, news risk, and current P/L.",
            "criteria": [
                "Low: horizon remains open and thesis/structure are intact.",
                "Moderate: some deterioration or time pressure; prepare but no strong need to exit immediately.",
                "High: material thesis/time/risk deterioration makes near-term reduction or exit important.",
                "Extreme: the planned window is exhausted or live evidence shows severe adverse asymmetry requiring immediate human attention.",
            ],
        },
        "exit_action": {
            "type": "choice",
            "instructions": "Concentrate the supplied trade plan, remaining time/event window, current P/L, live market evidence, personas, news risk, and uncertainty into one current position-management action. This is advisory; the human owns the final decision.",
            "criteria": {
                "hold": "Keep the current position size because the remaining edge and horizon still justify exposure.",
                "reduce": "Sell part of the position because edge remains but asymmetry/time/risk no longer supports full size.",
                "exit": "Sell the remaining position because the trade window, thesis, event edge, or risk/reward no longer justifies continued exposure.",
            },
        },
    }


def build_scalp_pattern_questions() -> dict[str, Any]:
    questions: dict[str, Any] = {}
    for pattern in SCALP_PATTERNS:
        questions[pattern.jev_question] = {
            "type": "noul",
            "instructions": (
                f"Does the supplied live intraday market state currently match the scalp pattern "
                f"'{pattern.label}' strongly enough that its stated short-horizon thesis is more likely "
                f"than its falsification condition in the next observation window? "
                "Judge the pattern state only; do not estimate realized profitability."
            ),
            "criteria": {
                "true": pattern.thesis,
                "false": pattern.falsification,
            },
        }
    return questions


def summarize_scalp_patterns(response: dict[str, Any] | None) -> dict[str, float]:
    if not response:
        return {}
    answers = response.get("answers", {})
    out: dict[str, float] = {}
    for pattern in SCALP_PATTERNS:
        value = answers.get(pattern.jev_question, {}).get("noul")
        if isinstance(value, (int, float)):
            out[pattern.key] = round(max(0.0, min(1.0, float(value))), 6)
    return out



def build_opening_hour_questions() -> dict[str, Any]:
    """Questions for one operating mode: the first 60 minutes of the KRX session."""
    return {
        "opening_hour_stance": {
            "type": "choice",
            "instructions": (
                "Inside the first 60 minutes after the KRX open, choose the current base operating stance. "
                "Choose buy_state only when today's observed flow supports taking/keeping long exposure. "
                "Otherwise choose sell_state; sell_state includes staying in cash."
            ),
            "criteria": {
                "buy_state": "Today's observed opening flow supports long exposure strongly enough to justify accepting near-term downside risk.",
                "sell_state": "Evidence does not justify long exposure yet, or protecting optionality/cash is superior to chasing the move.",
            },
        },
        "opening_hour_flow": {
            "type": "choice",
            "instructions": "Classify the currently observed opening-hour flow without extending the claim to the whole trading day.",
            "criteria": {
                "uptrend": "Price/volume structure is persistently accepting higher levels.",
                "downtrend": "Price/volume structure is persistently accepting lower levels.",
                "range": "Neither side has durable control and price is rotating.",
                "unstable": "Direction is changing too quickly or evidence is too contradictory for a stable flow label.",
            },
        },
        "buy_state_action": {
            "type": "choice",
            "instructions": (
                "If already operating in buy_state, choose the action for the opening-hour trade. "
                "The decision must remain inside the first 60-minute window; do not rescue a bad short-horizon trade by inventing a longer thesis."
            ),
            "criteria": {
                "hold": "The opening thesis remains intact and the exit condition has not arrived.",
                "reduce": "The edge has weakened enough that preserving capital is preferable to full exposure.",
                "exit": "The opening thesis is invalidated, the risk/reward has deteriorated, or the planned opening-hour window is ending.",
            },
        },
        "sell_state_action": {
            "type": "choice",
            "instructions": (
                "If operating in sell_state, decide whether today's opening flow justifies a new long entry. "
                "A missed rise is not a realized loss; waiting or observing the whole day are valid outcomes."
            ),
            "criteria": {
                "enter": "Fresh evidence shows a sufficiently asymmetric long entry now.",
                "wait": "The setup may become attractive but confirmation is still missing.",
                "observe_today": "Today's opening flow does not justify taking this risk; preserve cash/optionality.",
            },
        },
        "fomo_risk": {
            "type": "score",
            "instructions": (
                "Rate the risk that a long decision is being driven by fear of missing already-visible upside rather than current forward asymmetry. "
                "Treat uncaptured upside as hypothetical money, not a loss."
            ),
            "criteria": [
                "Low: entry/hold case is independent of the recent rise and has clear invalidation.",
                "Moderate: recent price strength is influencing urgency but evidence remains balanced.",
                "High: the main pressure to act is that price is running without us.",
                "Extreme: the decision is mostly an attempt to recover imagined missed profit.",
            ],
        },
        "falling_knife_risk": {
            "type": "score",
            "instructions": (
                "Rate the risk of calling a falling price an opportunity merely because it is cheaper. "
                "A lower price alone is not evidence of stabilization or reversal."
            ),
            "criteria": [
                "Low: deterioration has stopped and independent stabilization/reversal evidence is present.",
                "Moderate: some stabilization appears but downside control is not established.",
                "High: price is still accepting lower levels and the opportunity thesis is mostly price-cheapness.",
                "Extreme: the trade would average into unresolved downside momentum without a falsifiable reversal signal.",
            ],
        },
        "objectivity_risk": {
            "type": "score",
            "instructions": (
                "Rate how much current P/L, recent missed moves, attachment to an earlier thesis, or urge to be active could distort the next opening-hour decision."
            ),
            "criteria": [
                "Low: current decision can be stated from present evidence with a clear exit/inaction condition.",
                "Moderate: some emotional or position influence is visible but counterevidence is still considered.",
                "High: current position, missed move, or recent loss is materially steering interpretation.",
                "Extreme: the next action is mainly justified by recovering, proving, chasing, or refusing to miss rather than current evidence.",
            ],
        },
    }


def summarize_opening_hour_focus(response: dict[str, Any] | None) -> dict[str, Any]:
    if not response:
        return {
            "status": "unmeasured",
            "stance": None,
            "stance_probabilities": {},
            "flow": None,
            "buy_action": None,
            "sell_action": None,
            "fomo_risk": None,
            "falling_knife_risk": None,
            "objectivity_risk": None,
        }
    answers = response.get("answers", {})
    stance = answers.get("opening_hour_stance", {})
    flow = answers.get("opening_hour_flow", {})
    buy_action = answers.get("buy_state_action", {})
    sell_action = answers.get("sell_state_action", {})
    return {
        "status": "measured" if stance else "missing_opening_hour_answer",
        "stance": stance.get("choice"),
        "stance_probabilities": stance.get("probabilities", {}),
        "flow": flow.get("choice"),
        "buy_action": buy_action.get("choice"),
        "sell_action": sell_action.get("choice"),
        "fomo_risk": answers.get("fomo_risk"),
        "falling_knife_risk": answers.get("falling_knife_risk"),
        "objectivity_risk": answers.get("objectivity_risk"),
    }

def build_questions(*, include_exit: bool = False, include_scalp: bool = False, include_opening_hour: bool = False) -> dict[str, Any]:
    questions = {
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
    if include_scalp:
        questions.update(build_scalp_pattern_questions())
    if include_opening_hour:
        questions.update(build_opening_hour_questions())
    if include_exit:
        questions.update(build_exit_questions())
    return questions


def summarize_exit_focus(response: dict[str, Any] | None) -> dict[str, Any]:
    if not response:
        return {
            "status": "unmeasured",
            "action": None,
            "action_probabilities": {},
            "driver": None,
            "sell_urgency": None,
        }
    answers = response.get("answers", {})
    action = answers.get("exit_action", {})
    driver = answers.get("exit_driver", {})
    return {
        "status": "measured" if action else "missing_exit_answer",
        "action": action.get("choice"),
        "action_probabilities": action.get("probabilities", {}),
        "driver": driver.get("choice"),
        "sell_urgency": answers.get("sell_urgency"),
        "continue_probability": answers.get("position_continue_to_horizon", {}).get("noul"),
        "thesis_intact_probability": answers.get("original_trade_thesis_intact", {}).get("noul"),
    }
