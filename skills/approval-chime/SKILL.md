1|---
2|name: approval-chime
3|description: Use when an approval alert should chime instead of TTS.
4|version: 1.0.0
5|author: local
6|license: MIT
7|metadata:
8|  hermes:
9|    tags: [approval, voice, tts, alert, chime, audio]
10|    related_skills: [hermes-agent, skill-authoring]
11|---
12|
13|# Approval Chime (chime-on-alert)
14|
15|Make Hermes play a short bell/chime through your speakers instead of spoken TTS when an
16|approval card needs attention (also covers long-turn-finished alerts). Needed because the
17|default `approval-voice` TTS can fail silently in multiplexed-gateway profiles with
18|`cannot read this profile's MIMO_API_KEY` — the plugin hook fires but synthesis returns no
19|audio, so you never hear the alert.
20|
21|## When to Use
22|
23|- The `approval-voice` plugin is enabled but you never hear the spoken alert (TTS silently
24|  fails — check `~/.hermes/logs/agent.log` for `approval-voice: synthesis returned no audio`).
25|- You prefer a non-verbal bell over a spoken voice for approval/long-task alerts.
26|- Porting this chime-on-alert setup to another Hermes installation (e.g. Windows → Linux).
27|
28|## How it works
29|
30|The `approval-voice` plugin hooks `pre_approval_request`. We replace its `_speak()` so it
31|plays a fixed `chime.wav` via `tools.voice_mode.play_audio_file` instead of calling the TTS
32|provider. The hook machinery (`register()`) stays untouched.
33|
34|## Install (any platform)
35|
36|1. **Locate the plugin dir.** Find the folder that holds both `plugin.yaml` and `__init__.py`
37|   for approval-voice. It lives in the profile's plugins dir — on this install:
38|   `C:\Users\<user>\AppData\Local\hermes\plugins\approval-voice\` (Windows) or
39|   `~/.local/share/hermes/plugins/approval-voice/` (Linux). If unsure, run
40|   `find "$HERMES_HOME" "$HERMES_DATA" -type d -name approval-voice 2>/dev/null`.
41|2. **Put the chime sound next to `__init__.py`.** Copy `{baseDir}/assets/chime.wav` into the
42|   plugin dir. (Or regenerate it yourself: `yt-dlp -x --audio-format wav -o chime <URL>`.)
43|3. **Add `import os`** near the other imports if it is missing.
44|4. **Replace `_speak()`** with the chime version below.
45|5. **Restart the gateway** — REQUIRED. The plugin is loaded at gateway start; without a
46|   restart the running gateway still has the old `_speak` in memory.
47|   `hermes gateway restart`
48|6. **Test:** `hermes config set approvals.mode manual`, then run any terminal command; you
49|   should hear the chime (card waits up to `approvals.timeout`). Set the mode back to your
50|   normal value afterwards.
51|
52|   ## Patched `_speak()`
53|
54|```python
55|def _speak(text: str) -> None:
56|    """Play the chime alert sound instead of TTS (TTS unreliable in multiplexed gateway)."""
57|    try:
58|        from tools.voice_mode import play_audio_file
59|    except Exception as exc:  # pragma: no cover - import guard
60|        logger.warning("approval-voice: voice_mode unavailable: %s", exc)
61|        return
62|    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chime.wav")
63|    if not os.path.isfile(path):
64|        logger.warning("approval-voice: chime.wav not found at %s", path)
65|        return
66|    try:
67|        if not play_audio_file(path):
68|            logger.warning("approval-voice: could not play %s (no audio device/player?)", path)
69|    except Exception as exc:
70|        logger.warning("approval-voice: playback failed: %s", exc)
71|```
72|
73|## Pitfalls
74|
75|- **Gateway caches plugin code at process start** — always `hermes gateway restart` after
76|  editing, or the change never takes effect and you'll think it is broken.
77|- `play_audio_file` needs a system player for non-WAV formats, but `.wav` plays via
78|  sounddevice when allowed. On Windows Hermes bundles ffplay at
79|  `$HERMES_HOME/tools/ffmpeg-*/bin/ffplay.exe`; on Linux it needs `ffplay` or `aplay` on PATH.
80|- Keep `register()` and the other hooks (`post_approval_response`, `pre_llm_call`,
81|  `post_llm_call`) intact — only `_speak` changes.
82|- `chime.wav` must sit next to `__init__.py`; the path is computed relative to the module.
83|- This only silences the plugin's alert TTS. Normal `text_to_speech` tool calls are unaffected.
84|- To revert to spoken alerts later, restore the original `_speak` (it called
85|  `text_to_speech_tool` then `play_audio_file`) and reinstall/repair the plugin.