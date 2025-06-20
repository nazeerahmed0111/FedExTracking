import os
import json
from datetime import datetime
import random
import string
import psycopg2 # <-- PostgreSQL library
from urllib.parse import urlparse
from dotenv import load_dotenv # For loading environment variables locally

# Load environment variables from a .env file for local development
# In production (e.g., Streamlit Cloud), these env vars will be set directly.
load_dotenv()

# --- Database Configuration ---
# DATABASE_URL is essential for connecting to your Neon database
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Warning: DATABASE_URL environment variable is not set. Database functions may fail.")
    print("Please set DATABASE_URL in your environment or .env file for local testing.")
    # In a production app, you might want to raise an error here to prevent startup

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Cannot connect to database.")
    
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:], # Path is '/database_name', so [1:] removes the '/'
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            # Neon typically requires sslmode=require for secure connections
            sslmode='require' if url.query and 'sslmode=require' in url.query else 'prefer'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        # In a real app, you might want to log this error and provide user feedback
        raise # Re-raise the exception to indicate a critical failure

def init_db():
    """Initializes the database by creating tables if they do not exist."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Table to store unique bulk upload references (batch info)
        # We'll use this to get a representative upload_time for the batch
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                reference_id TEXT PRIMARY KEY,
                upload_time TEXT NOT NULL
            );
        """)
        
        # Table to store individual tracking numbers and their raw JSON data
        # 'id' is SERIAL for auto-incrementing primary key in PostgreSQL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracking_data (
                id SERIAL PRIMARY KEY,
                reference_id TEXT NOT NULL,
                tracking_number TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                upload_time TEXT NOT NULL,
                -- Foreign key constraint to link to the 'uploads' table
                FOREIGN KEY (reference_id) REFERENCES uploads (reference_id) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print("PostgreSQL tables created or already exist.")
    except Exception as e:
        print(f"Error initializing PostgreSQL database: {e}")
    finally:
        if conn:
            conn.close()

def generate_reference():
    """Generates a unique reference ID based on timestamp and random characters."""
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BULK-{now}-{rand}"

def save_upload_with_json(reference_id, tracking_number, raw_json):
    """
    Saves a single tracking entry and associates it with a reference_id.
    Also ensures the reference_id exists in the 'uploads' table.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        upload_time = datetime.now().isoformat()

        # Insert into 'uploads' table. If reference_id already exists, do nothing.
        # This handles multiple tracking numbers in one batch associated with the same reference_id.
        cursor.execute(
            "INSERT INTO uploads (reference_id, upload_time) VALUES (%s, %s) ON CONFLICT (reference_id) DO NOTHING;",
            (reference_id, upload_time)
        )
        
        # Insert into 'tracking_data' table
        cursor.execute(
            "INSERT INTO tracking_data (reference_id, tracking_number, raw_json, upload_time) VALUES (%s, %s, %s, %s);",
            (reference_id, tracking_number, raw_json, upload_time)
        )
        conn.commit()
        return True # Indicate success
    except Exception as e:
        print(f"Error saving tracking data for {tracking_number} (Ref: {reference_id}): {e}")
        if conn:
            conn.rollback() # Rollback changes if an error occurs
        return False # Indicate failure
    finally:
        if conn:
            conn.close()

def get_all_references():
    """
    Retrieves all unique reference IDs and their earliest upload times from the tracking_data table.
    This effectively gives you a list of all unique bulk uploads.
    """
    conn = None
    references = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Using MIN(upload_time) from 'tracking_data' to get the earliest upload time for each batch
        cursor.execute("SELECT reference_id, MIN(upload_time) AS upload_time FROM tracking_data GROUP BY reference_id ORDER BY upload_time DESC;")
        rows = cursor.fetchall()
        # Convert list of tuples to list of dictionaries for easier handling
        for row in rows:
            references.append({"reference_id": row[0], "upload_time": row[1]})
    except Exception as e:
        print(f"Error getting all references from PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()
    return references

def get_tracking_numbers(reference_id):
    """Retrieves all tracking numbers associated with a given reference ID."""
    conn = None
    tracking_numbers = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tracking_number FROM tracking_data WHERE reference_id = %s ORDER BY tracking_number;",
            (reference_id,) # Note the comma for a single-element tuple
        )
        rows = cursor.fetchall()
        tracking_numbers = [row[0] for row in rows] # Each row is a tuple, we want the first element
    except Exception as e:
        print(f"Error getting tracking numbers for reference {reference_id} from PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()
    return tracking_numbers

def get_tracking_json(reference_id):
    """
    Retrieves all tracking data (tracking_number, raw_json, upload_time)
    for a given reference ID.
    """
    conn = None
    tracking_data_entries = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tracking_number, raw_json, upload_time FROM tracking_data WHERE reference_id = %s ORDER BY upload_time DESC;",
            (reference_id,) # Note the comma for a single-element tuple
        )
        rows = cursor.fetchall()
        # Convert list of tuples to list of dictionaries for easier consumption
        for row in rows:
            tracking_data_entries.append({
                "tracking_number": row[0],
                "raw_json": row[1],
                "upload_time": row[2]
            })
    except Exception as e:
        print(f"Error getting tracking JSON for reference {reference_id} from PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()
    return tracking_data_entries

# --- Initialize the database when this module is imported ---
# This ensures tables are created when the Streamlit app starts
init_db()