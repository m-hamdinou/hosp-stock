
import os
import sqlite3
from contextlib import closing
import pandas as pd
import streamlit as st
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

ENTITES = ["Magasin 3", "Magasin 1 – Etage 3"]

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn, conn, closing(conn.cursor()) as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entite TEXT NOT NULL,
            produit TEXT NOT NULL,
            lot TEXT,
            date_peremption TEXT,
            stock_initial REAL DEFAULT 0,
            stock_actuel REAL DEFAULT 0,
            UNIQUE(entite, produit, lot)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mouvements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit_id INTEGER NOT NULL,
            type TEXT CHECK(type IN ('Entree','Sortie','Endommage')) NOT NULL,
            quantite REAL NOT NULL,
            service TEXT,
            ts TEXT NOT NULL,
            commentaire TEXT,
            FOREIGN KEY(produit_id) REFERENCES produits(id)
        )
        """)
        conn.commit()

def import_excel(df: pd.DataFrame):
    required = {"Entite","Produit","Lot","Date_peremption","Stock_initial"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Colonnes manquantes dans l'Excel: {', '.join(missing)}")
        return
    with closing(sqlite3.connect(DB_PATH)) as conn, conn, closing(conn.cursor()) as cur:
        for _, row in df.iterrows():
            entite = str(row["Entite"]).strip()
            if entite not in ENTITES:
                continue
            produit = str(row["Produit"]).strip()
            lot = ("" if pd.isna(row["Lot"]) else str(row["Lot"]).strip())
            datep = ("" if pd.isna(row["Date_peremption"]) else str(row["Date_peremption"]).strip())
            stock_initial = float(row["Stock_initial"]) if not pd.isna(row["Stock_initial"]) else 0.0
            cur.execute("""
            INSERT INTO produits (entite, produit, lot, date_peremption, stock_initial, stock_actuel)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entite, produit, lot) DO UPDATE SET
              date_peremption=excluded.date_peremption,
              stock_initial=excluded.stock_initial,
              stock_actuel=CASE
                WHEN produits.stock_actuel IS NULL OR produits.stock_actuel=0
                THEN excluded.stock_initial
                ELSE produits.stock_actuel
              END
            """, (entite, produit, lot, datep, stock_initial, stock_initial))
        conn.commit()
    st.success("Importation terminée ✅")

def get_produits(entite: str) -> pd.DataFrame:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        df = pd.read_sql_query("SELECT * FROM produits WHERE entite=? ORDER BY produit", conn, params=(entite,))
    return df

def add_mouvement(produit_id: int, typ: str, qte: float, service: str, commentaire: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(sqlite3.connect(DB_PATH)) as conn, conn, closing(conn.cursor()) as cur:
        cur.execute("""
        INSERT INTO mouvements (produit_id, type, quantite, service, ts, commentaire)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (prodit_id, typ, qte, service, ts, commentaire))

        signe = +1 if typ == "Entree" else -1
        if typ == "Endommage":
            signe = -1
        cur.execute("""
        UPDATE produits SET stock_actuel = COALESCE(stock_actuel,0) + (? * ?)
        WHERE id = ?
        """, (signe, qte, produit_id))
        conn.commit()

def export_rapport(entite: str) -> str:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        prod = pd.read_sql_query("SELECT * FROM produits WHERE entite=? ORDER BY produit", conn, params=(entite,))
        mv = pd.read_sql_query("""
            SELECT m.*, p.entite, p.produit, p.lot
            FROM mouvements m JOIN produits p ON p.id=m.produit_id
            WHERE p.entite=?
            ORDER BY ts DESC
        """, conn, params=(entite,))

    def tot(df, pid, typ):
        s = df[(df["produit_id"]==pid) & (df["type"]==typ)]["quantite"].sum()
        return float(s) if not pd.isna(s) else 0.0

    rows = []
    for _, r in prod.iterrows():
        pid = r["id"]
        rows.append({
            "Produit": r["produit"],
            "Lot": r["lot"],
            "Date péremption": r["date_peremption"],
            "Stock initial": r["stock_initial"],
            "Total entrées": tot(mv, pid, "Entree"),
            "Total sorties": tot(mv, pid, "Sortie"),
            "Total endommagé": tot(mv, pid, "Endommage"),
            "Stock actuel": r["stock_actuel"],
        })
    recap = pd.DataFrame(rows)

    out_name = f"Rapport_{entite.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    out_path = os.path.join(DATA_DIR, out_name)
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        recap.to_excel(writer, index=False, sheet_name="Récapitulatif")
        mv.to_excel(writer, index=False, sheet_name="Mouvements")
        prod.to_excel(writer, index=False, sheet_name="Produits")
    return out_path

st.set_page_config(page_title="HOSP-STOCK Assistant", page_icon="💊", layout="wide")
st.title("💊 HOSP-STOCK Assistant — Prototype")

init_db()

st.sidebar.header("Navigation")
page = st.sidebar.radio("Aller à :", ["Accueil", "Suivi & mouvements", "Rapport"])

if page == "Accueil":
    st.subheader("Sélection & import")
    entite = st.selectbox("Choisir l'espace de travail", ENTITES)
    st.info("Importer une première fois votre Excel (ou ré-importer pour mettre à jour). Utiliser `modele_import.xlsx`.")
    up = st.file_uploader("Importer l'Excel d'initialisation", type=["xlsx"])
    if up is not None:
        try:
            df = pd.read_excel(up)
            import_excel(df)
        except Exception as e:
            st.error(f"Erreur d'import: {e}")

    st.divider()
    st.subheader("Produits existants")
    dfp = get_produits(entite)
    st.dataframe(dfp, use_container_width=True, height=300)

elif page == "Suivi & mouvements":
    entite = st.selectbox("Espace de travail", ENTITES)
    dfp = get_produits(entite)
    if dfp.empty:
        st.warning("Aucun produit. Importez d'abord l'Excel dans l'onglet Accueil.")
    else:
        st.subheader(f"Produits — {entite}")
        st.dataframe(dfp[["id","produit","lot","date_peremption","stock_initial","stock_actuel"]],
                     use_container_width=True, height=300)

        st.markdown("### Enregistrer un mouvement")
        col1,col2,col3 = st.columns(3)
        with col1:
            choices = (dfp["produit"] + " | Lot " + dfp["lot"].fillna("")).tolist()
            choix = st.selectbox("Produit", options=choices, index=0)
            idx = (dfp["produit"] + " | Lot " + dfp["lot"].fillna("")) == choix
            produit_id = int(dfp[idx]["id"].iloc[0])
        with col2:
            typ = st.selectbox("Type de mouvement", ["Sortie","Entree","Endommage"])
            qte = st.number_input("Quantité", min_value=0.0, step=1.0, value=0.0)
        with col3:
            service = st.text_input("Service (si Sortie)", value="")
            commentaire = st.text_input("Commentaire", value="")

        if st.button("✅ Valider le mouvement", use_container_width=True, type="primary"):
            if qte <= 0:
                st.error("La quantité doit être > 0.")
            else:
                add_mouvement(produit_id, typ, qte, service, commentaire)
                st.success("Mouvement enregistré et stock mis à jour.")
                st.rerun()

elif page == "Rapport":
    entite = st.selectbox("Espace de travail", ENTITES, key="entite_rapport")
    if st.button("📤 Exporter rapport Excel", type="primary"):
        out_path = export_rapport(entite)
        with open(out_path, "rb") as f:
            st.download_button("Télécharger le rapport", f, file_name=os.path.basename(out_path), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.info("Le rapport inclut: Stock initial, Total entrées/sorties/endommagés, Stock actuel, + onglet des mouvements.")
