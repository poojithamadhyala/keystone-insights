# LeaseLens

A property-management reporting platform with an AI agent that answers questions about portfolio data and documents. **All data is synthetic.**

> Work in progress. The architecture, quickstart, benchmark table and limitations are filled in as milestones land.

## Quickstart (development)

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY / PINECONE_API_KEY later
make install
make up                   # api → http://localhost:8000/health, web → http://localhost:5173
make check                # lint + typecheck + tests
```

See [DECISIONS.md](DECISIONS.md) for design choices and [BENCHMARKS.md](BENCHMARKS.md) for measured results.
