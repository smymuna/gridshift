# GridShift API

The Python service behind GridShift: FastAPI app, scheduler, Energy-Charts client and CLI.
See the [repository README](../../README.md) for the full picture.

Run it on its own:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
gridshift serve                 # http://127.0.0.1:8000/docs
pytest --cov                    # tests
ruff check . && mypy src tests  # lint + types
```

Or from the repository root, through Turborepo: `npm run dev`, `npm test`.

Configuration is read from `GRIDSHIFT_*` environment variables; see [.env.example](.env.example).
