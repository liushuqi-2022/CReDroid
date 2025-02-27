import re
from env.state import State
import cv2
import time
import numpy as np
import os

last_check = 0

def get_state_sim(state_1: State, state_2: State):
    # todo: cal state sim
    return 0

def evaluate_crash_similarity(trace_info, current_stack_trace):
    # 权重定义
    weights = {
        'trace_tokens': 1,  # 关键字权重
        'class': 2,  # 类名权重
        'api': 3,  # API调用权重
        'exception': 5
    }

    # 初始化分数
    total_score = 0
    max_score = 0  # 计算可能的最大分数，用于归一化

    expected_coms=extract_componentInfo(trace_info)
    all_coms_found = all(com in current_stack_trace for com in expected_coms)

    expected_exceptions = extract_exceptions(trace_info)

    all_elements_found = all(exception in current_stack_trace for exception in expected_exceptions)

    if not all_coms_found:
        return 0

        # 1. 关键字匹配
    if trace_info['trace_tokens'] or trace_info['trace_tokens']:

        for token in trace_info['trace_tokens']:
            max_score += weights['trace_tokens']
            if token.lower() in current_stack_trace.lower():
                total_score += weights['trace_tokens']

        # 2. 类名匹配
        for class_name in trace_info['trace_eles']['class']:

            max_score += weights['class']
            if class_name.lower() in current_stack_trace.lower():
                total_score += weights['class']

        # 3. API调用匹配
        for api_call in trace_info['trace_eles']['api']:

            max_score += weights['api']
            if api_call.lower() in current_stack_trace.lower():
                total_score += weights['api']

    if all_elements_found:
        max_score += weights['exception']
        total_score += weights['exception']

    # 计算分数百分比
    if max_score == 0:
        return 0  # 防止除以0
    similarity_score = total_score / max_score
    return similarity_score


def extract_exceptions(trace_info):
    trace_text = trace_info.get('trace', '')
    exceptions = []

    # 匹配 "FATAL EXCEPTION:" 和 "Caused by:" 之后的异常信息
    fatal_exception_pattern = re.compile(r'FATAL EXCEPTION:\s*(\w+)')
    caused_by_pattern = re.compile(r'Caused by:\s*([\w.$]+)')
    exception_pattern = re.compile(r'(java\.[\w.]+Exception):\s*(.*)')

    # 查找所有匹配的异常
    fatal_exceptions = fatal_exception_pattern.findall(trace_text)
    caused_by_exceptions = caused_by_pattern.findall(trace_text)

    exceptions.extend(fatal_exceptions)
    exceptions.extend(caused_by_exceptions)

    if exception_pattern.search(trace_text):
        exception_type = exception_pattern.search(trace_text).group(1)
        exceptions.append(exception_type)

    return exceptions


def extract_componentInfo(trace_info):
    trace_text = trace_info.get('trace', '')
    components = []

    unable_to_start_pattern = re.compile(
        r'Unable to start activity ComponentInfo\{([^}]+)\}:?\s*([\w.$]+Exception):?\s*(.*)'
    )

    unable_to_start_matches = unable_to_start_pattern.findall(trace_text)

    for match in unable_to_start_matches:
        component_info, exception_type, exception_message = match
        print("component_info",component_info)
        components.append(component_info)

    error_pattern = re.compile(r':\s*([^\n:]*?)(?=\s+error)', re.IGNORECASE)
    error_exceptions = error_pattern.findall(trace_text)
    error_exceptions = [match for match in error_exceptions if match.strip()]
    components.extend(error_exceptions)
    return components

def clean_resource_id(resource_id: str):
    resid_ori=resource_id
    resource_id = re.sub(r'([a-z])([A-Z])', r'\1 \2', resource_id).lower()
    resource_id = re.sub("[^a-z]", " ", resource_id).strip()
    useless_words = ["edittext", "button", "none", "view", "textview", "action", "fab"]
    words = resource_id.strip().split(" ")
    for useless_word in useless_words:
        if "".join(words) == useless_word:
            return resid_ori

    use_word = []
    for word in words:
        word_char = set(word)
        # drop word that maybe abbreviation from edittext/button, like: edit, edt, ed, text...
        use_flag = True
        for useless_word in useless_words:
            inter_with_useless_word = word_char.intersection(set(useless_word))
            if len(word_char) <= len(inter_with_useless_word):
                use_flag = False
                break
        if use_flag:
            use_word.append(word)
    if len(use_word) == 0:
        return "none"
    else:
        return " ".join(use_word)

def check_crash():
    # print("checking crash")
    log_file = open("../Data/Temp/log/log_out.txt", "r", encoding="UTF-8", errors="ignore")
    log_lines = log_file.readlines()
    log_file.close()

    for line in log_lines[-200:]:
        if re.match(r".*?AndroidRuntime: FATAL EXCEPTION: .*", line):
            print(line)
            return True

        if re.match(r".*?getText\(\) = Unfortunately, .*? has stopped.*", line):
            print(line)
            return True
        if re.match(r".*?W DropBoxManagerService: Dropping: data_app_crash.*?", line):
            print(line)
            return True
        if re.match(r".*?UiObject: getText\(\) = .*? isn't responding\..*?", line):
            print(line)
            return True
    return False


def check_img_same(img_path1: str, img_path2: str):
    return True
    if not os.path.exists(img_path1) or not os.path.exists(img_path2):
        return True
    img1 = cv2.imread(img_path1)
    hash1 = pHash(img1)
    img2 = cv2.imread(img_path2)
    hash2 = pHash(img2)
    n3 = cmpHash(hash1, hash2)
    if n3 > 13:
        return False
    else:
        return True

def pHash(img):
    if not isinstance(img, np.ndarray):
        return [0]
    # if (not isinstance(img1.shape, tuple)) or len(img1.shape) != 3 or img.shape[0] < 10:
    #     return [0]
    if not isinstance(img.shape, tuple):
        return [0]
    if len(img.shape) != 3:
        return [0]
    if img.shape[0] < 10:
        return [0]
    img = cv2.resize(img, (32, 32))  # , interpolation=cv2.INTER_CUBIC
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dct = cv2.dct(np.float32(gray))
    dct_roi = dct[0:8, 0:8]

    hash = []
    avreage = np.mean(dct_roi)
    for i in range(dct_roi.shape[0]):
        for j in range(dct_roi.shape[1]):
            if dct_roi[i, j] > avreage:
                hash.append(1)
            else:
                hash.append(0)
    return hash


def cmpHash(hash1, hash2):
    n = 0
    if len(hash1) != len(hash2):
        return -1
    for i in range(len(hash1)):
        if hash1[i] != hash2[i]:
            n = n + 1
    return n

def get_input_content(edit_id: str, default_cont: str, default_input: str, input_cont: dict):
    for key, content in input_cont.items():
        if key in edit_id:
            return content
    if "all" in input_cont.keys():
        return input_cont["all"]
    if "name" in edit_id or "email" in edit_id:
        return "foo@bar.123"
    if default_cont.isdigit():
        return "1145141919810893"
    return default_input


def get_account():
    name_map = {"com.example.terin.asu_flashcardapp": "lu@gml.com", "com.fsck.k9.debug": "dingzhen1919810@outlook.com"}
    pass_map = {"com.example.terin.asu_flashcardapp": "12331986", "com.fsck.k9.debug": "zaq13edc"}
    return name_map, pass_map

def check_crash_trigger(stack_info: dict):
    global last_check
    current_stack_trace = open("../Data/Temp/log/log_out.txt", "r", encoding="UTF-8").read()
    log_file = open("../Data/Temp/log/log_out.txt", "r", encoding="UTF-8", errors="ignore")

    log_lines = []
    for line in log_file.readlines():
        if len(line.strip()) > 0:
            log_lines.append(line)
    log_file.close()
    check_begin = max(0, len(log_lines) - 1000)
    thres = 3
    crash_score = evaluate_crash_similarity(stack_info, current_stack_trace)
    if crash_score > 0.9:
        return 2
    else:

        for line_idx in range(check_begin, len(log_lines) - thres):
            line = log_lines[line_idx]
            if re.match(r".*?AndroidRuntime: FATAL EXCEPTION: .*", line):
                print("find a crash")
                print(line)
                return 1
            # if re.match(r".*?AndroidRuntime: FATAL EXCEPTION: main.*", line):
            #     print(line)
            #     return True
            if re.match(r".*?getText\(\) = Unfortunately, .*? has stopped.*", line):
                print("find a crash")
                print(line)
                return 1
            if re.match(r".*?W DropBoxManagerService: Dropping: data_app_crash.*?", line):
                print("find a crash")
                print(line)
                return 1
            if re.match(r".*?UiObject: getText\(\) = .*? isn't responding\..*?", line):
                print("find a crash")
                print(line)
                return 1
            if re.match(r".*?ACRA.*?: ACRA caught a RuntimeException for com.ichi2.anki.*?", line):
                print("find a crash")
                print(line)
                return 1

        last_check = 1
    return 0

def check_crash_strict(stack_trace: str, thres=3):
    global last_check
    tgt_trace = clean_trace_line(stack_trace.split("\n")[:thres])

    log_file = open("../Data/Temp/log/log_out.txt", "r", encoding="UTF-8", errors="ignore")
    log_lines = []
    for line in log_file.readlines():
        if len(line.strip()) > 0:
            log_lines.append(line)
    log_file.close()
    check_begin = max(0, len(log_lines)-1000)
    # 最后一百行
    for line_idx in range(check_begin, len(log_lines) - thres):
        cur_block = log_lines[line_idx: line_idx + thres]
        cur_trace_str = clean_trace_line(cur_block)
        if cur_trace_str == tgt_trace:
            return 2
        line = log_lines[line_idx]
        if re.match(r".*?AndroidRuntime: FATAL EXCEPTION: .*", line):
            print("find a crash")
            print(line)
            return 1

        if re.match(r".*?getText\(\) = Unfortunately, .*? has stopped.*", line):
            print("find a crash")
            print(line)
            return 1
        if re.match(r".*?W DropBoxManagerService: Dropping: data_app_crash.*?", line):
            print("find a crash")
            print(line)
            return 1
        if re.match(r".*?UiObject: getText\(\) = .*? isn't responding\..*?", line):
            print("find a crash")
            print(line)
            return 1
        if re.match(r".*?ACRA.*?: ACRA caught a RuntimeException for com.ichi2.anki.*?", line):
            print("find a crash")
            print(line)
            return 1

    last_check = 1
    return 0


def clean_trace_line(lines):
    process_res = ""
    for line in lines:
        line = re.sub("@[0-9a-f]+", "#", line)
        line = re.sub("#0x[0-9a-f]+", "#", line)
        process_res += re.sub("\d+", "#", line).strip()
    process_res2 = re.sub("[^A-Za-z#.:$]", "", process_res)
    return process_res2


if __name__ == '__main__':
    print()
