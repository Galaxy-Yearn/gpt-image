---
name: gpt-image
description: Generate or edit images with gpt-image-2 through a configurable OpenAI-compatible Images API. Convert Chinese requests into concise English prompts, while preserving requested in-image Chinese text verbatim.
---

# GPT Image

Use `scripts/gpt_image.py` with `gpt-image-2` only.

- `generate` -> `{BASE_URL}/images/generations`
- `edit` -> `{BASE_URL}/images/edits`
- `BASE_URL` is complete and user-provided; do not append or rewrite it.
- Read configuration from the skill-local `.env`; never ask the user to paste an API key in chat.

## Rules

- Convert the request into a compact English visual prompt.
- Keep Chinese only when it must appear inside the image, quoted exactly.
- Keep API controls in CLI flags or `.env`, not inside the prompt.
- Prefer `--prompt-file` for quotes, semicolons, newlines, or visible non-ASCII text.
- Use `generate` for new images.
- Use `edit` for "based on this image", "modify this poster", or partial replacement requests.
- Use `edit --mask` only for selected-area local edits.
- Do not send `input_fidelity`; `gpt-image-2` always processes image inputs at high fidelity.
- Read `references/prompting.md` only when the request is vague, style-sensitive, text-heavy, or an edit needs precise preserve/change wording.

## Output

- Unless the user specifies another path, create `gpt-image/` under the current workspace root.
- Save both the prompt `.txt` file and generated images there.
- Never save prompts or outputs in `.codex/`, `.codex/skills/`, or this skill directory.

## Config

Read defaults from the skill-local `.env`.

```text
BASE_URL=https://api.openai.com/v1
API_KEY=
MODEL=gpt-image-2
SIZE=auto
QUALITY=auto
OUTPUT_FORMAT=png
N=1
# BACKGROUND=auto
# OUTPUT_COMPRESSION=90
# MODERATION=auto
TIMEOUT_SECONDS=600
```

Precedence:

```text
CLI flag > .env key > environment variable alias > script default
```

## Parameters

- `model`: `gpt-image-2` only.
- `size`: `auto` or `WIDTHxHEIGHT`; each edge `<= 3840`, both edges multiples of `16`, long:short ratio `<= 3:1`, total pixels `655,360..8,294,400`.
- `quality`: `auto`, `low`, `medium`, `high`.
- `output_format`: `png`, `jpeg`, `webp`.
- `n`: `1..10`.
- `background`: `auto` or `opaque`. Never use `transparent`.
- `output_compression`: `0..100`. Use only with `jpeg` or `webp`.
- `moderation`: `auto` or `low`.
- `extra`: `key=value` pass-through only when you know the endpoint supports it.
- `image` for `edit`: repeat `--image <path>` up to `16` times; local `png`, `jpg`, `jpeg`, `webp`, each `<= 50MB`.
- `mask` for `edit`: PNG with alpha, `<= 4MB`, same dimensions as the first input image.
- `--out` default: `gpt-image/output.png`.
- `--out-dir`: writes `image_1.ext`, `image_2.ext`, and so on.

## Common Mappings

- square, icon, avatar -> `--size 1024x1024`
- wide, banner, landscape -> `--size 1536x1024`
- vertical, poster, phone wallpaper -> `--size 1024x1536`
- 2K square -> `--size 2048x2048`
- 2K wide -> `--size 2048x1152`
- 4K wide -> `--size 3840x2160`
- 4K vertical -> `--size 2160x3840`
- draft, quick -> `--quality low`
- balanced, standard -> `--quality medium`
- final, polished, detailed -> `--quality high`
- multiple variants -> `--n <count>`
- transparent background -> unsupported; use `auto` or `opaque`

## Run

```bash
uv run python scripts/gpt_image.py generate \
  --model gpt-image-2 \
  --prompt-file gpt-image/prompt.txt \
  --size 1536x1024 \
  --quality high \
  --background opaque \
  --output-format png \
  --n 1 \
  --out gpt-image/image.png
```

```bash
uv run python scripts/gpt_image.py edit \
  --model gpt-image-2 \
  --image <path/to/source.png> \
  --prompt-file gpt-image/prompt.txt \
  --size 1024x1536 \
  --quality high \
  --background opaque \
  --output-format png \
  --n 1 \
  --out gpt-image/image.png
```

Useful flags: `--force`, `--dry-run`, `--env <path>`, `--timeout <seconds>`, `--out-dir <dir>`.

Use `python` instead of `uv run python` when `uv` is unavailable.

Report the saved path, final prompt, and final parameters.
