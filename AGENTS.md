# Arohah — AI Agent Instructions

## Project
Arohah is a voice-first Indian-language music composition assistant.
The core experience is: record/upload a hum → extract notes → clean up
→ detect key/BPM → suggest arrangement → browser playback → MIDI export.

The Project Bible and API Contract are the source of truth.

## Non-negotiable rules
1. Follow the Project Bible. Do not introduce scope beyond the agreed plan.
2. Never invent Gnani API endpoints, parameters, language codes, or response shapes.
3. Keep external services behind adapter interfaces with mock implementations.
4. Never commit API keys, credentials, or `.env` files.
5. Do not make unsupported accuracy claims. Expose confidence and limitations.
6. Keep dependencies lightweight. Avoid large models and sample banks.
7. Add a test or runnable sample for each pipeline stage or endpoint.
8. Preserve raw input data when processing or cleaning it.
9. Treat seed samples as read-only. Editing a sample must create a separate project.
10. Record significant technical decisions in the appropriate DECISIONS file.

## Ownership
Every file has one owner. Do not edit another person's files.

### Person A — Backend and music engine
Refer to A's ownership list in Arohah_TEAM_PLAN.md.
Record cross-owner change requests in OPEN_QUESTIONS_A.md.

### Person B — Frontend, Gnani and voice
Refer to B's ownership list in Arohah_TEAM_PLAN.md.
Record cross-owner change requests in OPEN_QUESTIONS_B.md.

### Shared files
Changes to shared files require the approval process described in
Arohah_TEAM_PLAN.md.

## Git workflow
- Work on feature branches, not directly on main.
- Use feat/a/<topic> for Person A and feat/b/<topic> for Person B.
- Keep changes focused and submit small pull requests.
- Rebase or pull from main before starting work and before opening a PR.
- Do not force-push main.
- Do not modify another person's lockfile or requirements file.

## Before changing code
1. Inspect the existing implementation.
2. Check the Project Bible and API Contract.
3. Confirm that the file belongs to you.
4. Avoid unrelated refactoring.
5. Run the relevant tests and report what could not be tested.

## Reporting
Clearly distinguish implemented functionality, mock functionality, and
unverified functionality. Never present mock output as live provider output.

## Person A instructions
Person A: add any additional backend/music-engine instructions below.

## Person B instructions
Person B: add any additional frontend/Gnani/voice instructions below.
