# Prompting

Use this only when prompt shaping matters.

Read this when:

- the request is vague and needs a stronger visual direction
- the request is text-heavy and in-image text accuracy matters
- the request is style-sensitive and wording will change the result
- an edit needs precise keep/change instructions

## Output Contract

Return:

```text
Prompt: <English visual prompt>
Parameters: size=<...>, quality=<...>, output_format=<...>, n=<...>
```

Keep API controls out of the prompt. Pass `size`, `quality`, `output_format`, `n`, `background`, `moderation`, and compression as CLI flags.

For edits, describe what to keep and what to change. Do not describe file uploads, masks, or commands inside the prompt.

## Prompt Pattern

Keep it short, visual, and concrete:

```text
<subject and medium>. <composition and setting>. <lighting and color>. <key materials/details>. <constraints>.
```

Use:

- Lead with the subject and output medium.
- Use visible details only.
- Prefer one clear style direction over a list of styles.
- Add composition only if it changes the result.
- For edits, explicitly preserve layout, subject, or scene elements that must remain.
- For edits, state the exact visual changes instead of rewriting the whole scene from scratch.
- End with constraints such as `no watermark, no signature, no extra text`.
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

## Better Prompt Shapes

Weak:

```text
A beautiful premium poster for a tea brand, very artistic and cinematic.
```

Better:

```text
Prompt: A premium vertical tea campaign poster. Centered product composition with a clear glass cup of jasmine tea on a warm wooden table, soft spring sunlight, fresh green tea leaves, and a clean editorial layout. Text: "春日茶会". Constraint: render exactly this Chinese text and no additional text; no watermark, no signature.
Parameters: size=1024x1536, quality=high, output_format=png, n=1
```

Weak edit:

```text
Change this poster into a summer version.
```

Better edit:

```text
Prompt: Turn this existing premium tea poster into a summer iced tea version. Keep the elegant poster layout and centered product composition. Replace the hot tea with iced jasmine tea with visible ice cubes, brighter daylight, cooler green-cyan tones, and a cleaner refreshing summer mood. Text: "夏日茶会". Constraint: render exactly this Chinese text and no additional text; no watermark, no signature.
Parameters: size=1024x1536, quality=high, output_format=png, n=1
```
