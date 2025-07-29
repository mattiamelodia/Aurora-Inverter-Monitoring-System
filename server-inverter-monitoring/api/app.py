import os
import math # Importiamo la libreria matematica per controllare i valori NaN
from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

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

VALIDATION_RANGES = {
    "grid_voltage": (180, 280),
    "power_in_total": (0, 10000), 
    "inverter_temp": (-20, 120),
}

# --- API Endpoint Definition ---
@app.route('/api/reading', methods=['POST'])
def receive_reading():
    if not client:
        return jsonify({"status": "error", "message": "Server-side error: InfluxDB client not initialized"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid or empty JSON payload"}), 400

    # print(f"Data received from ESP: {data}")

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
