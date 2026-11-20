## 🤖 How to Use with AI Agents (OpenCode, Claude Code, Cursor)

This skill is designed for autonomous AI coding agents. You don't need to manually configure the timeline — simply attach your voiceover and script files, invoke the skill, and let the agent trigger full production.

### 1. Install the Skill
Place this entire folder into your agent's skills directory:
- **OpenCode:** `.opencode/skills/Automatic-Storytailer-Animate/`
- **Claude Code:** `.claude/skills/Automatic-Storytailer-Animate/`

### 2. Triggering via Prompt
In your agent chat, mention the skill and attach your files:

> **Example Prompt:**  
> *"@Automatic-Storytailer-Animate create an explainer video using voiceover `narration.mp3` and script `script.md`."*

### 3. What the Agent Does Automatically:
1. **Checks Prerequisites**: Validates Python, Skia, FFmpeg, Whisper, and the sibling engine.
2. **Generates Preview First**: Renders a fast 360p draft of blocks 0–1 to verify pacing, layout, and style rhythm.
3. **Executes Full Pipeline**: 
   - Transcribes & synchronizes audio word-for-word.
   - Alternates between blueprint whiteboard sketches and photo evidence-wall layouts.
   - Burns bottom-flush kinetic neon captions.
   - Mixes sound effects and background score to `-15 LUFS`.
4. **Runs Automated QA**: Validates audio loudness and visual margin bounds before delivering `FILM.mp4` and `FILM.srt`.