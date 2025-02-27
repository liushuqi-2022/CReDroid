import re

class Scorer:
    def __init__(self, trace_info: dict):
        self.interest_words = ["new", "create", "add", "agree", "preference", "option", "next", "start", "study", "ok",
                               "setting", "attach", "enter", "show", "open"]
        self.interest_words = set(self.interest_words)
        self.trace_info = trace_info
        self.trace_tokens = trace_info["trace_tokens"]
        self.trace_eles = trace_info["trace_eles"]
        self.trace = trace_info["trace"]

    def split_to_tokens(self, in_str: str):
        new_str = re.sub(r'([a-z])([A-Z])', r'\1 \2', in_str).lower()
        new_str = re.sub("[^a-z]", " ", new_str).strip()
        new_str = re.sub("\s+", " ", new_str)
        tokens = new_str.split(" ")
        return tokens

    def get_view_score(self, action_info: dict):
        view_score = 0
        action = action_info["action"]
        refer_name = action["refer_name"]
        action_class = action["class"]
        action_type = action["type"]
        refer_name_tokens = self.split_to_tokens(refer_name)
        refer_name_tokens = set(refer_name_tokens)
        if refer_name == "system back":
            return -0.1
        if action_class == "EditText":
            return -0.1
        if action_type == "fill_info":
            view_score += 0.2
        if len(refer_name_tokens.intersection(self.trace_tokens)) > 0:
            view_score += 0.5
        elif len(refer_name_tokens.intersection(self.interest_words)) > 0:
            view_score += 0.2
        return view_score