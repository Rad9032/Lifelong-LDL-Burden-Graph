import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="LDL Burden Tracker", layout="wide")

st.title("🫀 Lifelong LDL Burden Calculator")

# --- UNIT TOGGLE ---
unit_choice = st.radio("Select Units:", ["mmol/L", "mg/dL"], horizontal=True)
is_mgdl = unit_choice == "mg/dL"

unit_label = "mg/dL" if is_mgdl else "mmol/L"
burden_unit = f"{unit_label} · yr"
plaque_limit = 5000 if is_mgdl else 130
ha_limit = 8000 if is_mgdl else 190

# --- SIDEBAR: PERSONAL INFORMATION ---
st.sidebar.header("Personal Information")
dob = st.sidebar.date_input(
    "Date of Birth", 
    value=datetime(1970, 1, 1), 
    min_value=datetime(1900, 1, 1), 
    max_value=datetime.now()
)

default_target = 70.0 if is_mgdl else 1.8
target_ldl = st.sidebar.number_input(f"Target LDL ({unit_label})", value=default_target, step=1.0 if is_mgdl else 0.1)

# --- DATA INPUT ---
if 'input_data' not in st.session_state:
    st.session_state.input_data = pd.DataFrame([
        {"Date": dob, "LDL": 0.70 if not is_mgdl else 27.0},
        {"Date": datetime(2010, 1, 1), "LDL": 3.50 if not is_mgdl else 135.0},
        {"Date": datetime.now().date(), "LDL": 2.50 if not is_mgdl else 97.0}
    ])

st.subheader(f"1. Enter LDL Lab History ({unit_label})")
st.info("ℹ️ **Row 1 Note:** Humans are born with an average LDL of **0.7 mmol/L (27 mg/dL)**. This is your baseline.\n\n"
        "💡 **How to Edit:** You can paste from Excel, add new rows at the bottom, or select a row and press 'Delete' on your keyboard.")

# Display Data Editor - Columns: Date, LDL, Age at Test (Age at Test starts empty here)
edited_df = st.data_editor(
    st.session_state.input_data[['Date', 'LDL']], 
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Date": st.column_config.DateColumn("Date of Test", required=True),
        "LDL": st.column_config.NumberColumn(f"LDL ({unit_label})", required=True),
    }
)

# --- CALCULATIONS ---
def solve_for_age(calc_df, limit_mmol, last_age, last_exp, target_mmol):
    reached_past = calc_df[calc_df['Exposure_mmol'] >= limit_mmol]
    if not reached_past.empty:
        idx = reached_past.index[0]
        if idx == 0: return calc_df.loc[0, 'Age'], "Historical"
        age_start, age_end = calc_df.loc[idx-1, 'Age'], calc_df.loc[idx, 'Age']
        exp_start, exp_end = calc_df.loc[idx-1, 'Exposure_mmol'], calc_df.loc[idx, 'Exposure_mmol']
        exact_age = age_start + (limit_mmol - exp_start) * (age_end - age_start) / (exp_end - exp_start)
        return exact_age, "Historical"
    else:
        years_to_go = (limit_mmol - last_exp) / target_mmol
        return last_age + years_to_go, "Projected"

try:
    # 1. Clean Data
    df_clean = edited_df.dropna(subset=['Date', 'LDL']).copy()
    df_clean['Date'] = pd.to_datetime(df_clean['Date']).dt.date
    df_clean = df_clean.sort_values("Date").reset_index(drop=True)
    
    # 2. Add Age at Test to the Cleaned Data (Calculated dynamically)
    df_clean['Age at Test'] = df_clean['Date'].apply(lambda x: round((x - dob).days / 365.25, 1))
    
    # 3. Handle Units
    if is_mgdl:
        df_clean['LDL_mmol'] = df_clean['LDL'] / 38.67
        target_mmol = target_ldl / 38.67
    else:
        df_clean['LDL_mmol'] = df_clean['LDL']
        target_mmol = target_ldl

    # 4. Exposure Math
    df_clean['Age'] = df_clean['Age at Test']
    df_clean['Exposure_mmol'] = 0.0
    for i in range(1, len(df_clean)):
        yrs = df_clean.loc[i, 'Age'] - df_clean.loc[i-1, 'Age']
        avg_ldl = (df_clean.loc[i, 'LDL_mmol'] + df_clean.loc[i-1, 'LDL_mmol']) / 2
        df_clean.loc[i, 'Exposure_mmol'] = df_clean.loc[i-1, 'Exposure_mmol'] + (yrs * avg_ldl)
    
    last_age = df_clean.iloc[-1]['Age']
    last_exp = df_clean.iloc[-1]['Exposure_mmol']
    
    pl_age, pl_stat = solve_for_age(df_clean, 130, last_age, last_exp, target_mmol)
    ha_age, ha_stat = solve_for_age(df_clean, 190, last_age, last_exp, target_mmol)
    
    # Show the table with calculated ages right before the results
    st.write("**Calculated History:**")
    st.dataframe(df_clean[['Date', 'LDL', 'Age at Test']], use_container_width=True)

    # --- OUTPUT DASHBOARD ---
    st.subheader("2. Analysis Results")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(f"Plaque Threshold ({plaque_limit})", f"Age {pl_age:.1f}")
        if pl_stat == "Historical": st.warning("⚠️ **Threshold Reached**")
        else: st.success("✅ Predicted")
    with c2:
        st.metric(f"Heart Attack Threshold ({ha_limit})", f"Age {ha_age:.1f}")
        if ha_stat == "Historical": st.error("🚨 **Threshold Reached**")
        else: st.success("✅ Predicted")
    with c3:
        curr_burden = last_exp * (38.67 if is_mgdl else 1.0)
        st.metric("Current Total Burden", f"{curr_burden:.0f} {burden_unit}")

    # --- THE GRAPH ---
    fig = go.Figure()
    graph_y = df_clean['Exposure_mmol'] * (38.67 if is_mgdl else 1.0)
    fig.add_trace(go.Scatter(x=df_clean['Age'], y=graph_y, mode='lines+markers', name="Your Burden", line=dict(color='#4285F4', width=4)))
    
    fig.add_hline(y=plaque_limit, line=dict(color='#FBBC04', dash='dash', width=2), annotation_text="Plaque Limit", annotation_position="top left")
    fig.add_hline(y=ha_limit, line=dict(color='#EA4335', dash='dash', width=2), annotation_text="Heart Attack Limit", annotation_position="top left")
    
    fig.update_layout(xaxis_title="Age (Years)", yaxis_title=f"Cumulative Exposure ({burden_unit})", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    fig.update_xaxes(showgrid=True, gridcolor='Gray')
    fig.update_yaxes(showgrid=True, gridcolor='Gray')
    
    st.plotly_chart(fig, use_container_width=True)

except Exception:
    st.info("Please enter your Date of Birth and LDL entries to calculate results.")
