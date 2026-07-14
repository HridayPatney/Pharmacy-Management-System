# Experimental scripts

These files are **not** used by the production FastAPI app. They live here
(previously under `backend/testing phase/`) for research and one-off seeding.

| Script | Purpose | Extra deps |
|--------|---------|------------|
| `load_medicines_to_vector_db.py` | Seed Chroma with sample drugs + demo similar search | Full API / ML stack |
| `drugs_webscrape.py` | Playwright scrape of drug pages → CSV | `playwright`, `beautifulsoup4` |
| `ocr_service_paddleocr.py` | Alternate OCR path (PaddleOCR), unused by API | PaddleOCR stack |
| `drug_summaries.csv` | Sample scrape output | — |

Production OCR uses Gemini via `backend/services/ocr_service.py`. Production
indexing happens automatically on inventory add/update.

To rebuild the vector index after changing `EMBEDDING_MODEL` or
`CHROMA_COLLECTION`, see [docs/vector-search.md](../../docs/vector-search.md).
