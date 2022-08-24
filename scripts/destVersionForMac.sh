#!/usr/bin/env bash

set -eo pipefail

temp_path="WeChatMac/temp"
latest_path="WeChatMac/latest"

download_link="$1"
if [ -z "$1" ]; then
    >&2 echo -e "Missing argument. Using default download link"
    download_link="https://dldir1.qq.com/weixin/mac/WeChatMac.dmg"
fi

function install_depends() {
    printf "#%.0s" {1..60}
    echo 
    echo -e "## \033[1;33mInstalling 7zip, shasum, wget, curl, git\033[0m"
    printf "#%.0s" {1..60}
    echo 

    apt install -y p7zip-full p7zip-rar libdigest-sha-perl wget curl git python3 python3-pip
    pip install lxml request
}

function login_gh() {
    printf "#%.0s" {1..60}
    echo 
    echo -e "## \033[1;33mLogin to github to use github-cli...\033[0m"
    printf "#%.0s" {1..60}
    echo 
    if [ -z $GHTOKEN ]; then
        >&2 echo -e "\033[1;31mMissing Github Token! Please get a BotToken from 'Github Settings->Developer settings->Personal access tokens' and set it in Repo Secrect\033[0m"
        exit 1
    fi

    echo $GHTOKEN > WeChatMac/temp/GHTOKEN
    gh auth login --with-token < WeChatMac/temp/GHTOKEN
    if [ "$?" -ne 0 ]; then
        >&2 echo -e "\033[1;31mLogin Failed, please check your network or token!\033[0m"
        clean_data 1
    fi
    rm -rfv WeChatMac/temp/GHTOKEN
}

function download_wechat() {
    printf "#%.0s" {1..60}
    echo 
    echo -e "## \033[1;33mDownloading the newest WeChatMac...\033[0m"
    printf "#%.0s" {1..60}
    echo 

    wget -q "$download_link" -O ${temp_path}/WeChatMac.dmg
    if [ "$?" -ne 0 ]; then
        >&2 echo -e "\033[1;31mDownload Failed, please check your network!\033[0m"
        clean_data 1
    fi
}

function get_version() {
    dest_version=`python3 scripts/getVersion.py`
}


# rename and replace
function prepare_commit() {
    printf "#%.0s" {1..60}
    echo 
    echo -e "## \033[1;33mPrepare to commit new version\033[0m"
    printf "#%.0s" {1..60}
    echo 

    mkdir -p WeChatMac/$dest_version
    cp $temp_path/WeChatMac.dmg WeChatMac/$dest_version/WeChatMac-$dest_version.dmg
    echo "DestVersion: $dest_version" > WeChatMac/$dest_version/WeChatMac-$dest_version.dmg.sha256
    echo "Sha256: $now_sum256" >> WeChatMac/$dest_version/WeChatMac-$dest_version.dmg.sha256
    echo "UpdateTime: $(date -u '+%Y-%m-%d %H:%M:%S') (UTC)" >> WeChatMac/$dest_version/WeChatMac-$dest_version.dmg.sha256
    echo "DownloadFrom: $download_link" >> WeChatMac/$dest_version/WeChatMac-$dest_version.dmg.sha256
    
}

function clean_data() {
    printf "#%.0s" {1..60}
    echo 
    echo -e "## \033[1;33mClean runtime and exit...\033[0m"
    printf "#%.0s" {1..60}
    echo 

    rm -rfv WeChatMac/*
    exit $1
}

function main() {
    # rm -rfv WeChatSetup/*
    mkdir -p ${temp_path}/temp
    # login_gh
    ## https://github.com/actions/virtual-environments/blob/main/images/linux/Ubuntu2004-Readme.md
    # install_depends
    download_wechat

    now_sum256=`shasum -a 256 ${temp_path}/WeChatMac.dmg | awk '{print $1}'`
    local latest_sum256=`gh release view  --json body --jq ".body" | awk '/Sha256/{ print $2 }'`
    local latest_version=`gh release view  --json body --jq ".body" | awk '/DestVersion/{ print $2 }'`
    if [ "$now_sum256" = "$latest_sum256" ]; then
        >&2 echo -e "\n\033[1;32mThis is the newest Version!\033[0m\n"
        clean_data 0
    fi
    ## if not the newest
    get_version
    prepare_commit
    # if dest_version is the same as latest_version
    if [ "$dest_version" = "$latest_version" ]; then
        version="$dest_version"_`date -u '+%Y%m%d'`
        echo -e $dest_version
    else
        version="$dest_version"
    fi
    
    gh release create v$version ./WeChatMac/$dest_version/WeChatMac-$dest_version.dmg -F ./WeChatMac/$dest_version/WeChatMac-$dest_version.dmg.sha256 -t "Wechat For Mac v$version"

    # gh auth logout --hostname github.com | echo "y"

    clean_data 0
}

main

