"""Neutralisation des données saisies par des tiers avant export (PDF ReportLab, Excel)."""
from xml.sax.saxutils import escape


def pdf_text(value) -> str:
    """ReportLab interprète un mini-HTML dans Paragraph : `<`, `>` et `&` doivent être échappés
    (sinon erreur 500, mise en forme détournée, ou chargement de ressource via <img>)."""
    return escape("" if value is None else str(value))


def append_text_row(ws, row) -> None:
    """Ajoute une ligne en forçant les chaînes en texte : un nom commençant par « = » ne devient jamais une formule."""
    ws.append(row)
    for cell in ws[ws.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"
