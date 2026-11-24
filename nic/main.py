import json
import os
import shutil
import subprocess
import sys

import requests

INS_BASE_URL = "http://172.21.0.1/instructions/"
JSON_BASE_URL = "http://172.21.57.147/script/config"
OEM_JSON_BASE_URL = "http://172.21.57.147/script/config/oem_json"
FW_BASE_URL = "http://172.21.57.147/script/config/FW/ECO"
SCRIPT_BASE_URL = "http://172.21.57.147/script/"
TTY1_PATH = "/dev/tty1"
LOG_PATH = "/root/update_process.log"
SET_CBURN_COMMAND_URL = "http://172.21.57.147/script/set_cburn_2024.sh"
SET_CMD_FW_UPDATE_URL = "http://172.21.57.147/script/set_cmd_fw_update.sh"

STAGE2_PATH = "/root/sysinfo/stage2.json"
STAGE1_PATH = "/root/sysinfo/stage1.json"
PROC_CMD_LINE_PATH = "/root/sysinfo/proc-cmdline.log"
AFTERBURNIN = "AFTERBURNIN"


GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def tty_print(msg, color=""):
    try:
        with open(TTY1_PATH, "w") as tty1:
            tty1.write("{}{}{}\n".format(color, msg, RESET))
            tty1.flush()
    except Exception:
        sys.stdout.write("{}\n".format(msg))
        sys.stdout.flush()


def clean_value(value):
    return str(value).replace("'", "").replace(" ", "")


def convert_ins_to_dict(mac):
    ins = {}
    ins_path = "ins-{}".format(mac)

    with open(ins_path, "r") as ins_file:
        for line in ins_file:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                ins[k] = v

    return ins


def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def get_mac(file_path):
    data = load_json(file_path)
    return data["SYS_DIR"].split("/")[-1]


def _get_cburn_ver(file_path):
    data = load_json(file_path)
    return data["CBIMG"]


def _get_ins_file(mac):
    ins_path = "ins-{}".format(mac)
    response = requests.get(INS_BASE_URL + ins_path)

    if response.status_code != 200:
        tty_print(
            "Instruction file not found. Please Start Testing or ReGen.",
            RED
        )
        sys.exit(1)

    with open(ins_path, "w") as ins_file:
        ins_file.write(response.text)

    tty_print("Downloaded {}".format(ins_path), GREEN)


def download_json_file(ins, URL, option, skip_json_chk=False):
    ins[option] = clean_value(ins[option])
    json_name = "{}.json".format(ins[option])

    response = requests.get("{}/{}".format(URL, json_name))

    if response.status_code != 200:
        if skip_json_chk:
            tty_print(
                "JSON file {} not found, skipped".format(json_name),
                GREEN
            )
            return None

        tty_print(
            "JSON file {} not found on server".format(json_name),
            RED
        )
        sys.exit(1)

    with open(json_name, "w") as json_file:
        json_file.write(response.text)

    tty_print("Downloaded {}".format(json_name), GREEN)

    return os.path.abspath(json_name)


def download_file(file_url, name):
    local_path = os.path.abspath(name)

    tty_print("Downloading: {}".format(file_url))

    r = requests.get(file_url, stream=True)
    r.raise_for_status()

    total_size = int(r.headers.get("content-length", 0))
    downloaded = 0

    with open(local_path, "wb") as file:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)
                downloaded += len(chunk)

                if total_size > 0:
                    percent = downloaded * 100 / total_size
                    tty_print(
                        "Progress: {:6.2f}% ({}/{})".format(
                            percent,
                            downloaded,
                            total_size
                        )
                    )

    tty_print("Download completed", GREEN)

    return local_path


def convert_to_unix_format(script_path):
    with open(script_path, "rb") as f:
        data = f.read()

    data = data.replace(b"\r\n", b"\n")

    with open(script_path, "wb") as f:
        f.write(data)


def _run_shell_script(script_path, fw_path=""):
    script_path = os.path.abspath(script_path)

    tty_print("Script: {}".format(script_path))

    if not os.path.exists(script_path):
        raise FileNotFoundError("Script not found: {}".format(script_path))

    convert_to_unix_format(script_path)
    subprocess.run(["chmod", "+x", script_path], check=True)

    if fw_path:
        fw_path = os.path.abspath(fw_path)
        tty_print("Firmware: {}".format(fw_path))

        if not os.path.exists(fw_path):
            raise FileNotFoundError(
                "Firmware file not found: {}".format(fw_path)
            )

        subprocess.run(["bash", script_path, fw_path], check=True)
    else:
        subprocess.run(["bash", script_path], check=True)


def get_mo_info(ins):
    dir_value = clean_value(ins["DIR"])
    dir_value_6u = dir_value.replace("6U", "6u")
    mo_path = dir_value_6u.split("/")[:2]
    return dir_value, dir_value_6u, mo_path


def build_logging_path(mo_path, description):
    if (
        len(mo_path) > 1
        and mo_path[1]
        and mo_path[1].lower().startswith("6u")
    ):
        return "{}/{}/{}".format(
            mo_path[0],
            mo_path[1],
            description
        )

    return "{}/{}".format(
        mo_path[0],
        description
    )


def run_set_cmd_fw_update(logging_path):
    download_file(SET_CMD_FW_UPDATE_URL, "set_cmd_fw_update.sh")
    cburn_ver = _get_cburn_ver(STAGE1_PATH)

    tty_print(
        "Calling setcmd: {} {}".format(
            logging_path,
            cburn_ver
        ),
        GREEN
    )

    cmd = """
        source ./set_cmd_fw_update.sh
        setcmd {} {}
    """.format(logging_path, cburn_ver)

    subprocess.run(["bash", "-c", cmd], check=True)


def run_set_cburn():
    download_file(SET_CBURN_COMMAND_URL, "set_cburn_2024.sh")
    cburn_ver = _get_cburn_ver(STAGE1_PATH)

    cmd = """
        source ./set_cburn_2024.sh
        setcmd cburn-{}
    """.format(cburn_ver)

    subprocess.run(["bash", "-c", cmd], check=True)
    subprocess.run(["ipmicfg", "-raw", "0x30", "0xd"], check=True)
    subprocess.run(["reboot"])


def copy_log_to_path(log_path):
    os.makedirs(log_path, exist_ok=True)

    if os.path.exists(LOG_PATH):
        shutil.copy(LOG_PATH, log_path)


def run_process(ins, json_file, mac):
    is_sub_description = False

    json_data = load_json(json_file)

    sub_mo_remove_6u = ""
    sub_mo = ""

    if ins.get("DIR"):
        ins["DIR"] = clean_value(ins["DIR"])
        parts = str(ins["DIR"]).split("/")

        if len(parts) > 1:
            is_ord = parts[1]

            if is_ord.startswith("6U"):
                sub_mo_remove_6u = is_ord.replace("6U", "")
                sub_mo = is_ord.replace("6U", "6u")
            elif is_ord.startswith("6u"):
                sub_mo_remove_6u = is_ord.replace("6u", "")
                sub_mo = is_ord

    global_setting = json_data["global_setting"]
    global_setting_description = global_setting["description"]
    global_setting_is_logging = global_setting["is_logging"]
    global_setting_is_cburn = global_setting["is_cburn"]

    for item in json_data.get("fw_update", []):
        tty_print("--------------------------------")
        tty_print(json.dumps(item, indent=4))
        tty_print("--------------------------------")

        fw_local_path = ""
        script_local_path = ""

        if "skip_mos" in item:
            skip_mos = item["skip_mos"]

            if sub_mo in skip_mos or sub_mo_remove_6u in skip_mos:
                tty_print("Skipped because MO matched skip_mos")
                continue

        if "is_after_burnin" in item:
            tty_print("Program is checking if AFTERBURNIN in proc-cmdline")
            with open(PROC_CMD_LINE_PATH, "r") as proc_file:
                if AFTERBURNIN not in proc_file.read():
                    tty_print("There is no AFTERBURNIN in proc-cmdline, skip running script")
                    continue

        if "ECO" in item and "fw_name" in item:
            fw_url = "{}/{}/{}".format(
                FW_BASE_URL,
                item["ECO"],
                item["fw_name"]
            )

            fw_local_path = download_file(
                fw_url,
                item["fw_name"]
            )

        if "script" in item:
            script_url = "{}/{}".format(
                SCRIPT_BASE_URL,
                item["script"]
            )

            script_local_path = download_file(
                script_url,
                item["script"]
            )

        if script_local_path:
            _run_shell_script(
                script_local_path,
                fw_local_path
            )
        else:
            tty_print("No script specified, skipping")

        if "sub_description" in item:
            _, _, sub_mo_path = get_mo_info(ins)

            logging_path = build_logging_path(
                sub_mo_path,
                item["sub_description"]
            )

            log_path = "/mnt/{}/update_process/{}".format(
                logging_path,
                mac
            )

            copy_log_to_path(log_path)
            run_set_cmd_fw_update(logging_path)

            is_sub_description = True

    if not is_sub_description:
        _, _, mo_path = get_mo_info(ins)

        logging_path = build_logging_path(
            mo_path,
            global_setting_description
        )

        mo_path_str = "/mnt/{}/update_process/{}".format(
            logging_path,
            mac
        )

        copy_log_to_path(mo_path_str)

        if global_setting_is_logging == "true":
            run_set_cmd_fw_update(logging_path)
            subprocess.run(["reboot"])

    else:
        if global_setting_is_logging == "true":
            subprocess.run(["reboot"])

    if global_setting_is_cburn == "true":
        run_set_cburn()


if __name__ == "__main__":
    mac = get_mac(STAGE2_PATH)
    _get_ins_file(mac)

    ins = convert_ins_to_dict(mac)

    oem_json_file = download_json_file(
        ins,
        OEM_JSON_BASE_URL,
        "SPN",
        skip_json_chk=True
    )

    if oem_json_file:
        run_process(ins, oem_json_file, mac)

    json_file = download_json_file(
        ins,
        JSON_BASE_URL,
        option="ORDNUM"
    )

    run_process(ins, json_file, mac)