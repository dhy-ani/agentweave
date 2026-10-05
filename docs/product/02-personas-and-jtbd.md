# 02. Proto-Personas and Jobs to Be Done

Status: **hypothesis**. These are proto-personas built from the desk research in [01-market-research.md](01-market-research.md). No user interviews have been conducted yet.

## 1. Why proto-personas

Nielsen Norman Group defines proto-personas as "a lightweight form of ad-hoc personas created with no new research", which capture what a team already knows or assumes about users ([NN/g, persona types](https://www.nngroup.com/articles/persona-types/)). They are standard practice for aligning a team before research, and they are meant to be replaced by qualitative personas once interviews and usability tests are done.

Jobs to Be Done (JTBD) statements complement personas. The framing comes from Christensen et al., who argue that customers "hire" products to make progress in a given circumstance, rather than buying on demographics alone ([HBR, September 2016](https://hbr.org/2016/09/know-your-customers-jobs-to-be-done)).

Each persona below lists the research signals it draws on, so that it can be challenged.

## 2. Proto-personas

### Persona A: "The Inspiration Saver"

| Attribute | Hypothesis |
|---|---|
| Age / stage | 19 to 24, university student or first job |
| Current tools | Pinterest boards, TikTok, Instagram saves |
| Budget | Tight; mostly fast fashion and mid-range |
| Behaviour | Saves many looks, rarely turns them into an actual outfit or purchase |
| Frustration | "I have hundreds of saved pins and still nothing to wear." Boards are not connected to her body, weather, or wallet |
| Comfort with AI | High; already uses recommendation-driven feeds |

Signals: Gen Z is over half of Pinterest's user base ([Pinterest Q2 2025](https://www.sec.gov/Archives/edgar/data/1506293/000150629325000195/q2-25xpressrelease.htm)); swipe-based fashion discovery has existed since at least 2013 ([TechCrunch on Mallzee](https://techcrunch.com/2013/12/03/mallzee/)).

**Primary features used:** swipe deck, Saved board, Shop with low budget range.

### Persona B: "The Busy Professional"

| Attribute | Hypothesis |
|---|---|
| Age / stage | 25 to 32, early-career professional |
| Current tools | Has tried a styling box or a wardrobe app; may have stopped |
| Budget | Moderate; will pay more for fewer, better pieces |
| Behaviour | Dresses for work, occasional events, varied weather |
| Frustration | Decision fatigue in the morning; styling boxes felt expensive or ignored requests |
| Comfort with AI | Medium; wants it to save time, not to be a hobby |

Signals: Stitch Fix reviewers cite price and stylists not honouring requests ([Trustpilot](https://www.trustpilot.com/review/stitchfix.com)); Acloset and Whering both lead with weather and schedule based suggestions ([Acloset](https://apps.apple.com/us/app/acloset-ai-fashion-assistant/id1542311809), [Whering](https://apps.apple.com/us/app/-/id1519461680)), implying demand for context-aware picks.

**Primary features used:** preference form (occasion = work, weather), My Closet suggestions, Shop with mid-range budget.

### Persona C: "The Mindful Re-wearer"

| Attribute | Hypothesis |
|---|---|
| Age / stage | 22 to 35 |
| Current tools | Wardrobe app or spreadsheet; follows sustainability creators |
| Budget | Prefers not to buy; buys secondhand or rarely |
| Behaviour | Wants new ways to wear what she owns |
| Frustration | Wardrobe apps require heavy tagging, and auto-tagging is unreliable |
| Comfort with AI | Medium; sceptical of being pushed to shop |

Signals: Indyx positions itself against constant consumption ([Indyx](https://www.myindyx.com)); Whering reviewers report inaccurate auto-tagging and value cost-per-wear data ([Whering App Store](https://apps.apple.com/us/app/-/id1519461680)).

**Primary features used:** My Closet, swipe deck (to learn which aesthetics to recreate), Shop used rarely.

### Anti-persona

Users seeking precise fit or sizing advice. AgentWeave does not measure garments or bodies in centimetres, and body-shape categories are unreliable for fit ([Loughborough University, 2021](https://www.lboro.ac.uk/media-centre/press-releases/2021/may/you-might-not-be-the-body-shape-you-think/)). Stitch Fix or in-store fitting serve this user better.

## 3. Jobs to Be Done

Format: *When [situation], I want to [motivation], so I can [expected outcome].*

### Core functional jobs

| ID | Job statement | Persona | Feature(s) |
|---|---|---|---|
| J1 | When I am getting ready and nothing feels right, I want a few complete outfit ideas suited to today's weather and occasion, so I can decide quickly. | B, A | Preference form, recommendations |
| J2 | When I am bored with my look, I want to see aesthetics I would not have searched for, so I can discover what I actually like. | A | Swipe deck |
| J3 | When I see something I like, I want to keep it in one place with zero effort, so I can come back when I am ready to shop or recreate it. | A, C | Swipe up to save, Saved board |
| J4 | When I have clothes I rarely wear, I want suggestions that combine pieces I already own, so I can get more use out of them. | C, B | My Closet |
| J5 | When I have decided on a look, I want to know where to buy it within my budget, so I do not waste time on items I cannot afford. | A, B | Shop with budget sliders |

### Emotional and social jobs

| ID | Job statement |
|---|---|
| E1 | Help me feel confident that an outfit works for my body, without making me feel judged about my body. |
| E2 | Help me feel that my style is my own, not something a stylist or algorithm imposed. |
| E3 | Let me explore without feeling pressured to buy. |

E1 is in direct tension with the body-shape feature. See the PRD risk register and the design doc's treatment of wording.

## 4. What user interviews must validate

Target: 5 to 8 semi-structured interviews per primary persona, followed by usability tests with about 5 users per round; Nielsen's guidance is that 5 users find most usability problems in a round and that several small rounds beat one large one ([NN/g, 2000](https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/)).

| # | Hypothesis to validate | Method | Signal that would change the plan |
|---|---|---|---|
| H1 | Personas A and B exist as distinct segments with different needs | Interviews, screener | If they collapse into one, simplify IA |
| H2 | Users are comfortable uploading a full-body photo | Interviews, funnel drop-off at photo step | High refusal means make the photo optional and allow manual shape selection or none |
| H3 | Body-shape labels feel helpful rather than judgemental | Interviews, sentiment on result screen | Negative reaction means remove labels from UI and use the shape only internally, or drop the feature |
| H4 | Swiping is preferred to filling a long style quiz | Usability test, A/B of onboarding | If swipes produce poor recommendations, add a short rating step (see TU Wien trade-off in doc 04) |
| H5 | Up-swipe to save is discoverable | Usability test task success | Low discovery means keep visible Save button as primary |
| H6 | Budget split (in-budget vs stretch) is useful, not annoying | Interviews, click-through on stretch picks | No stretch clicks means collapse that section by default |
| H7 | Closet upload effort is acceptable | Task timing, abandonment | High abandonment means batch upload or retailer import |
| H8 | Users return weekly | Retention cohort after launch | Low return means rethink the trigger (for example, weather-based daily pick) |
| H9 | Which retailers matter to each persona | Card sort, interviews | Re-weight the brand catalogue |

## 5. Interview guide outline

1. Walk me through the last time you got dressed for something that mattered.
2. Where do you go for outfit ideas today? Show me (screen share of their saves).
3. What happened the last time you saved an outfit idea? Did you wear or buy anything from it?
4. How do you decide what you can afford for a piece of clothing?
5. Have you used a wardrobe app or styling service? Why did you start or stop?
6. How would you feel about an app asking for a full-body photo? What would make it acceptable?
7. Concept test: show the swipe deck and Shop panel; think aloud.

Questions avoid leading with AgentWeave's features until the concept test, so that problems are heard before solutions are shown.
