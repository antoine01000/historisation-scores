import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Historique des métriques")

# Bouton de rafraîchissement manuel
if st.button("🔄 Rafraîchir les données"):
    st.cache_data.clear()
    st.experimental_rerun()

@st.cache_data
def load_data():
    try:
        df = pd.read_csv("historique_df.csv", parse_dates=["horodatage", "date"])
    except FileNotFoundError:
        st.error("Le fichier `historique_df.csv` est introuvable.")
        return pd.DataFrame(), pd.DataFrame()
    try:
        scores = pd.read_csv("historique_scores.csv", parse_dates=["horodatage", "date"])
    except FileNotFoundError:
        scores = pd.DataFrame()
    return df, scores

df, scores = load_data()

# Si pas de données, on arrête
if df.empty:
    st.stop()

# Affichage de la dernière mise à jour
last_update = df["horodatage"].max()
if pd.notna(last_update):
    st.markdown(f"**Dernière mise à jour :** {last_update.strftime('%Y-%m-%d %H:%M:%S')}")

# Liste des métriques disponibles (vérifie que ça correspond aux colonnes de df)
METRICS = [
    "10y_avg_annual_return_%", "10y_R2", "5y_avg_annual_return_%",
    "SBC_as_%_of_FCF", "net_debt_to_ebitda",
    "Revenue_Growth_5Y", "Revenue_Growth_LastYear_%", "FreeCashFlow5Y",
    "EPS_Growth_5Y", "EPS_Growth_3Y", "ROIC_5Y", "ROI_ANNUAL",
    "Gross_Margin_5Y", "Gross_Margin_Annual"
]

st.sidebar.title("Filtrer")
metric = st.sidebar.selectbox("Choisir la métrique", [m for m in METRICS if m in df.columns])
ticker = st.sidebar.selectbox("Choisir l'entreprise", sorted(df["ticker"].unique()))

# Filtrer pour le ticker sélectionné
df_ticker = df[df["ticker"] == ticker].sort_values(["date", "horodatage"])
score_ticker = scores[scores["ticker"] == ticker].sort_values("date", ascending=False)

st.title(f"{ticker} — {metric}")

# Affichage de l'évolution de la métrique dans le temps pour ce ticker
st.subheader(f"Évolution de {metric}")
if metric in df_ticker.columns:
    chart_data = df_ticker.set_index("horodatage")[metric]
    if not chart_data.dropna().empty:
        st.line_chart(chart_data)
    else:
        st.info("Pas assez de points historiques pour tracer cette métrique.")
else:
    st.warning(f"La métrique {metric} n'est pas présente pour {ticker}.")

# Valeurs les plus récentes pour tous les tickers (comparaison)
st.subheader(f"Comparaison sur la date la plus récente ({df['date'].max()})")
latest_snapshot = df[df["date"] == df["date"].max()]
if metric in latest_snapshot.columns:
    sorted_latest = latest_snapshot[["ticker", metric]].sort_values(by=metric, ascending=False)
    st.dataframe(sorted_latest.reset_index(drop=True))
    st.bar_chart(sorted_latest.set_index("ticker")[metric])
else:
    st.warning(f"{metric} absent de la snapshot la plus récente.")

# Score global de l'entreprise
st.subheader("Score global historique")
if not score_ticker.empty:
    st.dataframe(score_ticker[["date", "Total_Score", "Score_sur_20"]].reset_index(drop=True))
else:
    st.info("Pas de score disponible pour ce ticker.")

# Dernière snapshot complète pour ce ticker
st.subheader("Dernière snapshot complète")
if not df_ticker.empty:
    st.table(df_ticker.sort_values(["date", "horodatage"]).iloc[-1])
else:
    st.info("Aucune donnée historique pour ce ticker.")
