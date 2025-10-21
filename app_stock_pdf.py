import os
import pandas as pd
import pdfplumber
import streamlit as st
from datetime import datetime
from fpdf import FPDF

# === Chemins ===
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RAPPORT_DIR = os.path.join(os.path.dirname(__file__), "rapports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAPPORT_DIR, exist_ok=True)

# === Fonctions utilitaires ===

def lire_pdf(path):
    """Lit un PDF et extrait les tableaux sous forme de DataFrame"""
    tables = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_table()
            if t:
                tables.append(pd.DataFrame(t[1:], columns=t[0]))
    if not tables:
        st.error("Aucun tableau détecté dans le PDF.")
        return pd.DataFrame()
    df = pd.concat(tables, ignore_index=True)
    return df


def lire_excel(path):
    """Lit le premier tableau Excel trouvé"""
    xls = pd.ExcelFile(path)
    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
    return df


def generer_pdf(df, entite):
    """Génère le rapport PDF professionnel"""
    mois = datetime.now().strftime("%B %Y")
    out_name = f"Rapport_{entite.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    out_path = os.path.join(RAPPORT_DIR, out_name)

    logo_path = os.path.join(os.path.dirname(__file__), "logo_hopital.png")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # === En-tête ===
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=8, w=25)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Rapport de vérification du stock", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"{entite} — {mois}", ln=True, align="C")
    pdf.ln(10)

    # === Tableau ===
    pdf.set_font("Helvetica", "B", 10)
    headers = ["Produit", "Qté théorique", "Qté réelle", "Écart", "Sorties", "Statut", "Commentaire"]
    col_widths = [55, 25, 25, 20, 20, 25, 35]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, align="C")
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 9)
    conformes = manquants = endo = 0
    for _, row in df.iterrows():
        for i, h in enumerate(headers):
            val = str(row[h]) if h in row else ""
            pdf.cell(col_widths[i], 7, val[:30], border=1)
        pdf.ln(7)
        if "Statut" in row:
            s = str(row["Statut"]).lower()
            if "conforme" in s: conformes += 1
            elif "manquant" in s: manquants += 1
            elif "endom" in s: endo += 1

    # === Résumé ===
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Résumé :", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Conformes : {conformes}    Manquants : {manquants}    Endommagés : {endo}", ln=True)
    pdf.ln(6)
    pdf.cell(0, 6, "Observations :", ln=True)
    pdf.multi_cell(0, 6, "......................................................................................\n" * 2)
    pdf.ln(10)
    pdf.cell(0, 6, "Signature du responsable : ____________________________", ln=True, align="L")

    pdf.output(out_path)
    return out_path


# === Interface Streamlit ===
st.set_page_config(page_title="HOSP-STOCK PDF", page_icon="💊", layout="wide")
st.title("💊 HOSP-STOCK PDF — Rapport automatique")

entite = st.selectbox("Choisir l'entité :", ["Magasin 3", "Magasin 1 – Étage 3"])

uploaded = st.file_uploader("Importer le fichier (PDF ou Excel)", type=["pdf", "xlsx"])

if uploaded:
    if uploaded.name.endswith(".pdf"):
        df = lire_pdf(uploaded)
    else:
        df = lire_excel(uploaded)

    if not df.empty:
        st.success(f"Fichier importé ({len(df)} lignes).")
        st.dataframe(df.head(20), use_container_width=True)
        st.markdown("---")

        # Colonnes standardisées
        final_cols = ["Produit", "Qté théorique", "Qté réelle", "Écart", "Sorties", "Statut", "Commentaire"]
        for col in final_cols:
            if col not in df.columns:
                df[col] = ""

        st.info("Corrigez les valeurs avant de générer le rapport :")
        edited_df = st.data_editor(df[final_cols], num_rows="dynamic", use_container_width=True)

        if st.button("📄 Générer le rapport PDF", type="primary"):
            pdf_path = generer_pdf(edited_df, entite)
            st.success("✅ Rapport généré avec succès !")
            with open(pdf_path, "rb") as f:
                st.download_button("Télécharger le rapport", f, file_name=os.path.basename(pdf_path))
else:
    st.info("Importez un fichier PDF ou Excel pour commencer.")
