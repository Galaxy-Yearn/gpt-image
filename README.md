# GPT Image Skill

Use `gpt-image-2` from Codex through an OpenAI-compatible Images API.

It supports `gpt-image-2` only.

## What It Does

- Generate new images with `gpt-image-2`.
- Edit existing images with `gpt-image-2`.
- Convert Chinese user requests into concise English prompts.
- Preserve exact Chinese text when that text must appear inside the image.
- Accept a custom OpenAI-compatible `BASE_URL`.
- Support one or more local input images for edits.
- Support PNG masks with alpha for local masked edits.

## Requirements

- Codex with local skill support.
- Python 3.10 or newer.
- Optional but recommended: `uv`.
- An OpenAI-compatible image API key and base URL.

The script uses only the Python standard library.

## Install

```bash
git clone https://github.com/Galaxy-Yearn/gpt-image.git ~/.codex/skills/gpt-image
```

PowerShell:

```powershell
git clone https://github.com/Galaxy-Yearn/gpt-image.git "$env:USERPROFILE\.codex\skills\gpt-image"
```

If `CODEX_HOME` is set, install under:

```bash
$CODEX_HOME/skills/gpt-image
```

This path is only for the skill itself. Generated prompts and images should go in the user's workspace, not under `.codex/`.

## Configuration

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Required:

```text
BASE_URL=https://api.openai.com/v1
API_KEY=replace-me
MODEL=gpt-image-2
```

Optional defaults:

```text
SIZE=auto
QUALITY=auto
OUTPUT_FORMAT=png
N=1
# BACKGROUND=auto
# OUTPUT_COMPRESSION=90
# MODERATION=auto
TIMEOUT_SECONDS=600
```

`BASE_URL` must include the complete API path. The script does not append `/v1`.

Do not commit `.env`.

## How Codex Should Use This Skill

- Use `scripts/gpt_image.py` with `gpt-image-2` only.
- `generate` calls `{BASE_URL}/images/generations`.
- `edit` calls `{BASE_URL}/images/edits`.
- Keep API controls as CLI flags or `.env` values, not inside the prompt text.
- Prefer `--prompt-file` when the prompt contains quotes, semicolons, newlines, or visible non-ASCII text.
- Unless the user asks for another location, save both the prompt file and generated images in a single `gpt-image/` folder under the current workspace.
- Do not save generated prompts or images inside `.codex/`, `.codex/skills/`, or this skill repository unless the user explicitly asks.

## Quick Start

If `uv` is unavailable, replace `uv run python` with `python`.

Generate a new image:

```bash
uv run python scripts/gpt_image.py generate \
  --model gpt-image-2 \
  --prompt "A clean studio product photograph of a ceramic coffee cup, warm neutral background, soft morning light, no logo, no text, no watermark" \
  --size 1536x1024 \
  --quality high \
  --background opaque \
  --output-format png \
  --n 1 \
  --out gpt-image/coffee-cup.png
```

Edit an existing image:

```bash
uv run python scripts/gpt_image.py edit \
  --model gpt-image-2 \
  --image assets/examples/spring-tea-poster.png \
  --prompt-file gpt-image/summer-tea-edit.txt \
  --size 1024x1536 \
  --quality high \
  --background opaque \
  --output-format png \
  --n 1 \
  --out gpt-image/summer-tea-edit.png
```

Inspect the final request without calling the API:

```bash
uv run python scripts/gpt_image.py generate \
  --model gpt-image-2 \
  --prompt "A clean studio product photograph of a ceramic coffee cup" \
  --size 1536x1024 \
  --quality high \
  --background opaque \
  --output-format png \
  --n 1 \
  --dry-run
```

Common CLI flags:

- `--out`: write a single output file. Default: `gpt-image/output.png`.
- `--out-dir`: write `image_1.ext`, `image_2.ext`, and so on into a directory.
- `--force`: overwrite existing output files.
- `--dry-run`: print request payload and resolved output paths without making an API call.
- `--env`: load configuration from a specific `.env` file.

## gpt-image-2 Parameters

Supported generation and edit parameters:

| API field | CLI / config | Supported values |
| --- | --- | --- |
| `model` | `--model`, `MODEL` | `gpt-image-2` only |
| `prompt` | `--prompt`, `--prompt-file` | Text prompt |
| `size` | `--size`, `SIZE` | `auto` or `WIDTHxHEIGHT` satisfying the constraints below |
| `quality` | `--quality`, `QUALITY` | `auto`, `low`, `medium`, `high` |
| `output_format` | `--output-format`, `OUTPUT_FORMAT` | `png`, `jpeg`, `webp` |
| `n` | `--n`, `N` | Integer `1..10` |
| `background` | `--background`, `BACKGROUND` | `auto`, `opaque` |
| `output_compression` | `--output-compression`, `OUTPUT_COMPRESSION` | Integer `0..100`; only for `jpeg` and `webp` |
| `moderation` | `--moderation`, `MODERATION` | `auto`, `low` |

Edit-only inputs:

| API field | CLI | Supported values |
| --- | --- | --- |
| `image[]` | `--image` | Repeat `--image <path>` up to `16` times; local `png`, `jpg`, `jpeg`, `webp` files, each `<= 50MB` |
| `mask` | `--mask` | Optional PNG with alpha, `<= 4MB`, same dimensions as the first input image |

Rules enforced by the script:

- `gpt-image-2` only.
- `transparent` background is rejected.
- Do not send `input_fidelity`; `gpt-image-2` image inputs are always high fidelity.
- `output_compression` only with `jpeg` or `webp`.
- For `edit`, at least one `--image` is required.
- For `edit`, `--mask` must be PNG with alpha and match the first input image size.

Size constraints:

- `auto` is supported.
- Popular sizes include `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, and `2160x3840`.
- Custom `WIDTHxHEIGHT` is supported when both edges are multiples of `16px`.
- Maximum edge length is `3840px`.
- Long edge to short edge ratio must not exceed `3:1`.
- Total pixels must be between `655,360` and `8,294,400`.

Parameter precedence:

```text
CLI flag > .env key > environment variable alias > script default
```

## Example Outputs

Generated poster:

![Spring tea poster example](assets/examples/spring-tea-poster.png)

Edited poster:

![Summer tea edit example](assets/examples/summer-tea-edit.png)

## Project Files

- `SKILL.md`: instructions that Codex follows when this skill is triggered.
- `scripts/gpt_image.py`: local CLI for `generate` and `edit`.
- `references/prompting.md`: optional prompt guidance for complex or text-heavy requests.
- `agents/openai.yaml`: UI metadata for skill lists and chips.
- `.env.example`: safe configuration template.

## Official References

- [Image generation guide](https://platform.openai.com/docs/guides/image-generation)
- [Images create API](https://platform.openai.com/docs/api-reference/images/create)
- [Images edit API](https://platform.openai.com/docs/api-reference/images/create-edit)
- [`gpt-image-2` model page](https://platform.openai.com/docs/models/gpt-image-2)
