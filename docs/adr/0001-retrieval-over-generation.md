# 0001. Recommend by retrieval over a curated image set

Status: Accepted

## Context
The app must show outfit ideas that match a person's context (occasion, weather, location, body shape). Options were: generate images (diffusion), generate text advice (LLM), or retrieve real outfit photos from a collection. The team has a small image collection, no budget for GPU inference, and a requirement that suggestions look like real, shoppable clothing.

## Decision
Embed every curated image once with CLIP and, at request time, embed the user's context as text and return the nearest images (cosine similarity), re-ranked with Maximal Marginal Relevance for variety.

## Consequences
- Cheap and fast at serving time: one text encoding plus a 205 x 512 matrix multiply.
- Every result is a real photo, which keeps Shop links meaningful.
- Quality is bounded by the collection: the system can only show what was curated, and the collection's licensing becomes a product risk (PRD R1).
- Scores are similarities, not probabilities; they must be presented honestly (see the match-score change in 0003's follow-ups).
