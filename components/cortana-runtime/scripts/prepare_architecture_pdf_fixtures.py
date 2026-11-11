"""Generate only labelled local acceptance PDFs; no real financial records."""
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from PIL import Image

folder=Path(__file__).resolve().parents[1]/'documents/Architecture Demo'
target=folder/'receipt-and-warranty-demo.pdf'
if not target.exists():
    writer=PdfWriter()
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    pages=[['FICTIONAL CORTANA DEMO RECEIPT','Issuer: Demo Store','Date: 2026-11-04',
            'Amount: INR 1250.00','Receipt number: DEMO-0042','Payment alone does not prove warranty coverage.'],
           ['FICTIONAL CORTANA DEMO - UNAPPROVED WARRANTY DRAFT','Reference: DEMO-0042',
            'Draft warranty expiry: 2026-12-01.','Review this draft on 2026-11-05.',
            'No approval or actual purchase is established by this test document.']]
    for lines in pages:
        page=writer.add_blank_page(width=595,height=842)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content='BT /F1 14 Tf 50 780 Td 24 TL\n'+'\n'.join('('+line.replace('(','\\(').replace(')','\\)')+') Tj T*' for line in lines)+'\nET'
        stream=DecodedStreamObject();stream.set_data(content.encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    with target.open('xb') as output:
        writer.write(output)
scan=folder/'scanned-receipt-demo.pdf'
if not scan.exists():
    with Image.open(folder/'scan.png') as image:
        image.convert('RGB').save(scan,'PDF',resolution=160)
print('Labelled two-page text PDF and scanned PDF fixtures are ready.')
