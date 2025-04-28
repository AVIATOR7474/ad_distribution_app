import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st # Import streamlit to use secrets
import traceback
import time

# Function to authenticate with Google Sheets using Streamlit Secrets
def authenticate_google_sheets():
    """Authenticates with Google Sheets API using credentials from Streamlit secrets."""
    try:
        # --- Use Streamlit secrets for credentials ---
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Ensure the secret key matches what's expected (e.g., "google_sheets_credentials")
        creds_json = st.secrets["google_sheets_credentials"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        # --- END ---
        client = gspread.authorize(creds)
        return client
    except KeyError:
        st.error("Google Sheets credentials not found in Streamlit secrets.")
        st.error("Please configure `st.secrets['google_sheets_credentials']` as described in the README.")
        st.stop()
    except Exception as e:
        st.error(f"Google Sheets Authentication Error: {e}")
        st.error("An error occurred during authentication. Check credentials format in secrets and API permissions.")
        st.stop() # Stop execution if authentication fails

# Function to load data from a specific sheet
def load_sheet_data(client, sheet_name, worksheet_name):
    """Loads data from a specific worksheet into a pandas DataFrame."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        data = sheet.get_all_records() # Assumes first row is header
        df = pd.DataFrame(data)
        # Convert numeric columns that might be read as strings
        for col in df.columns:
            # Attempt conversion to numeric, coercing errors to NaN
            # Note: errors='ignore' is deprecated, consider explicit try-except for future versions
            df[col] = pd.to_numeric(df[col], errors='ignore')
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found in Google Sheet '{sheet_name}'.")
        return pd.DataFrame() # Return empty DataFrame
    except Exception as e:
        st.error(f"Error loading data from sheet '{sheet_name}', worksheet '{worksheet_name}': {e}")
        return pd.DataFrame() # Return empty DataFrame

# Function to load all required data
def load_all_data(client, sheet_name):
    """Loads data from all required worksheets."""
    data = {}
    sheets_to_load = [
        "GlobalBudget", "Employees", "EmployeeBalances",
        "Projects", "Developers", "Regions", "UnitTypes", "AdsDistributionLog"
    ]
    all_loaded = True
    for ws_name in sheets_to_load:
        df = load_sheet_data(client, sheet_name, ws_name)
        if df.empty and ws_name not in ["AdsDistributionLog", "EmployeeBalances"]: # Allow Log and Balances to be initially empty
             st.warning(f"Warning: Worksheet '{ws_name}' is empty or could not be loaded.")
             # Depending on strictness, might want to set all_loaded = False here for critical sheets
        data[ws_name] = df

    # Basic validation (check if critical dataframes are loaded)
    if data["Projects"].empty or data["Employees"].empty or data["Regions"].empty or data["GlobalBudget"].empty:
        st.error("Critical data sheets (Projects, Employees, Regions, GlobalBudget) could not be loaded or are empty. Cannot proceed.")
        all_loaded = False

    if all_loaded:
        st.success("All required data loaded successfully from Google Sheets.")
    else:
        st.error("Failed to load some or all required data from Google Sheets.")

    return data, all_loaded


# Function to update a worksheet (e.g., append rows)
def append_to_sheet(client, sheet_name, worksheet_name, data_df):
    """Appends data from a DataFrame to a worksheet."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        # Convert DataFrame to list of lists for appending
        # Include header only if the sheet is empty
        if sheet.row_count == 0:
             header = data_df.columns.values.tolist()
             sheet.append_row(header)

        values_to_append = data_df.values.tolist()
        if values_to_append: # Only append if there's data
             sheet.append_rows(values_to_append, value_input_option='USER_ENTERED')
        st.success(f"Successfully appended {len(values_to_append)} rows to '{worksheet_name}'.")
        return True

    except Exception as e:
        st.error(f"Error appending data to sheet '{sheet_name}', worksheet '{worksheet_name}': {e}")
        return False


# Function to update specific cells or ranges (more complex updates)
def update_sheet_cells(client, sheet_name, worksheet_name, updates):
    """
    Updates specific cells in a worksheet.
    'updates' should be a list of dictionaries, e.g.,
    [{'range': 'A1', 'values': [['New Value']]}, {'range': 'B2:C3', 'values': [[1, 2], [3, 4]]}]
    """
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        batch_updates = []
        
        # Convert all updates to the correct format for batch_update
        for update in updates:
            if 'values' in update:
                # Already in correct format
                batch_updates.append(update)
            elif 'value' in update:
                # Convert single value to [[value]] format
                batch_updates.append({
                    'range': update['range'],
                    'values': [[update['value']]]
                })
            else:
                st.warning(f"Skipping invalid update format: {update}")
        
        # Perform batch updates if any
        if batch_updates:
            # Split updates into smaller batches to avoid quota issues
            batch_size = 5  # Adjust based on API limits
            for i in range(0, len(batch_updates), batch_size):
                current_batch = batch_updates[i:i+batch_size]
                sheet.batch_update(current_batch, value_input_option='USER_ENTERED')
                
                # Add a small delay between batches to avoid rate limiting
                if i + batch_size < len(batch_updates):
                    time.sleep(1)
            
            st.success(f"Successfully updated {len(batch_updates)} cells in '{worksheet_name}'.")
            return True
        else:
            st.info("No updates to perform.")
            return True
            
    except Exception as e:
        st.error(f"Error updating cells in sheet '{sheet_name}', worksheet '{worksheet_name}': {e}")
        st.error(f"Update details: {updates}") # Log the updates that failed
        return False

# Function to update employee balances
def update_employee_balances(client, sheet_name, employee_updates):
    """Updates employee balances in the EmployeeBalances sheet."""
    try:
        sheet = client.open(sheet_name).worksheet("EmployeeBalances")
        employee_balances_df = pd.DataFrame(sheet.get_all_records())
        if employee_balances_df.empty:
            st.warning("EmployeeBalances sheet is empty. Cannot update balances.")
            return True # Not an error if sheet is empty

        employee_balances_df['EmployeeID'] = employee_balances_df['EmployeeID'].astype(str) # Ensure ID is string for matching

        updates = []
        for emp_id, deduction in employee_updates.items():
            emp_id_str = str(emp_id)
            match = employee_balances_df[employee_balances_df['EmployeeID'] == emp_id_str]
            if not match.empty:
                row_index = match.index[0] + 2 # +1 for header, +1 for 0-based index to 1-based row
                current_balance = pd.to_numeric(match['AdsBalance'].iloc[0], errors='coerce')
                if pd.isna(current_balance):
                    st.warning(f"Could not parse current balance for EmployeeID {emp_id_str}. Skipping update.")
                    current_balance = 0 # Assume 0 if unparseable

                new_balance = current_balance - deduction
                # Find the column index for 'AdsBalance'
                try:
                    col_index = employee_balances_df.columns.get_loc('AdsBalance') + 1 # +1 for 1-based column index
                    cell_ref = gspread.utils.rowcol_to_a1(row_index, col_index)
                    # Note: Using 'values' instead of 'value' for compatibility with batch_update
                    updates.append({'range': cell_ref, 'values': [[float(new_balance)]]})
                except KeyError:
                    st.error("Column 'AdsBalance' not found in EmployeeBalances sheet.")
                    return False
            else:
                st.warning(f"EmployeeID {emp_id_str} not found in EmployeeBalances sheet. Cannot update balance.")

        if updates:
            st.info(f"Sending {len(updates)} balance updates to Google Sheets")
            return update_sheet_cells(client, sheet_name, "EmployeeBalances", updates)
        else:
            st.info("No employee balance updates were needed or possible.")
            return True # No updates needed is not an error

    except Exception as e:
        st.error(f"Error updating employee balances: {e}")
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False


# Function to update project ad distribution counts
def update_project_ads_distributed(client, sheet_name, project_updates):
    """Updates the AdsDistributed count for projects."""
    try:
        sheet = client.open(sheet_name).worksheet("Projects")
        projects_df = pd.DataFrame(sheet.get_all_records())

        # Debug message to show the data received
        st.info(f"Attempting to update projects with: {project_updates}")

        if projects_df.empty:
            st.error("Projects worksheet is empty or could not be loaded.")
            return False

        # Debug message to show the columns in the Projects sheet
        st.info(f"Projects sheet columns: {list(projects_df.columns)}")

        # Ensure ProjectID is treated as string for comparison
        projects_df["ProjectID"] = projects_df["ProjectID"].astype(str)

        updates = []
        for proj_id, ads_added in project_updates.items():
            proj_id_str = str(proj_id)
            st.info(f"Processing update for ProjectID: {proj_id_str}, adding {ads_added} ads")

            # Check if this project exists in the sheet
            match = projects_df[projects_df["ProjectID"] == proj_id_str]
            if not match.empty:
                row_index = match.index[0] + 2  # +1 header, +1 0-based index

                # Debug: Show the matched project data
                st.info(f"Found project: {match.iloc[0].to_dict()}")

                # Get current ads distributed value
                current_ads = pd.to_numeric(match["AdsDistributed"].iloc[0], errors="coerce")
                if pd.isna(current_ads):
                    st.warning(f"Current AdsDistributed value for ProjectID {proj_id_str} is not numeric or empty. Treating as 0.")
                    current_ads = 0

                new_ads_count = current_ads + ads_added
                st.info(f"Updating ProjectID {proj_id_str}: {current_ads} + {ads_added} = {new_ads_count}")

                # Find the column index for "AdsDistributed"
                if "AdsDistributed" not in projects_df.columns:
                    st.error("Column 'AdsDistributed' not found in Projects sheet.")
                    return False

                col_index = projects_df.columns.get_loc("AdsDistributed") + 1
                cell_ref = gspread.utils.rowcol_to_a1(row_index, col_index)

                st.info(f"Will update cell {cell_ref} with value {new_ads_count}")
                # Use 'values' instead of 'value' for compatibility with batch_update
                updates.append({"range": cell_ref, "values": [[float(new_ads_count)]]})
            else:
                st.warning(f"ProjectID {proj_id_str} not found in Projects sheet. Cannot update AdsDistributed count.")
                # Debug: Show all ProjectIDs in the sheet for comparison
                st.info(f"Available ProjectIDs in sheet: {projects_df['ProjectID'].tolist()}")

        if updates:
            st.info(f"Sending {len(updates)} project updates to Google Sheets")
            result = update_sheet_cells(client, sheet_name, "Projects", updates)
            if result:
                st.success("Successfully updated AdsDistributed values in Projects sheet.")
            else:
                st.error("Failed to update AdsDistributed values in Projects sheet.")
            return result
        else:
            st.info("No project ad distribution count updates were needed or possible.")
            return True

    except Exception as e:
        st.error(f"Error updating project AdsDistributed counts: {e}")
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False

# Function to update the global budget
def update_global_budget(client, sheet_name, total_ads_deducted):
    """Deducts the total distributed ads from the global budget."""
    try:
        sheet = client.open(sheet_name).worksheet("GlobalBudget")
        # Assuming the global budget is in cell A2 (value) with header in A1
        current_balance_str = sheet.acell('A2').value
        current_balance = pd.to_numeric(current_balance_str, errors='coerce')

        if pd.isna(current_balance):
             st.error("Could not read or parse the current GlobalAdsBalance from cell A2 in GlobalBudget sheet.")
             return False

        new_balance = current_balance - total_ads_deducted
        # Use update_sheet_cells for consistency and better error handling
        # Use 'values' instead of 'value' for compatibility with batch_update
        update = [{'range': 'A2', 'values': [[float(new_balance)]]}]
        result = update_sheet_cells(client, sheet_name, "GlobalBudget", update)
        if result:
            st.success(f"Global budget updated successfully. Deducted {total_ads_deducted} ads.")
        else:
            st.error("Failed to update GlobalBudget sheet.")
        return result

    except Exception as e:
        st.error(f"Error updating global budget: {e}")
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False

# Function to initialize employee balances (run once or on demand)
def initialize_employee_balances(client, sheet_name):
    """Calculates and sets initial employee balances based on GlobalBudget and percentages."""
    try:
        global_budget_df = load_sheet_data(client, sheet_name, "GlobalBudget")
        employees_df = load_sheet_data(client, sheet_name, "Employees")
        employee_balances_sheet = client.open(sheet_name).worksheet("EmployeeBalances")

        if global_budget_df.empty or 'GlobalAdsBalance' not in global_budget_df.columns:
            st.error("Cannot initialize balances: GlobalBudget sheet is empty or missing 'GlobalAdsBalance' column.")
            return False
        if employees_df.empty or 'EmployeeID' not in employees_df.columns or 'AdsBudgetPercentage' not in employees_df.columns:
            st.error("Cannot initialize balances: Employees sheet is empty or missing required columns.")
            return False

        global_balance = pd.to_numeric(global_budget_df['GlobalAdsBalance'].iloc[0], errors='coerce')
        if pd.isna(global_balance):
            st.error("Cannot initialize balances: GlobalAdsBalance is not a valid number.")
            return False

        balances_to_append = []
        # Prepare header if sheet is empty
        if employee_balances_sheet.row_count == 0:
             employee_balances_sheet.append_row(['EmployeeID', 'AdsBalance'])

        # Get existing data to avoid duplicates and update existing rows
        existing_balances_df = pd.DataFrame(employee_balances_sheet.get_all_records())
        if not existing_balances_df.empty:
            existing_balances_df['EmployeeID'] = existing_balances_df['EmployeeID'].astype(str)

        update_requests = [] # For batch update

        for index, employee in employees_df.iterrows():
            emp_id = str(employee['EmployeeID'])
            percentage_str = str(employee['AdsBudgetPercentage']).replace('%', '')
            percentage = pd.to_numeric(percentage_str, errors='coerce')

            if pd.isna(percentage):
                st.warning(f"Invalid percentage for EmployeeID {emp_id}. Skipping.")
                continue

            initial_balance = (percentage / 100.0) * global_balance

            # Check if employee exists in balances sheet
            match = existing_balances_df[existing_balances_df['EmployeeID'] == emp_id] if not existing_balances_df.empty else pd.DataFrame()

            if not match.empty:
                # Update existing row
                row_index = match.index[0] + 2 # +1 header, +1 0-based index
                col_index = 2 # Assuming 'AdsBalance' is column B
                cell_ref = gspread.utils.rowcol_to_a1(row_index, col_index)
                # Use 'values' instead of 'value' for compatibility with batch_update
                update_requests.append({'range': cell_ref, 'values': [[float(initial_balance)]]})
            else:
                # Prepare data for appending new row
                balances_to_append.append([emp_id, float(initial_balance)])

        # Append new rows first (if any)
        if balances_to_append:
             employee_balances_sheet.append_rows(balances_to_append, value_input_option='USER_ENTERED')
             st.success(f"Appended initial balances for {len(balances_to_append)} new employees.")

        # Then batch update existing rows (if any)
        if update_requests:
             # Use update_sheet_cells for consistency
             update_result = update_sheet_cells(client, sheet_name, "EmployeeBalances", update_requests)
             if update_result:
                 st.success(f"Updated initial balances for {len(update_requests)} existing employees.")
             else:
                 st.error("Failed to update initial balances for existing employees.")
                 return False

        st.success("Employee balances initialized/updated successfully.")
        return True

    except Exception as e:
        st.error(f"Error initializing employee balances: {e}")
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False
