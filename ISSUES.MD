# Summary of initial testing

All loads well (Sensor Types etc into Home Assistant) Correct Pump Model & Pump Serial are populated. .

## Sensors

19 Sensors have been created.
all are shown as "Unknown" with no statistics found

Entity                            Entity ID
Last glucose level mmol           sensor.last_glucose_level_mmol
Last glucose level mg/dl          sensor.last_glucose_level_mg_dl
Last glucose update               sensor.last_glucose_update
Last glucose delta                sensor.last_glucose_delta
Last update                       sensor.last_update
Active insulin (IOB)              sensor.active_insulin_iob
Basal rate                        sensor.basal_rate
Last bolus                        sensor.last_bolus
Last bolus time                   sensor.last_bolus_time
Last meal bolus                   sensor.last_meal_bolus
Last pump upload                  sensor.last_pump_upload
Average glucose level mmol        sensor.average_glucose_level_mmol
Average glucose level mg/dl       sensor.average_glucose_level_mg_dl
Time in range                     sensor.time_in_range
CGM usage                         sensor.cgm_usage
Control-IQ status                 sensor.control_iq_status
Software version                  sensor.software_version
Pump serial number                sensor.pump_serial_number
Pump model                        sensor.pump_model

# System Log contains the follwing error for investigation.

Logger: homeassistant.util.loop
Source: util/loop.py:137
First occurred: 11:39:45 (1 occurrence)
Last logged: 11:39:45

Detected blocking call to load_verify_locations with args (<ssl.SSLContext object at 0x7f37aa5119f0>, '/usr/local/lib/python3.13/site-packages/certifi/cacert.pem', None, None) inside the event loop by custom integration 'carelink' at custom_components/carelink/tandem_api.py, line 96: self._client = httpx.AsyncClient( (offender: /usr/local/lib/python3.13/ssl.py, line 717: context.load_verify_locations(cafile, capath, cadata)), please create a bug report at https://github.com/yo-han/Home-Assistant-Carelink/issues For developers, please see https://developers.home-assistant.io/docs/asyncio_blocking_operations/#load_verify_locations Traceback (most recent call last): File "<frozen runpy>", line 198, in _run_module_as_main File "<frozen runpy>", line 88, in _run_code File "/usr/src/homeassistant/homeassistant/__main__.py", line 229, in <module> sys.exit(main()) File "/usr/src/homeassistant/homeassistant/__main__.py", line 215, in main exit_code = runner.run(runtime_conf) File "/usr/src/homeassistant/homeassistant/runner.py", line 289, in run return loop.run_until_complete(setup_and_run_hass(runtime_config)) File "/usr/local/lib/python3.13/asyncio/base_events.py", line 712, in run_until_complete self.run_forever() File "/usr/local/lib/python3.13/asyncio/base_events.py", line 683, in run_forever self._run_once() File "/usr/local/lib/python3.13/asyncio/base_events.py", line 2050, in _run_once handle._run() File "/usr/local/lib/python3.13/asyncio/events.py", line 89, in _run self._context.run(self._callback, *self._args) File "/usr/local/lib/python3.13/site-packages/aiohttp/web_protocol.py", line 598, in start task = asyncio.Task(coro, loop=loop, eager_start=True) File "/usr/local/lib/python3.13/site-packages/aiohttp/web_protocol.py", line 510, in _handle_request resp = await request_handler(request) File "/usr/local/lib/python3.13/site-packages/aiohttp/web_app.py", line 569, in _handle return await handler(request) File "/usr/local/lib/python3.13/site-packages/aiohttp/web_middlewares.py", line 117, in impl return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/security_filter.py", line 92, in security_filter_middleware return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/forwarded.py", line 87, in forwarded_middleware return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/request_context.py", line 26, in request_context_middleware return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/ban.py", line 86, in ban_middleware return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/auth.py", line 242, in auth_middleware return await handler(request) File "/usr/src/homeassistant/homeassistant/components/http/headers.py", line 41, in headers_middleware response = await handler(request) File "/usr/src/homeassistant/homeassistant/helpers/http.py", line 73, in handle result = await handler(request, **request.match_info) File "/usr/src/homeassistant/homeassistant/components/http/decorators.py", line 83, in with_admin return await func(self, request, *args, **kwargs) File "/usr/src/homeassistant/homeassistant/components/config/config_entries.py", line 234, in post return await super().post(request, flow_id) File "/usr/src/homeassistant/homeassistant/components/http/data_validator.py", line 74, in wrapper return await method(view, request, data, *args, **kwargs) File "/usr/src/homeassistant/homeassistant/helpers/data_entry_flow.py", line 121, in post result = await self._flow_mgr.async_configure(flow_id, data) File "/usr/src/homeassistant/homeassistant/data_entry_flow.py", line 336, in async_configure result = await self._async_configure(flow_id, user_input) File "/usr/src/homeassistant/homeassistant/data_entry_flow.py", line 383, in _async_configure result = await self._async_handle_step( File "/usr/src/homeassistant/homeassistant/data_entry_flow.py", line 483, in _async_handle_step result: _FlowResultT = await getattr(flow, method)(user_input) File "/config/custom_components/carelink/config_flow.py", line 235, in async_step_tandem info = await validate_tandem_input(self.hass, user_input) File "/config/custom_components/carelink/config_flow.py", line 66, in validate_tandem_input if not await client.login(): File "/config/custom_components/carelink/tandem_api.py", line 129, in login client = self._get_client() File "/config/custom_components/carelink/tandem_api.py", line 96, in _get_client self._client = httpx.AsyncClient(
