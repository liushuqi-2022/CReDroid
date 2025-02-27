import random
from env.state_info import StateInfo, State
from env.emulator import EmuRunner
from env import util
import time
import logging
from strategy.action_recoder import ActionRecoder
import os


class QLearningExplore:
    def __init__(self, state_info: StateInfo, env: EmuRunner, app_info, lr=0.1, gamma=0.9):
        self.state_info = state_info
        self.env = env
        self.visit_actions = dict()
        self.action_q = dict()
        self.app_info = app_info
        self.scorer = app_info["scorer"]
        self.multi_flag = app_info["multi_click"]
        self.lr = lr
        self.gamma = gamma
        self.bored_counter = 0
        self.recoder = ActionRecoder(state_info, app_info["action_output"])
        self.action_count = {}
        self.action_history = []
        self.action_loop = []

    def explore(self):
        # self.env.reset(reset_all=True)
        if self.env.driver is None:
            return 0

        for step in range(1, 2001):
            logging.info("##### Step " + str(step) + " #####")
            if step == 1:
                time.sleep(3)
            before_state, _ = self.env.get_cur_state()
            logging.info("Before state: " + str(before_state))
            if before_state > 9000:
                logging.info("try relaunch")
                self.env.relaunch_app()
                before_state, _ = self.env.get_cur_state()
            if before_state not in self.action_q.keys():
                self.init_action_q(before_state, step)
            choose_idx, choose_action = self.choose_action(before_state)

            logging.info("Choose action: " + str(choose_idx))

            if before_state not in self.action_count:
                self.action_count[before_state] = {}

            # 统计该状态下的组件出现次数
            if choose_idx not in self.action_count[before_state]:
                self.action_count[before_state][choose_idx] = 1
            else:
                self.action_count[before_state][choose_idx] += 1

            if choose_idx == -1:
                self.punish_action_to_stuck(choose_action, step)
                self.recoder.add_restart_to_history()
                try:
                    self.driver.launch_app()
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error while hiding keyboard: {e}")
                    is_crash = util.check_crash_trigger(self.app_info["trace_info"])
                    if is_crash == 2:
                        return step
                continue
            after_state, reward, done, info = self.env.step(choose_idx)

            self.action_history = self.recoder.update(before_state, after_state, choose_idx, reward)
            logging.info("Update aciton q: " + str(before_state) + "," + str(choose_idx))
            if done == 2:
                return step
            elif done == 1:
                update_res = self.update_action_q(before_state, choose_idx, after_state, reward, choose_action, step)
                self.recoder.add_restart_to_history()
                self.env.reset(force_reset=True)
                os.system("adb logcat -c")
                f = open("../Data/Temp/log/log_out.txt", "w")
                time.sleep(0.5)
            elif done == 0:
                self.update_action_q(before_state, choose_idx, after_state, reward, choose_action, step)

            if after_state > 9000:
                self.recoder.add_restart_to_history()
                try:
                    self.env.reset()
                except Exception as e:
                    print(f"Error while hiding keyboard: {e}")
                    is_crash = util.check_crash_trigger(self.app_info["trace_info"])
                    if is_crash == 2:
                        return step
            self.state_info.save_pkl()
        return -1

    def update_action_q(self, before_state: int, before_action_idx: int, after_state: int, reward, choose_action, step):
        if before_state not in self.action_q.keys() or before_action_idx not in self.action_q[before_state].keys():
            return False
        if after_state not in self.action_q.keys() and after_state < 9000:
            self.init_action_q(after_state, step)
        if after_state < 9000:
            _, _, max_q_of_after = self.get_max_q_action(after_state)
        else:
            max_q_of_after = -9999
        before_score = self.action_q[before_state][before_action_idx]

        self.action_q[before_state][before_action_idx] = self.action_q[before_state][before_action_idx] + self.lr * (
                reward + self.gamma * max_q_of_after - self.action_q[before_state][before_action_idx])
        after_score = self.action_q[before_state][before_action_idx]
        logging.info("before_score: " + str(before_score) + ", after score: " + str(after_score))

        if choose_action is not None:
            if choose_action['type'] == 'fill_info':
                state = self.state_info.states[before_state]
                name2action = state.get_state_detail()

                indexes = name2action.get(choose_action['refer_name'], None)
                if indexes is not None:
                    if len(indexes) == 2:
                        click_index = before_action_idx - 1
                        self.action_q[before_state][click_index] = self.action_q[before_state][
                                                                       click_index] + self.lr * (
                                                                           reward + self.gamma * max_q_of_after -
                                                                           self.action_q[before_state][click_index])

            for state, components in self.action_count.items():
                if state == -1:
                    continue

                repeated_actions = [comp for comp, count in components.items() if count > 1]

                if repeated_actions:
                    for i in repeated_actions:
                        if i == -1:
                            continue
                        if i > len(repeated_actions) or len(repeated_actions) >= 0.5 * max(list(components.keys())):
                            if state == before_state and i == before_action_idx:
                                self.action_q[state][i] -= 1

            loops = self.find_first_loop_exceeding_threshold()
            # 输出结果
            if loops:
                for loop, count, first_pos in loops:
                    if len(self.action_loop) == 0:
                        self.action_loop.append(loop)
                    bi = {item.split('###')[0]: item.split('###')[1] for item in loop}
                    action_loop_list = []
                    for action_loop_i in self.action_loop:
                        ai = {item.split('###')[0]: item.split('###')[1] for item in action_loop_i}
                        action_loop_list.append(ai)
                    if loop not in self.action_loop and bi not in action_loop_list:
                        self.action_loop.append(loop)

                    loop_action = loop[0]
                    parts = loop_action.split('###')
                    before_hash = int(parts[0])  # '#' 前的元素
                    after_hash = int(parts[1])

                    if before_hash == before_state and after_hash == before_action_idx and loop in self.action_loop:
                        self.action_q[before_state][before_action_idx] -= 0.5

        return True

    def find_first_loop_exceeding_threshold(self, threshold=3):
        n = len(self.action_history)
        loop_dict = {}

        for i in range(n):
            for length in range(1, (n - i) // 2 + 1):  # 子序列长度
                sub_seq = self.action_history[i:i + length]
                repeat_count = 0
                j = i
                while j + length <= n and self.action_history[j:j + length] == sub_seq:
                    repeat_count += 1
                    j += length

                if repeat_count > 1:
                    loop_str = tuple(sub_seq)
                    if loop_str not in loop_dict:
                        # 如果循环对首次出现，记录其位置和重复次数
                        loop_dict[loop_str] = {'count': repeat_count, 'first_pos': i}
                    else:
                        # 更新最大重复次数，但保留最先出现的位置
                        loop_dict[loop_str]['count'] = max(loop_dict[loop_str]['count'], repeat_count)

        # 筛选重复次数超过阈值的循环对，并按首次出现位置排序
        loops_exceeding_threshold = [
            (list(loop), info['count'], info['first_pos'])
            for loop, info in loop_dict.items()
            if info['count'] > threshold
        ]
        loops_exceeding_threshold.sort(key=lambda x: x[2])  # 按首次出现位置排序

        return loops_exceeding_threshold

    def init_action_q(self, state_id: int, step: int):
        available_actions = self.state_info.get_available_actions(state_id)
        cur_action_q = {}
        for action_id in available_actions:
            query_info = {}
            query_info.setdefault("state_id", state_id)
            query_info.setdefault("action_id", action_id)
            action = self.state_info.get_state_action(state_id, action_id)
            query_info.setdefault("action", action)
            action_refer_name = action["refer_name"]
            init_score = self.scorer.get_view_score(query_info, available_actions, step)
            logging.info("init score [" + str(state_id) + ":" + str(action_id) + "] :" + action_refer_name + " " + str(
                init_score))
            cur_action_q.setdefault(action_id, init_score)
        self.action_q.setdefault(state_id, cur_action_q)

        self.visit_actions.setdefault(state_id, set())

    def choose_action(self, state_id: int):
        random_flag = random.random()
        action_prob = self.recoder.get_action_prob(self.multi_flag)

        if action_prob < 0:
            return -1, None
        elif random_flag < action_prob:

            # choose unvisited action
            unvisited_actions = self.recoder.get_unvisited_actions(state_id)
            if len(unvisited_actions) > 0:
                choose_idx = random.choice(list(unvisited_actions))
                choose_action = self.state_info.get_state_action(state_id, choose_idx)
            else:
                # all action has visited, still choose max q action
                choose_idx, choose_action, _ = self.get_max_q_action(state_id)
        else:
            choose_idx, choose_action, _ = self.get_max_q_action(state_id)
        self.visit_actions[state_id].add(choose_idx)
        return choose_idx, choose_action

    def get_max_q_action(self, state_id: int):
        sort_action_q = sorted(self.action_q[state_id].items(), key=lambda d: d[1], reverse=True)

        # return sort_action_q[0][0], sort_action_q[0][1]
        for i in range(len(sort_action_q)):
            choose_idx = sort_action_q[i][0]
            choose_action = self.state_info.get_state_action(state_id, choose_idx)
            if choose_action["type"] == "system_back":
                return choose_idx, choose_action, sort_action_q[0][1]
            else:
                if sort_action_q[i][1] > 2:
                    return choose_idx, choose_action, sort_action_q[i][1]
                choose_flag1 = len(sort_action_q) < 5
                choose_flag2 = (len(sort_action_q) >= 5 and not self.recoder.check_action_in_recent(state_id, choose_idx)) or (len(sort_action_q) >= 5 and self.recoder.check_action_in_recent(state_id, choose_idx) and state_id < 2)
                if choose_flag1 or choose_flag2:
                    return choose_idx, choose_action, sort_action_q[0][1]
        choose_idx = sort_action_q[0][0]
        return choose_idx, self.state_info.get_state_action(state_id, choose_idx), sort_action_q[0][1]

    def punish_action_to_stuck(self, choose_action, step):
        logging.info("begin punish action to stuck" + str(self.recoder.stuck_states))
        for stuck_state in self.recoder.stuck_states:
            logging.info("stuck state: " + str(stuck_state))
            action_to_state = self.state_info.get_action_to_state(stuck_state)
            for src_state, actions in action_to_state.items():
                for a_id in actions:
                    logging.info("punish to state " + str(stuck_state) + ": " + str(src_state) + "/" + str(a_id))
                    update_res = self.update_action_q(src_state, a_id, stuck_state, -4, choose_action, step)
        self.recoder.stuck_states.clear()


if __name__ == '__main__':
    # print(1)
    print(sorted([3, 5, 1, 4, 2], key=lambda x: -x))
