# NuvePro one-shot checklist

You get **one** upload. Use this checklist so the lab boots with **one command**.

## What to upload

1. On your Mac, from the project root:

```bash
chmod +x scripts/start.sh scripts/stop.sh scripts/pack_for_nuvepro.sh
./scripts/pack_for_nuvepro.sh
```

2. Upload `../cap_proj_nuvepro.zip` to NuvePro and extract it.

The packer **includes `.env`** (needed for Bedrock). Do **not** share that zip publicly.

Excluded from the zip: `.venv`, `.git`, caches, old reports, vector indexes (rebuilt on first run).

## Before you pack (required)

Confirm `.env` has live AWS Bedrock values:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION_NAME=us-east-1`
- `BEDROCK_PRIMARY_MODEL_ID=amazon.nova-lite-v1:0`
- `AGENT_AUTH_TOKEN=…` (any non-empty string is fine for the lab)

Quick local proof:

```bash
uv run python scripts/bedrock_ping.py
```

Must print `LIVE`.

## One command on NuvePro

```bash
chmod +x scripts/start.sh scripts/stop.sh
./scripts/start.sh
```

That will:

1. Install `uv` if missing  
2. `uv sync` (create `.venv` + install deps)  
3. Seed `data/input` from `Documentation/Data/incoming` if empty  
4. Start **lab stack**: Mock EHR `:8050` + Primary MCP `:8200` + Secondary MCP `:8201` + Streamlit `:8501`  
5. Bind with `BIND_HOST=0.0.0.0` so the lab browser can reach the UI  

Open **http://127.0.0.1:8501** (or the NuvePro forwarded URL for port **8501**).

### Optional modes

```bash
./scripts/start.sh          # HITL demo (recommended)
./scripts/stop.sh           # stop all
```

## After start — smoke test

1. Sidebar: search `1020` or `Diego`  
2. **Document Viewer** → **Process patient**  
3. **Validation Report** / **Corrections** / **Discharge Summary** as needed  

Logs: `logs/mock_ehr.log`, `logs/primary_mcp.log`, `logs/hitl_dashboard.log`, …

Stop: `./scripts/stop.sh`.

## If something fails

| Symptom | Fix |
|--------|-----|
| `uv: command not found` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` then `export PATH="$HOME/.local/bin:$PATH"` |
| Port busy | `./scripts/start.sh` clears `:8050/:8200/:8201/:8501` best-effort |
| Process patient fails | Check Bedrock: `uv run python scripts/bedrock_ping.py` |
| Empty patient list | Ensure `data/input/doctor_reports` has files (start.sh reseeds from Documentation) |
| Can’t open UI remotely | Confirm `BIND_HOST=0.0.0.0` (start.sh sets this) |

## Do not

- Prefer `./scripts/start.sh` for the lab boot (EHR + MCP + Streamlit).
- Do not upload `.venv` (huge; `uv sync` recreates it).  
- Do not forget AWS keys in `.env` before packing.
