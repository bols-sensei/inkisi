from io import BytesIO
import os, zipfile, secrets
from openpyxl import Workbook
from app.services.safe import pdf_text, append_text_row
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
import qrcode
from app.models import Invitation, Event, ConferenceRegistration
from app.services.qr import build_payload, qr_filename

def qr_png(payload: str) -> bytes:
    img=qrcode.make(payload)
    out=BytesIO(); img.save(out, format='PNG'); return out.getvalue()

def create_designer_zip(event: Event, invitations: list[Invitation]) -> bytes:
    out=BytesIO()
    # FIX: produire chaque QR une seule fois puis réutiliser ses octets pour le PDF et le ZIP.
    qr_images = {inv.badge_reference: qr_png(build_payload(event.id, inv.badge_reference)) for inv in invitations}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        # Excel manifest
        wb=Workbook(); ws=wb.active; ws.title='Invitations'
        append_text_row(ws,['Événement (ID)','Ordre','Référence','Nom invité / groupe','Type','Nombre autorisé','Table','Fichier QR'])
        for inv in invitations:
            append_text_row(ws,[event.id,inv.sequence_no,inv.badge_reference,inv.guest_name,inv.invitation_type,inv.quota,inv.table_name,qr_filename(event.id,inv.badge_reference)])
        x=BytesIO(); wb.save(x); z.writestr('manifest_invitations.xlsx', x.getvalue())
        # PDF reference
        pdf=BytesIO(); doc=SimpleDocTemplate(pdf,pagesize=landscape(A4),rightMargin=10*mm,leftMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
        styles=getSampleStyleSheet(); title=ParagraphStyle('TitleSmall', parent=styles['Title'], fontSize=16, leading=19)
        story=[Paragraph(f'Reference invitations — {pdf_text(event.name)}',title), Paragraph(f'Evenement n° {event.id} : {pdf_text(event.name)} | Date : {pdf_text(event.event_date or "Non precisee")} | Lieu : {pdf_text(event.venue or "Non precise")}',styles['Normal']), Spacer(1,5*mm)]
        data=[['Ordre','Référence','Invité / groupe','Type','Quota','Table','QR code']]
        for inv in invitations:
            qr=qr_images[inv.badge_reference]
            img=Image(BytesIO(qr), width=17*mm, height=17*mm)
            data.append([str(inv.sequence_no),inv.badge_reference,Paragraph(pdf_text(inv.guest_name),styles['BodyText']),inv.invitation_type,str(inv.quota),inv.table_name or '—',img])
        table=Table(data, colWidths=[13*mm,25*mm,65*mm,25*mm,17*mm,22*mm,22*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17324D')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#D4DCE5')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FB')]),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,1),(-1,-1),3),('BOTTOMPADDING',(0,1),(-1,-1),3)
        ]))
        story.append(table); doc.build(story); z.writestr('reference_invitations.pdf',pdf.getvalue())
        for inv in invitations: z.writestr(qr_filename(event.id,inv.badge_reference), qr_images[inv.badge_reference])
        instructions=(f"EVENEMENT: {event.name} (n° {event.id})\n\n" "RÈGLES POUR LE DESIGNER\n" "1. Utiliser les QR codes PNG fournis sans les recréer, retoucher ou recolorer.\n" "2. La référence UUID affichée dans le PDF est la correspondance avec le fichier PNG nommé E<n° événement>_<UUID>.png. Ne mélangez jamais les dossiers de deux événements.\n" "3. Respecter strictement l'ordre de la liste. Une invitation de groupe possède un seul QR code, quel que soit son quota.\n" "4. Tester un échantillon après intégration au design et avant impression.\n" "5. Chaque QR code n'est valable que pour son événement : un QR d'un autre événement sera refusé au contrôle.\n" "6. Ne pas publier ni transmettre les QR codes à des tiers.\n")
        z.writestr('instructions_designer.txt',instructions)
    return out.getvalue()


def generate_participants_document(event: Event, registrations: list[ConferenceRegistration]) -> bytes:
    """Génère le répertoire imprimable des participants inscrits à l'événement sélectionné (PDF paysage).
    
    Exigences :
      - Tableau propre et professionnel adapté à l'impression
      - Colonnes : N°, Nom & Prénom, Adresse e-mail, Téléphone, Profession
      - Aucun programme d'événement dans ce document (répertoire strict)
      - Protection des données saisies via pdf_text() (Invariant 6)
    """
    out = BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Title'], fontSize=16, leading=20, textColor=colors.HexColor('#0b5d4b'), alignment=0)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#4a6157'))
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#10231c'))
    cell_bold = ParagraphStyle('CellBold', parent=cell_style, fontName='Helvetica-Bold')

    event_date_str = event.start_date if getattr(event, 'start_date', None) else (event.event_date or "Non précisée")
    if getattr(event, 'start_time', None) and event.start_time:
        event_date_str += f" à {event.start_time}"

    story = [
        Paragraph(f"Répertoire des participants — {pdf_text(event.name)}", title_style),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Événement n° {event.id} : <b>{pdf_text(event.name)}</b> | "
            f"Date : {pdf_text(event_date_str)} | "
            f"Lieu : {pdf_text(event.venue or 'Non précisé')} | "
            f"Total inscrits : <b>{len(registrations)}</b> participant(s)",
            meta_style
        ),
        Paragraph("Document confidentiel réservé à l’administration de l’événement.", meta_style),
        Spacer(1, 5 * mm)
    ]

    # Entêtes du tableau : Nom, Prénom, E-mail, Téléphone, Profession (et Organisation si disponible)
    data = [['N°', 'Nom & Prénom', 'Adresse e-mail', 'Numéro de téléphone', 'Profession', 'Organisation / Société', 'Statut']]
    status_map = {
        'accepted': 'Acceptée',
        'waitlist': 'Liste d’attente',
        'pending': 'En attente',
        'rejected': 'Refusée',
        'cancelled': 'Annulée'
    }

    for idx, reg in enumerate(registrations, start=1):
        full_name = reg.full_name or f"{getattr(reg, 'first_name', '')} {getattr(reg, 'last_name', '')}".strip() or "—"
        profession = getattr(reg, 'profession', '') or "—"
        org_name = getattr(reg, 'organization_name', '') or "—"
        phone = reg.phone or "—"
        email = reg.email or "—"
        st_label = status_map.get(reg.status, reg.status)

        data.append([
            str(idx),
            Paragraph(pdf_text(full_name), cell_bold),
            Paragraph(pdf_text(email), cell_style),
            Paragraph(pdf_text(phone), cell_style),
            Paragraph(pdf_text(profession), cell_style),
            Paragraph(pdf_text(org_name), cell_style),
            Paragraph(pdf_text(st_label), cell_style)
        ])

    col_widths = [12 * mm, 55 * mm, 60 * mm, 38 * mm, 42 * mm, 45 * mm, 25 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b5d4b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#D4DCE5')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F8F6')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
    ]))

    story.append(table)
    doc.build(story)
    return out.getvalue()

