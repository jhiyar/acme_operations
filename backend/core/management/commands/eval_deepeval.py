"""
Run DeepEval metrics against recent agent outputs or canned goldens.

Requires: pip install deepeval (and usually OPENAI_API_KEY for judge models).

  python manage.py eval_deepeval
  python manage.py eval_deepeval --limit 5
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import AgentRun


class Command(BaseCommand):
    help = "Score recent AgentRun replies with DeepEval metrics (Postgres-backed traces)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=8)
        parser.add_argument(
            "--skip-live",
            action="store_true",
            help="Only score already-stored AgentRun rows (default behaviour).",
        )

    def handle(self, *args, **options) -> None:
        try:
            from deepeval import evaluate
            from deepeval.metrics import AnswerRelevancyMetric
            from deepeval.test_case import LLMTestCase
        except ImportError as exc:
            raise SystemExit(
                "deepeval is not installed. Add it with: pip install deepeval"
            ) from exc

        limit = max(1, min(int(options["limit"]), 40))
        runs = list(
            AgentRun.objects.exclude(assistant_reply="")
            .exclude(error__gt="")
            .order_by("-created_at")[:limit]
        )
        if not runs:
            self.stdout.write(self.style.WARNING("No successful AgentRun rows to score."))
            return

        metric = AnswerRelevancyMetric(threshold=0.5)
        cases = [
            LLMTestCase(
                input=run.user_message,
                actual_output=run.assistant_reply,
            )
            for run in runs
        ]

        self.stdout.write(
            self.style.NOTICE(f"Scoring {len(cases)} AgentRun replies with AnswerRelevancy…")
        )
        result = evaluate(test_cases=cases, metrics=[metric])

        out_dir = Path(settings.BASE_DIR) / "evals" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "framework": "deepeval",
            "metric": "AnswerRelevancyMetric",
            "threshold": 0.5,
            "run_ids": [str(run.id) for run in runs],
            "result": str(result),
        }
        path = out_dir / f"deepeval_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        latest = out_dir / "deepeval_latest.json"
        latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"DeepEval results → {path}"))
