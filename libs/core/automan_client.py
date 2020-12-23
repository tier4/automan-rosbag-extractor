import json
import time
import requests
MAX_RETRY_COUNT = 3


class AutomanClient():

    @staticmethod
    def send_result(automan_info, data, path=None):
        host = automan_info['host']
        if path is None:
            path = automan_info['path']
        automan_url = host + path
        print(automan_url)
        headers = {
            'Authorization': 'JWT ' + automan_info['jwt'],
            'Content-Type': 'application/json'
        }

        err_count = 0
        while err_count < MAX_RETRY_COUNT:
            try:
                res = requests.post(automan_url, data=json.dumps(data), headers=headers)
                return res
            except Exception as e:
                print(e)
                print("Try to resending complete signal to front server")
                time.sleep(1)
                err_count += 1

        raise Exception  # FIXME

    @staticmethod
    def send_get(automan_info, path=None, params=None):
        host = automan_info['host']
        if path is None:
            path = automan_info['path']
        automan_url = host + path
        headers = {
            'Authorization': 'JWT ' + automan_info['jwt'],
        }

        err_count = 0
        while err_count < MAX_RETRY_COUNT:
            try:
                res = requests.get(automan_url, headers=headers, params=params)
                return res
            except Exception as e:
                print(e)
                print("Try to resending complete signal to front server")
                time.sleep(1)
                err_count += 1

        raise Exception  # FIXME
