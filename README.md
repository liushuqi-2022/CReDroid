# CReDroid

## 1. 运行前准备
* 安卓模拟器
* Windows
* [Appium 桌面客户端](https://github.com/appium/appium-desktop/releases/tag/v1.22.3-4)
* Python 3.9
* [Requirements](https://github.com/liushuqi-2022/CReDroid/blob/main/requirements.txt)

## 2. 运行CReDroid

2.1 运行[`staticAnalysis.py`](https://github.com/liushuqi-2022/CReDroid/blob/main/staticAnalysis.py)使用［`ICCBot`](https://github.com/liushuqi-2022/CReDroid/blob/main/tool/ICCBot.jar)工具构建应用组件转换图（CTG）, 其中apk_dir为app目录, sdk_platform为安卓Sdk的安装目录, iccBot_path为工具ICCBot目录, out_path为输出目录

2.2 启动安卓模拟器和`Appium Desktop Client`

2.3 获取标题的关键操作

* 本文使用微调后的GPT-3.5-turbo模型来获取标题中的关键操作。由于GPT-3.5-turbo不是免费的，我们不直接提供我们的账户（api_key）和微调后的模型。
微调所用数据集手稿采用后公开，您可参考官方文档使用我们的数据集在您的账户上对GPT-3.5-turbo模型进行微调，微调步骤如下：
  * 导出OpenAI API key并在环境变量中配置
  * 使用`Semantics`目录下的[`fine_tune.py`](https://github.com/liushuqi-2022/CReDroid/blob/main/Semantics/fine_tune.py)微调, 获取微调后的模型ft:gpt-3.5-turbo-0125:*****
  
* 不使用微调后的模型，代码仍可正常运行。
  * 由于deepseek获得较大的关注, 可通过def extract_actions使用deepseek来获取标题中的关键操作，需要在`Semantics`目录下的['get_title_action.py'](https://github.com/liushuqi-2022/CReDroid/blob/main/Semantics/get_title_action.py)配置Line 10的api_key
  
  
2.4 在`Main`目录下，有几个脚本来运行CReDroid：
* `run_andror2.py`：在['AndroR2'](https://github.com/liushuqi-2022/CReDroid/tree/main/Data/AndroR2)数据集的应用程序上运行CReDroid
* `run_recdroid.py`：在['ReCDroid'](https://github.com/liushuqi-2022/CReDroid/tree/main/Data/ReCDroid)数据集的应用程序上运行CReDroid
* `run_crashtranslator.py`：在['CrashTranslator'](https://github.com/liushuqi-2022/CReDroid/tree/main/Data/CrashTranslator)数据集的应用程序上运行CReDroid
* 要更改运行的应用程序，请修改`do_test(app_idx)`中的`app_idx`变量,并在`env`目录下的[`emulator.py`](https://github.com/liushuqi-2022/CReDroid/blob/main/env/emulator.py)的`def init_appium()`中修改对应的desired_caps



