import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.persistent_notification import async_create
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DEFAULT_SCAN_INTERVAL,
    CONF_HIDS,
    MODEL_MOISTURE_SIMPLE,
    MODEL_MOISTURE_FULL,
    MODEL_RAIN,
    MODEL_TEMPHUM,
    MODEL_FLOWMETER,
    MODEL_CO2,
    MODEL_POOL,
    MODEL_POOL_PLUS,
    MODEL_DISPLAY_HUB,
    MODEL_VALVE_HUB,
)
from .homgar_api import (
    HomGarClient, HomGarApiError,
    decode_moisture_simple, decode_moisture_full, decode_rain,
    decode_temphum, decode_flowmeter, decode_co2, decode_pool, decode_pool_plus,
    decode_valve_hub,
)

_LOGGER = logging.getLogger(__name__)


class HomGarCoordinator(DataUpdateCoordinator):
    """Coordinator for HomGar polling."""

    def __init__(self, hass: HomeAssistant, client: HomGarClient, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="HomGar coordinator",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._client = client
        self._entry = entry
        self._hids = entry.data.get(CONF_HIDS, [])
        self._notified_unknown_models: set[str] = set()

    async def _async_update_data(self):
        """Fetch and decode data from HomGar."""
        try:
            homes = self._hids
            hubs: list[dict] = []
            for hid in homes:
                devices = await self._client.get_devices_by_hid(hid)
                for hub in devices:
                    hub_copy = dict(hub)
                    hub_copy["hid"] = hid
                    hubs.append(hub_copy)

            status_by_mid: dict[int, dict] = {}
            decoded_sensors: dict[str, dict] = {}

            # Build the device list for the batch status call from hubs that have
            # deviceName and productKey available (i.e. the valve hub and others
            # that expose these fields).  Fall back to per-hub getDeviceStatus for
            # any hub that does not have them.
            batch_devices = [
                {"deviceName": h["deviceName"], "mid": str(h["mid"]), "productKey": h["productKey"]}
                for h in hubs
                if h.get("deviceName") and h.get("productKey")
            ]
            fallback_mids = {
                h["mid"] for h in hubs
                if not (h.get("deviceName") and h.get("productKey"))
            }

            if batch_devices:
                batch_results = await self._client.get_multiple_device_status(batch_devices)
                # multipleDeviceStatus returns a list; index by mid for lookup below
                for result in batch_results:
                    result_mid = int(result.get("mid", 0))
                    status_by_mid[result_mid] = result
                _LOGGER.debug("Batch status fetched for %d devices", len(batch_devices))

            for mid in fallback_mids:
                status = await self._client.get_device_status(mid)
                status_by_mid[mid] = status
                _LOGGER.debug("Fallback status fetched for mid=%s", mid)

            for hub in hubs:
                mid = hub["mid"]
                status = status_by_mid.get(mid, {})

                _LOGGER.debug("Processing status for mid=%s: %s", mid, status)

                # multipleDeviceStatus returns a 'status' list; getDeviceStatus returns
                # 'subDeviceStatus'. Support both so the fallback path still works.
                raw_status_list = (
                    status.get("subDeviceStatus")
                    or status.get("status")
                    or []
                )
                sub_status = {s["id"]: s for s in raw_status_list if s.get("id")}

                # Map addr -> subDevice
                addr_map = {sd["addr"]: sd for sd in hub.get("subDevices", [])}

                for sid, s in sub_status.items():
                    if not sid.startswith("D"):
                        continue
                    addr_str = sid[1:]
                    try:
                        addr = int(addr_str)
                    except ValueError:
                        continue

                    sub = addr_map.get(addr)
                    if not sub:
                        continue

                    raw_value = s.get("value")
                    if not raw_value:
                        # No reading / offline
                        decoded = None
                        _LOGGER.debug("No raw_value for mid=%s addr=%s (sid=%s)", mid, addr, sid)
                    else:
                        model = sub.get("model")
                        try:
                            _LOGGER.debug("Decoding payload for model=%s mid=%s addr=%s: %s", model, mid, addr, raw_value)
                            if model == MODEL_MOISTURE_SIMPLE:
                                decoded = decode_moisture_simple(raw_value)
                            elif model == MODEL_MOISTURE_FULL:
                                decoded = decode_moisture_full(raw_value)
                            elif model == MODEL_RAIN:
                                decoded = decode_rain(raw_value)
                            elif model == MODEL_TEMPHUM:
                                decoded = decode_temphum(raw_value)
                            elif model == MODEL_FLOWMETER:
                                decoded = decode_flowmeter(raw_value)
                            elif model == MODEL_CO2:
                                decoded = decode_co2(raw_value)
                            elif model == MODEL_POOL:
                                decoded = decode_pool(raw_value)
                            elif model == MODEL_POOL_PLUS:
                                decoded = decode_pool_plus(raw_value)
                            elif model == MODEL_DISPLAY_HUB:
                                from .homgar_api import decode_hws019wrf_v2
                                decoded = decode_hws019wrf_v2(raw_value)
                            elif model == MODEL_VALVE_HUB:
                                decoded = decode_valve_hub(raw_value)
                            else:
                                # Store raw data for unknown models so users can report it
                                decoded = {
                                    "type": "unknown",
                                    "model": model,
                                    "raw_value": raw_value,
                                }
                                _LOGGER.warning(
                                    "="*60 + "\n"
                                    "UNSUPPORTED SENSOR MODEL DETECTED\n"
                                    "Please report this to: https://github.com/brettmeyerowitz/homeassistant-homgar/issues\n"
                                    "Include the following information:\n"
                                    "  Model: %s\n"
                                    "  Device ID (mid): %s\n"
                                    "  Address: %s\n"
                                    "  Raw Payload: %s\n"
                                    + "="*60,
                                    model, mid, addr, raw_value
                                )
                                # Send persistent notification (once per model)
                                if model and model not in self._notified_unknown_models:
                                    self._notified_unknown_models.add(model)
                                    async_create(
                                        self.hass,
                                        f"HomGar detected an unsupported sensor model: **{model}**\n\n"
                                        f"To help add support for this sensor, please open an issue at:\n"
                                        f"https://github.com/brettmeyerowitz/homeassistant-homgar/issues\n\n"
                                        f"Include the following raw payload data:\n"
                                        f"```\n{raw_value}\n```\n\n"
                                        f"You can also find this data in the sensor's attributes in Home Assistant.",
                                        title="HomGar: Unsupported Sensor Detected",
                                        notification_id=f"homgar_unsupported_{model}",
                                    )
                            _LOGGER.debug("Decoded data for mid=%s addr=%s: %s", mid, addr, decoded)
                        except Exception as ex:  # noqa: BLE001
                            _LOGGER.warning(
                                "Failed to decode payload for %s addr=%s: %s",
                                model,
                                addr,
                                ex,
                            )
                            decoded = None

                    sensor_key = f"{hub['hid']}_{mid}_{addr}"
                    decoded_sensors[sensor_key] = {
                        "hid": hub["hid"],
                        "mid": mid,
                        "addr": addr,
                        "home_name": hub.get("homeName"),  # may not be present
                        "hub_name": hub.get("name", "Hub"),
                        "sub_name": sub.get("name"),
                        "model": sub.get("model"),
                        "raw_status": s,
                        "data": decoded,
                        "device_name": hub.get("deviceName"),
                        "product_key": hub.get("productKey"),
                    }

                    _LOGGER.debug("Sensor entity key=%s info=%s", sensor_key, decoded_sensors[sensor_key])

            return {
                "hubs": hubs,
                "status": status_by_mid,
                "sensors": decoded_sensors,
            }
        except HomGarApiError as err:
            raise UpdateFailed(f"HomGar API error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected HomGar error: {err}") from err