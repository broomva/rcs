# memory/ — your knowledge graph

This is your persistent memory. It survives across episodes within a run.
Read existing entries; add new ones when you discover something durable.

## Convention

Every entry is a markdown file with frontmatter:

```markdown
---
name: <human-readable name>
description: <one-line summary>
type: concept | pattern | task
score: 1-9                    # 9 = highly salient/reused
status: draft | canonical
created_episode: <n>
last_used_episode: <n>
related: ["[[other-slug]]", ...]   # wikilinks to related entries
---

<body — your notes, in markdown>
```

## Categories

- `concept/` — what you've learned about the world (facts, patterns, rules)
- `pattern/` — process lessons (e.g., "verify each arithmetic step")
- `task/` — past task records (input, your approach, outcome)

## How to use

- Before starting a task, `find memory -name "*.md" | head -20` to scan
- Search by content: `grep -rl "keyword" memory/`
- Add a new entry: `cat > memory/concept/foo.md << 'EOF'\n---\n...\nEOF`
- Bump score on entries you reuse: edit the frontmatter

## What gets remembered across runs

By default, `memory/` is per-run. The L2 meta-controller decides which
entries get `status: canonical`; canonical entries are candidates for
cross-run promotion (V1 feature).

The L3 governance level may change this convention — check the latest
`memory/SCHEMA.md` if it exists.
