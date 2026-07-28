# Ardour Live Workflow Pack — image-generation prompts

Mode: built-in image generation

## Initial generation

```text
Use case: ui-mockup
Asset type: high-fidelity desktop DAW compatibility-pack concept, 16:10 landscape application screenshot
Primary request: Show what a PhotoGIMP-style “Live Workflow Pack for Ardour” would look like: Ardour’s professional open-source audio engine and features reorganized to feel immediately familiar to experienced Ableton Live users, while remaining clearly Ardour and not copying Ableton logos or proprietary devices.
Scene/backdrop: straight-on full-screen desktop application UI only, no device frame, no desk, no browser chrome.
Style/medium: shippable realistic product UI, implementation-ready, crisp vector-like application screenshot; restrained modern DAW interface, not concept art.
Composition/framing: full app window. A slim top control bar with “ARDOUR” at far left and a small secondary label “LIVE WORKFLOW”; centered transport controls, tempo “124.00”, time signature “4/4”, global quantization “1 Bar”, metronome, loop, play, stop and record. At upper right, two compact view selectors labeled exactly “ARRANGEMENT” and “SESSION”, with ARRANGEMENT active.
Subject and layout: Recreate the familiar functional topology of a clip-based production DAW using Ardour concepts. Left column is a tall searchable Browser labeled “BROWSER” with categories “Favorites”, “Instruments”, “Audio Effects”, “MIDI Effects”, “Plug-ins”, “Clips”, “Samples”, and “Places”; small colored collection tags at top; a believable item list below. Center is a spacious horizontal Arrangement timeline with bar ruler, locator markers “Intro”, “Verse”, “Drop”, “Break”, and “Outro”; eight vertically stacked tracks containing crisp colored audio waveform clips and MIDI clips, automation, loop brace, and a precise playhead. Track controls are compact and aligned on the right edge of each lane to match Live-user muscle memory, with names “Kick”, “Percussion”, “Bass”, “Chords”, “Lead”, “Vocal”, “A Reverb”, “B Delay”, and “Master”, plus mute, solo, arm, monitoring and slim level meters. The selected track is “Chords”.
Bottom work area: a full-width dock divided by two tabs labeled exactly “CLIP” and “DEVICES”, with DEVICES active. Show a horizontal Ardour processor chain as a row of compact device cards labeled “MIDI Filter”, “ACE Synth”, “ACE EQ”, “Compressor”, “Utility”, and “Reverb Send”, with clear enable buttons, small high-quality parameter graphs and controls. At bottom-left show a subtle help/status line. At bottom-right show “48 kHz”, “64 samples”, “DSP 27%”.
Behavior conveyed visually: Tab switches ARRANGEMENT/SESSION; Shift+Tab switches CLIP/DEVICES; browser items drag into tracks or the processor chain; selected clip or track determines the bottom panel; Return buses and Master are always visible; secondary controls collapse cleanly.
Visual system: neutral graphite and warm gray surfaces, nearly flat, thin crisp dividers, clean sans-serif typography, no skeuomorphism. Bright but restrained clip colors: amber, teal, violet, coral and blue. Green only for play, red only for record/armed state. Dense professional information with excellent alignment and generous legibility. A subtle “Live Workflow” badge may use Ardour-red, but do not reproduce Ableton’s wordmark or logo.
Text (verbatim where visible): “ARDOUR”, “LIVE WORKFLOW”, “ARRANGEMENT”, “SESSION”, “BROWSER”, “Favorites”, “Instruments”, “Audio Effects”, “MIDI Effects”, “Plug-ins”, “Clips”, “Samples”, “Places”, “Intro”, “Verse”, “Drop”, “Break”, “Outro”, “Kick”, “Percussion”, “Bass”, “Chords”, “Lead”, “Vocal”, “A Reverb”, “B Delay”, “Master”, “CLIP”, “DEVICES”, “MIDI Filter”, “ACE Synth”, “ACE EQ”, “Compressor”, “Utility”, “Reverb Send”, “124.00”, “4/4”, “1 Bar”, “48 kHz”, “64 samples”, “DSP 27%”.
Constraints: preserve Ardour identity and plausible Ardour functionality; the result should feel like a reversible workflow/theme pack, not a separate DAW and not an Ableton clone. No Ableton logo, no proprietary Ableton device names, no trademarked marketing copy, no hardware mockup, no perspective tilt, no floating windows, no glassmorphism, no neon cyberpunk, no glossy gradients, no illegible microtext, no watermark.
```

## Targeted layout refinement

```text
Use case: precise-object-edit
Asset type: high-fidelity desktop DAW UI mockup refinement
Primary request: Change only the placement of the Arrangement track headers and their controls. Move the complete track-control column for “Kick”, “Percussion”, “Bass”, “Chords”, “Lead”, “Vocal”, “A Reverb”, “B Delay”, and “Master” from the left edge of the timeline to the far right edge of the timeline, directly before the application’s outer right border, matching the familiar Ableton Live Arrangement topology. Keep each header perfectly aligned with its corresponding track lane and retain mute, solo, arm, monitoring and meter controls. After moving them, let the colored clip lanes begin immediately to the right of the Browser.
Constraints: change only this layout placement. Keep the Browser on the far left unchanged; keep the entire top control bar, transport, labels, timeline content, clip colors, locator names, bottom CLIP/DEVICES panel, device cards, dimensions, typography, styling and all other content unchanged. Preserve “ARDOUR” and “LIVE WORKFLOW”. Do not add or remove tracks. No Ableton logo, no watermark, no perspective tilt.
```
