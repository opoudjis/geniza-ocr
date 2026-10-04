# Extra Tesseract models — provenance

## `orus.traineddata` — pre-reform Russian (added 2026-09-28, on the editor's decision to take on pre-revolutionary Russian)

- Source: https://github.com/AButon-8/iskra_ocr (a single user's repository — NOT in the official `tesseract-ocr` organisation, NOT in `tessdata_contrib`). Fetched 2026-09-28 10:08 from `raw.githubusercontent.com/AButon-8/iskra_ocr/HEAD/orus.traineddata`.
- What it is: `rus` fine-tuned on ground truth from *Iskra* (1900–1905), printed in pre-reform orthography (ѣ, і, ѳ, ѵ, final ъ) — the same period as the venture's Russian-era Esperanto press (*Ruslanda Esperantisto* 1905–07, *La Ondo de Esperanto* 1909–17, *Kovno Esperanto* 1911–14).
- Licence: Apache 2.0 (`iskra_ocr-LICENSE`, beside this file); README kept as `iskra_ocr-README.md`.
- 11,786,045 bytes · sha256 `cac59e7e4b8e29de87a1ab8c831c8abff5bfc4492f137adc3bd31ec9e8bf2a13`.
- Installed by copying to `/opt/homebrew/share/tessdata/orus.traineddata` (Tesseract's model folder on this machine); the model file is git-ignored — re-fetch from the URL above and check the sha256.
- Status: adopted after trial against the stock `rus` model on the project's own pages; the old-letter rule (`tools/ocr_russian_reading.py`) chooses per page between its reading and the stock model's (see `docs/REPLICATION.md`).
