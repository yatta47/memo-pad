"""Optional LLM explanation for Design Review. Only active when ANTHROPIC_API_KEY is set.

The deterministic result + ontology are passed as context; the model writes the explanation,
it never makes the decision (design §11).
"""
from __future__ import annotations

import json
import logging

from app.config import settings
from app.domain.models import DesignReviewIn, DesignReviewOut

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a data architecture reviewer for an enterprise Knowledge Graph. "
    "Given a proposal for new data and a deterministic analysis (recommendation, candidates, owners, consumers), "
    "write a concise explanation in Japanese (max ~8 sentences) for the proposing engineer: why the recommendation, "
    "which existing assets and teams are involved, and what to confirm before proceeding. "
    "Do not change the recommendation. Do not invent objects that are not in the analysis."
)


def explain(req: DesignReviewIn, result: DesignReviewOut) -> tuple[str | None, str | None]:
    if not settings.llm_enabled:
        return None, None
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        log.warning("anthropic SDK not installed; skipping LLM explanation")
        return None, None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = {
        "proposal": req.model_dump(exclude={"use_llm"}),
        "analysis": result.model_dump(exclude={"llmExplanation", "llmModel"}),
    }
    try:
        response = client.beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
        )
        if response.stop_reason == "refusal":
            return None, response.model
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return text.strip() or None, response.model
    except anthropic.APIStatusError as exc:
        log.warning("LLM explanation failed (%s): %s", exc.status_code, exc.message)
    except anthropic.APIConnectionError as exc:
        log.warning("LLM connection failed: %s", exc)
    except Exception as exc:  # pragma: no cover
        log.warning("LLM explanation failed: %s", exc)
    return None, None
