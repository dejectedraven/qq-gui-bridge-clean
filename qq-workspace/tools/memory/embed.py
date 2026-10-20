import json
import urllib.request


def embed_text(text: str, model: str = "nomic-embed-text", base_url: str = "http://127.0.0.1:11434", timeout: int = 30):
    base = base_url.rstrip("/")
    attempts = (
        ("/api/embed", {"model": model, "input": text}),
        ("/api/embeddings", {"model": model, "prompt": text}),
    )
    for path, payload in attempts:
        try:
            request = urllib.request.Request(
                base + path,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            if "embeddings" in data and data["embeddings"]:
                return [float(value) for value in data["embeddings"][0]]
            if "embedding" in data and data["embedding"]:
                return [float(value) for value in data["embedding"]]
        except Exception:
            continue
    return None
