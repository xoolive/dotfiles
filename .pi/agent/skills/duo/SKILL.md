---
name: duo
description: Process a Duolingo (or similar) language learning video into a study memo. Use when the user provides a video file and wants a clean transcript with pinyin/furigana for hard words, vocabulary table, grammar notes, and an extracted audio file. Trigger on requests like "make a study memo from this video", "transcribe and explain", or "/duo".
---

# Duo — Language learning video to study memo

Given a video file and a target language, produce:
1. An extracted audio file (same name as video, audio extension)
2. A markdown study memo (same name as video, `.md`)

## Workflow

### 1. Find the video

If the user provides a filename (possibly incomplete), search the current directory for a match:
```bash
find . -iname "*partial_name*" | head -5
```

### 2. Extract audio

Strip the video stream with ffmpeg, no re-encoding:
```bash
ffmpeg -i "input.MP4" -vn -acodec copy "output.m4a"
```
Use `.m4a` for MP4/MOV sources, `.mp3` if the source is webm/mkv.

### 3. Transcribe with Whisper

Use the `medium` model for better accuracy (the default `tiny`/`base` hallucinates on non-English):
```bash
uvx --from openai-whisper whisper --language LANG_CODE --model medium "input.MP4"
```

Common language codes: `zh` (Chinese), `ja` (Japanese), `es` (Spanish), `fr` (French), `de` (German), `ko` (Korean).

Whisper may hallucinate on:
- Silent gaps (channel intros, music, pauses) — watch for garbled English in a non-English transcript
- Looping/repeated segments — deduplicate
- Channel branding overlaid as audio — cut these (they're not lesson content)

### 4. Identify show structure

From the transcript, identify:
- **Host intro** (keep — it introduces characters and sets context)
- **Vocabulary preview** (keep — list the words)
- **Main dialogue** (keep — the core lesson content)
- **Outro/branding** (cut — "请保持好奇心，下期见" type lines are not lesson content)

### 5. Write the markdown memo

Use this structure:

```markdown
# [Title in target language]
*[English translation; include romanization only for languages/scripts where it helps, e.g. Chinese/Japanese]*

---

## 📄 Transcript

[Clean transcript. First choose a concise vocabulary list of genuinely difficult/useful words for the learner; do not include easy words. In the transcript, annotate only those selected vocabulary items (ideally at first occurrence). For languages where the learner needs pronunciation help (e.g. Chinese/Japanese), add pinyin/furigana. For languages whose pronunciation the user can already handle (e.g. Swedish), annotate with a short English meaning instead.
Format examples: **词** (pīnyīn), **漢字** (かんじ), or **blyg** (*shy*)]

---

## 🔤 Vocabulary

| Word | Meaning |
|---|---|
| ... | ... |

---

## 📚 Grammar structures

### 1. [Pattern in target language; add romanization only if useful] — *[English gloss]*
> [Example sentence from the transcript]
> *[English translation]*

[2–3 sentences explaining the pattern, when to use it, variations.]

---
```

### Annotation guidelines by language

**Chinese (zh):**
- Add pinyin only for words a learner at this level likely doesn't know yet
- Skip pinyin for words already in the vocabulary preview (they're being taught)
- Include tones — `mā má mǎ mà`
- Grammar: focus on patterns like 把, 是…的, 只要…就, 一边…一边, 越来越, 虽然…但是

**Japanese (ja):**
- Add furigana for kanji a learner at this level likely doesn't know
- Format: **漢字** (かんじ)
- Grammar: focus on te-form uses, conditionals, particles, keigo levels

**Other languages:**
- Do not add pronunciation by default. If the user can already pronounce the language/script (e.g. Swedish), put the English meaning inline for harder words instead of pronunciation hints.
- Only add pronunciation hints when pronunciation is genuinely non-obvious or the user asks for them.
- Vocabulary tables should omit pronunciation columns unless pronunciation is needed for that language.
- Grammar: focus on structures that differ significantly from English

### 6. Save files

- Audio: `[video_basename].[audio_ext]` in the same directory as the video
- Markdown: `[video_basename].md` in the same directory as the video

If the video filename is truncated or missing words (e.g. `表格和.MP4`), infer the full title from the transcript content and use that as the markdown filename (e.g. `表格和规定.md`) and as the document title.

## Example invocation

> `/duo 表格和.MP4 Chinese`
> `/duo 咖啡店里的办公趋势.mp4 zh`
> "make a study memo from this Japanese video: lesson3.mp4"
