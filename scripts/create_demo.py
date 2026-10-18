"""Create a captioned, offline video walkthrough from a saved real synthetic run.

Requires Pillow (installed with the parser stack), Windows Segoe UI fonts, and ffmpeg.
This is an explanatory slideshow, not a screen recording or a new extraction.
"""
import json
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def main():
    result = json.loads((ROOT / "examples/sample_result.json").read_text())
    fields = result["extraction"]
    slides = [
        ("From contract to evidence", ["Document Intelligence Pipeline", "Five fields. Validated JSON. Source quotations.",
         "Offline walkthrough using a saved real synthetic extraction.", "Local portfolio pilot; no production accuracy claim."]),
        ("1 / Supply a PDF", ["POST /extract   |   Browser upload page at localhost:8080", "Example: a two-page services agreement", "Acme Ltd + Example Technologies", "Only listed CUAD/synthetic PDFs, up to 10 MiB."]),
        ("2 / Parse, extract, validate", ["Docling: PDF pages and text", "LlamaIndex: page-preserving chunks", "OpenAI: structured candidate values", "Pydantic + quotation checks: validate shape and source evidence"]),
        ("3 / Inspect the result", [f"Name: {fields['document_name']['value']}",
         f"Parties: {', '.join(fields['parties']['value'])}",
         f"Agreement date: {fields['agreement_date']['value']}",
         f"Governing law: {fields['governing_law']['value']}"]),
        ("4 / Keep uncertainty visible", [f"Effective date status: {fields['effective_date']['status']}",
         'Evidence: "Effective upon first delivery." (page 2)',
         "No fixed date is established. Do not invent a timestamp.", "A matching quote supports review; it does not prove interpretation."]),
        ("5 / Measure and disclose", ["20 development contracts / 10 held-out test contracts", "Frozen model, prompt, parsers, schema and scoring", "Field precision/recall/F1, evidence overlap, failures, cost and latency", "See reports/held_out.md. Cloud deployment awaits billing and checks."]),
    ]
    out = ROOT / "outputs/demo_frames"
    out.mkdir(parents=True, exist_ok=True)
    title_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 46)
    body_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28)
    small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 21)
    for index, (title, lines) in enumerate(slides):
        im = Image.new("RGB", (1280, 720), "#101d2e")
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((64, 66, 1216, 654), radius=22, fill="#172a40")
        draw.rectangle((96, 103, 164, 109), fill="#5ad4bd")
        draw.text((96, 137), title, font=title_font, fill="white")
        y = 240
        for line in lines:
            for segment in textwrap.wrap(line, width=70):
                draw.text((96, y), segment, font=body_font, fill="#dde7f1")
                y += 39
            y += 23
        draw.text((96, 606), f"SAVED SYNTHETIC EXAMPLE  |  {index + 1}/{len(slides)}", font=small, fill="#5ad4bd")
        im.save(out / f"{index:02}.png")
    target = ROOT / "examples/pilot_walkthrough.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1/8",
                    "-i", str(out / "%02d.png"), "-c:v", "libx264", "-r", "24",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)], check=True)
    print(target)


if __name__ == "__main__":
    main()
