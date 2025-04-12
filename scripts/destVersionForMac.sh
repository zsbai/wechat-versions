#!/usr/bin/env bash

set -eo pipefail

# ====================================================
# 配置变量
# ====================================================
TEMP_PATH="WeChatMac/temp"
WEBSITE_URL="https://mac.weixin.qq.com/?t=mac&lang=zh_CN"
DOWNLOAD_LINK=""

# ====================================================
# 函数定义
# ====================================================

# 打印分隔线
print_separator() {
    printf '%*s\n' 60 | tr ' ' '#'
}

# 彩色输出函数
echo_color() {
    local color="$1"
    shift
    local message="$*"
    case "$color" in
        yellow)
            echo -e "\033[1;33m$message\033[0m"
            ;;
        red)
            echo -e "\033[1;31m$message\033[0m" >&2
            ;;
        green)
            echo -e "\033[1;32m$message\033[0m"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# 安装依赖项
install_depends() {
    print_separator
    echo_color "yellow" "Installing dependencies: 7zip, wget, curl, git, gh, dmg2img, shasum, pup"
    print_separator

    sudo apt update
    sudo apt install -y p7zip-full p7zip-rar libdigest-sha-perl wget curl git gh dmg2img

    curl -LO  https://github.com/ericchiang/pup/releases/download/v0.4.0/pup_v0.4.0_linux_amd64.zip
	unzip pup_v0.4.0_linux_amd64.zip
    sudo mv pup /usr/local/bin/
}

# 下载 WeChat DMG
download_wechat() {
    DOWNLOAD_LINK=$(curl -s "$WEBSITE_URL" | pup 'a.download-button:nth-of-type(1) attr{href}')
    
    print_separator
    echo_color "yellow" "Downloading the newest WeChatMac..."
    print_separator

    mkdir -p "$TEMP_PATH"

    wget -q "$DOWNLOAD_LINK" -O "${TEMP_PATH}/WeChatMac.dmg"
    if [ "$?" -ne 0 ]; then
        echo_color "red" "Download Failed, please check your network!"
        clean_data 1
    fi
}

# 从 Info.plist 提取版本信息
get_version() {
    print_separator
    echo_color "yellow" "Extracting version from Info.plist..."
    print_separator

    # 使用 dmg2img 将 DMG 转换为 IMG
    dmg2img "${TEMP_PATH}/WeChatMac.dmg" "${TEMP_PATH}/WeChatMac.img"

    set +e
    # 使用 7z x 解压 IMG 文件，保留目录结构
    7z x "${TEMP_PATH}/WeChatMac.img" -o"${TEMP_PATH}" >/dev/null
    exit_code=$?

    # 检查退出代码，忽略退出代码 2
    if [ $exit_code -ne 0 ] && [ $exit_code -ne 2 ]; then
        echo_color "red" "Failed to extract DMG file!"
        clean_data 1
    else
        echo_color "green" "Extraction completed successfully, ignoring warnings."
    fi

    if [ $exit_code -eq 2 ]; then
        echo_color "yellow" "Warning: Exit code 2 ignored."
        exit 0
    fi
    set -e

    # 查找 Info.plist
    INFO_PLIST=$(find "${TEMP_PATH}" -type f -name "Info.plist" | head -n 1)
    # INFO_PLIST=${TEMP_PATH}/微信\ WeChat/WeChat.app/Contents/Info.plist

    if [ -z "$INFO_PLIST" ] || [ ! -f "$INFO_PLIST" ]; then
        echo_color "red" "Info.plist not found in the IMG!"
        clean_data 1
    fi

    # 使用 grep 和 sed 提取版本号
    VERSION=$(grep -A1 '<key>CFBundleShortVersionString</key>' "$INFO_PLIST" | grep '<string>' | sed -E 's/.*<string>([^<]+)<\/string>.*/\1/')

    if [ -z "$VERSION" ]; then
        VERSION=$(grep -A1 '<key>CFBundleVersion</key>' "$INFO_PLIST" | grep '<string>' | sed -E 's/.*<string>([^<]+)<\/string>.*/\1/')
    fi

    if [ -z "$VERSION" ]; then
        echo_color "red" "Version information not found in Info.plist!"
        clean_data 1
    fi

    echo "Version: $VERSION"
}

# 计算 SHA256
compute_sha256() {
    local file_path="$1"
    shasum -a 256 "$file_path" | awk '{print $1}'
}

# 准备提交（复制 DMG 并创建 .sha256 文件）
prepare_commit() {
    print_separator
    echo_color "yellow" "Preparing to commit new version..."
    print_separator

    VERSION_DIR="WeChatMac/$VERSION"
    mkdir -p "$VERSION_DIR"

    cp "${TEMP_PATH}/WeChatMac.dmg" "$VERSION_DIR/WeChatMac-$VERSION.dmg"

    NOW_SUM256=$(compute_sha256 "$VERSION_DIR/WeChatMac-$VERSION.dmg")

    cat > "$VERSION_DIR/WeChatMac-$VERSION.dmg.sha256" <<EOF
DestVersion: $VERSION
Sha256: $NOW_SUM256
UpdateTime: $(date -u '+%Y-%m-%d %H:%M:%S') (UTC)
DownloadFrom: $DOWNLOAD_LINK
EOF

    echo "SHA256: $NOW_SUM256"
}

# 获取最新的 GitHub Release 信息
get_latest_release_info() {
    print_separator
    echo_color "yellow" "Getting latest GitHub release info..."
    print_separator

    LATEST_BODY=$(gh release view --json body --jq ".body" || true)

    if [ -z "$LATEST_BODY" ]; then
        LATEST_SUM256=""
        LATEST_VERSION=""
    else
        LATEST_SUM256=$(echo "$LATEST_BODY" | grep 'Sha256:' | awk -F': ' '{print $2}')
        LATEST_VERSION=$(echo "$LATEST_BODY" | grep 'DestVersion:' | awk -F': ' '{print $2}')
    fi

    echo "Latest Version: $LATEST_VERSION"
    echo "Latest SHA256: $LATEST_SUM256"
}

# 创建新的 GitHub Release
create_release() {
    print_separator
    echo_color "yellow" "Creating new GitHub release..."
    print_separator

    if [ "$VERSION" = "$LATEST_VERSION" ]; then
        VERSION_TAG="${VERSION}_$(date -u '+%Y%m%d')"
    else
        VERSION_TAG="$VERSION"
    fi

    gh release create "v$VERSION_TAG" "WeChatMac/$VERSION/WeChatMac-$VERSION.dmg" -F "WeChatMac/$VERSION/WeChatMac-$VERSION.dmg.sha256" -t "Wechat For Mac v$VERSION_TAG"
}

# 清理临时数据并退出
clean_data() {
    print_separator
    echo_color "yellow" "Cleaning runtime and exiting..."
    print_separator

    rm -rf "WeChatMac"
    exit "$1"
}

# ====================================================
# 主流程
# ====================================================
main() {
    # 创建临时目录
    mkdir -p "$TEMP_PATH"

    # 安装依赖项
    install_depends

    # 下载 WeChat DMG
    download_wechat

    # 提取版本信息
    get_version

    # 准备提交（复制 DMG 并创建 .sha256 文件）
    prepare_commit

    # 获取最新的 GitHub Release 信息
    get_latest_release_info

    # 比较 SHA256 值
    if [ "$NOW_SUM256" = "$LATEST_SUM256" ] && [ -n "$LATEST_SUM256" ]; then
        echo_color "green" "This is the newest Version!"
        clean_data 0
    fi

    # 创建新的 GitHub Release
    create_release

    # 清理临时数据并退出
    clean_data 0
}

# 执行主流程
main
