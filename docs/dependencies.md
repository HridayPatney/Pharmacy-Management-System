# Dependency files

| File | Use |
|------|-----|
| `requirements-api.txt` | **Backend** — FastAPI, SQLAlchemy, pgvector, ONNX MiniLM (via `chromadb` EF only), Gemini client, pytest |
| `requirements.txt` | API + legacy Streamlit UI |
| `requirements-ui.txt` | Streamlit UI only |
| `requirements-lock.txt` | Exact package freeze from a known working environment |

Most backend work: `pip install -r requirements-api.txt`.

Use `requirements-lock.txt` when you need bit-for-bit matching of transitive versions (CI or debugging install drift).

### Notes

- **pgvector** stores embeddings in Postgres. There is **no** Chroma persistent client / disk collection in production.
- `chromadb` is pulled only for its default ONNX embedding function (384-d MiniLM). You do **not** need `torch` or `sentence-transformers` for the supported path.
- First API install can still be large because of ONNX / ML wheels — that is expected.

React UI deps live under `frontend-web/package.json` (`npm ci`).
