"""
agents/report_exporter.py — Export operation reports to PDF and HTML.
Uses only stdlib + optional reportlab. Falls back to HTML if reportlab unavailable.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def export_html(report_data: dict, output_path: str) -> str:
    """Generate a professional HTML report from the API response data."""
    r = report_data
    cycles = r.get("cycles", [])
    total_lives = r.get("total_lives_saved", 0) or 0
    audit_valid = r.get("audit_chain_valid", False)

    cycle_rows = ""
    for c in cycles:
        zones_html = ""
        for z in c.get("priority_zones", [])[:5]:
            vuln = "⚠️" if z.get("has_vulnerable_populations") else ""
            zones_html += f"""
            <tr>
              <td>{z.get('name','—')}</td>
              <td>{z.get('priority_score',0):.2f}</td>
              <td>{z.get('population_at_risk',0):,}</td>
              <td>{vuln}</td>
            </tr>"""

        chaos = c.get("chaos_event", {})
        chaos_html = ""
        if chaos.get("event_type", "none") != "none":
            chaos_html = f"""
            <div class="chaos-box">
              ⚡ <strong>{chaos.get('event_type','').upper()}</strong>
              ×{chaos.get('severity_multiplier',1):.1f} —
              {chaos.get('description','')}
            </div>"""

        cycle_rows += f"""
        <div class="cycle-card">
          <div class="cycle-header">Cycle {c.get('cycle_num','?')} — Confidence: {c.get('avg_confidence',0)*100:.0f}% — Lives Saved: {c.get('lives_saved_estimate',0):,}</div>
          {chaos_html}
          <table class="zone-table">
            <thead><tr><th>Zone</th><th>Score</th><th>Population</th><th>Vulnerable</th></tr></thead>
            <tbody>{zones_html}</tbody>
          </table>
          <div class="pub-msg">📡 {c.get('public_message','')[:400]}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Disaster Response Report — {r.get('location','')}</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#222;margin:0;padding:20px}}
  .header{{background:linear-gradient(135deg,#cc0000,#ff4444);color:white;padding:30px;border-radius:8px;margin-bottom:20px}}
  .header h1{{margin:0;font-size:1.8rem;letter-spacing:2px}}
  .header p{{margin:4px 0;opacity:.9;font-size:.9rem}}
  .meta-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
  .meta-card{{background:white;border-radius:6px;padding:16px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  .meta-card .val{{font-size:1.8rem;font-weight:bold;color:#cc0000}}
  .meta-card .lbl{{font-size:.75rem;color:#666;text-transform:uppercase;letter-spacing:1px}}
  .section{{background:white;border-radius:6px;padding:20px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  .section h2{{margin:0 0 12px;font-size:1rem;color:#cc0000;text-transform:uppercase;letter-spacing:2px;border-bottom:2px solid #ffeeee;padding-bottom:8px}}
  .cycle-card{{border:1px solid #eee;border-radius:6px;padding:14px;margin-bottom:12px}}
  .cycle-header{{font-weight:bold;color:#333;margin-bottom:8px;font-size:.9rem}}
  .chaos-box{{background:#fff3f3;border:1px solid #ffcccc;border-radius:4px;padding:8px;margin:8px 0;font-size:.8rem;color:#cc0000}}
  .zone-table{{width:100%;border-collapse:collapse;font-size:.8rem;margin:8px 0}}
  .zone-table th{{background:#f8f8f8;padding:6px 10px;text-align:left;font-size:.7rem;text-transform:uppercase;color:#666}}
  .zone-table td{{padding:5px 10px;border-bottom:1px solid #f0f0f0}}
  .pub-msg{{font-size:.78rem;color:#555;background:#f9f9f9;padding:8px;border-radius:4px;margin-top:8px;line-height:1.5}}
  .audit{{font-size:.75rem;color:#666;word-break:break-all}}
  .audit-ok{{color:#00aa44;font-weight:bold}}
  .audit-fail{{color:#cc0000;font-weight:bold}}
  .lives-big{{font-size:3rem;font-weight:900;color:#00aa44;text-align:center;padding:20px}}
  @media print{{body{{background:white}}}}
</style>
</head>
<body>
<div class="header">
  <h1>🚨 DISASTER RESPONSE OPERATION REPORT</h1>
  <p>{r.get('disaster_type','').upper()} — {r.get('location','')} — Severity {r.get('severity','')}/10</p>
  <p>Generated: {r.get('generated_at','')[:19].replace('T',' ')} UTC | Session: {r.get('session_token','')[:16]}...</p>
</div>

<div class="meta-grid">
  <div class="meta-card"><div class="val">{r.get('severity','')}/10</div><div class="lbl">Severity</div></div>
  <div class="meta-card"><div class="val">{r.get('total_cycles','')}</div><div class="lbl">Cycles Run</div></div>
  <div class="meta-card"><div class="val" style="color:#00aa44">{total_lives:,}</div><div class="lbl">Lives Saved</div></div>
  <div class="meta-card"><div class="val" style="color:{'#00aa44' if audit_valid else '#cc0000'}">{'✓' if audit_valid else '✗'}</div><div class="lbl">Audit Valid</div></div>
</div>

<div class="section">
  <h2>💚 Total Lives Saved</h2>
  <div class="lives-big">{total_lives:,}</div>
</div>

<div class="section">
  <h2>🔄 Cycle Summaries</h2>
  {cycle_rows}
</div>

<div class="section">
  <h2>🔐 Audit Chain</h2>
  <p class="audit">Hash: {r.get('audit_chain_hash','—')}</p>
  <p>Status: <span class="{'audit-ok' if audit_valid else 'audit-fail'}">{'✓ VERIFIED — Chain intact, no tampering detected' if audit_valid else '✗ INVALID — Chain may have been tampered'}</span></p>
</div>

{'<div class="section"><h2>⚖️ Agent Disagreements</h2><p style="font-size:.8rem;color:#555;line-height:1.6">' + r.get('disagreement_summary','') + '</p></div>' if r.get('disagreement_summary') else ''}

<div style="text-align:center;color:#999;font-size:.7rem;margin-top:20px;padding:10px;border-top:1px solid #eee">
  Disaster Response AI System v2.0 — Powered by Groq LLM + RAG + Multi-Agent Coordination
</div>
</body>
</html>"""

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    return str(path)


def export_pdf(report_data: dict, output_path: str) -> str:
    """
    Generate PDF report. Uses reportlab if available, otherwise HTML.
    Returns path to the generated file.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        r = report_data
        cycles = r.get("cycles", [])
        total_lives = r.get("total_lives_saved", 0) or 0
        audit_valid = r.get("audit_chain_valid", False)

        pdf_path = output_path.replace(".html", ".pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                 leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        RED = colors.HexColor("#cc0000")
        GREEN = colors.HexColor("#00aa44")

        title_style = ParagraphStyle("title", parent=styles["Title"],
                                      textColor=RED, fontSize=18, spaceAfter=6)
        h2_style = ParagraphStyle("h2", parent=styles["Heading2"],
                                   textColor=RED, fontSize=11, spaceAfter=4)
        body_style = ParagraphStyle("body", parent=styles["Normal"],
                                     fontSize=9, spaceAfter=3)

        story = []
        story.append(Paragraph("🚨 DISASTER RESPONSE OPERATION REPORT", title_style))
        story.append(Paragraph(
            f"{r.get('disaster_type','').upper()} — {r.get('location','')} — "
            f"Severity {r.get('severity','')}/10", styles["Heading3"]
        ))
        story.append(Paragraph(
            f"Generated: {r.get('generated_at','')[:19].replace('T',' ')} UTC | "
            f"Session: {r.get('session_token','')[:16]}...", body_style
        ))
        story.append(HRFlowable(width="100%", color=RED, thickness=2, spaceAfter=10))

        # Summary table
        summary_data = [
            ["Metric", "Value"],
            ["Disaster Type", r.get("disaster_type", "").upper()],
            ["Location", r.get("location", "")],
            ["Severity", f"{r.get('severity', '')}/10"],
            ["Cycles Completed", str(r.get("total_cycles", ""))],
            ["Total Lives Saved", f"{total_lives:,}"],
            ["Audit Chain", "✓ VERIFIED" if audit_valid else "✗ INVALID"],
        ]
        t = Table(summary_data, colWidths=[5*cm, 10*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff8f8")]),
            ("TEXTCOLOR", (1, 6), (1, 6), GREEN if audit_valid else RED),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        # Cycles
        story.append(Paragraph("CYCLE SUMMARIES", h2_style))
        for c in cycles:
            story.append(Paragraph(
                f"<b>Cycle {c.get('cycle_num','?')}</b> — "
                f"Confidence: {c.get('avg_confidence',0)*100:.0f}% — "
                f"Lives Saved: {c.get('lives_saved_estimate',0):,}",
                body_style
            ))
            chaos = c.get("chaos_event", {})
            if chaos.get("event_type", "none") != "none":
                story.append(Paragraph(
                    f"⚡ Chaos: {chaos.get('event_type','').upper()} ×{chaos.get('severity_multiplier',1):.1f} — "
                    f"{chaos.get('description','')}",
                    ParagraphStyle("chaos", parent=body_style, textColor=RED)
                ))
            pub = c.get("public_message", "")
            if pub:
                story.append(Paragraph(f"📡 {pub[:300]}", body_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        return pdf_path

    except ImportError:
        # reportlab not installed — fall back to HTML
        html_path = output_path.replace(".pdf", ".html")
        return export_html(report_data, html_path)
