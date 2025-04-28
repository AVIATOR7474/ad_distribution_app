import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

def distribute_ads_automatically(projects_df, selected_region, num_ads_to_distribute, employee_id):
    """
    Distributes ads automatically to projects within a selected region based on importance scores.

    Args:
        projects_df (pd.DataFrame): DataFrame containing project data.
        selected_region (str): The name of the region to distribute ads within.
        num_ads_to_distribute (int): The total number of ads to distribute.
        employee_id (str): The ID of the employee receiving the ad distribution task.

    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: Log of the distribution details.
            - dict: Updates for project AdsDistributed counts {ProjectID: ads_added}.
            - int: Total number of ads actually allocated.
    """
    distribution_log_entries = []
    project_ads_update = {}
    total_ads_allocated = 0

    # --- Data Cleaning and Preparation ---
    # Ensure required columns exist
    required_cols = ["ProjectID", "RegionName", "Req", "ProjectOrder", "ProjectExcellenceScore", "MarketingSize", "AdsDistributed", "UnitTypesInProject"]
    if not all(col in projects_df.columns for col in required_cols):
        st.error(f"Missing required columns in Projects data: {', '.join(set(required_cols) - set(projects_df.columns))}")
        return pd.DataFrame(), {}, 0

    # Convert relevant columns to numeric, coercing errors
    numeric_cols = ["ProjectOrder", "ProjectExcellenceScore", "MarketingSize", "AdsDistributed"]
    for col in numeric_cols:
        # Corrected line below
        projects_df[col] = pd.to_numeric(projects_df[col], errors='coerce')

    # Filter projects for the selected region and where marketing is required (
    #Req == "Yes")
    # Case-insensitive comparison for 'Req'
    region_projects = projects_df[
        (projects_df["RegionName"].str.strip().str.lower() == selected_region.strip().lower()) &
        (projects_df["Req"].astype(str).str.strip().str.lower() == "yes")
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    if region_projects.empty:
        st.warning(f"No active projects requiring marketing found in region '{selected_region}'.") # Corrected quotes
        return pd.DataFrame(distribution_log_entries), project_ads_update, total_ads_allocated

    # Fill NaN values in numeric columns used for scoring with 0 after filtering
    region_projects[numeric_cols] = region_projects[numeric_cols].fillna(0)

    # --- Calculate Importance Scores ---
    # Calculate max_order for priority score (use fillna(0) in case all are NaN)
    max_order = region_projects["ProjectOrder"].max()
    if pd.isna(max_order):
        max_order = 0 # Handle case where the column might be all NaN or empty after filtering

    # Calculate components of the importance score
    # Ensure ProjectOrder is treated correctly if it was NaN (now 0)
    region_projects["PriorityScore"] = max_order - region_projects["ProjectOrder"] + 1

    # Demand Score is implicitly handled by filtering Req == "Yes", adding 5 points
    region_projects["DemandScore"] = 5

    # Excellence Score
    region_projects["ExcellenceScoreCalc"] = region_projects["ProjectExcellenceScore"] / 10.0

    # Remaining Size Score
    region_projects["RemainingSizeScore"] = region_projects["MarketingSize"] - region_projects["AdsDistributed"]
    # Ensure remaining size is not negative
    region_projects["RemainingSizeScore"] = region_projects["RemainingSizeScore"].clip(lower=0)

    # Calculate Total Importance Score
    region_projects["TotalScore"] = (
        region_projects["PriorityScore"] +
        region_projects["DemandScore"] +
        region_projects["ExcellenceScoreCalc"] +
        region_projects["RemainingSizeScore"]
    )

    # Ensure scores are not negative
    region_projects["TotalScore"] = region_projects["TotalScore"].clip(lower=0)

    # --- Allocate Ads to Projects ---
    total_importance_score = region_projects["TotalScore"].sum()

    if total_importance_score <= 0:
        st.warning(f"No projects with positive importance score found in region '{selected_region}'. Cannot distribute ads.") # Corrected quotes
        return pd.DataFrame(distribution_log_entries), project_ads_update, total_ads_allocated

    # Calculate ads per project (proportional allocation)
    region_projects["Proportion"] = region_projects["TotalScore"] / total_importance_score
    region_projects["CalculatedAds"] = region_projects["Proportion"] * num_ads_to_distribute

    # Allocate integer ads, ensuring the total doesn't exceed num_ads_to_distribute
    region_projects["AllocatedAdsProject"] = np.floor(region_projects["CalculatedAds"]).astype(int)
    allocated_so_far = region_projects["AllocatedAdsProject"].sum()
    remainder_ads = num_ads_to_distribute - allocated_so_far

    # Distribute remainder ads one by one based on the fractional part of CalculatedAds
    region_projects["RemainderPriority"] = region_projects["CalculatedAds"] - region_projects["AllocatedAdsProject"]
    # Sort by remainder priority to distribute remaining ads
    sorted_indices = region_projects.sort_values(by="RemainderPriority", ascending=False).index

    for i in range(min(remainder_ads, len(region_projects))):
        idx = sorted_indices[i]
        region_projects.loc[idx, "AllocatedAdsProject"] += 1

    total_ads_allocated = region_projects["AllocatedAdsProject"].sum()

    # --- Allocate Ads to Unit Types within Projects ---
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for index, project in region_projects.iterrows():
        project_id = project["ProjectID"]
        ads_for_project = project["AllocatedAdsProject"]

        if ads_for_project <= 0:
            continue # Skip projects that received 0 ads

        # Update the project_ads_update dictionary
        project_ads_update[str(project_id)] = ads_for_project # Ensure ID is string

        unit_types_str = project["UnitTypesInProject"]
        if pd.isna(unit_types_str) or not unit_types_str.strip():
            st.warning(f"Project {project_id} has no unit types listed. Cannot distribute ads for this project.")
            # Note: Ads allocated to the project are still counted in total_ads_allocated
            # and project_ads_update, but won't appear in the detailed log.
            # Consider if this requires different handling (e.g., reallocating these ads).
            continue

        # Corrected split
        unit_types = [ut.strip() for ut in unit_types_str.split(',') if ut.strip()]
        if not unit_types:
            st.warning(f"Project {project_id} has no valid unit types after parsing. Cannot distribute ads.")
            continue

        num_unit_types = len(unit_types)
        ads_per_unit_type = ads_for_project // num_unit_types
        remainder_unit_ads = ads_for_project % num_unit_types

        for i, unit_type_name in enumerate(unit_types):
            ads_for_this_unit = ads_per_unit_type
            if i < remainder_unit_ads:
                ads_for_this_unit += 1

            if ads_for_this_unit > 0:
                distribution_log_entries.append({
                    "DistributionID": f"dist_{employee_id}_{project_id}_{unit_type_name.replace(' ','_')}_{datetime.now().timestamp()}", # Generate a unique-ish ID
                    "EmployeeID": str(employee_id),
                    "ProjectID": str(project_id),
                    "RegionName": selected_region,
                    "UnitTypeName": unit_type_name,
                    "AdsAllocated": ads_for_this_unit,
                    "DistributionDate": current_date
                })

    # --- Finalize and Return ---
    distribution_log_df = pd.DataFrame(distribution_log_entries)

    # Reorder columns to match expected AdsDistributionLog structure if needed
    if not distribution_log_df.empty:
        distribution_log_df = distribution_log_df[[
            "DistributionID", "EmployeeID", "ProjectID", "RegionName",
            "UnitTypeName", "AdsAllocated", "DistributionDate"
        ]]

    return distribution_log_df, project_ads_update, total_ads_allocated

# Example Usage (for testing purposes, would be called from Streamlit app)
if __name__ == '__main__':
    # Create dummy data similar to Google Sheets structure
    projects_data = {
        'ProjectID': ['P1', 'P2', 'P3', 'P4'],
        'ProjectName': ['Sky Tower', 'Ocean View', 'Green Hills', 'City Central'],
        'DeveloperID': ['D1', 'D2', 'D1', 'D3'],
        'RegionName': ['North', 'North', 'South', 'North'],
        'UnitTypesInProject': ['Apt, Studio', 'Villa, Apt', 'Townhouse', 'Studio'],
        'ProjectOrder': [1, 2, 1, 3],
        'Req': ['Yes', 'Yes', 'Yes', 'No'], # P4 should be excluded
        'ProjectExcellenceScore': [80, 95, 70, 90],
        'MarketingSize': [100, 150, 80, 50],
        'AdsDistributed': [20, 30, 10, 5]
    }
    projects_df = pd.DataFrame(projects_data)

    selected_region = 'North'
    num_ads_to_distribute = 50
    employee_id = 'E101'

    log_df, proj_updates, total_allocated = distribute_ads_automatically(
        projects_df.copy(), # Pass a copy to avoid modifying original test data
        selected_region,
        num_ads_to_distribute,
        employee_id
    )

    print("--- Distribution Log ---")
    print(log_df)
    print("\n--- Project Ads Updates ---")
    print(proj_updates)
    print(f"\n--- Total Ads Allocated: {total_allocated} ---")


