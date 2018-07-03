from __future__ import absolute_import

import logging

import salt.utils
import salt.ext.six as six

__virtualname__ = 'niteststand_remote_executor'

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def execute(sequence_file, local_properties, **kwargs):
    executor_path = "C:\\Program Files\\" \
                            "National Instruments\\TestStand Executor\\" \
                            "NationalInstruments.TestStandExecutor.exe"
    webservice_user = None
    for key, value in kwargs.items():
        if key == '__pub_metadata':
            webservice_user = value['ws_user']
    arg = '{0} "{1}" -v'.format(executor_path, sequence_file)
    if webservice_user:
        arg = '{0} -u {1}'.format(arg, webservice_user)
    for property in local_properties:
        arg = '{0} {1}'.format(arg, property)
    return __salt__['cmd.run_all'](arg, python_shell=False)
