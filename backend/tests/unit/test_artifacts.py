import hashlib
import io
import json
import os

import pytest

from ai import artifacts
from ai.artifacts import ArtifactError

PAYLOAD = b"fake onnx model bytes" * 100


def _entry(data: bytes) -> dict:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated model dir, cache dir and manifest; downloads served from memory."""
    model_dir = tmp_path / "models"
    cache = tmp_path / "cache"
    model_dir.mkdir()
    manifest = model_dir / "manifest.json"
    monkeypatch.setenv("AGENTWEAVE_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("AGENTWEAVE_MODEL_CACHE_DIR", str(cache))
    monkeypatch.setenv("AGENTWEAVE_MODEL_BASE_URL", "https://example.test/release/v9/")
    monkeypatch.setattr(artifacts, "MANIFEST_PATH", str(manifest))

    served: dict[str, bytes] = {}
    requested: list[str] = []

    def fake_urlopen(url, timeout):
        requested.append(url)
        assert timeout == 60
        return io.BytesIO(served[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(artifacts.urllib.request, "urlopen", fake_urlopen)

    class Env:
        pass

    e = Env()
    e.model_dir, e.cache, e.manifest, e.served, e.requested = model_dir, cache, manifest, served, requested
    e.write_manifest = lambda files: manifest.write_text(json.dumps({"files": files}))
    return e


def test_env_overrides_and_defaults(monkeypatch):
    monkeypatch.delenv("AGENTWEAVE_MODEL_DIR", raising=False)
    monkeypatch.delenv("AGENTWEAVE_MODEL_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTWEAVE_MODEL_CACHE_DIR", raising=False)
    assert artifacts.model_dir() == artifacts.DEFAULT_MODEL_DIR
    assert artifacts.base_url() == artifacts.DEFAULT_BASE_URL
    assert artifacts.cache_dir().endswith("agentweave-models")
    monkeypatch.setenv("AGENTWEAVE_MODEL_BASE_URL", "https://x.test/a//")
    assert artifacts.base_url() == "https://x.test/a"


def test_committed_manifest_lists_every_serving_file():
    manifest = artifacts.load_manifest()
    assert set(artifacts.SERVING_FILES) <= set(manifest["files"])
    for entry in manifest["files"].values():
        assert len(entry["sha256"]) == 64 and entry["size"] > 0


def test_sha256_of_streams_file(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "_CHUNK", 7)
    path = tmp_path / "f.bin"
    path.write_bytes(PAYLOAD)
    assert artifacts.sha256_of(str(path)) == hashlib.sha256(PAYLOAD).hexdigest()


def test_resolve_prefers_local_model_dir_when_size_matches(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    (env.model_dir / "m.onnx").write_bytes(PAYLOAD)
    assert artifacts.resolve("m.onnx") == os.path.join(str(env.model_dir), "m.onnx")
    assert env.requested == []


def test_resolve_uses_cached_copy_from_previous_download(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.cache.mkdir()
    (env.cache / "m.onnx").write_bytes(PAYLOAD)
    assert artifacts.resolve("m.onnx") == os.path.join(str(env.cache), "m.onnx")
    assert env.requested == []


def test_resolve_downloads_and_verifies_missing_file(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.served["m.onnx"] = PAYLOAD
    path = artifacts.resolve("m.onnx")
    assert path == os.path.join(str(env.cache), "m.onnx")
    assert open(path, "rb").read() == PAYLOAD
    assert env.requested == ["https://example.test/release/v9/m.onnx"]
    assert os.listdir(env.cache) == ["m.onnx"]  # no temp file left behind


def test_resolve_redownloads_when_local_file_has_wrong_size(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    (env.model_dir / "m.onnx").write_bytes(PAYLOAD[:-1])
    env.served["m.onnx"] = PAYLOAD
    assert artifacts.resolve("m.onnx").startswith(str(env.cache))


def test_download_with_checksum_mismatch_raises_and_cleans_up(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    tampered = bytearray(PAYLOAD)
    tampered[0] ^= 0xFF
    env.served["m.onnx"] = bytes(tampered)  # same size, different hash
    with pytest.raises(ArtifactError, match="checksum mismatch"):
        artifacts.resolve("m.onnx")
    assert os.listdir(env.cache) == []


def test_download_with_size_mismatch_raises(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.served["m.onnx"] = PAYLOAD + b"x"
    with pytest.raises(ArtifactError, match=f"got {len(PAYLOAD) + 1} bytes"):
        artifacts.resolve("m.onnx")
    assert not (env.cache / "m.onnx").exists()


def test_resolve_without_manifest_uses_any_local_file(env):
    (env.model_dir / "m.onnx").write_bytes(b"whatever size")
    assert artifacts.resolve("m.onnx") == os.path.join(str(env.model_dir), "m.onnx")


def test_resolve_without_manifest_and_without_file_raises(env):
    with pytest.raises(ArtifactError, match="not found"):
        artifacts.resolve("m.onnx")
    assert env.requested == []


def test_resolve_file_not_listed_in_manifest_raises(env):
    env.write_manifest({"other.onnx": _entry(PAYLOAD)})
    with pytest.raises(ArtifactError, match="not listed"):
        artifacts.resolve("m.onnx")


def test_fetch_all_downloads_missing_and_corrupt_files_only(env, tmp_path):
    good, bad = b"good" * 10, b"bad!" * 10
    env.write_manifest({"good.onnx": _entry(good), "bad.onnx": _entry(bad), "new.onnx": _entry(b"new")})
    dest = tmp_path / "bundle"
    dest.mkdir()
    (dest / "good.onnx").write_bytes(good)
    (dest / "bad.onnx").write_bytes(b"BAD!" * 10)  # right size, wrong hash
    env.served.update({"bad.onnx": bad, "new.onnx": b"new"})
    paths = artifacts.fetch_all(str(dest))
    assert [os.path.basename(p) for p in paths] == ["good.onnx", "bad.onnx", "new.onnx"]
    assert sorted(u.rsplit("/", 1)[-1] for u in env.requested) == ["bad.onnx", "new.onnx"]
    assert (dest / "bad.onnx").read_bytes() == bad


def test_write_manifest_records_present_files_and_merges_metadata(env, tmp_path):
    env.manifest.write_text(json.dumps({"checkpoint": "clip", "files": {"stale.onnx": {}}}))
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.onnx").write_bytes(b"aaa")
    result = artifacts.write_manifest(str(src), files=("a.onnx", "missing.onnx"), lora_merged=True)
    on_disk = json.loads(env.manifest.read_text())
    assert on_disk == result
    assert result["checkpoint"] == "clip"
    assert result["lora_merged"] is True
    assert result["release"] == "v9"
    assert result["files"] == {"a.onnx": _entry(b"aaa")}
    assert env.manifest.read_text().endswith("}\n")


def test_write_manifest_creates_manifest_when_absent(env, tmp_path):
    result = artifacts.write_manifest(str(tmp_path), files=())
    assert result == {"release": "v9", "files": {}}
    assert env.manifest.exists()


def test_cache_dir_defaults_to_system_temp(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTWEAVE_MODEL_CACHE_DIR", raising=False)
    monkeypatch.setattr(artifacts.tempfile, "gettempdir", lambda: str(tmp_path))
    assert artifacts.cache_dir() == os.path.join(str(tmp_path), "agentweave-models")


def test_base_url_only_strips_trailing_slashes(monkeypatch):
    monkeypatch.setenv("AGENTWEAVE_MODEL_BASE_URL", "https://x.test/releases/models-X/")
    assert artifacts.base_url() == "https://x.test/releases/models-X"


def test_download_streams_into_temp_file_next_to_destination(env, monkeypatch):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.served["m.onnx"] = PAYLOAD
    seen = []
    serve = artifacts.urllib.request.urlopen

    def spying_urlopen(url, timeout):
        seen.extend(os.listdir(env.cache))  # the temp file exists before any byte arrives
        return serve(url, timeout)

    monkeypatch.setattr(artifacts.urllib.request, "urlopen", spying_urlopen)
    artifacts.resolve("m.onnx")
    assert len(seen) == 1 and seen[0].startswith(".m.onnx.")


def test_checksum_mismatch_message_shows_size_and_hash_prefix(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.served["m.onnx"] = b"short"
    digest = hashlib.sha256(b"short").hexdigest()
    with pytest.raises(ArtifactError) as exc:
        artifacts.resolve("m.onnx")
    assert str(exc.value) == f"m.onnx: checksum mismatch (got 5 bytes, sha256 {digest[:12]}...)"


def test_resolve_ignores_cached_file_with_wrong_size(env):
    env.write_manifest({"m.onnx": _entry(PAYLOAD)})
    env.cache.mkdir()
    (env.cache / "m.onnx").write_bytes(b"partial")
    env.served["m.onnx"] = PAYLOAD
    path = artifacts.resolve("m.onnx")
    assert open(path, "rb").read() == PAYLOAD
    assert len(env.requested) == 1


def test_download_logs_source_size_and_duration(env, caplog):
    big = bytes(2_500_000)
    env.write_manifest({"m.onnx": _entry(big)})
    env.served["m.onnx"] = big
    with caplog.at_level("INFO", logger="ai.artifacts"):
        artifacts.resolve("m.onnx")
    messages = [r.getMessage() for r in caplog.records]
    assert messages[0] == "m.onnx not found locally; downloading from https://example.test/release/v9"
    import re

    match = re.fullmatch(r"Downloaded m\.onnx \(2\.5 MB\) in (\d+\.\d)s", messages[1])
    assert match and float(match.group(1)) < 60


def test_write_manifest_is_pretty_printed_json(env, tmp_path):
    (tmp_path / "a.onnx").write_bytes(b"a")
    manifest = artifacts.write_manifest(str(tmp_path), files=("a.onnx",))
    assert env.manifest.read_text(encoding="utf-8") == json.dumps(manifest, indent=2) + "\n"
