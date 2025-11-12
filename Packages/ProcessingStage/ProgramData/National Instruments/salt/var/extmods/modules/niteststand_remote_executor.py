from __future__ import absolute_import

import logging
from pathlib import Path
import json
import requests

__virtualname__ = 'niteststand_remote_executor'

log = logging.getLogger(__name__)

executor_path = (
    r"C:\Program Files\National Instruments\TestStand Executor\NationalInstruments.TestStandExecutor.exe"
)

config_path = Path(r"C:\ProgramData\National Instruments\Skyline\HttpConfigurations\http_master.json")

# Globals populated at import; guarded for safety
base_uri = None
api_key = None


def __virtual__():
    return __virtualname__


def _load_config():
    global base_uri, api_key
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        base_uri = (cfg.get("Uri") or "").rstrip("/")
        api_key = cfg.get("ApiKey")
        if not base_uri or not api_key:
            log.warning("SystemLink config loaded but Uri/ApiKey missing: %s", cfg)
    except FileNotFoundError:
        log.error("SystemLink config not found at %s", config_path)
    except Exception as e:
        log.exception("Failed to load SystemLink config: %s", e)


_load_config()


def _executor_installed():
    return Path(executor_path).exists()


def _get_webservice_user(**kwargs):
    try:
        meta = kwargs.get('__pub_metadata') or {}
        user = meta.get("user_login")
        log.debug('Test executor user: %s', user)
        return user
    except Exception as e:
        log.debug("Unable to read webservice user from kwargs: %s", e)
        return None


def execute(sequence_file, local_properties, **kwargs):
    if not _executor_installed():
        return {"retcode": 1, "stderr": "Executor not installed", "stdout": ""}

    if not base_uri or not api_key:
        return {"retcode": 1, "stderr": "SystemLink config is missing Uri/ApiKey", "stdout": ""}

    test_plan_id = None
    args = [executor_path, "execute", sequence_file, "-v"]

    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        args += ["-u", webservice_user]

    for p in local_properties:
        args.append(p)
        if isinstance(p, str) and p.startswith("TestPlanId="):
            test_plan_id = p.split("=", 1)[1]

    serial = get_dut_serial_number(test_plan_id) if test_plan_id else None
    if serial:
        args.append("SerialNumber={0}".format(serial))
    else:
        log.warning("Serial number could not be resolved (test_plan_id=%s). Proceeding without SerialNumber.", test_plan_id)

    log.debug('Test executor cmd argv: %s', args)
    return __salt__['cmd.run_all'](args, python_shell=False)


def can_execute(sequence_file, **kwargs):
    ret = {'can_execute': True}

    if not _executor_installed():
        ret['can_execute'] = False
        return ret

    args = [executor_path, "find", sequence_file, "-v"]
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        args += ["-u", webservice_user]

    find_cmd_ret = __salt__['cmd.run_all'](args, python_shell=False)
    if find_cmd_ret.get('retcode', 1) != 0:
        ret['can_execute'] = False
    return ret


def list_sequences(pattern=None, **kwargs):
    args = [executor_path, "list"]
    if pattern:
        args.append(pattern)
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        args += ["-u", webservice_user]

    result = __salt__['cmd.run_all'](args, python_shell=False)
    stdout = result.get('stdout', '')
    return stdout.replace('\r', '').split('\n') if stdout else []


def get_dut_serial_number(testplan_id):
    if not testplan_id:
        log.warning("get_dut_serial_number called without testplan_id")
        return None

    dut_id = get_dut_id(testplan_id)
    if not dut_id:
        return None

    if not base_uri or not api_key:
        log.error("SystemLink config missing; cannot query asset")
        return None

    url = "{0}/niapm/v1/assets/{1}".format(base_uri, dut_id)
    headers = {"x-ni-api-key": api_key, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        serial_number = data.get("serialNumber")
        log.debug("Serial Number: %s", serial_number)
        return serial_number
    except requests.exceptions.HTTPError:
        log.error("Asset request failed (%s): %s", response.status_code, response.text)
    except Exception as e:
        log.exception("Unexpected error retrieving serial number: %s", e)

    return None


def get_dut_id(testplan_id):
    if not base_uri or not api_key:
        log.error("SystemLink config missing; cannot query testplan")
        return None

    url = "{0}/niworkorder/v1/testplans/{1}".format(base_uri, testplan_id)
    headers = {"x-ni-api-key": api_key, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        dut_id = data.get("dutId")
        log.debug("DUT ID: %s (TestPlanId=%s)", dut_id, testplan_id)
        return dut_id
    except requests.exceptions.HTTPError:
        log.error("Testplan request failed (%s): %s", response.status_code, response.text)
    except Exception as e:
        log.exception("Unexpected error retrieving DUT ID: %s", e)

    return None