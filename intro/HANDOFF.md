# "ASH SAYS" YouTube Intro — Handoff Notes

## Goal
Replace the current plain intro (crumpled paper unfolds → "ASH SAYS" appears centre → dissolve to the episode subtitle) with a character-driven title motion graphic starring **Ash**.

## Specs
- Aspect ratio: **16:9**
- Duration: **5–8 s** (target ~6–7 s)
- On-screen text: **English**
  - Main title: `ASH SAYS`
  - Episode subtitle: changes every episode (text TBD — ask the user)
- Font / colour for ASH SAYS: TBD — ask the user whether an existing brand font/colour exists

## Character: Ash
- Reference image: `intro/assets/ash_reference.png`
  (also uploaded to Higgsfield; the user's recent Higgsfield image uploads are from 2026-09-27)
- 3D paper-crafted man: white folded paper, low-poly faceted body, boxy square head, soft grey studio backdrop.
- **Hard rules (never violate):**
  - No pupils / irises / eye highlights — eyes stay as the two plain square cut-outs.
  - No tongue, no teeth — the mouth stays a closed flat line and never opens.
  - Emotion is conveyed through body language only (head tilt, pointing, hops, flipping paper).
  - Frame-check every generated clip; discard any take where pupils or an open mouth appear.

## Chosen direction: Concept A — "Paper Pop-out"
| Time | Beat |
|---|---|
| 0–1.5 s | A crumpled paper ball rolls into centre frame and pauses. |
| 1.5–3 s | The paper unfolds and folds itself up into Ash, who stands and spreads the sheet open. |
| 3–5 s | `ASH SAYS` is stamped onto the sheet; Ash points at it proudly. |
| 5–7 s | Instead of a dissolve, Ash flips the sheet over to reveal the episode subtitle on the back. |

Alternatives considered: B (speech bubble — rejected, implies mouth), C (crumple & toss).

## Production plan
1. Generate 3–4 storyboard still frames with Higgsfield (Ash reference as image input) and get user approval.
2. Generate the character animation once with Higgsfield image-to-video (no text in the generated clip).
3. Render the text layers here (HTML/CSS → frames via headless Chromium, or ffmpeg drawtext) and composite with ffmpeg,
   so the English text is pixel-exact.
4. Keep the subtitle as a template parameter: future episodes only re-render the text layer, not the character clip.

## Environment note
Higgsfield media is served from `d2ol7oe51mr4n9.cloudfront.net`. The environment's network access was switched to
**Custom** with that domain allowed (plus the default list); this applies to sessions started after the change.
Verify with: `curl -sS -o /dev/null -w "%{http_code}\n" https://d2ol7oe51mr4n9.cloudfront.net/`
