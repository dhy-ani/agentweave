# 0004. Run the API on Vercel Functions with external state

Status: Accepted. Supersedes Render as the only target; `render.yaml` is kept as an alternative.

## Context
The product owner asked for the backend to be deployable on Vercel. Vercel Functions have a read-only filesystem except `/tmp`, a 4.5 MB request body limit, and instances that can be recycled at any time. The backend previously wrote SQLite and uploaded wardrobe photos to local disk.

## Decision
- Database: SQLAlchemy with `DATABASE_URL`; Postgres in production (for example Neon via the Vercel Marketplace), SQLite locally. Wardrobe embeddings move from disk into the database row.
- Files: a storage interface with a local implementation for development and a Vercel Blob implementation when `BLOB_READ_WRITE_TOKEN` is set.
- Uploads: downscale images in the browser to 1280 px before upload; the server rejects anything over the limit with HTTP 413 and re-encodes accepted images as JPEG, which also strips EXIF location data.
- Configuration through environment variables only, documented in `backend/.env.example`. Vercel project root directory is `backend/`.

## Consequences
- The same code runs locally, on Render and on Vercel.
- Without `DATABASE_URL` on Vercel the app falls back to an ephemeral SQLite file in `/tmp` and logs a warning; data would not persist.
- The Vercel Blob client calls the HTTP API the official SDK uses because Vercel does not document a raw REST API; it has been tested against a mock, not a live store.
