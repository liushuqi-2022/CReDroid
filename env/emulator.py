from appium import webdriver
from env.state_info import StateInfo
import time
from appium.webdriver.common.mobileby import MobileBy
from appium.webdriver.common.touch_action import TouchAction
import os
import re
import logging
from env.util import clean_resource_id, check_crash, get_input_content, check_crash_trigger
from env.parse_layout2 import get_edittexts_on_page
from Semantics.scorer import SimScorer
from selenium.webdriver.common.action_chains import ActionChains


class EmuRunner():
    def __init__(self, app_info: dict, state_info: StateInfo, state_size=100, action_size=50):
        self.app_package = app_info["app_pkg"]
        self.app_activity = app_info["app_acti"]
        self.input_cont = app_info["input_cont"]
        self.do_reset = app_info["reset"]
        # self.relaunch = app_info["relaunch"]
        self.trace_info = app_info["trace_info"]
        self.title_context = app_info["title_context"]
        self.state_info = state_info
        self.multi_click = app_info["multi_click"]
        self.tgt_actions = []
        self.init_appium(app_info)
        self.scorer = app_info["scorer"]
        self.ella_caller = app_info["ella_caller"]
        if "relaunch" not in app_info.keys():
            self.relaunch = False
        else:
            self.relaunch = app_info["relaunch"]

    def init_appium(self, app_info: dict):
        desired_caps = {}
        desired_caps['platformName'] = 'Android'
        desired_caps['platformVersion'] = '8.1'
        desired_caps['deviceName'] = '127.0.0.1:5554'
        desired_caps['appPackage'] = app_info["app_pkg"]
        desired_caps['appActivity'] = app_info["app_acti"]
        desired_caps['noReset'] = True
        # desired_caps['dontStopAppOnReset'] = "True"
        desired_caps['autoGrantPermissions'] = True
        desired_caps['newCommandTimeout'] = 6000
        desired_caps['automationName'] = 'UiAutomator2'
        desired_caps['settings[waitForIdleTimeout]'] = 100

        try:
            # 尝试初始化 Appium driver
            self.driver = webdriver.Remote('http://localhost:4723/wd/hub', desired_caps)
            logging.info("Appium driver initialized successfully.")
        except Exception as e:
            # 捕获异常并记录日志，不停止程序
            logging.error(f"Failed to initialize Appium driver: {e}")
            self.driver = None  # 设置 driver 为 None，表示初始化失败

    def step(self, action_id):
        # if action_id == -1:
        #     self.reset()
        before_state, _ = self.get_cur_state()
        if before_state > 9000:
            logging.info("try relaunch")

            try:
                self.relaunch()  # 尝试调用 relaunch 方法
            except Exception as e:
                # 捕获 TypeError 并打印相关信息，避免程序崩溃
                logging.error(f"Exception during relaunch: {e}")

            # 检查元素是否存在，如果存在则点击
            elements = self.driver.find_elements_by_xpath("//android.widget.TextView[@text='Open app again' or @text='OK' or @text='ALLOW']")
            if elements:
                elements[0].click()  # 点击第一个匹配的元素
            self.relaunch()

            before_state, _ = self.get_cur_state()
        # get target action
        tgt_action = self.state_info.get_state_action(before_state, action_id)
        logging.info("perform begin")
        # perform action
        self.perform_action(action_id, tgt_action)
        logging.info("perform done")

        if tgt_action is not None and len(self.has_common_words(tgt_action['refer_name'])) > 0 and self.multi_click:
            for _ in range(20):
                self.tgt_actions.append(tgt_action)
                self.tgt_actions.append({'refer_name': 'system back', 'is_scroll': False, 'xpath': '', 'type': 'system_back', 'content': '', 'class': 'system_back', 'bounds': [[175, 1785], [305, 1915]]})
        else:
            self.tgt_actions.append(tgt_action)
        # capture current state
        if tgt_action is not None and tgt_action['refer_name'].lower in ['allow', 'done']:
            time.sleep(2)
        after_state, state_type = self.get_cur_state()
        #         #   0: state already found
        #         #   1: state new find (activity already found)
        #         #   2: state new find (activity new find)
        logging.info("After state: " + str(after_state) + ", after type: " + str(state_type))
        #add transition information
        except_state = self.state_info.get_action_transition(before_state, action_id)
        if except_state is None or after_state != except_state:
            self.state_info.update_transition(before_state, action_id, after_state)
        # get current activity
        full_activity = self.get_full_activity()
        is_state_same = (after_state == before_state)
        # todo: reward function
        reward, done = self.scorer.get_state_score_heuristically(before_state, full_activity, state_type, tgt_action, is_state_same, self.tgt_actions)

        logging.info("reward: " + str(reward))
        logging.info("crash type: " + str(done))

        # todo: fill info (optional)
        info = {}
        return after_state, reward, done, info

    # gym method
    def reset(self, force_reset=False, force_restart=False):
        if self.driver.current_activity == "com.android.camera.CaptureActivity":
            self.system_back()
        if self.relaunch and not force_restart:
            self.relaunch_app()
        else:
            self.driver.close_app()
            if self.do_reset or force_reset:
                self.driver.reset()
            self.ella_caller.close_connection()
            self.driver.orientation = "PORTRAIT"
            self.driver.launch_app()
            self.driver.orientation = "PORTRAIT"

    def relaunch_app(self):
        print("### relaunch_app!!!!!")
        self.ella_caller.close_connection()
        launch_cmd = "adb -s emulator-5554 shell am start " + self.app_package + "/" + self.app_activity
        launch_p = os.popen(launch_cmd)
        launch_res = launch_p.read()
        time.sleep(1)

    def get_screen_info(self):
        temp_img_path = "../Data/Temp/cur_screen.png"
        # 检查是否有键盘弹出，如果有则先收起
        try:
            if self.driver.is_keyboard_shown():
                self.driver.hide_keyboard()
        except Exception as e:
            print(f"Error while hiding keyboard: {e}")

        try:
            self.driver.get_screenshot_as_file(temp_img_path)
        except Exception as e:
            print(e)
            f = open(temp_img_path, "w")
        temp_xml_path = "../Data/Temp/cur_screen.xml"

        try:
            screen_xml = None
            screen_xml = self.driver.page_source
            with open(temp_xml_path, "w", encoding="UTF-8") as f:
                f.write(screen_xml)
                f.close()
        except Exception as e:
            print(f"Failed to get page source: {e}")

        # activity .DeckPicker
        cur_screen_info = {"activity": self.driver.current_activity, "xml_path": temp_xml_path,
                           "img_path": temp_img_path, "package": self.driver.current_package, "page_source": screen_xml}

        return cur_screen_info


    def get_cur_state(self):
        screen_info = self.get_screen_info()
        return self.state_info.get_state_idx(screen_info)

    def perform_action(self, action_id, tgt_action: dict):

        if tgt_action is None:
            return False
        self.log_action(action_id, tgt_action)
        common_words = self.has_common_words(tgt_action['refer_name'])
        if len(common_words) > 0 and self.multi_click:
            self.click_until_crash_detected(tgt_action)
            self.system_back()
            return True
        if tgt_action["type"] == "click":
            return self.click_view_by_xpath(tgt_action["xpath"])
        elif tgt_action["type"] == "long_click":
            return self.long_click_view_by_xpath(tgt_action["xpath"])
        elif tgt_action["type"] == "input":
            try:
                # 尝试获取元素并执行操作
                element = self.driver.find_element_by_xpath(tgt_action["xpath"])
                element.send_keys(tgt_action["content"])
                return True
            except Exception as e:
                return False
        elif tgt_action["type"] == "system_back":
            self.system_back()
            # self.driver.press_keycode(4)
            return True
        elif tgt_action["type"] == "fill_info":
            return self.fill_and_confirm(tgt_action["xpath"])
        elif tgt_action["type"] == "system_rotate":
            return self.rotate_screen()
        else:
            logging.info("undefine action")
        return False

    def get_view_by_xpath(self, xpath: str):
        ele = self.driver.find_element(MobileBy.XPATH, xpath)
        return ele

    def has_common_words(self, str1):
        words1 = set(str1.lower().split())
        words2 = set(self.title_context.lower().split())
        common_words = words1.intersection(words2)
        return common_words

    def click_until_crash_detected(self, tgt_action, click_count=20, interval=0.5):
        if tgt_action["type"] == "click":
            for i in range(click_count):
                try:
                    ele = self.get_view_by_xpath(tgt_action["xpath"])
                    ele.click()
                    time.sleep(interval)

                except Exception as e:
                    print(e)
                    return False

            return True


    def check_if_crashed(self):
        crashed_page_element = self.driver.find_elements_by_xpath("//android.widget.TextView[@text='Open app again']")
        if crashed_page_element:
            return True
        return False

    def click_view_by_xpath(self, view_xpath: str):
        try:
            ele = self.get_view_by_xpath(view_xpath)
            ele.click()
            time.sleep(0.2)
            return True
        except Exception as e:
            print(e)
            return False

    def long_click_view_by_xpath(self, view_xpath: str):
        try:
            ele = self.get_view_by_xpath(view_xpath)
            TouchAction(self.driver).long_press(ele).perform()
            time.sleep(0.2)
            return True
        except Exception as e:
            print(e)
            return False

    def rotate_screen(self):
        try:
            self.driver.orientation = "LANDSCAPE"
            time.sleep(0.8)
            if check_crash():
                return
            self.driver.orientation = "PORTRAIT"
            time.sleep(0.8)
        except Exception as e:
            print(e)
            return

    def send_view_text(self, xpath, default_input="HelloWorld!"):
        try:
            ele = self.driver.find_element(MobileBy.XPATH, xpath)
        except Exception as e:
            print(xpath)
            print(e)
            return False
        ele_id = ele.get_attribute("resourceId")

        if ele_id == None or type(ele_id) != type("a"):
            ele_id = "none"
        else:
            ele_id = ele_id.split("/")[-1]

        ele_id = clean_resource_id(ele_id)
        default_cont = ele.text
        if ":" in default_cont and ele_id == "time":
            return True
        if "/" in default_cont and ele_id == "date":
            return True

        content = get_input_content(ele_id, default_cont, default_input, self.input_cont)

        is_password = "pass" in ele_id.split() or "password" in ele_id.split()
        is_search = "search" in ele_id.split()
        if "\'" in content or "\"" in content or " " in content:
            logging.info("use appium send key!")
            ele.send_keys(content)
        else:
            logging.info("use adb cmd!")
            ele.click()
            # move_cmd = "adb -s emulator-5554 shell input keyevent KEYCODE_MOVE_END"
            move_cmd = "adb shell input keyevent KEYCODE_MOVE_END"
            os.system(move_cmd)
            if not is_password:
                ori_content_len = len(ele.text) + 1
            else:
                ori_content_len = 20

            del_cmd = "adb shell input keyevent" + " KEYCODE_DEL" * ori_content_len
            os.system(del_cmd)

            input_cmd = "adb shell input text \"" + content + "\""
            os.system(input_cmd)
            time.sleep(0.2)
        if is_search:
            # enter_cmd = "adb -s emulator-5554 shell input keyevent KEYCODE_ENTER"
            enter_cmd = "adb shell input keyevent KEYCODE_ENTER"
            os.system(enter_cmd)

        if self.driver.is_keyboard_shown():
            self.driver.hide_keyboard()
            time.sleep(2)
        return True

    def log_action(self, action_id, action_info):

        logging.info("perform [" + str(action_id) + "] " + action_info["type"] + ": " + action_info[
            "refer_name"] + " (" + action_info["class"] + ", " + str(action_info["bounds"]) + ")")

    def get_full_activity(self):
        full_activity = self.app_package + "." + self.driver.current_activity
        full_activity = re.sub("\.+", ".", full_activity)
        return full_activity

    def system_back(self):
        before_state = self.get_cur_state()
        self.driver.press_keycode(4)
        time.sleep(0.2)
        after_state = self.get_cur_state()
        if after_state == before_state:
            logging.info("try back one more time!")
            self.driver.press_keycode(4)
            time.sleep(0.2)

    def fill_and_confirm(self, view_xpath, input_content="HelloWorld!"):
        try:
            screen_info = self.get_screen_info()
            edittext_xpaths = get_edittexts_on_page(screen_info["page_source"])
            for edittext_xpath in edittext_xpaths:
                self.send_view_text(edittext_xpath, input_content)
            ele = self.get_view_by_xpath(view_xpath)
            ele.click()
            time.sleep(2)
            return True
        except Exception as e:
            print(e)
            return False

