# 03. Product Requirements Document: AgentWeave

| Field | Value |
|---|---|
| Product | AgentWeave (style discovery and outfit recommendation web app) |
| Document status | Living document. Section 5 describes shipped scope; section 6 marks future work |
| Inputs | [01 Market research](01-market-research.md), [02 Personas and JTBD](02-personas-and-jtbd.md) |
| Related | [04 Feature-to-design mapping](04-feature-to-design-mapping.md), [SDLC process](../process/sdlc-how-professionals-build.md) |

## 1. Problem statement

Style-curious users, skewing young women, collect outfit inspiration across many apps but struggle to turn it into a decision: what to wear today, and where to buy a missing piece at a price they can afford. Existing tools each solve one slice. Inspiration platforms are not personalised to body, weather or occasion; wardrobe apps start from what you own and require heavy tagging; styling services cost money and commitment; shopping aggregators assume you already know what to search for ([market research, section 5](01-market-research.md#5-gap-analysis)).

**Problem in one sentence:** there is no low-effort way to go from "I don't know what I like or what to wear" to "this outfit, from my closet or within my budget".

## 2. Goals and non-goals

### Goals

| ID | Goal |
|---|---|
| G1 | Let a new user reach a first personalised outfit recommendation in a single short session |
| G2 | Capture taste with minimal effort (swipes) and make it reusable (saved board) |
| G3 | Help users re-wear what they own (closet suggestions) |
| G4 | Bridge to shopping with explicit budget control, across multiple retailers |
| G5 | Treat body data and photos respectfully: minimal collection, clear purpose, non-judgemental language |

### Non-goals (this release)

- Size and fit prediction. Body-shape categories are not a reliable fit signal ([Loughborough University, 2021](https://www.lboro.ac.uk/media-centre/press-releases/2021/may/you-might-not-be-the-body-shape-you-think/)).
- Checkout, payments, or holding inventory. Shop links hand off to retailer search pages.
- Live product prices or stock. Prices shown are brand-level estimates.
- Human stylists, social feeds, or following other users.
- Native mobile apps. Web only (responsive).
- Affiliate monetisation (see risk R5 before enabling).

## 3. Target users

Primary: proto-personas A "Inspiration Saver" and B "Busy Professional". Secondary: C "Mindful Re-wearer". Anti-persona: users needing precise fit. Full detail in [02](02-personas-and-jtbd.md). All personas are unvalidated hypotheses.

## 4. Scope overview

| # | Feature | Persona | Job (from doc 02) |
|---|---|---|---|
| F1 | Body-shape analysis from photo | A, B | J1, E1 |
| F2 | Preference form and CLIP-based outfit recommendations | A, B | J1, J2 |
| F3 | Swipe deck with like / pass / save, and Saved board | A, C | J2, J3 |
| F4 | My Closet: upload own clothes, get outfit suggestions | C, B | J4 |
| F5 | Shop: budget sliders, ranked retailer links, click tracking | A, B | J5 |
| F0 | Authentication (email and Google via Firebase) | all | prerequisite |

## 5. Shipped features: user stories and acceptance criteria

Acceptance criteria are written in Given / When / Then form and describe current behaviour.

### F0. Sign in

**Story.** As a new or returning user, I want to sign in with email or Google so that my saves, swipes and closet persist.

- Given I am signed out, when I open the app, then I see sign-in and sign-up options for email/password and Google.
- Given I sign in successfully, then a user profile is created or updated on the backend (`POST /user/upsert`) keyed by Firebase UID.
- Given I am signed in, when I reload, then I remain signed in and land on the dashboard.

### F1. Body-shape analysis

**Story.** As a user, I want to upload a full-body photo and get a body-shape category so that recommendations can account for silhouette.

- Given I upload a full-body image, when the backend (`POST /analyze-body`) runs YOLOv8-pose keypoint detection, then shoulder, waist-proxy and hip ratios are computed and mapped by rule to one of: hourglass, pear, apple, rectangle, inverted triangle.
- Given no person or insufficient keypoints are detected, then I see a clear error asking for a clearer, full-body photo, and no category is assigned.
- Given a category is returned, then it is used as an input to recommendations and is shown with neutral wording.
- Large images are resized client-side before upload.

### F2. Preferences and outfit recommendations

**Story.** As a user, I want to tell the app my gender expression, weather, occasion, location and occupation so that the outfits fit my day.

- Given I complete the preference form, when I submit, then the backend builds a text query from body shape and preferences, embeds it with the LoRA-fine-tuned CLIP model, and retrieves the closest images from the curated 205-image dataset spanning 24 aesthetic categories (for example boho beach, Y2K pastel, quiet luxury, techwear, cottagecore).
- Given results are returned, then each card shows an image and a style caption.
- Given the model or retrieval fails, then I see an error message, not a silently blank deck.

### F3. Swipe deck and Saved board

**Story.** As a user, I want to swipe through recommendations so I can react quickly, and save the ones I love to come back to.

- Given a card is shown, when I drag right past the threshold (80 px), then it is recorded as a like (`POST /user/swipe`).
- When I drag left past the threshold, then it is recorded as a pass.
- When I drag up past the threshold, then the outfit is saved to my board (`POST /user/outfits/save`) and I see a confirmation.
- Given a short drag below the threshold, then the card snaps back and no action is recorded.
- Given I cannot or prefer not to drag, then visible Pass, Like and Save buttons perform the same actions with a single tap or click (WCAG 2.2 SC 2.5.1 and 2.5.7; see [doc 04](04-feature-to-design-mapping.md)).
- Given I open the Saved tab, then I see my saved outfits (`GET /user/{uid}/outfits`) and can remove one (`DELETE /user/outfits/{id}`).
- Given the Saved board is empty, then I see an empty state that links back to Discover.

### F4. My Closet

**Story.** As a user, I want to upload photos of my own clothes and get outfit suggestions from them, so I re-wear what I own.

- Given I upload a clothing photo with a category, and optionally a colour and description (`POST /wardrobe/upload`), then it appears in my closet list (`GET /wardrobe/items`).
- Given I delete an item (`DELETE /wardrobe/items/{id}`), then it is removed from the list.
- Given my closet has items, when I request suggestions (`POST /wardrobe/suggest`), then I receive outfit combinations built only from my items.
- Given my closet is empty or too small, then I should see guidance on what to add rather than a raw error. (Verify current behaviour; treat as target if not yet met.)

### F5. Shop

**Story.** As a user, I want to set a budget and see where to buy a look, split into what fits my budget and what is a stretch.

- Given I am viewing a recommended look, when I open Shop, then I can set minimum and maximum price with sliders (range $0 to $500+) or presets (Under $50, $30 to $100, $50 to $200, $100 to $300, $200+). The minimum can never exceed the maximum.
- When I submit (`POST /shopping/suggest`), then the backend scores 18 curated brands (including H&M, Zara, ASOS, Uniqlo, Free People, Anthropologie, Nordstrom, Net-a-Porter) by CLIP similarity between the look's caption and each brand's style description, and returns two lists: within budget and outside budget, each sorted by relevance.
- Each result shows brand, tier (Budget, Mid-Range, Premium, Luxury), suggested item, an estimated price range, and a link to that retailer's search results for the generated query.
- When I click a result, then the click is recorded (`POST /user/shopping/click`) before opening the retailer in a new tab.
- Known limitation: "within budget" compares the budget to a brand-level average price, not to live item prices. The UI must label prices as estimates.

## 6. Prioritisation

### 6.1 MoSCoW for the shipped release

MoSCoW categories follow the DSDM definitions: Must Have is the minimum usable subset; Won't Have is agreed out of scope for this timeframe ([Agile Business Consortium](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/)).

| Item | Category | Rationale |
|---|---|---|
| F0 Sign in | Must | Persistence of saves, swipes and closet depends on identity |
| F2 Preferences and recommendations | Must | Core value; without it there is nothing to swipe |
| F3 Swipe deck and Saved board | Must | Primary interaction and taste capture (J2, J3) |
| F5 Shop with budget split | Should | Closes the loop to purchase; product still useful without it |
| F1 Body-shape analysis | Should | Differentiator, but sensitive and optional by design |
| F4 My Closet | Could | Serves secondary persona C; heavy upload effort |
| Live prices, affiliate links, social, native apps | Won't (this release) | See future backlog |

### 6.2 RICE for the future backlog

RICE = Reach x Impact x Confidence / Effort ([Intercom](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/)). Impact uses Intercom's scale (3 massive, 2 high, 1 medium, 0.5 low, 0.25 minimal); confidence 100/80/50%; effort in person-months. Reach is users per quarter and is a placeholder **assumption** until analytics exist.

| Future item | Reach (assumed) | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|---|
| Use swipe history to re-rank recommendations | 1,000 | 2 | 80% | 1 | 1,600 |
| Make body photo optional with manual or no shape | 1,000 | 1 | 80% | 0.5 | 1,600 |
| Daily weather-based pick (location already collected) | 800 | 1 | 50% | 1 | 400 |
| Live product results via retailer or affiliate API | 600 | 2 | 50% | 3 | 200 |
| Closet auto-tagging (category, colour) | 300 | 1 | 50% | 2 | 75 |
| Retailer import of past purchases into closet | 200 | 1 | 50% | 3 | 33 |

## 7. Success metrics

Definitions only. No values have been measured; targets are set after a baseline period. Instrumentation sources are noted.

| Metric | Definition | Type | Source |
|---|---|---|---|
| Activation rate | Share of new sign-ups who complete preferences and see at least one recommendation in first session | North-star input | Backend events |
| Time to first recommendation | Median seconds from sign-in to first card rendered | Efficiency | Frontend timing |
| Swipe depth | Median swipes per session | Engagement | `/user/swipe` |
| Like rate | Likes / (likes + passes) | Recommendation quality proxy | `/user/swipe` |
| Save rate | Saves / cards shown | Taste capture | `/user/outfits/save` |
| Shop click-through | Sessions with at least one shop click / sessions that opened Shop | Commercial intent | `/user/shopping/click` |
| In-budget click share | Clicks on within-budget results / all shop clicks | Budget-split usefulness (H6) | `/user/shopping/click` |
| Closet adoption | Share of active users with 5+ closet items | Feature adoption | `/wardrobe/items` |
| Photo-step drop-off | Users who leave at body-photo step / users who reach it | Privacy comfort (H2) | Frontend funnel |
| W4 retention | Share of a weekly cohort active in week 4 | Retention (H8) | Backend events |

Guardrails: API error rate and p95 latency per endpoint; zero incidents of photos exposed to other users.

## 8. Assumptions and dependencies

- Firebase Authentication availability for sign-in.
- Retailer search URL formats remain stable; links break silently if a retailer changes its URL scheme.
- The 205-image curated dataset is representative enough of the 24 aesthetics to give acceptable retrieval quality. Not yet evaluated with users.
- Database is configured by `DATABASE_URL` (SQLite by default for local development).

## 9. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Training-data licensing.** Images collected from Pinterest. Pinterest's terms prohibit collecting content "by using automated means" without authorisation, and users retain rights in what they post ([Pinterest ToS](https://policy.pinterest.com/en/terms-of-service)). | High if images were scraped | High (takedown, legal exposure, public demo removed) | Document provenance per image in a datasheet ([Gebru et al.](https://arxiv.org/abs/1803.09010)); replace with licensed, public-domain or self-shot images before any public launch; keep the dataset out of public repos. |
| R2 | **Body-image sensitivity.** Shape labels can feel judgemental; categories are unstable (1 cm tape shift reclassified 40% of 1,679 women) ([Loughborough, 2021](https://www.lboro.ac.uk/media-centre/press-releases/2021/may/you-might-not-be-the-body-shape-you-think/)). | Medium | High (harm to users, brand trust) | Make photo optional; neutral copy with no "flattering" or "hide" language; never show measurements; allow user override; validate in H3. |
| R3 | **Privacy of uploaded photos.** Full-body and wardrobe photos are personal data. | Medium | High | Collect only for stated purpose; do not retain body photos after analysis unless the user opts in; store per-user with access checks on UID; HTTPS only; deletion path for all user data. |
| R4 | **Model bias.** Pose model and CLIP may perform unevenly across body sizes, skin tones, and gender expressions. | Medium | Medium | Evaluate per subgroup and publish a model card ([Mitchell et al., 2019](https://arxiv.org/abs/1810.03993)). |
| R5 | **Undisclosed monetisation.** If affiliate links are added later, FTC guidance requires clear disclosure near the link ([FTC](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)). | Low today | Medium | Add disclosure copy before enabling any commission links. |
| R6 | **Misleading prices.** Budget split uses brand averages. | High | Low to medium | Label as estimates; move to live prices in future backlog. |
| R7 | **Serverless limits.** Model weights and request payloads may exceed hosting limits (for example, 4.5 MB request body on Vercel Functions) ([Vercel limits](https://vercel.com/docs/functions/limitations)). | Medium | Medium | ONNX export, client-side resize, see SDLC doc. |

## 10. Open questions

1. Should body-shape analysis be opt-in, opt-out, or removed if interviews show harm (H3)?
2. What is the retention policy for body photos and closet photos, and is it stated in a privacy notice?
3. Can the curated dataset be fully replaced with licensed imagery without losing aesthetic coverage?
4. Should swipe history change future recommendations, and how is that explained to users?
5. Which retailers should be in the catalogue, and should fast-fashion brands be included given persona C's values?
6. Is "gender expression" collected as free choice, and how does it affect retrieval for non-binary users?
7. What is the minimum closet size for useful suggestions?
8. Will the product ever monetise via affiliate links, and if so, which disclosure pattern?
