import os
import subprocess
import re

def do_clean():
    # os.remove("../Data/Temp/log/log_out.txt")
    # res = subprocess.Popen('ps aux | grep "adb logcat"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    # result = res.stdout.readlines()
    # for line in result:
    #     pid = str(line).split(" ")[1]
    #     print(pid)
    #     os.system("kill " + pid)
    # print("### clean process")
    try:
        port_query = subprocess.check_output('tasklist | findstr "adb logcat"', shell=True)
        if len(port_query) > 20:
            port_query_str = re.sub(r"\s+", " ", str(port_query, 'utf-8'))
            pid = port_query_str.split(" ")[1]
            kill_cmd = "kill " + pid
            os.system(kill_cmd)
        else:
            print("not process listen 23745")
    except Exception as e:
        print(e)


    # try:
    #     # 使用tasklist和findstr来查找包含"adb logcat"的进程
    #     port_query = subprocess.check_output('tasklist | findstr "adb logcat"', shell=True)
    #     port_query_str = str(port_query, 'utf-8').strip()
    #
    #     # 检查输出是否包含预期的进程信息
    #     if len(port_query_str) > 20:
    #         # 使用正则表达式匹配进程ID
    #         pid_match = re.search(r"\s(\d+)\s", port_query_str)
    #         if pid_match:
    #             pid = pid_match.group(1)
    #             # 使用taskkill命令结束进程
    #             kill_cmd = f'taskkill /F /PID {pid}'
    #             os.system(kill_cmd)
    #         else:
    #             print("Process ID not found.")
    #     else:
    #         print("No process listening on port 23745.")
    # except Exception as e:
    #     print(e)


if __name__ == '__main__':
    do_clean()