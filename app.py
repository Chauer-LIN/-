
import streamlit as st
import pandas as pd


st.set_page_config(page_title="房產淨利試算", layout="wide")

st.title("🏡 個人專屬：房產賣出淨利試算器")

# --- Sidebar: 基礎設定 ---
st.sidebar.header("1. 基本交易設定")
sell_price = st.sidebar.number_input("預估賣出總價 (元)", value=8000000, step=100000)
buy_price = st.sidebar.number_input("原始買入總價 (元)", value=6000000, step=100000)
renovation_cost = st.sidebar.number_input("可扣抵成本 (裝潢/修繕) (元)", value=500000, step=50000)

st.sidebar.markdown("---")
st.sidebar.header("2. 稅費與規費設定")
holding_period_tax = st.sidebar.selectbox("持有期間 (房地合一稅率)", 
                                        options=["2年內 (45%)", "2~5年 (35%)", "5~10年 (20%)", "10年以上 (15%)"], 
                                        index=1)
tax_rate_map = {"2年內 (45%)": 0.45, "2~5年 (35%)": 0.35, "5~10年 (20%)": 0.20, "10年以上 (15%)": 0.15}
tax_rate = tax_rate_map[holding_period_tax]

agency_fee_pct = st.sidebar.number_input("仲介服務費 (%)", value=4.0, step=0.5) / 100
escrow_fee = sell_price * 0.00015 # 履保費通常為成交價萬分之三，買賣各半
document_fee = st.sidebar.number_input("塗銷代書費 (元)", value=3000, step=500)
land_value_increment_tax = st.sidebar.number_input("土地增值稅預估 (元)", value=50000, step=10000)


# --- Main Content: 貸款動態試算 ---
st.header("房貸剩餘成本試算")
col1, col2, col3, col4 = st.columns(4)
with col1:
    loan_amount = st.number_input("原始貸款總額 (元)", value=5640000, step=100000)
with col2:
    total_months = st.number_input("貸款總期數 (月)", value=360, step=12)
with col3:
    grace_period = st.number_input("寬限期 (月)", value=36, step=12)
with col4:
    months_paid = st.number_input("目前已繳納總期數 (月)", value=24, step=1)

st.subheader("利率變動設定")
st.write("請依時間順序輸入利率變動。例如：第1期開始 2.26%，第25期開始 2.41%。")

# Dynamic rate input
if 'rate_changes' not in st.session_state:
    st.session_state.rate_changes = [{'start_month': 1, 'rate_pct': 2.26}]

def add_rate_change():
    st.session_state.rate_changes.append({'start_month': st.session_state.rate_changes[-1]['start_month'] + 12, 'rate_pct': 2.41})

def remove_rate_change(index):
    st.session_state.rate_changes.pop(index)

for i, rate_change in enumerate(st.session_state.rate_changes):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        rate_change['start_month'] = st.number_input(f"起始期數", value=rate_change['start_month'], step=1, key=f"start_{i}")
    with c2:
        rate_change['rate_pct'] = st.number_input(f"年利率 (%)", value=float(rate_change['rate_pct']), step=0.01, format="%.3f", key=f"rate_{i}")
    with c3:
        if i > 0:
            st.button("移除", key=f"remove_{i}", on_click=remove_rate_change, args=(i,))

st.button("➕ 新增利率變動", on_click=add_rate_change)

# --- Calculate Loan Amortization ---
def calculate_amortization(loan_amount, total_months, grace_period, rate_changes):
    # Sort rate changes by start month
    rate_changes = sorted(rate_changes, key=lambda x: x['start_month'])
    
    schedule = []
    current_balance = loan_amount
    
    for month in range(1, total_months + 1):
        # Determine current rate
        current_rate_pct = rate_changes[0]['rate_pct']
        for rc in rate_changes:
            if month >= rc['start_month']:
                current_rate_pct = rc['rate_pct']
        
        monthly_rate = (current_rate_pct / 100) / 12
        interest_payment = current_balance * monthly_rate
        
        if month <= grace_period:
            principal_payment = 0
            monthly_payment = interest_payment
        else:
            # Need to recalculate PMT based on remaining balance, remaining periods, and current rate
            # remaining_periods = total_months - month + 1 
            # However, if rate just changed, we recalculate PMT. 
            # To be accurate at any point, if it's not a grace period, PMT = P * r(1+r)^n / ((1+r)^n - 1)
            remaining_periods = total_months - month + 1
            if monthly_rate > 0:
                monthly_payment = current_balance * (monthly_rate * (1 + monthly_rate)**remaining_periods) / ((1 + monthly_rate)**remaining_periods - 1)
            else:
                monthly_payment = current_balance / remaining_periods
                
            principal_payment = monthly_payment - interest_payment
            
        current_balance -= principal_payment
        
        schedule.append({
            "期數": month,
            "年利率(%)": current_rate_pct,
            "當期還本金額": round(principal_payment),
            "當期利息金額": round(interest_payment),
            "月付本息金額": round(monthly_payment),
            "本金餘額": round(current_balance) if current_balance > 0 else 0
        })
        
    return pd.DataFrame(schedule)

df_schedule = calculate_amortization(loan_amount, total_months, grace_period, st.session_state.rate_changes)

# Get remaining balance at 'months_paid'
if months_paid > 0 and months_paid <= total_months:
    remaining_loan_balance = df_schedule.loc[months_paid - 1, "本金餘額"]
else:
    remaining_loan_balance = loan_amount

st.markdown("### 攤還表明細 (部分)")
with st.expander("點擊展開查看詳細攤還表"):
    st.dataframe(df_schedule, use_container_width=True)
    
st.info(f"👉 賣出時（第 {months_paid} 期繳完），剩餘房貸本金約為： **{int(remaining_loan_balance):,} 元**")

# --- Final Calculation & Dashboard ---
st.header("最終淨利結算")

# Calculate Capital Gains Tax (房地合一稅)
agency_fee_amount = sell_price * agency_fee_pct
total_selling_costs = agency_fee_amount + escrow_fee + document_fee

# 課稅所得 = 賣價 - 買價 - 裝潢 - 賣出費用 - 土地漲價總數額 (簡化假設無)
taxable_income = max(0, sell_price - buy_price - renovation_cost - total_selling_costs)
capital_gains_tax = taxable_income * tax_rate

# 實際到手現金 = 賣出總價 - 剩餘房貸本金 - 交易規費 - 房地合一稅 - 土地增值稅
net_profit = sell_price - remaining_loan_balance - total_selling_costs - capital_gains_tax - land_value_increment_tax

col_a, col_b = st.columns([1, 1])

with col_a:
    st.markdown("#### 收入與支出明細")
    st.write(f"**預估賣出總價:** {int(sell_price):,} 元")
    st.write(f"**扣除：剩餘房貸本金:** - {int(remaining_loan_balance):,} 元")
    st.write(f"**扣除：仲介服務費 ({agency_fee_pct*100}%):** - {int(agency_fee_amount):,} 元")
    st.write(f"**扣除：履約保證費 (買賣各半):** - {int(escrow_fee):,} 元")
    st.write(f"**扣除：塗銷代書費:** - {int(document_fee):,} 元")
    st.write(f"**扣除：預估土地增值稅:** - {int(land_value_increment_tax):,} 元")
    st.write(f"**扣除：預估房地合一稅 ({tax_rate*100}%):** - {int(capital_gains_tax):,} 元")
    st.markdown("---")
    st.markdown(f"### 🎉 實際到手淨利: <span style='color:green'>{int(net_profit):,} 元</span>", unsafe_allow_html=True)

with col_b:
    st.markdown("#### 資金流向比例")
    pie_data = {
        "分類": ["剩餘房貸", "仲介與規費", "稅賦 (房地合一+土增)", "到手淨利"],
        "金額": [
            remaining_loan_balance, 
            total_selling_costs, 
            capital_gains_tax + land_value_increment_tax, 
            max(0, net_profit)
        ]
    }
    df_pie = pd.DataFrame(pie_data)
    st.bar_chart(df_pie, x="分類", y="金額", color="分類") # Use bar chart for simplicity in base streamlit, or could use Altair/Plotly
