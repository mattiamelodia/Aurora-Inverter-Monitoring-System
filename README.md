# Aurora-Inverter-Monitoring-System

A Docker-based and ESP32-powered system for monitoring Aurora/Power-One inverters. It collects real-time data, stores it in InfluxDB, and visualizes it via Grafana dashboards.

## System Components

1.  **Docker Backend (on VPS/Server):**
    * **InfluxDB 2.x**: Time-Series database.
    * **Grafana**: Data visualization.
    * **Python/Flask API**: Receives ESP32 data, writes to InfluxDB.

2.  **ESP32 Firmware (physical device):**
    * ESPHome-based firmware connects to the inverter and sends data to the API.

## Prerequisites

* **Server/VPS**: With Docker, Docker Compose Plugin, and Git installed.
* **NGINX Proxy Manager (NPM)**: Installed and configured on your server for subdomain/SSL management.
* **ESPHome CLI**: On your local machine.
* **Inverter**: Aurora/Power-One compatible.
* **Hardware**: ESP32 board with RS485 adapter.

## Communication Protocol

The Aurora Communication Protocol (version 4.2), used for communication with the inverter, is detailed in this document:
[https://www.drhack.it/images/PDF/AuroraCommunicationProtocol_4_2.pdf](https://www.drhack.it/images/PDF/AuroraCommunicationProtocol_4_2.pdf)

The protocol implementation in the ESP32 firmware leverages the `jrbenito/ABBAurora` library:
[https://github.com/jrbenito/ABBAurora](https://github.com/jrbenito/ABBAurora)

## Docker Backend Setup (on Server)

1.  **Clone the Repository:**
    ```bash
    cd ~/projects/ # Or your preferred directory
    git clone [https://github.com/mattiamelodia/Aurora-Inverter-Monitoring-System.git](https://github.com/mattiamelodia/Aurora-Inverter-Monitoring-System.git)
    cd Aurora-Inverter-Monitoring-System/server-inverter-monitoring/
    ```
    *(Note: The backend is located directly in `server-inverter-monitoring/`.)*

2.  **Configure `.env` File:**
    This file stores InfluxDB and Grafana credentials. **It must not be committed to Git.**
    Create/edit `.env` in `server-inverter-monitoring/`:
    ```bash
    nano .env
    ```
    Paste and **replace placeholder values with your own**:
    ```
    INFLUXDB_INIT_MODE=setup
    INFLUXDB_INIT_USERNAME=your_influxdb_user
    INFLUXDB_INIT_PASSWORD=your_influxdb_password
    INFLUXDB_INIT_ORG=your_influxdb_org
    INFLUXDB_INIT_BUCKET=your_influxdb_bucket
    INFLUXDB_INIT_ADMIN_TOKEN=your_influxdb_admin_token

    GRAFANA_USER=your_grafana_user
    GRAFANA_PASSWORD=your_grafana_password

    INFLUXDB_URL=http://influxdb:8086
    INFLUXDB_TOKEN=${INFLUXDB_INIT_ADMIN_TOKEN}
    INFLUXDB_ORG=${INFLUXDB_INIT_ORG}
    INFLUXDB_BUCKET=${INFLUXDB_INIT_BUCKET}
    ```
    Save and exit.

3.  **Start Docker Services:**
    From `server-inverter-monitoring/`:
    ```bash
    make inverter-monitoring
    ```

4.  **Verify Services:**
    ```bash
    docker ps
    ```
    Confirm `influxdb`, `grafana`, and `api-inverter` are `Up`.

## Grafana Configuration

1.  **Access Grafana UI:**
    `http://<YOUR_SERVER_IP>:3000` (or your configured NGINX Proxy Manager domain). Log in with your Grafana credentials from `.env`.
2.  **Import Dashboards:**
    Go to "Dashboards" -> "New Dashboard" -> "Import". Upload your `dashboard.json` and select the appropriate InfluxDB data source.

## NGINX Proxy Manager Configuration

Configure the following Proxy Hosts in NGINX Proxy Manager (`http://<YOUR_SERVER_IP>:81`):

* **Grafana:**
    * Domain: `grafana.yourdomain.com`
    * Forward Hostname / IP: `grafana`
    * Forward Port: `3000`
    * Enable SSL.
* **Inverter API:**
    * Domain: `api.yourdomain.com`
    * Forward Hostname / IP: `api-inverter`
    * Forward Port: `5000`
    * Enable SSL if desired.

## ESP32 Firmware Setup

This section covers ESP32 firmware configuration and upload.

1.  **Configure `config.yaml` and `secrets.yaml`:**
    The `config.yaml` file in `esp32/esphome-aurora-inverter/` uses ESPHome's `secrets` mechanism for sensitive data (like Wi-Fi credentials and the API endpoint URL).

    **`config.yaml` example (within `esp32/esphome-aurora-inverter/`):**
    This configuration sends inverter data to your API every 60 seconds, but only if the `power_in_total` is greater than zero (i.e., when the inverter is actively producing power).

    ```yaml
    # ... other configurations ...
    wifi:
      ssid: "${wifi_ssid}"
      password: "${wifi_password}"
      # ...

    interval:
      - interval: 60s
        then:
          - if:
              condition:
                lambda: return id(power_in_total).state > 0;
              then:
                - http_request.send:
                    method: POST
                    url: "${inverter_api_url}/api/inverter_data" # Uses secret for base URL
                    request_headers:
                      Content-Type: application/json
                    json: !lambda |-
                      root["power_in_total"] = id(power_in_total).state;
                      root["power_peak_today"] = id(power_peak_today).state;
                      root["power_peak_max"] = id(power_peak_max).state;
                      root["inverter_temp"] = id(inverter_temp).state;
                      root["cumulated_energy_today"] = id(cumulated_energy_today).state;
                      root["cumulated_energy_week"] = id(cumulated_energy_week).state;
                      root["cumulated_energy_month"] = id(cumulated_energy_month).state;
                      root["cumulated_energy_year"] = id(cumulated_energy_year).state;
                      root["cumulated_energy_total"] = id(cumulated_energy_total).state;
                      root["grid_voltage"] = id(grid_voltage).state;
                      root["connection_status"] = id(connection_status).state;
    # ... other configurations ...
    ```

    **You MUST create a `secrets.yaml` file** in the same directory (`esp32/esphome-aurora-inverter/`) with your actual credentials and API base URL:
    ```yaml
    wifi_ssid: "Your_WiFi_SSID"
    wifi_password: "Your_WiFi_Password"
    inverter_api_url: "[https://api.yourdomain.com](https://api.yourdomain.com)"
    ```
    This `secrets.yaml` file is handled by `.gitignore` and is not part of the Git repository.

2.  **Compile and Upload:**
    From your local machine, navigate to the ESPHome project directory:
    ```bash
    cd /path/to/your/Aurora-Inverter-Monitoring-System/esp32/esphome-aurora-inverter/
    esphome run config.yaml
    ```
    Follow ESPHome's prompts to connect your ESP32 and upload the firmware.

---

## Credits and Attribution

The ESP32 firmware configuration (`esp32/esphome-aurora-inverter/`) in this project is based on the work by **Michel Sciortino**. The original repository can be found here:

[https://github.com/michelsciortino/esphome-aurora-inverter](https://github.com/michelsciortino/esphome-aurora-inverter)

This project extends and customizes that base for integration with a Dockerized backend.