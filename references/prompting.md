# Prompting

Use this reference only when prompt shaping matters.

## Contract

Return a compact English prompt and separate generation parameters:

```text
Prompt: <English visual prompt>
Parameters: size=<...>, quality=<...>, output_format=<...>, n=<...>
```

Never hide API controls inside the prompt. Pass `size`, `quality`, `output_format`, `n`, `background`, `moderation`, and compression as CLI flags.

## Strong Prompt Pattern

Keep it short, concrete, and visual:

```text
<subject and medium>. <composition and setting>. <lighting and color>. <key materials/details>. <constraints>.
```

Good prompt traits:

- Lead with the subject and output medium.
- Use visible details only.
- Prefer one clear style direction over a list of styles.
- Add composition only if it changes the result.
- End with constraints: `no watermark, no signature, no extra text`.
- If visible text is required, quote it exactly and request no additional text.

Avoid:

- Long mood-board lists.
- Abstract adjectives without visible details.
- Extra props, characters, brands, slogans, or story beats not requested.
- Repeating size, quality, format, or model inside the prompt.

## Chinese Input

Translate visual instructions into English.

Keep Chinese only for visible in-image text:

```text
Text: "春日上新"
Constraint: render exactly this Chinese text and no additional text.
```

If Chinese text accuracy matters, make the rest of the image simpler.

## Parameter Mapping

- Square, avatar, icon, 1:1 -> `--size 1024x1024`.
- Wide, landscape, banner, hero -> `--size 1536x1024`.
- Vertical, portrait, poster, phone wallpaper -> `--size 1024x1536`.
- Draft, quick, cheap -> `--quality low`.
- Balanced, standard -> `--quality medium`.
- High quality, polished, final, detailed -> `--quality high`.
- Requested PNG/JPEG/WebP -> `--output-format png|jpeg|webp`.
- Multiple variants/options -> `--n <count>`, max 10.
- Transparent background -> do not use with default `gpt-image-2`; ask for a compatible model/provider first.

## Examples

Chinese request:

```text
生成一张高清竖版春节海报，红金配色，上面写“新春快乐”
```

Use:

```text
Prompt: A polished vertical Lunar New Year poster illustration. Centered festive composition with elegant paper-cut motifs, lantern silhouettes, and balanced decorative framing. Rich red and metallic gold palette with warm celebratory lighting. Text: "新春快乐". Constraint: render exactly this Chinese text and no additional text; no watermark, no signature.
Parameters: size=1024x1536, quality=high, output_format=png, n=1
```

Chinese request:

```text
给我三个宽屏咖啡杯产品图，快速草稿
```

Use:

```text
Prompt: A clean studio product photograph of a ceramic coffee cup. Wide landscape composition with subtle negative space, warm neutral background, soft morning light, glazed ceramic texture, gentle reflections. Constraints: no logo, no text, no watermark, no signature.
Parameters: size=1536x1024, quality=low, output_format=png, n=3
```
