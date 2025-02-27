import re
from openai import OpenAI

def extract_actions(sentence, package_name):
    if sentence == '':
        return None, [], False

    sentence = re.sub(r'^(app\s+crash.*?)(?=\s+)', '', sentence, flags=re.IGNORECASE)
    multi_click = has_repeated_action_keywords(sentence)
    client = OpenAI(api_key="sk-**********", base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": f"The crash report summary is: {sentence}. Which words in the summary are likely to be related to the app UI elements?"},
        ],
        stream=False
    )

    items_in_bold = re.findall(r'\*\*(.*?)\*\*', response.choices[0].message.content)

    items_in_bold = [item.strip('"') if '"' in item else item for item in items_in_bold]

    lower_word = items_in_bold[0].replace(' ', '').lower()
    if lower_word in package_name:
        items_in_bold.pop(0)

    indices = []

    for word in items_in_bold:
        index = sentence.lower().find(word.lower())
        if index != -1:
            indices.append(index)

    if indices:
        start_index = min(indices)
        end_index = max(indices)
        result = sentence[start_index:end_index + len(items_in_bold[indices.index(end_index)])]
    else:
        result = None

    result = replace_symbols(result)
    items_in_bold = [replace_symbols(item) for item in items_in_bold]
     # "App crashes when I try to add Provisioner" -> result, items_in_bold, multi_click add Provisioner ['add', 'Provisioner'] False
    return result, items_in_bold, multi_click

# 定义替换函数
def replace_symbols(text):
    replace_dict = {
        "/": " or ",
        "&": " and "
    }

    for key, value in replace_dict.items():
        text = text.replace(key, value)
    return text

def has_repeated_action_keywords(text):
    """
    检查文本中是否包含表示重复操作的关键词。
    """
    # 常见的重复操作关键词列表
    repeated_action_keywords = [
        "multiple clicks", "fast multiple clicks", "double click", "double tap", "multi-tap",
        "rapid clicks", "fast clicks", "repeated clicks", "repeated taps", "frequent clicks",
        "frequent taps", "excessive clicks", "excessive tapping", "clicking too fast",
        "tapping too fast", "button spam", "spam click", "burst click", "burst tap",
        "user input flood", "input flood", "click storm", "tap storm", "button mash",
        "mash click", "rapid user input", "input overload", "over-click", "over-tap"
    ]

    # 检查是否包含任意关键词
    for keyword in repeated_action_keywords:
        if keyword.lower() in text.lower():
            return True
    return False

# extract_actions("App crashes when I try to add Provisioner", "no.nordicsemi.android.sdbviewer")

