# HOSP-STOCK Assistant (Prototype)

## Utilisation rapide
1) Préparez un Excel d'initialisation à partir de `modele_import.xlsx`.
2) Lancez localement: `streamlit run app_stock.py`.
3) Ou déployez sur Streamlit Cloud en important ce dossier depuis GitHub.

## Flux
- Page Accueil: choisir l'entité (Magasin 3 ou Magasin 1 – Etage 3) et importer l'Excel (1ère fois).
- Page Suivi: enregistrer Entrée / Sortie / Endommagé, le stock se met à jour.
- Page Rapport: exporter un Excel récapitulatif daté.
