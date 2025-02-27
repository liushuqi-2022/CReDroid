import os
import re
import json
import pandas as pd
import xml.etree.ElementTree as ET
from collections import OrderedDict

trace_stopwords = ['java', 'exception', 'on', 'e', 'lang', 'android', 'invoke', 'runtime', 'at', 'run', 'os', 'method',
                   'handle', 'fatal', 'com', 'internal', 'pid', 'main', 'dispatch', 'process', 'app', 'message',
                   'thread', 'activity', 'zygote', 'reflect', 'caller', 'handler', 'args', 'native', 'looper', 'loop',
                   'and', 'init', 'perform', 'to', 'get', 'by', 'view', 'caused', 'a', 'more', 'null', 'pointer',
                   'callback', 'start', 'call', 'wrap', 'attempt', 'impl', 'unable', 'h', 'list', 'object', 'reference',
                   'state', 'create', 'virtual', 'widget', 'instrumentation', 'launch', 'org', 'adapter', 'item',
                   'click', 'manager', 'info', 'fragment', 'ui', 'for', 'component', 'do', 'util', 'window', 'illegal',
                   'action', 'helper', 'not', 'async', 'selected', 'policy', 'phone', 'input', 'abs', 'builder', 'menu',
                   'root', 'group', 'queue', 'layout', 'jni', 'event', 'sqlite', 'database', 'support', 'v', 'androidx',
                   'touch', 'task', 'stage', 'drawable', 'compat', 'pager', 'inflate', 'kt', 'delegate', 'integer', 'k',
                   'fsck', 'vdc', 'camera', 'class', 'acra', 'open', 'fretboard', 'account', 'base', 'linear',
                   'presenter']

def preprocess_trace(trace_path: str, full_app_pkg: str, all_actis: list,CTG_dir,CTG):
    app_pkg = ".".join(full_app_pkg.split(".")[:2])
    trace = open(trace_path, "r", encoding="UTF-8").read()
    trace_eles = get_related_element(full_app_pkg, trace, app_pkg,all_actis)
    trace_actis = get_trace_activities(trace, CTG_dir, all_actis,trace_eles,CTG)
    trace_tokens = get_token_from_eles(trace, trace_eles, full_app_pkg)
    trace_info = {"trace": trace, "trace_tokens": trace_tokens, "trace_eles": trace_eles, "trace_actis": trace_actis}
    return trace_info

def get_trace_activities(trace: str, CTG_dir, all_actis,trace_eles,CTG):
    trace_actis = set()
    trace_class=trace_eles['class']

    last_class = None
    for line in trace.split("\n"):
        for cls in trace_class:
            if cls in line:
                last_class = cls

    # 尝试利用最后一个出现的class来检索source activity
    CTG_xml = CTG_dir + "/CTGResult/" + 'CTG.xml'
    activity_name = find_activity_for_classes(CTG_xml, last_class)
    if activity_name:
        trace_actis.add(activity_name)
    else:
        if last_class is not None and "$" in last_class:
            last_class = last_class.split("$")[0]
        if last_class in CTG.nodes():
            trace_actis.add(last_class)
    # 如果找不到具体的活动或者fragment，匹配活动

    if not trace_actis:
        # 将所有活动名拼接成正则表达式模式
        pattern = r'|'.join(map(re.escape, all_actis))  # 使用 re.escape 处理特殊字符
        matches = re.findall(pattern, trace)
        # 将匹配到的活动名添加到 trace_actis 中
        trace_actis.update(matches)

    return list(trace_actis)


def find_activity_for_classes(xml_file, last_class):
    # 解析XML文件
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # 遍历所有source节点
    for source in root.findall('source'):
        # 用于记录当前source节点下已经找到的类
        found_classes = set()

        # 遍历source节点下的所有destination节点
        for destination in source.findall('destination'):
            method_str = destination.get('method')
            if method_str:
                # 正则表达式提取方法签名中的类名
                match = re.search(r'<([^:]+):', method_str)
                if match:
                    class_name = match.group(1)

                    if class_name == last_class:
                        found_classes.add(class_name)

            # 如果找到了所有的目标类，返回该source节点的name属性
            if 0 < len(found_classes):
                return source.get('name')

    # 如果没有找到匹配的source，则返回None
    return None


def get_related_element(full_app_pkg, trace: str, app_pkg: str, all_actis):
    # trace = trace.replace("\t", " ").replace("\n", " ")

    # 分割s以获取分割后的部分数量
    parts = app_pkg.split('.')
    # 从all_actis中截取相同数量的部分
    # 使用join是为了确保即使有重叠的部分也能正确截取
    app_pkg = '.'.join(all_actis[0].split('.')[:len(parts)])

    trace1 = re.sub("[^a-zA-Z0-9.()$<>]", " ", trace)
    split_app_pkg = app_pkg.split(".")
    if len(split_app_pkg) >= 3:
        short_app_pkg = ".".join(split_app_pkg[:1])
    else:
        short_app_pkg = app_pkg

    trace_eles = trace1.split(" ")
    temp_class = []
    related_eles = {"class": [], "api": set(), "all": set()}
    for element in trace_eles:
        # if app_pkg in element and element != app_pkg:
        if len(element.strip()) < 3:
            continue
        if element[-1] == ".":
            element = element[:-1]
        if (app_pkg in element or short_app_pkg in element) and element != app_pkg:
            related_eles["all"].add(element)
            if "(" in element:
                method = element.split("(")[0]
                related_eles["api"].add(method)
                class_of_method = ".".join(method.split(".")[:-1])
                # related_eles["class"].add(class_of_method)
                if class_of_method not in temp_class:
                    temp_class.append(class_of_method)
            else:
                if element not in temp_class:
                    temp_class.append(element)

    temp_class2 = []

    for idx, class1 in enumerate(temp_class):
        skip_flag = False
        for class2 in temp_class:
            if class1 != class2 and class1 in class2 and class1.count(".") < class2.count("."):
                skip_flag = True
                break
        if skip_flag:
            continue

        if "activity" in class1.lower() or "fragment" in class1.lower():
            temp_class2.append([class1, idx - 100])
        else:
            temp_class2.append([class1, idx])
    temp_class2.sort(key=lambda x: x[1])
    for t in temp_class2:
        related_eles["class"].append(t[0])

    classes = get_trace_classes(full_app_pkg,trace)

    # 使用集合操作来去重
    existing_classes = set(related_eles["class"])  # 转换为集合以去重
    new_classes = set(classes)  # 转换 classes 列表为集合
    merged_classes = existing_classes.union(new_classes)
    related_eles["class"] = list(merged_classes)

    return related_eles

def get_trace_classes(app_pkg,trace):
    # 提取堆栈跟踪中的类名和方法名

    pattern = re.compile(r'at (\S+)\.(\S+)\((\S+):(\d+)\)')
    lines = trace.split('\n')
    methods = OrderedDict()
    classes = OrderedDict()
    for line in lines:
        match = pattern.search(line)

        if match:
            class_name = match.group(1)
            if app_pkg in class_name:
                method_name = match.group(2)
                methods[f"{class_name}.{method_name}"] = None  # OrderedDict键唯一
                classes[class_name] = None  # OrderedDict键唯一

    classes_list = list(classes.keys())
    pattern = r"fragment\s([A-Za-z0-9]+Fragment)"

    match0 = re.findall(pattern, trace)
    if match0 and match0[0] not in classes_list:
        classes_list.extend(match0)
    return classes_list

def get_trace_tokens(trace: str, app_pkg: str):
    clean_trace_tokens = []
    for trace_line in trace.split("\n"):
        if app_pkg not in trace_line:
            continue
        trace_tokens = split_to_tokens(trace_line)
        trace_tokens = [t for t in trace_tokens if t not in trace_stopwords]
        clean_trace_tokens.extend(trace_tokens)
    return clean_trace_tokens


def split_to_tokens(in_str: str):
    new_str = re.sub(r'([a-z])([A-Z])', r'\1 \2', in_str).lower()
    new_str = re.sub("[^a-z]", " ", new_str)
    new_str = re.sub("\s+", " ", new_str).strip()
    tokens = new_str.split(" ")
    return set(tokens)

def get_trace_stopwords():
    file_freq = {}
    word_freq = {}
    for root, dirs, files in os.walk("traces/"):
        for name in files:
            trace_content = open(os.path.join(root, name), "r").read()
            trace_tokens = split_to_tokens(trace_content)
            for token in trace_tokens:
                if token not in word_freq.keys():
                    word_freq.setdefault(token, 1)
                else:
                    word_freq[token] += 1
            trace_tokens_set = set(trace_tokens)
            for token in trace_tokens_set:
                if token not in file_freq.keys():
                    file_freq.setdefault(token, 1)
                else:
                    file_freq[token] += 1
    sort_word_freq = sorted(word_freq.items(), key=lambda d: d[1], reverse=True)
    sort_file_freq = sorted(file_freq.items(), key=lambda d: d[1], reverse=True)
    stopwords = []
    for (word, freq) in sort_file_freq:
        if freq >= 7:
            stopwords.append(word)
    for (word, freq) in sort_word_freq[:100]:
        if word not in stopwords:
            stopwords.append(word)
    return stopwords


def get_token_from_eles(trace: str, trace_eles: dict, app_pkg: str):
    all_tokens = set()
    app_pkg_token = app_pkg.split(".")
    for line in trace.split("\n")[:2]:
        line_tokens = split_to_tokens(line)
        for token in line_tokens:
            if token not in trace_stopwords and token not in app_pkg_token and len(token) > 0:
                all_tokens.add(token)

    for ele_type, eles in trace_eles.items():
        for ele in eles:
            clean_ele = re.sub(r"[^a-zA-Z]", " ", ele.replace(app_pkg, "")).strip()
            if len(clean_ele) > 0:
                token_set1 = split_to_tokens(clean_ele)
                all_tokens = all_tokens.union(token_set1)
                for token in clean_ele.lower().strip().split(" "):
                    if len(token) > 0:
                        all_tokens.add(token)
    all_tokens = [token for token in all_tokens
              if token not in app_pkg and token not in ['activity', 'widget', 'service']]
    return all_tokens


def test_trace_analyse():
    res = {"app": [], "trace": [], "trace_tokens": [], "trace_eles": [], "trace_actis": []}
    trace_dir = "../Data/ReCDriod/traces/"
    app_file = open("../Data/ReCDriod/activity.txt", "r")
    app_info = json.load(app_file)
    for apk, info in app_info.items():
        trace_path = trace_dir + apk.replace(".apk", ".txt")
        app_pkg = info["app_pkg"]
        trace_info = preprocess_trace(trace_path, app_pkg, info["all_actis"],apk)
        res["app"].append(apk)
        res["trace"].append(trace_info["trace"])
        res["trace_tokens"].append(trace_info["trace_tokens"])
        res["trace_eles"].append(trace_info["trace_eles"])
        res["trace_actis"].append(trace_info["trace_actis"])
    df = pd.DataFrame(res)
    df.to_csv("trace.csv", index=False)


if __name__ == '__main__':
    # get_trace_stopwords()
    # preprocess_trace("", "com.orpheusdroid.screenrecorder")
    # test_trace_analyse()
    # a = set(["a", "b", "c"])
    # b = set(["d", "b", "c"])
    # c = a.union(b)
    # print(c)
    # t = preprocess_trace("../Data/MyData/traces/3_ankidroid-Anki-Android-9914.txt", "com.ichi2.anki", [])
    # for k, v in t.items():
    #     print(k)
    #     print(v)
    a = [1, 5, 2, 3, 6, 4]
    a.sort(reverse=True)
    print(a)
