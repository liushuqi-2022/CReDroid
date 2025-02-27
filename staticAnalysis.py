import os
import time

class StaticAnalysis(object):
    def __init__(self, apk_path, sdk_platform, iccBot_path, out_path):
        self.apk_path = apk_path
        self.iccBot_path = iccBot_path
        self.out_path = out_path
        if not os.path.exists(self.out_path):
            os.makedirs(self.out_path)
        self.sdk_platform = sdk_platform

    def analyzeIccCallGraph(self):
        icc_result = None
        apk_dir = os.path.dirname(self.apk_path)
        apk_name = os.path.basename(self.apk_path).split('.')[0]
        if self.apk_path[-4:] == ".apk":
            print("start static analyze: ", apk_name)

            cmd1 = 'java -jar ' + self.iccBot_path + ' -path ' + apk_dir + ' -name ' + os.path.basename(self.apk_path) + ' -androidJar ' + self.sdk_platform + ' -time 30 -maxPathNumber 100 -client CTGClient -outputDir ' + out_path
            os.system(cmd1)

        return icc_result


if __name__ == '__main__':

    apk_dir = r'E:\CReDroid\Data\AndroR2\apps'
    sdk_platform = r'D:\Android\Sdk\platforms'
    iccBot_path = r'E:\CReDroid\tool\ICCBot.jar'
    out_path = r'E:\CReDroid\Data\AndroR2\CTG'
    # time_log_file = r"E:\CReDroid\Data\AndroR2\CTG\CTG_time.txt"
    for apk_name in os.listdir(apk_dir):
        if apk_name.endswith(".apk"):
            apk_path = os.path.join(apk_dir, apk_name)
            staticAanlysis = StaticAnalysis(apk_path,
                                            sdk_platform=sdk_platform,
                                            iccBot_path=iccBot_path,
                                            out_path=out_path)
            print("Starting analysis: ", apk_name)
            # start_time = time.time()
            icc_result = staticAanlysis.analyzeIccCallGraph()
            # print("icc_result",icc_result)

            # 计算分析花费的时间
            # end_time = time.time()
            # analysis_time = end_time - start_time
            # 将分析结果和时间写入到文件
            # with open(time_log_file, "a") as log_file:
            #     log_file.write(f"APK: {apk_name}, Analysis Time: {analysis_time:.2f} seconds\n")



