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
        {"Date": dob, "LDL": 0.70},
        {"Date": datetime(2010, 1, 1), "LDL": 3.50},
        {"Date": datetime.now().date(), "LDL": 2.50}
    ])

st.subheader(f"1. Enter LDL Lab History ({unit_label})")
st.info(f"ℹ️ **Note on Row 1:** Science shows humans are born with an average LDL of **0.7 mmol/L (approx. 27 mg/dL)**. This baseline is used to calculate your 'head start' on cholesterol exposure.")

# Pre-calculate Age for the display table
input_df = st.session_state.input_data.copy()
input_df['Date'] = pd.to_datetime(input_df['Date']).dt.date
input_df['Age at Test'] = input_df['Date'].apply(lambda x: round((x - dob).days / 365.25, 1))

edited_df = st.data_editor(
    input_df[['Date', 'Age at Test', 'LDL']], 
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Date": st.column_config.DateColumn("Date of Test", required=True),
        "Age at Test": st.column_config.NumberColumn("Age at Test", disabled=True, help="Calculated automatically from DOB"),
        "LDL": st.column_config.NumberColumn(f"LDL ({unit_label})", required=True)
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
    df_clean = edited_df.dropna(subset=['Date', 'LDL']).copy()
    df_clean['Date'] = pd.to_datetime(df_clean['Date']).dt.date
    df_clean = df_clean.sort_values("Date").reset_index(drop=True)
    
    if is_mgdl:
        df_clean['LDL_mmol'] = df_clean['LDL'] / 38.67
        target_mmol = target_ldl / 38.67
    else:
        df_clean['LDL_mmol'] = df_clean['LDL']
        target_mmol = target_ldl

    df_clean['Age'] = df_clean['Date'].apply(lambda x: (x - dob).days / 365.25)
    df_clean['Exposure_mmol'] = 0.0
    for i in range(1, len(df_clean)):
        yrs = df_clean.loc[i, 'Age'] - df_clean.loc[i-1, 'Age']
        avg_ldl = (df_clean.loc[i, 'LDL_mmol'] + df_clean.loc[i-1, 'LDL_mmol']) / 2
        df_clean.loc[i, 'Exposure_mmol'] = df_clean.loc[i-1, 'Exposure_mmol'] + (yrs * avg_ldl)
    
    last_age = df_clean.iloc[-1]['Age']
    last_exp = df_clean.iloc[-1]['Exposure_mmol']
    
    pl_age, pl_stat = solve_for_age(df_clean, 130, last_age, last_exp, target_mmol)
    ha_age, ha_stat = solve_for_age(df_clean, 190, last_age, last_exp, target_mmol)
    
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
    
    # Improved visibility for limit lines
    fig.add_hline(y=plaque_limit, line=dict(color='#FBBC04', dash='dash'), 
                  annotation_text="Plaque Limit", annotation_position="top left",
                  annotation_font=dict(color="white" if st.get_option("theme.base") == "dark" else "black"))
    fig.add_hline(y=ha_limit, line=dict(color='#EA4335', dash='dash'), 
                  annotation_text="Heart Attack Limit", annotation_position="top left",
                  annotation_font=dict(color="white" if st.get_option("theme.base") == "dark" else "black"))
    
    fig.update_layout(xaxis_title="Age (Years)", yaxis_title=f"Cumulative Exposure ({burden_unit})", plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

except Exception:
    st.info("Please enter your Date of Birth and at least one lab result above.")
