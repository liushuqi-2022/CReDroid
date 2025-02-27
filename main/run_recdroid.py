from env.emulator import EmuRunner
from env.state_info import StateInfo
from env.util import check_crash_trigger
import networkx as nx
from Semantics.scorer import SimScorer
from Semantics.get_title_action import has_repeated_action_keywords
from strategy.q_learning import QLearningExplore
import subprocess
import logging
import os
import json
from trace_process.trace_preprocess import preprocess_trace
from ella.ella_caller import EllaCaller
from trigger_check.checker import APITriggerChecker
import re
import time
from main.clean_adb import do_clean
from step_generation.gen_steps import StepGenerator

def get_app_info(app_idx, dataset_dir="../Data/ReCDroid", debug=False):
    app_dict = {}
    for app_name in os.listdir(dataset_dir + "/apps"):
        app_dict.setdefault(int(app_name.split(".")[0]), app_name)

    tgt_app = app_dict[app_idx]
    app_dir = dataset_dir + "/data/" + tgt_app.replace(".apk", "")
    if not os.path.exists(app_dir):
        os.mkdir(app_dir)

    CTG_dir = dataset_dir + "/CTG/" + tgt_app.replace(".apk", "")
    CTG_txt_path1 = CTG_dir + "/CTGResult/" + tgt_app.replace(".apk", "_CTG.txt")
    CTG_txt_path2 = CTG_dir + "/CTGResult/" + tgt_app.replace(".apk", "_CTGwithFragment.txt")
    CTG_paths = [CTG_txt_path1, CTG_txt_path2]
    # 创建一个有向图
    CTG = nx.DiGraph()
    # 读取文本文件并添加边到图中CTG_txt_path
    for file_path in CTG_paths:
        with open(file_path, 'r') as file:
            for line in file:
                # 假设每行的格式是 "node1 -> node2"
                parts = line.strip().split(' -> ')
                if len(parts) == 2:
                    CTG.add_edge(parts[0], parts[1])

    entry_json = json.load(open(dataset_dir + "/activity.txt", "r"))
    app_pkg = entry_json[tgt_app]["app_pkg"]
    # app_pkg com.ichi2.anki
    app_acti = entry_json[tgt_app]["app_acti"][0]
    all_actis = entry_json[tgt_app]["all_actis"]
    trace_path = dataset_dir + "/traces/" + tgt_app.replace(".apk", ".txt")
    trace_info = preprocess_trace(trace_path, app_pkg, all_actis, CTG_dir, CTG)
    # trace_info {'trace': '08-16 22:35:20.168  4573  4629 E ACRA    : com.ichi2.anki fatal error : file:///storage/emulated/0/Pictures/img_201808162235181848646504.jpg exposed beyond app through ClipData.Item.getUri()\n08-16 22:35:20.168  4573  4629 E ACRA    : android.os.FileUriExposedException: file:///storage/emulated/0/Pictures/img_201808162235181848646504.jpg exposed beyond app through ClipData.Item.getUri()\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.os.StrictMode.onFileUriExposed(StrictMode.java:1799)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.net.Uri.checkFileUriExposed(Uri.java:2346)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.content.ClipData.prepareToLeaveProcess(ClipData.java:832)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.content.Intent.prepareToLeaveProcess(Intent.java:8909)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.content.Intent.prepareToLeaveProcess(Intent.java:8894)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.app.Instrumentation.execStartActivity(Instrumentation.java:1517)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.app.Activity.startActivityForResult(Activity.java:4224)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.support.v4.app.BaseFragmentActivityJB.startActivityForResult(BaseFragmentActivityJB.java:50)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.support.v4.app.FragmentActivity.startActivityForResult(FragmentActivity.java:79)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.app.Activity.startActivityForResult(Activity.java:4183)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.support.v4.app.FragmentActivity.startActivityForResult(FragmentActivity.java:859)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat com.ichi2.anki.AnkiActivity.startActivityForResult(AnkiActivity.java:175)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat com.ichi2.anki.multimediacard.fields.BasicImageFieldController$2.onClick(BasicImageFieldController.java:125)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.view.View.performClick(View.java:5610)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.view.View$PerformClick.run(View.java:22265)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.os.Handler.handleCallback(Handler.java:751)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.os.Handler.dispatchMessage(Handler.java:95)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.os.Looper.loop(Looper.java:154)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat android.app.ActivityThread.main(ActivityThread.java:6077)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat java.lang.reflect.Method.invoke(Native Method)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat com.android.internal.os.ZygoteInit$MethodAndArgsCaller.run(ZygoteInit.java:866)\n08-16 22:35:20.168  4573  4629 E ACRA    : \tat com.android.internal.os.ZygoteInit.main(ZygoteInit.java:756)', 'trace_tokens': {'field', 'basicimagefieldcontroller', 'click', 'anki', 'activity', 'storage', 'pictures', 'uri', 'result', 'for', 'image', 'startactivityforresult', 'clip', 'controller', 'java', 'exposed', 'img', 'ichi', 'onclick', 'on', 'fields', 'file', 'emulated', 'error', 'basic', 'beyond', 'through', 'start', 'multimediacard', 'data', 'ankiactivity', 'jpg'}, 'trace_eles': {'class': ['com.ichi2.anki.AnkiActivity', 'com.ichi2.anki.multimediacard.fields.BasicImageFieldController$2'], 'api': {'com.ichi2.anki.multimediacard.fields.BasicImageFieldController$2.onClick', 'com.ichi2.anki.AnkiActivity.startActivityForResult'}, 'all': {'com.ichi2.anki.AnkiActivity.startActivityForResult(AnkiActivity.java', 'com.ichi2.anki.multimediacard.fields.BasicImageFieldController$2.onClick(BasicImageFieldController.java', 'com.ichi2.anki'}},
    # 'trace_actis': ['com.ichi2.anki.multimediacard.activity.MultimediaEditFieldActivity']}

    title_path = dataset_dir + "/titles/" + tgt_app.replace(".apk", ".txt")
    ori_apk_path = dataset_dir + "/apps/" + tgt_app
    ella_caller = EllaCaller(ori_apk_path)
    api_checker = APITriggerChecker(trace_info, app_pkg, ella_caller)
    # print("api_checker",vars(api_checker))

    input_path = dataset_dir + "/input/" + tgt_app.replace(".apk", ".json")
    if os.path.exists(input_path):
        input_cont = json.load(open(input_path, "r"))
    else:
        input_cont = {}

    if len(trace_info["trace_actis"]) > 0:
        dst_acti = trace_info["trace_actis"][0].split(".")[-1]
        logging.info("dst activity: case find in trace: " + dst_acti)
    elif len(trace_info["trace_eles"]["class"]) > 0:
        # trace_eles_class = list(trace_info["trace_eles"]["class"])
        # dst_acti = trace_eles_class[0].split(".")[-1].split("$")[0]
        # logging.info("dst activity: case use first class: " + dst_acti)
        trace_eles_class = list(trace_info["trace_eles"]["class"])
        print(trace_eles_class)
        if "$" in trace_eles_class[0]:
            dst_acti = trace_eles_class[0].split(".")[-1].split("$")[0]
        else:
            dst_acti1 = trace_eles_class[0].split(".")[-1][0]
            if dst_acti1.istitle():
                dst_acti = trace_eles_class[0].split(".")[-1]
            else:
                dst_acti = trace_eles_class[0].split(".")[-2]
        logging.info("dst activity: case use first class: " + dst_acti)
    else:
        dst_acti = "unknown"
        logging.info("dst activity: case unknown: " + dst_acti)
    # dst_acti = trace_info["trace_actis"][0]
    all_pages = get_activity_names(all_actis)
    with open(title_path, 'r', encoding='utf-8') as file:
        title_context = file.read()

    scorer = SimScorer(dst_acti, api_checker, all_pages, trace_info, app_pkg, CTG, title_context, CTG_dir, input_cont)
    multi_click = has_repeated_action_keywords(title_context)

    data_dir = app_dir
    action_output = data_dir + "/action_history.txt"
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    with open(action_output, 'w') as file:
        pass
    # uninstall_cmd = "adb shell pm uninstall " + app_pkg
    # os.system(uninstall_cmd)
    # install_cmd = "adb install -g " + ella_caller.out_apk
    #
    # os.system(install_cmd)

    if app_idx in [2, 5]:
        need_rotate = True
    else:
        need_rotate = False
    app_info = {"app_pkg": app_pkg, "app_acti": app_acti, "scorer": scorer, "trace_info": trace_info, "reset": True,
                "data_dir": data_dir, "all_actis": all_actis, "api_checker": api_checker, "input_cont": input_cont,
                "need_rotate": need_rotate, "ella_caller": ella_caller, "action_output": action_output, "use_page": 0,
                "multi_click": multi_click, "title_context": title_context}
    if app_idx in [3, 21, 15]:
        app_info["reset"] = False
    if debug:
        for k, v in trace_info.items():
            print(k)
            print(v)
    if app_pkg == "com.fsck.k9.debug":
        print("%%% push com.fsck.k9.debug")
        app_info["reset"] = False
        push_cmd = "adb -s emulator-5554 root | adb -s emulator-5554 remount | adb  -s emulator-5554 push ../Data/Temp/app_data/com.fsck.k9.debug/ /data/data/"
        os.system(push_cmd)
    return app_info


def do_test(app_idx):
    os.system("adb logcat -c")
    log_out = open("../Data/Temp/log/log_out.txt", "wb")
    log_err = open("../Data/Temp/log/log_err.txt", "wb")
    log_proc = subprocess.Popen("adb logcat *:E", stdout=log_out, stderr=log_err, shell=True)
    app_info = get_app_info(app_idx, dataset_dir=dataset_dir)
    # app_info = {"app_pkg": "com.rigid.birthdroid", "app_acti": "com.rigid.birthdroid.BirthdroidActivity",
    #             "data_dir": "../Data/Test"}
    logging.info("Stage 1: init state info")
    state_info = StateInfo(app_info)
    # print("state_info",vars(state_info))
    app_info["scorer"].set_state_info(state_info)
    logging.info("Stage 2: init env")
    env = EmuRunner(app_info, state_info)
    # print("env",vars(env))
    logging.info("Stage 3: init strategy")
    # explore = RandomExplore(state_info, env)
    explore = QLearningExplore(state_info, env, app_info)
    time.sleep(1)
    logging.info("Stage 4: run testing")
    start_time = time.time()
    step = explore.explore()
    if step > 0:
        logging.info("try step: " + str(step))
        logging.info("reproducing time: " + str(time.time() - start_time))
        uninstall_cmd = "adb shell pm uninstall " + app_info["app_pkg"]
        os.system(uninstall_cmd)
        sg = StepGenerator(app_info["data_dir"])
        sg.gen_reproducing_steps()
    elif step == 0:
        is_crash = check_crash_trigger(app_info["trace_info"])
        if is_crash == 2:
            logging.info("try step: " + str(step))
            logging.info("reproducing time: " + str(time.time() - start_time))
            uninstall_cmd = "adb shell pm uninstall " + app_info["app_pkg"]
            os.system(uninstall_cmd)

def get_activity_names(all_actis):
    names = []
    for acti in all_actis:
        activity_name = acti.split(".")[-1]
        activity_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', activity_name).lower()
        activity_name = re.sub(r"[^a-z0-9]", " ", activity_name)
        activity_name = re.sub(r"\s+", " ", activity_name).strip()
        activity_name = activity_name.replace("activity", "").replace("fragment", "").strip()
        names.append(activity_name)
    return names


if __name__ == '__main__':
    do_clean()
    dataset_dir = "../Data/ReCDroid"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(filename)s:%(lineno)s] %(message)s",
                         datefmt="%m-%d %H:%M:%S")
    do_test(1)

