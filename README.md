# GPT Image Skill

Codex skill for generating raster images with GPT image models through an OpenAI-compatible Images API. It is designed for text-to-image workflows where Codex turns the user's request into a concise English image prompt, extracts generation parameters, and calls a configurable endpoint.

## Capabilities

- Generate new images with `gpt-image-2` by default.
- Use a custom OpenAI-compatible `BASE_URL`.
- Configure model, size, quality, output format, image count, moderation, background, compression, and timeout.
- Convert Chinese image requests into English prompts while preserving requested in-image Chinese text verbatim.
- Save generated images to local project paths.

This skill only supports image generation. It does not edit existing images.

## Requirements

- Codex with local skill support.
- Python 3.10 or newer.
- Optional but recommended: `uv`.
- An OpenAI-compatible image API key and base URL.

The Python script uses only the standard library; there are no package dependencies.

## Installation

Clone or copy this repository into your Codex skills directory:

```bash
git clone https://github.com/Galaxy-Yearn/gpt-image.git ~/.codex/skills/gpt-image
```

On Windows PowerShell:

```powershell
git clone https://github.com/Galaxy-Yearn/gpt-image.git "$env:USERPROFILE\.codex\skills\gpt-image"
```

If `CODEX_HOME` is set, install under:

```bash
$CODEX_HOME/skills/gpt-image
```

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Required:

```text
BASE_URL=https://your-openai-compatible-base-url/v1
API_KEY=your-api-key
MODEL=gpt-image-2
```

Optional defaults:

```text
SIZE=auto
QUALITY=auto
OUTPUT_FORMAT=png
N=1
BACKGROUND=auto
OUTPUT_COMPRESSION=90
MODERATION=auto
TIMEOUT_SECONDS=600
```

`BASE_URL` must include the complete API base path. The script does not append `/v1`.

Do not commit `.env`; it is ignored by `.gitignore`.

## Usage

With `uv`:

```bash
uv run python scripts/gpt_image.py generate \
  --prompt "A clean studio product photograph of a ceramic coffee cup, warm neutral background, soft morning light, no logo, no text, no watermark" \
  --size 1536x1024 \
  --quality high \
  --output-format png \
  --out output/gpt-image/coffee-cup.png
```

With local Python:

```bash
python scripts/gpt_image.py generate \
  --prompt "A clean studio product photograph of a ceramic coffee cup, warm neutral background, soft morning light, no logo, no text, no watermark" \
  --size 1536x1024 \
  --quality high \
  --output-format png \
  --out output/gpt-image/coffee-cup.png
```

For prompts containing quotes, semicolons, newlines, or visible non-ASCII text, prefer a prompt file:

```bash
mkdir -p tmp/gpt-image
printf '%s\n' 'A polished vertical Chinese tea poster. Warm spring light, jasmine tea, clean premium layout. Text: "春日茶会". Constraint: render exactly this Chinese text and no additional text; no watermark, no signature.' > tmp/gpt-image/prompt.txt

uv run python scripts/gpt_image.py generate \
  --prompt-file tmp/gpt-image/prompt.txt \
  --size 1024x1536 \
  --quality high \
  --output-format png \
  --out output/gpt-image/tea-poster.png
```

## Parameters

- `--model`: image model; defaults to `gpt-image-2`.
- `--size`: `auto`, `1024x1024`, `1536x1024`, `1024x1536`, or another provider-supported size.
- `--quality`: `auto`, `low`, `medium`, or `high`.
- `--output-format`: `png`, `jpeg`, or `webp`.
- `--n`: number of images, `1..10`.
- `--background`: `auto` or `opaque` for default `gpt-image-2`.
- `--output-compression`: `0..100` for compressed formats when supported.
- `--moderation`: provider-supported moderation value.
- `--extra key=value`: pass through provider-specific fields.
- `--dry-run`: print endpoint, output paths, and JSON payload without calling the API.

Parameter precedence:

```text
CLI flag > .env key > environment variable alias > script default
```

## Skill Files

- `SKILL.md`: concise instructions loaded by Codex when the skill is invoked.
- `scripts/gpt_image.py`: generation CLI.
- `references/prompting.md`: optional prompt-shaping guidance for complex requests.
- `agents/openai.yaml`: UI metadata.
- `.env.example`: safe configuration template.
