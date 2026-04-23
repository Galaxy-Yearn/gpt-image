#!/usr/bin/env python3
"""Generate images through an OpenAI-compatible Images API.

Configuration is read from the skill-local .env file by default.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL: str | None = None
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "auto"
DEFAULT_QUALITY = "auto"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_OUTPUT_PATH = "output/gpt-image/output.png"
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_N = 1


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_env_path() -> Path:
    return skill_dir() / ".env"


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            warn(f"Ignoring malformed .env line {line_no}: {raw}")
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            warn(f"Ignoring .env line {line_no} with empty key")
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def first_value(
    cli_value: str | None,
    file_values: dict[str, str],
    names: tuple[str, ...],
    default: str | None = None,
) -> str | None:
    if cli_value not in (None, ""):
        return cli_value
    for name in names:
        value = file_values.get(name)
        if value not in (None, ""):
            return value
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default


def normalize_output_format(value: str | None) -> str:
    fmt = (value or DEFAULT_OUTPUT_FORMAT).lower().strip()
    if fmt == "jpg":
        return "jpeg"
    if fmt not in {"png", "jpeg", "webp"}:
        die("--output-format must be png, jpeg, jpg, or webp")
    return fmt


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        die("BASE_URL is empty")
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        die("BASE_URL must include scheme and host, for example https://api.example.com/v1")
    return value


def parse_int_value(value: str | int | None, name: str, *, minimum: int | None = None, maximum: int | None = None) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        die(f"{name} must be an integer")
    if minimum is not None and parsed < minimum:
        die(f"{name} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        die(f"{name} must be <= {maximum}")
    return parsed


def read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        die("Use --prompt or --prompt-file, not both")
    if prompt_file:
        path = Path(prompt_file)
        if not path.exists():
            die(f"Prompt file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
    elif prompt:
        text = prompt.strip()
    else:
        die("Missing prompt. Use --prompt or --prompt-file")
    if not text:
        die("Prompt is empty")
    return text


def parse_extra(values: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            die(f"--extra must be key=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            die(f"--extra has an empty key: {item}")
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError:
            parsed[key] = value
    return parsed


def build_output_paths(out: str, out_dir: str | None, fmt: str, count: int) -> list[Path]:
    ext = ".jpg" if fmt == "jpeg" else f".{fmt}"

    if out_dir:
        base = Path(out_dir)
        base.mkdir(parents=True, exist_ok=True)
        return [base / f"image_{idx}{ext}" for idx in range(1, count + 1)]

    path = Path(out)
    if path.suffix == "":
        path = path.with_suffix(ext)

    if count == 1:
        return [path]

    return [
        path.with_name(f"{path.stem}-{idx}{path.suffix}")
        for idx in range(1, count + 1)
    ]


def validate_payload(payload: dict[str, Any]) -> None:
    model = str(payload.get("model", ""))
    background = payload.get("background")
    if model == "gpt-image-2" and background == "transparent":
        die("gpt-image-2 does not support --background transparent; use auto/opaque or another model")


def ensure_writable(paths: list[Path], force: bool) -> None:
    for path in paths:
        if path.exists() and not force:
            die(f"Output already exists: {path} (use --force to overwrite)")
        path.parent.mkdir(parents=True, exist_ok=True)


def post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"HTTP {exc.code} from image API: {detail}")
    except URLError as exc:
        die(f"Could not reach image API: {exc}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        die(f"Image API returned non-JSON response: {raw[:500]}")


def fetch_url(url: str, timeout: int) -> bytes:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read()
    except URLError as exc:
        die(f"Could not download image URL: {exc}")


def decode_image_item(item: dict[str, Any], timeout: int) -> bytes:
    b64_value = item.get("b64_json") or item.get("image_base64") or item.get("base64")
    if b64_value:
        if isinstance(b64_value, str) and b64_value.startswith("data:"):
            b64_value = b64_value.split(",", 1)[-1]
        try:
            return base64.b64decode(str(b64_value))
        except Exception as exc:
            die(f"Could not decode base64 image: {exc}")

    url = item.get("url")
    if url:
        return fetch_url(str(url), timeout=timeout)

    die(f"Image item has neither b64_json nor url: {json.dumps(item)[:500]}")


def write_images(response: dict[str, Any], outputs: list[Path], force: bool, timeout: int) -> None:
    data = response.get("data")
    if not isinstance(data, list) or not data:
        die(f"Image API response did not contain data[]: {json.dumps(response)[:500]}")

    if len(data) > len(outputs):
        warn(f"Response returned {len(data)} images, but only {len(outputs)} output paths were prepared")

    ensure_writable(outputs, force)
    for idx, item in enumerate(data[: len(outputs)]):
        if not isinstance(item, dict):
            die(f"Unexpected image item at index {idx}: {item}")
        image_bytes = decode_image_item(item, timeout=timeout)
        outputs[idx].write_bytes(image_bytes)
        print(f"Wrote {outputs[idx]}")


def build_payload(args: argparse.Namespace, file_values: dict[str, str]) -> tuple[str, str, dict[str, Any], int]:
    base_url_raw = first_value(
        args.base_url,
        file_values,
        ("BASE_URL", "GPT_IMAGE_BASE_URL", "OPENAI_BASE_URL"),
        DEFAULT_BASE_URL,
    )
    if not base_url_raw:
        die(f"BASE_URL is missing. Set BASE_URL in {args.env or default_env_path()} or pass --base-url")
    base_url = normalize_base_url(base_url_raw)
    api_key = first_value(
        args.api_key,
        file_values,
        ("API_KEY", "GPT_IMAGE_API_KEY", "OPENAI_API_KEY"),
    )
    model = first_value(
        args.model,
        file_values,
        ("MODEL", "GPT_IMAGE_MODEL", "OPENAI_IMAGE_MODEL"),
        DEFAULT_MODEL,
    )
    size = first_value(
        args.size,
        file_values,
        ("SIZE", "GPT_IMAGE_SIZE", "OPENAI_IMAGE_SIZE"),
        DEFAULT_SIZE,
    )
    quality = first_value(
        args.quality,
        file_values,
        ("QUALITY", "GPT_IMAGE_QUALITY", "OPENAI_IMAGE_QUALITY"),
        DEFAULT_QUALITY,
    )
    output_format = normalize_output_format(
        first_value(
            args.output_format,
            file_values,
            ("OUTPUT_FORMAT", "GPT_IMAGE_OUTPUT_FORMAT", "OPENAI_IMAGE_OUTPUT_FORMAT"),
            DEFAULT_OUTPUT_FORMAT,
        )
    )
    background = first_value(
        args.background,
        file_values,
        ("BACKGROUND", "GPT_IMAGE_BACKGROUND", "OPENAI_IMAGE_BACKGROUND"),
    )
    output_compression = parse_int_value(
        first_value(
            str(args.output_compression) if args.output_compression is not None else None,
            file_values,
            ("OUTPUT_COMPRESSION", "GPT_IMAGE_OUTPUT_COMPRESSION", "OPENAI_IMAGE_OUTPUT_COMPRESSION"),
        ),
        "OUTPUT_COMPRESSION",
        minimum=0,
        maximum=100,
    )
    moderation = first_value(
        args.moderation,
        file_values,
        ("MODERATION", "GPT_IMAGE_MODERATION", "OPENAI_IMAGE_MODERATION"),
    )
    n = parse_int_value(
        first_value(
            str(args.n) if args.n is not None else None,
            file_values,
            ("N", "GPT_IMAGE_N", "OPENAI_IMAGE_N"),
            str(DEFAULT_N),
        ),
        "N",
        minimum=1,
        maximum=10,
    )
    timeout_raw = first_value(
        str(args.timeout) if args.timeout is not None else None,
        file_values,
        ("TIMEOUT_SECONDS", "GPT_IMAGE_TIMEOUT_SECONDS", "OPENAI_IMAGE_TIMEOUT_SECONDS"),
        str(DEFAULT_TIMEOUT_SECONDS),
    )

    if not api_key and not args.dry_run:
        die(f"API key is missing. Set API_KEY in {args.env or default_env_path()} or pass --api-key")

    try:
        timeout = int(timeout_raw or DEFAULT_TIMEOUT_SECONDS)
    except ValueError:
        die("TIMEOUT_SECONDS must be an integer")

    prompt = read_prompt(args.prompt, args.prompt_file)
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
    }

    optional_values = {
        "size": size,
        "quality": quality,
        "background": background,
        "output_format": output_format,
        "output_compression": output_compression,
        "moderation": moderation,
    }
    for key, value in optional_values.items():
        if value not in (None, ""):
            payload[key] = value

    payload.update(parse_extra(args.extra or []))
    validate_payload(payload)
    return base_url, api_key or "", payload, timeout


def command_generate(args: argparse.Namespace) -> None:
    file_values = parse_dotenv(Path(args.env) if args.env else default_env_path())
    base_url, api_key, payload, timeout = build_payload(args, file_values)
    output_format = normalize_output_format(str(payload.get("output_format", DEFAULT_OUTPUT_FORMAT)))
    outputs = build_output_paths(args.out, args.out_dir, output_format, int(payload.get("n", DEFAULT_N)))
    endpoint = f"{base_url}/images/generations"

    if args.dry_run:
        print(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "outputs": [str(path) for path in outputs],
                    "payload": payload,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(f"Calling {endpoint} with model {payload.get('model')}. This may take a few minutes.", file=sys.stderr)
    started = time.time()
    response = post_json(endpoint, api_key, payload, timeout)
    elapsed = time.time() - started
    print(f"Image generation completed in {elapsed:.1f}s.", file=sys.stderr)
    write_images(response, outputs, args.force, timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate images with an OpenAI-compatible Images API")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate new image(s) from a text prompt")
    generate.add_argument("--prompt", help="Final English image prompt")
    generate.add_argument("--prompt-file", help="UTF-8 text file containing the final English image prompt")
    generate.add_argument("--out", default=DEFAULT_OUTPUT_PATH, help="Output file path")
    generate.add_argument("--out-dir", help="Output directory; writes image_1.ext, image_2.ext, ...")
    generate.add_argument("--n", type=int, help="Number of images to request")
    generate.add_argument("--size", help="Image size, e.g. auto, 1024x1024, 1536x1024, 1024x1536")
    generate.add_argument("--quality", help="Quality value supported by the endpoint")
    generate.add_argument("--background", help="opaque, auto, or a provider-supported value")
    generate.add_argument("--output-format", help="png, jpeg, or webp")
    generate.add_argument("--output-compression", type=int, help="0-100 for jpeg/webp when supported")
    generate.add_argument("--moderation", help="Moderation value supported by the endpoint")
    generate.add_argument("--extra", action="append", default=[], help="Provider-specific key=value JSON/string field")
    generate.add_argument("--base-url", help="OpenAI-compatible base URL, including the API path such as /v1")
    generate.add_argument("--api-key", help="API key. Prefer .env instead of passing this in shell history")
    generate.add_argument("--model", help="Model override; defaults to gpt-image-2")
    generate.add_argument("--env", help="Path to .env file; defaults to the skill-local .env")
    generate.add_argument("--timeout", type=int, help="HTTP timeout in seconds")
    generate.add_argument("--force", action="store_true", help="Overwrite existing output files")
    generate.add_argument("--dry-run", action="store_true", help="Print payload and paths without calling the API")
    generate.set_defaults(func=command_generate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.n is not None and (args.n < 1 or args.n > 10):
        die("--n must be between 1 and 10")
    if args.output_compression is not None and not (0 <= args.output_compression <= 100):
        die("--output-compression must be between 0 and 100")

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
