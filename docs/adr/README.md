# Architecture Decision Records

Short records of significant technical decisions, in the format proposed by Michael Nygard ([Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)): context, decision, consequences. Records are never edited to change history; a later decision supersedes an earlier one.

| # | Decision | Status |
|---|---|---|
| [0001](0001-retrieval-over-generation.md) | Recommend by retrieval over a curated image set, not by generating images or text | Accepted |
| [0002](0002-lora-fine-tuning.md) | Adapt CLIP with LoRA instead of full fine-tuning | Accepted |
| [0003](0003-onnx-serving.md) | Serve models with ONNX Runtime, not PyTorch | Accepted |
| [0004](0004-vercel-stateless-backend.md) | Run the API on Vercel Functions with external state | Accepted (supersedes Render-only hosting) |
| [0005](0005-css-swipe-animation.md) | Drive the swipe animation with CSS and a timer, not react-spring | Accepted |
| [0006](0006-mutation-testing.md) | Gate quality with mutation testing, not line coverage alone | Accepted |
