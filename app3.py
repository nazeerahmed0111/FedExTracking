import os
import requests
import streamlit as st
import pandas as pd
# Consolidated datetime imports to avoid confusion
from datetime import datetime
import datetime # Keep this for datetime.date.today() and datetime.fromisoformat
from dotenv import load_dotenv
import json
import io
import time
import plotly.express as px
import altair as alt

# Assuming db_helper is in the same directory and its functions are correctly defined
from db_helper import generate_reference, save_upload_with_json, get_all_references, get_tracking_numbers, get_tracking_json

st.set_page_config(page_title="FedEx Shipment Tracker", layout="wide")

# ✅ Global CSS Styling (Keeping this for general styling)
st.markdown("""
    <style>
    .custom-title {
        font-size: 26px;
        font-weight: bold;
        color: black;
        margin-bottom: 10px;
    }
    /* No specific .nav-link styles needed for st.button */
    </style>
""", unsafe_allow_html=True)

# --- Session State Initialization (Keep as is) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'single' # Default page
# --- End of Session State Initialization ---


# ✅ Load environment variables
load_dotenv()
API_ENDPOINT = "https://apis-sandbox.fedex.com/track/v1/trackingnumbers"
AUTH_URL = "https://apis-sandbox.fedex.com/oauth/token"
#API_KEY = os.getenv("FEDEX_API_KEY")
#API_SECRET = os.getenv("FEDEX_API_SECRET") # Ensure this matches your .env key

# Change these lines to use st.secrets
API_KEY = st.secrets["FEDEX_API_KEY"]
API_SECRET = st.secrets["FEDEX_API_SECRET"]

if not API_KEY or not API_SECRET:
    st.error("❌ API_KEY or API_SECRET environment variables not set.")
    st.stop()

# ✅ API functions (no change needed here)
def get_access_token():
    data = {
        'grant_type': 'client_credentials',
        'client_id': API_KEY,
        'client_secret': API_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(AUTH_URL, data=data, headers=headers)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        st.error(f"Failed to authenticate: {response.status_code} - {response.text}")
        return None

def track_shipment(tracking_number, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "trackingInfo": [
            {"trackingNumberInfo": {"trackingNumber": tracking_number}}
        ],
        "includeDetailedScans": True
    }
    response = requests.post(API_ENDPOINT, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to track shipment: {response.status_code} - {response.text}")
        return None

def get_sample_template():
    sample_df = pd.DataFrame({'TrackingNumber': ['123456789012', '987654321098']})
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        sample_df.to_excel(writer, index=False, sheet_name='Template')
        workbook  = writer.book
        worksheet = writer.sheets['Template']
        left_align = workbook.add_format({'align': 'left'})
        worksheet.set_column('A:A', 25, left_align)
    output.seek(0)
    return output

# --- Login Page Function ---
def login_page():
    st.markdown("<div class='custom-title'>🔒 Login to Shipment Tracker</div>", unsafe_allow_html=True)
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "admin" and password == "admin": # Hardcoded for demo, replace in production
            st.session_state.logged_in = True
            st.rerun() # Rerun to trigger the main app content
        else:
            st.error("Incorrect username or password.")

# --- Main Application Content Function ---
def main_app():
    # ✅ Sidebar Navigation - REVISED TO USE ST.BUTTON
    with st.sidebar:
        st.markdown("<h3 style='color:#0d6efd; font-weight:bold;'>📚 Shipment Tracker</h3>", unsafe_allow_html=True)
        
        # Use individual buttons for navigation
        # We check if the button is clicked, then update the session state variable
        # Streamlit automatically reruns the app when a session state variable changes
        # No need for st.rerun() after setting st.session_state.current_page
        
        if st.button("📦 Shipment Tracking (Single)", key="nav_single"):
            st.session_state.current_page = 'single'
        
        if st.button("📂 Bulk Upload", key="nav_bulk"):
            st.session_state.current_page = 'bulk'
            
        if st.button("🗂️ Tracking Results", key="nav_results"):
            st.session_state.current_page = 'results'
            
        if st.button("📊 Analytics Dashboard", key="nav_analytics"):
            st.session_state.current_page = 'analytics'

        # Add a logout button to the sidebar for convenience
        st.markdown("---") # Separator for logout button
        if st.button("Logout", key="logout_sidebar"):
            st.session_state.logged_in = False
            st.session_state.current_page = 'single' # Reset page on logout
            st.rerun() # This rerun is still needed to clear the app and show login immediately

    # ✅ Page logic now uses st.session_state.current_page (This part is largely unchanged)
    if st.session_state.current_page == 'single':
        st.markdown("<div class='custom-title'>📦 FedEx Shipment Tracking (Single)</div>", unsafe_allow_html=True)
        tracking_number = st.text_input("Enter Tracking Number:", placeholder="e.g., 581190049992")

        if st.button("Track Shipment"):
            with st.spinner("Getting access token..."):
                access_token = get_access_token()

            if access_token:
                with st.spinner("Fetching tracking details..."):
                    result = track_shipment(tracking_number, access_token)

                    if result:
                        st.subheader("Tracking Summary:")

                        try:
                            complete_results = result.get('output', {}).get('completeTrackResults', [])
                            if not complete_results:
                                st.warning("No tracking results found.")
                                return

                            track_results = complete_results[0].get('trackResults', [])
                            if not track_results:
                                st.warning("No track results found.")
                                return

                            track_info = track_results[0]
                            tracking_num = complete_results[0].get('trackingNumber', 'N/A')
                            st.write(f"**Tracking Number:** {tracking_num}")
                            current_status = track_info.get('latestStatusDetail', {}).get('statusByLocale', 'N/A')
                            st.write(f"**Current Status:** {current_status}")

                            date_times_info = track_info.get('dateAndTimes', []) # Renamed 'date_Times' to avoid confusion with the module
                            est_delivery = 'N/A'
                            for item in date_times_info:
                                if item.get('type') == 'ESTIMATED_DELIVERY':
                                    est_delivery = item.get('dateTime','N/A')
                                    break
                            if est_delivery != 'N/A':
                                try:
                                    est_delivery = pd.to_datetime(est_delivery)
                                except:
                                    pass
                            st.write(f"**Estimated Delivery:** {est_delivery}")

                            pod = 'N/A'
                            pod_list = track_info.get('availableImages', [])
                            for pod_item in pod_list: # Renamed 'pod_Item' to 'pod_item' for consistency
                                if pod_item.get('type'):
                                    pod = pod_item.get('type')
                                    break
                            st.write(f"**Proof of Delivery:** {pod}")

                            scan_events = track_info.get('scanEvents', [])
                            st.write("**Shipment History & Location Updates:**")

                            display_events = []
                            for event in scan_events:
                                event_desc = event.get('eventDescription', 'N/A')
                                # Renamed 'date' local variable to 'event_date_str' to avoid shadowing
                                event_date_str = event.get('date', 'N/A')
                                excep_desc = event.get('exceptionDescription', 'N/A')
                                try:
                                    # Use event_date_str here
                                    event_date_obj = pd.to_datetime(event_date_str)
                                except:
                                    event_date_obj = event_date_str # Keep as string if parsing fails

                                scan_loc = event.get('scanLocation', {})
                                loc_parts = []
                                for key in ['city', 'stateOrProvinceCode', 'countryCode', 'postalCode']:
                                    val = scan_loc.get(key)
                                    if val:
                                        loc_parts.append(val)
                                scan_location_str = ', '.join(loc_parts) if loc_parts else 'N/A'

                                display_events.append({
                                    'Event Description': event_desc,
                                    'Date': event_date_obj, # Use the parsed/original date
                                    'Exception Description' : excep_desc,
                                    'Location': scan_location_str
                                })

                            if display_events:
                                df = pd.DataFrame(display_events)
                                try:
                                    df = df.sort_values(by='Date', ascending=False)
                                except:
                                    pass
                                st.dataframe(df)
                            else:
                                st.info("No shipment history or exceptions available.")

                        except Exception as e:
                            st.error(f"Error extracting tracking details: {e}")

                        st.subheader("Full Raw JSON Response")
                        with st.expander("Show/Hide Full JSON"):
                            pretty_json = json.dumps(result, indent=2)
                            st.text_area("Full JSON Response", value=pretty_json, height=300)

    elif st.session_state.current_page == 'bulk':
        st.markdown("<div class='custom-title'>📂 Bulk Upload - Multiple Tracking Numbers</div>", unsafe_allow_html=True)
        st.download_button(
            label="📥 Download Sample Template",
            data=get_sample_template(),
            file_name="FedEx_Bulk_Upload_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type="xlsx")

        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if 'TrackingNumber' not in df.columns:
                    st.error("Excel must have a column named 'TrackingNumber'")
                else:
                    tracking_numbers = df['TrackingNumber'].dropna().astype(str).tolist()
                    reference_id = generate_reference()
                    with st.spinner("Getting access token..."):
                        access_token = get_access_token()

                    if not access_token:
                        st.error("Could not get API access token. Upload aborted.")
                        return

                    with st.spinner(f"Fetching tracking data for {len(tracking_numbers)} shipments..."):
                        success_count = 0
                        for tn in tracking_numbers:
                            result = track_shipment(tn, access_token)
                            if result:
                                save_upload_with_json(reference_id, tn, result)
                                success_count += 1
                            else:
                                st.warning(f"Failed to fetch tracking info for {tn}")
                            time.sleep(0.1)

                    st.success(f"✅ Upload Successful! Reference ID: `{reference_id}`")
                    st.write(f"Tracking info saved for {success_count} shipments.")
                    st.dataframe(pd.DataFrame({'Tracking Numbers': tracking_numbers}))

            except Exception as e:
                st.error(f"❌ Error processing file: {e}")

    elif st.session_state.current_page == 'results':
        st.markdown("<div class='custom-title'>🗂️ Shipment Tracking Results (Bulk Upload)</div>", unsafe_allow_html=True)
        
        # 1. Fetch all references (batches) from the database
        all_references_from_db = get_all_references() # This fetches from 'references_data'

        if not all_references_from_db:
            st.info("No bulk uploads found yet.")
            return # Exit if no references are found in the DB

        # 2. Allow user to filter the *batches* by upload date
        selected_date = st.date_input(
            "Filter Bulk Upload Batches by Upload Date:",
            value=datetime.date.today(), # Changed to datetime.date.today()
            key="date_filter_results_page"
        )

        # 3. Filter the references based on the selected_date
        filtered_references = []
        for r in all_references_from_db:
            try:
                # 'upload_time' exists in the 'references_data' table, so this is correct here
                #ref_upload_date = datetime.fromisoformat(r['upload_time']).date()
                ref_upload_date = datetime.datetime.fromisoformat(r['upload_time']).date()
                if ref_upload_date == selected_date:
                    filtered_references.append(r)
            except ValueError:
                st.warning(f"Could not parse upload time for reference {r.get('reference_id', 'N/A')}. Skipping date filter for this reference.")

        if not filtered_references:
            st.info(f"No bulk uploads found for `{selected_date.strftime('%Y-%m-%d')}`.")
            return # Exit if no batches match the date filter

        # 4. Prepare options for the selectbox from the filtered references
        ref_options = {f"{r['reference_id']} (Uploaded: {r['upload_time']})": r['reference_id'] for r in filtered_references}

        # Ensure selected_ref_id is valid for the currently filtered options
        if 'selected_ref_id' not in st.session_state or st.session_state.selected_ref_id not in ref_options.values():
            st.session_state.selected_ref_id = list(ref_options.values())[0] if ref_options else None

        if st.session_state.selected_ref_id is None:
            st.info("No batches available for selection after date filter.")
            return

        selected_ref_display = st.selectbox(
            "Select a Bulk Upload Reference (Batch ID):",
            options=list(ref_options.keys()),
            key="batch_id_selector",
            # Set index to the current selected_ref_id if it's in the filtered options
            index=list(ref_options.values()).index(st.session_state.selected_ref_id) if st.session_state.selected_ref_id in list(ref_options.values()) else 0
        )
        st.session_state.selected_ref_id = ref_options[selected_ref_display]

        # 5. Button to fetch results for the selected batch ID
        if st.button("Fetch Tracking Results for Selected Batch"):
            # Fetch ALL tracking data for the selected reference_id.
            # No further date filtering needed here, as the batch itself was already filtered by date.
            all_saved_data_for_ref = get_tracking_json(st.session_state.selected_ref_id)

            if not all_saved_data_for_ref:
                st.warning(f"No tracking data found for Reference ID `{st.session_state.selected_ref_id}`.")
                return

            all_results = []
            def event_date(ev):
                try:
                    dt = pd.to_datetime(ev.get('date', ''))
                    if dt.tzinfo is not None:
                        dt = dt.tz_localize(None)
                    return dt
                except:
                    return pd.Timestamp.min

            for entry in all_saved_data_for_ref:
                tn = entry['tracking_number']
                raw_json = entry['raw_json'] # This is correct: raw_json is a dict/list

                complete_results = raw_json.get('output', {}).get('completeTrackResults', [])
                if complete_results:
                    tracking_num = complete_results[0].get('trackingNumber', tn)
                    track_results = complete_results[0].get('trackResults', [])
                    if track_results:
                        track_info = track_results[0]
                        status = track_info.get('latestStatusDetail', {}).get('statusByLocale', 'N/A')
                        est_delivery = 'N/A'
                        date_times_list = track_info.get('dateAndTimes', []) # Renamed to avoid shadowing
                        for item in date_times_list:
                            if item.get('type') == 'ESTIMATED_DELIVERY':
                                est_delivery = item.get('dateTime', 'N/A')
                                try:
                                    dt_est = pd.to_datetime(est_delivery)
                                    if dt_est.tzinfo is not None:
                                        dt_est = dt_est.tz_localize(None)
                                    est_delivery = dt_est
                                except:
                                    pass
                                break
                        pod = 'N/A'
                        pod_list = track_info.get('availableImages', [])
                        for pod_item in pod_list:
                            pod_type = pod_item.get('type', '')
                            if pod_type:
                                pod = pod_type
                                break

                        scan_events = track_info.get('scanEvents', [])
                        if scan_events:
                            latest_event = max(scan_events, key=event_date)
                            event_desc = latest_event.get('eventDescription', 'N/A')
                            event_date_val = latest_event.get('date', 'N/A')
                            try:
                                dt_val = pd.to_datetime(event_date_val)
                                if dt_val.tzinfo is not None:
                                    dt_val = dt_val.tz_localize(None)
                                event_date_val = dt_val
                            except:
                                pass
                            scan_loc = latest_event.get('scanLocation', {})
                            loc_parts = []
                            for key in ['city', 'stateOrProvinceCode', 'countryCode', 'postalCode']:
                                val = scan_loc.get(key)
                                if val:
                                    loc_parts.append(val)
                            scan_location_str = ', '.join(loc_parts) if loc_parts else 'N/A'
                        else:
                            event_desc = 'N/A'
                            event_date_val = 'N/A'
                            scan_location_str = 'N/A'
                    else:
                        status = 'N/A'
                        est_delivery = 'N/A'
                        pod = 'N/A'
                        event_desc = 'N/A'
                        event_date_val = 'N/A'
                        scan_location_str = 'N/A'
                else:
                    tracking_num = tn
                    status = 'N/A'
                    est_delivery = 'N/A'
                    pod = 'N/A'
                    event_desc = 'N/A'
                    event_date_val = 'N/A'
                    scan_location_str = 'N/A'

                all_results.append({
                    'Tracking Number': tracking_num,
                    'Status': status,
                    'Estimated Delivery': est_delivery,
                    'Proof of Delivery': pod,
                    'Latest Event': event_desc,
                    'Event Date': event_date_val,
                    'Location': scan_location_str
                })

            st.success("Results Fetched Successfully!")
            result_df = pd.DataFrame(all_results)
            try:
                result_df = result_df.sort_values(by='Event Date', ascending=False)
            except Exception:
                pass
            st.dataframe(result_df)
            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results as CSV", data=csv, file_name=f"{st.session_state.selected_ref_id}_{selected_date.strftime('%Y-%m-%d')}_results.csv", mime='text/csv')


    elif st.session_state.current_page == 'analytics':
        st.markdown("<div class='custom-title'>📊 Analytics Dashboard</div>", unsafe_allow_html=True)
        st.subheader("Shipment Performance Overview")

        references = get_all_references()
        if not references:
            st.info("No bulk uploads found yet to analyze.")
            return

        reference_options_for_analytics = {"All Uploads": "all_uploads"}
        reference_options_for_analytics.update({f"{r['reference_id']} (Uploaded: {r['upload_time']})": r['reference_id'] for r in references})

        selected_analytics_ref_key = st.selectbox(
            "Select Bulk Upload(s) for Analysis:",
            options=list(reference_options_for_analytics.keys()),
            key="analytics_ref_selector"
        )
        selected_analytics_ref_id = reference_options_for_analytics[selected_analytics_ref_key]

        all_raw_tracking_data = []

        if selected_analytics_ref_id == "all_uploads":
            with st.spinner("Fetching all tracking data for analysis..."):
                for ref_item in references:
                    all_raw_tracking_data.extend(get_tracking_json(ref_item['reference_id']))
        else:
            with st.spinner(f"Fetching tracking data for {selected_analytics_ref_id}..."):
                all_raw_tracking_data = get_tracking_json(selected_analytics_ref_id)

        if not all_raw_tracking_data:
            st.info("No tracking data available for the selected range to generate analytics.")
            return

        processed_data = []
        for entry in all_raw_tracking_data:
            tn = entry['tracking_number']
            # REMOVED: raw_json = json.loads(entry['raw_json'])
            # The 'raw_json' column from Supabase is already parsed JSONB (Python dict/list)
            raw_json = entry['raw_json']

            complete_results = raw_json.get('output', {}).get('completeTrackResults', [])
            if complete_results:
                track_results = complete_results[0].get('trackResults', [])
                if track_results:
                    track_info = track_results[0]
                    current_status = track_info.get('latestStatusDetail', {}).get('statusByLocale', 'UNKNOWN')
                    shipper_city = track_info.get('shipperInformation', {}).get('address', {}).get('city', 'N/A')
                    recipient_city = track_info.get('recipientInformation', {}).get('address', {}).get('city', 'N/A')
                    weight_value = 'N/A'
                    package_weights = track_info.get('packageDetails', {}).get('weightAndDimensions', {}).get('weight', [])
                    if package_weights:
                        try:
                            weight_value = float(package_weights[0].get('value', 'N/A'))
                        except (ValueError, TypeError):
                            weight_value = 'N/A'
                    processed_data.append({
                        'Tracking Number': tn,
                        'Status': current_status,
                        'Shipper City': shipper_city,
                        'Recipient City': recipient_city,
                        'Weight Value': weight_value,
                        'Weight Value (LB)': weight_value
                    })

        if not processed_data:
            st.info("No detailed tracking data could be processed for analytics.")
            return

        df_analytics = pd.DataFrame(processed_data)
        df_analytics['Weight Value (LB)'] = pd.to_numeric(df_analytics['Weight Value (LB)'], errors='coerce')

        st.markdown("---")
        st.subheader("Key Performance Indicators")
        col1, col2, col3, col4 = st.columns(4)
        total_shipments = len(df_analytics)
        delivered_shipments = df_analytics[df_analytics['Status'] == 'Delivered'].shape[0]
        in_transit_shipments = df_analytics[(df_analytics['Status'] != 'Delivered') & (~df_analytics['Status'].str.contains('exception', case=False, na=False))].shape[0]
        exception_shipments = df_analytics[df_analytics['Status'].str.contains('exception', case=False, na=False)].shape[0]

        with col1:
            st.metric("Total Shipments", total_shipments)
        with col2:
            st.metric("Delivered Shipments", delivered_shipments)
        with col3:
            st.metric("In-Transit Shipments", in_transit_shipments)
        with col4:
            st.metric("Shipments with Exceptions", exception_shipments)
        
        st.markdown("---")
        col_shipper, col_recipient = st.columns(2)

        with col_shipper:
            st.subheader("Shipments by Shipper City")
            valid_shipper_cities = df_analytics[df_analytics['Shipper City'] != 'N/A']
            valid_shipper_cities = valid_shipper_cities[valid_shipper_cities['Shipper City'] != '']
            if not valid_shipper_cities.empty:
                shipper_city_counts = valid_shipper_cities['Shipper City'].value_counts().reset_index()
                shipper_city_counts.columns = ['Shipper City', 'Count']
                base_shipper = alt.Chart(shipper_city_counts).encode(theta=alt.Theta("Count", stack=True))
                pie_shipper = base_shipper.mark_arc(outerRadius=120).encode(
                    color=alt.Color("Shipper City"), order=alt.Order("Count", sort="descending"),
                    tooltip=["Shipper City", "Count", alt.Tooltip("Count", format=".1%")]
                )
                text_shipper = base_shipper.mark_text(radius=140).encode(
                    text=alt.Text("Count", format=".0f"), order=alt.Order("Count", sort="descending"),
                    color=alt.value("black")
                )
                chart_shipper_cities = (pie_shipper + text_shipper).properties(title='Shipments by Shipper City')
                st.altair_chart(chart_shipper_cities, use_container_width=True)
            else:
                st.info("No valid shipper city data to display.")

        with col_recipient:
            st.subheader("Shipments by Recipient City")
            valid_recipient_cities = df_analytics[df_analytics['Recipient City'] != 'N/A']
            valid_recipient_cities = valid_recipient_cities[valid_recipient_cities['Recipient City'] != '']
            if not valid_recipient_cities.empty:
                recipient_city_counts = valid_recipient_cities['Recipient City'].value_counts().reset_index()
                recipient_city_counts.columns = ['Recipient City', 'Count']
                base_recipient = alt.Chart(recipient_city_counts).encode(theta=alt.Theta("Count", stack=True))
                pie_recipient = base_recipient.mark_arc(outerRadius=120).encode(
                    color=alt.Color("Recipient City"), order=alt.Order("Count", sort="descending"),
                    tooltip=["Recipient City", "Count", alt.Tooltip("Count", format=".1%")]
                )
                text_recipient = base_recipient.mark_text(radius=140).encode(
                    text=alt.Text("Count", format=".0f"), order=alt.Order("Count", sort="descending"),
                    color=alt.value("black")
                )
                chart_recipient_cities = (pie_recipient + text_recipient).properties(title='Shipments by Recipient City')
                st.altair_chart(chart_recipient_cities, use_container_width=True)
            else:
                st.info("No valid recipient city data to display.")

        st.markdown("---")
        st.subheader("Distribution of Shipment Weights")
        valid_weights = df_analytics.dropna(subset=['Weight Value (LB)'])
        if not valid_weights.empty:
            chart_weights = alt.Chart(valid_weights).mark_bar().encode(
                alt.X('Weight Value (LB)', bin=alt.Bin(maxbins=20), title='Weight (LB)'),
                alt.Y('count()', title='Number of Shipments'),
                tooltip=[alt.Tooltip('Weight Value (LB)', bin=True, title='Weight Range'), 'count()']
            ).properties(
                title='Distribution of Shipment Weights'
            )
            st.altair_chart(chart_weights, use_container_width=True)
        else:
            st.info("No valid weight data to display.")
    else:
        st.warning("An unexpected page state was encountered.")


# --- Application Entry Point ---
if st.session_state.logged_in:
    main_app()
else:
    login_page()