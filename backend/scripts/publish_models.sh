#!/usr/bin/env bash
# Publish the serving ONNX models as GitHub Release assets (tag models-v1).
#
# NOT run automatically: publishing is a deliberate, human-approved step.
# Prerequisites: `gh auth login`, and the models exported locally:
#   python ai/export_onnx.py && python ai/build_corpus_embeddings.py
#
# ai/models/manifest.json (committed) pins each file's size and SHA-256;
# ai/artifacts.py refuses any download that doesn't match it. If you re-export,
# commit the regenerated manifest + corpus embeddings and publish under a NEW
# tag (e.g. models-v2), then point AGENTWEAVE_MODEL_BASE_URL at it, rather than
# replacing assets of a tag that deployed builds already reference.
set -euo pipefail

cd "$(dirname "$0")/.."

TAG="${1:-models-v1}"
REPO="${REPO:-dhy-ani/agentweave}"
FILES=(ai/models/clip_vision_int8.onnx ai/models/clip_text_int8.onnx ai/models/yolov8n_pose.onnx)

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "missing $f - run python ai/export_onnx.py first" >&2; exit 1; }
done

python - <<'EOF'
import sys
sys.path.insert(0, ".")
from ai import artifacts
manifest = artifacts.load_manifest()["files"]
for name, meta in manifest.items():
    digest = artifacts.sha256_of(f"ai/models/{name}")
    if digest != meta["sha256"]:
        sys.exit(f"{name}: sha256 {digest} does not match manifest.json; re-run export_onnx.py")
print("manifest verified")
EOF

gh release create "$TAG" "${FILES[@]}" \
  --repo "$REPO" \
  --title "AgentWeave serving models ($TAG)" \
  --notes "ONNX models for the serverless backend: CLIP ViT-B/32 (laion2B + LoRA, weight-only int8) vision/text towers and YOLOv8n-pose. Checksums: backend/ai/models/manifest.json."
