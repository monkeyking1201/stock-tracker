# -*- coding: utf-8 -*-
"""
核心資產與氣韻觀測 App
"""

import base64
import io
import os
from datetime import date

import gspread
import pandas as pd
import streamlit as st
import yfinance as yf
from google.oauth2.service_account import Credentials
from PIL import Image

st.set_page_config(page_title="核心資產與氣韻觀測", page_icon="💰", layout="centered")

STOCKS = {"台積電": "2330.TW", "台達電": "2308.TW"}
HWM_LOG_PATH = "hwm_log.csv"
REALIZED_LOG_PATH = "realized_profit.csv"
HWM_COLUMNS = ["日期", "本期未實現損益", "歷史最高損益HWM", "創高日期", "本期新增氣韻點數"]
REALIZED_COLUMNS = ["結算日期", "標的", "已實現獲利金額"]

BACKGROUND_IMAGE_URL = ""
BACKGROUND_IMAGE_FILE = "background.png"


def _resolve_background_layer():
    if BACKGROUND_IMAGE_URL:
        return 'url("' + BACKGROUND_IMAGE_URL + '")' 
    if BACKGROUND_IMAGE_FILE and os.path.exists(BACKGROUND_IMAGE_FILE):
        ext = os.path.splitext(BACKGROUND_IMAGE_FILE)[1].lstrip(".").lower()
        mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
        try:
            with open(BACKGROUND_IMAGE_FILE, "rb") as f:
                enc = base64.b64encode(f.read()).decode("ascii")
            return 'url("data:image/' + mime + ';base64,' + enc + '")' 
        except Exception:
            return "none"
    return "none"


_bg_layer = _resolve_background_layer()

_BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@900&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, .stNumberInput label,
.stSelectbox label, .stDateInput label, .stButton button, .stDataFrame,
h2, h3, h4, h5, h6, p, span, div {
    font-family: 'Noto Sans TC', 'Source Han Sans TC', 'Microsoft JhengHei', sans-serif !important;
}
.stApp {
    background-color: #0e1117;
    background-image: __BG_IMAGE__;
    background-size: contain;
    background-position: top center;
    background-attachment: fixed;
    background-repeat: no-repeat;
}
.block-container { max-width: 720px; padding-top: 2.5rem; padding-bottom: 4rem; }
h1.ryo-main-title {
    font-family: 'Noto Serif TC', serif !important;
    font-weight: 900; font-size: 2.6rem; text-align: center;
    color: #FFD700; text-shadow: 0 0 20px rgba(255,215,0,0.7); margin-bottom: 2.5rem;
}
h2, h3 { font-weight: 700; font-size: 1.25rem; color: #FFFFFF; margin-top: 0; margin-bottom: 1.2rem; }
div[data-testid="stVerticalBlockBorderWrapper"].st-key-panel_hwm,
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div.st-key-panel_hwm),
div[data-testid="stVerticalBlockBorderWrapper"].st-key-panel_zeroshare,
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div.st-key-panel_zeroshare),
div[data-testid="stVerticalBlockBorderWrapper"].st-key-panel_realized,
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div.st-key-panel_realized) {
    background-color: rgba(10,10,10,0.9) !important;
    border: 3px solid #B8860B !important;
    border-radius: 10px !important;
    padding: 40px !important;
    margin-bottom: 50px !important;
    box-shadow: 0 0 25px rgba(184,134,11,0.55), 0 0 55px rgba(184,134,11,0.25) !important;
}
.ryo-panel {
    background-color: rgba(10,10,10,0.9);
    border: 3px solid #B8860B; border-radius: 10px; padding: 24px;
    margin: 0.5rem 0 1.4rem 0;
    box-shadow: 0 0 20px rgba(184,134,11,0.5), 0 0 45px rgba(184,134,11,0.2);
}
.ryo-panel:last-child { margin-bottom: 0; }
.stNumberInput input, .stTextInput input, .stDateInput input,
.stSelectbox div[data-baseweb="select"] > div {
    border: 1px solid rgba(184,134,11,0.6) !important; font-weight: 500 !important;
}
label, .stMarkdown p, .stForm label, .stText { color: #FAEBD7 !important; font-weight: 500 !important; }
/* 修復 expander arrow_right 顯示 bug */
/* 1. 隱藏 Material Icon 圖示文字（arrow_right 外露的元凶） */
div[data-testid="stExpander"] summary span:first-child,
div[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"] {
    display: none !important;
}
/* 2. 確保標題文字正常顯示 */
div[data-testid="stExpander"] summary p {
    display: block !important;
    color: #FAEBD7 !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
}
div[data-testid="stExpander"] summary { color: #FAEBD7 !important; cursor: pointer; }
.stButton button, .stFormSubmitButton button {
    background-color: #B8860B; color: #000000; border: 2px solid #B8860B;
    border-radius: 6px; letter-spacing: 0.08em; font-weight: 700;
}
.stButton button:hover, .stFormSubmitButton button:hover {
    background-color: #FFD700; color: #000000; border-color: #FFD700;
}
.ryo-label { font-size: 0.95rem; color: #B8860B; letter-spacing: 0.05em; font-weight: 700; margin-bottom: 0.2rem; }
.ryo-value { font-weight: 900; letter-spacing: 0.03em; color: #FFD700; text-shadow: 0 0 10px rgba(255,215,0,0.5); margin-bottom: 0.4rem; }
.ryo-list { color: #FAEBD7; line-height: 2; font-size: 0.95rem; }
.stDataFrame {
    background-color: rgba(0,0,0,0.6) !important; color: #FFFFFF !important;
    border: 1px solid rgba(184,134,11,0.6) !important;
}
.stExpander {
    background-color: rgba(0,0,0,0.6) !important;
    border: 1px solid rgba(184,134,11,0.6) !important;
}
div[data-testid="stAlert"] {
    background-color: rgba(0,0,0,0.75) !important; border: 1px solid #B8860B !important; color: #FAEBD7 !important;
}
"""

st.markdown("<style>" + _BASE_CSS.replace("__BG_IMAGE__", _bg_layer) + "</style>", unsafe_allow_html=True)






def _make_app_icon_b64():
    img = Image.new("RGB", (180, 180), color=(10, 10, 10))
    from PIL import ImageDraw as _ID
    draw = _ID.Draw(img)
    draw.ellipse([8,   8,  172, 172], fill=(184, 134, 11))
    draw.ellipse([22,  22, 158, 158], fill=(10,  10,  10))
    draw.ellipse([36,  36, 144, 144], fill=(255, 215,   0))
    draw.ellipse([60,  60, 120, 120], fill=(10,  10,  10))
    draw.ellipse([76,  76, 104, 104], fill=(255, 215,   0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_APP_ICON_B64 = _make_app_icon_b64()
_ICON_JS = (
    "<script>(function(){"
    "var l=document.createElement('link');"
    "l.rel='apple-touch-icon';"
    "l.href='data:image/png;base64," + _APP_ICON_B64 + "';"
    "document.head.appendChild(l);"
    "var m=document.createElement('link');"
    "m.rel='apple-touch-icon-precomposed';"
    "m.href=l.href;document.head.appendChild(m);"
    "})();</script>"
)
st.markdown(_ICON_JS, unsafe_allow_html=True)


def _remove_bg(path, mode="black", threshold=30):
    """去除圖片背景，回傳 base64 data URI。
    mode="black": 移除黑色背景（R/G/B 全 < threshold）
    mode="white": 移除白色背景（R/G/B 全 > 255-threshold）
    """
    img = Image.open(path).convert("RGBA")
    pixels = list(img.getdata())
    new_pixels = []
    for r, g, b, a in pixels:
        if mode == "black":
            if r < threshold and g < threshold and b < threshold:
                new_pixels.append((r, g, b, 0))
            else:
                new_pixels.append((r, g, b, a))
        else:
            hi = 255 - threshold
            if r > hi and g > hi and b > hi:
                new_pixels.append((r, g, b, 0))
            else:
                new_pixels.append((r, g, b, a))
    img.putdata(new_pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_TITLE_IMAGE = "jojo_title.png"
if os.path.exists(_TITLE_IMAGE):
    _b64 = _remove_bg(_TITLE_IMAGE, mode="black", threshold=30)
    st.markdown(
        "<div style='text-align:center;margin-bottom:20px;'>"
        "<img src='data:image/png;base64," + _b64 + "' "
        "style='width:100%;max-width:720px;background:transparent;'/>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown("<h1 class='ryo-main-title'>💰 氣韻積蓄繪卷</h1>", unsafe_allow_html=True)


def stat_block(label, value, size="2.2rem"):
    return (
        "<div class='ryo-label'>" + label + "</div>"
        "<div class='ryo-value' style='font-size:" + size + ";'>" + value + "</div>"
    )


def wrap_with_panel(content_html, border_color="#B8860B"):
    return (
        "<div class='ryo-panel' style='"
        "border-color:" + border_color + ";"
        "box-shadow:0 0 20px " + border_color + "99,0 0 45px " + border_color + "40;'>"
        + content_html + "</div>"
    )


@st.cache_data(ttl=300, show_spinner="正在抓取即時股價...")
def fetch_latest_prices(stock_map):
    prices = {}
    for name, code in stock_map.items():
        price = None
        try:
            ticker = yf.Ticker(code)
            # 方法1: fast_info.last_price
            try:
                fi = ticker.fast_info
                lp = getattr(fi, "last_price", None)
                if lp and float(lp) > 0:
                    price = float(lp)
            except Exception:
                price = None
            # 方法2: history 5日
            if price is None:
                try:
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                except Exception:
                    price = None
            # 方法3: history 1個月
            if price is None:
                try:
                    hist = ticker.history(period="1mo")
                    if not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                except Exception:
                    price = None
        except Exception:
            price = None
        prices[name] = round(price, 2) if price is not None else None
    return prices


latest_prices = fetch_latest_prices(STOCKS)


# ----------------------------------------------------------------------------
# Google Sheets 整合（自動偵測：有金鑰用 Sheets，否則退回本地 CSV）
# ----------------------------------------------------------------------------

_GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_GS_WORKSHEET_HWM = "HWM紀錄"
_GS_WORKSHEET_REALIZED = "戰功存摺"


def _use_sheets() -> bool:
    """判斷是否啟用 Google Sheets（需要在 secrets.toml 設定 gcp_service_account）。"""
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


@st.cache_resource
def _gs_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=_GS_SCOPES
    )
    return gspread.authorize(creds)


def _gs_spreadsheet():
    return _gs_client().open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])


def load_data(path_or_sheet: str, columns: list, sheet_tab: str = "") -> pd.DataFrame:
    """讀取資料：有 Google Sheets 設定則從 Sheets 讀，否則讀本地 CSV。"""
    if _use_sheets() and sheet_tab:
        try:
            sh = _gs_spreadsheet()
            try:
                ws = sh.worksheet(sheet_tab)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=sheet_tab, rows=1000, cols=len(columns))
                ws.append_row(columns)
                return pd.DataFrame(columns=columns)
            records = ws.get_all_records()
            if not records:
                return pd.DataFrame(columns=columns)
            df = pd.DataFrame(records)
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            return df[columns]
        except Exception as e:
            st.warning("Google Sheets 讀取失敗，退回本地 CSV：" + str(e))
    # 本地 CSV 退回
    if os.path.exists(path_or_sheet):
        try:
            df = pd.read_csv(path_or_sheet)
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            return df[columns]
        except Exception:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)


def save_data(df: pd.DataFrame, path_or_sheet: str, columns: list, sheet_tab: str = ""):
    """寫入資料：有 Google Sheets 設定則寫 Sheets，否則寫本地 CSV。"""
    if _use_sheets() and sheet_tab:
        try:
            sh = _gs_spreadsheet()
            try:
                ws = sh.worksheet(sheet_tab)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=sheet_tab, rows=1000, cols=len(columns))
            ws.clear()
            ws.append_row(columns)
            for _, row in df.iterrows():
                ws.append_row([str(row.get(col, "")) for col in columns])
            return
        except Exception as e:
            st.warning("Google Sheets 寫入失敗，退回本地 CSV：" + str(e))
    df.to_csv(path_or_sheet, index=False)


with st.container(border=True, key="panel_hwm"):
    st.markdown("<h3>替身數值面板：最高淨值黃金</h3>", unsafe_allow_html=True)
    hwm_df = load_data(HWM_LOG_PATH, HWM_COLUMNS, sheet_tab=_GS_WORKSHEET_HWM)
    if not hwm_df.empty and hwm_df["歷史最高損益HWM"].notna().any():
        last_row = hwm_df.iloc[-1]
        current_hwm = float(last_row["歷史最高損益HWM"])
        raw_hwm_date = last_row.get("創高日期")
        if pd.isna(raw_hwm_date) or not str(raw_hwm_date).strip():
            raw_hwm_date = last_row.get("日期")
        current_hwm_date = str(raw_hwm_date) if pd.notna(raw_hwm_date) else None
    else:
        current_hwm = 0.0
        current_hwm_date = None
    total_points = float(hwm_df["本期新增氣韻點數"].sum()) if not hwm_df.empty else 0.0
    if current_hwm_date:
        try:
            hwm_date_display = date.fromisoformat(str(current_hwm_date)).strftime("%Y/%m/%d")
        except ValueError:
            hwm_date_display = str(current_hwm_date)
    else:
        hwm_date_display = "—"
    st.markdown(
        wrap_with_panel(
            stat_block("目前歷史最高未實現損益（HWM）", "{:,.0f} 元".format(current_hwm))
            + "<div class='ryo-label' style='margin-top:0.8rem;'>創高日期</div>"
            + "<div class='ryo-value' style='font-size:1.1rem;'>" + hwm_date_display + "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        wrap_with_panel(stat_block("累積黃金", "{:,.1f} 點".format(total_points))),
        unsafe_allow_html=True,
    )
    pnl_input = st.number_input(
        "請輸入券商當前題示的「總未實現損益金額」（元）",
        value=0.0, step=1000.0, format="%.0f",
    )
    if st.button("結算本月黃金"):
        today_str = date.today().isoformat()
        if pnl_input > current_hwm:
            new_points = (pnl_input - current_hwm) * 0.10
            new_hwm = pnl_input
            new_hwm_date = today_str
        else:
            new_points = 0.0
            new_hwm = current_hwm
            new_hwm_date = current_hwm_date if current_hwm_date else today_str
        new_row = pd.DataFrame([{
            "日期": today_str,
            "本期未實現損益": pnl_input,
            "歷史最高損益HWM": new_hwm,
            "創高日期": new_hwm_date,
            "本期新增氣韻點數": new_points,
        }])
        hwm_df = pd.concat([hwm_df, new_row], ignore_index=True)
        save_data(hwm_df, HWM_LOG_PATH, HWM_COLUMNS, sheet_tab=_GS_WORKSHEET_HWM)
        if new_points > 0:
            st.success("創新高！本次新增氣韻點數：{:,.1f} 點（新 HWM：{:,.0f} 元）".format(new_points, new_hwm))
        else:
            st.info("本期損益未超越歷史最高紀錄（{:,.0f} 元），本期新增氣韻點數為 0。".format(current_hwm))
        st.rerun()
    if not hwm_df.empty:
        with st.expander("歷史黃金紀錄"):
            st.dataframe(hwm_df.sort_values("日期", ascending=False), use_container_width=True, hide_index=True)


with st.container(border=True, key="panel_zeroshare"):
    st.markdown("<h3>零股購買力試算</h3>", unsafe_allow_html=True)
    cash_amount = st.number_input(
        "預計投入的法幣現金總額（元）",
        min_value=0.0, value=10000.0, step=1000.0, format="%.0f",
    )
    cols = st.columns(2)
    for col, (name, code) in zip(cols, STOCKS.items()):
        with col:
            price = latest_prices.get(name)
            if price:
                shares = int(cash_amount // price)
                card = (
                    "<div class='ryo-label' style='font-size:1.05rem;'>" + name + "（" + code + "）</div>"
                    + stat_block("即時股價", "{:,.2f} 元".format(price), size="1.4rem")
                    + stat_block("可購入股數（零股）", "{:,} 股".format(shares), size="2rem")
                )
            else:
                card = (
                    "<div class='ryo-label' style='font-size:1.05rem;'>" + name + "（" + code + "）</div>"
                    "<div class='ryo-value' style='font-size:1rem;'>即時股價讀取失敗</div>"
                )
            st.markdown(wrap_with_panel(card), unsafe_allow_html=True)


with st.container(border=True, key="panel_realized"):
    st.markdown("<h3>歷史戰功軌跡</h3>", unsafe_allow_html=True)
    realized_df = load_data(REALIZED_LOG_PATH, REALIZED_COLUMNS, sheet_tab=_GS_WORKSHEET_REALIZED)
    if not realized_df.empty:
        realized_df["已實現獲利金額"] = pd.to_numeric(
            realized_df["已實現獲利金額"], errors="coerce"
        ).fillna(0)
        total_realized = float(realized_df["已實現獲利金額"].sum())
    else:
        total_realized = 0.0
    st.markdown(
        wrap_with_panel(stat_block("歷史已落袋總利潤", "{:,.0f} 元".format(total_realized), size="2.4rem")),
        unsafe_allow_html=True,
    )
    with st.form("realized_profit_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            settle_date = st.date_input("結算日期", value=date.today())
        with col2:
            target = st.selectbox("標的", list(STOCKS.keys()))
        with col3:
            profit_amount = st.number_input("已實現獲利金額（元）", step=1000.0, format="%.0f")
        submitted = st.form_submit_button("記錄這筆戰功")
        if submitted:
            new_record = pd.DataFrame([{
                "結算日期": settle_date.isoformat(),
                "標的": target,
                "已實現獲利金額": profit_amount,
            }])
            realized_df = pd.concat([realized_df, new_record], ignore_index=True)
            save_data(realized_df, REALIZED_LOG_PATH, REALIZED_COLUMNS, sheet_tab=_GS_WORKSHEET_REALIZED)
            st.success("已記錄此筆戰功。")
            st.rerun()
    if not realized_df.empty:
        sorted_df = realized_df.copy()
        sorted_df["_sort_date"] = pd.to_datetime(sorted_df["結算日期"], errors="coerce")
        sorted_df = sorted_df.sort_values("_sort_date", ascending=False)
        lines = []
        for _, row in sorted_df.iterrows():
            raw_date = row["結算日期"]
            try:
                disp = date.fromisoformat(str(raw_date)).strftime("%Y/%m/%d")
            except ValueError:
                disp = str(raw_date)
            lines.append(disp + " | " + str(row["標的"]) + " | 獲利：" + "{:,.0f} 元".format(row["已實現獲利金額"]))
        st.markdown(
            wrap_with_panel("<div class='ryo-list'>" + "<br>".join(lines) + "</div>"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            wrap_with_panel("<div class='ryo-list'>尚無已實現獲利紀錄。</div>"),
            unsafe_allow_html=True,
        )
