# Metadata JSON Schema

`output/metadata/merch_metadata.json` must include:

```json
{
  "schemaVersion": "1.0.0",
  "designId": "string",
  "status": "ready_for_human_review",
  "riskLevel": "low|medium|high",
  "upload": false,
  "humanReviewRequired": true,
  "selectedProducts": ["string"],
  "selectedMarketplaces": ["US"],
  "artworkFiles": [
    {
      "file": "output/final/design_01_standard_apparel_4500x5400.png",
      "canvas": "standard_apparel",
      "width": 4500,
      "height": 5400,
      "transparent": true,
      "validated": true
    }
  ],
  "listings": {
    "US": {
      "brand": "string",
      "title": "string",
      "bullet1": "string",
      "bullet2": "string",
      "description": "string"
    }
  },
  "keywords": {
    "primary": ["string"],
    "secondary": ["string"],
    "removedForRisk": ["string"]
  },
  "compliance": {},
  "researchSummary": {}
}
```

The machine-readable schema is in `assets/metadata-schema.json`.

The validator must check required fields, type correctness, marketplace coverage, artwork file references, upload=false, humanReviewRequired=true, keyword linting, and listing text risk terms.
