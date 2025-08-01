import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(layout="wide", page_title="Historique des métriques fondamentales")

st.title("📊 Exploration des métriques fondamentales")

# ==== Rafraîchir ====
def do_refresh():
    try:
        if hasattr(st, "cache_data") and hasattr(st.cache_data, "clear"):
            st.cache_data.clear()
    except Exception:
        pass
    try:
        st.experimental_rerun()
    except AttributeError:
        try:
            st.rerun()
        except Exception:
            st.warning("Impossible de relancer automatiquement, recharge la page manuellement.")

if st.button("🔄 Rafraîchir les données"):
    do_refresh()

# ==== Chargement des données ====
@st.cache_data
def load_data():
    df_path = "historique_df.csv"
    scores_path = "historique_scores.csv"
    if not os.path.exists(df_path):
        st.error(f"Le fichier '{df_path}' est introuvable.")
        return pd.DataFrame(), pd.DataFrame()
    df = pd.read_csv(df_path, parse_dates=["date", "horodatage"])
    if os.path.exists(scores_path):
        scores = pd.read_csv(scores_path, parse_dates=["date", "horodatage"])
    else:
        scores = pd.DataFrame()
    return df, scores

df, scores = load_data()

if df.empty:
    st.stop()

# Info de dernière mise à jour
last_update = df["horodatage"].max()
if pd.notna(last_update):
    try:
        st.markdown(f"**Dernière mise à jour enregistrée :** {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        st.markdown(f"**Dernière mise à jour enregistrée :** {last_update}")

# ==== Sélection de la vue ====
view = st.sidebar.radio("Vue", ["Métriques", "Scores"])

# ==== Common selections ====
tickers_available = sorted(df["ticker"].dropna().unique())
tickers_selected = st.sidebar.multiselect(
    "Choisir une ou plusieurs entreprises",
    options=tickers_available,
    default=tickers_available[:3] if len(tickers_available) >= 3 else tickers_available
)

# ==== Données dérivées ====
latest_date = df["date"].max()
latest_snapshot = df[df["date"] == latest_date]
df_filtered = df[df["ticker"].isin(tickers_selected)].sort_values(["ticker", "date", "horodatage"])
scores_filtered = scores[scores["ticker"].isin(tickers_selected)].sort_values(["ticker", "date"], ascending=[True, False])

# --- Vue Métriques ---
if view == "Métriques":
    # Liste des métriques disponibles (intersection avec colonnes)
    POSSIBLE_METRICS = [
        "10y_avg_annual_return_%", "10y_R2", "5y_avg_annual_return_%",
        "SBC_as_%_of_FCF", "net_debt_to_ebitda",
        "Revenue_Growth_5Y", "Revenue_Growth_LastYear_%", "FreeCashFlow5Y",
        "EPS_Growth_5Y", "EPS_Growth_3Y", "ROIC_5Y", "ROI_ANNUAL",
        "Gross_Margin_5Y", "Gross_Margin_Annual"
    ]
    METRICS = [m for m in POSSIBLE_METRICS if m in df.columns]

    st.sidebar.header("Filtres métriques")
    metric = st.sidebar.selectbox("Choisir la métrique", METRICS)

    st.subheader(f"Évolution de **{metric}** pour {', '.join(tickers_selected)}")
    if metric not in df.columns:
        st.warning(f"La métrique {metric} n'existe pas dans les données.")
    else:
        if not df_filtered.empty:
            df_plot = df_filtered.copy()
            df_plot["date_snapshot"] = pd.to_datetime(df_plot["date"]).dt.date
            df_plot = df_plot.sort_values(["ticker", "date_snapshot"])
            fig = px.line(
                df_plot,
                x="date_snapshot",
                y=metric,
                color="ticker",
                markers=True,
                title=f"{metric} — évolution dans le temps",
                labels={metric: metric, "date_snapshot": "Date"}
            )
            fig.update_xaxes(type="category")
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aucune donnée disponible pour les tickers sélectionnés.")

    st.subheader(f"Comparaison de **{metric}** sur la dernière date ({latest_date})")
    if metric in latest_snapshot.columns:
        comp = latest_snapshot[["ticker", metric]].dropna()
        if not comp.empty:
            comp_sorted = comp.sort_values(by=metric, ascending=False)
            st.dataframe(comp_sorted.reset_index(drop=True))
            bar = px.bar(
                comp_sorted,
                x="ticker",
                y=metric,
                title=f"{metric} — snapshot la plus récente",
                labels={metric: metric, "ticker": "Ticker"}
            )
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("Pas de valeur disponible pour cette métrique dans la dernière snapshot.")
    else:
        st.warning(f"{metric} absent de la dernière snapshot.")

    # Détail (si un seul ticker)
    if len(tickers_selected) == 1:
        ticker = tickers_selected[0]
        st.subheader(f"Détail pour {ticker}")
        df_t = df[df["ticker"] == ticker].sort_values(["date", "horodatage"])
        st.markdown("**Dernière snapshot complète :**")
        if not df_t.empty:
            st.table(df_t.iloc[-1])
        else:
            st.info("Pas de données historiques pour ce ticker.")

        st.markdown("**Score historique :**")
        if not scores.empty and ticker in scores["ticker"].values:
            score_t = scores[scores["ticker"] == ticker].sort_values("date", ascending=False)
            st.dataframe(score_t[["date", "Total_Score", "Score_sur_20"]].reset_index(drop=True))
        else:
            st.info("Pas de score disponible pour ce ticker.")
    else:
        st.subheader("Scores globaux des tickers sélectionnés")
        if not scores.empty:
            scores_filtered_latest = scores_filtered[scores_filtered["date"] == scores_filtered["date"].max()]
            if not scores_filtered_latest.empty:
                st.dataframe(
                    scores_filtered_latest[["ticker", "Score_sur_20", "Total_Score"]]
                    .sort_values("Score_sur_20", ascending=False)
                    .reset_index(drop=True)
                )
            else:
                st.info("Pas de scores pour cette sélection.")
        else:
            st.info("Fichier de scores introuvable ou vide.")

# --- Vue Scores ---
else:
    st.subheader("Évolution du Score sur 20")
    if scores_filtered.empty:
        st.warning("Aucune donnée de score disponible pour la sélection.")
    else:
        # ligne temporelle du Score_sur_20
        fig_score = px.line(
            scores_filtered,
            x="date",
            y="Score_sur_20",
            color="ticker",
            markers=True,
            title="Évolution du Score sur 20 par entreprise",
            labels={"Score_sur_20": "Score / 20", "date": "Date"}
        )
        fig_score.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_score, use_container_width=True)

        # comparaison sur la dernière snapshot de score
        st.subheader(f"Classement des scores sur la dernière date ({scores['date'].max()})")
        if "Score_sur_20" in scores.columns:
            latest_scores_snapshot = scores[scores["date"] == scores["date"].max()]
            if not latest_scores_snapshot.empty:
                ranking = latest_scores_snapshot[["ticker", "Score_sur_20", "Total_Score"]].sort_values("Score_sur_20", ascending=False)
                st.dataframe(ranking.reset_index(drop=True))
                bar2 = px.bar(
                    ranking,
                    x="ticker",
                    y="Score_sur_20",
                    title="Distribution du Score sur 20 (dernière snapshot)",
                    labels={"Score_sur_20": "Score / 20", "ticker": "Ticker"}
                )
                st.plotly_chart(bar2, use_container_width=True)
            else:
                st.info("Pas de snapshot récente de scores.")
        else:
            st.warning("La colonne 'Score_sur_20' est absente du fichier de scores.")

    # Détail score pour un seul ticker (si sélection unique)
    if len(tickers_selected) == 1:
        ticker = tickers_selected[0]
        st.subheader(f"Détail du score pour {ticker}")
        if not scores.empty and ticker in scores["ticker"].values:
            score_t = scores[scores["ticker"] == ticker].sort_values("date", ascending=False)
            st.dataframe(score_t[["date", "Total_Score", "Score_sur_20"]].reset_index(drop=True))
        else:
            st.info("Pas de score disponible pour ce ticker.")

# ==== Données brutes ====
with st.expander("Afficher les données brutes"):
    st.markdown("**DF historique filtré :**")
    st.dataframe(df_filtered)
    st.markdown("**Scores filtrés :**")
    st.dataframe(scores_filtered)
