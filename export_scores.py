import datetime
import os
import time
import sys
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

# ==== clé Finnhub en dur ====
FINNHUB_API_KEY = "csiada1r01qpalorrno0csiada1r01qpalorrnog"

# Silence partiel des warnings de yfinance (optionnel)
original_stderr = sys.stderr
sys.stderr = open(os.devnull, 'w')


def calculate_performance_metrics(symbol: str, years: int) -> tuple[float, float, float]:
    today = datetime.date.today()
    try:
        start_date = today.replace(year=today.year - years)
    except ValueError:
        # Cas des 29 février ou dates invalides
        start_date = today - datetime.timedelta(days=365 * years)
    try:
        data = yf.download(
            symbol,
            start=start_date.isoformat(),
            end=(today + datetime.timedelta(days=1)).isoformat(),
            progress=False,
            actions=True,
            auto_adjust=False
        )
    except Exception:
        return float('nan'), float('nan'), float('nan')

    if data.empty or len(data) < 2:
        return float('nan'), float('nan'), float('nan')

    p0 = float(data["Adj Close"].iloc[0])
    p1 = float(data["Adj Close"].iloc[-1])
    total_div = float(data["Dividends"].sum())

    total_return_factor = (p1 - p0 + total_div) / p0 + 1

    if total_return_factor <= 0:
        annualized_performance = float('nan')
    else:
        actual_years_covered = (data.index[-1] - data.index[0]).days / 365.25
        if actual_years_covered <= 0:
            annualized_performance = float('nan')
        else:
            annualized_performance = (total_return_factor ** (1 / actual_years_covered) - 1) * 100

    rounded_annualized_performance = round(annualized_performance, 2)
    rounded_total_performance = round((total_return_factor - 1) * 100, 2)

    X = np.arange(len(data)).reshape(-1, 1)
    y = data["Adj Close"].values.reshape(-1, 1)

    if np.all(y == y[0]):
        return rounded_total_performance, rounded_annualized_performance, float('nan')

    try:
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        r_squared = r2_score(y, y_pred)
        rounded_r_squared = round(r_squared, 4)
    except Exception:
        rounded_r_squared = float('nan')

    return rounded_total_performance, rounded_annualized_performance, rounded_r_squared


def fetch_finnhub_metrics(symbol: str, api_key: str) -> dict:
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            headers={"X-Finnhub-Token": api_key},
            params={"symbol": symbol, "metric": "all"},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("metric", {}) or {}
    except Exception:
        pass
    return {}


def build_scores_dataframe():
    # Liste des tickers
    tickers = [
        "AMZN", "ASML", "NVDA", "GOOG", "BKNG", "NEM.HA",
        "CRM", "INTU", "MA", "MSFT", "SPGI", "V", "SNY", "IONQ", "AAPL", "TSLA", "JNJ"
    ]

    # --- perf et R² ---
    rows = []
    for sym in tickers:
        total_ret_10y, avg_annual_ret_10y, r2_10y = calculate_performance_metrics(sym, 10)
        _, avg_annual_ret_5y, _ = calculate_performance_metrics(sym, 5)
        rows.append([sym, avg_annual_ret_10y, r2_10y, avg_annual_ret_5y])
    df_base = pd.DataFrame(rows, columns=[
        "ticker",
        "10y_avg_annual_return_%", "10y_R2",
        "5y_avg_annual_return_%"
    ])

    # --- SBC / FCF ---
    rows_sbc = []
    for symbol in tickers:
        t = yf.Ticker(symbol)
        try:
            cf = t.cashflow
        except Exception:
            cf = pd.DataFrame()
        if isinstance(cf, pd.DataFrame) and 'Stock Based Compensation' in cf.index and 'Free Cash Flow' in cf.index:
            latest_sbc = cf.loc['Stock Based Compensation'].iloc[0]
            latest_fcf = cf.loc['Free Cash Flow'].iloc[0]
            ratio = (latest_sbc / latest_fcf) * 100 if latest_fcf else None
        else:
            ratio = None
        rows_sbc.append({
            "ticker": symbol,
            "SBC_as_%_of_FCF": round(ratio, 2) if ratio is not None else None
        })
    df_sbc_fcf = pd.DataFrame(rows_sbc)

    df = pd.merge(df_base, df_sbc_fcf, on='ticker')

    # --- Net debt to EBITDA ---
    net_debt_to_ebitda_ratios = []
    for symbol in tickers:
        try:
            t = yf.Ticker(symbol)
            info = t.info
            total_debt = info.get("totalDebt")
            total_cash = info.get("totalCash")
            ebitda = info.get("ebitda")
            if total_debt is not None and total_cash is not None and ebitda:
                net_debt = total_debt - total_cash
                net_debt_to_ebitda = net_debt / ebitda
                net_debt_to_ebitda_ratios.append(net_debt_to_ebitda)
            else:
                net_debt_to_ebitda_ratios.append(None)
        except Exception:
            net_debt_to_ebitda_ratios.append(None)
    df['net_debt_to_ebitda'] = net_debt_to_ebitda_ratios

    # --- Finnhub ---
    finnhub_rows = []
    for ticker in tickers:
        metrics = fetch_finnhub_metrics(ticker, FINNHUB_API_KEY)
        finnhub_rows.append({
            'ticker': ticker,
            'Revenue_Growth_5Y': metrics.get("revenueGrowth5Y"),
            'Revenue_Growth_LastYear_%': metrics.get("revenueGrowthTTMYoy"),
            'FreeCashFlow5Y': metrics.get("focfCagr5Y"),
            'EPS_Growth_5Y': metrics.get("epsGrowth5Y"),
            'EPS_Growth_3Y': metrics.get("epsGrowth3Y"),
            'ROIC_5Y': metrics.get("roi5Y"),
            'ROI_ANNUAL': metrics.get("roiAnnual"),
            'Gross_Margin_5Y': metrics.get("grossMargin5Y"),
            'Gross_Margin_Annual': metrics.get("grossMarginAnnual")
        })
    df_finnhub = pd.DataFrame(finnhub_rows)
    df = pd.merge(df, df_finnhub, on='ticker', how='left')

    # --- Arrondis ---
    for col in [
        'Revenue_Growth_5Y',
        'Revenue_Growth_LastYear_%',
        'FreeCashFlow5Y',
        'EPS_Growth_5Y',
        'EPS_Growth_3Y',
        'ROIC_5Y',
        'ROI_ANNUAL',
        'Gross_Margin_5Y',
        'Gross_Margin_Annual',
        'SBC_as_%_of_FCF'
    ]:
        if col in df.columns:
            df[col] = df[col].round(2)

    # --- Vérification de df ---
    print("=== df (fusionné et arrondi) ===")
    print(df.to_string())

    # --- Construction des scores ---
    df_score = pd.DataFrame({'ticker': df['ticker']})

    def score_linearite_perf10y(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 0.8:
            return 1.0
        elif v >= 0.6:
            return 0.5
        else:
            return 0.0

    def score_perf5y(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 12.0:
            return 1.0
        elif v >= 8.0:
            return 0.5
        else:
            return 0.0

    def score_perf10y(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 12.0:
            return 1.0
        elif v >= 8.0:
            return 0.5
        else:
            return 0.0

    def score_revenuegrowth_5y(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 8:
            return 1.0
        elif v >= 5:
            return 0.5
        else:
            return 0.0

    def score_sbc_of_fcf(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v < 10:
            return 1.0
        elif v < 20:
            return 0.5
        else:
            return 0.0

    def score_revenue_lastyear(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 8:
            return 1.0
        elif v >= 5:
            return 0.5
        else:
            return 0.0

    def score_freecashflow5ans(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 14:
            return 1.0
        elif v >= 10:
            return 0.5
        else:
            return 0.0

    def score_eps5ans(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 12:
            return 1.0
        elif v >= 8:
            return 0.5
        else:
            return 0.0

    def score_eps3ans(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 12:
            return 1.0
        elif v >= 8:
            return 0.5
        else:
            return 0.0

    def score_roi5ans(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 15:
            return 1.0
        elif v >= 10:
            return 0.5
        else:
            return 0.0

    def score_roiannual(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 15:
            return 1.0
        elif v >= 10:
            return 0.5
        else:
            return 0.0

    def score_grossmargin5y(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 20:
            return 1.0
        elif v >= 10:
            return 0.5
        else:
            return 0.0

    def score_grossmargin_annual(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v >= 20:
            return 1.0
        elif v >= 10:
            return 0.5
        else:
            return 0.0

    def score_net_debt_to_ebitda(v):
        if pd.isna(v):
            return None
        v = float(v)
        if v < 1:
            return 1.0
        elif v < 3:
            return 0.5
        else:
            return 0.0

    df_score['Score_Linearite_Perf10y'] = df['10y_R2'].apply(score_linearite_perf10y)
    df_score['Score_Performance_5y'] = df['5y_avg_annual_return_%'].apply(score_perf5y)
    df_score['Score_Performance_10y'] = df['10y_avg_annual_return_%'].apply(score_perf10y)
    df_score['Score_RevenueGrowth_5y'] = df['Revenue_Growth_5Y'].apply(score_revenuegrowth_5y)
    df_score['Score_SBCofFCF'] = df['SBC_as_%_of_FCF'].apply(score_sbc_of_fcf)
    df_score['Score_RevenueGrowth_LastYear'] = df['Revenue_Growth_LastYear_%'].apply(score_revenue_lastyear)
    df_score['Score_FreeCashFlow5ans'] = df['FreeCashFlow5Y'].apply(score_freecashflow5ans)
    df_score['Score_EPS5ans'] = df['EPS_Growth_5Y'].apply(score_eps5ans)
    df_score['Score_EPS3ans'] = df['EPS_Growth_3Y'].apply(score_eps3ans)
    df_score['Score_ROI5ans'] = df['ROIC_5Y'].apply(score_roi5ans)
    df_score['Score_ROIANNUAL'] = df['ROI_ANNUAL'].apply(score_roiannual)
    df_score['Score_GrossMargin5y'] = df['Gross_Margin_5Y'].apply(score_grossmargin5y)
    df_score['Score_GrossMarginAnnual'] = df['Gross_Margin_Annual'].apply(score_grossmargin_annual)
    df_score['Score_Net_Debt_to_EBITDA'] = df['net_debt_to_ebitda'].apply(score_net_debt_to_ebitda)

    # Somme et normalisation
    cols_scores = [c for c in df_score.columns if c != 'ticker']
    df_score[cols_scores] = df_score[cols_scores].apply(pd.to_numeric, errors='coerce')
    df_score['Total_Score'] = df_score[cols_scores].sum(axis=1)
    df_score['Valid_Criteria_Count'] = df_score[cols_scores].notna().sum(axis=1)
    df_score['Max_Theoretical_Score'] = df_score['Valid_Criteria_Count'] * 1
    df_score['Score_sur_20'] = (df_score['Total_Score'] / df_score['Max_Theoretical_Score']) * 20
    df_score['Score_sur_20'] = df_score['Score_sur_20'].round(2)

    df_score_sorted = df_score.sort_values(by='Score_sur_20', ascending=False)
    return df, df_score_sorted


def save_df_history(df):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    df_export = df.copy()
    df_export['date'] = today_str
    df_export['horodatage'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_path = "historique_df.csv"

    if os.path.exists(csv_path):
        df_old = pd.read_csv(csv_path)
        combined = pd.concat([df_old, df_export], ignore_index=True)
        combined = combined.sort_values('horodatage').drop_duplicates(subset=['ticker', 'date'], keep='last')
        combined.to_csv(csv_path, index=False)
    else:
        df_export.to_csv(csv_path, index=False)


def save_history(df_score_sorted):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    df_export = df_score_sorted[['ticker', 'Total_Score', 'Score_sur_20']].copy()
    df_export['date'] = today_str
    df_export['horodatage'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_path = "historique_scores.csv"
    if os.path.exists(csv_path):
        df_old = pd.read_csv(csv_path)
        merged = pd.concat([df_old, df_export], ignore_index=True)
        merged = merged.sort_values('horodatage').drop_duplicates(subset=['ticker', 'date'], keep='last')
        merged.to_csv(csv_path, index=False)
    else:
        df_export.to_csv(csv_path, index=False)


def main():
    try:
        df, df_score_sorted = build_scores_dataframe()
        save_df_history(df)
        save_history(df_score_sorted)
        print("✅ Historisation faite.")
    except Exception as e:
        print(f"❌ Erreur : {e}")
        raise
    finally:
        # restauration de stderr
        try:
            sys.stderr.close()
        except Exception:
            pass
        sys.stderr = original_stderr


if __name__ == "__main__":
    main()

