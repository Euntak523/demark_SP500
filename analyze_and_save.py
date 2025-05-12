import yfinance as yf
import pandas as pd
from datetime import datetime

# DeMark 분석 함수 (간략화)
def current_demark_status(symbol):
    df = yf.download(symbol, period="3mo")
    if df.empty or len(df) < 30:
        return None

    df = df.copy()
    df['Close-4'] = df['Close'].shift(4)
    df['Close-2'] = df['Close'].shift(2)
    df['Setup'] = None
    df['Countdown'] = 0

    setup_count = 0
    setup_indices = []

    for i in range(4, len(df)):
        try:
            if df.iloc[i]['Close'] < df.iloc[i]['Close-4']:
                setup_count += 1
                if setup_count == 9:
                    df.loc[df.index[i], 'Setup'] = "하락"
                    setup_indices.append(i)
                    setup_count = 0
            else:
                setup_count = 0
        except:
            continue

    if not setup_indices:
        return None

    setup_done_index = setup_indices[-1]
    countdown_count = 0
    for j in range(setup_done_index + 1, len(df)):
        try:
            if df.iloc[j]['Close'] < df.iloc[j]['Close-2']:
                countdown_count += 1
                df.loc[df.index[j], 'Countdown'] = countdown_count
        except:
            continue

    if countdown_count >= 13:
        return "Countdown 13 (Signal)"
    elif countdown_count > 0:
        return f"Countdown {countdown_count}/13"
    else:
        return "Countdown 시작 전"

# S&P 500 종목 리스트 불러오기
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    return table[0][["Symbol", "GICS Sector"]]

# 시가총액 불러오기
def get_market_cap(symbol):
    try:
        info = yf.Ticker(symbol).info
        cap = info.get("marketCap", None)
        if cap:
            return cap, f"{cap / 1_000_000_000:.2f}B"
        return None, None
    except:
        return None, None

# 분석 실행
def run_analysis():
    symbols_df = get_sp500_symbols()
    results = []

    for _, row in symbols_df.iterrows():
        symbol = row['Symbol']
        sector = row['GICS Sector']
        status = current_demark_status(symbol)
        if status:
            cap_raw, cap_str = get_market_cap(symbol)
            results.append({
                "종목": symbol,
                "상태": status,
                "업종": sector,
                "시가총액": cap_str,
                "시총_RAW": cap_raw
            })

    df = pd.DataFrame(results)
    if "시총_RAW" in df.columns:
        df = df.sort_values(by="시총_RAW", ascending=False)
    filename = f"daily_result_{datetime.today().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False)
    print(f"✅ 분석 완료. {filename} 저장됨")

if __name__ == "__main__":
    run_analysis()
