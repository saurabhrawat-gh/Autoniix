# Autoniix Wiki Source

This directory holds the source markdown for the GitHub project wiki.
The wiki itself lives in a separate git repo (`Autoniix.wiki.git`) which the
GitHub API/MCP cannot push to directly. Use the sync command below to mirror.

## Sync to wiki

```bash
# From the repo root
git clone https://github.com/saurabhrawat-gh/Autoniix.wiki.git /tmp/autoniix-wiki
cp docs/wiki/*.md /tmp/autoniix-wiki/
cd /tmp/autoniix-wiki
git add -A
git commit -m "Sync wiki from docs/wiki @ $(git -C - rev-parse --short HEAD 2>/dev/null || date +%F)"
git push
```

First-time setup of the wiki: visit the repo on github.com, click the Wiki
tab, and create any page (even empty). That initialises the wiki repo so
the `git clone` above succeeds.

## Page inventory

See `Home.md` for the table of contents. ~74 pages organised into:

- Architecture (5)
- Temporal Workflows (8)
- Application Services (14)
- Providers (6)
- Dashboard BFF (9)
- Dashboard UI (10)
- Database (3)
- Intelligence / ML (3)
- Quality & Environments (3)
- Observability & Ops (5)
- Security (2)
- Testing & CI (2)
- Reference Appendix (3)

## Conventions

- Source file references use repo-relative paths with line ranges:
  `src/services/research/main.py:1-120`.
- Tables list endpoints/signals/columns; code blocks embed key signatures
  and payload shapes.
- Each page ends with a **Related pages** section linking to siblings.
