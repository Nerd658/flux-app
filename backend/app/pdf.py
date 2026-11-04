"""PDF de la demande validée : mise en page soignée, fidèle aux rubriques du formulaire officiel.

Structure : bandeau (titre, référence, statut) → informations (demandeur, manager, direction, période)
→ tableau des flux (colonnes du modèle) → bloc des validations signées → pied de page (sceau, pagination).
"""
from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas import RequestDetail

# Palette
ORANGE = colors.HexColor("#FF7900")
ORANGE_PALE = colors.HexColor("#FFF1E5")
BLACK = colors.black
INK_2 = colors.HexColor("#595959")
LINE = colors.HexColor("#DDDDDD")
ZEBRA = colors.HexColor("#FAFAFA")
GREEN = colors.HexColor("#16803C")
GREEN_PALE = colors.HexColor("#E8F7ED")
RED = colors.HexColor("#B42318")
RED_PALE = colors.HexColor("#FBECE8")

PAGE = landscape(A4)
MARGIN = 14 * mm
HEADER_H = 22 * mm
WIDTH = PAGE[0] - 2 * MARGIN

# Styles de texte
_base = ParagraphStyle("base", fontName="Helvetica", fontSize=8, leading=10, textColor=BLACK)
S_CELL = _base
S_CELL_B = ParagraphStyle("cellb", parent=_base, fontName="Helvetica-Bold")
S_HEAD = ParagraphStyle("head", parent=_base, fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
S_HEAD_DARK = ParagraphStyle("headdark", parent=S_HEAD, textColor=BLACK)    # texte noir sur fond orange
S_SUB = ParagraphStyle("sub", parent=_base, fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=INK_2, alignment=1)
S_LABEL = ParagraphStyle("label", parent=_base, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=INK_2)
S_VALUE = ParagraphStyle("value", parent=_base, fontName="Helvetica-Bold", fontSize=10.5, leading=13)
S_META = ParagraphStyle("meta", parent=_base, fontSize=8.5, leading=11, textColor=INK_2)
S_SECTION = ParagraphStyle("section", parent=_base, fontName="Helvetica-Bold", fontSize=12, leading=15)
S_SMALL = ParagraphStyle("small", parent=_base, fontSize=6.5, leading=8.5, textColor=INK_2)


def P(text, style=S_CELL) -> Paragraph:
    # Échappement obligatoire : Paragraph interprète le balisage (anti-injection de markup)
    return Paragraph(escape(str(text if text not in (None, "") else "—")), style)


def _fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)               # MySQL renvoie une date naïve, stockée en UTC
    return dt.astimezone(timezone.utc).strftime("%d/%m/%Y à %H:%M (GMT)")


def _section_title(text: str) -> Table:
    """Titre de section précédé d'un repère orange."""
    t = Table([["", Paragraph(escape(text), S_SECTION)]], colWidths=[3 * mm, WIDTH - 3 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ORANGE),
        ("LEFTPADDING", (1, 0), (1, 0), 7), ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _info_card(label: str, value: str, lines: list[str]) -> list:
    return [Paragraph(escape(label), S_LABEL), Spacer(1, 2), P(value, S_VALUE), Spacer(1, 2),
            *[P(line, S_META) for line in lines]]


# ---------- Canevas : bandeau et pied de page sur chaque page, pagination « x / n » ----------

def _make_canvas(req: RequestDetail):
    generated = _fmt_dt(datetime.now(timezone.utc))

    class PageCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int):
            w, h = PAGE
            # Bandeau noir + repère orange
            self.setFillColor(BLACK)
            self.rect(0, h - HEADER_H, w, HEADER_H, stroke=0, fill=1)
            self.setFillColor(ORANGE)
            self.rect(MARGIN, h - HEADER_H + 6 * mm, 10 * mm, 10 * mm, stroke=0, fill=1)
            self.setFillColor(BLACK)
            self.setStrokeColor(BLACK)
            self.setLineWidth(1.4)
            cy = h - HEADER_H + 11 * mm
            self.circle(MARGIN + 2.6 * mm, cy, 0.9 * mm, stroke=0, fill=1)
            self.circle(MARGIN + 7.4 * mm, cy, 0.9 * mm, stroke=0, fill=1)
            self.line(MARGIN + 3.6 * mm, cy, MARGIN + 6.4 * mm, cy)
            # Titre
            self.setFillColor(colors.white)
            self.setFont("Helvetica-Bold", 15)
            self.drawString(MARGIN + 14 * mm, h - HEADER_H + 11.6 * mm, "DEMANDE D'OUVERTURE DE FLUX")
            self.setFont("Helvetica", 8.5)
            self.setFillColor(colors.HexColor("#BDBDBD"))
            self.drawString(MARGIN + 14 * mm, h - HEADER_H + 6.6 * mm, f"Type d'ouverture : {req.flux_type}")
            # Référence et statut à droite
            self.setFillColor(colors.white)
            self.setFont("Helvetica-Bold", 13)
            self.drawRightString(w - MARGIN, h - HEADER_H + 11.6 * mm, req.reference or "")
            badge_w = 24 * mm
            self.setFillColor(ORANGE)
            self.rect(w - MARGIN - badge_w, h - HEADER_H + 4.2 * mm, badge_w, 5.2 * mm, stroke=0, fill=1)
            self.setFillColor(BLACK)
            self.setFont("Helvetica-Bold", 7.5)
            self.drawCentredString(w - MARGIN - badge_w / 2, h - HEADER_H + 5.9 * mm, "VALIDÉE")

            # Pied de page
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(MARGIN, 11 * mm, w - MARGIN, 11 * mm)
            self.setFont("Helvetica", 6.5)
            self.setFillColor(INK_2)
            ticket_info = f"  ·  Ticket Oline : {req.ticket_ref}" if getattr(req, "ticket_ref", None) else ""
            self.drawString(MARGIN, 7 * mm, f"Sceau SHA-256 : {req.content_hash}{ticket_info}")
            self.drawRightString(w - MARGIN, 7 * mm, f"{req.reference}  ·  Vérifiable sur /verifier  ·  Page {self._pageNumber} / {total}")

    return PageCanvas


# ---------- Construction du document ----------

def build_pdf(req: RequestDetail) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=HEADER_H + 7 * mm, bottomMargin=16 * mm,
        title=f"Demande d'ouverture de flux {req.reference}", author="Application Ouverture de flux",
        subject="Demande d'ouverture de flux validée",
    )
    story = []

    # 1. Informations générales : quatre cartes
    d, m = req.demandeur, req.manager
    tmp = req.periode.value == "temporaire"
    if tmp:
        days = (req.date_fin - req.date_debut).days + 1
        periode_val, periode_lines = f"Du {_fmt_date(req.date_debut)} au {_fmt_date(req.date_fin)}", [f"Temporaire, {days} jours"]
    else:
        periode_val, periode_lines = f"À partir du {_fmt_date(req.date_debut)}", ["Permanente, sans date de fin"]
    statut_labels = {
        "employe": "Employé",
        "prestataire": "Prestataire",
        "stagiaire": "Stagiaire",
    }
    statut_val = d.statut_pro.value if getattr(d, "statut_pro", None) else ""
    statut_str = statut_labels.get(statut_val, "Employé")
    demandeur_lines = [d.email]
    if d.telephone:
        demandeur_lines.append(d.telephone)
    demandeur_lines.append(f"Statut : {statut_str}")

    mgr_lines = [m.email]
    if m.telephone:
        mgr_lines.append(m.telephone)

    direction_sublines = []
    if getattr(req, "direction", None):
        direction_sublines.append(f"Direction : {req.direction}")
    direction_sublines.append(f"Soumise le {_fmt_dt(req.created_at)}")

    cards = [
        _info_card("DEMANDEUR", f"{d.prenom} {d.nom.upper()}", demandeur_lines),
        _info_card("MANAGER", f"{m.prenom} {m.nom.upper()}", mgr_lines),
        _info_card("DÉPARTEMENT", req.departement, direction_sublines),
        _info_card("PÉRIODE SOUHAITÉE", periode_val, periode_lines),
    ]
    info = Table([cards], colWidths=[WIDTH / 4] * 4)
    info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (1, 0), (-1, 0), 0.6, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, ORANGE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [info, Spacer(1, 7 * mm)]

    # 2. Tableau des flux : colonnes du formulaire officiel
    story += [_section_title(f"Flux demandés ({len(req.lines)})"), Spacer(1, 3 * mm)]
    header1 = [P("N°", S_HEAD), P("SOURCE", S_HEAD), "", "", "", P("DESTINATION", S_HEAD_DARK), "", "", "", "", "",
               P("TYPE D'ACCÈS", S_HEAD), P("JUSTIFICATION", S_HEAD)]
    header2 = ["", *[P(h, S_SUB) for h in ("IP", "Zone", "Pays", "Application / URL",
                                          "IP", "Port(s)", "Protocole", "Zone", "Pays", "Application / URL")], "", ""]
    rows = [header1, header2]
    for line in req.lines:
        rows.append([
            P(line.numero, S_CELL_B), P(line.src_ip, S_CELL_B), P(line.src_zone), P(line.src_pays), P(line.src_app),
            P(line.dst_ip, S_CELL_B), P(line.dst_ports or "—"), P(line.protocole, S_CELL_B), P(line.dst_zone),
            P(line.dst_pays), P(line.dst_app), P(line.type_acces), P(line.justification),
        ])
    ratios = [7, 24, 15, 17, 24, 24, 16, 14, 15, 17, 24, 22, 35]
    unit = WIDTH / sum(ratios)
    style = [
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (4, 0)), ("SPAN", (5, 0), (10, 0)),
        ("SPAN", (11, 0), (11, 1)), ("SPAN", (12, 0), (12, 1)),
        # En-têtes : source en noir, destination en orange (comme dans l'application)
        # Les cellules fusionnées sur deux lignes (N°, type d'accès, justification) sont colorées sur toute leur hauteur
        ("BACKGROUND", (0, 0), (0, 1), BLACK), ("BACKGROUND", (1, 0), (4, 0), BLACK), ("BACKGROUND", (11, 0), (12, 1), BLACK),
        ("BACKGROUND", (5, 0), (10, 0), ORANGE),
        ("BACKGROUND", (1, 1), (10, 1), colors.HexColor("#F2F2F2")),
        ("LINEBELOW", (0, 1), (-1, 1), 1, BLACK),
        ("LINEBELOW", (0, 2), (-1, -1), 0.4, LINE),
        ("LINEAFTER", (4, 2), (4, -1), 0.8, colors.HexColor("#BDBDBD")),     # séparation source | destination
        ("LINEAFTER", (10, 2), (10, -1), 0.8, colors.HexColor("#BDBDBD")),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("VALIGN", (0, 2), (-1, -1), "TOP"),
        ("ALIGN", (0, 2), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(2, len(rows)):
        if i % 2 == 1:
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    flows = Table(rows, colWidths=[r * unit for r in ratios], repeatRows=2)
    flows.setStyle(TableStyle(style))
    story += [flows, Spacer(1, 8 * mm)]

    # 3. Validations : un bloc de signature par niveau (Manager, Technique, RSSI)
    sig_cells = []
    level_titles = {
        1: "VALIDATION 1 : MANAGER",
        2: "VALIDATION 2 : TECHNIQUE (SÉCURITÉ)",
        3: "VALIDATION 3 : RSSI (FINALE)",
    }
    for v in req.validations:
        ok = v.decision.value == "validee"
        stamp = Table([[Paragraph(f'<font color="{(GREEN if ok else RED).hexval()}"><b>{"VALIDÉ" if ok else "REFUSÉ"}</b></font>',
                                  ParagraphStyle("st", parent=_base, fontSize=9, alignment=1))]],
                      colWidths=[20 * mm], rowHeights=[7 * mm])
        stamp.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1.2, GREEN if ok else RED),
            ("BACKGROUND", (0, 0), (-1, -1), GREEN_PALE if ok else RED_PALE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        title = level_titles.get(v.niveau, f"VALIDATION NIVEAU {v.niveau}")
        left = [Paragraph(title, S_LABEL), Spacer(1, 2), P(v.validateur, S_VALUE), Spacer(1, 1),
                P(f"Le {_fmt_dt(v.decided_at)}", S_META), Spacer(1, 3),
                P(f"Clé : {v.key_fingerprint[:24]}…", S_SMALL)]
        block = Table([[left, stamp]], colWidths=[WIDTH / 3 - 24 * mm, 22 * mm])
        block.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        sig_cells.append(block)
    while len(sig_cells) < 3:
        sig_cells.append("")
    sigs = Table([sig_cells], colWidths=[WIDTH / 3] * 3)
    sigs.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (1, 0), (-1, 0), 0.6, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    note = P("Chaque validation est signée électroniquement (Ed25519). Toute modification du contenu après signature "
             "rompt le sceau ; la vérification est disponible dans l'application à partir de la référence.", S_SMALL)
    story.append(KeepTogether([_section_title("Validations"), Spacer(1, 3 * mm), sigs, Spacer(1, 3 * mm), note]))

    doc.build(story, canvasmaker=_make_canvas(req))
    return buf.getvalue()
