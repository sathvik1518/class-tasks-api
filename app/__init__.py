"""Class Tasks API. Layers: domain (rules) -> services (use cases) -> repositories (SQL) and api (HTTP).
Nothing in this file imports a layer, so `import app.services` never drags FastAPI or SQLite in."""
