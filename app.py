import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Funds Relative Return",
    page_icon="📊",
    layout="wide"
)

# Custom CSS - Fintech Light Mode
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background-color: #F8FAFC;
    }
    
    h1, h2, h3 {
        color: #1E293B;
        font-weight: 600;
    }
    
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    .positive {
        color: #10B981 !important;
        font-weight: 500;
    }
    
    .negative {
        color: #EF4444 !important;
        font-weight: 500;
    }
    
    /* Highlight date input */
    [data-testid="stDateInput"] {
        background-color: #EFF6FF;
        border-radius: 8px;
        padding: 8px;
        border: 2px solid #2563EB;
    }
    
    [data-testid="stDateInput"] label {
        color: #2563EB !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# Google Drive settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import tempfile

FILE_ID = '1ud_TRzKqMaKSwoDi_HATSiam9frraEuo'
CREDENTIALS_FILE = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json'

# Fund list and VNI mapping
FUNDS = ['DCVEUF.USD', 'VEIL-R', 'Big Port.VND', 'Small Port.VND', 'SNBIM', 'VF1', 'DC25']

# Display names mapping
DISPLAY_NAMES = {
    'DCVEUF.USD': 'UCITS',
    'VEIL-R': 'VEIL',
    'Big Port.VND': 'Big port',
    'Small Port.VND': 'Small port',
    'SNBIM': 'NBIM',
    'VF1': 'DCDS',
    'DC25': 'DC25'
}

VNI_MAPPING = {
    'DCVEUF.USD': 'VNIIndex.USD',
    'VEIL-R': 'VNIIndex.USD',
    'SNBIM': 'VNIIndex.USD',
    'DC25': 'VNIIndex.USD',
    'Big Port.VND': 'VNINDEX Index',
    'Small Port.VND': 'VNINDEX Index',
    'VF1': 'VNINDEX Index'
}

@st.cache_data(ttl=3600)  # Cache for 1 hour, then reload from Drive
def load_data():
    """Load data directly from Google Drive"""
    try:
        import os
        credentials = None
        
        # Try local file first (for local development)
        if os.path.exists(CREDENTIALS_FILE):
            credentials = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE, 
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
        # Then try Streamlit Cloud secrets
        elif hasattr(st, 'secrets') and len(st.secrets) > 0:
            if 'gcp_service_account' in st.secrets:
                credentials = service_account.Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"],
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
            elif 'type' in st.secrets and st.secrets['type'] == 'service_account':
                credentials = service_account.Credentials.from_service_account_info(
                    dict(st.secrets),
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
        
        if credentials is None:
            st.error("Credentials not found in local file or Streamlit Secrets.")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        service = build('drive', 'v3', credentials=credentials)
        
        # Download file to memory
        request = service.files().get_media(fileId=FILE_ID)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # Save to temp file and read as SQLite
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp.write(file_content.getvalue())
            tmp_path = tmp.name
        
        conn = sqlite3.connect(tmp_path)
        df_returns = pd.read_sql_query("SELECT * FROM DailyReturns ORDER BY Date", conn)
        
        # Try to load Holdings table
        try:
            df_holdings = pd.read_sql_query("SELECT * FROM IrisHoldings", conn)
        except:
            df_holdings = pd.DataFrame()
            
        # Try to load Fundamentals table
        try:
            df_fundamental = pd.read_sql_query("SELECT * FROM HoldingsFundamentals", conn)
        except:
            df_fundamental = pd.DataFrame()
            
        conn.close()
        
        # Clean up temp file
        import os
        os.remove(tmp_path)
        
        df_returns['Date'] = pd.to_datetime(df_returns['Date'])
        return df_returns, df_holdings, df_fundamental
    except Exception as e:
        st.error(f"Error loading data from Google Drive: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def calculate_cumulative(df, fund, start_date, end_date):
    """Calculate cumulative return for a fund"""
    fund_data = df[(df['Fund'] == fund) & (df['Date'] >= start_date) & (df['Date'] <= end_date)].copy()
    fund_data = fund_data.sort_values('Date')
    
    if fund_data.empty:
        return pd.DataFrame()
    
    # Cumulative return: (1 + r1/100) * (1 + r2/100) * ... - 1
    fund_data['Cumulative'] = ((1 + fund_data['DailyReturn'] / 100).cumprod() - 1) * 100
    return fund_data

def get_fund_actual_start_date(df, fund, start_date, end_date):
    """Get the actual first date with data for a fund within the selected range"""
    fund_data = df[(df['Fund'] == fund) & (df['Date'] >= start_date) & (df['Date'] <= end_date)]
    if fund_data.empty:
        return None
    return fund_data['Date'].min()

def get_all_funds_vs_vni(df, start_date, end_date):
    """Get vs VNI data for all funds for the chart - with Dynamic Re-basing"""
    all_data = []
    
    for fund in FUNDS:
        # Find actual start date for this fund (Dynamic Re-basing)
        actual_start = get_fund_actual_start_date(df, fund, start_date, end_date)
        if actual_start is None:
            continue
        
        # Calculate cumulative from the fund's actual start date
        fund_cum = calculate_cumulative(df, fund, actual_start, end_date)
        vni_benchmark = VNI_MAPPING.get(fund)
        # VNI is also re-based from the same actual start date
        vni_cum = calculate_cumulative(df, vni_benchmark, actual_start, end_date)
        
        if not fund_cum.empty and not vni_cum.empty:
            merged = fund_cum.merge(vni_cum[['Date', 'Cumulative']], on='Date', suffixes=('', '_VNI'))
            merged['vs_VNI'] = merged['Cumulative'] - merged['Cumulative_VNI']
            merged['Fund_Name'] = DISPLAY_NAMES.get(fund, fund)
            all_data.append(merged[['Date', 'Fund_Name', 'vs_VNI']])
    
    # Add Small vs Big line - also with Dynamic Re-basing
    small_start = get_fund_actual_start_date(df, 'Small Port.VND', start_date, end_date)
    big_start = get_fund_actual_start_date(df, 'Big Port.VND', start_date, end_date)
    
    if small_start is not None and big_start is not None:
        # Use the later of the two start dates for fair comparison
        common_start = max(small_start, big_start)
        small_cum = calculate_cumulative(df, 'Small Port.VND', common_start, end_date)
        big_cum = calculate_cumulative(df, 'Big Port.VND', common_start, end_date)
        
        if not small_cum.empty and not big_cum.empty:
            small_vs_big = small_cum.merge(big_cum[['Date', 'Cumulative']], on='Date', suffixes=('', '_Big'))
            small_vs_big['vs_VNI'] = small_vs_big['Cumulative'] - small_vs_big['Cumulative_Big']
            small_vs_big['Fund_Name'] = 'Small vs Big'
            all_data.append(small_vs_big[['Date', 'Fund_Name', 'vs_VNI']])
    
    if all_data:
        return pd.concat(all_data)
    return pd.DataFrame()

def get_all_funds_relative_ratio(df, start_date, end_date):
    """Get Relative Ratio (Fund/Index) for all funds"""
    all_data = []
    
    for fund in FUNDS:
        fund_cum = calculate_cumulative(df, fund, start_date, end_date)
        vni_benchmark = VNI_MAPPING.get(fund)
        vni_cum = calculate_cumulative(df, vni_benchmark, start_date, end_date)
        
        if not fund_cum.empty and not vni_cum.empty:
            merged = fund_cum.merge(vni_cum[['Date', 'Cumulative']], on='Date', suffixes=('', '_VNI'))
            # Relative Ratio = (1 + Fund_cum) / (1 + VNI_cum)
            merged['Relative_Ratio'] = (1 + merged['Cumulative']/100) / (1 + merged['Cumulative_VNI']/100)
            merged['Fund_Name'] = DISPLAY_NAMES.get(fund, fund)
            all_data.append(merged[['Date', 'Fund_Name', 'Relative_Ratio']])
    
    # Add Small vs Big line
    small_cum = calculate_cumulative(df, 'Small Port.VND', start_date, end_date)
    big_cum = calculate_cumulative(df, 'Big Port.VND', start_date, end_date)
    if not small_cum.empty and not big_cum.empty:
        small_vs_big = small_cum.merge(big_cum[['Date', 'Cumulative']], on='Date', suffixes=('', '_Big'))
        small_vs_big['Relative_Ratio'] = (1 + small_vs_big['Cumulative']/100) / (1 + small_vs_big['Cumulative_Big']/100)
        small_vs_big['Fund_Name'] = 'Small vs Big'
        all_data.append(small_vs_big[['Date', 'Fund_Name', 'Relative_Ratio']])
    
    if all_data:
        return pd.concat(all_data)
    return pd.DataFrame()


def main():
    st.title("📊 Funds Relative Return")
    
    # Load data
    df, df_holdings, df_fundamental = load_data()
    
    # Check if data loaded successfully
    if df.empty:
        st.error("❌ Không thể load data. Vui lòng kiểm tra kết nối Google Drive hoặc credentials.")
        st.stop()
    
    # Get date range from data
    min_date = df['Date'].min().date()
    max_date = df['Date'].max().date()
    
    # Sidebar
    st.sidebar.header("⚙️ Settings")
    
    # Fund selector with display names
    fund_display_options = [DISPLAY_NAMES.get(f, f) for f in FUNDS]
    # Default to Big port (index 2)
    selected_display = st.sidebar.selectbox("Select Fund", fund_display_options, index=2)
    # Map back to internal name
    selected_fund = FUNDS[fund_display_options.index(selected_display)]
    
    # Date range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        default_start = datetime(2023, 5, 1).date()
        if default_start < min_date:
            default_start = min_date
        start_date = st.date_input("Start Date", value=default_start, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)
    
    # Get VNI benchmark for selected fund (internal use)
    vni_benchmark = VNI_MAPPING.get(selected_fund, 'N/A')
    
    # Show funds benchmark mapping in sidebar
    st.sidebar.markdown("""
**Funds vs Benchmark:**
1. Big model port/VnIndex
2. Small model port/VnIndex
3. Small model port/ Big model port
4. DCDS/VnIndex (VND return)
5. VEIL/VnIndex (USD return)
6. Ucits/VnIndex (USD return)
7. NBIM/VnIndex (USD return)
8. DC25/VNIndex (USD return)
""")
    
    # ============ LINE CHART ============
    
    chart_data = get_all_funds_vs_vni(df, start_date, end_date)
    
    if not chart_data.empty:
        # Color palette for funds (using display names)
        colors = {
            'UCITS': '#2563EB',
            'VEIL': '#7C3AED',
            'Big port': '#059669',
            'Small port': '#10B981',
            'NBIM': '#F59E0B',
            'DCDS': '#EF4444',
            'DC25': '#EC4899',
            'Small vs Big': '#000000'
        }
        
        fig = px.line(
            chart_data, 
            x='Date', 
            y='vs_VNI', 
            color='Fund_Name',
            color_discrete_map=colors,
            labels={'vs_VNI': 'vs VNI (%)', 'Date': '', 'Fund_Name': 'Fund'},
            template='plotly_white'
        )
        
        # Hide all traces except Big port by default (user can click legend to show)
        for trace in fig.data:
            if trace.name != 'Big port':
                trace.visible = 'legendonly'
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="#94A3B8")
        
        fig.update_layout(
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20),
            font=dict(family="Inter", size=12)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available for selected date range")
    
    # ============ DATA TABLE ============
    st.subheader(f"📋 {DISPLAY_NAMES.get(selected_fund, selected_fund)} - Daily Performance")
    
    # Calculate fund data with Dynamic Re-basing
    # Find the actual start date for the selected fund
    actual_fund_start = get_fund_actual_start_date(df, selected_fund, start_date, end_date)
    
    if actual_fund_start is not None:
        # Calculate cumulative from the fund's actual start date
        fund_data = calculate_cumulative(df, selected_fund, actual_fund_start, end_date)
        # VNI is also re-based from the same actual start date
        vni_data = calculate_cumulative(df, vni_benchmark, actual_fund_start, end_date)
    else:
        fund_data = pd.DataFrame()
        vni_data = pd.DataFrame()
    
    if not fund_data.empty and not vni_data.empty:
        # Merge with VNI
        table_data = fund_data.merge(vni_data[['Date', 'Cumulative']], on='Date', suffixes=('', '_VNI'))
        table_data['vs VNI'] = table_data['Cumulative'] - table_data['Cumulative_VNI']
        
        # Small vs Big (only for Small Port.VND) - with Dynamic Re-basing
        if selected_fund == 'Small Port.VND':
            big_start = get_fund_actual_start_date(df, 'Big Port.VND', start_date, end_date)
            if big_start is not None:
                # Use the later of the two start dates for fair comparison
                common_start = max(actual_fund_start, big_start)
                # Re-calculate Small from common start for this comparison
                small_for_comparison = calculate_cumulative(df, 'Small Port.VND', common_start, end_date)
                big_port_data = calculate_cumulative(df, 'Big Port.VND', common_start, end_date)
                
                if not big_port_data.empty and not small_for_comparison.empty:
                    comparison_data = small_for_comparison.merge(big_port_data[['Date', 'Cumulative']], on='Date', suffixes=('', '_Big'))
                    comparison_data['Small vs Big'] = comparison_data['Cumulative'] - comparison_data['Cumulative_Big']
                    # Merge back to table_data
                    table_data = table_data.merge(comparison_data[['Date', 'Small vs Big']], on='Date', how='left')
                else:
                    table_data['Small vs Big'] = None
            else:
                table_data['Small vs Big'] = None
        else:
            table_data['Small vs Big'] = None
        
        # Format table
        display_df = table_data[['Date', 'DailyReturn', 'Cumulative', 'Cumulative_VNI', 'vs VNI', 'Small vs Big']].copy()
        display_df.columns = ['Date', 'Daily Return (%)', 'Cumulative (%)', 'VNI Cum (%)', 'vs VNI (%)', 'Small vs Big (%)']
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        
        # Sort by date descending (newest first)
        display_df = display_df.sort_values('Date', ascending=False)
        
        # Style the dataframe
        def color_values(val):
            if pd.isna(val):
                return ''
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'color: #10B981; font-weight: 500'
                elif val < 0:
                    return 'color: #EF4444; font-weight: 500'
            return ''
        
        styled_df = display_df.style.applymap(
            color_values, 
            subset=['Daily Return (%)', 'Cumulative (%)', 'VNI Cum (%)', 'vs VNI (%)', 'Small vs Big (%)']
        ).format({
            'Daily Return (%)': '{:.2f}',
            'Cumulative (%)': '{:.2f}',
            'VNI Cum (%)': '{:.2f}',
            'vs VNI (%)': '{:.2f}',
            'Small vs Big (%)': lambda x: '{:.2f}'.format(x) if pd.notna(x) else '-'
        })
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Summary metrics
        st.subheader("📊 Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        latest = table_data.iloc[-1]
        
        with col1:
            st.metric("Total Cumulative", f"{latest['Cumulative']:.2f}%")
        with col2:
            st.metric("vs VNI", f"{latest['vs VNI']:.2f}%")
        with col3:
            st.metric("VNI Benchmark Cumulative", f"{latest['Cumulative_VNI']:.2f}%")
        with col4:
            if selected_fund == 'Small Port.VND' and pd.notna(latest.get('Small vs Big')):
                st.metric("Small vs Big", f"{latest['Small vs Big']:.2f}%")
            else:
                st.metric("Trading Days", f"{len(table_data)}")
    else:
        st.warning("No data available for selected fund and date range")

    # ============ PORTFOLIO POSITIONING ============
    st.markdown("---")
    
    # Get report date
    report_date_str = ""
    if df_holdings is not None and not df_holdings.empty and 'ReportDate' in df_holdings.columns:
        # Assuming all rows have the same report date, take the first one
        r_date = df_holdings['ReportDate'].iloc[0]
        if pd.notna(r_date):
            report_date_str = f" (Data date: {r_date})"
            
    st.header(f"⚡ Portfolio Positioning vs VNIndex{report_date_str}")
    
    # Process positioning data
    if df_holdings is not None and not df_holdings.empty:
        # Fund mapping
        fund_col_map = {
            'DCVEUF.USD': 'DCVEUF',
            'VEIL-R': 'VEIL',
            'Big Port.VND': 'RT Big Port',
            'Small Port.VND': 'RT Small Port',
            'SNBIM': 'NBIM',
            'VF1': 'DCDS',
            'DC25': 'VFMVSF'
        }
        
        fund_col = fund_col_map.get(selected_fund)
        
        if fund_col and fund_col in df_holdings.columns:
            # Calculate Active Weight
            # Fill NaN with 0 for calculation
            df_pos = df_holdings.copy()
            df_pos[fund_col] = df_pos[fund_col].fillna(0)
            df_pos['VNI %'] = df_pos['VNI %'].fillna(0)
            
            # Filter for stocks only (Ticker length == 3)
            df_pos = df_pos[df_pos['Ticker'].astype(str).str.len() == 3]
            
            df_pos['Active Weight'] = df_pos[fund_col] - df_pos['VNI %']
            
            # Merge with fundamentals
            if df_fundamental is not None and not df_fundamental.empty:
                df_pos = df_pos.merge(
                    df_fundamental[['Ticker', 'NPATMI_2026', 'Growth_2026', 'PE_2026', 'PB_2026', 'Alpha_1M', 'Alpha_3M']], 
                    on='Ticker', 
                    how='left'
                )
            else:
                df_pos['NPATMI_2026'] = None
                df_pos['Growth_2026'] = None
                df_pos['PE_2026'] = None
                df_pos['PB_2026'] = None
                df_pos['Alpha_1M'] = None
                df_pos['Alpha_3M'] = None
            
            # Select columns for display
            display_cols = ['Ticker', fund_col, 'VNI %', 'Active Weight', 'Alpha_1M', 'Alpha_3M', 'NPATMI_2026', 'Growth_2026', 'PE_2026', 'PB_2026']
            rename_cols = {
                fund_col: 'Fund %',
                'Alpha_1M': 'Alpha 1M',
                'Alpha_3M': 'Alpha 3M',
                'NPATMI_2026': 'NPATMI 2026',
                'Growth_2026': 'Growth 2026',
                'PE_2026': 'PE 2026',
                'PB_2026': 'PB 2026'
            }
            
            # Top 15 Overweight
            overweight = df_pos.nlargest(15, 'Active Weight')[display_cols].rename(columns=rename_cols)
            
            # Top 15 Underweight
            underweight = df_pos.nsmallest(15, 'Active Weight')[display_cols].rename(columns=rename_cols)
            
            def style_positioning_table(dframe):
                return dframe.style.format({
                    'Fund %': '{:.2f}%',
                    'VNI %': '{:.2f}%',
                    'Active Weight': '{:.2f}%',
                    'Alpha 1M': '{:.1f}%',
                    'Alpha 3M': '{:.1f}%',
                    'NPATMI 2026': '{:,.0f}',
                    'Growth 2026': '{:.1f}%',
                    'PE 2026': '{:.1f}',
                    'PB 2026': '{:.1f}'
                })
            
            st.subheader("📈 Top 15 Overweight")
            st.dataframe(style_positioning_table(overweight), use_container_width=True, hide_index=True)
                
            st.subheader("📉 Top 15 Underweight")
            st.dataframe(style_positioning_table(underweight), use_container_width=True, hide_index=True)
                
        else:
            st.info(f"Positioning data not available for {DISPLAY_NAMES.get(selected_fund, selected_fund)}")
    else:
        st.error("Could not load holdings data.")

if __name__ == "__main__":
    main()
