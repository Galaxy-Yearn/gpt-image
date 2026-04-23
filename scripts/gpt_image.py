#!/usr/bin/env python3
"""Generate or edit images with gpt-image-2 through an OpenAI-compatible Images API.

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
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid


DEFAULT_BASE_URL: str | None = None
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "auto"
DEFAULT_QUALITY = "auto"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_OUTPUT_PATH = "output/gpt-image/output.png"
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_N = 1
SUPPORTED_MODEL = "gpt-image-2"
SUPPORTED_QUALITIES = {"auto", "low", "medium", "high"}
SUPPORTED_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
SUPPORTED_BACKGROUNDS = {None, "auto", "opaque", "transparent"}
SUPPORTED_MODERATIONS = {None, "auto", "low"}
SUPPORTED_SIZES = {"auto", "1024x1024", "1536x1024", "1024x1536"}
MAX_INPUT_IMAGES = 16
MAX_INPUT_IMAGE_BYTES = 50 * 1024 * 1024
MAX_MASK_BYTES = 4 * 1024 * 1024


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_env_path() -> Path:
    return skill_dir() / ".env"


def safe_print_json(value: dict[str, Any]) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


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
    if fmt not in SUPPORTED_OUTPUT_FORMATS:
        die("--output-format must be png, jpeg, jpg, or webp")
    return fmt


def normalize_optional_choice(value: str | None, name: str, choices: set[str | None]) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).lower().strip()
    if normalized not in choices:
        valid = ", ".join(sorted(v for v in choices if v is not None))
        die(f"{name} must be one of: {valid}")
    return normalized


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


def validate_size(value: str | None) -> None:
    if not value:
        die("--size is required after defaults are applied")
    if value not in SUPPORTED_SIZES:
        valid = ", ".join(sorted(SUPPORTED_SIZES))
        die(f"--size must be one of: {valid}")


def read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        die("Use --prompt or --prompt-file, not both")
    if prompt_file:
        path = Path(prompt_file)
        if not path.exists():
            die(f"Prompt file not found: {path}")
        text = path.read_text(encoding="utf-8-sig").strip()
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


def ensure_writable(paths: list[Path], force: bool) -> None:
    for path in paths:
        if path.exists() and not force:
            die(f"Output already exists: {path} (use --force to overwrite)")
        path.parent.mkdir(parents=True, exist_ok=True)


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


def read_binary_file(path_str: str, what: str) -> tuple[Path, bytes]:
    path = Path(path_str)
    if not path.exists():
        die(f"{what} not found: {path}")
    if not path.is_file():
        die(f"{what} is not a file: {path}")
    return path, path.read_bytes()


def guess_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    die(f"Unsupported image file extension for {path.name}; use .png, .jpg, .jpeg, or .webp")


def parse_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        die("Mask must be a valid PNG file")
    if data[12:16] != b"IHDR":
        die("PNG mask is missing an IHDR chunk")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def png_has_alpha(data: bytes) -> bool:
    if len(data) < 26 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    color_type = data[25]
    return color_type in {4, 6}


def parse_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        die("Input JPEG is not valid")
    pos = 2
    while pos + 1 < len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            break
        segment_length = int.from_bytes(data[pos : pos + 2], "big")
        if segment_length < 2 or pos + segment_length > len(data):
            break
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3,
            0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB,
            0xCD, 0xCE, 0xCF,
        }:
            if pos + 7 > len(data):
                break
            height = int.from_bytes(data[pos + 3 : pos + 5], "big")
            width = int.from_bytes(data[pos + 5 : pos + 7], "big")
            return width, height
        pos += segment_length
    die("Could not read JPEG dimensions")


def parse_webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        die("Input WebP is not valid")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            die("Could not read WebP VP8 dimensions")
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        if data[20] != 0x2F:
            die("Could not read WebP VP8L dimensions")
        bits = int.from_bytes(data[21:25], "little")
        width = 1 + (bits & 0x3FFF)
        height = 1 + ((bits >> 14) & 0x3FFF)
        return width, height
    die("Unsupported WebP chunk type")


def image_dimensions(path: Path, data: bytes) -> tuple[int, int]:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return parse_png_dimensions(data)
    if suffix in {".jpg", ".jpeg"}:
        return parse_jpeg_dimensions(data)
    if suffix == ".webp":
        return parse_webp_dimensions(data)
    die(f"Unsupported image file extension for {path.name}; use .png, .jpg, .jpeg, or .webp")


def validate_input_images(image_paths: list[str]) -> list[tuple[Path, bytes]]:
    if not image_paths:
        die("Edit requires at least one --image input")
    if len(image_paths) > MAX_INPUT_IMAGES:
        die(f"Edit supports at most {MAX_INPUT_IMAGES} input images")

    files: list[tuple[Path, bytes]] = []
    for idx, image_path in enumerate(image_paths, start=1):
        path, data = read_binary_file(image_path, f"input image {idx}")
        guess_mime_type(path)
        if len(data) > MAX_INPUT_IMAGE_BYTES:
            die(f"Input image {idx} exceeds 50MB: {path}")
        files.append((path, data))
    return files


def validate_mask(mask_path: str | None, image_files: list[tuple[Path, bytes]]) -> tuple[Path, bytes] | None:
    if not mask_path:
        return None

    path, data = read_binary_file(mask_path, "mask")
    if path.suffix.lower() != ".png":
        die("Mask must be a PNG file")
    if len(data) > MAX_MASK_BYTES:
        die("Mask exceeds 4MB")
    if not png_has_alpha(data):
        die("Mask PNG must contain an alpha channel")

    mask_size = parse_png_dimensions(data)
    first_image_size = image_dimensions(image_files[0][0], image_files[0][1])
    if mask_size != first_image_size:
        die(
            "Mask dimensions must match the first input image: "
            f"mask={mask_size[0]}x{mask_size[1]}, image={first_image_size[0]}x{first_image_size[1]}"
        )
    return path, data


def validate_payload(payload: dict[str, Any]) -> None:
    model = str(payload.get("model", ""))
    if model != SUPPORTED_MODEL:
        die(f"This skill only supports model {SUPPORTED_MODEL}")
    size = payload.get("size")
    validate_size(str(size) if size is not None else None)
    quality = payload.get("quality")
    if quality not in SUPPORTED_QUALITIES:
        valid = ", ".join(sorted(SUPPORTED_QUALITIES))
        die(f"--quality must be one of: {valid}")
    background = payload.get("background")
    if background not in SUPPORTED_BACKGROUNDS:
        die("--background must be one of: auto, opaque, transparent")
    moderation = payload.get("moderation")
    if moderation not in SUPPORTED_MODERATIONS:
        die("--moderation must be auto or low")
    output_format = payload.get("output_format")
    output_compression = payload.get("output_compression")
    if output_compression is not None and output_format not in {"jpeg", "webp"}:
        die("--output-compression is only supported with --output-format jpeg or webp")
    if background == "transparent" and output_format not in {"png", "webp"}:
        die("--background transparent requires --output-format png or webp")


def parse_response_bytes(raw: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        die(f"Image API returned non-JSON response: {raw[:500]!r}")


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
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"HTTP {exc.code} from image API: {detail}")
    except URLError as exc:
        die(f"Could not reach image API: {exc}")

    return parse_response_bytes(raw)


def build_multipart_body(
    fields: dict[str, Any],
    file_fields: list[tuple[str, Path, bytes]],
) -> tuple[bytes, str]:
    boundary = f"----gpt-image-{uuid.uuid4().hex}"
    body = bytearray()

    def append_line(text: str) -> None:
        body.extend(text.encode("utf-8"))
        body.extend(b"\r\n")

    for name, value in fields.items():
        append_line(f"--{boundary}")
        append_line(f'Content-Disposition: form-data; name="{name}"')
        append_line("")
        append_line(str(value))

    for name, path, data in file_fields:
        append_line(f"--{boundary}")
        append_line(f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"')
        append_line(f"Content-Type: {guess_mime_type(path)}")
        append_line("")
        body.extend(data)
        body.extend(b"\r\n")

    append_line(f"--{boundary}--")
    return bytes(body), boundary


def post_multipart(
    url: str,
    api_key: str,
    fields: dict[str, Any],
    file_fields: list[tuple[str, Path, bytes]],
    timeout: int,
) -> dict[str, Any]:
    body, boundary = build_multipart_body(fields, file_fields)
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"HTTP {exc.code} from image API: {detail}")
    except URLError as exc:
        die(f"Could not reach image API: {exc}")

    return parse_response_bytes(raw)


def resolve_common_config(args: argparse.Namespace, file_values: dict[str, str]) -> tuple[str, str, int]:
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
    if not api_key and not args.dry_run:
        die(f"API key is missing. Set API_KEY in {args.env or default_env_path()} or pass --api-key")

    timeout_raw = first_value(
        str(args.timeout) if args.timeout is not None else None,
        file_values,
        ("TIMEOUT_SECONDS", "GPT_IMAGE_TIMEOUT_SECONDS", "OPENAI_IMAGE_TIMEOUT_SECONDS"),
        str(DEFAULT_TIMEOUT_SECONDS),
    )
    try:
        timeout = int(timeout_raw or DEFAULT_TIMEOUT_SECONDS)
    except ValueError:
        die("TIMEOUT_SECONDS must be an integer")
    return base_url, api_key or "", timeout


def build_generation_payload(args: argparse.Namespace, file_values: dict[str, str]) -> tuple[str, str, dict[str, Any], int]:
    base_url, api_key, timeout = resolve_common_config(args, file_values)
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
    background = normalize_optional_choice(
        first_value(
            args.background,
            file_values,
            ("BACKGROUND", "GPT_IMAGE_BACKGROUND", "OPENAI_IMAGE_BACKGROUND"),
        ),
        "BACKGROUND",
        SUPPORTED_BACKGROUNDS,
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
    moderation = normalize_optional_choice(
        first_value(
            args.moderation,
            file_values,
            ("MODERATION", "GPT_IMAGE_MODERATION", "OPENAI_IMAGE_MODERATION"),
        ),
        "MODERATION",
        SUPPORTED_MODERATIONS,
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
    return base_url, api_key, payload, timeout


def build_edit_request(
    args: argparse.Namespace,
    file_values: dict[str, str],
) -> tuple[str, str, dict[str, Any], list[tuple[str, Path, bytes]], int]:
    base_url, api_key, timeout = resolve_common_config(args, file_values)
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
    background = normalize_optional_choice(
        first_value(
            args.background,
            file_values,
            ("BACKGROUND", "GPT_IMAGE_BACKGROUND", "OPENAI_IMAGE_BACKGROUND"),
        ),
        "BACKGROUND",
        SUPPORTED_BACKGROUNDS,
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
    moderation = normalize_optional_choice(
        first_value(
            args.moderation,
            file_values,
            ("MODERATION", "GPT_IMAGE_MODERATION", "OPENAI_IMAGE_MODERATION"),
        ),
        "MODERATION",
        SUPPORTED_MODERATIONS,
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
    prompt = read_prompt(args.prompt, args.prompt_file)

    fields: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    if background not in (None, ""):
        fields["background"] = background
    if output_compression is not None:
        fields["output_compression"] = output_compression
    if moderation not in (None, ""):
        fields["moderation"] = moderation

    fields.update(parse_extra(args.extra or []))
    validate_payload(fields)

    image_files = validate_input_images(args.image or [])
    mask_file = validate_mask(args.mask, image_files)

    file_fields: list[tuple[str, Path, bytes]] = [
        ("image[]", path, data)
        for path, data in image_files
    ]
    if mask_file is not None:
        file_fields.append(("mask", mask_file[0], mask_file[1]))

    # Official docs: omit input_fidelity for gpt-image-2.
    if "input_fidelity" in fields:
        die("Do not send input_fidelity with gpt-image-2")

    return base_url, api_key, fields, file_fields, timeout


def command_generate(args: argparse.Namespace) -> None:
    file_values = parse_dotenv(Path(args.env) if args.env else default_env_path())
    base_url, api_key, payload, timeout = build_generation_payload(args, file_values)
    output_format = normalize_output_format(str(payload.get("output_format", DEFAULT_OUTPUT_FORMAT)))
    outputs = build_output_paths(args.out, args.out_dir, output_format, int(payload.get("n", DEFAULT_N)))
    endpoint = f"{base_url}/images/generations"

    if args.dry_run:
        safe_print_json(
            {
                "endpoint": endpoint,
                "outputs": [str(path) for path in outputs],
                "payload": payload,
            }
        )
        return

    print(f"Calling {endpoint} with model {payload.get('model')}. This may take a few minutes.", file=sys.stderr)
    started = time.time()
    response = post_json(endpoint, api_key, payload, timeout)
    elapsed = time.time() - started
    print(f"Image generation completed in {elapsed:.1f}s.", file=sys.stderr)
    write_images(response, outputs, args.force, timeout)


def command_edit(args: argparse.Namespace) -> None:
    file_values = parse_dotenv(Path(args.env) if args.env else default_env_path())
    base_url, api_key, fields, file_fields, timeout = build_edit_request(args, file_values)
    output_format = normalize_output_format(str(fields.get("output_format", DEFAULT_OUTPUT_FORMAT)))
    outputs = build_output_paths(args.out, args.out_dir, output_format, int(fields.get("n", DEFAULT_N)))
    endpoint = f"{base_url}/images/edits"

    if args.dry_run:
        safe_print_json(
            {
                "endpoint": endpoint,
                "outputs": [str(path) for path in outputs],
                "fields": fields,
                "files": [
                    {
                        "field": name,
                        "path": str(path),
                        "bytes": len(data),
                    }
                    for name, path, data in file_fields
                ],
            }
        )
        return

    print(f"Calling {endpoint} with model {fields.get('model')}. This may take a few minutes.", file=sys.stderr)
    started = time.time()
    response = post_multipart(endpoint, api_key, fields, file_fields, timeout)
    elapsed = time.time() - started
    print(f"Image edit completed in {elapsed:.1f}s.", file=sys.stderr)
    write_images(response, outputs, args.force, timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or edit images with gpt-image-2 through an OpenAI-compatible Images API")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate new image(s) from a text prompt")
    generate.add_argument("--prompt", help="Final English image prompt")
    generate.add_argument("--prompt-file", help="UTF-8 text file containing the final English image prompt")
    generate.add_argument("--out", default=DEFAULT_OUTPUT_PATH, help="Output file path")
    generate.add_argument("--out-dir", help="Output directory; writes image_1.ext, image_2.ext, ...")
    generate.add_argument("--n", type=int, help="Number of images to request")
    generate.add_argument("--size", help="auto, 1024x1024, 1536x1024, or 1024x1536")
    generate.add_argument("--quality", help="auto, low, medium, or high")
    generate.add_argument("--background", help="auto, opaque, or transparent")
    generate.add_argument("--output-format", help="png, jpeg, or webp")
    generate.add_argument("--output-compression", type=int, help="0-100 for jpeg/webp when supported")
    generate.add_argument("--moderation", help="auto or low")
    generate.add_argument("--extra", action="append", default=[], help="Provider-specific key=value JSON/string field")
    generate.add_argument("--base-url", help="OpenAI-compatible base URL, including the API path such as /v1")
    generate.add_argument("--api-key", help="API key. Prefer .env instead of passing this in shell history")
    generate.add_argument("--model", help="Must be gpt-image-2")
    generate.add_argument("--env", help="Path to .env file; defaults to the skill-local .env")
    generate.add_argument("--timeout", type=int, help="HTTP timeout in seconds")
    generate.add_argument("--force", action="store_true", help="Overwrite existing output files")
    generate.add_argument("--dry-run", action="store_true", help="Print payload and paths without calling the API")
    generate.set_defaults(func=command_generate)

    edit = subparsers.add_parser("edit", help="Edit image(s) with gpt-image-2")
    edit.add_argument("--image", action="append", required=True, help="Input image path. Repeat up to 16 times")
    edit.add_argument("--mask", help="Optional PNG mask path with alpha, same size as the first input image")
    edit.add_argument("--prompt", help="Final English edit prompt")
    edit.add_argument("--prompt-file", help="UTF-8 text file containing the final English edit prompt")
    edit.add_argument("--out", default=DEFAULT_OUTPUT_PATH, help="Output file path")
    edit.add_argument("--out-dir", help="Output directory; writes image_1.ext, image_2.ext, ...")
    edit.add_argument("--n", type=int, help="Number of images to request")
    edit.add_argument("--size", help="auto, 1024x1024, 1536x1024, or 1024x1536")
    edit.add_argument("--quality", help="auto, low, medium, or high")
    edit.add_argument("--background", help="auto, opaque, or transparent")
    edit.add_argument("--output-format", help="png, jpeg, or webp")
    edit.add_argument("--output-compression", type=int, help="0-100 for jpeg/webp when supported")
    edit.add_argument("--moderation", help="auto or low")
    edit.add_argument("--extra", action="append", default=[], help="Provider-specific key=value JSON/string field")
    edit.add_argument("--base-url", help="OpenAI-compatible base URL, including the API path such as /v1")
    edit.add_argument("--api-key", help="API key. Prefer .env instead of passing this in shell history")
    edit.add_argument("--model", help="Must be gpt-image-2")
    edit.add_argument("--env", help="Path to .env file; defaults to the skill-local .env")
    edit.add_argument("--timeout", type=int, help="HTTP timeout in seconds")
    edit.add_argument("--force", action="store_true", help="Overwrite existing output files")
    edit.add_argument("--dry-run", action="store_true", help="Print fields and files without calling the API")
    edit.set_defaults(func=command_edit)
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
