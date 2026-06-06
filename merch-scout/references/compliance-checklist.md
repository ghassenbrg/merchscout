# Compliance Checklist

Run checks for every visible phrase, title, brand candidate, and keyword:

- exact phrase scan,
- near-match scan,
- local forbidden keyword scan,
- known entity scan,
- public figure / celebrity / team / franchise scan,
- marketplace/product policy lint,
- official/public trademark source links or API adapters.

Recommended official/public sources:

- US: USPTO trademark search and data portal.
- EU: EUIPO / TMview.
- UK: UK IPO trademark search.
- JP: J-PlatPat / JPO.
- DE: DPMAregister.
- International: WIPO Global Brand Database.

The v1 local adapter records source URLs and local lint results. Live API credentials are optional. Absence of a live result must be reported as unresolved human-review work, not as safety.
