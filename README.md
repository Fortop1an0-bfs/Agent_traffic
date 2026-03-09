# AI Media Service MVP

MVP service that uses a chief AI agent to coordinate specialized sub-agents for:

- Website content
- Telegram channel
- Short videos for TikTok / Reels / Shorts

## What is implemented

- Agent role registry with inputs/outputs/KPIs
- 10 niche directions with unified multi-channel model
- Pilot niche selection and 4-week content strategy
- Content pipeline with templates and QA checks
- Metrics collection and weekly decision loop dashboard
- 8-week MVP sprint plan with A/B tests and scaling gates
- Runnable CLI demo

## Quick start

1. Use Python 3.11+.
2. Run:

```bash
python -m src.ai_media_service.cli
```

## Project layout

- `src/ai_media_service/roles.py` - chief and sub-agent role definitions
- `src/ai_media_service/niches.py` - 10 niche catalog + pilot picker
- `src/ai_media_service/strategy.py` - 4-week strategy builder
- `src/ai_media_service/pipeline.py` - repurposing and QA flow
- `src/ai_media_service/metrics.py` - KPI, A/B tests, weekly report
- `src/ai_media_service/mvp.py` - 8-week rollout model and readiness gates
- `src/ai_media_service/orchestrator.py` - chief-agent coordination logic
- `src/ai_media_service/cli.py` - end-to-end MVP scenario
