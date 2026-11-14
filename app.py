import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import datetime
import urllib3
from streamlit_calendar import calendar

# Отключаем предупреждения SSL (нужно для работы с API Т-Банка на Render)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
try:
    TBANK_TOKEN = st.secrets["TBANK_TOKEN"]
except:
    TBANK_TOKEN = None

def get_coupons_for_bond(figi, from_date, to_date):
    url = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"
    headers = {"Authorization": f"Bearer {TBANK_TOKEN}", "Content-Type": "application/json"}
    payload = {"instrumentId": figi, "from": from_date + "T00:00:00Z", "to": to_date + "T23:59:59Z"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            coupons = []
            for event in data.get("events", []):
                amount = float(event["payOneBond"]["units"]) + (float(event["payOneBond"]["nano"]) / 1_000_000_000)
                coupons.append({"date": event["couponDate"][:10], "amount": amount})
            return coupons
        else:
            return []
    except Exception as e:
        st.error(f"Ошибка соединения: {e}")
        return []

def fetch_all_coupons():
    if not TBANK_TOKEN: return []
    all_events = []
    try:
        url_acc = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
        resp_acc = requests.post(url_acc, headers={"Authorization": f"Bearer {TBANK_TOKEN}"}, json={}, verify=False)
        
        if resp_acc.status_code == 200:
            accounts = resp_acc.json().get("accounts", [])
            if accounts:
                acc_id = accounts[0]["id"]
                url_port = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio"
                resp_port = requests.post(url_port, headers={"Authorization": f"Bearer {TBANK_TOKEN}"}, json={"accountId": acc_id}, verify=False)
                
                if resp_port.status_code == 200:
                    positions = resp_port.json().get("positions", [])
                    for pos in positions:
                        if pos.get("instrumentType") == "bond":
                            figi = pos["figi"]
                            name = pos.get("ticker", figi)
                            today = datetime.date.today().strftime("%Y-%m-%d")
                            next_year = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                            coupons = get_coupons_for_bond(figi, today, next_year)
                            for c in coupons:
                                all_events.append({
                                    "title": f"{name}: {c['amount']:.2f} ₽",
                                    "start": c["date"],
                                    "allDay": True
                                })
    except Exception as e:
        st.error(f"Ошибка загрузки купонов: {e}")
    return all_events
def get_dividends_for_share(figi, from_date, to_date):
    url = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetDividends"
    headers = {"Authorization": f"Bearer {TBANK_TOKEN}", "Content-Type": "application/json"}
    payload = {"instrumentId": figi, "from": from_date + "T00:00:00Z", "to": to_date + "T23:59:59Z"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            dividends = []
            for div in data.get("dividends", []):
                # Сумма на одну акцию
                amount = float(div["dividendNet"]["units"]) + (float(div["dividendNet"]["nano"]) / 1_000_000_000)
                # Берем дату выплаты (paymentDate), если ее нет — дату фиксации (recordDate)
                pay_date = div.get("paymentDate") or div.get("recordDate")
                if pay_date:
                    dividends.append({"date": pay_date[:10], "amount": amount})
            return dividends
        else:
            return []
    except Exception as e:
        return []

def fetch_all_dividends():
    if not TBANK_TOKEN: return []
    all_events = []
    try:
        url_acc = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
        resp_acc = requests.post(url_acc, headers={"Authorization": f"Bearer {TBANK_TOKEN}"}, json={}, verify=False)
        
        if resp_acc.status_code == 200:
            accounts = resp_acc.json().get("accounts", [])
            if accounts:
                acc_id = accounts[0]["id"]
                url_port = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio"
                resp_port = requests.post(url_port, headers={"Authorization": f"Bearer {TBANK_TOKEN}"}, json={"accountId": acc_id}, verify=False)
                
                if resp_port.status_code == 200:
                    positions = resp_port.json().get("positions", [])
                    for pos in positions:
                        # Ищем именно АКЦИИ (share)
                        if pos.get("instrumentType") == "share":
                            figi = pos["figi"]
                            name = pos.get("ticker", figi)
                            today = datetime.date.today().strftime("%Y-%m-%d")
                            next_year = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                            divs = get_dividends_for_share(figi, today, next_year)
                            for d in divs:
                                all_events.append({
                                    "title": f"{name}: {d['amount']:.2f} ₽",
                                    "start": d["date"],
                                    "allDay": True
                                })
    except Exception as e:
        st.error(f"Ошибка загрузки дивидендов: {e}")
    return all_events
# ==========================================
# БОКОВАЯ ПАНЕЛЬ (Управление счетами)
# ==========================================
with st.sidebar:
    st.header("⚙️ Управление счетами")
    tab1, tab2, tab3 = st.tabs(["➕ Добавить", "✏️ Изменить", "🗑️ Удалить"])
    
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
        account_to_delete = st.selectbox("Кого удаляем?", accounts_df["name"].tolist(), key="del_select")
        if st.button("🗑️ Удалить счет", type="primary"):
            accounts_df = accounts_df[accounts_df["name"] != account_to_delete]
            save_data(accounts_df)
            st.success(f"Удален: {account_to_delete}")
            st.rerun()

# ==========================================
# ОСНОВНОЙ ЭКРАН (С ВЕРХНИМИ ВКЛАДКАМИ)
# ==========================================
total_capital = accounts_df["balance"].sum()
capital_in_usd = total_capital / usd_rate
working_capital = accounts_df[accounts_df["works_for_income"] == True]["balance"].sum()
percent_working = (working_capital / total_capital) * 100 if total_capital > 0 else 0

# Шапка сайта (как на скриншоте)
st.markdown("<h2 style='margin-bottom: 0;'>Сентябрь 2026</h2>", unsafe_allow_html=True)
st.caption(f"Курс $ = {usd_rate:.2f} ₽")

# ВЕРХНИЕ ВКЛАДКИ (Меню навигации)
# Мы создаем 4 вкладки: Обзор, Дивиденды (демо), Купоны (Календарь), История
tab_overview, tab_dividends, tab_coupons, tab_history = st.tabs([
    "📊 Обзор и Счета", 
    "💰 Дивиденды (в разработке)", 
    "📅 Купоны", 
    "📋 История"
])

# --- ВКЛАДКА 1: ОБЗОР ---
with tab_overview:
    # Верхние карточки
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Капитал", f"{total_capital:,.0f} ₽")
    col2.metric("Работает на %", f"{working_capital:,.0f} ₽", f"{percent_working:.1f}%")
    col3.metric("В долларах", f"${capital_in_usd:,.0f}", f"курс {usd_rate:.2f}")
    col4.metric("Цель месяца", "6 555 406 ₽", "110.7%")
    col5.metric("Цель к 2030", "20 000 000 ₽", "36.3%")
    
    st.divider()
    
    # Счета и График
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
        fig = px.line(history_df, x="month", y="capital", title="Динамика капитала",
                      markers=True, labels={"month": "Месяц", "capital": "Капитал (₽)"})
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)

# --- ВКЛАДКА 2: ДИВИДЕНДЫ (Заглушка для красоты) ---
with tab_dividends:
    st.subheader("Календарь дивидендов")
    if st.button("🔄 Обновить дивиденды", key="refresh_dividends", use_container_width=True):
        st.session_state['dividends_data'] = fetch_all_dividends()
    
    if 'dividends_data' not in st.session_state:
        st.session_state['dividends_data'] = []
        
    if st.session_state['dividends_data']:
        calendar_options = {
            "initialView": "dayGridMonth",
            "locale": "ru",
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"}
        }
        calendar(events=st.session_state['dividends_data'], options=calendar_options, key="main_dividends_calendar")
    else:
        st.info("Нажмите кнопку 'Обновить дивиденды', чтобы загрузить данные по акциям из вашего портфеля.")

# --- ВКЛАДКА 3: КУПОНЫ (ТОТ САМЫЙ КАЛЕНДАРЬ) ---
with tab_coupons:
    # Заголовок и кнопка обновления в одну строку
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("Календарь купонов")
    with col_btn:
        if st.button("🔄 Обновить", key="refresh_coupons", use_container_width=True):
            st.session_state['coupons_data'] = fetch_all_coupons()
    
    # Загружаем данные при первом входе, если их нет
    if 'coupons_data' not in st.session_state:
        st.session_state['coupons_data'] = []
        
    # Отображаем календарь
    if st.session_state['coupons_data']:
        calendar_options = {
            "initialView": "dayGridMonth",
            "locale": "ru",
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"}
        }
        calendar(events=st.session_state['coupons_data'], options=calendar_options, key="main_coupon_calendar")
    else:
        st.info("Нажмите кнопку 'Обновить', чтобы загрузить данные из Т-Инвестиций.")

# --- ВКЛАДКА 4: ИСТОРИЯ ---
with tab_history:
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