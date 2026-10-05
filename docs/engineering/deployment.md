# Deployment

**Live:** frontend https://dhy-ani.github.io/agentweave, backend https://agentweave-api.vercel.app (`/health`, `/docs`).

## How deploys happen automatically

| Trigger | Frontend | Backend |
|---|---|---|
| Push to any branch or open a pull request | CI runs tests, build and mutation tests | Vercel builds a preview deployment (once the Vercel GitHub App can see the repo) |
| Push or merge to `main` | `deploy.yml` builds and publishes to GitHub Pages | Vercel builds and promotes to production |

The Vercel project (`agentweave-api`) was set up with the CLI. The exact commands are in section 2b so they can be repeated.

The app is deployed in three parts:
- **Frontend:** a static React build on GitHub Pages.
- **Backend:** FastAPI on Vercel Functions, with `render.yaml` kept as an alternative host.
- **Model files:** versioned GitHub release assets.

## 1. Model artifacts (one-time per model version)

The ONNX models are too large to commit. Their names, sizes and SHA-256 hashes are pinned in `backend/ai/models/manifest.json`.

1. Export them with the training environment:

   ```bash
   cd backend
   pip install -r requirements-train.txt
   python ai/export_onnx.py
   python ai/build_corpus_embeddings.py
   ```

2. Publish them with `bash scripts/publish_models.sh`. This verifies the hashes and creates the `models-v1` release.
3. If you re-export, publish under a **new** tag (for example `models-v2`), commit the new manifest and corpus embeddings, and point `AGENTWEAVE_MODEL_BASE_URL` at the new tag. Never replace the assets of a tag that existing builds use.

`backend/ai/artifacts.py` checks a local directory first, then downloads any missing file and refuses one whose hash doesn't match the manifest.

## 2. Backend on Vercel

1. Import the GitHub repo as a new Vercel project and set **Root Directory** to `backend`. `backend/vercel.json` and `backend/.vercelignore` are picked up from there.
2. Leave "Include files outside the root directory in the Build Step" on (the default). The build script `scripts/vercel_build.py` needs it to copy the curated images from `datasets/processedImages` and to download the models into the bundle.
3. Storage, from the Vercel Marketplace or the Storage tab:
   - **Postgres** (for example Neon): this sets `DATABASE_URL`. `postgres://` URLs are rewritten to the psycopg 3 driver automatically.
   - **Blob store, public access**: this sets `BLOB_READ_WRITE_TOKEN` for wardrobe photos.
4. Environment variables (see `backend/.env.example` for the full list):

   | Variable | Value |
   |---|---|
   | `CORS_ORIGINS` | `https://dhy-ani.github.io` (comma-separate any others) |
   | `AGENTWEAVE_MODEL_BASE_URL` | Only if you use a release tag other than `models-v1` |
   | `LOG_LEVEL` | `INFO` |

5. Deploy, then check `GET https://<project>.vercel.app/health`. Expect `"model_backend": "onnx"`, `"torch_imported": false`, `"database": "postgresql"` and `"storage": "vercel-blob"`.

**Limits to keep in mind** ([Vercel Functions limits](https://vercel.com/docs/functions/limitations)):
- Python bundle: 500 MB. This app is about 398 MB with models bundled. Setting `AGENTWEAVE_BUNDLE_MODELS=0` gives about 230 MB, with the models downloaded to `/tmp` on cold start instead.
- Memory: 2 GB on Hobby. The app uses about 385 MB with all models loaded.
- Request body: 4.5 MB. The frontend downscales photos and the backend returns 413 above the limit.
- `maxDuration` is set to 60 s in `vercel.json`.

## 2b. What was run to create the live backend

From the repo root, logged in with `vercel login`:

```bash
vercel project add agentweave-api
# Root directory + framework (Git Bash on Windows: export MSYS_NO_PATHCONV=1 first)
echo '{"rootDirectory":"backend","framework":"fastapi","sourceFilesOutsideRootDirectory":true}' > body.json
vercel api /v9/projects/agentweave-api -X PATCH --input body.json
vercel link --yes --project agentweave-api
vercel blob create-store agentweave-wardrobe --access public -e production -e preview -e development --yes
vercel integration add neon --name agentweave-db --plan free_v3   # sets DATABASE_URL
printf 'https://dhy-ani.github.io,http://localhost:3000' | vercel env add CORS_ORIGINS production
vercel deploy --prod
vercel git connect https://github.com/dhy-ani/agentweave.git      # enables deploy-on-push
```

Deploying with the CLI from the repo root uses the root `.vercelignore`, which uploads only `backend/` and `datasets/processedImages/`. Git-triggered builds use `backend/.vercelignore`.

`vercel git connect` only works once the Vercel GitHub App has access to the repository. Grant it at GitHub > Settings > Applications > Vercel > Configure > Repository access.

## 3. Frontend on GitHub Pages

`.github/workflows/deploy.yml` builds and publishes on every push to `main`. It needs these repository secrets:

| Secret | Value |
|---|---|
| `REACT_APP_API_URL` | The Vercel backend URL |
| `REACT_APP_FIREBASE_API_KEY`, `REACT_APP_FIREBASE_AUTH_DOMAIN`, `REACT_APP_FIREBASE_PROJECT_ID`, `REACT_APP_FIREBASE_STORAGE_BUCKET`, `REACT_APP_FIREBASE_MESSAGING_SENDER_ID`, `REACT_APP_FIREBASE_APP_ID` | From Firebase project settings |

In the Firebase console, add `dhy-ani.github.io` to Authentication > Settings > Authorized domains so that Google sign-in works.

## 4. Alternative: Render

`render.yaml` deploys the same backend as a long-running web service. The ONNX runtime fits within much smaller instances than the old PyTorch stack did. Render's disk isn't persistent on the free tier either, so set `DATABASE_URL` and `BLOB_READ_WRITE_TOKEN` there as well.

## 5. Release checklist
- [ ] CI is green (frontend tests and build, backend tests).
- [ ] The model release tag in the manifest exists and its hashes match.
- [ ] `/health` on the preview deployment reports ONNX, no torch, Postgres and Blob.
- [ ] One manual run through the full flow on the preview URL: sign in, body photo, preferences, swipe, save, Saved tab, Shop, Closet upload.
- [ ] `REACT_APP_API_URL` points at the production backend.
