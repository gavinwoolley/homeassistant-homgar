# HomGar Cloud integration for Home Assistant

Unofficial Home Assistant component for HomGar Cloud, supporting RF soil moisture, rain, and irrigation valve control via the HomGar cloud API.

---

## Compatibility

Tested with:

- Hub: `HWG023WBRF-V2`
- Soil moisture probes:
  - `HCS026FRF` (moisture-only)
  - `HCS021FRF` (moisture + temperature + lux)
- Rain gauge:
  - `HCS012ARF`
- Temperature/Humidity:
  - `HCS014ARF`
- Flowmeter:
  - `HCS008FRF`
- CO2/Temperature/Humidity:
  - `HCS0530THO`
- Pool/Temperature:
  - `HCS0528ARF`
- Pool + Ambient temp/humidity:
  - `HCS015ARF+`
- Irrigation valve hub:
  - `HTV0540FRF` (multi-zone; zone count detected automatically from device payload)

The integration communicates with the same cloud endpoints as the HomGar app (`region3.homgarus.com`).

---

## Features

- Login with your HomGar account (email + area code)
- Select which homes to include
- Auto-discovers supported sub-devices
- Exposes:
  - Moisture %
  - Temperature (where applicable)
  - Illuminance (HCS021FRF)
  - Rain:
    - Last hour
    - Last 24 hours
    - Last 7 days
    - Total rainfall
  - Temperature/Humidity (HCS014ARF)
  - Flowmeter readings (HCS008FRF)
  - CO2, temperature, humidity (HCS0530THO)
  - Pool temperature (HCS0528ARF)
  - Pool + ambient temperature and humidity (HCS015ARF+)
  - **Irrigation valve control (HTV0540FRF)**:
    - One `valve` entity per zone - open/close from the HA UI or automations
    - One `number` entity per zone - configurable run duration (1-60 minutes, persisted across restarts)
    - Zone count is detected automatically from the device payload; no hardcoded assumption about 1, 2, 3 or more zones
    - Immediate state reflection after a command - no waiting for the next poll cycle
    - State attributes: `duration_seconds`, `state_raw`
- Attributes (sensors):
  - `rssi_dbm`
  - `battery_status_code`
  - `last_updated` (cloud timestamp)

---

## Irrigation valve usage

Each zone appears as two entities in Home Assistant:

| Entity type | Name example | Purpose |
| --- | --- | --- |
| `valve` | `Zone 1` | Open / close the zone |
| `number` | `Zone 1 Duration` | Default run time in minutes (1–60) |

**Opening a zone:**

Call the `valve.open_valve` service. The zone will run for the duration currently set in the companion `number` entity (default 10 minutes). You can override the duration at service-call time using the `duration` attribute (value in seconds):

```yaml
service: valve.open_valve
target:
  entity_id: valve.my_valve_hub_zone_1
data:
  duration: 300   # 5 minutes (seconds)
```

**Closing a zone:**

```yaml
service: valve.close_valve
target:
  entity_id: valve.my_valve_hub_zone_1
```

---

## Installation

### Easy Installation via HACS

You can quickly add this repository to HACS by clicking the button below:

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=brettmeyerowitz&repository=homeassistant-homgar&category=integration)

#### Manual Installation

1. Copy the `custom_components/homgar` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for **HomGar Cloud**. Enter your HomGar account credentials (email and area code) to connect.

---

## Reporting Unsupported Sensors

If you have a HomGar sensor that isn't supported yet, the integration will:

1. **Show a persistent notification** in Home Assistant with the sensor model and raw payload data
2. **Create a diagnostic entity** named `[Sensor Name] Unsupported ([Model])` with the raw payload in its attributes
3. **Log a warning** with full details to the Home Assistant logs

To help add support for your sensor:

1. Open the HomGar app on your phone and note the sensor values being displayed (e.g., temperature, humidity, battery level)
2. In Home Assistant, go to **Settings → Devices & Services → HomGar** and find the unsupported sensor entity
3. Click on the entity and copy the `raw_payload` attribute value
4. Open an issue at https://github.com/brettmeyerowitz/homeassistant-homgar/issues with:
   - Your sensor model (e.g., `HCS015ARF+`)
   - The raw payload data
   - **Screenshots or values from the HomGar app** showing what the sensor is currently reading
   - This helps us decode the payload by matching the raw bytes to actual values

---

## Credits

This integration was developed by Brett Meyerowitz. It is not affiliated with HomGar.

**Special thanks to [shaundekok/rainpoint](https://github.com/shaundekok/rainpoint) for Node-RED flow inspiration, payload decoding, and entity mapping logic.**

Feedback and contributions are welcome!
