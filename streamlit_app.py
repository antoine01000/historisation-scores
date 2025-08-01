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
            st.warning("Recharge la page manuellement.")

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

# ==== Vue ====
view = st.sidebar.radio("Vue", ["Métriques", "Scores"])

# ==== Données communes ====
tickers_available = sorted(df["ticker"].dropna().unique())
latest_date = df["date"].max()
latest_snapshot = df[df["date"] == latest_date]

# Initialisation persistée
if "metrics_tickers" not in st.session_state:
    st.session_state.metrics_tickers = tickers_available[:3] if len(tickers_available) >= 3 else tickers_available
if "scores_tickers" not in st.session_state:
    st.session_state.scores_tickers = tickers_available[:3] if len(tickers_available) >= 3 else tickers_available

# --- Vue Métriques ---
if view == "Métriques":
    POSSIBLE_METRICS = [
        "10y_avg_annual_return_%", "10y_R2", "5y_avg_annual_return_%",
        "SBC_as_%_of_FCF", "net_debt_to_ebitda",
        "Revenue_Growth_5Y", "Revenue_Growth_LastYear_%", "FreeCashFlow5Y",
        "EPS_Growth_5Y", "EPS_Growth_3Y", "ROIC_5Y", "ROI_ANNUAL",
        "Gross_Margin_5Y", "Gross_Margin_Annual"
    ]
    METRICS = [m for m in POSSIBLE_METRICS if m in df.columns]

    st.sidebar.header("Filtres métriques")
    metric = st.sidebar.selectbox("Choisir la métrique", METRICS, key="metric_choice")

    col1, col2 = st.sidebar.columns([1, 1])
    if col1.button("Tout sélectionner métriques"):
        st.session_state.metrics_tickers = tickers_available.copy()
    if col2.button("Tout désélectionner métriques"):
        st.session_state.metrics_tickers = []

    tickers_metrics = st.sidebar.multiselect(
        "Choisir entreprises (métriques)",
        options=tickers_available,
        default=st.session_state.metrics_tickers,
        key="metrics_tickers"
    )

    df_filtered = df[df["ticker"].isin(tickers_metrics)].sort_values(["ticker", "date", "horodatage"])
    scores_filtered_metrics = scores[scores["ticker"].isin(tickers_metrics)].sort_values(["ticker", "date"], ascending=[True, False])

    st.subheader(f"Évolution de **{metric}** pour {', '.join(tickers_metrics) if tickers_metrics else '(aucune sélection)'}")
    if metric not in df.columns:
        st.warning(f"La métrique {metric} n'existe pas.")
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
                title=f"{metric} — évolution",
                labels={metric: metric, "date_snapshot": "Date"}
            )
            fig.update_xaxes(type="category")
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée pour la sélection métrique.")

    st.subheader(f"Comparaison de **{metric}** sur la dernière date ({latest_date})")
    if metric in latest_snapshot.columns:
        comp = latest_snapshot[["ticker", metric]].dropna()
        if not comp.empty:
            comp_sorted = comp.sort_values(by=metric, ascending=False)
            st.dataframe(comp_sorted.reset_index(drop=True))
            bar = px.bar(comp_sorted, x="ticker", y=metric, labels={metric: metric})
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("Pas de valeur disponible pour cette métrique.")
    else:
        st.warning(f"{metric} absent de la dernière snapshot.")

    if len(tickers_metrics) == 1:
        ticker = tickers_metrics[0]
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
            st.info("Pas de score disponible.")
    else:
        st.subheader("Scores globaux (métriques)")
        if not scores_filtered_metrics.empty:
            latest_scores_snapshot = scores_filtered_metrics[
                scores_filtered_metrics["date"] == scores_filtered_metrics["date"].max()
            ]
            if not latest_scores_snapshot.empty:
                st.dataframe(
                    latest_scores_snapshot[["ticker", "Score_sur_20", "Total_Score"]]
                    .sort_values("Score_sur_20", ascending=False)
                    .reset_index(drop=True)
                )
            else:
                st.info("Pas de score récent pour cette sélection.")
        else:
            st.info("Aucun score pour cette sélection.")

# --- Vue Scores ---
else:
    st.sidebar.header("Filtres scores")
    col1s, col2s = st.sidebar.columns([1, 1])
    if col1s.button("Tout sélectionner scores"):
        st.session_state.scores_tickers = tickers_available.copy()
    if col2s.button("Tout désélectionner scores"):
        st.session_state.scores_tickers = []

    tickers_scores = st.sidebar.multiselect(
        "Choisir entreprises (scores)",
        options=tickers_available,
        default=st.session_state.scores_tickers,
        key="scores_tickers"
    )

    scores_filtered = scores[scores["ticker"].isin(tickers_scores)].sort_values(["ticker", "date"], ascending=[True, False])

    st.subheader("Évolution du Score sur 20")
    if scores_filtered.empty:
        st.warning("Aucune donnée de score pour la sélection.")
    else:
        fig_score = px.line(
            scores_filtered,
            x="date",
            y="Score_sur_20",
            color="ticker",
            markers=True,
            title="Évolution du Score sur 20",
            labels={"Score_sur_20": "Score / 20", "date": "Date"}
        )
        fig_score.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_score, use_container_width=True)

        st.subheader(f"Classement sur la dernière date ({scores['date'].max()})")
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
                    labels={"Score_sur_20": "Score / 20"}
                )
                st.plotly_chart(bar2, use_container_width=True)
            else:
                st.info("Pas de snapshot récente.")
        else:
            st.warning("Colonne 'Score_sur_20' absente.")

    if len(tickers_scores) == 1:
        ticker = tickers_scores[0]
        st.subheader(f"Détail du score pour {ticker}")
        if not scores.empty and ticker in scores["ticker"].values:
            score_t = scores[scores["ticker"] == ticker].sort_values("date", ascending=False)
            st.dataframe(score_t[["date", "Total_Score", "Score_sur_20"]].reset_index(drop=True))
        else:
            st.info("Pas de score disponible pour ce ticker.")

# ==== Données brutes ====
with st.expander("Afficher les données brutes"):
    st.markdown("**DF historique complet :**")
    st.dataframe(df)
    st.markdown("**Scores complets :**")
    st.dataframe(scores)
