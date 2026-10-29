import io
import zipfile
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

class SimpleDocxBuilder:
    """
    Pure Python DOCX generator conforming to ECMA-376 OpenXML standard.
    Produces valid .docx files compatible with Microsoft Word, LibreOffice, and Google Docs
    without requiring third-party C-extensions or external libraries.
    """
    def __init__(self, title: str):
        self.title = title
        self.paragraphs = []

    def add_heading(self, text: str, level: int = 1):
        size = 32 if level == 1 else (26 if level == 2 else 22)
        color = "2B3A67" if level == 1 else "496A81"
        self.paragraphs.append({
            "type": "heading",
            "text": text,
            "size": size,
            "color": color,
            "bold": True,
            "space_before": 240,
            "space_after": 120
        })

    def add_paragraph(self, text: str, bold: bool = False, italic: bool = False, bullet: bool = False):
        self.paragraphs.append({
            "type": "paragraph",
            "text": text,
            "bold": bold,
            "italic": italic,
            "bullet": bullet,
            "size": 20,
            "color": "333333",
            "space_before": 60,
            "space_after": 60
        })

    def escape_xml(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def build(self) -> bytes:
        doc_body_xml = []
        for p in self.paragraphs:
            escaped = self.escape_xml(p["text"])
            r_pr = []
            if p.get("bold"):
                r_pr.append("<w:b/>")
            if p.get("italic"):
                r_pr.append("<w:i/>")
            if p.get("size"):
                r_pr.append(f'<w:sz w:val="{p["size"]}"/>')
            if p.get("color"):
                r_pr.append(f'<w:color w:val="{p["color"]}"/>')
            
            p_pr = []
            if p.get("bullet"):
                p_pr.append('<w:pStyle w:val="ListBullet"/>')
                escaped = f"•  {escaped}"
            if p.get("space_before") or p.get("space_after"):
                p_pr.append(f'<w:spacing w:before="{p.get("space_before", 0)}" w:after="{p.get("space_after", 0)}"/>')

            p_pr_str = f"<w:pPr>{''.join(p_pr)}</w:pPr>" if p_pr else ""
            r_pr_str = f"<w:rPr>{''.join(r_pr)}</w:rPr>" if r_pr else ""

            doc_body_xml.append(f'<w:p>{p_pr_str}<w:r>{r_pr_str}<w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>')

        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(doc_body_xml)}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>"""

        content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("word/document.xml", document_xml)

        return buffer.getvalue()


class SimplePdfBuilder:
    """
    Pure Python PDF 1.4 generator.
    Creates structured, multi-page vector PDF documents with text wrapping,
    tables, metadata headers, and visual dividers without requiring ReportLab.
    """
    def __init__(self, title: str):
        self.title = title
        self.pages = []  # list of list of content stream operations
        self.current_stream = []
        self.page_width = 595.28  # A4 width in pt
        self.page_height = 841.89  # A4 height in pt
        self.margin_x = 50.0
        self.margin_y = 50.0
        self.cursor_y = self.page_height - self.margin_y

    def _start_new_page(self):
        if self.current_stream:
            self.pages.append("".join(self.current_stream))
            self.current_stream = []
        self.cursor_y = self.page_height - self.margin_y

    def check_space(self, height_needed: float):
        if self.cursor_y - height_needed < self.margin_y + 30:
            self._start_new_page()

    def add_header(self, text: str, subtitle: Optional[str] = None):
        self.check_space(70)
        # Accent bar
        self.current_stream.append(f"0.24 0.35 0.90 rg\n") # Indigo/blue brand accent
        self.current_stream.append(f"{self.margin_x:.1f} {self.cursor_y - 2:.1f} 495.0 3.0 re f\n")
        
        # Title text
        safe_title = self._escape_pdf(text)
        self.current_stream.append(f"0.1 0.1 0.15 rg\n")
        self.current_stream.append(f"BT /F2 20 Tf {self.margin_x:.1f} {self.cursor_y - 24:.1f} Td ({safe_title}) Tj ET\n")
        self.cursor_y -= 34

        if subtitle:
            safe_sub = self._escape_pdf(subtitle)
            self.current_stream.append(f"0.4 0.45 0.55 rg\n")
            self.current_stream.append(f"BT /F1 10 Tf {self.margin_x:.1f} {self.cursor_y:.1f} Td ({safe_sub}) Tj ET\n")
            self.cursor_y -= 22

    def add_section(self, title: str):
        self.check_space(45)
        safe = self._escape_pdf(title)
        self.current_stream.append(f"0.2 0.25 0.4 rg\n")
        self.current_stream.append(f"BT /F2 13 Tf {self.margin_x:.1f} {self.cursor_y - 12:.1f} Td ({safe}) Tj ET\n")
        self.current_stream.append(f"0.85 0.88 0.92 RG 0.75 w\n")
        self.current_stream.append(f"{self.margin_x:.1f} {self.cursor_y - 16:.1f} m 545.0 {self.cursor_y - 16:.1f} l S\n")
        self.cursor_y -= 28

    def add_text_paragraph(self, text: str, font="F1", size=10, leading=14, indent=0, bullet=False):
        safe_text = self._escape_pdf(text)
        prefix = "•  " if bullet else ""
        full = prefix + safe_text

        # Approximate line wrapping (~85 chars per line at 10pt)
        words = full.split(" ")
        lines = []
        cur_line = []
        for w in words:
            cur_line.append(w)
            if len(" ".join(cur_line)) > 82:
                cur_line.pop()
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        for line in lines:
            self.check_space(leading)
            escaped_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            self.current_stream.append(f"0.15 0.18 0.22 rg\n")
            self.current_stream.append(f"BT /{font} {size} Tf {self.margin_x + indent:.1f} {self.cursor_y:.1f} Td ({escaped_line}) Tj ET\n")
            self.cursor_y -= leading

        self.cursor_y -= 4

    def _escape_pdf(self, s: str) -> str:
        # Standard ASCII representation, filter control characters
        clean = re.sub(r'[^\x20-\x7E]', ' ', s)
        return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def build(self) -> bytes:
        if self.current_stream:
            self.pages.append("".join(self.current_stream))

        if not self.pages:
            self.pages.append("BT /F1 12 Tf 50 750 Td (Empty Document) Tj ET")

        objects = []
        # Obj 1: Catalog
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        
        # Obj 2: Pages placeholder
        # Will build dynamically
        
        # Obj 3: Font F1 (Helvetica)
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        # Obj 4: Font F2 (Helvetica-Bold)
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        # Page objects and Stream objects
        page_obj_ids = []
        content_objects = []
        
        # Base ID starts at 5:
        # 1: Catalog
        # 2: Pages
        # 3: F1
        # 4: F2
        curr_id = 5
        for page_stream in self.pages:
            page_id = curr_id
            stream_id = curr_id + 1
            curr_id += 2

            page_obj_ids.append(page_id)
            page_dict = f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /MediaBox [0 0 595.28 841.89] /Contents {stream_id} 0 R >>".encode("ascii")
            
            stream_bytes = page_stream.encode("latin-1", "replace")
            stream_obj = f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii") + stream_bytes + b"\nendstream"

            content_objects.append((page_id, page_dict))
            content_objects.append((stream_id, stream_obj))

        # Build Obj 2: Pages
        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        pages_dict = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_obj_ids)} >>".encode("ascii")

        all_objs = {
            1: objects[0],
            2: pages_dict,
            3: objects[1],
            4: objects[2],
        }
        for oid, obytes in content_objects:
            all_objs[oid] = obytes

        # Write output PDF
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        
        xref_offsets = {}
        for oid in range(1, len(all_objs) + 1):
            xref_offsets[oid] = out.tell()
            out.write(f"{oid} 0 obj\n".encode("ascii"))
            out.write(all_objs[oid])
            out.write(b"\nendobj\n")

        xref_start = out.tell()
        out.write(f"xref\n0 {len(all_objs) + 1}\n".encode("ascii"))
        out.write(b"0000000000 65535 f \n")
        for oid in range(1, len(all_objs) + 1):
            out.write(f"{xref_offsets[oid]:010d} 00000 n \n".encode("ascii"))

        out.write(b"trailer\n")
        out.write(f"<< /Size {len(all_objs) + 1} /Root 1 0 R >>\n".encode("ascii"))
        out.write(b"startxref\n")
        out.write(f"{xref_start}\n%%EOF\n".encode("ascii"))

        return out.getvalue()

