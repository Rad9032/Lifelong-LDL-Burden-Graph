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
plaque_limit = 5000 if is_mgdl else 130
ha_limit = 8000 if is_mgdl else 190

# --- SIDEBAR: PERSONAL INFORMATION ---
st.sidebar.header("Personal Information")
dob = st.sidebar.date_input("Date of Birth", value=datetime(1970, 1, 1), min_value=datetime(1900, 1, 1), max_value=datetime.now())

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
# We use a copy to avoid internal conflicts
edited_df = st.data_editor(
    st.session_state.input_data, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Date": st.column_config.DateColumn("Date of Test", required=True),
        "LDL": st.column_config.NumberColumn(f"LDL ({unit_label})", required=True)
    }
)

# --- BULLETPROOF CALCULATIONS ---
def run_calculations(df, birth_date, target, is_us):
    # 1. Clean data: Remove empty rows and convert dates properly
    calc_df = df.copy().dropna()
    calc_df['Date'] = pd.to_datetime(calc_df['Date']).dt.date
    calc_df = calc_df.sort_values("Date").reset_index(drop=True)
    
    # 2. Unit Conversion
    if is_us:
        calc_df['LDL_mmol'] = calc_df['LDL'] / 38.67
        target_mmol = target / 38.67
    else:
        calc_df['LDL_mmol'] = calc_df['LDL']
        target_mmol = target

    # 3. Calculate Age and Exposure
    calc_df['Age'] = calc_df['Date'].apply(lambda x: (x - birth_date).days / 365.25)
    
    calc_df['Exposure_mmol'] = 0.0
    for i in range(1, len(calc_df)):
        years_passed = calc_df.loc[i, 'Age'] - calc_df.loc[i-1, 'Age']
        # Trapezoidal rule for smoother burden calculation
        avg_ldl = (calc_df.loc[i, 'LDL_mmol'] + calc_df.loc[i-1, 'LDL_mmol']) / 2
        calc_df.loc[i, 'Exposure_mmol'] = calc_df.loc[i-1, 'Exposure_mmol'] + (years_passed * avg_ldl)
    
    last_age = calc_df.iloc[-1]['Age']
    last_exp_mmol = calc_df.iloc[-1]['Exposure_mmol']
    
    # 4. Predictions
    output_metrics = {}
    for label, limit_mmol in [("Plaque", 130), ("Heart Attack", 190)]:
        if last_exp_mmol >= limit_mmol:
            # Linear interpolation to find the exact age the limit was hit
            output_metrics[label] = "Limit Reached"
        else:
            years_to_go = (limit_mmol - last_exp_mmol) / target_mmol
            output_metrics[label] = f"Age {last_age + years_to_go:.1f}"
            
    return calc_df, output_metrics, last_exp_mmol

# Run the math
try:
    calc_df, results, current_exp_mmol = run_calculations(edited_df, dob, target_ldl, is_mgdl)
    current_exp_display = current_exp_mmol * (38.67 if is_mgdl else 1.0)

    # --- OUTPUTS ---
    st.subheader("2. Your Results")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(f"Plaque Age ({plaque_limit})", results["Plaque"])
    with c2:
        st.metric(f"Heart Attack Age ({ha_limit})", results["Heart Attack"])
    with c3:
        st.metric(f"Total Burden ({unit_label}·yr)", f"{current_exp_display:.0f}" if is_mgdl else f"{current_exp_display:.1f}")

    # --- THE GRAPH ---
    fig = go.Figure()
    graph_y = calc_df['Exposure_mmol'] * (38.67 if is_mgdl else 1.0)

    fig.add_trace(go.Scatter(x=calc_df['Age'], y=graph_y, mode='lines+markers', name="Your Burden", line=dict(color='#4285F4', width=4)))
    fig.add_hline(y=plaque_limit, line=dict(color='#FBBC04', width=2, dash='dash'), annotation_text="Plaque")
    fig.add_hline(y=ha_limit, line=dict(color='#EA4335', width=2, dash='dash'), annotation_text="Heart Attack")

    fig.update_layout(
        xaxis=dict(title="Age (Years)", showgrid=True),
        yaxis=dict(title=f"Cumulative Exposure ({unit_label} . years)", showgrid=True),
        plot_bgcolor='white', height=500
    )
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error("Please ensure all rows have a Date and LDL value.")
