# Two-minute portfolio walkthrough

Use synthetic data only for the demo. Start the local server with the README command.

1. **0:00 — Problem.** “Contracts are long and inconsistent. This pilot extracts five fields and supplies quotations so a reviewer can check each answer.” Show the upload page at `http://127.0.0.1:8080`.
2. **0:20 — Input.** Open `examples/sample_agreement.pdf`: two parties, an agreement date, a conditional effective date, and Illinois law. Upload it and select Extract. Explain that actual processing takes time; do not present an edited wait as a latency measurement.
3. **0:45 — Output.** Show the returned name and parties with page-1 quotations. Show agreement date `2024-01-01`, then the ambiguous effective date with page-2 evidence. “A date depending on delivery is not a timestamp we can guess.” Download JSON.
4. **1:15 — Architecture.** Show the README diagram: Docling reads the PDF, LlamaIndex coordinates chunks, OpenAI returns structured candidates, Pydantic and evidence checks validate them.
5. **1:35 — Measurement.** Show `reports/held_out.md`: ten official test contracts, frozen configuration, per-field support, errors and processing failures. Distinguish supplied-text results from PDF results and the three-contract development parser comparison.
6. **1:55 — Scope.** “This is a local portfolio pilot. Cloud deployment awaits billing and live checks. Scores are not production-wide accuracy claims.”

For an offline walkthrough, play [pilot_walkthrough.mp4](examples/pilot_walkthrough.mp4) (48 seconds, captions, no audio), or show `examples/sample_result.json`. The video is an explanatory slideshow using a saved real synthetic extraction, not a live screen recording or a new benchmark run. Rebuild it with `python -m scripts.create_demo` when Pillow, ffmpeg and the Windows Segoe UI fonts are available.
