import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# --- Настройка страницы ---
st.set_page_config(page_title="Мой Капитал", layout="wide", page_icon="💰")

# --- Функция получения курса доллара ---
@st.cache_data(ttl=3600)
def get_usd_rate():
    try:
        resp = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5)
        data = resp.json()
        return data["Valute"]["USD"]["Value"]
    except:
        return 80.56

# --- Загрузка и СОХРАНЕНИЕ данных ---
def load_data():
    accounts = pd.read_csv("data/accounts.csv")
    history = pd.read_csv("data/history.csv")
    return accounts, history

def save_data(df):
    # Сохраняем обновленный датафрейм обратно в CSV
    df.to_csv("data/accounts.csv", index=False)

accounts_df, history_df = load_data()
usd_rate = get_usd_rate()

# ==========================================
# БОКОВАЯ ПАНЕЛЬ (Sidebar) ДЛЯ РЕДАКТИРОВАНИЯ
# ==========================================
with st.sidebar:
    st.header("⚙️ Управление счетами")
    
    # 1. Форма для изменения существующего счета
    with st.form("edit_account_form"):
        st.subheader("Изменить баланс")
        # Выпадающий список всех счетов
        account_to_edit = st.selectbox("Выберите счет", accounts_df["name"].tolist())
        # Находим текущий баланс для выбранного счета
        current_balance = accounts_df[accounts_df["name"] == account_to_edit]["balance"].values[0]
        # Поле ввода новой суммы
        new_balance = st.number_input("Новый баланс (₽)", value=float(current_balance), step=1000.0)
        
        if st.form_submit_button("Обновить счет"):
            # Меняем значение в датафрейме
            accounts_df.loc[accounts_df["name"] == account_to_edit, "balance"] = new_balance
            # Сохраняем в файл
            save_data(accounts_df)
            st.success(f"Счет '{account_to_edit}' обновлен!")
            st.rerun() # Перезагружаем страницу, чтобы увидеть новые цифры

    st.divider()

    # 2. Форма для добавления нового счета
    with st.form("add_account_form"):
        st.subheader("Добавить новый счет")
        new_name = st.text_input("Название (например, Альфа-Банк)")
        new_group = st.selectbox("Группа", ["Накопительные счета", "Вклады", "Брокерские счета", "Криптовалюта"])
        new_bal = st.number_input("Сумма (₽)", step=1000.0, value=0.0)
        new_works = st.checkbox("Приносит доход (%)", value=True)
        
        if st.form_submit_button("Создать счет"):
            if new_name:
                # Создаем новую строку
                new_row = pd.DataFrame([{
                    "group": new_group, 
                    "name": new_name, 
                    "balance": new_bal, 
                    "currency": "RUB", 
                    "works_for_income": new_works
                }])
                # Добавляем к старому датафрейму
                accounts_df = pd.concat([accounts_df, new_row], ignore_index=True)
                save_data(accounts_df)
                st.success(f"Счет '{new_name}' добавлен!")
                st.rerun()
            else:
                st.error("Введите название счета!")

# ==========================================
# ОСНОВНОЙ ЭКРАН (Дашборд)
# ==========================================
total_capital = accounts_df["balance"].sum()
capital_in_usd = total_capital / usd_rate
working_capital = accounts_df[accounts_df["works_for_income"] == True]["balance"].sum()
percent_working = (working_capital / total_capital) * 100 if total_capital > 0 else 0

st.title("📊 Октябрь 2026")
st.caption(f"Курс $ = {usd_rate:.2f} ₽")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Капитал", f"{total_capital:,.0f} ₽")
col2.metric("Работает на %", f"{working_capital:,.0f} ₽", f"{percent_working:.1f}%")
col3.metric("В долларах", f"${capital_in_usd:,.0f}", f"курс {usd_rate:.2f}")
col4.metric("Цель месяца", "6 555 406 ₽", "110.7%")
col5.metric("Цель к 2030", "20 000 000 ₽", "36.3%")

st.divider()

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