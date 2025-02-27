from openai import OpenAI

client = OpenAI()

# Step 1: 上传文件, 获取FileObject, id='file-***'
response=client.files.create(
  file=open(r"E:\CReDroid\Semantics\data_train.jsonl", "rb"),
  purpose="fine-tune"
)

# Step 2: 输入上一步获取的file id,启动微调
# response = client.fine_tuning.jobs.create(
#   training_file="file-***",
#   model="gpt-3.5-turbo"
# )

# 可检索微调状态
# response = client.fine_tuning.jobs.retrieve("ftjob-***")

print("response",response)

