import os

try:
    import ujson as json
except ImportError:
    import json

try:
    import uhashlib as hashlib
except ImportError:
    import hashlib

try:
    import ubinascii as binascii
except ImportError:
    import binascii


STATE_FILE = "ota_version.txt"
CHUNK_SIZE = 1024
BLOCK_SIZE = 64


def _get_config():
    try:
        import secrets
    except Exception:
        return None

    manifest_url = getattr(secrets, "OTA_MANIFEST_URL", "")
    hmac_key = getattr(secrets, "OTA_HMAC_KEY", "")
    device = getattr(secrets, "OTA_DEVICE", "")
    enabled = getattr(secrets, "OTA_ENABLED", True)
    token = getattr(secrets, "GITHUB_TOKEN", "")
    requires_token = getattr(secrets, "OTA_REQUIRES_TOKEN", False)
    allow_boot = getattr(secrets, "OTA_ALLOW_BOOT_UPDATE", False)

    if not enabled:
        print("OTA disabled: OTA_ENABLED is False")
        return None

    if not manifest_url or not hmac_key or not device:
        print("OTA disabled: missing OTA_MANIFEST_URL, OTA_HMAC_KEY, or OTA_DEVICE")
        return None

    if requires_token and not token:
        print("OTA disabled: private repository token is missing")
        return None

    return {
        "manifest_url": manifest_url,
        "hmac_key": hmac_key,
        "device": device,
        "token": token,
        "allow_boot": allow_boot,
    }


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode()


def _hex_digest(data):
    return binascii.hexlify(data).decode()


def _sha256(data):
    digest = hashlib.sha256()
    digest.update(data)
    return digest.digest()


def _hmac_sha256_hex(key, message):
    key = _to_bytes(key)
    message = _to_bytes(message)

    if len(key) > BLOCK_SIZE:
        key = _sha256(key)

    if len(key) < BLOCK_SIZE:
        key = key + b"\x00" * (BLOCK_SIZE - len(key))

    outer_key = bytes([byte ^ 0x5C for byte in key])
    inner_key = bytes([byte ^ 0x36 for byte in key])

    return _hex_digest(_sha256(outer_key + _sha256(inner_key + message)))


def _manifest_payload(manifest):
    lines = [str(manifest.get("version", "")), manifest.get("device", "")]
    for file_info in manifest.get("files", []):
        lines.append(
            "%s|%s|%s"
            % (
                file_info.get("path", ""),
                file_info.get("sha256", ""),
                file_info.get("url", ""),
            )
        )
    return "\n".join(lines)


def _decode_github_content_api(data):
    try:
        payload = json.loads(data.decode())
    except Exception:
        return data

    if payload.get("encoding") != "base64" or "content" not in payload:
        return data

    return binascii.a2b_base64(payload["content"])


def _request(url, token=""):
    try:
        import urequests as requests
    except ImportError:
        import requests

    headers = {"User-Agent": "GreenHouse-OTA"}
    if token:
        headers["Authorization"] = "Bearer " + token

    response = requests.get(url, headers=headers)
    try:
        status = getattr(response, "status_code", 200)
        if status != 200:
            raise RuntimeError("HTTP %s for %s" % (status, url))
        return _decode_github_content_api(response.content)
    finally:
        try:
            response.close()
        except Exception:
            pass


def _read_version():
    try:
        with open(STATE_FILE, "r") as file:
            return int(file.read().strip())
    except Exception:
        return 0


def _write_version(version):
    with open(STATE_FILE, "w") as file:
        file.write(str(version))


def get_current_version(default_version=0):
    try:
        default_version = int(default_version)
    except Exception:
        default_version = 0

    stored_version = _read_version()
    if stored_version > default_version:
        return stored_version
    return default_version


def _notify(callback, event, local_version=0, remote_version=0, path=""):
    if callback is None:
        return

    try:
        callback(event, local_version, remote_version, path)
    except Exception as exc:
        print("OTA_STATUS_CALLBACK_ERROR", repr(exc))


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _safe_path(path, allow_boot=False):
    if not path or path.startswith("/") or ":" in path or "\\" in path:
        return False
    if ".." in path.split("/"):
        return False
    if path == "boot.py" and not allow_boot:
        return False
    return True


def _ensure_parent_dir(path):
    parts = path.split("/")[:-1]
    current = ""
    for part in parts:
        current = part if not current else current + "/" + part
        try:
            os.mkdir(current)
        except OSError:
            pass


def _sha256_file_hex(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return _hex_digest(digest.digest())


def _stage_file(file_info, token):
    path = file_info["path"]
    tmp_path = path + ".new"
    _ensure_parent_dir(path)

    data = _request(file_info["url"], token)
    with open(tmp_path, "wb") as file:
        file.write(data)

    actual_hash = _sha256_file_hex(tmp_path)
    expected_hash = file_info["sha256"].lower()
    if actual_hash != expected_hash:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise RuntimeError("SHA256 mismatch for %s" % path)


def _install_file(file_info):
    path = file_info["path"]
    tmp_path = path + ".new"
    bak_path = path + ".bak"

    if _exists(bak_path):
        os.remove(bak_path)
    if _exists(path):
        os.rename(path, bak_path)
    os.rename(tmp_path, path)


def check_for_updates(current_version=0, status_callback=None):
    config = _get_config()
    if config is None:
        _notify(status_callback, "disabled")
        return False

    local_version = get_current_version(current_version)
    _notify(status_callback, "checking", local_version)

    manifest_bytes = _request(config["manifest_url"], config["token"])
    manifest = json.loads(manifest_bytes.decode())

    if manifest.get("device") != config["device"]:
        raise RuntimeError("OTA manifest device mismatch")

    expected_signature = manifest.get("signature", "").lower()
    actual_signature = _hmac_sha256_hex(
        config["hmac_key"], _manifest_payload(manifest)
    )
    if actual_signature != expected_signature:
        raise RuntimeError("OTA manifest signature mismatch")

    remote_version = int(manifest.get("version", 0))
    if remote_version <= local_version:
        print("OTA up to date: version", local_version)
        _notify(status_callback, "up_to_date", local_version, remote_version)
        return False

    files = manifest.get("files", [])
    if not files:
        raise RuntimeError("OTA manifest has no files")

    for file_info in files:
        path = file_info.get("path", "")
        if not _safe_path(path, config["allow_boot"]):
            raise RuntimeError("Unsafe OTA path: %s" % path)

    print("OTA update available:", local_version, "->", remote_version)
    _notify(status_callback, "update_available", local_version, remote_version)
    for file_info in files:
        _notify(
            status_callback,
            "downloading",
            local_version,
            remote_version,
            file_info.get("path", ""),
        )
        _stage_file(file_info, config["token"])

    for file_info in files:
        _notify(
            status_callback,
            "installing",
            local_version,
            remote_version,
            file_info.get("path", ""),
        )
        _install_file(file_info)

    _write_version(remote_version)
    print("OTA installed version", remote_version)
    _notify(status_callback, "installed", local_version, remote_version)

    import machine

    machine.reset()
    return True
