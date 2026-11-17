"""이 PC가 노트북 SFTP 서버에서 파일을 받는 클라이언트다."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

CONFIG_PATH = Path(__file__).with_name("config") / "server.json"


def default_server_config() -> dict:
    """노트북 서버 주소와 이 PC에 받을 폴더의 기본값."""
    return {
        "host": "",
        "port": 22,
        "user": "",
        "key": "",
        "remote_path": "",
        "local_dir": str(Path.home() / "review-inbox"),
    }


def load_server_config() -> dict:
    """저장된 노트북 접속 정보를 읽는다. 비밀번호는 저장하지 않는다."""
    config = default_server_config()
    if not CONFIG_PATH.exists():
        return config
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    for key in ("host", "user", "key", "remote_path", "local_dir"):
        if isinstance(loaded.get(key), str):
            config[key] = loaded[key].strip()
    try:
        config["port"] = int(loaded.get("port", 22))
    except (TypeError, ValueError):
        config["port"] = 22
    return config


def save_server_config(config: dict) -> None:
    """접속 정보를 저장하고, 이 PC에서 받을 폴더를 만든다."""
    folder = Path(str(config["local_dir"]).strip())
    folder.mkdir(parents=True, exist_ok=True)
    stored = {
        "host": str(config["host"]).strip(),
        "port": int(config["port"]),
        "user": str(config["user"]).strip(),
        "key": str(config["key"]).strip(),
        "remote_path": str(config["remote_path"]).strip(),
        "local_dir": str(folder),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")


def ollama_version(url: str) -> str:
    """Ollama /api/version. 실패하면 빈 문자열."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/version", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return ""
    return str(payload.get("version") or "")


def _connect(config: dict, password: str) -> paramiko.SSHClient:
    """노트북 SSH 서버에 클라이언트로 붙는다."""
    host = str(config["host"]).strip()
    user = str(config["user"]).strip()
    if not host or not user:
        raise OSError("노트북 주소와 사용자가 필요합니다.")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": host,
        "port": int(config["port"]),
        "username": user,
        "timeout": 8,
        "banner_timeout": 8,
        "auth_timeout": 8,
        "allow_agent": True,
        "look_for_keys": True,
    }
    key_path = str(config.get("key") or "").strip()
    if key_path:
        kwargs["key_filename"] = key_path
        kwargs["look_for_keys"] = False
    if password:
        kwargs["password"] = password
    try:
        client.connect(**kwargs)
    except Exception:
        client.close()
        raise
    return client


def check_laptop_sftp(config: dict, password: str) -> tuple[bool, str]:
    """노트북 SFTP 서버에 붙고, 원격 파일이 있으면 그것까지 확인한다."""
    target = f"{config['user']}@{config['host']}:{config['port']}"
    if not str(config["host"]).strip() or not str(config["user"]).strip():
        return False, "노트북 주소와 사용자를 서버 설정에 저장하세요."
    try:
        client = _connect(config, password)
    except Exception as error:
        return False, f"{target} 접속 실패: {error}"
    remote_path = str(config.get("remote_path") or "").strip()
    try:
        sftp = client.open_sftp()
        try:
            if remote_path:
                sftp.stat(remote_path)
                return True, f"{target} · {remote_path}"
            sftp.listdir(".")
            return True, f"{target} 접속됨"
        finally:
            sftp.close()
    except Exception as error:
        return False, f"{target} 접속 실패: {error}"
    finally:
        client.close()


def download_remote_file(config: dict, password: str) -> Path:
    """노트북의 파일 하나를 이 PC 폴더로 받는다."""
    remote_path = str(config.get("remote_path") or "").strip().replace("\\", "/")
    if not remote_path:
        raise OSError("받을 원격 파일 경로가 없습니다.")
    folder = Path(str(config["local_dir"]).strip())
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / Path(remote_path).name
    client = _connect(config, password)
    try:
        sftp = client.open_sftp()
        try:
            sftp.get(remote_path, str(destination))
        finally:
            sftp.close()
    finally:
        client.close()
    return destination


def local_dir_state(folder: str) -> tuple[bool, str]:
    """받은 파일을 둘 폴더를 확인한다."""
    path = Path(folder)
    if not path.is_dir():
        return False, f"폴더 없음: {path}"
    probe = path / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False, f"폴더에 쓸 수 없음: {path}"
    return True, str(path)


def collect_server_status(ollama_url: str, config: dict, password: str) -> list[dict]:
    """Ollama, 노트북 SFTP, 이 PC의 받을 폴더 상태."""
    version = ollama_version(ollama_url)
    sftp_ok, sftp_detail = check_laptop_sftp(config, password)
    folder_ok, folder_detail = local_dir_state(str(config["local_dir"]))
    return [
        {
            "name": "Ollama",
            "ok": bool(version),
            "detail": f"{ollama_url} · {version}" if version else f"{ollama_url} 응답 없음",
        },
        {
            "name": "노트북 SFTP",
            "ok": sftp_ok,
            "detail": sftp_detail,
        },
        {
            "name": "받을 폴더",
            "ok": folder_ok,
            "detail": folder_detail,
        },
    ]


def tcp_reachable(host: str, port: int) -> bool:
    """상태 표시 전에 포트만 짧게 확인한다. 인증은 하지 않는다."""
    if not host.strip():
        return False
    try:
        with socket.create_connection((host.strip(), int(port)), timeout=1.5):
            return True
    except OSError:
        return False
