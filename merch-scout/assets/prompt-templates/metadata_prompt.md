# Merch Scout Metadata Prompt Template

Generate marketplace metadata for:

```json
{{concept_brief_json}}
```

Rules:

- Return strict JSON only.
- Include brand, title, bullet1, bullet2, description, primary keywords, secondary keywords, and removed risky terms.
- Do not use competitor names, brand names, public figures, official/licensed claims, or misleading keywords.
- Localize naturally for each marketplace.
- Set status to `ready_for_human_review`.
- Include: "Human review is required before upload."
