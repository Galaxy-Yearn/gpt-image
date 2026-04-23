---
name: gpt-image
description: Generate raster images with gpt-image-2 through a configurable OpenAI-compatible Images API. Use for text-to-image generation, including Chinese requests that should become English prompts while preserving requested in-image Chinese text verbatim.
---

# GPT Image

Use `scripts/gpt_image.py` to generate images with `gpt-image-2` through `{BASE_URL}/images/generations`. `BASE_URL` is complete and user-provided; do not append or rewrite it.

## Rules

- Generate new raster images only with `gpt-image-2`. Do not use this skill for editing existing images or other image models.
- Read configuration from the skill-local `.env`; never ask the user to paste an API key in chat.
- Convert visual instructions to a concise English prompt.
- Keep Chinese only when it must appear inside the image, quoted exactly.
- Pass API controls as CLI flags, not inside the prompt.
- Prefer `--prompt-file` for prompts with quotes, semicolons, newlines, or non-ASCII visible text.
- Read `references/prompting.md` only for complex, vague, or text-heavy image requests.

## Configuration

`.env` supports:

```text
BASE_URL=https://your-openai-compatible-base-url/v1
API_KEY=
MODEL=gpt-image-2
SIZE=auto
QUALITY=auto
OUTPUT_FORMAT=png
N=1
```

Optional keys: `BACKGROUND`, `OUTPUT_COMPRESSION`, `MODERATION`, `TIMEOUT_SECONDS`.

Precedence:

```text
CLI flag > .env key > environment variable alias > script default
```

Aliases include `GPT_IMAGE_*` and selected `OPENAI_*` names.

## Parameters

Use only these values:

- `model`: `gpt-image-2` only. Default: `gpt-image-2`.
- `size`: `auto` or `WIDTHxHEIGHT`. Default: `auto`.
  Constraints: each edge `<= 3840`, both edges multiples of `16`, long:short ratio `<= 3:1`, total pixels `655,360..8,294,400`.
  Common choices: `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, `2160x3840`.
- `quality`: `auto`, `low`, `medium`, `high`. Default: `auto`.
- `output_format`: `png`, `jpeg`, `webp`. Default: `png`.
- `n`: integer `1..10`. Default: `1`.
- `background`: `auto` or `opaque`. Default: unset unless provided by `.env`. Never use `transparent`.
- `output_compression`: integer `0..100`. Use only with `output_format=jpeg` or `output_format=webp`.
- `moderation`: `auto` or `low`. Default: unset unless provided by `.env`.
- `extra`: `key=value` pass-through fields. Use only when you know the target endpoint accepts them for `gpt-image-2`.

Execution rule:

- Keep these as CLI parameters or `.env` values.
- Do not encode them inside the prompt text.

Natural-language mapping:

- Square, avatar, icon -> `--size 1024x1024`.
- Wide, landscape, banner -> `--size 1536x1024`.
- Vertical, portrait, poster, phone wallpaper -> `--size 1024x1536`.
- Quick, draft, cheap -> `--quality low`.
- Final, high quality, detailed -> `--quality high`.
- Multiple variants -> `--n <count>`.

## Run

Use `uv` when available:

```bash
uv run python scripts/gpt_image.py generate --prompt-file tmp/gpt-image/prompt.txt --out output/gpt-image/image.png
```

Use local Python when `uv` is unavailable:

```bash
python scripts/gpt_image.py generate --prompt-file tmp/gpt-image/prompt.txt --out output/gpt-image/image.png
```

For every result, report the saved path, final prompt, and final parameters.
