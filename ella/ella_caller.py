import os
import re
import shutil
import subprocess
import socket
import logging
import json
import time


class EllaCaller:
    def __init__(self, ori_app_path: str):

        app_name = ori_app_path.split("/")[-1]

        copy_dir = "../ella/ella-out/res/" + app_name.replace(".apk", "")
        self.out_apk = ori_app_path
        self.stop_server()
        self.covids_path = ori_app_path.replace(".apk", "").replace("/apps/", "/covids/")
        if not os.path.exists(self.covids_path):
            print("not find!" + self.covids_path)
        self.coverage_path = ori_app_path.replace(".apk", "").replace("/apps/", "/data/") + "/my_coverage.txt"
        f = open(self.coverage_path, "w")
        f.close()
        self.server = MyEllaServer(self.coverage_path, self.covids_path)

    def get_coverage_path(self):
        return self.coverage_path

    def get_coverage(self):
        self.server.get_cov()

    def stop_server(self):
        # ubuntu
        try:
            port_query = subprocess.check_output("lsof -i:23745 | grep LISTEN", shell=True)
            if len(port_query) > 20:
                port_query_str = re.sub(r"\s+", " ", str(port_query, 'utf-8'))
                pid = port_query_str.split(" ")[1]
                kill_cmd = "kill " + pid
                os.system(kill_cmd)
            else:
                print("not process listen 23745")
        except Exception as e:
            print(e)

    def close_connection(self):
        if self.server.conn != None:
            self.server.conn.close()
            self.server.conn = None

class MyEllaServer:
    def __init__(self, coverage_path: str, covids_path, port=23745):
        self.coverage_path = coverage_path
        cov_cont = open(covids_path, "r").read()
        if len(cov_cont.strip()) == 0:
            self.covids_path = None
        else:
            self.covids_path = covids_path
        self.m_socket = socket.socket()
        self.m_socket.bind(("0.0.0.0", port))
        self.m_socket.listen(3)
        self.conn = None
        self.addr = None
        logging.info("my ella server begin!")

    def get_cov(self):
        if self.covids_path is None:
            return
        try:
            if self.conn == None and os.path.exists(self.covids_path):
                print("waiting for accept")
                self.conn, self.addr = self.m_socket.accept()
            total_data = b''
            while True:
                data = self.conn.recv(1024)
                total_data += data
                if len(data) < 1024:
                    break
            data_str = str(total_data, encoding="utf-8").strip()
            if data_str.count('{"id":"') > 1:
                data_str = '{"id":"' + data_str.split('{"id":"')[-1].strip()
            data_json = json.loads(data_str)
            cov = data_json["cov"]
            logging.info("current coverage len:" + str(len(cov.split("\n"))))
            f = open(self.coverage_path, "w")
            f.write(cov)
            f.close()
        except Exception as e:
            print(e)

if __name__ == '__main__':
    ori_app_path = "../Data/ReCDroid/apps/1.newsblur_s.apk"
    a = EllaCaller(ori_app_path)