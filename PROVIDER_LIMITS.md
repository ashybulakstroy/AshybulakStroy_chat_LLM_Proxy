# Provider Limits

Snapshot date: 2026-03-31

Estimated request limits for the current project setup:

- Groq: 30 RPM, 14,400 RPD
- Cerebras: 30 RPM, 14,400 RPD
- OpenRouter (`:free` models): 20 RPM, 50-1,000 RPD depending on credits
- Gemini 2.5 Flash (`free tier`, if the current project is still on free tier): 10 RPM, 250 RPD
- SambaNova (`free tier`, estimated): 20 RPM, 20 RPD

Notes:

- These values are operational planning limits, not guaranteed SLA values.
- Some providers expose live rate-limit headers in responses, others do not.
- OpenRouter and Gemini often require checking account tier or provider docs in addition to live API responses.
- SambaNova currently exposes daily limits more clearly than per-minute limits in the observed responses.

Observed details used for this estimate:

- Groq live responses and provider docs matched a 30 RPM / 14,400 RPD tier for the tested model.
- Cerebras live headers exposed `30 requests/minute` and `14,400 requests/day`.
- OpenRouter free-model documentation indicates `20 RPM`; free-tier daily limits depend on credits and are typically `50 RPD` or `1,000 RPD`.
- Gemini 2.5 Flash free-tier documentation indicates `10 RPM` and `250 RPD`.
- SambaNova live responses clearly exposed `20 requests/day`; free-tier documentation suggests `20 RPM`.
