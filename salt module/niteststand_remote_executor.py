from __future__ import absolute_import

import logging
from pathlib import Path

import salt.utils
import salt.ext.six as six

__virtualname__ = 'niteststand_remote_executor'

log = logging.getLogger(__name__)

executor_path = "C:\\Program Files\\" \
                    "National Instruments\\TestStand Executor\\" \
                    "NationalInstruments.TestStandExecutor.exe"


def __virtual__():
    return __virtualname__


def _executor_installed():
    path = Path(executor_path)
    return path.exists()


def _get_webservice_user(**kwargs):
    webservice_user = None
    for key, value in kwargs.items():
        if key == '__pub_metadata':
            webservice_user = value['ws_user']
    return webservice_user


def execute(sequence_file, local_properties, **kwargs):
    webservice_user = _get_webservice_user(**kwargs)
    arg = '{0} execute "{1}" -v'.format(executor_path, sequence_file)
    if webservice_user:
        arg = '{0} -u {1}'.format(arg, webservice_user)
    for property in local_properties:
        arg = '{0} {1}'.format(arg, property)
    return __salt__['cmd.run_all'](arg, python_shell=False)


def can_execute(sequence_file, **kwargs):
    ret = {
        'can_execute': True
    }
    if not _executor_installed():
        ret['can_execute'] = False
    arg = '{0} find "{1}" -v'.format(executor_path, sequence_file)
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        arg = '{0} -u {1}'.format(arg, webservice_user)
    find_cmd_ret = __salt__['cmd.run_all'](arg, python_shell=False)
    if find_cmd_ret['retcode'] is not 0:
        ret['can_execute'] = False
    return ret


def list_sequences(pattern=None, **kwargs):
    arg = '{0} list'.format(executor_path)
    if pattern:
        arg = '{0} {1}'.format(arg, pattern)
    webservice_user = _get_webservice_user(**kwargs)
    if webservice_user:
        arg = '{0} -u {1}'.format(arg, webservice_user)
    list_cmd_ret = __salt__['cmd.run_all'](arg, python_shell=False)
    return list_cmd_ret['stdout'].replace('\r', '').split('\n')
