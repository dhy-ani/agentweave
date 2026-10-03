# 01. Market Research and Competitive Landscape

Status: desk research, compiled October 2026. Figures are point-in-time snapshots from the linked sources and will drift. App store ratings and review counts were read from the public listing on the date of access.

## 1. Purpose and method

This document positions AgentWeave against products that solve adjacent problems: finding style inspiration, getting outfits chosen for you, organising the clothes you already own, and finding where to buy. It is the input to the personas ([02](02-personas-and-jtbd.md)), the PRD ([03](03-prd.md)) and the design rationale ([04](04-feature-to-design-mapping.md)).

Rules followed:

- Every number and factual claim links to the page it came from.
- User sentiment is summarised from public review pages (App Store, Trustpilot). These are self-selected reviewers, not a representative sample, and are treated as signals, not measurements.
- Anything not verified is either omitted or marked **Assumption**.

## 2. Market context

Only cited figures are included. No total-addressable-market estimate is given because no source was found that sizes "AI outfit recommendation" as a distinct segment.

| Signal | Figure | Source |
|---|---|---|
| Visual inspiration at scale | Pinterest reported 578 million global monthly active users in Q2 2025, up 11% year over year | [Pinterest Q2 2025 results (SEC 8-K)](https://www.sec.gov/Archives/edgar/data/1506293/000150629325000195/q2-25xpressrelease.htm) |
| Young audience on inspiration platforms | Pinterest's CEO stated that "Gen Z has grown to over half of our user base" | [Pinterest Q2 2025 results (SEC 8-K)](https://www.sec.gov/Archives/edgar/data/1506293/000150629325000195/q2-25xpressrelease.htm) |
| Algorithmic styling is a real but contracting business | Stitch Fix: 2.309 million active clients, down 7.9% YoY; net revenue per active client $549, up 3.0%; FY2025 net revenue $1.27 billion, down 5.3% | [Stitch Fix FY2025 results](https://investors.stitchfix.com/news-events/press-releases/news-details/2025/Stitch-Fix-Announces-Fourth-Quarter-and-Full-Fiscal-Year-2025-Financial-Results-09-24-2025/default.aspx) |
| Creator-led shopping is large | LTK reports 44M+ monthly shoppers and $6B+ in annual consumer sales | [LTK company site](https://company.shopltk.com/) |
| Industry intent around AI discovery | The State of Fashion 2025 (BoF and McKinsey) is reported as ranking customer product discovery and search as the top generative-AI use case cited by fashion executives (50%) | [BoF summary of State of Fashion 2025](https://www.businessoffashion.com/articles/technology/the-state-of-fashion-2025-report-generative-ai-artificial-intelligence-search-discovery/), [report PDF](https://www.mckinsey.com/~/media/mckinsey/industries/retail/our%20insights/state%20of%20fashion/2025/the-state-of-fashion-2025-v2.pdf) |

Caveat on the last row: the BoF article returned HTTP 403 to automated fetch, so the 50% figure is taken from search-result excerpts of that article, not a full read. Treat it as indicative.

**Reading of the context.** Inspiration (Pinterest) and creator commerce (LTK) operate at very large scale and skew young. Paid human-plus-algorithm styling (Stitch Fix) still generates meaningful revenue per client but is losing active clients. Fashion executives say discovery is where they expect generative AI to matter. AgentWeave sits at the junction: inspiration-style browsing, lightweight personalisation, and a hand-off to shopping, without a subscription or a box.

## 3. Competitor profiles

### 3.1 Pinterest (visual inspiration)

- **What it does.** Visual search and saving ("pinning") of images into boards. Widely used for outfit inspiration.
- **Business model.** Advertising. Q2 2025 revenue was $998 million ([SEC 8-K](https://www.sec.gov/Archives/edgar/data/1506293/000150629325000195/q2-25xpressrelease.htm)).
- **Strengths.** Scale (578M MAU) and the board metaphor, which is the mental model AgentWeave's Saved board borrows.
- **Limits relevant to AgentWeave.** Pinterest is general-purpose: it does not take body shape, weather, occasion or the user's own wardrobe as structured inputs. Its terms also matter to us directly: users agree "not to scrape, collect, search, copy or otherwise access data or content from Pinterest in unauthorized ways, such as by using automated means" ([Pinterest Terms of Service](https://policy.pinterest.com/en/terms-of-service)). See the data-licensing risk in the PRD.
- **Gap AgentWeave addresses.** Structured, context-aware recommendations (body shape, weather, occasion) with a direct path to shopping or to the user's own closet.

### 3.2 Stitch Fix (algorithmic plus human styling)

- **What it does.** Ships a "Fix" of clothing chosen by stylists assisted by algorithms; customers keep and pay for what they want and return the rest.
- **Business model.** Retail margin on kept items plus a styling fee, reported as $20 and credited toward kept items ([Wikipedia: Stitch Fix](https://en.wikipedia.org/wiki/Stitch_Fix)).
- **What users praise and complain about.** Trustpilot shows a TrustScore of 4.2 from 44,635 reviews at time of access. Recurring positive themes: stylist attentiveness and convenience of trying on at home. Recurring negative themes: pricing perceived as high, inconsistent sizing, and stylists not honouring specific requests ([Trustpilot: Stitch Fix](https://www.trustpilot.com/review/stitchfix.com)).
- **Gap AgentWeave addresses.** Zero-cost, instant exploration with explicit budget control, and no commitment to buy before the user has formed a preference. AgentWeave does not ship clothes and cannot match Stitch Fix on fit.

### 3.3 Whering (digital wardrobe, social)

- **What it does.** Digital closet with background removal, outfit planner, a "Dress Me" randomiser, weather-based suggestions, cost-per-wear analytics, packing lists, wishlists and moodboards ([App Store listing](https://apps.apple.com/us/app/-/id1519461680)).
- **Business model.** Free, with optional in-app purchases (credits $2.99 to $12.99, supporter tiers, a $4.99 outfit maker) ([App Store listing](https://apps.apple.com/us/app/-/id1519461680)). The listing describes itself as the largest free social styling and closet app with 9+ million users (self-reported).
- **What users praise and complain about.** 4.7 out of 5 from 12,000+ ratings. Reviewers praise rediscovering forgotten pieces and the cost-per-wear data; complaints include background removal picking up unwanted elements, limited outfit-maker control, and inaccurate auto-tagging of colour and style ([App Store listing](https://apps.apple.com/us/app/-/id1519461680)).
- **Gap AgentWeave addresses.** Whering starts from what you own. AgentWeave starts from what you might like (swipe deck) and then connects that to both your closet and to shopping.

### 3.4 Acloset (AI wardrobe assistant)

- **What it does.** Photo-to-closet digitisation, AI outfit recommendations based on weather and preferences, virtual try-on with an avatar, outfit calendar, and import of shopping history ([App Store listing](https://apps.apple.com/us/app/acloset-ai-fashion-assistant/id1542311809)).
- **Business model.** Freemium: free up to 100 items; subscriptions from $3.99/month (Basic) to $24.99/month (Expert) ([App Store listing](https://apps.apple.com/us/app/acloset-ai-fashion-assistant/id1542311809)).
- **What users praise and complain about.** 4.4 out of 5 from 5,300+ ratings on the US listing. Praise for ease of use, background removal and weather-based picks; complaints about "wonky" outfit suggestions, connectivity issues when adding items, and limited filtering ([App Store listing](https://apps.apple.com/us/app/acloset-ai-fashion-assistant/id1542311809)).
- **Gap AgentWeave addresses.** Acloset is the closest feature overlap (weather, AI outfits, closet). AgentWeave differs in its discovery-first swipe deck over curated aesthetics and its budget-split shopping hand-off.

### 3.5 Stylebook (paid closet organiser)

- **What it does.** Long-running iOS closet app: import clothes, collage outfits, outfit calendar, packing lists, cost-per-wear stats; describes "over 90 features" and "15+ years" in market; small family-owned business ([App Store listing via AppFollow](https://apps.appfollow.io/ios/stylebook/335709058?country=us)).
- **Business model.** One-time paid app, $4.99 in the US ([AppFollow](https://apps.appfollow.io/ios/stylebook/335709058?country=us)).
- **Gap AgentWeave addresses.** Stylebook is a power-user organisation tool; it does not focus on discovering new aesthetics or on shopping.

### 3.6 Indyx (digital wardrobe plus human stylists)

- **What it does.** Free digital wardrobe (unlimited items, background removal, wear tracking) plus paid sessions with human stylists, for example "The Lookbook Mini" from $60 and "The Lookbook" from $150, and an in-home cataloguing service in select US metros ([Indyx](https://www.myindyx.com)).
- **Business model.** Free app; revenue from stylist services and an "Indyx Insider" paid membership ([Indyx](https://www.myindyx.com)).
- **Positioning.** Explicitly human-led and consumption-sceptical: "The fashion industry has trained us to think that the only way to feel stylish is to buy something new" ([Indyx](https://www.myindyx.com)).
- **Gap AgentWeave addresses.** Instant, free, automated suggestions for users who are not ready to pay a stylist.

### 3.7 Lyst (fashion shopping aggregator)

- **What it does.** Aggregates products across brands and retailers and redirects shoppers to complete purchases on partner sites.
- **Business model.** Commission on referred sales; in 2018 Glossy reported 12,000 brands, 5 million products, and a model where brands could bid higher commission for placement ([Glossy, May 2018](https://www.glossy.co/fashion/how-the-lvmh-backed-aggregator-lyst-does-business/)). These figures are dated; current numbers were not verified.
- **Gap AgentWeave addresses.** Lyst assumes the user already knows what item to search for. AgentWeave helps decide the look first, then generates the search.

### 3.8 LTK and ShopStyle (creator commerce)

- **LTK.** Three-sided marketplace of shoppers, creators and brands; creators curate shoppable posts and earn commission. Reports 44M+ monthly shoppers, $6B+ annual consumer sales and 8,000 integrated retailers ([LTK](https://company.shopltk.com/)).
- **ShopStyle.** Fashion search engine turned affiliate marketplace; acquired by Rakuten-owned Ebates from PopSugar in 2017 ([PerformanceIN, 2017](https://performancein.com/news/2017/02/24/ebates-acquires-popsugars-e-commerce-marketplace-shopstyle/)). Current scale not verified.
- **Gap AgentWeave addresses.** Creator commerce depends on following a person whose taste matches yours. AgentWeave learns taste from the user's own swipes instead.

### 3.9 Swipe-based fashion discovery

- **Mallzee.** Launched in 2013 in the UK; users swipe right to like and left to reject, friends can vote on items, and the company earned affiliate commission on purchases from around 200 retailers ([TechCrunch, Dec 2013](https://techcrunch.com/2013/12/03/mallzee/)). Current operating status not verified.
- **Doppl (Google Labs).** Experimental app for virtual try-on that added an AI discovery feed with shoppable items on 8 December 2025, US only, 18+ ([Google blog](https://blog.google/technology/google-labs/discover-new-outfits-try-them-on-and-shop-from-doppls-new-discovery-feed/)). It is a feed, not a swipe deck, but it targets the same discovery job.
- **Newer App Store entrants.** Search results show listings such as "Tailored: Swipe for Clothes" ([App Store](https://apps.apple.com/us/app/-/id6727003656)). The listing returned 404 on direct fetch, so no features are claimed here beyond the name.
- **Implication.** Swipe-to-like for fashion is an established pattern, not a novel invention. AgentWeave's differentiation is not the gesture itself but what the swipes feed: body-shape and context-aware retrieval, a saved board, a closet, and budget-split shopping.

## 4. Feature comparison

Legend: Yes = core feature per cited source; Partial = present but limited or indirect; No = not offered per the cited source; ? = not verified.

| Capability | AgentWeave | Pinterest | Stitch Fix | Whering | Acloset | Stylebook | Indyx | Lyst | LTK | Mallzee |
|---|---|---|---|---|---|---|---|---|---|---|
| Visual inspiration feed | Yes | Yes | No | Partial | Partial | No | Partial | Partial | Yes | Yes |
| Swipe like / pass | Yes | No | ? | No | No | No | No | No | No | Yes |
| Save to board | Yes | Yes | No | Yes (moodboards) | ? | No | ? | ? | ? | ? |
| Body-shape input | Yes | No | Partial (profile) | No | Partial (fit analysis via AI chat) | No | No | No | No | No |
| Weather / occasion input | Yes | No | ? | Yes | Yes | No | ? | No | No | No |
| Digital closet | Yes | No | No | Yes | Yes | Yes | Yes | No | No | No |
| Outfits from own clothes | Yes | No | No | Yes | Yes | Yes | Yes (human) | No | No | No |
| Shopping links | Yes | Yes | Ships items | Partial | Partial | No | No | Yes | Yes | Yes |
| Explicit budget split | Yes | No | Partial (budget in profile) | No | No | No | No | Partial (filters) | No | ? |
| Human stylist | No | No | Yes | No | No | No | Yes | No | Creators | No |
| Price to user | Free | Free | Styling fee + items | Freemium | Freemium | $4.99 | Free + paid services | Free | Free | Free |

Sources for each cell are the profile sections above. "Partial (budget in profile)" for Stitch Fix reflects that the company describes recommending "based on fit, budget and style preferences" in search-result excerpts of [Wikipedia](https://en.wikipedia.org/wiki/Stitch_Fix).

## 5. Gap analysis

No single product verified above combines all four of:

1. low-effort taste capture (swipe),
2. body-shape and context-aware recommendations,
3. the user's own wardrobe, and
4. a budget-aware hand-off to multiple retailers.

AgentWeave's thesis is that combining them in one session shortens the path from "I don't know what to wear" to either "I'll wear this from my closet" or "I'll look for this, within my budget".

**Assumption (to validate):** users value this combination enough to return. The competitive evidence shows each piece exists and has demand separately; it does not show demand for the combination.

## 6. Risks surfaced by the research

| Risk | Evidence | Where handled |
|---|---|---|
| Training data sourced from Pinterest images conflicts with Pinterest's terms | [Pinterest Terms of Service](https://policy.pinterest.com/en/terms-of-service) | PRD section 9 |
| Body-shape categories are unstable and sensitive | Loughborough University (2021): moving the tape measure by 1 cm could shift 40% of 1,679 women into a different shape class ([Loughborough press release](https://www.lboro.ac.uk/media-centre/press-releases/2021/may/you-might-not-be-the-body-shape-you-think/)) | PRD section 9; design doc section 3 |
| Swipe interfaces trade accuracy for ease | A 2025 TU Wien study (382 participants, leisure activities, not fashion) found swipe had the highest usability and completion but the least accurate preference profiles ([Fink, TU Wien, 2025](https://repositum.tuwien.at/handle/20.500.12708/216555)) | Design doc section 2 |
| Affiliate disclosure if links are ever monetised | FTC guidance asks for clear disclosure near the link ([FTC Endorsement Guides FAQ](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)) | PRD section 9 |

## 7. Deliberately excluded

- Market-size numbers for "fashion apps" or "AI styling": no primary source was fetched that sizes these segments.
- Current Lyst and ShopStyle scale: only dated (2017, 2018) figures were verifiable.
- Acloset's total user count: sources disagreed (the App Store listing and a third-party summary gave different figures), so only ratings data from the listing is used.
- Direct user quotes beyond short phrases visible on review pages.
