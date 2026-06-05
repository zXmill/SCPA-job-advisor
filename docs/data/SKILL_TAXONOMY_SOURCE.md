# Skill Taxonomy Source

Updated: 2026-06-01

SCPA uses an authorized local skill taxonomy seed built from:

- ESCO v1.2.1 Web Services API, published by the European Commission DG Employment, Social Affairs and Inclusion.
- O*NET 30.3 Software Skills and Essential Skills text files, published by the O*NET Resource Center.
- SCPA local Indonesian aliases for common user-entered terms such as `ML`, `AI`, `Pembelajaran Mesin`, `Analisis Data`, `Komunikasi`, `Credit Scoring`, `MLOps`, `Docker`, and `Kubernetes`.

Builder:

```bash
python scripts/data/build_skill_taxonomy.py
```

Generated files:

- `data/skills/skills_seed.json`
- `data/skills/skill_aliases.json`

Runtime rules:

- The skill autocomplete seed must come from these authorized sources or local aliases.
- Fake generated skill names such as `Skill 001` must not be used in runtime taxonomy or extraction.
- Scraped LinkedIn-like data may not be used as a required taxonomy dependency unless its license and terms are documented first.
