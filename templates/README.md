# How to Use Storyteller Templates 🎬

These templates are pre-structured scripts designed to trigger the visual layouts of **Automatic Storyteller Animate** (`chain`, `split`, `window`, `check`, `stat`, `quote`, and photo blocks).

---

## Available Templates

| Template | Genre | Key Visual Hits |
|---|---|---|
| [`tech-explainer/`](./tech-explainer/script.md) | Software, Cybersecurity, AI | Terminal code windows, pipelines, comparisons |
| [`business-story/`](./business-story/script.md) | Product launch, Startups, Case studies | Big numbers, metric counters, quotes, checkmarks |
| [`science-curiosity/`](./science-curiosity/script.md) | Science, "What If", History | Dramatic stats, split contrasts, evidence-board photos |

---

## 3-Step Workflow

### Step 1: Pick and Edit a Template
Copy any `script.md` into your project directory and adapt the text.

> **Script formatting tip**:
> - `# Headings` become section kickers on screen.
> - Keep sentences punchy (under 9 words / 64 characters per line) for optimal caption typography.
> - Keywords like `code`, `terminal`, `versus`, `before`, `after`, `protect`, and numbers automatically trigger visual blueprints!

### Step 2: Generate or Record Narration
Generate your voiceover file (`voice.mp3` or `voice.wav`) using:
- Any TTS engine (ElevenLabs, OpenAI TTS, Kokoro, Edge TTS)
- Or your own microphone recording in a single clean take.

### Step 3: Run the Engine
```powershell
python scripts/run.py --project my-video --voice voice.mp3 --script script.md
```
Or run a fast 360p draft first:
```powershell
python scripts/run.py --project my-video --voice voice.mp3 --script script.md --preview
```
