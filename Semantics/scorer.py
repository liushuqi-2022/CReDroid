import os
import xml.etree.ElementTree as ET
import re
import networkx as nx
from env.state_info import StateInfo, State
from env.currFrag import getcurfrag
import logging
import nltk
import inflect
from env.util import check_crash_trigger
from trigger_check.checker import APITriggerChecker
from Semantics.bert_similarity_calc import SimilarityCalculator_BERT
from Semantics.get_title_action import extract_actions
from nltk.stem import SnowballStemmer
from collections import OrderedDict, Counter

stemmer = SnowballStemmer("english")

os.environ['TOKENIZERS_PARALLELISM'] = "False"


class SimScorer:
    def __init__(self, dst_acti: str, checker: APITriggerChecker, all_pages: list, trace_info: dict, app_pkg: str, CTG,
                 title_context, CTG_dir, input_cont, use_page=1,
                 use_widget=1):
        self.input_content = input_cont
        self.state_action_score = {}
        self.state_info = None
        self.dst_acti = dst_acti
        self.checker = checker
        self.all_pages = all_pages
        self.trace_info = trace_info
        self.trace = trace_info["trace"]
        # self.need_rotate = trace_info["need_rotate"]
        self.use_page = use_page
        self.app_pkg = app_pkg
        self.CTG = CTG
        self.CTG_dir = CTG_dir
        self.tokens_to_remove = ['activity', 'fragment', 'service', 'screen', 'widget', 'ui', 'android', 'dialog',
                                 'button', 'views', 'view', 'utils']
        self.classes_list = trace_info["trace_eles"]["class"]
        # self.classes_list = self.get_trace_classes(self.trace)
        self.long_flag = False
        self.selected_path = []

        if use_page != 1:
            print("#" * 10, "Note", "#" * 10)
            print("use_page: ", self.use_page)
            print("#" * 26)
        self.use_widget = use_widget
        if use_widget != 1:
            print("#" * 10, "Note", "#" * 10)
            print("use_widget: ", self.use_widget)
            print("#" * 26)
        self.text_sim_bert = SimilarityCalculator_BERT()
        self.words = set(nltk.corpus.words.words())
        self.title_actions, self.title_actions_list, self.multi_click = extract_actions(title_context,self.app_pkg)
        print("self.title_actions, self.title_actions_list, self.multi_click",self.title_actions, self.title_actions_list, self.multi_click)

    def get_trace_classes(self, trace):
        # 提取堆栈跟踪中的类名和方法名
        pattern = re.compile(r'at (\S+)\.(\S+)\((\S+):(\d+)\)')
        lines = trace.split('\n')
        methods = OrderedDict()
        classes = OrderedDict()
        for line in lines:
            match = pattern.search(line)
            if match:
                class_name = match.group(1)
                if self.app_pkg in class_name:
                    method_name = match.group(2)
                    methods[f"{class_name}.{method_name}"] = None
                    classes[class_name] = None

        classes_list = list(classes.keys())
        return classes_list

    def set_state_info(self, state_info: StateInfo):
        self.state_info = state_info

    def init_state(self, state_id: int, available_actions,step):
        if state_id < 0 and state_id > 100:
            logging.info("State " + str(state_id) + " maybe invalid, shoult not do init!")
        if state_id in self.state_action_score.keys():
            logging.info("State " + str(state_id) + " has already init!")
            return
        state = self.state_info.states[state_id]
        cur_action_score = self.do_score(state, self.dst_acti, available_actions,step , self.use_page)
        self.state_action_score.setdefault(state_id, cur_action_score)
        logging.info("State " + str(state_id) + " success init!")

    def get_view_score(self, query_info: dict, available_actions, step):
        state_id = query_info["state_id"]
        action_id = query_info["action_id"]
        if state_id not in self.state_action_score.keys():
            logging.info("State " + str(state_id) + " has not init!")
            if state_id >= 0 and state_id < 100:
                self.init_state(state_id,available_actions,step)
            else:
                return -1
        if action_id not in self.state_action_score[state_id].keys():
            logging.info("Error: action not find!: " + str(state_id) + "/" + str(action_id))
            return -1
        return self.state_action_score[state_id][action_id]

    def do_score(self, state: State, dst_acti, available_actions, step, use_page=1):

        name2action = state.get_state_detail()
        filtered_name2action = {key: [action for action in actions if action in available_actions]
                                for key, actions in name2action.items()}
        # 删除值为空的键
        name2action = {key: actions for key, actions in filtered_name2action.items() if actions}

        action_score = {0: -0.1}

        if 1 in state.actions.keys() and state.actions[1]["type"] == "system_rotate":
            action_score.setdefault(1, 3)

        trace_class = self.trace_info['trace_eles']['class']

        if state.activity in self.CTG.nodes():
            src_acti = state.activity
        else:
            src_acti = self.app_pkg + state.activity

        src_frg = ""
        cur_frag = getcurfrag()
        if cur_frag.name != "":
            for node in self.CTG.nodes():
                if cur_frag.name in node and cur_frag.name == node.split(".")[-1]:
                    src_frg = node
                    break  # 找到第一个匹配的节点后就跳出循环
        if "." not in self.dst_acti:
            for node in self.CTG.nodes():
                if self.dst_acti in node:
                    self.dst_acti=node
                    break

        if src_acti == self.dst_acti and self.title_actions is not None:
            if "long" in self.title_actions:
                self.long_flag = True

        for _, action_ids in name2action.items():
            for action_id in action_ids:
                heuristic_score = self.get_view_score_heuristically(state, action_id, step, self.use_widget)
                action_score.setdefault(action_id, heuristic_score)

        if src_acti != self.dst_acti:
            paths = []
            if src_frg != "":
                paths = self.get_can_path(src_frg, self.dst_acti, self.CTG)

            if not paths:
                paths = self.get_can_path(src_acti, self.dst_acti, self.CTG)
            self.selected_path = self.get_best_path(paths[:5], self.title_actions_list)

            if self.selected_path:
                current_index = 0
                if current_index + 1 < len(self.selected_path) and 'Service' in self.selected_path[current_index + 1] and current_index + 2 < len(self.selected_path):
                    # 如果下一个组件是Service，则跳过它
                    next_page = self.selected_path[current_index + 2] if current_index + 2 < len(self.selected_path) else None
                else:
                    # 否则，下一个组件就是当前组件的下一个
                    next_page = self.selected_path[current_index + 1] if current_index + 1 < len(self.selected_path) else None

                # 找到 next_page 在列表中的位置
                index = self.selected_path.index(next_page)

                # 确保 index+1 不超出列表范围
                if index + 1 < len(self.selected_path):
                    next_and_after = self.selected_path[index:index + 2]
                else:
                    next_and_after = [self.selected_path[index]]
            else:
                next_page = self.dst_acti
                next_and_after = [next_page]
                self.selected_path = [src_acti, next_page]
            logging.info("next Component may be: " + next_page)

            if next_page == dst_acti:
                # ②api/class dependency

                    action_score2, self.classes_list = self.get_title_sim0(self.classes_list, name2action)
                    action_score2 = self.get_title_sim(self.title_actions, name2action, action_score2)
                    action_score = self.combine_dict(action_score, action_score2)
            else:
                # ①activity/fragment
                action_score1 = self.get_com_sim(next_and_after, name2action)
                action_score = self.combine_dict(action_score, action_score1)
                if all(value == 0 for value in action_score1.values()):
                    action_score = self.get_title_sim(self.title_actions, name2action, action_score)
        else:
            action_score = self.get_title_sim(self.title_actions, name2action, action_score)
            self.selected_path = [src_acti, dst_acti]
        print("total score", action_score)

        return action_score

    def get_class_semantic(self, trace_class):

        target_class = [cls for cls in trace_class if '$' in cls]
        found_classes = set()

        class_name = target_class[0].split('$')[0]

        xml_file = self.CTG_dir + "/CTGResult/" + 'CTG.xml'
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # 遍历所有source节点
        for source in root.findall('source'):
            # 用于记录当前source节点下已经找到的类
            # 遍历source节点下的所有destination节点
            for destination in source.findall('destination'):
                method_str = destination.get('method')
                if class_name in method_str:
                    found_classes.add(source.get('name').rsplit('.', 1)[-1])

        if len(found_classes) == 0:
            return None

        max_similarity = 0
        most_similar_word = None

        class_name_string = " ".join(self.split_to_tokens(class_name.rsplit('.', 1)[-1]))
        for class_i in found_classes:
            tokens = self.split_to_tokens(class_i)
            string = " ".join(tokens)
            score = self.text_sim_bert.calc_similarity(string, class_name_string)
            if score > max_similarity:
                max_similarity = score
                most_similar_word = string

        return most_similar_word

    def combine_dict(self, dict1, dict2):
        combined_score = {}
        for key, value in dict1.items():
            combined_score[key] = combined_score.get(key, 0) + value

        for key, value in dict2.items():
            combined_score[key] = combined_score.get(key, 0) + value
        return combined_score

    def process_path(self, path):
        processed_path = []
        for component in path:
            # 处理每个组件并将其分割为 token
            # 移除 APK 包名
            component = component.replace(self.app_pkg, '')
            # 分割驼峰命名法的组件名称
            tokens = re.findall(r'[A-Z][a-z]*', component)
            # 移除指定的字符
            processed_tokens = [token for token in tokens if
                                token.lower() not in self.tokens_to_remove]
            # ['Add', 'Provisioner', 'Activity']
            if processed_tokens:
                processed_path.append(' '.join(processed_tokens))  # 添加到结果列表
        return processed_path

    def calculate_relevance_score(self, path_words, bug_report_tokens):

        if not path_words or not bug_report_tokens:
            relevance_score = 0
            return relevance_score
        else:
            similarities = []
            # 计算所有可能的词对的相似度
            for component in path_words:
                for title in bug_report_tokens:
                    similarity = self.text_sim_bert.calc_similarity(component, title)
                    similarities.append((component, title, similarity))

            # 按相似度排序
            similarities.sort(key=lambda x: x[2], reverse=True)
            # 存储最终的匹配结果
            matches = []
            used_components = set()
            used_titles = set()

            # 确保每个词只匹配一次
            for component, title, similarity in similarities:
                if component not in used_components and title not in used_titles:
                    matches.append((component, title, similarity))
                    used_components.add(component)
                    used_titles.add(title)

            # 计算加权平均分数
            if matches:
                total_similarity = sum(match[2] for match in matches)
                relevance_score = total_similarity / len(matches)
            else:
                relevance_score = 0
        return relevance_score

    def get_best_path(self, paths, title_actions_list):
        best_path = []
        best_score = -1

        for path in paths:

            path_word_list = self.process_path(path)
            # [['Preferences']]
            # ②将title词跟component对应
            relevance_score = self.calculate_relevance_score(path_word_list, title_actions_list)
            # ①距离
            # 综合评分
            total_score = relevance_score
            if total_score > best_score:
                best_score = total_score
                best_path = path
        return best_path

    def get_com_sim(self, next_and_after, name2action):
        # ①目前的widget与component的匹配度
        action_score = {}
        for activity_name in next_and_after:
            class_name = activity_name.split('.')[-1]
            # 步骤 2: 使用驼峰命名法分解类名为单词
            # 使用正则表达式来分解驼峰命名
            keywords = re.findall(r'[A-Z][a-z]*', class_name)
            # 名词到动词的映射字典
            noun_to_verb = {
                "Editor": "Edit",
                "Creator": "Create",
                "Viewer": "View",
                # 可以根据需要扩展更多的映射
            }
            sim_keywords = []
            for keyword in keywords:
                # 使用映射字典转换
                converted_keyword = noun_to_verb.get(keyword, keyword)
                sim_keywords.append(converted_keyword)

            # 删除指定的词
            sim_keywords = [keyword for keyword in sim_keywords if
                            keyword.lower() not in self.app_pkg and keyword.lower() not in self.tokens_to_remove]

            sentence_keywords = ' '.join(sim_keywords)

            for _, action_ids in name2action.items():
                for action_id in action_ids:
                    score0 = self.text_sim_bert.calc_similarity(_, sentence_keywords) if _ != 'other' and sim_keywords else 0
                    action_score[action_id] = action_score.get(action_id, 0) + score0

        # ①目前的widget与target component的前一个的组件的匹配度

        predecessors = list(self.CTG.predecessors(self.dst_acti))
        if predecessors:
            for _, action_ids in name2action.items():
                for action_id in action_ids:
                    for pre_i in predecessors:
                        if _.replace(" ", "") in pre_i.lower():
                            action_score[action_id] += 1/ len(predecessors)
        return action_score

    def get_title_sim0(self, classes_list, name2action):
        action_score = {}
        if len(classes_list) == 0:
            action_score.update({action_id: 0 for action_ids in name2action.values() for action_id in action_ids})
            return action_score, classes_list

        class_name0 = classes_list[0]
        class_keywords = self.process_class_name(class_name0, self.app_pkg)

        class_keywords_list = class_keywords.split()
        for i in range(len(class_keywords_list) - 1, -1, -1):
            if class_keywords_list[i].lower() in self.app_pkg.lower() or class_keywords_list[i].lower() in self.tokens_to_remove:
                del class_keywords_list[i]

        if not class_keywords_list:
            action_score.update({action_id: 0 for action_ids in name2action.values() for action_id in action_ids})
            return action_score, classes_list

        for _, action_ids in name2action.items():
            for action_id in action_ids:
                score0 = self.text_sim_bert.calc_similarity(_, ' '.join(class_keywords_list))
                if score0:
                    action_score[action_id] = score0

        classes_list.remove(class_name0)

        return action_score, classes_list

    def process_class_name(self, full_class_name, known_package_name):
        if full_class_name.startswith(known_package_name):
            class_name_part = full_class_name[len(known_package_name) + 1:]  #
        else:
            class_name_part = full_class_name

        # 提取类名部分
        class_parts = class_name_part.split(".")
        # 获取类的层级（网络/模块名和实际类名）
        class_hierarchy = " ".join(class_parts[:-1])  # 网络/模块部分：network
        class_name = class_parts[-1]  # 实际类名：APIManager
        words = re.findall(r'[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z][a-z]*', class_name)
        words = words[-3:]
        # 保留连续大写字母不变，其他部分转为小写
        processed_class_name = " ".join([word if word.isupper() else word.lower() for word in words])
        # 将层级和类名组合
        full_processed_class_name = f"{class_hierarchy} {processed_class_name}".strip()

        return full_processed_class_name

    def get_title_sim(self, title_actions, name2action, action_score):
        if len(action_score) > 30:
            return action_score
        for _, action_ids in name2action.items():
            for action_id in action_ids:
                score0 = self.text_sim_bert.calc_similarity(_, title_actions) if (_ != 'other' and title_actions) else 0
                if score0 > 0.45:
                    action_score[action_id] += score0
                else:
                    score_similarity = 0
                    for action in self.title_actions_list:
                        similarity = self.text_sim_bert.calc_similarity(_, action) if (_ != 'other' and title_actions) else 0

                        if similarity > 0.45:
                            score_similarity = similarity
                            break
                    action_score[action_id] += score_similarity
        return action_score

    def get_can_path(self, src_node, des_acti, CTG):
        if src_node in CTG.nodes():
            can_paths = list(nx.all_simple_paths(CTG, source=src_node, target=des_acti))
            can_paths.sort(key=len)
        else:
            return []
        return can_paths

    def get_activity_name(self, activity_name):
        activity_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', activity_name).lower()
        activity_name = re.sub(r"[^a-z]", " ", activity_name)
        activity_name = re.sub(r"\s+", " ", activity_name).strip()
        activity_name = activity_name.replace("activity", "").replace("fragment", "").strip()
        return activity_name

    def get_state_score_heuristically(self, before_state, full_activity: str, state_type: int, action: dict, is_state_same: bool,tgt_actions):
        logging.info("reward:")
        if action["type"] == "system_rotate":
            # rotate would be tried at first, but only one time
            return -1000, 0

        is_crash = check_crash_trigger(self.trace_info)
        if is_crash == 2:
            return 1000, 2
        if is_crash == 1:
            return -1000, 1

        trigger_res = self.checker.check_trigger_res()

        base_score = 0
        if trigger_res == 5:
            base_score = 20
        elif trigger_res == 4:
            base_score = 5
        elif trigger_res == 3:
            base_score = 5
        elif trigger_res == 2:
            base_score = 1

        if is_state_same and not self.multi_click:
            return base_score - 2, 0
        if action["type"] == "system_back" and state_type == 0:
            return base_score, 0
        # todo: prefix activity of crash return 1

#         #   9999: not the activity in app
#         #   0: state already found
#         #   1: state new find (activity already found)
#         #   2: state new find (activity new find)
        if state_type == -1:
            base_score -= 100
        elif state_type == 0:
            base_score -= 2
        elif state_type == 1:
            base_score += 4
        elif state_type == 2:
            base_score += 10
        else:
            base_score -= 100
            logging.info("Unexcept state type:" + str(state_type))

        if action['refer_name'] == 'system back':
            return base_score, 0

        if self.title_actions is not None:
        # ①add: to title
        #     common_words = self.has_common_words(action['refer_name'], self.title_actions)
            sore = self.text_sim_bert.calc_similarity(action['refer_name'], self.title_actions)
            if sore > 0.75:
                base_score += 5
            elif action['type'] == 'click' and action['refer_name'] == "more options" and "setting" in self.title_actions:
                base_score += 3

        # ②add: to CTG
        if full_activity == self.selected_path[0]:
            base_score += 3
        elif full_activity == self.selected_path[-1]:
            base_score += 5
        elif full_activity in self.selected_path:
            base_score += 5
        return base_score, is_crash

    def plural_to_singular(self, word):
        p = inflect.engine()
        singular_word = p.singular_noun(word)
        if singular_word:
            return singular_word
        else:
            return word  # 如果没有复数形式，返回原单词

    def has_common_words(self, str1, str2):
        if '/' in str1:
            str1 = str1.replace('/', ' ')
        if len(str1.split()) == 1:
            str1 = self.plural_to_singular(str1)
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        common_words = words1.intersection(words2)
        return common_words

    def get_view_score_heuristically(self, state: State, action_id: int, step, use_widget=1):
        interest_words = {"new", "create", "agree", "navigation", "drawer", "next", "send", "ok", "enter", "show",
                          "photo", "study", "skip", "open", "done", "refresh"}

        not_interest_words = ["download", "preferences", "filter", "preview", "icons", "genres", "message icons",  "close"]

        view_score = 0
        action = state.actions[action_id]
        refer_name = action["refer_name"]
        action_class = action["class"]
        action_type = action["type"]
        refer_name_tokens = self.split_to_tokens(refer_name)
        refer_name_tokens = set(refer_name_tokens)

        stem_trace_tokens = set()
        for token in self.trace_info["trace_tokens"]:
            stem_trace_tokens.add(stemmer.stem(token))
        stem_dst_tokens = set()
        for token in self.get_activity_name(self.dst_acti).split():
            stem_dst_tokens.add(stemmer.stem(token))
        stem_refer_name_tokens = set()
        for token in refer_name_tokens:
            stem_refer_name_tokens.add(stemmer.stem(token))

        if refer_name == "system back":
            return -0.1

        if action_type == "fill_info":
            view_score += 0.11

        if action_class == "EditText" and "search" in refer_name:
            view_score += 0.3

        if self.title_actions is not None:
            if refer_name in ["settings"] and "option" in self.title_actions:
                view_score += 0.3
            if "options" in refer_name and ("create" in self.title_actions or "settings" in self.title_actions):
                view_score += 0.3
            if action_type == "input" and "enter" in self.title_actions:
                view_score += 0.3

        inter_token_len = len(stem_refer_name_tokens.intersection(stem_trace_tokens))

        in_token_flag = ' '.join(self.split_to_tokens(refer_name)) in self.trace_info["trace_tokens"]

        widget_type_in_token = action_class.lower() in self.trace_info["trace_tokens"]
        if self.title_actions is not None:
            if len(self.has_common_words(refer_name, self.title_actions)) > 0 or refer_name in self.title_actions.lower():
                if len(self.has_common_words(refer_name, self.title_actions)) > 2:
                    view_score += 0.4*2
                else:
                    view_score += 0.4
        if self.is_full_width(action_class, action['bounds']):
            view_score += 0.4
        if self.is_menu_element(action_class, action['bounds'], refer_name) and step > 30:
            view_score += 0.5
        if refer_name in list(self.input_content.values()) and action_class in ['LinearLayout', 'RecyclerView']:
            view_score += 0.8
        if inter_token_len > 0 and use_widget > 0:
            view_score += 0.15 * inter_token_len * use_widget
        elif in_token_flag or widget_type_in_token and use_widget > 0:
            view_score += 0.15 * use_widget
        elif len(refer_name_tokens.intersection(interest_words)) > 0 and view_score == 0:
            view_score += 0.1
        elif action_type == "long_click" and self.long_flag:
            view_score += 0.4
        elif action_type == "long_click" and "root" in refer_name:
            view_score += 0.1
        elif action_type == "long_click" and "hello" in refer_name.lower():
            view_score += 0.01
        elif refer_name in not_interest_words and state.state_id > 1:
            view_score -= 0.4
        return view_score

    def is_menu_element(self, element_class, bounds, refer_name, screen_width=1080, screen_height=1920):
        if element_class != 'ImageButton' or "search" in refer_name or len(refer_name.split()) > 3:
            return False
        x1, y1 = bounds[0]
        x2, y2 = bounds[1]

        width = x2 - x1
        height = y2 - y1

        if (x1 < screen_width * 0.1 and width < screen_width * 0.2 and height < screen_height * 0.1) or (x2 > screen_width * 0.9 and width < screen_width * 0.2 and height < screen_height * 0.1):
            return True

        return False

    def is_full_width(self, element_class, bounds):

        if element_class != 'RelativeLayout':
            return False

        left = bounds[0][0]
        right = bounds[1][0]
        if left == 0 and right == 1080:
            return True

        return False

    def split_to_tokens(self, in_str: str):
        new_str = re.sub(r'([a-z])([A-Z])', r'\1 \2', in_str).lower()
        new_str = re.sub("[^a-z]", " ", new_str).strip()
        new_str = re.sub("\s+", " ", new_str)
        tokens = new_str.split(" ")
        tokens = [token for token in tokens
                  if token not in self.app_pkg and token not in self.tokens_to_remove]

        return tokens


if __name__ == '__main__':
    in_str = 'FilesystemDialogCreator'
    new_str = re.sub(r'([a-z])([A-Z])', r'\1 \2', in_str).lower()
    new_str = re.sub("[^a-z]", " ", new_str).strip()
    new_str = re.sub("\s+", " ", new_str)
    tokens = new_str.split(" ")
    string = " ".join(tokens)

    print("tokens", string)
