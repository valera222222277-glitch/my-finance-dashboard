import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# --- Настройка страницы ---
st.set_page_config(page_title="Мой Капитал", layout="wide", page_icon="💰")

# --- Функция получения курса доллара (ЦБ РФ) ---
@st.cache_data(ttl=3600)
def get_usd_rate():
    try:
        resp = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5)
        data = resp.json()
        return data["Valute"]["USD"]["Value"]
    except:
        return 80.56

# --- Загрузка данных ---
@st.cache_data
def load_data():
    accounts = pd.read_csv("data/accounts.csv")
    history = pd.read_csv("data/history.csv")
    return accounts, history

accounts_df, history_df = load_data()
usd_rate = get_usd_rate()

# --- Расчёты ---
total_capital = accounts_df["balance"].sum()
capital_in_usd = total_capital / usd_rate
working_capital = accounts_df[accounts_df["works_for_income"] == True]["balance"].sum()
percent_working = (working_capital / total_capital) * 100

# --- Верхняя панель ---
st.title("📊 Октябрь 2026")
st.caption(f"Курс $ = {usd_rate:.2f} ₽")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Капитал", f"{total_capital:,.0f} ₽")
col2.metric("Работает на %", f"{working_capital:,.0f} ₽", f"{percent_working:.1f}%")
col3.metric("В долларах", f"${capital_in_usd:,.0f}", f"курс {usd_rate:.2f}")
col4.metric("Цель месяца", "6 555 406 ₽", "110.7%")
col5.metric("Цель к 2030", "20 000 000 ₽", "36.3%")

st.divider()

# --- Две колонки ---
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("Счета")
    for group in accounts_df["group"].unique():
        group_df = accounts_df[accounts_df["group"] == group]
        group_sum = group_df["balance"].sum()
        with st.expander(f"{group} — {group_sum:,.0f} ₽", expanded=True):
            for _, row in group_df.iterrows():
                icon = "🟢" if row["works_for_income"] else "⚪"
                st.markdown(f"{icon} **{row['name']}** — `{row['balance']:,.0f} ₽`")

with right_col:
    st.subheader("Капитал по месяцам")
    st.dataframe(
        history_df.style.format({
            "capital": "{:,.0f} ₽",
            "gain": "{:+,.0f} ₽",
            "percent": "{:+.1f}%",
            "deposit": "{:,.0f} ₽",
            "target": "{:,.0f} ₽"
        }),
        use_container_width=True,
        hide_index=True
    )
    fig = px.line(history_df, x="month", y="capital", title="Динамика капитала",
                  markers=True, labels={"month": "Месяц", "capital": "Капитал (₽)"})
    fig.update_layout(template="plotly_white", height=350)
    st.plotly_chart(fig, use_container_width=True)