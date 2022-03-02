import base64
import io
import os
import os.path
import tempfile
import time
import subprocess
from subprocess import Popen
from PIL import Image
from connectors.core.connector import get_logger, ConnectorError
from integrations.crudhub import make_request, make_file_upload_request

logger = get_logger('web-screenshot')


def create_file(file_name, file_content, file_type):
    try:
        response = make_file_upload_request(file_name, file_content, file_type)
        logger.info(f"File upload complete {str(response)}")
        return response
    except Exception as e:
        logger.exception("An exception occurred {0}".format(e))
        raise ConnectorError("{0}".format(e))


def create_attachment(file_resp, desc):
    try:
        file_id = file_resp.get("@id")
        file_name = file_resp.get("filename")
        response = make_request('/api/3/attachments', 'POST',
                                {'name': file_name, 'file': file_id, 'description': desc})
        logger.info(f"File attachment complete {str(response)}")
        return response
    except Exception as e:
        logger.exception("An exception occurred {0}".format(e))
        raise ConnectorError("{0}".format(e))


def take_screenshot(config, params):
    binary = config.get("path").strip()
    url = params.get("url").strip()
    if not url.startswith('http'):
        url = f"http://{url}"
    width = config.get("width")
    height = config.get("height")
    t_width = config.get("t_width")
    t_height = config.get("t_height")
    tmp_name = f"{next(tempfile._get_candidate_names())}.png"
    tmp_path = f"/tmp/{tmp_name}"
    if "chrome" not in binary.lower():
        raise ConnectorError("Unable to find chrome binary")

    cmd_parameter = ["--ignore-certificate-errors",
                     # "--no-sandbox",
                     "--incognito",
                     "--disable-gpu",
                     "--allow-running-insecure-content",
                     "--disable-web-security",
                     "--headless",
                     "--virtual-time-budget=10000",
                     f"--window-size={width},{height}",
                     f"--screenshot=\'{tmp_path}\'",
                     f"\'{url}\'"]
    cmd_parameter = " ".join(cmd_parameter)
    try:
        proc = Popen(f"{binary} {cmd_parameter}", shell=True)
        try:
            proc.communicate(timeout=1000)
        except subprocess.TimeoutExpired as e:
            proc.kill()
            raise ConnectorError("Process exited with timeout.{0}".format(e))
        except subprocess.SubprocessError as e:
            raise ConnectorError("Process exited with non-zero value.{0}".format(e))

        with open(tmp_path, mode='rb') as file:
            tmp_content = file.read()
        file_object = create_file(tmp_name, tmp_content, "png")
        tmp_image = Image.open(io.BytesIO(tmp_content))
        tmp_image_resize = tmp_image.resize((t_width, t_height))  # x, y
        buffer = io.BytesIO()
        tmp_image_resize.save(buffer, format="PNG")
        tmp_image_resize_base64 = base64.b64encode(buffer.getvalue())
        tmp_image_resize_base64 = tmp_image_resize_base64.decode('utf-8')
        desc = f"<img src=\"data:image/png;base64, {tmp_image_resize_base64}\" width=\"{t_width}\" height=\"{t_height}\"> <br>|Screenshot for {url} at {time.strftime('%m/%d/%Y %H:%M:%S', time.localtime())}"
        attachment_object = create_attachment(file_object, desc)
    except Exception as e:
        logger.exception("An exception occurred {0}".format(e))
        raise ConnectorError("{0}".format(e))
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)
    return attachment_object


def _check_health(config):
    binary = config.get("path").strip()
    if not os.path.exists(binary):
        raise ConnectorError("Invalid Chrome path {0}".format(binary))


operations = {
    'take_screenshot': take_screenshot
}
