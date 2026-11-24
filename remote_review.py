"""노트북에서 소스 하나를 보내고, cppcheck는 로컬, 모델 호출만 PC에서 한다."""

from __future__ import annotations

import argparse
import os
import socket
import threading
from pathlib import Path

import paramiko

from cli import BUG_LABELS
from hardware import hardware_profile, ollama_call_options
from report import save_reports
from reviewer import DEFAULT_MODEL, PREDICT_CHOICES, ReviewError, review_paths

EXAMPLE_CONFIG = Path(__file__).with_name("config") / "remote.example.yaml"


def load_remote_config(path: Path) -> dict[str, str]:
    """key: value 형식만 읽는다. 비밀번호는 파일에 두지 않는다."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _pipe(left, right) -> None:
    """소켓과 SSH 채널 사이를 한 방향으로 옮긴다."""
    try:
        while True:
            data = left.recv(65536)
            if not data:
                break
            right.sendall(data)
    except Exception:
        pass
    finally:
        for endpoint in (left, right):
            try:
                endpoint.close()
            except Exception:
                pass


class PcLink:
    """SFTP로 파일 하나를 올리고, PC의 Ollama 포트만 노트북으로 가져온다."""

    def __init__(self, host: str, port: int, user: str, key_path: str, password: str):
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 20,
            "allow_agent": True,
            "look_for_keys": True,
        }
        if key_path:
            connect_kwargs["key_filename"] = key_path
            connect_kwargs["look_for_keys"] = False
        if password:
            connect_kwargs["password"] = password
        self._client.connect(**connect_kwargs)
        self._stop = threading.Event()
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def upload(self, source: Path, remote_dir: str) -> str:
        """원격 폴더에 파일 하나만 넣는다."""
        remote_dir = remote_dir.replace("\\", "/").rstrip("/")
        remote_path = f"{remote_dir}/{source.name}"
        sftp = self._client.open_sftp()
        try:
            try:
                sftp.stat(remote_dir)
            except OSError:
                sftp.mkdir(remote_dir)
            sftp.put(str(source), remote_path)
        finally:
            sftp.close()
        return remote_path

    def open_ollama(self, local_port: int, remote_host: str, remote_port: int) -> None:
        """노트북의 local_port를 PC의 Ollama로 잇는다."""
        transport = self._client.get_transport()
        if transport is None:
            raise ReviewError("SSH 연결이 없습니다.")
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", local_port))
        server.listen(8)
        server.settimeout(0.5)
        self._server = server

        def accept_loop() -> None:
            while not self._stop.is_set():
                try:
                    client, address = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    channel = transport.open_channel(
                        "direct-tcpip",
                        (remote_host, remote_port),
                        address,
                    )
                except Exception:
                    client.close()
                    continue
                threading.Thread(target=_pipe, args=(client, channel), daemon=True).start()
                threading.Thread(target=_pipe, args=(channel, client), daemon=True).start()

        self._thread = threading.Thread(target=accept_loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._server is not None:
            self._server.close()
        self._client.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="소스 하나를 SFTP로 PC에 두고, cppcheck는 이 컴퓨터, 모델은 PC에서 돌립니다. 결과는 CSV입니다."
    )
    parser.add_argument("source", help="검토할 소스 파일 하나")
    parser.add_argument("--config", default="", help="config/remote.yaml 경로. 없으면 아래 옵션을 씁니다.")
    parser.add_argument("--host", default="", help="PC의 SSH 주소")
    parser.add_argument("--port", type=int, default=0, help="SSH 포트. 기본 22")
    parser.add_argument("--user", default="", help="SSH 사용자")
    parser.add_argument("--key", default="", help="개인키 파일. 비우면 ssh-agent 또는 SFTP_PASSWORD")
    parser.add_argument("--remote-dir", default="", help="PC에 파일을 넣을 폴더")
    parser.add_argument("--local-port", type=int, default=0, help="노트북에서 열 터널 포트. 기본 11435")
    parser.add_argument("--ollama-port", type=int, default=0, help="PC의 Ollama 포트. 기본 11434")
    parser.add_argument("--vram", default="8", choices=["lt1", "8", "20"], help="PC 그래픽 메모리")
    parser.add_argument("--ram", default="16", choices=["16", "32"], help="PC 메인 메모리")
    parser.add_argument("--std", default="c++03", choices=["c++03", "c++17"])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--num-predict", type=int, default=2048, choices=PREDICT_CHOICES)
    parser.add_argument("--note", default="이 소스의 메모리 버그와 초기화 버그를 찾아 주세요.")
    return parser


def _setting(args: argparse.Namespace, config: dict[str, str], name: str, flag: str, fallback: str = "") -> str:
    value = str(getattr(args, flag) or "").strip()
    if value and value != "0":
        return value
    return config.get(name, fallback).strip()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    source = Path(args.source)
    if not source.is_file():
        print(f"파일이 아닙니다: {source}")
        return 1
    config_path = Path(args.config) if args.config else Path(__file__).with_name("config") / "remote.yaml"
    config = load_remote_config(config_path)
    host = _setting(args, config, "host", "host")
    user = _setting(args, config, "user", "user")
    remote_dir = _setting(args, config, "remote_dir", "remote_dir")
    key_path = _setting(args, config, "key", "key")
    port = int(_setting(args, config, "port", "port", "22") or "22")
    local_port = int(_setting(args, config, "local_port", "local_port", "11435") or "11435")
    ollama_port = int(_setting(args, config, "ollama_port", "ollama_port", "11434") or "11434")
    if not host or not user or not remote_dir:
        print(f"host, user, remote_dir 가 필요합니다. 예시는 {EXAMPLE_CONFIG} 입니다.")
        return 1
    password = os.environ.get("SFTP_PASSWORD", "")
    profile = hardware_profile(args.vram, args.ram)
    options = ollama_call_options(args.vram, args.ram, args.num_predict, args.model)
    link = PcLink(host, port, user, key_path, password)
    try:
        remote_path = link.upload(source, remote_dir)
        print(f"SFTP 전송: {source.name} -> {remote_path}")
        link.open_ollama(local_port, "127.0.0.1", ollama_port)
        ollama_url = f"http://127.0.0.1:{local_port}"
        print(
            f"cppcheck는 이 컴퓨터, 모델은 PC {host} 의 Ollama. "
            f"num_ctx {options['num_ctx']} / {profile['note']}"
        )

        def on_progress(percent: float, label: str) -> None:
            print(f"[진행 {percent:.0f}%] {label}")

        result = review_paths(
            [source],
            args.note,
            model=args.model,
            standard=args.std,
            num_ctx=int(options["num_ctx"]),
            num_gpu=options.get("num_gpu"),
            num_batch=int(options.get("num_batch", 512)),
            on_progress=on_progress,
            ollama_url=ollama_url,
            deepseek_model="",
            llama_model=args.model,
            num_predict=int(options["num_predict"]),
        )
    except (ReviewError, OSError, paramiko.SSHException, socket.error) as error:
        print(error)
        return 1
    finally:
        link.close()
    _markdown_path, csv_path = save_reports(result["findings"], BUG_LABELS)
    print(f"CSV: {csv_path}")
    if result["rejected"]:
        print(result["reject_reason"] or "메모리 버그와 초기화 버그 검토만 처리합니다.")
    elif not result["findings"]:
        print("보고할 메모리 버그와 초기화 버그가 없습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
