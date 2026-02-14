# Tandem t:slim Pump Integration for Home Assistant

> **Tested with Tandem t:slim X2.** Medtronic Carelink support is inherited from the [original integration](https://github.com/yo-han/Home-Assistant-Carelink) by @yo-han but has not been tested under this fork. For verified Medtronic support, please refer to the original repo.

## Documentation

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [Contributing Guidelines](CONTRIBUTING.md) - How to contribute to this project
- [Changelog](CHANGELOG.md) - Version history and release notes

---

## Prerequisites

1. **A Tandem t:slim pump** syncing data to [Tandem Source](https://source.eu.tandemdiabetes.com) (EU) or [source.tandemdiabetes.com](https://source.tandemdiabetes.com) (US)
2. **Home Assistant** (2023.x or later)
3. **Tandem Source account credentials** (email + password)

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** > **3-dot menu** > **Custom repositories**
3. Add repository URL: `https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink`
4. Category: **Integration**
5. Click **Add**, then find "Carelink" and click **Download**
6. Restart Home Assistant

### Method 2: Manual

1. Copy the `custom_components/carelink/` folder into your Home Assistant `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── carelink/
           ├── __init__.py
           ├── api.py
           ├── tandem_api.py
           ├── config_flow.py
           ├── const.py
           ├── sensor.py
           ├── binary_sensor.py
           ├── nightscout_uploader.py
           ├── manifest.json
           ├── strings.json
           └── translations/
               └── en.json
   ```
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **"Carelink"**
3. Select **Tandem t:slim** as the platform
4. Fill in:
   - **Email**: Your Tandem Source account email
   - **Password**: Your Tandem Source account password
   - **Region**: `EU` or `US` (depending on your Tandem Source URL)
   - **Scan interval**: Polling frequency in seconds (default: 300, range: 60–900)
   - Leave Nightscout fields blank (see below if you want Nightscout later)
5. Click **Submit**

## Sensors Created

Once configured, the integration creates these sensors:

| Sensor | Description |
|--------|-------------|
| Last SG (mmol/L) | Latest glucose reading in mmol/L |
| Last SG (mg/dL) | Latest glucose reading in mg/dL |
| SG Delta (mg/dL) | Change since previous reading |
| Active Insulin (IOB) | Insulin on board |
| Basal Rate | Current basal rate (U/hr) |
| Last Bolus Amount | Most recent bolus (units) |
| Last Bolus Time | Timestamp of most recent bolus |
| Last Bolus Type | Normal, Extended, or Automatic |
| Last Meal Bolus | Most recent meal bolus (units) |
| Last Meal Time | Timestamp of most recent meal bolus |
| Control-IQ Status | Current Control-IQ mode |
| Pump Battery | Battery level |
| Reservoir Level | Insulin remaining (units) |
| Pump Serial Number | Device serial |
| Average Reading | Average glucose (from dashboard) |
| Time in Range (%) | Percentage of time in target range |
| CGM Inactive (%) | Percentage of time CGM was inactive |
| Pump Model | Pump model name |
| Last Update | Timestamp of last data sync |

---

## Optional: Nightscout Setup

Nightscout provides a web dashboard for glucose data visualization and remote monitoring. If you want this, here are two options:

### Option A: Docker Compose (Standalone)

1. Create a directory for Nightscout:
   ```bash
   mkdir -p ~/nightscout && cd ~/nightscout
   ```

2. Create `docker-compose.yml`:
   ```yaml
   version: '3.8'

   services:
     mongo:
       image: mongo:4.4
       container_name: nightscout-mongo
       volumes:
         - mongo-data:/data/db
       restart: unless-stopped

     nightscout:
       image: nightscout/cgm-remote-monitor:latest
       container_name: nightscout
       depends_on:
         - mongo
       ports:
         - "1337:1337"
       environment:
         NODE_ENV: production
         TZ: Europe/Amsterdam          # <-- your timezone
         MONGO_CONNECTION: mongodb://mongo:27017/nightscout
         API_SECRET: your-api-secret-min-12-chars   # <-- change this!
         DISPLAY_UNITS: mmol                         # or "mg/dl"
         ENABLE: careportal basal iob cob cage sage pump openaps
         AUTH_DEFAULT_ROLES: readable
         BASE_URL: http://your-ha-ip:1337            # <-- your HA server IP
       restart: unless-stopped

   volumes:
     mongo-data:
   ```

3. Start it:
   ```bash
   docker compose up -d
   ```

4. Verify at `http://your-ha-ip:1337`

### Option B: Portainer

1. Open **Portainer** > **Stacks** > **Add stack**
2. Name: `nightscout`
3. Paste the same `docker-compose.yml` content from Option A above into the **Web editor**
4. Update the environment values (timezone, API_SECRET, BASE_URL)
5. Click **Deploy the stack**
6. Verify at `http://your-ha-ip:1337`

### Connecting Nightscout to the Integration

Once Nightscout is running, reconfigure the integration:

1. Go to **Settings** > **Devices & Services** > **Carelink** > **Configure**
2. Enter:
   - **Nightscout URL**: `http://your-ha-ip:1337` (or use the Docker hostname if HA runs in Docker too, e.g., `http://nightscout:1337`)
   - **Nightscout API Secret**: The `API_SECRET` value from your Docker config
3. Click **Submit**

The integration will then upload glucose data to Nightscout on each poll cycle.

### Important Notes for Nightscout

- `API_SECRET` must be at least 12 characters
- If Home Assistant and Nightscout run on the same Docker network, use the container name (`http://nightscout:1337`) as the URL
- For external access, set up a reverse proxy (e.g., Nginx Proxy Manager, Caddy, or Traefik) with HTTPS
- Default Nightscout port is `1337` — change the left side of the port mapping if needed (e.g., `8080:1337`)
