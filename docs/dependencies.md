# Dependency files

| File | Use |
|------|-----|
| `requirements.txt` | Default full install (API + Streamlit UI) |
| `requirements-api.txt` | Backend only (FastAPI, SQLAlchemy, Chroma, Gemini, etc.) |
| `requirements-ui.txt` | Streamlit UI only |
| `requirements-lock.txt` | Exact package freeze from a known working environment |

Install path for most contributors: `pip install -r requirements.txt`.

Use `requirements-lock.txt` when you need bit-for-bit matching of transitive versions (CI or debugging install drift).

Heavy ML packages (`torch`, `sentence-transformers`, `chromadb`) live under the API extras and make the first install large; that is expected for vector search.
