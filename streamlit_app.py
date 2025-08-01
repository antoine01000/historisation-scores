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

if st.button("🔄 Rafraîchir les données", key="refresh_button"):
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
view = st.sidebar.radio(
    "Vue", 
    ["Métriques", "Scores"], 
    index=0, 
    key="view_selection"
)

# ==== Valeurs communes ====
tickers_available = sorted(df["ticker"].dropna().unique())
latest_date = df["date"].max()
latest_snapshot = df[df["date"] == latest_date]

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
    metric = st.sidebar.selectbox("Choisir la métrique", METRICS, key="metric_selection")
    tickers_metrics = st.sidebar.multiselect(
        "Choisir entreprises (métriques)",
        options=tickers_available,
        default=tickers_available[:3] if len(tickers_available) >= 3 else tickers_available,
        key="tickers_metrics"
    )

    # Filtrer les données
    df_filtered = df[df["ticker"].isin(tickers_metrics)].sort_values(["ticker", "date", "horodatage"])
    scores_filtered_metrics = scores[scores["ticker"].isin(tickers_metrics)].sort_values(["ticker", "date"], ascending=[True, False])

    # Évolution de la métrique
    st.subheader(f"Évolution de **{metric}** pour {', '.join(tickers_metrics)}")
    if metric not in df.columns:
        st.warning(f"La métrique {metric} n'existe pas.")
    elif df_filtered.empty:
        st.warning("Aucune donnée pour ces tickers.")
    else:
        df_plot = df_filtered.copy()
        df_plot["date_snapshot"] = df_plot["date"].dt.date
        df_plot = df_plot.sort_values(["ticker", "date_snapshot"])
        fig = px.line(
            df_plot, x="date_snapshot", y=metric, color="ticker", markers=True,
            title=f"{metric} — évolution", labels={metric: metric, "date_snapshot": "Date"}
        )
        fig.update_xaxes(type="category", tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # Comparaison dernière date
    st.subheader(f"Comparaison de **{metric}** le {latest_date}")
    if metric in latest_snapshot.columns:
        comp = latest_snapshot[["ticker", metric]].dropna().sort_values(by=metric, ascending=False)
        if not comp.empty:
            st.dataframe(comp.reset_index(drop=True))
            bar = px.bar(comp, x="ticker", y=metric, labels={metric: metric})
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("Pas de valeurs disponibles.")
    else:
        st.warning(f"{metric} absent de la dernière snapshot.")

    # Détail par ticker
    if len(tickers_metrics) == 1:
        t = tickers_metrics[0]
        st.subheader(f"Détail pour {t}")
        df_t = df[df["ticker"] == t].sort_values(["date", "horodatage"])
        st.markdown("**Dernière snapshot complète :**")
        st.table(df_t.iloc[-1] if not df_t.empty else pd.DataFrame())
        st.markdown("**Score historique :**")
        if not scores.empty and t in scores["ticker"].values:
            score_t = scores[scores["ticker"] == t].sort_values("date", ascending=False)
            st.dataframe(score_t[["date", "Total_Score", "Score_sur_20"]])
        else:
            st.info("Pas de score disponible.")

# --- Vue Scores ---
else:
    st.sidebar.header("Filtres scores")
    tickers_scores = st.sidebar.multiselect(
        "Choisir entreprises (scores)",
        options=tickers_available,
        default=tickers_available[:3] if len(tickers_available) >= 3 else tickers_available,
        key="tickers_scores"
    )

    scores_filtered = scores[scores["ticker"].isin(tickers_scores)].sort_values(["ticker", "date"], ascending=[True, False])

    st.subheader("Évolution du Score sur 20")
    if scores_filtered.empty:
        st.warning("Aucune donnée de score.")
    else:
        fig_score = px.line(
            scores_filtered, x="date", y="Score_sur_20", color="ticker", markers=True,
            title="Score sur 20 — évolution", labels={"Score_sur_20": "Score / 20", "date": "Date"}
        )
        fig_score.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_score, use_container_width=True)

        st.subheader(f"Classement le {scores['date'].max()}")
        latest_scores = scores[scores["date"] == scores["date"].max()][["ticker", "Score_sur_20", "Total_Score"]]
        if not latest_scores.empty:
            st.dataframe(latest_scores.sort_values("Score_sur_20", ascending=False).reset_index(drop=True))
            bar2 = px.bar(latest_scores, x="ticker", y="Score_sur_20", labels={"Score_sur_20": "Score / 20"})
            st.plotly_chart(bar2, use_container_width=True)
        else:
            st.info("Pas de snapshot de scores.")

        if len(tickers_scores) == 1:
            t = tickers_scores[0]
            st.subheader(f"Détail du score pour {t}")
            score_t = scores[scores["ticker"] == t].sort_values("date", ascending=False)
            if not score_t.empty:
                st.dataframe(score_t[["date", "Total_Score", "Score_sur_20"]])
            else:
                st.info("Pas de score disponible pour ce ticker.")

# ==== Données brutes ====
with st.expander("Afficher les données brutes"):
    st.markdown("**Historique complet DF :**")
    st.dataframe(df)
    st.markdown("**Historique complet Scores :**")
    st.dataframe(scores)
