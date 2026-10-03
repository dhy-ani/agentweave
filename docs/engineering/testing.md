# Testing

## Strategy

| Layer | What it checks | Tools | Where |
|---|---|---|---|
| Unit | Pure logic: swipe direction and card transform, budget guards, prompt building, retrieval math, MMR, score calibration, body-shape rules, ONNX pre/post-processing, artifact checksums, storage, settings | Jest; pytest | `frontend/src/lib/*.test.js`, `backend/tests/unit/` |
| Component / API | Components with mocked `fetch` and Firebase; every FastAPI endpoint through `TestClient` with fake models, an in-memory SQLite database per test and a temporary upload directory | React Testing Library; pytest + FastAPI TestClient | `frontend/src/components/*.test.jsx`, `backend/tests/api/` |
| Model smoke | Real ONNX models end to end (skipped when model files are absent, as in CI) | pytest `-m models` | `backend/tests/test_models_smoke.py` |
| Model parity | ONNX int8 against PyTorch fp32: embedding cosine, top-10 overlap, retrieval metrics, pose keypoints | `backend/ai/onnx_parity.py` | [onnx_parity.md](../../backend/ai/data/eval/onnx_parity.md) |
| Real browser | The swipe deck and full flow in headless Chrome against the real backend and Firebase emulator | Playwright (`playwright-core` + system Chrome) | `frontend/scripts/capture-screenshots.mjs` |
| Mutation | Whether the tests detect injected faults | StrykerJS; mutmut | `frontend/stryker.config.json`, `backend/setup.cfg` |

**Fakes, not mocks of internals.** On the backend, the model layer is swapped at its facade (`model_cache._backend`, `body_shape_classifier._pose`) for deterministic fakes (`backend/tests/fakes.py`). Routers, retrieval, scoring and the database code all run for real, so no test depends on model files or the network.

## Results

| Suite | Count | Result |
|---|---|---|
| Frontend (Jest + RTL) | 99 tests | All pass |
| Backend (pytest) | 345 tests: unit, API and 3 real-model smoke tests | All pass on Windows; smoke tests skip in CI |
| Backend branch coverage (serving code) | | 100% for most modules; 94–99% for `main`, `shopping`, `onnx_inference`, `model_cache`, `body_shape_classifier` |

### Mutation scores

**Frontend (StrykerJS 10, Jest runner):** 63.3% before targeted tests, **87.8%** after.

| Module | Score |
|---|---|
| `lib/budget.js` | 100% |
| `lib/recommendation.js` | 100% |
| `config.js` | 100% |
| `ShoppingPanel` | 94.6% |
| `lib/swipe.js` | 89.3% |
| `SavedBoard` | 87.4% |
| `Dashboard` | 85.8% |
| `FashionCard` | 67.7% |

**Backend (mutmut 3.8, WSL / Ubuntu):** 85.6% before targeted tests, **94.2%** after (1117 of 1186 mutants killed).

| Module | Killed / total |
|---|---|
| `routers/stylegenie.py` | 55 / 55 |
| `ai/score_calibration.py` | 49 / 49 |
| `ai/model_cache.py` | 62 / 65 |
| `image_io.py` | 38 / 40 |
| `ai/artifacts.py` | 224 / 237 |
| `ai/onnx_inference.py` | 248 / 263 |
| `ai/body_shape_classifier.py` | 121 / 129 |
| `settings.py` | 59 / 63 |
| `storage.py` | 65 / 70 |
| `routers/shopping.py` | 74 / 81 |
| `ai/retrieval.py` | 122 / 134 |

### What was deliberately not counted
- **Frontend.** Tailwind `className` and inline `style` mutants are excluded by `frontend/stryker/presentation-ignorer.mjs`, because they only change how something looks. Animation-physics constants carry inline `// Stryker disable` comments with a reason.
- **Backend.** All 69 surviving mutants were reviewed and judged equivalent or behaviour-neutral:
  - encoding defaults that are UTF-8 on Linux,
  - case-insensitive names (HTTP headers, file extensions),
  - arguments equal to their defaults (numpy dtypes, PIL bicubic resampling),
  - redundant guards and unreachable branches,
  - display precision in log messages.

## Bugs found by testing

| Found by | Bug | Fix |
|---|---|---|
| Playwright in real Chrome | react-spring never animated with React 19.1, so no swipe or save ever registered, by button or by drag. Unit tests missed it because they disable animation. | CSS transition plus timer ([ADR 0005](../adr/0005-css-swipe-animation.md)) |
| Component tests | "That was the last look" appeared as soon as the user reached the last card, before acting on it | Track `deckDone` explicitly |
| Real-app review | Raw CLIP text-to-image cosine maxes out around 0.3, so every result showed as a "29% loose match" | Per-modality calibration against same-aesthetic pairs (text AUC 0.95, image 0.87) |
| ONNX parity script | The earlier PyTorch dynamic int8 quantization had degraded text embeddings (cosine 0.29 min) | ONNX weight-only quantization ([ADR 0003](../adr/0003-onnx-serving.md)) |

## Running the tests

**Frontend**, from `frontend/`:

```bash
npm run test:ci
npm run test:mutation
```

`test:ci` runs the Jest suite with coverage. `test:mutation` runs StrykerJS and writes an HTML report to `reports/mutation/`.

**Backend**, from `backend/`:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest --cov --cov-report=term
python -m pytest -m models
```

The last command runs only the smoke tests and needs the ONNX files in `ai/models/`.

**Backend mutation testing** runs on Linux or WSL only, because mutmut does not support native Windows:

```bash
cd backend
mutmut run --max-children 8
mutmut results
mutmut show <mutant-name>
```

**CI** (`.github/workflows/ci.yml`) runs the unit and API suites and the frontend build on every push and pull request. Both mutation suites run weekly and on manual dispatch, and upload their reports as artifacts.
