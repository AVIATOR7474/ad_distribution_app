import streamlit as st
import pandas as pd
from datetime import datetime
import uuid # For generating unique IDs if needed

# Import utility functions
import google_sheets_utils as gs
import distribution_logic as dl

# --- Page Configuration ---
st.set_page_config(page_title="Smart Ad Distributor", layout="wide")
st.title("📊 Smart Ad Distribution Application")
st.markdown("""**Developed by Manus AI** - Your intelligent assistant for marketing task distribution.""")

# --- Authentication and Data Loading ---
# Authenticate with Google Sheets
# Note: Requires google_sheets_credentials setup in Streamlit secrets
client = gs.authenticate_google_sheets()

# Define Google Sheet Name (replace with your actual sheet name)
# This should ideally be configurable or obtained from the user/secrets
GOOGLE_SHEET_NAME = "MarketingData" # <<< IMPORTANT: User needs to ensure this matches their sheet name

# Initialize session state variables if they don't exist
def init_session_state():
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'all_data' not in st.session_state:
        st.session_state.all_data = {}
    if 'distribution_summary' not in st.session_state:
        st.session_state.distribution_summary = None
    if 'last_distribution_log' not in st.session_state:
        st.session_state.last_distribution_log = pd.DataFrame()

init_session_state()

# Load data if not already loaded or if refresh is requested
if not st.session_state.data_loaded:
    with st.spinner("Loading data from Google Sheets..."):
        st.session_state.all_data, loaded_successfully = gs.load_all_data(client, GOOGLE_SHEET_NAME)
        if loaded_successfully:
            st.session_state.data_loaded = True
            # Ensure critical dataframes have expected types
            if 'EmployeeID' in st.session_state.all_data.get("Employees", pd.DataFrame()).columns:
                st.session_state.all_data["Employees"]["EmployeeID"] = st.session_state.all_data["Employees"]["EmployeeID"].astype(str)
            if 'EmployeeID' in st.session_state.all_data.get("EmployeeBalances", pd.DataFrame()).columns:
                st.session_state.all_data["EmployeeBalances"]["EmployeeID"] = st.session_state.all_data["EmployeeBalances"]["EmployeeID"].astype(str)
            if 'ProjectID' in st.session_state.all_data.get("Projects", pd.DataFrame()).columns:
                st.session_state.all_data["Projects"]["ProjectID"] = st.session_state.all_data["Projects"]["ProjectID"].astype(str)
        else:
            st.error("Failed to load initial data. Please check Google Sheet configuration and permissions.")
            st.stop()

# Button to manually refresh data
if st.button("🔄 Refresh Data from Google Sheets"):
    with st.spinner("Reloading data..."):
        st.session_state.all_data, loaded_successfully = gs.load_all_data(client, GOOGLE_SHEET_NAME)
        if loaded_successfully:
            st.session_state.data_loaded = True
            # Re-apply type conversions after refresh
            if 'EmployeeID' in st.session_state.all_data.get("Employees", pd.DataFrame()).columns:
                st.session_state.all_data["Employees"]["EmployeeID"] = st.session_state.all_data["Employees"]["EmployeeID"].astype(str)
            if 'EmployeeID' in st.session_state.all_data.get("EmployeeBalances", pd.DataFrame()).columns:
                st.session_state.all_data["EmployeeBalances"]["EmployeeID"] = st.session_state.all_data["EmployeeBalances"]["EmployeeID"].astype(str)
            if 'ProjectID' in st.session_state.all_data.get("Projects", pd.DataFrame()).columns:
                st.session_state.all_data["Projects"]["ProjectID"] = st.session_state.all_data["Projects"]["ProjectID"].astype(str)
            st.success("Data reloaded successfully!")
        else:
            st.error("Failed to reload data.")

# --- Display Global Budget ---
st.sidebar.header("📊 Global Budget")
global_budget_df = st.session_state.all_data.get("GlobalBudget", pd.DataFrame())
current_global_balance = 0
if not global_budget_df.empty and 'GlobalAdsBalance' in global_budget_df.columns:
    # Corrected line below
    current_global_balance = pd.to_numeric(global_budget_df["GlobalAdsBalance"].iloc[0], errors='coerce')
    if pd.notna(current_global_balance):
        st.sidebar.metric("Total Available Ad Budget", f"{current_global_balance:,.0f}")
    else:
        st.sidebar.warning("Could not read global budget.")
else:
    st.sidebar.warning("GlobalBudget data not available.")

# --- Initialize Employee Balances --- (Sidebar Action)
st.sidebar.header("⚙️ Actions")
if st.sidebar.button("Initialize/Update Employee Balances"):
    with st.spinner("Initializing employee balances..."):
        success = gs.initialize_employee_balances(client, GOOGLE_SHEET_NAME)
        if success:
            st.sidebar.success("Employee balances initialized/updated successfully!")
            # Reload balance data
            st.session_state.all_data["EmployeeBalances"] = gs.load_sheet_data(client, GOOGLE_SHEET_NAME, "EmployeeBalances")
            if 'EmployeeID' in st.session_state.all_data["EmployeeBalances"].columns:
                 st.session_state.all_data["EmployeeBalances"]["EmployeeID"] = st.session_state.all_data["EmployeeBalances"]["EmployeeID"].astype(str)
        else:
            st.sidebar.error("Failed to initialize employee balances.")
# --- Automatic Ad Distribution Section ---
st.header("🚀 Automatic Ad Distribution")

employees_df = st.session_state.all_data.get("Employees", pd.DataFrame())
regions_df = st.session_state.all_data.get("Regions", pd.DataFrame())
projects_df = st.session_state.all_data.get("Projects", pd.DataFrame())
employee_balances_df = st.session_state.all_data.get("EmployeeBalances", pd.DataFrame())

if employees_df.empty or regions_df.empty or projects_df.empty or employee_balances_df.empty:
    st.warning("Missing necessary data (Employees, Regions, Projects, or Balances). Distribution cannot proceed.")
else:
    col1, col2 = st.columns(2)

    with col1:
        # Employee Selection
        employee_options = {row["EmployeeID"]: row["EmployeeName"] for index, row in employees_df.iterrows()}
        selected_employee_id = st.selectbox(
            "Select Employee:",
            options=list(employee_options.keys()),
            format_func=lambda x: f"{employee_options[x]} (ID: {x})"
        )

        # Display Employee Balance
        current_balance = 0
        if selected_employee_id:
            balance_row = employee_balances_df[employee_balances_df["EmployeeID"] == str(selected_employee_id)]
            if not balance_row.empty:
                # Corrected line below
                current_balance = pd.to_numeric(balance_row["AdsBalance"].iloc[0], errors='coerce')
                if pd.notna(current_balance):
                    st.metric(f"Current Ad Balance for {employee_options[selected_employee_id]}", f"{current_balance:,.0f}")
                else:
                    st.warning("Could not parse employee balance.")
            else:
                st.warning(f"Balance data not found for Employee ID: {selected_employee_id}")
                current_balance = 0 # Assume 0 if not found
        else:
            current_balance = 0

    with col2:
        # Region Selection
        region_options = sorted(regions_df["RegionName"].unique().tolist())
        selected_region = st.selectbox("Select Region:", options=region_options)

        # Number of Ads Input
        num_ads_to_distribute = st.number_input("Number of Ads to Distribute in Region:", min_value=1, value=10, step=1)

    # Distribution Button
    if st.button("🤖 Distribute Ads Automatically", key="distribute_button"):
        if not selected_employee_id or not selected_region:
            st.error("Please select both an employee and a region.")
        elif num_ads_to_distribute <= 0:
            st.error("Number of ads must be positive.")
        elif num_ads_to_distribute > current_balance:
            # تحسين رسالة الخطأ لتوضيح الرصيد المتبقي بشكل أفضل
            st.error(f"رصيد غير كافٍ! الموظف {employee_options[selected_employee_id]} لديه فقط {current_balance:,.0f} إعلان متاح، بينما تم طلب {num_ads_to_distribute:,.0f} إعلان.")
            
            # إضافة تحقق من الرصيد العام وإظهار رسالة إضافية إذا كان الرصيد العام غير كافٍ أيضًا
            if current_global_balance < num_ads_to_distribute:
                st.warning(f"ملاحظة: الرصيد العام المتاح ({current_global_balance:,.0f}) أيضًا غير كافٍ لتوزيع {num_ads_to_distribute:,.0f} إعلان. يرجى تحديث الرصيد العام أولاً.")
            
            # اقتراح عدد الإعلانات المناسب
            suggested_ads = min(current_balance, current_global_balance)
            if suggested_ads > 0:
                st.info(f"اقتراح: يمكنك توزيع ما يصل إلى {suggested_ads:,.0f} إعلان بناءً على الرصيد المتاح.")
        else:
            with st.spinner(f"Calculating distribution for {num_ads_to_distribute} ads in {selected_region} for {employee_options[selected_employee_id]}..."):
                # --- Run Distribution Logic ---
                distribution_log_df, project_updates, total_allocated = dl.distribute_ads_automatically(
                    projects_df.copy(), # Pass a copy to avoid modifying the dataframe in session state
                    selected_region,
                    num_ads_to_distribute,
                    selected_employee_id
                )

                st.session_state.last_distribution_log = distribution_log_df
                st.session_state.distribution_summary = {
                    "employee": employee_options[selected_employee_id],
                    "region": selected_region,
                    "requested_ads": num_ads_to_distribute,
                    "allocated_ads": total_allocated,
                    "project_updates": project_updates,
                    "log": distribution_log_df
                }

                if total_allocated > 0:
                    st.success(f"Successfully calculated distribution: {total_allocated} ads allocated.")

                    # --- Update Google Sheets ---
                    st.info("Attempting to update Google Sheets with distribution results...")
                    update_success = True

                    # 1. Append to AdsDistributionLog
                    if not distribution_log_df.empty:
                        if not gs.append_to_sheet(client, GOOGLE_SHEET_NAME, "AdsDistributionLog", distribution_log_df):
                            update_success = False
                            st.error("Failed to update AdsDistributionLog sheet.")

                    # 2. Update EmployeeBalances
                    employee_update_data = {str(selected_employee_id): total_allocated}
                    if not gs.update_employee_balances(client, GOOGLE_SHEET_NAME, employee_update_data):
                        update_success = False
                        st.error("Failed to update EmployeeBalances sheet.")

                    # 3. Update Projects (AdsDistributed)
                    if project_updates:
                        if not gs.update_project_ads_distributed(client, GOOGLE_SHEET_NAME, project_updates):
                            update_success = False
                            st.error("Failed to update AdsDistributed in Projects sheet.")

                    # 4. Update GlobalBudget
                    if not gs.update_global_budget(client, GOOGLE_SHEET_NAME, total_allocated):
                        update_success = False
                        st.error("Failed to update GlobalBudget sheet.")

                    if update_success:
                        st.success("Google Sheets updated successfully!")
                        # Refresh data locally after successful update
                        st.session_state.data_loaded = False # Trigger reload on next run
                        st.rerun()
                    else:
                        st.error("One or more Google Sheets updates failed. Please check logs and sheet permissions.")

                elif not distribution_log_df.empty:
                     st.warning("Distribution calculated, but 0 ads were allocated based on project criteria or unit types.")
                     # Optionally, still log the attempt or handle differently
                else:
                     st.warning("No ads were distributed. This might be due to no active projects in the region or other criteria.")

# --- Display Last Distribution Summary ---
st.header("📄 Last Distribution Summary")
if st.session_state.distribution_summary:
    summary = st.session_state.distribution_summary
    # Corrected line below
    st.markdown(f"**Employee:** {summary['employee']} | **Region:** {summary['region']} | **Requested:** {summary['requested_ads']} | **Allocated:** {summary['allocated_ads']}")

    # Corrected line below
    if not summary['log'].empty:
        # Corrected line below
        st.dataframe(summary['log'])

        # Provide download for the log
        # Corrected line below
        csv = summary['log'].to_csv(index=False).encode('utf-8')
        st.download_button(
           label="Download Last Distribution Log as CSV",
           data=csv,
           # Corrected line below
           file_name=f"distribution_log_{summary['employee']}_{summary['region']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv",
           mime='text/csv',
        )
    else:
        st.info("No ads were allocated in the last distribution attempt.")
else:
    # Corrected line below (removed trailing 'se')
    st.info("No distribution has been performed yet in this session.")

# --- Reporting Section (Basic) ---
st.header("📈 Reports")
ads_log_df = st.session_state.all_data.get("AdsDistributionLog", pd.DataFrame())

if not ads_log_df.empty:
    st.subheader("Full Distribution Log")
    # Add filtering options
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        report_employee_id = st.selectbox("Filter by Employee:", options=["All"] + list(employee_options.keys()), format_func=lambda x: "All" if x == "All" else f"{employee_options.get(x, x)} (ID: {x})")
    with filter_col2:
        report_region = st.selectbox("Filter by Region:", options=["All"] + region_options)
    with filter_col3:
        # Add date filtering if needed later
        pass

    filtered_log = ads_log_df.copy()
    if report_employee_id != "All":
        filtered_log = filtered_log[filtered_log["EmployeeID"] == str(report_employee_id)]
    if report_region != "All":
        filtered_log = filtered_log[filtered_log["RegionName"] == report_region]

    st.dataframe(filtered_log)

    # Provide download for the filtered log
    csv_report = filtered_log.to_csv(index=False).encode("utf-8")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S") # Define timestamp here
    st.download_button(
       label="Download Filtered Log as CSV",
       data=csv_report,
       file_name=f"filtered_distribution_log_{timestamp}.csv", # Use timestamp variable
       mime="text/csv",
    )
# --- Placeholder for Future Features ---
# st.header("Future Features")
# - Update Global Budget Interface
# - Unit Type Importance Integration
# - Enhanced Reporting
# - User Management
