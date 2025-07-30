import os
import math # Importiamo la libreria matematica per controllare i valori NaN
from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi

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
