# Engineering notes

## EDU-8: real-model smoke test

Model: `claude-haiku-5-5`. Four samples run through `scripts/smoke_test.py`: printed (Newton's second
law triangle), handwritten (`Solve: 2x + 5 = 13`), no_text (a landscape photo) and diagram (a
hand-drawn water cycle). The first run used the prompts as first written (9 API calls for three
samples); later runs were repeated after each change below.

The pipeline worked from the start: text was read correctly, `no_text` failed cleanly with
`no_text_found` (HTTP 422), and the Mermaid diagrams that were produced all parsed with the real
`mermaid` parser. The problems were about fidelity and tone, not crashes.

### What the smoke tests showed, and what changed

| # | Problem seen | Cause | Change |
|---|---|---|---|
| 1 | "Solve:" missing from the handwritten text | Ran the extract step alone: it returns `Solve: 2x + 5 = 13 ...`. The **clean** step was dropping it. | CLEAN prompt: never remove instruction words or labels such as "Solve:" or "Q1". Also told EXTRACT to keep instructions and labels. |
| 2 | Topic casing inconsistent ("Newton's second law" next to lowercase subjects) | Asking for lowercase in the prompt is only a request | Enforced in code: `Classification` validators strip and lowercase `subject` and `topic` (blank is rejected). The prompt just says "lowercase". Tests added. |
| 3 | Diagram descriptions leaked into `text`, and the explanation described the drawing | One field mixed visible text with descriptions of arrows and shapes | `ExtractionResult` has a separate optional `layout`. `text` is only what is written in the image. Layout goes to classify and generate (not clean), is stored in a new `layout` column and returned in the API. |
| 4 | Explanations described the picture ("four wavy arrows", "read the diagram from bottom to top") | GENERATE prompt let the model treat the drawing as the subject | GENERATE now teaches the concept, forbids describing shapes or arrow counts, uses layout only to understand relationships, and keeps difficulty and classification out of the student-facing text (a precaution; not seen in the outputs). Anything beyond the source must be framed as an example or extension. |
| 5 | The Mermaid diagram added a loop (Rain back to Water) that is not in the image | The model completes the "water cycle" it knows | Solid edges may only show relationships present in the image. Inferred ones must be dotted with a label ending "(not shown)". |
| 6 | Layout text was long, with arrow counts and angles | No length limit | EXTRACT: one or two sentences about relationships and order, no counts or angles. |

Before and after, same samples: the printed sample went from `definition` to `diagram` and its
explanation now covers the triangle's use; the diagram sample went from an invented loop plus
"oceans, lakes, rivers" to a faithful diagram with an explicitly labelled inferred edge.

### Things worth remembering

- When an output is wrong, find which step caused it before editing prompts. The "Solve:" bug looked
  like an extraction problem but was in clean.
- Rules the code can enforce (lowercase) belong in code, not in the prompt.
- Splitting one noisy field into two (`text`, `layout`) fixed more than extra prompt wording did.
- Adding a column means deleting the dev database; there is no migration tool.

### Known issues

- **Invented detail in diagram labels.** The latest diagram run labelled a node "Water in oceans
  lakes and rivers"; the image only says "Water". Prompts reduce this but do not remove it.
- **The model can still add content** (for example "falls back down") in the summary and key
  points. Only the examples are reliably framed as extensions.
- **Mermaid is not validated** by the service. It parsed in every smoke run, but a malformed diagram
  would be stored as is.
- **Large images are sent at full size.** A 4032x3024 photo cost about 8,000 input tokens and about
  4 s in extract. Downscaling is planned (Future phases).
- **No Mermaid for formula or table content.** The printed sample is classified as `diagram` but
  gets no diagram, which is acceptable but inconsistent.
- **Small sample set, one model.** Results come from four images and `claude-haiku-5-5`; the eval
  harness (phase 5) is where accuracy should be measured.
- **Smoke runs write to the dev database** and upload directory, which are git-ignored.
