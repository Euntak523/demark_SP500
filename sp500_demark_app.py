import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------------
# 데이터/헬퍼
# -----------------------------
@st.cache_data(ttl=86400)
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'GICS Sector']]

def _download_retry(symbol, period="6mo", tries=3):
    for _ in range(tries):
        try:
            df = yf.download(symbol, period=period, auto_adjust=False, progress=False, threads=False)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    return None

def current_demark_setup(symbol):
    df = _download_retry(symbol, period="6mo", tries=3)
    if df is None or df.empty or len(df) < 30:
        return "데이터 부족", None, None

    df = df.copy()
    df['Close-4'] = df['Close'].shift(4)
    df['Setup'] = None

    setup_count = 0
    setup_index = 0
    setup_direction = "하락"  # 현재 로직은 하락 Setup 기준

    for i in range(4, len(df)):
        try:
            close = float(df.iloc[i]['Close'])
            close_4 = float(df.iloc[i]['Close-4'])
        except Exception:
            continue

        if close < close_4:
            setup_count += 1
            if setup_count == 9:
                setup_index += 1
                df.loc[df.index[i], 'Setup'] = f"Setup {setup_index}번째 완료"
                setup_count = 0
        else:
            setup_count = 0

    if df['Setup'].isnull().all():
        return "최근 90일 기준 Setup 미완료", df, None

    return f"총 {setup_index}개 Setup 완료", df, setup_direction

def draw_chart(symbol: str):
    status, df, _ = current_demark_setup(symbol)
    if df is None or df.empty:
        st.warning(f"{symbol}: 데이터가 부족합니다.")
        return

    df = df.copy()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df.index, df['Close'], label='Close', linewidth=1.2)
    ax.plot(df.index, df['MA20'], label='MA20', linestyle='--')
    ax.plot(df.index, df['MA60'], label='MA60', linestyle=':')
    ax.plot(df.index, df['MA120'], label='MA120', linestyle='-.')
    setup_df = df[df['Setup'].notnull()]
    if not setup_df.empty:
        ax.scatter(setup_df.index, setup_df['Close'], label="Setup 9 완료", marker='o')
    ax.legend()
    ax.set_title(f"{symbol} DeMark Setup + MAs")
    st.pyplot(fig)
    plt.close(fig)

# -----------------------------
# 앱
# -----------------------------
st.set_page_config(layout="wide")
st.title("📊 S&P 500 DeMark Setup 자동 분석기")

if "setup_results" not in st.session_state:
    st.session_state.setup_results = []
if "df_result" not in st.session_state:
    st.session_state.df_result = pd.DataFrame()
if "symbol_select" not in st.session_state:
    st.session_state.symbol_select = None

# 분석 실행
if st.button("전체 S&P 500 분석 시작"):
    sp500_df = get_sp500_symbols()
    results = []
    with st.spinner("분석 중입니다..."):
        for _, row in sp500_df.iterrows():
            sym = row['Symbol']; sector = row['GICS Sector']
            try:
                status, df, direction = current_demark_setup(sym)
                if "Setup 미완료" not in status and status != "데이터 부족":
                    # 시총(옵션)
                    try:
                        info = yf.Ticker(sym).info
                        cap = info.get("marketCap")
                        cap_str = f"{cap/1_000_000_000:.2f}B" if cap else None
                    except Exception:
                        cap, cap_str = None, None
                    results.append({
                        "Symbol": sym,
                        "Status": status,
                        "Direction": direction,
                        "Sector": sector,
                        "MarketCap": cap_str,
                        "MarketCap_RAW": cap
                    })
            except Exception:
                continue

    if results:
        df = pd.DataFrame(results).sort_values(by="MarketCap_RAW", ascending=False, na_position="last")
        st.session_state.df_result = df
        st.session_state.setup_results = results
        st.success(f"총 {len(df)}개 종목이 Setup 완료 상태입니다.")
        st.session_state.symbol_select = df.iloc[0]["Symbol"]  # 기본 선택값

# 결과 표시
if len(st.session_state.setup_results) == 0:
    st.warning("Setup 완료된 종목이 없습니다.")
    st.stop()

df_result = st.session_state.df_result.copy()

# 업종 필터
sectors = df_result["Sector"].dropna().unique().tolist()
selected_sector = st.selectbox("업종 필터링:", ["전체"] + sorted(sectors))
if selected_sector != "전체":
    df_result = df_result[df_result["Sector"] == selected_sector]

if df_result.empty:
    st.warning("필터 결과가 비어 있습니다.")
    st.stop()

# 표 (AgGrid는 보기용, 선택 실패해도 드롭다운으로 차트 선택 가능)
display_df = df_result.drop(columns=["MarketCap_RAW"])
gb = GridOptionsBuilder.from_dataframe(display_df)
gb.configure_selection(selection_mode="single", use_checkbox=True)
gb.configure_grid_options(suppressRowClickSelection=False, rowSelection="single")
grid_options = gb.build()

grid_response = AgGrid(
    display_df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.SELECTION_CHANGED,
    height=500,
    fit_columns_on_grid_load=True,
    key="main_grid"
)

# AgGrid 선택값이 잡히면 드롭다운 값 덮어쓰기 (가능한 경우만)
try:
    rows = grid_response["selected_rows"] or []
except Exception:
    rows = []
if rows:
    try:
        sym_from_grid = pd.DataFrame(rows).iloc[0].get("Symbol")
        if sym_from_grid:
            st.session_state.symbol_select = sym_from_grid
    except Exception:
        pass

# ✅ 차트용 심볼 드롭다운 (핵심)
symbols = df_result["Symbol"].tolist()
default_idx = 0
if st.session_state.symbol_select in symbols:
    default_idx = symbols.index(st.session_state.symbol_select)

selected_symbol = st.selectbox("차트 볼 심볼을 선택하세요:", symbols, index=default_idx)
st.session_state.symbol_select = selected_symbol

st.markdown(f"### {selected_symbol} 차트")
draw_chart(selected_symbol)
