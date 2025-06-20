import os
import json
from datetime import datetime, date
import random
import string
#from dotenv import load_dotenv # <--- ADD THIS IMPORT
from supabase import create_client, Client
import streamlit as st # Only needed for st.cache_resource, etc.

# --- Step 1: Explicitly load environment variables at the very top ---
# This ensures that if db_helper.py is imported or run directly,
# it has access to the environment variables.
# Specify the absolute path to your .env.txt file for robustness.
env_file_path = "C:\\Users\\rcmsbot\\Documents\\FedEx Shipment Tracker\\.env.txt"

print(f"DEBUG: Attempting to load .env from: {env_file_path}")
if os.path.exists(env_file_path):
    load_dotenv(dotenv_path=env_file_path)
    print(f"DEBUG: Successfully called load_dotenv for {env_file_path}")
else:
    print(f"ERROR: .env file NOT FOUND at: {env_file_path}. Please check the path.")
    # Exit or raise an error immediately if the .env is critical and not found
    # import sys
    # sys.exit("Missing .env file. Exiting.")


# --- Step 2: Retrieve environment variables and print their status ---
# Ensure these variables are read AFTER load_dotenv()
'''
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
FEDEX_API_KEY = os.getenv("FEDEX_API_KEY")
FEDEX_API_SECRET = os.getenv("FEDEX_API_SECRET")
'''

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]
FEDEX_API_KEY = st.secrets["FEDEX_API_KEY"]
FEDEX_API_SECRET = st.secrets["FEDEX_API_SECRET"]



print(f"DEBUG (db_helper): SUPABASE_URL = {'(set)' if SUPABASE_URL else '(None)'}")
print(f"DEBUG (db_helper): SUPABASE_ANON_KEY = {'(set)' if SUPABASE_ANON_KEY else '(None)'}")
print(f"DEBUG (db_helper): SUPABASE_SERVICE_KEY = {'(set)' if SUPABASE_SERVICE_KEY else '(None)'}") # THIS IS THE CRITICAL ONE
print(f"DEBUG (db_helper): FEDEX_API_KEY = {'(set)' if FEDEX_API_KEY else '(None)'}")
print(f"DEBUG (db_helper): FEDEX_API_SECRET = {'(set)' if FEDEX_API_SECRET else '(None)'}")


# --- Supabase Client Initialization ---
@st.cache_resource
def get_supabase_client():
    if not SUPABASE_URL:
        st.error("Supabase URL is not set. Please configure SUPABASE_URL in your .env.txt.")
        raise ValueError("Supabase URL missing.")
    if not SUPABASE_ANON_KEY:
        st.error("Supabase ANON Key is not set. Please configure SUPABASE_ANON_KEY in your .env.txt.")
        raise ValueError("Supabase ANON Key missing.")
    
    try:
        print("DEBUG: Initializing Supabase client with ANON_KEY...") # Debugging
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as e:
        st.error(f"Error initializing Supabase client with ANON key: {e}")
        print(f"ERROR: Supabase ANON client initialization failed: {e}")
        raise

supabase: Client = get_supabase_client()


# --- Database Initialization Function ---
def init_db():
    print("DEBUG: Entering init_db function.")
    print(f"DEBUG (init_db): SUPABASE_URL = {'(set)' if SUPABASE_URL else '(None)'}")
    print(f"DEBUG (init_db): SUPABASE_SERVICE_KEY = {'(set)' if SUPABASE_SERVICE_KEY else '(None)'}") # AGAIN, CRITICAL

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        error_msg = "Supabase URL or SERVICE Key is not set for database initialization. Please configure SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env.txt."
        st.error(error_msg)
        print(f"ERROR: {error_msg}")
        raise ValueError("Supabase SERVICE_KEY credentials missing for init_db.")

    try:
        # Create a client with the SERVICE_KEY for admin tasks
        print("DEBUG: Attempting to create admin_supabase client...")
        admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) # <--- THIS IS THE LINE THAT IS FAILING
        print("DEBUG: admin_supabase client created successfully.")
        
        # ... (rest of your init_db function remains the same, assuming tables are pre-created or handled)
        print("Database initialization check (tables assumed to exist).")

    except Exception as e:
        error_msg = f"Error during database initialization (init_db): {e}"
        print(f"ERROR: {error_msg}")
        st.error(f"Failed to initialize database tables: {e}. Ensure Supabase SERVICE_KEY is correct and tables are created.")
        raise # Re-raise to halt execution if DB init fails

# --- Utility Functions (unchanged from your code, keeping for completeness) ---

def generate_reference():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REF-{timestamp}-{random_str}"



# (Keep all your existing code above this function, including load_dotenv,
# SUPABASE_URL, etc., and the @st.cache_resource get_supabase_client, and init_db)

def save_upload_with_json(reference_id, tracking_number, raw_json_data):
    try:
        # Use upsert() for the 'references' table
        reference_data, count = supabase.table('references_data').upsert({
            "reference_id": reference_id,
            "upload_time": datetime.now().isoformat()
        }, on_conflict='reference_id').execute()

        # --- REVISED DEBUGGING BLOCK FOR JSON DATA ---
        print(f"\n--- DEBUGGING JSON FOR TRACKING: {tracking_number} ---")
        print(f"DEBUG: Type of 'raw_json_data' received by save_upload_with_json: {type(raw_json_data)}")
        print(f"DEBUG: Content of 'raw_json_data' (truncated if long): {str(raw_json_data)[:500]}...")

        json_to_save = raw_json_data # <--- THIS IS THE KEY CHANGE!

        # Optional: Add a check for type, though Supabase client is usually robust
        if not isinstance(json_to_save, (dict, list, type(None))):
            print(f"WARNING: 'json_to_save' is not a dict, list, or None. Type: {type(json_to_save)}")
            st.warning(f"Unexpected data type for JSON column: {type(json_to_save)}. Attempting to save.")

        print(f"DEBUG: Final object to be saved as JSONB. Type: {type(json_to_save)}")
        # --- END DEBUGGING BLOCK ---

        # Then insert into 'tracking_datanew'
        data, count = supabase.table('tracking_datanew').insert({
            "reference_id": reference_id,
            "tracking_number": tracking_number,
            "raw_json": json_to_save # Pass the dict/list directly
        }).execute()
        
        print(f"DEBUG: Data successfully inserted for tracking number: {tracking_number}")
        return True
    except Exception as e:
        error_message = f"Error saving tracking data for {tracking_number}: {e}"
        st.error(error_message)
        print(f"ERROR (save_upload_with_json): {error_message}")
        import traceback
        traceback.print_exc() # Print full traceback for this specific error
        return False

# (Keep the rest of your db_helper.py, including get_all_references, get_tracking_numbers, etc.,
# and the final init_db() call)


def get_all_references():
    try:
        response = supabase.table('references_data').select('*').order('upload_time', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching references: {e}")
        return []

def get_tracking_numbers(reference_id):
    try:
        response = supabase.table('tracking_datanew').select('tracking_number').eq('reference_id', reference_id).execute()
        return [item['tracking_number'] for item in response.data]
    except Exception as e:
        st.error(f"Error fetching tracking numbers for {reference_id}: {e}")
        return []

def get_tracking_json(reference_id):
    try:
        response = supabase.table('tracking_datanew').select('*').eq('reference_id', reference_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching tracking JSON for {reference_id}: {e}")
        return []

# --- Initializing the database tables on app start ---
try:
    print("DEBUG: Calling init_db() at the end of db_helper.py.")
    init_db()
except Exception as e:
    fatal_error_msg = f"FATAL ERROR: Database initialization failed. Please check your Supabase keys and table setup. Details: {e}"
    st.error(fatal_error_msg)
    print(f"ERROR: {fatal_error_msg}")
    import sys
    sys.exit(1) # Exit if critical initialization fails