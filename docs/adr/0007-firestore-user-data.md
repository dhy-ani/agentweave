# 0007. Store user data in Firestore and verify Firebase tokens in the API

Status: Accepted. Supersedes the database part of [0004](0004-vercel-stateless-backend.md).

## Context
The backend kept user data (profile, saved looks, swipes, wardrobe) in SQLAlchemy tables and identified the user by a `firebase_uid` field in the request. The server never checked that value, so anyone who knew or guessed a uid could read or change that user's data. Running Postgres also meant a second provider (Neon) and connection handling inside short-lived Vercel Functions. Sign-in already used Firebase Auth.

## Decision
- All user data lives in Cloud Firestore under `users/{uid}`, with the subcollections `savedLooks`, `swipes`, `closet` and `shopClicks`. The browser reads and writes it directly with the Firebase SDK, using live listeners.
- Access control is in `frontend/firestore.rules`. A user can only reach their own `users/{uid}` tree. Every write is checked against a field whitelist, types and ranges, and server timestamps (`request.time`). Saved looks can't be edited, shop clicks are append-only, and anything not listed is denied. The rules are unit-tested against the Firestore emulator (`npm run test:rules`).
- The API is a stateless ML service. The closet endpoints need a Firebase ID token. The API checks the RS256 signature against Google's published keys, plus the audience, issuer and expiry, and takes the uid only from the token. Photos are stored under `closet/{uid}/` in Vercel Blob.
- Local development runs the Firebase Auth and Firestore emulators under the `demo-agentweave` project, so no cloud account is needed.

## Consequences
- A forged uid no longer gives access to anything. Authorization is enforced in two independent places, and both are tested.
- There is one fewer provider to run. The backend has no database driver and no migrations.
- Firestore is weak at cross-user queries and analytics (joins, aggregates over all users). If that's needed later, export to BigQuery rather than querying in the app.
- Deleting a closet item takes two steps (the Firestore document, then the photo). The frontend deletes the uploaded photo if saving the record fails. A photo can be orphaned if the second call fails, which leaks only storage.
- The local emulator needs Java 11 or newer.
