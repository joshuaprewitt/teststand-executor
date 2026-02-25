from __future__ import absolute_import

import json
import logging
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Module: niteststand_remote_executor
# Purpose: Salt execution module that wraps the TestStand Executor CLI and
# provides helpers to run TestStand sequences from SystemLink jobs. This
# module reads SystemLink configuration at import-time to locate the
# server `base_uri` and `api_key`, and exposes functions used by Salt jobs.

__virtualname__ = 'niteststand_remote_executor'

log = logging.getLogger(__name__)

# Path to the external TestStand Executor binary used to run sequences.
EXECUTOR_PATH = (
    r"C:\Program Files\National Instruments\TestStand Executor\NationalInstruments.TestStandExecutor.exe"
)

# Location of SystemLink http_master.json that contains the server Uri and ApiKey
CONFIG_PATH = Path(r"C:\ProgramData\National Instruments\Skyline\HttpConfigurations\http_master.json")

# Globals populated at import; guarded for safety
base_uri = None
api_key = None


def __virtual__():
    # Standard Salt module virtualname export
    return __virtualname__


def _load_config():
    global base_uri, api_key
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        base_uri = (cfg.get("Uri") or "").rstrip("/")
        api_key = cfg.get("ApiKey")
        if not base_uri or not api_key:
            log.warning("SystemLink config loaded but Uri/ApiKey missing: %s", cfg)
    except FileNotFoundError:
        log.error("SystemLink config not found at %s", CONFIG_PATH)
    except Exception as e:
        log.exception("Failed to load SystemLink config: %s", e)


_load_config()


def _executor_installed():
    # Quick check whether the TestStand Executor executable exists on disk
    return Path(EXECUTOR_PATH).exists()


def _build_headers():
    return {"x-ni-api-key": api_key, "Accept": "application/json"}


def _fetch_json(url, error_context):
    try:
        response = requests.get(url, headers=_build_headers(), timeout=10)
        response.raise_for_status()
        return response.json() or {}
    except requests.exceptions.HTTPError:
        log.error("%s (%s): %s", error_context, response.status_code, response.text)
    except Exception as e:
        log.exception("Unexpected error during %s: %s", error_context, e)

    return None


def _get_webservice_user(**kwargs):
    # When Salt is used as a web service this helper pulls the original
    # webservice username out of the published metadata (if present).
    try:
        meta = kwargs.get('__pub_metadata') or {}
        user = meta.get("user_login")
        log.debug('Test executor user: %s', user)
        return user
    except Exception as e:
        log.debug("Unable to read webservice user from kwargs: %s", e)
        return None


def _execute_interactive_task(args):
    """
    Create and execute a scheduled task in interactive mode.
    Returns result dict matching __salt__['cmd.run_all'] format.
    """
    # Build a deterministic short task name so multiple tasks don't collide
    task_name = "TestStandExecutor_Interactive_{0}".format(uuid.uuid4().hex[:8])

    # `schtasks /tr` is limited to 261 characters. Write a temp .cmd wrapper
    # to avoid length limits and preserve proper argument quoting.
    cmd_str = subprocess.list2cmdline(args)
    temp_cmd_path = None
    temp_output_path = None
    
    try:
        # Create temporary files for the command wrapper and output logging
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cmd", delete=False, encoding="utf-8") as temp_cmd:
            temp_cmd_path = temp_cmd.name
            
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as temp_out:
            temp_output_path = temp_out.name
        
        # Write the executor command with output redirection to the .cmd file
        with open(temp_cmd_path, "w", encoding="utf-8") as f:
            f.write("@echo off\r\n")
            f.write(cmd_str)
            f.write(" >> \"{0}\" 2>&1\r\n".format(temp_output_path))
            f.write("echo Exit Code: %ERRORLEVEL% >> \"{0}\" 2>&1\r\n".format(temp_output_path))

        # Create a one-shot scheduled task that will be run immediately.
        # Using Task Scheduler allows the Executor to run in an interactive
        # desktop session even when invoked from a service/minion context.
        start_dt = datetime.now() + timedelta(minutes=1)
        start_time = start_dt.strftime("%H:%M")
        start_date = start_dt.strftime("%m/%d/%Y")

        create_task_cmd = [
            'schtasks', '/create',
            '/tn', task_name,
            '/tr', 'cmd.exe /c "{0}"'.format(temp_cmd_path),
            '/sc', 'once',
            '/st', start_time,
            '/sd', start_date,
            '/ru', 'SYSTEM',
            '/it',
            '/f'
        ]
        
        log.debug('Creating scheduled task: %s', task_name)
        subprocess.run(
            create_task_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Request the task to run now (this will execute it in an interactive session)
        run_task_cmd = ['schtasks', '/run', '/tn', task_name]
        result = subprocess.run(run_task_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        log.debug('Executed scheduled task: %s', task_name)
        
        # Poll for task completion by checking if the output file contains the exit code
        output_stdout = ""
        output_stderr = ""
        timeout_seconds = 300  # 5 minute timeout
        poll_interval = 0.5    # Check every 500ms
        elapsed = 0
        
        while elapsed < timeout_seconds:
            task_stopped = False
            try:
                query_cmd = ['schtasks', '/query', '/tn', task_name, '/fo', 'list']
                query_result = subprocess.run(
                    query_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=5
                )
                status_text = (query_result.stdout or "").lower()
                if "status:" in status_text and "running" not in status_text:
                    task_stopped = True
            except Exception as e:
                log.debug("Error checking task status: %s", e)

            if temp_output_path and Path(temp_output_path).exists():
                try:
                    with open(temp_output_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # If we see the exit code marker, the task has completed
                    if "Exit Code:" in content:
                        output_stdout = content
                        log.debug('Task completed after %.1f seconds', elapsed)
                        break
                except Exception as e:
                    log.debug("Error reading output file: %s", e)

            if task_stopped:
                # Task finished but output marker not found; read what we have and exit.
                if temp_output_path and Path(temp_output_path).exists():
                    try:
                        with open(temp_output_path, "r", encoding="utf-8") as f:
                            output_stdout = f.read()
                    except Exception as e:
                        log.debug("Error reading output file: %s", e)
                log.warning('Task stopped but no exit code marker found; returning output as-is')
                break

            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            # Timeout reached
            log.warning('Task did not complete within %d seconds', timeout_seconds)
            if temp_output_path and Path(temp_output_path).exists():
                try:
                    with open(temp_output_path, "r", encoding="utf-8") as f:
                        output_stdout = f.read()
                except Exception as e:
                    log.warning("Failed to read task output: %s", e)
        
        # Clean up the scheduled task with a timeout to prevent hanging
        delete_task_cmd = ['schtasks', '/delete', '/tn', task_name, '/f']
        try:
            subprocess.run(delete_task_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
        except subprocess.TimeoutExpired:
            log.warning('Task deletion timed out for %s', task_name)
        
        # Normalize the subprocess result to the Salt `cmd.run_all` return shape
        # Use the output captured from the task's log file
        return {
            'retcode': 0 if output_stdout and 'Exit Code: 0' in output_stdout else 1,
            'stdout': output_stdout,
            'stderr': output_stderr
        }
    except subprocess.CalledProcessError as e:
        log.error("Task Scheduler error: %s", e)
        stderr = e.stderr if isinstance(e.stderr, str) else ''
        stdout = e.stdout if isinstance(e.stdout, str) else ''
        return {
            'retcode': 1,
            'stdout': stdout,
            'stderr': 'Task Scheduler execution failed: {0}'.format(stderr or str(e))
        }
    except Exception as e:
        log.exception("Unexpected error in interactive task execution: %s", e)
        return {
            'retcode': 1,
            'stdout': '',
            'stderr': str(e)
        }
    finally:
        # Cleanup without blocking - use async deletion for both files
        try:
            import threading
            
            def delete_async(path):
                try:
                    for attempt in range(10):
                        try:
                            p = Path(path)
                            if p.exists():
                                p.unlink()
                            break
                        except Exception:
                            if attempt < 9:
                                time.sleep(0.1)
                except Exception:
                    pass
            
            # Delete both temp files asynchronously in background threads
            if temp_cmd_path:
                thread = threading.Thread(target=delete_async, args=(temp_cmd_path,), daemon=True)
                thread.start()
            
            if temp_output_path:
                thread = threading.Thread(target=delete_async, args=(temp_output_path,), daemon=True)
                thread.start()
        except Exception:
            log.debug("Could not cleanup temp files asynchronously")


def execute(sequence_file, local_properties, **kwargs):
    # Validate prerequisites: executor binary and SystemLink config
    if not _executor_installed():
        return {"retcode": 1, "stderr": "Executor not installed", "stdout": ""}

    if not base_uri or not api_key:
        return {"retcode": 1, "stderr": "SystemLink config is missing Uri/ApiKey", "stdout": ""}

    test_plan_id = None
    args = [EXECUTOR_PATH, "execute", sequence_file, "-v"]

    # If this was invoked from the webservice pass the original user to the executor
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        args += ["-u", webservice_user]

    for p in local_properties:
        args.append(p)
        if isinstance(p, str) and p.startswith("TestPlanId="):
            test_plan_id = p.split("=", 1)[1]

    # Attempt to resolve DUT serial from the TestPlan if present
    serial = get_dut_serial_number(test_plan_id) if test_plan_id else None
    if serial:
        args.append("SerialNumber={0}".format(serial))
    else:
        log.warning("Serial number could not be resolved (test_plan_id=%s). Proceeding without SerialNumber.", test_plan_id)

    # Determine whether to run interactively. This can be triggered by either:
    #  - a local property passed in the Salt job: "Interactive=true"
    #  - a TestPlan property on the server: properties.Interactive == true
    is_interactive_local = any(p == "Interactive=true" or (isinstance(p, str) and p.startswith("Interactive=true")) for p in local_properties)

    # Check TestPlan metadata for properties.Interactive (remote flag)
    testplan_interactive = False
    if test_plan_id:
        try:
            testplan_interactive = get_testplan_interactive(test_plan_id)
        except Exception:
            log.exception("Failed reading testplan Interactive flag for TestPlanId=%s", test_plan_id)

    is_interactive = is_interactive_local or bool(testplan_interactive)

    # Log final command and dispatch accordingly. Interactive mode uses
    # a scheduled task so the process runs in an interactive desktop.
    log.debug('Test executor cmd argv: %s', args)
    if is_interactive:
        log.info('Running in interactive mode via Task Scheduler')
        return _execute_interactive_task(args)
    else:
        # Non-interactive: run via Salt's cmd runner (normal path)
        return __salt__['cmd.run_all'](args, python_shell=False)


def can_execute(sequence_file, **kwargs):
    ret = {'can_execute': True}

    if not _executor_installed():
        ret['can_execute'] = False
        return ret

    # Ask the TestStand Executor to find the sequence file on disk
    args = [EXECUTOR_PATH, "find", sequence_file, "-v"]
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        args += ["-u", webservice_user]

    find_cmd_ret = __salt__['cmd.run_all'](args, python_shell=False)
    if find_cmd_ret.get('retcode', 1) != 0:
        ret['can_execute'] = False
    return ret


def list_sequences(pattern=None, **kwargs):
    args = [EXECUTOR_PATH, "list"]
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
    data = _fetch_json(url, "Asset request failed")
    if not data:
        return None

    serial_number = data.get("serialNumber")
    log.debug("Serial Number: %s", serial_number)
    return serial_number

    return None


def get_dut_id(testplan_id):
    if not base_uri or not api_key:
        log.error("SystemLink config missing; cannot query testplan")
        return None

    url = "{0}/niworkorder/v1/testplans/{1}".format(base_uri, testplan_id)
    data = _fetch_json(url, "Testplan request failed")
    if not data:
        return None

    dut_id = data.get("dutId")
    log.debug("DUT ID: %s (TestPlanId=%s)", dut_id, testplan_id)
    return dut_id

    return None


def get_testplan_interactive(testplan_id):
    """
    Query the testplan and return True if it specifies Interactive=true.
    The testplan JSON may include the flag at the top-level or under a
    `properties` object. Returns boolean.
    """
    if not testplan_id:
        return False

    if not base_uri or not api_key:
        log.error("SystemLink config missing; cannot query testplan for Interactive property")
        return False

    url = "{0}/niworkorder/v1/testplans/{1}".format(base_uri, testplan_id)
    data = _fetch_json(url, "Testplan request failed")
    if not data:
        return False

    props = data.get("properties") or {}
    val = (
        props.get("Interactive")
        or props.get("interactive")
        or data.get("Interactive")
        or data.get("interactive")
    )

    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() == "true"

    return False

    return False