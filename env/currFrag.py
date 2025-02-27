import subprocess


class Fragment:
    def __init__(self, name, id):
        self.name = ""
        self.id = ""

def getcurfrag():
    frag = Fragment("","")
    cmd = "adb -s emulator-5554 shell dumpsys activity top"
    result = subprocess.check_output(cmd, shell=True).decode('utf8')

    split = result.split('\n')
    fragflag = 0
    flag = 0
    for line in range(0, len(split)):
        try:
            if "Local FragmentActivity " in split[line]:
                fragflag = 1
            if fragflag == 1 and "Added Fragments:" in split[line]:
                flag = 1
            if flag == 1 and fragflag == 1 and "#0:" in split[line]:
                try:
                    name = split[line].split('#' + str(0) + ": ")[1].split("{")[0]
                    id = split[line].split('id=')[1].split("}")[0]
                    frag.id = id
                    frag.name = name
                    print("frag.name",frag.name)
                    break
                except:
                    pass
        except:
            pass
    return frag


if __name__ == '__main__':
    frag = getcurfrag()