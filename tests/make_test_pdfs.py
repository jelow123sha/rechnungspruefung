"""Erzeugt Test-PDFs im Eingangsordner und prueft die App-Logik."""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "eingang"
INPUT.mkdir(exist_ok=True)


def make_pdf(path: Path, lines: list[str], creation: str) -> None:
    content_parts = ["BT /F1 12 Tf 50 800 Td 16 TL"]
    for line in lines:
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_parts.append(f"({safe}) Tj T*")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /Info 6 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /CreationDate ({creation}) /Producer (TestTool) >>".encode(),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    path.write_bytes(out)


make_pdf(
    INPUT / "RE-2024-001_muster_gmbh.pdf",
    [
        "Muster GmbH, Musterstr. 1, 12345 Musterstadt",
        "USt-IdNr: DE123456789",
        "",
        "Rechnungssteller: Muster GmbH",
        "Rechnungsempfaenger: Stadtwerke Beispielstadt",
        "Rechnungsnummer: RE-2024-001",
        "",
        "Pos 1  Beratung  500,00 EUR",
        "Pos 2  Wartung   300,00 EUR",
        "Nettobetrag: 800,00 EUR",
        "Umsatzsteuer 19%: 152,00 EUR",
        "Gesamtbetrag (brutto): 952,00 EUR",
    ],
    "D:20250115103000",
)
make_pdf(
    INPUT / "nord_dienstleistungen_4711.pdf",
    [
        "Nord Dienstleistungen AG",
        "Hafenstr. 10, 20095 Hamburg",
        "",
        "Kunde: Baufirm Mueller & Partner GbR",
        "Rechnung Nr. 4711",
        "",
        "Zwischensumme: 1.000,00 EUR",
        "MwSt 19%: 190,00 EUR",
        "Rechnungsbetrag: 1.190,00 EUR",
    ],
    "D:20250220141500",
)

# ZUGFeRD-ahnliche E-Rechnung: kaum sichtbarer Text, Daten in eingebetteter XML
make_pdf(
    INPUT / "EB-2025-088_elektro_bauer.pdf",
    ["Elektronische Rechnung EB-2025-088", "Siehe eingebettete XRechnung (XML)."],
    "D:20250310091500",
)
CII_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty><ram:Name>Elektro Bauer GmbH</ram:Name></ram:SellerTradeParty>
      <ram:BuyerTradeParty><ram:Name>Stadt Musterhausen</ram:Name></ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>1200.00</ram:TaxBasisTotalAmount>
        <ram:GrandTotalAmount>1428.00</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
from pypdf import PdfReader, PdfWriter
writer = PdfWriter(clone_from=str(INPUT / "EB-2025-088_elektro_bauer.pdf"))
writer.add_attachment("factur-x.xml", CII_XML.encode("utf-8"))
with open(INPUT / "EB-2025-088_elektro_bauer.pdf", "wb") as fh:
    writer.write(fh)

print("Test-PDFs erstellt:", [p.name for p in INPUT.glob('*.pdf')])
