# Cut Away frontend redesign plan

## Product direction
A cinematic editor console for Cut Away: users import a source video, describe the moments they want, watch the analysis state, and preview/download a merged cut.

## Design system
- **Design movement:** cinematic darkroom + modern non-linear editing workstation.
- **Core principles:** high signal over decoration; depth through layered surfaces; progress always visible; controls feel tactile and intentional.
- **Color philosophy:** graphite and ink create a quiet monitoring room; acid lime marks readiness and successful cuts; warm coral is reserved for the active action; lavender-blue is used for analysis intelligence.
- **Layout paradigm:** asymmetric workstation shell with a fixed command rail, a dominant monitor canvas, and a lower timeline strip rather than centered marketing cards.
- **Signature elements:** animated 3D analysis core, film-strip timeline markers, and thin technical readouts.
- **Interaction philosophy:** every action has an immediate visual response; steps transition in place; buttons use concise editor language.
- **Animation:** slow ambient orb drift, scanline shimmer during processing, progress sweep, and restrained slide/fade transitions. Respect prefers-reduced-motion.
- **Typography:** Space Grotesk for controls and headlines, IBM Plex Mono for timecodes, status and metadata.
- **Brand essence:** an AI-assisted rough-cut workstation for people who want the good parts of long videos without watching the whole export. Precise, cinematic, quietly technical.
- **Brand voice:** direct and editorial. Example: “Find the signal.” / “Your cut is ready to screen.”
- **Wordmark:** a compact “CA” monogram built from two crossing edit blades beside the Cut Away wordmark.
- **Signature brand color:** acid lime `#d8ff63`.

## Implementation
- Keep the dependency-free HTML/CSS/JS frontend.
- Preserve `POST /upload`, `POST /generate`, `GET /status/{job_id}`, and `GET /result/{job_id}` contracts.
- Use the existing XHR upload progress implementation and status polling, while exposing richer progress text in the new editor UI.
- Add `public/manus-routes.json` for route discovery.
- Update README with Linux/macOS and Windows run commands and the new UI flow.
