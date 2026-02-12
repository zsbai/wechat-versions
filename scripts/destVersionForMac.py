#!/usr/bin/env python3

import datetime
import hashlib
import html.parser
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WEBSITE_URL = "https://mac.weixin.qq.com/?t=mac&lang=zh_CN"
BASE_DIR = Path.cwd() / "WeChatMac"
TEMP_DIR = BASE_DIR / "temp"

class DownloadLinkParser(html.parser.HTMLParser):
    """
    从微信 Mac 官方网站的 HTML 中解析下载链接。
    """

    def __init__(self) -> None:
        super().__init__()
        self.link = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self.link:
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = attrs_dict.get("class", "").split()
        if "download-button" in classes:
            self.link = attrs_dict.get("href", "").strip()

def run(
    cmd: list[str], check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess:
    """
    运行子进程命令的辅助函数，默认捕获输出并检查返回码。

    Args:
        cmd (list[str]): 要执行的命令列表。
        check (bool, optional): 是否检查命令返回码。默认为 True。
        capture (bool, optional): 是否捕获命令输出。默认为 True。

    Returns:
        subprocess.CompletedProcess: 子进程执行结果。
    """
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )

def log(message: str) -> None:
    """
    打印日志信息并立即刷新输出缓冲区。

    Args:
        message (str): 要打印的日志信息。
    """
    print(message, flush=True)

def fetch_download_link() -> str:
    """
    从微信 Mac 官方网站获取最新的下载链接

        Raises:
            RuntimeError: 如果在网站上未找到下载链接

        Returns:
            str: 下载链接 URL
    """
    # Fetch HTML and extract the first download link on the page.
    with urllib.request.urlopen(WEBSITE_URL, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = DownloadLinkParser()
    parser.feed(html)
    if not parser.link:
        raise RuntimeError("Download link not found on website.")
    return parser.link

def fetch_head_metadata(url: str) -> dict[str, str]:
    """
    使用 HEAD 请求从直接文件链接读取元数据。
    Args:
        url (str): 文件的直接下载链接
    Returns:
        dict[str, str]: 从 HEAD 响应中提取的元数据字典，键为小写字符串，值为对应的响应头值
    """
    # Use HEAD request to read metadata from the direct file link.
    attempts = 2
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, timeout=30) as response:
                return {key.lower(): value.strip() for key, value in response.headers.items()}
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                log(f"HEAD request failed (attempt {attempt}). Waiting before retry...")
                time.sleep(10)
    if last_error:
        log(f"HEAD request failed after {attempts} attempts: {last_error}")
        return {}

def download_with_retry(url: str, dest: Path) -> None:
    """
    下载软件包

    Args:
        url (str): 文件的直接下载链接
        dest (Path): 目标文件路径
    """
    # Keep temp files under current working directory for debugging.
    dest.parent.mkdir(parents=True, exist_ok=True)
    attempts = 2
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            run(
                [
                    "wget",
                    "--quiet",
                    "--tries",
                    "5",
                    "--waitretry",
                    "5",
                    "--retry-connrefused",
                    "--timeout",
                    "30",
                    url,
                    "-O",
                    str(dest),
                ]
            )
            return
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                log(f"Download failed (attempt {attempt}). Waiting before retry...")
                time.sleep(10)
    if last_error:
        raise last_error

def mount_dmg(dmg_path: Path) -> str:
    """
    挂载目标 dmg 镜像到本地

    Args:
        dmg_path (Path): dmg 镜像文件路径

    Raises:
        RuntimeError: 如果挂载失败或未找到挂载点

    Returns:
        str: 挂载点路径
    """
    # Mount DMG and capture the mount point under /Volumes.
    result = run(["hdiutil", "attach", str(dmg_path), "-nobrowse"])
    matches = re.findall(r"(/Volumes/[^\n]+)", result.stdout)
    if not matches:
        raise RuntimeError("Failed to mount DMG.")
    return matches[-1].strip()

def detach_dmg(mount_dir: str) -> None:
    """
    解除挂载对应目录

    Args:
        mount_dir (str): 挂载点路径
    """
    run(["hdiutil", "detach", mount_dir], check=False)

def get_tag_from_plist(mount_dir: str) -> str:
    """
    解析 Info.plist 构建 Tag 标签

    如果 WeChatBundleVersion 存在则直接使用，否则使用 CFBundleShortVersionString 和 CFBundleVersion 组合的形式。

    Args:
        mount_dir (str): 挂载路径

    Raises:
        RuntimeError: 如果 Info.plist 文件未找到
        RuntimeError: 如果 CFBundleShortVersionString 未找到
        RuntimeError: 如果 CFBundleVersion 未找到

    Returns:
        str: 构建标签
    """
    # Info.plist lives inside the mounted WeChat.app bundle.
    info_plist = Path(mount_dir) / "WeChat.app" / "Contents" / "Info.plist"
    if not info_plist.exists():
        raise RuntimeError("Info.plist not found in mounted volume.")
    with info_plist.open("rb") as handle:
        data = plistlib.load(handle)
    short_version = str(data.get("CFBundleShortVersionString", "")).strip()
    build = str(data.get("CFBundleVersion", "")).strip()
    version = str(data.get("WeChatBundleVersion", "")).strip()

    if not short_version:
        raise RuntimeError("CFBundleShortVersionString not found.")
    if not build:
        raise RuntimeError("CFBundleVersion not found.")
    if version:
        tag = version
    else:
        tag = f"{short_version}+build.{build}"
    return tag

def compute_sha256(file_path: Path) -> str:
    """
    计算文件的 sha256

    Args:
        file_path (Path): 文件路径

    Returns:
        str: 文件的 sha256 值
    """
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def parse_release_body(body: str) -> dict[str, str]:
    """
    从 GitHub release 的 body 文本中解析出键值对信息，返回一个字典。

    Args:
        body (str): GitHub release 的 body 文本，预期包含多行 "Key: Value" 格式的内容。

    Returns:
        dict[str, str]: 从 body 中解析出的键值对字典.
    """
    info: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.lstrip("- ").strip()] = value.strip()
    return info

def get_latest_release_info() -> dict[str, str]:
    """
    获取最新 GitHub release 的信息，返回一个包含键值对的字典。

    Returns:
        dict[str, str]: 包含最新 release 信息的字典
    """
    result = run(
        ["gh", "release", "view", "--json", "body", "--jq", ".body"], check=False
    )
    if result.returncode != 0 or not result.stdout:
        return {}
    return parse_release_body(result.stdout)

def tag_exists(tag: str) -> bool:
    """
    检查指定的 Git 标签是否已经存在于远程仓库中。

    Args:
        tag (str): Git 标签名称

    Returns:
        bool: 指定的 Git 标签是否存在
    """
    result = run(["gh", "release", "view", tag, "--json", "tagName"], check=False)
    return result.returncode == 0

def build_release_notes(
    tag: str,
    download_link: str,
    remote_md5: str,
    sha256_sum: str,
    remote_size: str,
    remote_last_modified: str,
) -> str:
    """
    构建 Release 发布信息

    Args:
        tag (str): 构建版本号
        download_link (str): 下载链接
        remote_md5 (str): 远端md5的值
        sha256_sum (str): sha256的值
        remote_size (str): 文件大小
        remote_last_modified (str): 最后修改时间

    Returns:
        str: 最终的发布信息
    """
    lines = [
        "WeChat for Mac automatic release",
        "",
        "Download and integrity details are below.",
        "",
        "Release details",
        f"- DestVersion: {tag}",
        "",
        "Source and checksums",
        f"- DownloadFrom: {download_link}",
        f"- Md5: {remote_md5}",
        f"- Sha256: {sha256_sum}",
    ]
    if remote_size:
        lines.append(f"- ContentLength: {remote_size}")
    if remote_last_modified:
        lines.append(f"- LastModified: {remote_last_modified}")
    return "\n".join(lines) + "\n"

def write_sha_file(
    sha_file: Path,
    tag: str,
    download_link: str,
    sha256_sum: str,
    remote_md5: str,
    remote_size: str,
    remote_last_modified: str,
) -> None:
    """
    写入 SHA 文件

    Args:
        sha_file (Path): SHA 文件路径
        tag (str): 构建标签
        download_link (str): 下载链接
        sha256_sum (str): sha256的值
        remote_md5 (str): 远端md5的值
        remote_size (str): 文件大小
        remote_last_modified (str): 最后修改时间
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    lines = [
        f"DestVersion: {tag}",
        f"Md5: {remote_md5}",
        f"Sha256: {sha256_sum}",
    ]
    if remote_size:
        lines.append(f"ContentLength: {remote_size}")
    if remote_last_modified:
        lines.append(f"LastModified: {remote_last_modified}")
    lines.extend(
        [
            f"UpdateTime: {timestamp} (UTC)",
            f"DownloadFrom: {download_link}",
        ]
    )
    sha_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    mount_dir = ""
    try:
        force_release = os.environ.get("FORCE_RELEASE", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        log(f"Force release: {'true' if force_release else 'false'}")

        # Step 1: resolve download link from website.
        log("Resolving download link from website...")
        download_link = fetch_download_link()
        log(f"Download link: {download_link}")

        # Step 2: read metadata from HEAD response.
        log("Fetching HEAD metadata...")
        headers = fetch_head_metadata(download_link)
        remote_md5 = headers.get("x-cos-meta-md5", "")
        remote_size = headers.get("content-length", "")
        remote_last_modified = headers.get("last-modified", "")
        log(
            "HEAD metadata: "
            f"md5={remote_md5 or 'n/a'}, "
            f"size={remote_size or 'n/a'}, "
            f"last_modified={remote_last_modified or 'n/a'}"
        )

        # Step 3: compare with latest release by MD5 to avoid downloads.
        log("Fetching latest GitHub release info...")
        latest_info = get_latest_release_info()
        latest_md5 = latest_info.get("Md5", "")
        latest_sha256 = latest_info.get("Sha256", "")
        log(
            "Latest release: "
            f"md5={latest_md5 or 'n/a'}, "
            f"sha256={latest_sha256 or 'n/a'}"
        )

        if remote_md5 and latest_md5 and remote_md5 == latest_md5:
            if force_release:
                log("MD5 matches latest release, but force release is enabled.")
            else:
                log("No new version detected by MD5. Skipping download.")
                return 0

        # Step 4: download DMG with retry.
        log("Downloading DMG...")
        dmg_path = TEMP_DIR / "WeChatMac.dmg"
        download_with_retry(download_link, dmg_path)
        log(f"Downloaded DMG to {dmg_path}")

        # Step 5: mount DMG and read plist values.
        log("Mounting DMG and reading Info.plist...")
        mount_dir = mount_dmg(dmg_path)
        tag = get_tag_from_plist(mount_dir)
        detach_dmg(mount_dir)
        mount_dir = ""
        log(f"Detected tag: {tag}")

        # Step 6: prepare release assets in workspace.
        log("Preparing release assets...")
        version_dir = BASE_DIR / tag
        version_dir.mkdir(parents=True, exist_ok=True)
        final_dmg = version_dir / f"WeChatMac-{tag}.dmg"
        shutil.copy2(dmg_path, final_dmg)

        sha256_sum = compute_sha256(final_dmg)
        log(f"Computed SHA256: {sha256_sum}")
        sha_file = version_dir / f"WeChatMac-{tag}.dmg.sha256"
        write_sha_file(
            sha_file,
            tag,
            download_link,
            sha256_sum,
            remote_md5,
            remote_size,
            remote_last_modified,
        )

        if not latest_md5 and latest_sha256 and sha256_sum == latest_sha256:
            if force_release:
                log("SHA256 matches latest release, but force release is enabled.")
            else:
                log("No new version detected by SHA256. Skipping release.")
                return 0
        if not latest_md5:
            log("Latest release has no MD5, used SHA256 fallback check.")

        if tag_exists(tag):
            suffix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
            tag = f"{tag}_{suffix}"
        log(f"Release tag: {tag}")

        title = f"Wechat For Mac {tag}"
        notes_content = build_release_notes(
            tag,
            download_link,
            remote_md5,
            sha256_sum,
            remote_size,
            remote_last_modified,
        )
        notes_file = TEMP_DIR / "release_notes.txt"
        notes_file.write_text(notes_content, encoding="utf-8")
        log(f"Release notes written to {notes_file}")

        # Step 7: publish release with assets and notes.
        log("Creating GitHub release...")
        run(
            [
                "gh",
                "release",
                "create",
                tag,
                str(final_dmg),
                str(sha_file),
                "-F",
                str(notes_file),
                "-t",
                title,
            ]
        )
        log("GitHub release created.")

        return 0
    finally:
        # Always detach and cleanup to keep workspace tidy.
        if mount_dir:
            detach_dmg(mount_dir)
        shutil.rmtree(BASE_DIR, ignore_errors=True)
        log("Cleanup completed.")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
