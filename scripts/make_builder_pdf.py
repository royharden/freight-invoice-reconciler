"""Author one deterministic original builder PDF, without external document bytes."""

import base64
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT = "\n".join([
    "FREIGHTREC INVOICE V1", "Carrier: Saffron Meadow Demo Carrier",
    "Invoice: BUILDER-PDF-1", "Issued: 2026-01-07T12:00:00+00:00",
    "Currency: USD", "Total: 1735.00", "Lines:",
    "PDF-LH-1|BUILDER-SHIPMENT-1|LINEHAUL|0|USD|1400.00",
    "PDF-FS-1|BUILDER-SHIPMENT-1|FUEL|0|USD|140.00",
    "PDF-DET-1|BUILDER-SHIPMENT-1|DETENTION|1|USD|195.00",
])


def original_pdf(text=TEXT):
    """Plain ASCII text in original PDF objects, following the repo test pattern."""
    commands = [b"BT /F1 10 Tf 40 760 Td 14 TL"]
    for line in text.splitlines():
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(b"(" + escaped.encode("ascii") + b") Tj T*")
    content = b"\n".join([*commands, b"ET"])
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii") + value + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def preserve(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("refusing to replace frozen builder fixture: " + str(path))
    else:
        with path.open("xb") as stream:
            stream.write(raw)


def main():
    fixtures = ROOT / "fixtures/builder"
    pdf = original_pdf()
    bundle = json.loads((fixtures / "simple-shipment.json").read_text(encoding="utf-8"))
    bundle["invoices"] = [{"media_type": "application/pdf", "template_id": "freightrec-invoice-v1",
                           "data_base64": base64.b64encode(pdf).decode("ascii")}]
    preserve(fixtures / "native-invoice-v1.pdf", pdf)
    preserve(fixtures / "native-pdf-bundle.json",
             (json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"origin": "builder_non_independent", "pdf_bytes": len(pdf),
                      "pdf_sha256": sha256(pdf).hexdigest()}))


if __name__ == "__main__":
    main()
