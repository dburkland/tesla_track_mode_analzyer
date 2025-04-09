import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np
import psycopg2
import sys

def clean_headers(df):
    df.columns = [col.split('(')[0].strip().replace(' ', '_').lower() for col in df.columns]
    return df

def process_csv(filename, pg_hostname, pg_username, pg_password, table_name, motor_count):
    # Load CSV file
    print(f"Processing file: {filename}")
    df = pd.read_csv(filename)
    
    # Clean headers
    df = clean_headers(df)
    print("Headers cleaned")

    # Delete rows where Lap = 0
    df = df[df['lap'] != 0]
    print(f"Rows after filtering Lap != 0: {len(df)}")
    
    if df.empty:
        print(f"No data to process in {filename}. Skipping this file.")
        return

    # Add session column (convert to integer if possible, or adjust table schema later)
    session_value = os.path.splitext(filename)[0]  # e.g., "1" from "1.csv"
    try:
        df['session'] = int(session_value)  # Convert to integer
    except ValueError:
        df['session'] = session_value  # Keep as string if conversion fails
    print("Session column added")

    # Reorder columns to put 'session' as the leftmost column
    cols = df.columns.tolist()
    cols.insert(0, cols.pop(cols.index('session')))
    df = df[cols]
    print("Session column reordered")

    # Set start time
    start_time = datetime(2024, 1, 1, 18, 0, 0)

    # Create time column
    df['time'] = pd.NaT  # Initialize time column with NaT (Not a Time)

    # Fill time column, converting numpy.int64 to int and using .loc for assignment
    df.loc[df.index[0], 'time'] = start_time + timedelta(milliseconds=int(df.loc[df.index[0], 'elapsed_time']))
    for i in range(1, len(df)):
        prev_time = df.loc[df.index[i-1], 'time']
        time_diff = int(df.loc[df.index[i], 'elapsed_time'] - df.loc[df.index[i-1], 'elapsed_time'])
        df.loc[df.index[i], 'time'] = prev_time + timedelta(milliseconds=time_diff)
    print("Time column populated")

    # Reorder columns to put 'time' as the leftmost column
    cols = df.columns.tolist()
    cols.insert(0, cols.pop(cols.index('time')))
    df = df[cols]
    print("Time column reordered")

    # Save to new CSV file
    new_filename = f"{os.path.splitext(filename)[0]}_new.csv"
    df.to_csv(new_filename, index=False)
    print(f"New file saved: {new_filename}")

    # Connect to PostgreSQL database
    try:
        conn = psycopg2.connect(
            host=pg_hostname,
            port=5432,
            database="tesla_track_db",
            user=pg_username,
            password=pg_password
        )
        print("Connected to the PostgreSQL database successfully")
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        return

    # Create table if it doesn't exist
    try:
        with conn.cursor() as cursor:
            if motor_count == 2:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        time TIMESTAMP,
                        session INTEGER,
                        lap INTEGER,
                        elapsed_time INTEGER,
                        speed FLOAT,
                        latitude FLOAT,
                        longitude FLOAT,
                        lateral_acceleration FLOAT,
                        longitudinal_acceleration FLOAT,
                        throttle_position FLOAT,
                        brake_pressure FLOAT,
                        steering_angle FLOAT,
                        steering_angle_rate FLOAT,
                        yaw_rate FLOAT,
                        power_level FLOAT,
                        state_of_charge FLOAT,
                        tire_pressure_front_left FLOAT,
                        tire_pressure_front_right FLOAT,
                        tire_pressure_rear_left FLOAT,
                        tire_pressure_rear_right FLOAT,
                        brake_temperature_front_left FLOAT,
                        brake_temperature_front_right FLOAT,
                        brake_temperature_rear_left FLOAT,
                        brake_temperature_rear_right FLOAT,
                        front_inverter_temp FLOAT,
                        rear_inverter_temp FLOAT,
                        battery_temp FLOAT,
                        tire_slip_front_left FLOAT,
                        tire_slip_front_right FLOAT,
                        tire_slip_rear_left FLOAT,
                        tire_slip_rear_right FLOAT      
                    )
                """)
            elif motor_count == 3:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        time TIMESTAMP,
                        session INTEGER,
                        lap INTEGER,
                        elapsed_time INTEGER,
                        speed FLOAT,
                        latitude FLOAT,
                        longitude FLOAT,
                        lateral_acceleration FLOAT,
                        longitudinal_acceleration FLOAT,
                        throttle_position FLOAT,
                        brake_pressure FLOAT,
                        steering_angle FLOAT,
                        steering_angle_rate FLOAT,
                        yaw_rate FLOAT,
                        power_level FLOAT,
                        state_of_charge FLOAT,
                        tire_pressure_front_left FLOAT,
                        tire_pressure_front_right FLOAT,
                        tire_pressure_rear_left FLOAT,
                        tire_pressure_rear_right FLOAT,
                        brake_temperature_front_left FLOAT,
                        brake_temperature_front_right FLOAT,
                        brake_temperature_rear_left FLOAT,
                        brake_temperature_rear_right FLOAT,
                        front_inverter_temp FLOAT,
                        rear_left_inverter_temp FLOAT,
                        rear_right_inverter_temp FLOAT,
                        battery_temp FLOAT,
                        tire_slip_front_left FLOAT,
                        tire_slip_front_right FLOAT,
                        tire_slip_rear_left FLOAT,
                        tire_slip_rear_right FLOAT      
                    )
                """)
            conn.commit()  # Commit the table creation
            print(f"Created table {table_name} if it did not exist")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.close()
        return  # Exit if table creation fails

    # Copy data from CSV to PostgreSQL
    try:
        with conn.cursor() as cursor:
            cursor.copy_expert(f"COPY {table_name} FROM STDIN WITH CSV HEADER", open(new_filename, 'r'))
            conn.commit()
            print(f"Data from {new_filename} has been successfully copied to the database in table {table_name}")
    except Exception as e:
        print(f"Error copying data to PostgreSQL: {e}")
        conn.close()
        return
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: script.py <PGSQL_Hostname> <PGSQL_Username> <PGSQL_Password> <track_name>_<track_event>_<YYYYMMDD> <motor_count>")
        print("Example 1: script.py localhost postgres Password123 buttonwillow_tc38_20241221 2")
        print("Example 2: script.py localhost postgres Password123 buttonwillow_tc38_20241221 3")
        sys.exit(1)
    
    pg_hostname = sys.argv[1]
    pg_username = sys.argv[2]
    pg_password = sys.argv[3]
    table_name = sys.argv[4]
    motor_count = int(sys.argv[5])  # Convert motor_count to integer
    
    filename = "1.csv"
    process_csv(filename, pg_hostname, pg_username, pg_password, table_name, motor_count)

    # # Process each CSV file (uncomment if needed)
    # for i in range(1, 5):
    #     filename = f"{i}.csv"
    #     process_csv(filename, pg_hostname, pg_username, pg_password, table_name, motor_count)

    print("All files processed.")
