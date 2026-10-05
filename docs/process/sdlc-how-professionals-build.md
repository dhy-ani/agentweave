# How Professional Teams Take a Product From Idea to Production

This is a practical guide to the software development lifecycle (SDLC) as practised by professional product teams, written with AgentWeave as the running example. Each stage covers what teams do, why they do it, and one short line on how AgentWeave applies it. Figures quoted here come from the project's own evaluation reports and test runs; where something has not been measured yet, it says so.

The stages are presented in order, but real teams loop back: usability findings change requirements, evaluation results change data collection, incidents change tests.

## Stage map

| # | Stage | Main artefact | AgentWeave location |
|---|---|---|---|
| 1 | Discovery and market research | Research doc | [docs/product/01](../product/01-market-research.md) |
| 2 | Users and jobs | Personas, JTBD | [docs/product/02](../product/02-personas-and-jtbd.md) |
| 3 | Requirements | PRD | [docs/product/03](../product/03-prd.md) |
| 4 | UX design | Flows, wireframes, design system | [docs/product/04](../product/04-feature-to-design-mapping.md) |
| 5 | Architecture | ADRs | [docs/adr/](../adr/README.md) |
| 6 | ML lifecycle | Datasheet, eval report, model card | [dataset card](../ml/dataset-card.md), [ablation report](../../backend/ai/data/eval/ablation_report.md), [model card](../ml/model-card.md) |
| 7 | Model deployment | Exported model, serving config | `backend/ai/` |
| 8 | API and integration | OpenAPI contract | FastAPI `/docs` |
| 9 | Testing | Test suites, coverage and mutation reports | `test/`, `backend/`, `frontend/` |
| 10 | CI/CD | Pipelines | `.github/workflows/` |
| 11 | Observability | Dashboards, alerts | Structured logs and `/health`; dashboards not built |
| 12 | Security and privacy | Threat model, privacy notice | Known gaps listed in section 12; not yet written |
| 13 | Documentation | README, runbooks | `README.md`, `docs/` |

## 1. Discovery and market research

**What professionals do.** Before building, teams map the competitive landscape, read what users say about existing products, and gather market signals with sources. The output states a problem and a gap, not a solution.

**Why.** It is cheaper to discover that a problem is already well solved, or not painful, before writing code. Citing sources keeps the team honest about what is known versus assumed.

**How AgentWeave applies this.** Desk research on nine competitors with cited figures and an explicit list of excluded, unverifiable claims ([01](../product/01-market-research.md)).

## 2. Users and jobs to be done

**What professionals do.** Teams start with proto-personas, which NN/g describes as lightweight personas "created with no new research" ([NN/g](https://www.nngroup.com/articles/persona-types/)), and replace them with research-based personas after interviews. Jobs to Be Done frames needs as the progress a customer is trying to make in a circumstance ([Christensen et al., HBR 2016](https://hbr.org/2016/09/know-your-customers-jobs-to-be-done)).

**Why.** Personas align the team on who the product is for; JTBD keeps features tied to outcomes rather than to demographics.

**How AgentWeave applies this.** Three hypothesis personas, eight job statements and nine hypotheses to validate in interviews ([02](../product/02-personas-and-jtbd.md)).

## 3. Requirements and the PRD

**What professionals do.** A Product Requirements Document states the problem, goals and non-goals, user stories with testable acceptance criteria, prioritisation, success metrics, risks and open questions. Common prioritisation frameworks are MoSCoW from DSDM ([Agile Business Consortium](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/)) and RICE, scored as Reach x Impact x Confidence / Effort ([Intercom](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/)).

**Why.** Non-goals prevent scope creep. Acceptance criteria become test cases. Defining metrics before launch avoids choosing flattering numbers afterwards.

**How AgentWeave applies this.** PRD with Given/When/Then criteria for five shipped features, MoSCoW for shipped scope, RICE for the backlog, and metrics defined but not yet measured ([03](../product/03-prd.md)).

## 4. UX design

**What professionals do.**

1. **User flows** of the core journey, before any screens.
2. **Low-fidelity wireframes** to test structure cheaply.
3. **Design system**: colour tokens, type scale, spacing, components, accessibility rules.
4. **High-fidelity mockups and prototypes**, typically in Figma, linked to the design system.
5. **Usability testing** in small, repeated rounds. Nielsen's guidance is that about 5 users per round find most problems, and that several small rounds beat one large one ([NN/g, 2000](https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/)).
6. **Accessibility** against WCAG 2.2, for example alternatives to gestures ([SC 2.5.1](https://www.w3.org/WAI/WCAG22/Understanding/pointer-gestures.html), [SC 2.5.7](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html)) and text contrast ([SC 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)).

**Why.** Changing a flow on paper costs minutes; changing it in code costs days.

**How AgentWeave applies this.** Mermaid user flow, four-tab IA, Tailwind colour and font tokens, tap-button alternatives to swipes ([04](../product/04-feature-to-design-mapping.md)). Wireframes and hi-fi screens were built in Figma before code. No usability sessions have been run yet; the test plan is in [04 section 11](../product/04-feature-to-design-mapping.md).

## 5. Architecture and Architecture Decision Records

**What professionals do.** Teams record significant technical decisions as Architecture Decision Records. Michael Nygard's format has five sections: Title, Context, Decision ("We will..."), Status (proposed, accepted, deprecated, superseded) and Consequences; each record is one or two pages, numbered sequentially and stored in version control ([Nygard, 2011](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)).

**Why.** Six months later, nobody remembers why a choice was made. ADRs make trade-offs reviewable and stop old debates from restarting.

**How AgentWeave applies this.** Candidate ADRs: React (CRA) plus FastAPI split; Firebase for auth; SQLAlchemy with `DATABASE_URL` (SQLite default); CLIP retrieval over a curated set instead of a generative model; rule-based body-shape classification on pose keypoints; ONNX for serving. Written as [ADRs 0001 to 0006](../adr/README.md), including two reversals found during this work: PyTorch serving to ONNX, and react-spring to a CSS transition.

Example skeleton:

```markdown
# ADR 0003: Serve CLIP via ONNX Runtime
Status: Accepted
Context: PyTorch adds large dependencies; hosting has bundle and memory limits.
Decision: We will export the fine-tuned CLIP encoders to ONNX and run them with ONNX Runtime.
Consequences: Smaller deploy and faster cold start; export step must be re-run after each training run; parity tests needed.
```

## 6. ML lifecycle

**What professionals do.**

| Step | Practice | Reference |
|---|---|---|
| Problem framing | Decide whether ML is needed at all; a heuristic may get you much of the way. "Don't be afraid to launch a product without machine learning." | [Google, Rules of ML, Rule 1](https://developers.google.com/machine-learning/guides/rules-of-ml) |
| Data collection and licensing | Record where every example came from and under what licence or permission; platform terms may prohibit automated collection | [Pinterest ToS](https://policy.pinterest.com/en/terms-of-service) |
| Curation and documentation | Document motivation, composition and collection process in a datasheet | [Gebru et al., Datasheets for Datasets](https://arxiv.org/abs/1803.09010) |
| Baseline | Start with a simple model and get the pipeline right: "Keep the first model simple and get the infrastructure right." | [Rules of ML, Rule 4](https://developers.google.com/machine-learning/guides/rules-of-ml) |
| Training | Prefer parameter-efficient fine-tuning when data is small; LoRA freezes pretrained weights and trains low-rank adapters | [Hu et al., LoRA](https://arxiv.org/abs/2106.09685) |
| Evaluation | Measure on held-out data never used for training or tuning; compare against the baseline; break results down by subgroup | [Mitchell et al.](https://arxiv.org/abs/1810.03993) |
| Model card | Short document reporting intended use, evaluation across groups and conditions, and limitations | [Mitchell et al., FAT* 2019](https://arxiv.org/abs/1810.03993) |

**Why.** Most ML failures in products are data and evaluation failures, not algorithm failures. Without a held-out set, reported accuracy is optimistic; without provenance, a dataset can become a legal liability.

**How AgentWeave applies this.**

- Body shape: rule-based ratios on 17 COCO keypoints from a YOLO pose model ([Ultralytics pose docs](https://docs.ultralytics.com/tasks/pose/)), effectively a heuristic baseline.
- Recommendations: CLIP ([Radford et al., 2021](https://arxiv.org/abs/2103.00020)) fine-tuned with LoRA on 205 curated images across 24 aesthetics.
- Baseline vs fine-tuned retrieval on the held-out split: P@5 0.487 to 0.494, mAP@5 0.427 to 0.450, class-separation margin 0.145 to 0.191 ([ablation report](../../backend/ai/data/eval/ablation_report.md)).
- Image provenance: scraped from Pinterest, licences unverified; documented in the [dataset card](../ml/dataset-card.md) (PRD risk R1).
- [Model card](../ml/model-card.md) for both models. Performance across body sizes and skin tones has not been measured; the card lists it as the first recommended audit.

## 7. Model deployment and serving

**What professionals do.**

- **Export to a portable format.** ONNX is "an open format built to represent machine learning models" usable across frameworks and runtimes ([onnx.ai](https://onnx.ai/)).
- **Quantise** where accuracy allows. ONNX Runtime converts float models to 8-bit integers to cut size and memory; dynamic quantisation is suggested for transformer models and static for CNNs ([ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
- **Respect platform limits.** Serverless platforms cap bundle size, memory, duration and payloads. For example, Vercel Functions document a 250 MB uncompressed bundle limit (500 MB for Python), 2 GB default memory, and a 4.5 MB request or response body limit ([Vercel Functions limits](https://vercel.com/docs/functions/limitations)).
- **Cache warm models** in memory between requests and verify output parity between the training framework and the exported model.

**Why.** A model that works in a notebook can fail in production because of cold-start time, memory, or payload size.

**How AgentWeave applies this.** CLIP is exported to ONNX (`backend/ai/export_onnx.py`, `backend/ai/onnx_inference.py`) and cached (`backend/ai/model_cache.py`); images are resized client-side before upload (`frontend/src/lib/resizeImage.js`). Weight-only int8 quantization (int4 token embeddings), chosen after plain dynamic int8 broke the text encoder: vision 98.4 MB, text 55.7 MB, pose 13.5 MB; parity 0.998 / 0.994 mean cosine for image / text; serving bundle 398 MB of Vercel's 500 MB; about 385 MB resident. Cold-start latency on Vercel has not been measured ([ADR 0003](../adr/0003-onnx-serving.md)).

## 8. API design and frontend-backend integration

**What professionals do.**

- **Contract first.** Describe the API in OpenAPI, "a standard, language-agnostic interface to HTTP APIs" ([OpenAPI Specification](https://swagger.io/specification/)); generate docs and, optionally, typed clients from it.
- **Typed request and response models** with validation at the boundary.
- **Config in the environment**, not in code: API base URLs, keys and database URLs vary per deploy ([Twelve-Factor App, Config](https://12factor.net/config)).
- **CORS** configured to allow only known frontend origins. When credentials are involved, the server must name an explicit origin rather than `*` ([MDN, CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)).
- **Consistent errors** with proper HTTP status codes.

**Why.** A contract lets frontend and backend work in parallel and catches breaking changes in review.

**How AgentWeave applies this.** FastAPI generates the OpenAPI schema and Swagger UI automatically ([FastAPI features](https://fastapi.tiangolo.com/features/)); Pydantic models type requests; the frontend reads `REACT_APP_API_URL`; the backend reads `DATABASE_URL`. CORS origins come from `CORS_ORIGINS`, oversize uploads return 413, and every setting is documented in `backend/.env.example`. Remaining gap: `/analyze-body` still reports "no person found" as HTTP 200 with an `error` field, kept for frontend compatibility.

## 9. Testing strategy

**What professionals do.**

- **Test pyramid.** Mike Cohn's pyramid, as explained by Ham Vocke: write lots of small, fast unit tests, some coarser integration or service tests, and very few end-to-end tests; avoid the inverted "ice-cream cone" ([Practical Test Pyramid, martinfowler.com](https://martinfowler.com/articles/practical-test-pyramid.html)).

| Layer | Scope | AgentWeave examples |
|---|---|---|
| Unit | Pure functions | `swipeDirection`, budget slider guards, body-shape ratio rules, query building in Shop |
| Integration | API plus database, model stubbed or small | FastAPI `TestClient` on `/shopping/suggest`, `/user/swipe`, `/wardrobe/*` |
| End-to-end | Real browser through core flow | Sign in, preferences, swipe, save, shop click |

- **Coverage as a floor, not a goal.** Line coverage shows which lines ran, not whether a test would notice if they were wrong.
- **Mutation testing** measures that difference. Tools insert small bugs ("mutants") into the code and rerun the tests; a mutant is "killed" if a test fails. Stryker: "The higher the percentage of mutants killed, the more effective your tests are", and it notes that coverage can be inflated by tests without assertions ([Stryker docs](https://stryker-mutator.io/docs/)). For Python, mutmut runs with `mutmut run` and lets you inspect surviving mutants with `mutmut browse` ([mutmut docs](https://mutmut.readthedocs.io/en/latest/)). A surviving mutant points to a missing or weak assertion.
- **ML-specific tests**: shape and dtype checks, ONNX vs PyTorch output parity within a tolerance, and a fixed small evaluation set as a regression check.

**Why.** Fast lower-level tests give quick feedback; mutation score shows whether those tests actually check behaviour.

**How AgentWeave applies this.** 99 frontend tests (Jest + React Testing Library) and 347 backend tests (pytest, with fake models at the model facade), plus Playwright runs in real Chrome and an ONNX-vs-PyTorch parity script. Mutation scores: StrykerJS 63.3% to 87.8%, mutmut 85.6% to 94.2%. Testing found four real bugs, including a swipe deck that never registered swipes in real browsers ([testing guide](../engineering/testing.md)).

## 10. CI/CD

**What professionals do.** Continuous integration means frequently committing to a shared repository so errors are caught quickly ([GitHub Docs, CI](https://docs.github.com/en/actions/get-started/continuous-integration)). Every pull request runs lint, unit and integration tests and a build; merges to main deploy automatically to a preview and then production. Delivery performance is tracked with DORA's metrics: change lead time, deployment frequency, failed deployment recovery time, change fail rate, and deployment rework rate ([DORA](https://dora.dev/guides/dora-metrics-four-keys/)).

**Why.** Small, frequent, automatically tested changes are easier to review and to roll back.

**How AgentWeave applies this.** `.github/workflows/ci.yml` runs frontend tests and build plus backend tests on every push and pull request, and both mutation suites weekly or on demand; `deploy.yml` publishes the frontend to GitHub Pages; the backend targets Vercel ([deployment guide](../engineering/deployment.md)).

## 11. Observability

**What professionals do.** Instrument logs, metrics and traces, and alert on symptoms users feel. Google's SRE book recommends four golden signals: latency, traffic, errors and saturation ([Google SRE book](https://sre.google/sre-book/monitoring-distributed-systems/)). Product analytics events back the PRD metrics. Logs are structured and never contain personal data or images.

**Why.** Without signals, the first report of an outage comes from a user.

**How AgentWeave applies this.** The backend logs through `logging` with method, path, status and duration per request, and `/health` reports model backend, loaded models, database and storage. Product events exist for swipes, saves and shop clicks. Dashboards and alerts are not built yet.

## 12. Security and privacy

**What professionals do.**

- Threat-model the system and review against the [OWASP Top 10](https://top10.owasp.org/).
- **Verify identity server-side.** Firebase recommends sending the ID token to the server over HTTPS and verifying it there to obtain the `uid` ([Firebase, verify ID tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens)), rather than trusting a UID supplied by the client.
- Keep secrets out of the repository (environment variables, CI secrets).
- **Data minimisation** for sensitive inputs such as body photos: collect only what is needed, define retention, provide deletion, and explain it in a privacy notice.
- Dependency scanning and pinned versions.

**Why.** Photos of people's bodies and wardrobes are personal; a leak would be a serious harm and a trust-ending event.

**How AgentWeave applies this.** Firebase handles sign-in and build-time secrets come from GitHub Actions secrets. Gaps: user routes accept `firebase_uid` from the path or body without server-side token verification; body-photo retention policy and privacy notice are not yet written. Both remain open and are tracked as PRD risk R3. Wardrobe uploads are re-encoded server-side, which strips EXIF location data.

## 13. Documentation

**What professionals do.** Keep docs next to the code and update them in the same pull request: a README with setup, run and test commands; architecture overview and ADRs; API reference generated from the contract; model cards and datasheets; runbooks for deploy and rollback; and product docs (research, PRD, design rationale).

**Why.** Docs that live elsewhere go stale; docs in the repo are reviewed with the change that makes them necessary.

**How AgentWeave applies this.** `README.md`, auto-generated API docs at `/docs`, and this `docs/` tree. Also [ADRs](../adr/README.md), a [model card](../ml/model-card.md), a [dataset card](../ml/dataset-card.md), a [deployment guide](../engineering/deployment.md) and a [testing guide](../engineering/testing.md).

## Checklist before calling a release production-ready

- [ ] PRD acceptance criteria have matching automated tests
- [ ] Held-out evaluation and model card published for each model
- [ ] Image provenance documented; unlicensed images removed
- [ ] Server-side Firebase token verification on all user routes
- [ ] CORS origins and API URLs from environment variables
- [ ] Body-photo retention and deletion implemented and disclosed
- [ ] CI runs tests on every pull request; deploy is automatic and reversible
- [ ] Golden-signal dashboards and error alerts in place
- [ ] WCAG 2.2 AA checks for contrast, target size and gesture alternatives
