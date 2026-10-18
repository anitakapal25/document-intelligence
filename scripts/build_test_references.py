"""Reference adjudication from CUAD answers, reviewed before test predictions."""
import json
from scripts.build_dev_references import ROOT, FIELDS, found, missing, ambiguous


def unsupported(value):
    return {"status": "unscorable", "value": value,
            "note": "Jurisdiction is absent from the frozen scorer lookup; excluded before predictions, not an extraction error."}


LABELS = [
    [found("SUPPLY AGREEMENT"), found(["Integra LifeSciences Corporation", "PcoMed, LLC"]), found("2013-05-15"), found("2013-05-15"), unsupported("New Jersey, US")],
    [found("AMENDMENT NO. 2 TO MANUFACTURING AND SUPPLY AGREEMENT"), found(["Columbia Laboratories, (Bermuda) Ltd.", "Fleet Laboratories Limited"]), ambiguous("Only 2018 is supplied for this amendment; older dates refer to other agreements."), ambiguous("Only a year is supplied."), found("England and Wales")],
    [found("AMENDED AND RESTATED STRATEGIC LICENSING, DISTRIBUTION AND MARKETING AGREEMENT"), found(["PACIRA PHARMACEUTICALS, INC.", "EKR THERAPEUTICS, INC."]), found("2009-10-15"), found("2007-08-10"), found("New York, US")],
    [found("OUTSOURCING AGREEMENT"), found(["Photronics, Inc.", "Dai Nippon Printing Co., Ltd.", "Photronics DNP Photomask Corporation", "Xiamen American Japan Photronics Mask Co., Ltd."]), found("2017-05-16"), missing(), missing()],
    [found("COMPLEHON AGREEMENT AND UQITDITV MAINTENANCE AGREEMENT"), found(["PRIMEEVERGY CORPORATION", "PRIME OFFSHORE L.L.C.", "GUARANTY BANK"]), found("2006-06-29"), found("2006-06-29"), found("Texas, US")],
    [found("Manufacturing and Supply Agreement"), found(["VAPOTHERM, INC.", "MEDICA S.p.A."]), found("2013-01-01"), missing(), found("New York, US")],
    [found("Sales, Marketing, Distribution, and Supply Agreement"), found(["Hemispherx Biopharma, Inc.", "Scientific Products Pharmaceutical Co. LTD."]), found("2016-03-31"), ambiguous("Last signature is March 31, 2016, but main agreement also requires receipt of all counterparts; no receipt date is supplied."), unsupported("Delaware, US")],
    [found("COOPERATION AGREEMENT"), found(["City of Fort Stockton", "STW Resources Holding Corp"]), ambiguous("Notary and signature dates are blank except year 2014."), ambiguous("Depends on last signature; signature dates are blank."), found("Texas, US")],
    [found("HOSTING AGREEMENT"), found(["eGain Communications Corporation", "Eliance Corporation"]), missing(), missing(), found("California, US")],
    [found("SPONSORSHIP AGREEMENT"), found(["PEEK Investments LLC", "Platinum Partners Value Arbitrage Fund L.P.", "Snowy August Fund I LP"]), found("2012-07-16"), found("2012-07-16"), found("New York, US")],
]


def main():
    manifest = json.loads((ROOT / "manifests/held_out.json").read_text())
    dataset = json.loads((ROOT / "data/raw/cuad_benchmark/test.json").read_text(encoding="utf-8"))
    by_title = {c["title"]: c for c in dataset["data"]}
    contracts = []
    for entry, labels in zip(manifest["contracts"], LABELS, strict=True):
        spans = {f: [] for f in FIELDS}
        for pi, paragraph in enumerate(by_title[entry["title"]]["paragraphs"]):
            for qa in paragraph["qas"]:
                field = qa["id"].rsplit("__", 1)[-1]
                if field.rsplit("_", 1)[-1].isdigit():
                    field = field.rsplit("_", 1)[0]
                if field not in spans:
                    continue
                for answer in qa["answers"]:
                    start, quote = answer["answer_start"], answer["text"]
                    if paragraph["context"][start:start + len(quote)] != quote:
                        raise ValueError("Reference offset mismatch")
                    spans[field].append({"paragraph": pi, "start": start,
                                         "end": start + len(quote), "qa_id": qa["id"]})
        fields = {f: {**label, "source_spans": spans[f]} for f, label in zip(FIELDS, labels, strict=True)}
        for field in fields.values():
            if field["status"] == "found" and not field["source_spans"]:
                raise ValueError("Found reference requires evidence")
            if field["status"] == "missing" and field["source_spans"]:
                raise ValueError("Missing reference has annotated evidence")
        contracts.append({"title": entry["title"], "fields": fields})
    result = {"source_split": "test", "review": "Agent-reviewed against CUAD spans and source context before predictions; no independent human adjudication.",
              "policy": "Collapse aliases/former names to legal entities. Retain CUAD OCR spellings and annotated title extent. Absent annotations remain missing; not proof that the full contract lacks a clause. Incomplete dates are ambiguous. Unsupported frozen jurisdictions are unscorable.",
              "contracts": contracts}
    target = ROOT / "references/held_out.json"
    if target.exists() and json.loads(target.read_text()) != result:
        raise ValueError("Refusing to overwrite reviewed test references")
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
