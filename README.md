# Autoniix

> Strategy: C-Optimized | 10 diversified channels | $328/mo
> Target: $2K profit by Month 7-8

## Development

- **[docs/architecture/TOOLCHAIN.md](docs/architecture/TOOLCHAIN.md)** — pinned toolchain (Rust, Node, Python, Go, Buf, Postgres) and setup instructions
- `make verify-versions` — assert local tools match [`versions.env`](versions.env)
- `make check-drift` — assert every pin file matches `versions.env`
- `make ci-local` — fast Rust CI mirror on host
- `make ci-local-full` — full CI mirror on host (every language)
- `make ci-local-docker` — full CI mirror inside pinned ubuntu:24.04 (max prod parity)
- `make install-hooks` — install pre-push hook (auto drift check)

## Structure

```
autoniix/
├── docs/                    # Architecture & planning (9 docs)
├── scripts/
│   └── setup-sheets.gs      # Google Apps Script — auto-setup all Sheet tabs
├── workflows/               # n8n importable JSON files
│   ├── A-control.json
│   ├── B1-research.json
│   ├── B2-assets.json
│   ├── B3-thumbnail.json
│   ├── B4-assembly.json
│   ├── C-delivery.json
│   ├── D-intelligence.json
│   ├── E-trends.json
│   └── Admin-control.json
└── README.md
```

## Setup Order

### 1. Google Sheets
1. Open your Sheet: `https://docs.google.com/spreadsheets/d/11-vlRvjXfDVLQMnrHzuujE5A1i4luy2DG-ycUtsS-c4`
2. Go to **Extensions → Apps Script**
3. Paste contents of `scripts/setup-sheets.gs`
4. Click **Run → setupAll**
5. Authorize when prompted
6. Verify all tabs are created and data is seeded

### 2. n8n Credentials
Configure in n8n (Settings → Credentials):
- Google Sheets OAuth2
- OpenAI API Key
- Anthropic (Claude) API Key
- Google Gemini API Key
- ElevenLabs API Key
- SerpAPI API Key
- Pixabay API Key
- Pexels API Key

### 3. n8n Variables
Set in n8n (Settings → Variables):
- `SHEET_ID` = `11-vlRvjXfDVLQMnrHzuujE5A1i4luy2DG-ycUtsS-c4`
- `REMOTION_RENDER_URL` = `http://<remotion-server-ip>:3000`

### 4. Import Workflows
For each file in `workflows/`:
1. n8n → Workflows → Import from File
2. Select the JSON file
3. Configure credentials (select your saved credentials in each node)
4. Activate Workflow A first, test, then activate remaining

## Channels (10)

| Brand | Channel | Niche |
|-------|---------|-------|
| Body Signals | Sleep & Recovery | Health |
| Body Signals | Hair & Skin Restoration | Health |
| Body Signals | Gut Health & Digestion | Health |
| Body Signals | Anxiety & Stress Signals | Health |
| Body Signals | Metabolism & Weight Science | Health |
| Money Decoded | Investing for Beginners | Finance |
| Money Decoded | Money Psychology | Finance |
| Money Decoded | Credit & Debt Freedom | Finance |
| Mind Shifts | Dark Psychology & Persuasion | Psychology |
| Mind Shifts | Stoic Mindset | Psychology |

## Docs Index

| Doc | Contents |
|-----|----------|
| 00-OVERVIEW.md | System summary, locked decisions |
| 01-SHEETS-STRUCTURE.md | All 10 tabs, columns, seed data |
| 02-WORKFLOW-NODES.md | Node-by-node for all 9 workflows |
| 03-COST-ANALYSIS.md | C-Optimized costs, scaling |
| 04-STRATEGY-SWITCHING.md | Strategy switching, system controls |
| 05-QUALITY-GATES.md | 30 quality gates, failure points |
| 06-REMOTION-ARCHITECTURE.md | Renderer components, API |
| 07-BUILD-ORDER.md | Build plan, scaling roadmap |
| 08-YOUTUBE-POLICY-SAFETY.md | YouTube policy, legal, safety |
