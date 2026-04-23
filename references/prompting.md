# Prompting

Use this reference only when prompt shaping matters.

## Contract

Return a compact English prompt and separate image parameters:

```text
Prompt: <English visual prompt>
Parameters: size=<...>, quality=<...>, output_format=<...>, n=<...>
```

Never hide API controls inside the prompt. Pass `size`, `quality`, `output_format`, `n`, `background`, `moderation`, and compression as CLI flags.

For edits, describe what to keep and what to change. Do not describe the upload itself.

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
- For edits, explicitly preserve layout, subject, or scene elements that must remain.
- For edits, state the exact visual changes instead of rewriting the whole scene from scratch.
- End with constraints: `no watermark, no signature, no extra text`.
- If visible text is required, quote it exactly and request no additional text.

Avoid:

- Long mood-board lists.
- Abstract adjectives without visible details.
- Extra props, characters, brands, slogans, or story beats not requested.
- Repeating size, quality, format, or model inside the prompt.
- Describing masks, file uploads, or command-line flags inside the prompt.

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
- 2K square -> `--size 2048x2048`.
- 2K wide -> `--size 2048x1152`.
- 4K wide -> `--size 3840x2160`.
- 4K vertical -> `--size 2160x3840`.
- Draft, quick, cheap -> `--quality low`.
- Balanced, standard -> `--quality medium`.
- High quality, polished, final, detailed -> `--quality high`.
- Requested PNG/JPEG/WebP -> `--output-format png|jpeg|webp`.
- Multiple variants/options -> `--n <count>`, max 10.
- Transparent background -> not supported by this skill with `gpt-image-2`.
- Based on this image / modify this poster / change part of the image -> use `edit`.
- Replace only a selected area -> use `edit` with `--mask`.

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

Chinese edit request:

```text
基于这张海报改成夏日冰茶版本，保留高级版式，把热茶改成冰茶，标题改成“夏日茶会”
```

Use:

```text
Prompt: Turn this existing premium tea poster into a summer iced tea version. Keep the elegant poster layout and centered product composition. Replace the hot tea with iced jasmine tea with visible ice cubes, brighter daylight, and a cleaner refreshing summer mood. Text: "夏日茶会". Constraint: render exactly this Chinese text and no additional text; no watermark, no signature.
Parameters: size=1024x1536, quality=high, output_format=png, n=1
```
