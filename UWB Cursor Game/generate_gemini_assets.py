#!/usr/bin/env python3
import base64
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request


API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


ASSET_SPECS = [
    {
        "name": "bg_space_arena",
        "model": "nano-banana-pro-preview",
        "modalities": ["IMAGE"],
        "prompt": (
            "Cinematic game background, sci-fi space arena with anime arcade energy, "
            "neon cyan and orange lights, soft depth fog, no characters, no text, "
            "clean center area for UI readability, wide 16:9 composition."
        ),
        "out_dir": "assets/generated/backgrounds",
        "preferred_ext": ".jpg",
    },
    {
        "name": "bg_redlight_stage",
        "model": "nano-banana-pro-preview",
        "modalities": ["IMAGE"],
        "prompt": (
            "Stylized red-light-green-light futuristic game stage, hazard stripes, "
            "checkpoint gates, dramatic perspective track, anime arcade art direction, "
            "no text, no characters, wide 16:9 composition."
        ),
        "out_dir": "assets/generated/backgrounds",
        "preferred_ext": ".jpg",
    },
    {
        "name": "coin_core",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite icon of an energy coin, transparent background, bold outline, "
            "high contrast, glossy arcade style, cyan and gold."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "bomb_core",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite icon of a hazard bomb, transparent background, strong silhouette, "
            "arcade style, red and black, no text."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "warning_core",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite warning symbol, transparent background, triangular hazard icon, "
            "bold neon outline, red/orange/yellow, no text."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "goal_core",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite finish target emblem, transparent background, futuristic checkpoint icon, "
            "bold cyan glow, arcade style, no text."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "checkpoint_ring",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite ring gate checkpoint, transparent background, anime arcade style, "
            "neon cyan/orange ring with clear center hole, no text."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "pulse_safezone",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite safe zone marker, transparent background, glowing circular platform, "
            "cyan and green energy rings, high contrast."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
    {
        "name": "rhythm_note",
        "model": "gemini-2.5-flash-image",
        "modalities": ["IMAGE"],
        "prompt": (
            "Game sprite rhythm hit marker, transparent background, neon star-note hybrid icon, "
            "magenta and cyan, arcade style."
        ),
        "out_dir": "assets/generated/sprites",
        "preferred_ext": ".png",
    },
]


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ext_for_mime(mime: str, preferred: str) -> str:
    if mime == "image/png":
        return ".png"
    if mime == "image/jpeg":
        return ".jpg"
    return preferred


def extract_inline_image(resp_obj: dict):
    candidates = resp_obj.get("candidates", [])
    for c in candidates:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData")
            if inline and inline.get("data"):
                return inline
    return None


def run():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY is required", file=sys.stderr)
        sys.exit(2)

    metadata = {
        "generated_at_unix": int(time.time()),
        "assets": [],
    }

    for spec in ASSET_SPECS:
        model = spec["model"]
        url = f"{API_ROOT}/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": spec["prompt"]}]}],
            "generationConfig": {"responseModalities": spec["modalities"]},
        }
        print(f"[gen] {spec['name']} ({model})")
        try:
            resp_obj = post_json(url, payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"HTTPError for {spec['name']}: {e.code} {body}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Request failed for {spec['name']}: {e}", file=sys.stderr)
            continue

        if "error" in resp_obj:
            print(f"API error for {spec['name']}: {resp_obj['error']}", file=sys.stderr)
            continue

        inline = extract_inline_image(resp_obj)
        if not inline:
            print(f"No inline image returned for {spec['name']}", file=sys.stderr)
            continue

        mime = inline.get("mimeType", "")
        data = inline.get("data", "")
        raw = base64.b64decode(data)

        out_dir = pathlib.Path(spec["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = ext_for_mime(mime, spec["preferred_ext"])
        out_path = out_dir / f"{spec['name']}{ext}"
        out_path.write_bytes(raw)

        metadata["assets"].append(
            {
                "name": spec["name"],
                "model": model,
                "mime": mime,
                "path": str(out_path),
                "prompt": spec["prompt"],
                "bytes": len(raw),
            }
        )
        print(f"  -> {out_path} ({mime}, {len(raw)} bytes)")

    meta_path = pathlib.Path("assets/generated/GEMINI_ASSET_METADATA.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"[done] metadata: {meta_path}")


if __name__ == "__main__":
    run()
