import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import datetime # <--- ДОБАВИТЬ ЭТО

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
    df.to_csv("data/accounts.csv", index=False)

accounts_df, history_df = load_data()
usd_rate = get_usd_rate()
# ==========================================
# ИНТЕГРАЦИЯ С Т-ИНВЕСТИЦИЯМИ
# ==========================================
# Безопасно достаем токен
try:
    TBANK_TOKEN = st.secrets["TBANK_TOKEN"]
except:
    TBANK_TOKEN = None

def get_coupons_for_bond(figi, from_date, to_date):
    """Запрашивает купоны по облигации через API Т-Банка"""
    url = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"
    headers = {
        "Authorization": f"Bearer {TBANK_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "instrumentId": figi,
        "from": from_date + "T00:00:00Z",
        "to": to_date + "T23:59:59Z"
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Переводим ответ в удобную таблицу
            coupons = []
            for event in data.get("events", []):
                amount = float(event["payOneBond"]["units"]) + (float(event["payOneBond"]["nano"]) / 1_000_000_000)
                coupons.append({
                    "Дата": event["couponDate"][:10],
                    "Сумма (₽)": amount,
                    "Валюта": event["payOneBond"]["currency"]
                })
            return pd.DataFrame(coupons)
        else:
            st.error(f"Ошибка API: {response.status_code}. Проверьте токен.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Ошибка соединения: {e}")
        return pd.DataFrame()

# ==========================================
# БОКОВАЯ ПАНЕЛЬ (Управление)
# ==========================================
with st.sidebar:
    st.header("⚙️ Управление счетами")
    
    # Создаем три вкладки в сайдбаре
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Добавить", "✏️ Изменить", "🗑️ Удалить", "📈 Купоны"])
    
    # Вкладка 1: Добавление
    with tab1:
        with st.form("add_account_form"):
            new_name = st.text_input("Название счета")
            new_group = st.selectbox("Группа", ["Накопительные счета", "Вклады", "Брокерские счета", "Криптовалюта"])
            new_bal = st.number_input("Сумма (₽)", step=1000.0, value=0.0)
            new_works = st.checkbox("Приносит доход (%)", value=True)
            
            if st.form_submit_button("Создать"):
                if new_name:
                    new_row = pd.DataFrame([{
                        "group": new_group, "name": new_name, "balance": new_bal, 
                        "currency": "RUB", "works_for_income": new_works
                    }])
                    accounts_df = pd.concat([accounts_df, new_row], ignore_index=True)
                    save_data(accounts_df)
                    st.success(f"Добавлен: {new_name}")
                    st.rerun()
                else:
                    st.error("Введите название!")

    # Вкладка 2: Изменение баланса
    with tab2:
        with st.form("edit_account_form"):
            account_to_edit = st.selectbox("Выберите счет", accounts_df["name"].tolist())
            current_balance = accounts_df[accounts_df["name"] == account_to_edit]["balance"].values[0]
            new_balance = st.number_input("Новый баланс (₽)", value=float(current_balance), step=1000.0)
            
            if st.form_submit_button("Обновить"):
                accounts_df.loc[accounts_df["name"] == account_to_edit, "balance"] = new_balance
                save_data(accounts_df)
                st.success(f"Обновлен: {account_to_edit}")
                st.rerun()

    # Вкладка 3: Удаление счета
    with tab3:
        st.write("Удаление счета из списка.")
        account_to_delete = st.selectbox("Кого удаляем?", accounts_df["name"].tolist(), key="del_select")
        
        if st.button("🗑️ Удалить счет", type="primary"):
            # Фильтруем датафрейм, оставляя всех, кроме выбранного
            accounts_df = accounts_df[accounts_df["name"] != account_to_delete]
            save_data(accounts_df)
            st.success(f"Удален: {account_to_delete}")
            st.rerun()
    # Вкладка 4: Купоны из API
    with tab4:
        st.write("Получение графика купонов напрямую из Т-Инвестиций.")
        
        if not TBANK_TOKEN:
            st.warning("⚠️ Токен не найден. Добавьте файл `.streamlit/secrets.toml` и вставьте туда токен.")
        else:
            # ВАЖНО: Сюда нужно вписать FIGI ваших облигаций. 
            # Пример: FIGI ОФЗ или корпоративной облигации
            figi_input = st.text_input("Введите FIGI облигации (например, TCSTRP1072)", value="TCSTRP1072")
            
            if st.button("Загрузить купоны"):
                today = datetime.date.today().strftime("%Y-%m-%d")
                next_year = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                
                with st.spinner("Запрашиваем данные у брокера..."):
                    coupons_df = get_coupons_for_bond(figi_input, today, next_year)
                    
                if not coupons_df.empty:
                    st.success(f"Найдено {len(coupons_df)} выплат")
                    st.dataframe(coupons_df, use_container_width=True)
                    
                    # График купонов
                    fig_coupons = px.bar(coupons_df, x="Дата", y="Сумма (₽)", title="График купонных выплат")
                    st.plotly_chart(fig_coupons, use_container_width=True)
                else:
                    st.info("По этой бумаге нет данных или FIGI введен неверно.")
                    
# ==========================================
# ОСНОВНОЙ ЭКРАН
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