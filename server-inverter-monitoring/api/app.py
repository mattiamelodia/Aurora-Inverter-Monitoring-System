import os
import math
import time
from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
import requests

# --- Flask App Initialization ---
app = Flask(__name__)

# --- InfluxDB Configuration ---
INFLUXDB_URL = os.environ.get("INFLUXDB_URL")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET")

# --- Initialize InfluxDB Client ---
try:
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    print("Successfully connected to InfluxDB.")
except Exception as e:
    print(f"FATAL: Could not connect to InfluxDB. Please check credentials and URL. Error: {e}")
    client = None
    
query_api = client.query_api()

VALIDATION_RANGES = {
    "grid_voltage": (180, 280),
    "power_in_total": (0, 10000), 
    "inverter_temp": (-20, 120),
}

# --- Gotify Configuration ---
GOTIFY_URL = os.environ.get("GOTIFY_URL")
GOTIFY_TOKEN = os.environ.get("GOTIFY_TOKEN")
SAME_VALUE_THRESHOLD = 5

last_power_value = None
same_value_count = 0
last_notification_time = 0

def send_gotify_notification(title, message, priority=5):
    if not GOTIFY_URL or not GOTIFY_TOKEN:
        print("Gotify URL or token not configured, skipping notification.")
        return

    headers = {"Content-Type": "application/json"}
    data = {"title": title, "message": message, "priority": priority}
    
    try:
        response = requests.post(
            f"{GOTIFY_URL}/message?token={GOTIFY_TOKEN}",
            json=data,
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            print("Gotify notification sent successfully.")
        else:
            print(f"Failed to send Gotify notification: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending Gotify notification: {e}")


@app.route('/api/power', methods=['GET'])
def get_power():
    if not client:
        return jsonify({"status": "error", "message": "InfluxDB client not initialized"}), 500
    try:
        query = f'''
        from(bucket:"{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "inverter_readings" and r._field == "power_in_total")
        |> last()
        '''
        tables = query_api.query(query, org=INFLUXDB_ORG)

        if not tables or len(tables) == 0:
            return jsonify({"status": "error", "message": "No data found"}), 404
        
        last_power = None
        for table in tables:
            for record in table.records:
                last_power = record.get_value()

        if last_power is None:
            return jsonify({"status": "error", "message": "No power data available"}), 404
        
        return jsonify({
            "status": "success",
            "power_in_total": last_power
        })

    except Exception as e:
        print(f"ERROR fetching power data: {e}")
        return jsonify({"status": "error", "message": "Error fetching data"}), 500
    

@app.route('/api/energy/today', methods=['GET'])
def get_today_energy():
    if not client:
        return jsonify({"status": "error", "message": "InfluxDB client not initialized"}), 500
    try:
        query = f'''
        from(bucket:"{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "inverter_readings" and r._field == "cumulated_energy_today")
        |> last()
        '''
        tables = query_api.query(query, org=INFLUXDB_ORG)

        if not tables or len(tables) == 0:
            return jsonify({"status": "error", "message": "No data found"}), 404
        
        cumulated_energy_today = None
        for table in tables:
            for record in table.records:
                cumulated_energy_today = record.get_value()

        if cumulated_energy_today is None:
            return jsonify({"status": "error", "message": "No energy data available"}), 404
        
        return jsonify({
            "status": "success",
            "cumulated_energy_today": cumulated_energy_today
        })

    except Exception as e:
        print(f"ERROR fetching power data: {e}")
        return jsonify({"status": "error", "message": "Error fetching data"}), 500
    

@app.route('/api/inverter_data', methods=['POST'])
def receive_reading():
    global last_power_value, same_value_count, last_notification_time

    if not client:
        return jsonify({"status": "error", "message": "Server-side error: InfluxDB client not initialized"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid or empty JSON payload"}), 400

    current_power = data.get('power_in_total')
    if current_power is not None and isinstance(current_power, (int, float)) and math.isfinite(current_power):
        if last_power_value is None:
            # First reading, initialize the last power value
            last_power_value = current_power
            same_value_count = 0
        elif current_power == last_power_value:
            same_value_count += 1
            print(f"Received same power value: {current_power} W, count: {same_value_count}")

            if same_value_count >= SAME_VALUE_THRESHOLD:
                current_time = time.time()
                if current_time - last_notification_time >= 300:
                    send_gotify_notification(
                        title="Inverter Power Alert",
                        message=f"Power value has not changed for the last {SAME_VALUE_THRESHOLD} readings: {current_power} W",
                        priority=5
                    )
                    last_notification_time = current_time
        else:
            # New reading, reset the counter
            last_power_value = current_power
            same_value_count = 0
            print(f"New power value received: {current_power} W, resetting counter.")            
    try:
        point = Point("inverter_readings") \
            .tag("device_name", "main_inverter")

        valid_fields = 0
        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, (int, float)):
                if not math.isfinite(value):
                    print(f"Skipping non-finite value for key '{key}': {value}")
                    continue
                
                if key in VALIDATION_RANGES:
                    min_val, max_val = VALIDATION_RANGES[key]
                    if not (min_val <= value <= max_val):
                        print(f"Skipping out-of-range value for key '{key}': {value}")
                        continue
                    
                point.field(key, float(value)) 
                valid_fields += 1
            
            elif isinstance(value, str):
                if value:
                    point.tag(key, value)

        if valid_fields == 0:
            print("Warning: Received data but no valid numerical fields to store.")
            return jsonify({"status": "success", "message": "Data received but contained no storeable fields"}), 200

        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        return jsonify({"status": "success", "message": "Data stored"}), 201

    except Exception as e:
        print(f"ERROR: An unexpected error occurred while processing data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An internal error occurred while processing the data"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
