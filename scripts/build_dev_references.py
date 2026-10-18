"""Build manually reviewed pilot labels from CUAD training annotations.

The values below were reviewed against answer spans and selected source context.
Ambiguous or misleading annotations are kept visible instead of forcing labels.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("Document Name", "Parties", "Agreement Date", "Effective Date", "Governing Law")


def found(value, manual_evidence=None):
    label = {"status": "found", "value": value}
    if manual_evidence:
        label["manual_evidence"] = manual_evidence
    return label


def missing():
    return {"status": "missing", "value": None}


def ambiguous(note):
    return {"status": "ambiguous", "value": None, "note": note}


def unscorable(note):
    return {"status": "unscorable", "value": None, "note": note}


# Each row follows FIELDS order. Index refers to manifests/development.json.
LABELS = [
    [found("DISTRIBUTOR AGREEMENT"), found(["Electric City Corp.", "Electric City of Illinois LLC"]), found("1999-09-07"), ambiguous("Commencement depends on delivery of the last Sample; immediate-effect clause does not establish a calendar date."), found("Illinois, US")],
    [found("Promotion and Distribution Agreement"), found(["Google Inc", "Whitesmoke Inc."]), missing(), found("2011-08-01"), found("England and Wales")],
    [found("Attachment C to Master Franchise Agreement MULTI-STATE ADDENDUM CALIFORNIA APPENDIX"), missing(), missing(), missing(), found("New York, US")],
    [found("DOMAIN NAME AND CONTENT LICENSE AGREEMENT"), found(["Beijing Yisheng Leju Information Services Co., Ltd.", "Beijing SINA Internet Information Service Co., Ltd."]), missing(), ambiguous("Effective Date is defined by a different agreement's Closing Date."), found("China (PRC)")],
    [found("JOINT FILING STATEMENT"), found(["SCULPTOR MANAGEMENT, INC.", "SCULPTOR CAPITAL LP", "SCULPTOR CAPITAL HOLDING CORPORATION", "SCULPTOR MASTER FUND LTD"]), found("2020-04-08"), missing(), missing()],
    [found("DISTRIBUTION AND SERVICES AGREEMENT"), found(["Integrity Short Term Government Fund", "Integrity Funds Distributor, LLC"]), found("2020-01-18"), found("2020-01-18", ["DISTRIBUTION AND SERVICES AGREEMENT January 18, 2020", "executed as of the date first set forth herein."]), found("Kansas, US")],
    [found("TRANSITION SERVICES AGREEMENT"), found(["Reynolds Consumer Products Inc.", "Reynolds Group Holdings Inc."]), ambiguous("Day is redacted in the annotated agreement date."), missing(), found("Illinois, US")],
    [found("JACKSONVILLE JAGUARS SPONSORSHIP AGREEMENT"), found(["The ARC Group, Inc.", "Jacksonville Jaguars, LLC"]), found("2017-11-27"), found("2018-04-01"), missing()],
    [found("Maintenance and support contract"), found(["Sicap Ltd", "EuroTel"]), found("2000-10-10", ["dated 10 October 2000"]), found("2000-10-06"), missing()],
    [found("AFFILIATE OFFICE AGREEMENT"), found(["Payment Data Systems, Inc.", "NETWORK 1 FINANCIAL, INC."]), ambiguous("Annotated agreement date is an unfilled template."), missing(), unscorable("CUAD Governing Law spans describe two arbitration locations, not a governing-law clause.")],
    [found("MASTER OPERATION AND MAINTENANCE AGREEMENT"), found(["DIAMOND STATE GENERATION PARTNERS, LLC", "BLOOM ENERGY CORPORATION"]), found("2012-04-13"), ambiguous("Term starts with a future warranty-period event."), found("New York, US")],
    [found("SUPPLY AGREEMENT"), found(["CREMER OLEO GmbH & Co KG", "Ultragenyx Pharmaceutical Inc"]), found("2012-11-19"), found("2012-11-19", ["This Agreement shall become effective on the date of its execution", "Hamburg, November 19t h, 2012"]), found("Germany")],
    [found("Strategic Alliance Agreement"), found(["UTEK Corporation", "Manakoa Services Corporation"]), found("2006-06-14"), missing(), missing()],
    [found("PRODUCT MANUFACTURING AGREEMENT"), found(["KITOV Pharma Ltd.", "DEXCEL LTD."]), missing(), ambiguous("Effective date is the last party's signature date, which is not provided in the annotated span."), found("Israel")],
    [found("CONSULTING AGREEMENT"), found(["Kiromic, Inc", "Gianluca Rotino"]), found("2018-07-20"), found("2018-07-01"), found("Texas, US")],
    [found("SERVICES AGREEMENT"), found(["PFS Funds", "Potomac Fund Management, Inc."]), found("2020-06-24"), found("2020-06-24"), found("Massachusetts, US")],
    [found("Strategic Alliance Agreement"), found(["Bravatek Solutions, Inc.", "Sibannac, Inc."]), found("2017-11-30"), found("2017-11-30", ["This Agreement shall not be considered accepted, approved or otherwise effective until signed by the appropriate parties.", "Date: November 30, 2017"]), found("Texas, US")],
    [found("DISTRIBUTORSHIP AGREEMENT"), ambiguous("Distributor's legal name and both dates are blank in this template."), ambiguous("Agreement date is blank."), ambiguous("Effective date is blank."), found("California, US")],
    [found("Amendment n� 01 to the Global Maintenance Agreement ref. DS/C-3957/14 Issue 7"), found(["AZUL LINHAS A�REAS BRASILEIRAS S/A", "AVIONS DE TRANSPORT REGIONAL, G.I.E"]), found("2016-01-06"), found("2016-01-06"), found("New York, US")],
    [found("DISTRIBUTOR AGREEMENT"), found(["European Micro", "WatchGuard Technologies, Inc."]), found("1997-11-05"), found("1997-11-05"), found("Washington, US")],
]


def main() -> None:
    manifest = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
    dataset = json.loads(
        (ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8")
    )
    by_title = {contract["title"]: contract for contract in dataset["data"]}
    if len(LABELS) != len(manifest["contracts"]):
        raise ValueError("Reference rows do not match development manifest")

    reviewed = []
    for entry, values in zip(manifest["contracts"], LABELS, strict=True):
        contract = by_title[entry["title"]]
        if len(values) != len(FIELDS):
            raise ValueError(f"Wrong field count for {entry['title']}")
        spans = {field: [] for field in FIELDS}
        for paragraph_index, paragraph in enumerate(contract["paragraphs"]):
            context = paragraph["context"]
            for qa in paragraph["qas"]:
                field = qa["id"].rsplit("__", 1)[-1].rsplit("_", 1)[0]
                if field not in spans:
                    continue
                for answer in qa["answers"]:
                    start, quote = answer["answer_start"], answer["text"]
                    if context[start : start + len(quote)] != quote:
                        raise ValueError(f"Invalid evidence offset for {entry['title']} {field}")
                    spans[field].append({
                        "paragraph": paragraph_index,
                        "start": start,
                        "end": start + len(quote),
                        "qa_id": qa["id"],
                    })
        fields = {}
        for field, label in zip(FIELDS, values, strict=True):
            for quote in label.get("manual_evidence", []):
                matches = [(index, paragraph["context"].find(quote))
                           for index, paragraph in enumerate(contract["paragraphs"])]
                matches = [(index, start) for index, start in matches if start >= 0]
                if len(matches) != 1:
                    raise ValueError(f"Manual evidence not uniquely located: {entry['title']} {field}")
                paragraph_index, start = matches[0]
                spans[field].append({"paragraph": paragraph_index, "start": start,
                                     "end": start + len(quote), "qa_id": None,
                                     "origin": "manual_review"})
            if label["status"] == "missing" and spans[field]:
                raise ValueError(f"Missing label has evidence: {entry['title']} {field}")
            if label["status"] == "found" and (label["value"] is None or not spans[field]):
                raise ValueError(f"Found label lacks value/evidence: {entry['title']} {field}")
            fields[field] = {key: value for key, value in label.items() if key != "manual_evidence"}
            fields[field]["source_spans"] = spans[field]
        reviewed.append({"title": entry["title"], "fields": fields})

    output = ROOT / "references/development.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"source_split": "train", "contracts": reviewed}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(reviewed)} development references: {output}")
    print("Unscorable fields:", sum(f["status"] == "unscorable" for c in reviewed for f in c["fields"].values()))


if __name__ == "__main__":
    main()
