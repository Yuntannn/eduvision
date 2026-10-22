# Samples

Images used by `scripts/smoke_test.py`. They are git-ignored (only this README is tracked), so
add your own. Use your own photos or drawings, not copyrighted images.

Expected files (any supported extension, e.g. `printed.jpg` or `printed.png`):

| File | What it should contain | What the smoke test expects |
|---|---|---|
| `printed` | Printed or typed educational content, such as a textbook page or a formula sheet | Text transcribed correctly, sensible classification, valid explanation |
| `handwritten` | Handwriting, such as a worked maths problem on paper | Text transcribed including instructions like "Solve:", worked-example classification |
| `no_text` | A photo or picture with no readable text, such as a landscape | Analysis fails with `no_text_found` (HTTP 422) |
| `diagram` | A simple labelled diagram, such as a hand-drawn water cycle | Labels and arrows read, and a valid Mermaid diagram in the explanation |

Supported formats: JPEG, PNG, WebP. Maximum size: 10 MB.

A missing sample is skipped with a message; the others still run.

Run: `uv run python scripts/smoke_test.py` (or name samples: `... smoke_test.py diagram`).
This makes real, billed API calls using the settings in `.env`.
