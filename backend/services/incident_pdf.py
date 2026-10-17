"""
Cyber Hazard Lab - Pure-Python SOC Incident Report PDF Generator
Produces standard PDF 1.4 documents without requiring third-party libraries.
"""

import time
import textwrap


def _escape_pdf(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    # Replace backslash and parentheses
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Keep printable ASCII, replace any non-ascii safely
    clean = []
    for ch in text:
        code = ord(ch)
        if 32 <= code < 127:
            clean.append(ch)
        elif ch in "\r\n\t":
            clean.append(" ")
        else:
            clean.append("?")
    return "".join(clean)


def generate_incident_pdf(incident: dict, lab_name: str = "Cyber Hazard Lab") -> bytes:
    """
    Generates a professionally formatted PDF report for a SOC incident.
    """
    title = incident.get("title", "Untitled Incident Report")
    inc_id = incident.get("id", "INC-UNKNOWN")
    severity = str(incident.get("severity", "MEDIUM")).upper()
    status = str(incident.get("status", "OPEN")).upper()
    timestamp = incident.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%SZ"))
    scope = incident.get("scope", "Enterprise Network Infrastructure")
    notes = incident.get("notes", "No detailed analysis provided.")
    evidence = incident.get("chained_evidence", []) or []
    display_lab = str(lab_name or "Cyber Hazard Lab").strip()

    # Page setup (A4: 595 x 842 points)
    width = 595
    height = 842
    left_margin = 40
    right_margin = 555
    content_width = right_margin - left_margin

    pages_ops = []
    current_ops = []

    def start_new_page():
        nonlocal current_ops
        if current_ops:
            pages_ops.append("\n".join(current_ops))
        current_ops = []
        # Header banner
        current_ops.append("0.05 0.08 0.14 rg")
        current_ops.append(f"{left_margin} 770 {content_width} 45 re f")
        current_ops.append("0.0 0.85 1.0 rg")
        current_ops.append(f"{left_margin} 767 {content_width} 3 re f")

        current_ops.append("BT")
        current_ops.append("/F2 14 Tf")
        current_ops.append("1 1 1 rg")
        current_ops.append(f"{left_margin + 12} 788 Td")
        current_ops.append(f"({_escape_pdf(display_lab.upper() + '  |  SECURITY OPERATIONS CENTER')}) Tj")
        current_ops.append("ET")

        # Footer
        current_ops.append("0.5 0.55 0.6 rg")
        current_ops.append(f"{left_margin} 45 {content_width} 0.5 re f")
        current_ops.append("BT")
        current_ops.append("/F1 8 Tf")
        current_ops.append(f"{left_margin} 32 Td")
        current_ops.append(f"({_escape_pdf('CONFIDENTIAL  -  SOC INCIDENT CASE FILE ' + inc_id + '  -  ' + display_lab.upper())}) Tj")
        current_ops.append("ET")

    start_new_page()

    y = 740

    sev_colors = {
        "CRITICAL": "0.85 0.15 0.15",
        "HIGH": "0.95 0.45 0.1",
        "MEDIUM": "0.85 0.7 0.1",
        "LOW": "0.15 0.65 0.85"
    }
    sev_col = sev_colors.get(severity, "0.5 0.5 0.5")

    # Document Title
    current_ops.append("BT")
    current_ops.append("/F2 16 Tf")
    current_ops.append("0.1 0.15 0.25 rg")
    current_ops.append(f"{left_margin} {y} Td")
    current_ops.append(f"({_escape_pdf('INCIDENT REPORT: ' + title)}) Tj")
    current_ops.append("ET")
    y -= 26

    # Metadata Box
    box_height = 84
    box_y = y - box_height
    current_ops.append("0.96 0.97 0.98 rg")
    current_ops.append(f"{left_margin} {box_y} {content_width} {box_height} re f")
    current_ops.append("0.8 0.85 0.9 RG")
    current_ops.append("1 w")
    current_ops.append(f"{left_margin} {box_y} {content_width} {box_height} re s")

    current_ops.append("BT")
    current_ops.append("/F2 9 Tf")
    current_ops.append("0.2 0.25 0.35 rg")

    # Col 1
    current_ops.append(f"{left_margin + 12} {y - 18} Td")
    current_ops.append(f"({_escape_pdf('Incident ID: ')}) Tj")
    current_ops.append("/F1 9 Tf")
    current_ops.append(f"({_escape_pdf(inc_id)}) Tj")

    current_ops.append("/F2 9 Tf")
    current_ops.append(f"0 -16 Td")
    current_ops.append(f"({_escape_pdf('Lab / Org: ')}) Tj")
    current_ops.append("/F1 9 Tf")
    current_ops.append(f"({_escape_pdf(display_lab)}) Tj")

    current_ops.append("/F2 9 Tf")
    current_ops.append(f"0 -16 Td")
    current_ops.append(f"({_escape_pdf('Logged Time: ')}) Tj")
    current_ops.append("/F1 9 Tf")
    current_ops.append(f"({_escape_pdf(str(timestamp))}) Tj")

    current_ops.append("/F2 9 Tf")
    current_ops.append(f"0 -16 Td")
    current_ops.append(f"({_escape_pdf('Target Scope: ')}) Tj")
    current_ops.append("/F1 9 Tf")
    current_ops.append(f"({_escape_pdf(str(scope))}) Tj")

    # Col 2
    current_ops.append("/F2 9 Tf")
    current_ops.append(f"280 48 Td")
    current_ops.append(f"({_escape_pdf('Severity: ')}) Tj")
    current_ops.append(f"{sev_col} rg")
    current_ops.append(f"({_escape_pdf(severity)}) Tj")

    current_ops.append("0.2 0.25 0.35 rg")
    current_ops.append(f"0 -16 Td")
    current_ops.append(f"({_escape_pdf('Status: ')}) Tj")
    current_ops.append("0.0 0.5 0.8 rg")
    current_ops.append(f"({_escape_pdf(status)}) Tj")

    current_ops.append("0.2 0.25 0.35 rg")
    current_ops.append(f"0 -16 Td")
    current_ops.append(f"({_escape_pdf('Chained Evidence: ')}) Tj")
    current_ops.append("/F1 9 Tf")
    current_ops.append(f"({_escape_pdf(str(len(evidence)) + ' events')}) Tj")
    current_ops.append("ET")

    y = box_y - 25

    # Section 1: Executive Summary & Analysis
    current_ops.append("0.1 0.15 0.25 rg")
    current_ops.append(f"{left_margin} {y} {content_width} 1.5 re f")
    y -= 14
    current_ops.append("BT")
    current_ops.append("/F2 11 Tf")
    current_ops.append("0.1 0.15 0.25 rg")
    current_ops.append(f"{left_margin} {y} Td")
    current_ops.append(f"({_escape_pdf('1. INVESTIGATION SUMMARY & FINDINGS')}) Tj")
    current_ops.append("ET")
    y -= 18

    paragraphs = str(notes).split("\n")
    current_ops.append("BT")
    current_ops.append("/F1 9.5 Tf")
    current_ops.append("0.15 0.2 0.25 rg")

    first_text = True
    for p in paragraphs:
        lines = textwrap.wrap(p, width=88) or [""]
        for line in lines:
            if y < 75:
                current_ops.append("ET")
                start_new_page()
                y = 740
                current_ops.append("BT")
                current_ops.append("/F1 9.5 Tf")
                current_ops.append("0.15 0.2 0.25 rg")
                current_ops.append(f"{left_margin} {y} Td")
                first_text = False
            elif first_text:
                current_ops.append(f"{left_margin} {y} Td")
                first_text = False
            else:
                current_ops.append(f"0 -13 Td")
            current_ops.append(f"({_escape_pdf(line)}) Tj")
            y -= 13
        y -= 4
    current_ops.append("ET")
    y -= 15

    # Section 2: Chained Evidence Timeline
    if y < 140:
        start_new_page()
        y = 740

    current_ops.append("0.1 0.15 0.25 rg")
    current_ops.append(f"{left_margin} {y} {content_width} 1.5 re f")
    y -= 14
    current_ops.append("BT")
    current_ops.append("/F2 11 Tf")
    current_ops.append("0.1 0.15 0.25 rg")
    current_ops.append(f"{left_margin} {y} Td")
    current_ops.append(f"({_escape_pdf('2. CHAINED EVIDENCE TIMELINE (' + str(len(evidence)) + ' EVENTS)')}) Tj")
    current_ops.append("ET")
    y -= 18

    if not evidence:
        current_ops.append("BT")
        current_ops.append("/F1 9 Tf")
        current_ops.append("0.5 0.55 0.6 rg")
        current_ops.append(f"{left_margin} {y} Td")
        current_ops.append(f"({_escape_pdf('No specific SIEM telemetry events chained to this incident report.')}) Tj")
        current_ops.append("ET")
        y -= 20
    else:
        th_h = 18
        current_ops.append("0.15 0.2 0.3 rg")
        current_ops.append(f"{left_margin} {y - th_h} {content_width} {th_h} re f")
        current_ops.append("BT")
        current_ops.append("/F2 8.5 Tf")
        current_ops.append("1 1 1 rg")
        current_ops.append(f"{left_margin + 6} {y - 13} Td")
        current_ops.append(f"({_escape_pdf('TIMESTAMP')}) Tj")
        current_ops.append(f"90 0 Td")
        current_ops.append(f"({_escape_pdf('SEVERITY')}) Tj")
        current_ops.append(f"65 0 Td")
        current_ops.append(f"({_escape_pdf('DETECTION RULE')}) Tj")
        current_ops.append(f"185 0 Td")
        current_ops.append(f"({_escape_pdf('SOURCE -> DESTINATION')}) Tj")
        current_ops.append("ET")
        y -= th_h

        for i, ev in enumerate(evidence):
            row_h = 16
            if y < 70:
                start_new_page()
                y = 740
                current_ops.append("0.15 0.2 0.3 rg")
                current_ops.append(f"{left_margin} {y - th_h} {content_width} {th_h} re f")
                current_ops.append("BT")
                current_ops.append("/F2 8.5 Tf")
                current_ops.append("1 1 1 rg")
                current_ops.append(f"{left_margin + 6} {y - 13} Td")
                current_ops.append(f"({_escape_pdf('TIMESTAMP')}) Tj")
                current_ops.append(f"90 0 Td")
                current_ops.append(f"({_escape_pdf('SEVERITY')}) Tj")
                current_ops.append(f"65 0 Td")
                current_ops.append(f"({_escape_pdf('DETECTION RULE')}) Tj")
                current_ops.append(f"185 0 Td")
                current_ops.append(f"({_escape_pdf('SOURCE -> DESTINATION')}) Tj")
                current_ops.append("ET")
                y -= th_h

            bg = "0.97 0.98 0.99" if i % 2 == 0 else "1 1 1"
            current_ops.append(f"{bg} rg")
            current_ops.append(f"{left_margin} {y - row_h} {content_width} {row_h} re f")
            current_ops.append("0.88 0.9 0.92 RG")
            current_ops.append("0.5 w")
            current_ops.append(f"{left_margin} {y - row_h} {content_width} {row_h} re s")

            ev_time = str(ev.get("timestamp", ""))[-8:]
            ev_sev = str(ev.get("severity", "LOW")).upper()
            ev_rule = str(ev.get("rule_name", ev.get("rule_id", "Detection Alert")))[:32]
            ev_flow = f"{ev.get('source', '-')} -> {ev.get('destination', '-')}"[:28]

            e_col = sev_colors.get(ev_sev, "0.3 0.3 0.3")

            current_ops.append("BT")
            current_ops.append("/F1 8 Tf")
            current_ops.append("0.2 0.25 0.3 rg")
            current_ops.append(f"{left_margin + 6} {y - 11} Td")
            current_ops.append(f"({_escape_pdf(ev_time)}) Tj")

            current_ops.append(f"{e_col} rg")
            current_ops.append("/F2 8 Tf")
            current_ops.append("90 0 Td")
            current_ops.append(f"({_escape_pdf(ev_sev)}) Tj")

            current_ops.append("0.2 0.25 0.3 rg")
            current_ops.append("/F1 8 Tf")
            current_ops.append("65 0 Td")
            current_ops.append(f"({_escape_pdf(ev_rule)}) Tj")

            current_ops.append("185 0 Td")
            current_ops.append(f"({_escape_pdf(ev_flow)}) Tj")
            current_ops.append("ET")
            y -= row_h

    if current_ops:
        pages_ops.append("\n".join(current_ops))

    num_pages = len(pages_ops)
    objects = []

    # 1: Catalog
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")

    # 2: Pages
    page_ids = [str(6 + i * 2) for i in range(num_pages)]
    kids_str = " ".join([f"{pid} 0 R" for pid in page_ids])
    objects.append(f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>")

    # 3: Fonts
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    for i in range(num_pages):
        content_obj_num = 7 + i * 2
        page_dict = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> /Contents {content_obj_num} 0 R >>"
        objects.append(page_dict)

        c_stream = pages_ops[i].encode("latin-1")
        content_dict = f"<< /Length {len(c_stream)} >>\nstream\n{pages_ops[i]}\nendstream"
        objects.append(content_dict)

    output = bytearray()
    output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = []
    for i, obj in enumerate(objects):
        obj_num = i + 1
        offsets.append(len(output))
        if isinstance(obj, str):
            obj_bytes = f"{obj_num} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        else:
            obj_bytes = f"{obj_num} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
        output.extend(obj_bytes)

    xref_offset = len(output)
    total_objs = len(objects) + 1
    output.extend(f"xref\n0 {total_objs}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets:
        output.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    output.extend(trailer.encode("latin-1"))

    return bytes(output)
