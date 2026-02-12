# Wechat For Macos Version Archive
收集官网 Mac 微信版本并保存至release。

## 更新日志
* 2026.2.12：使用python重写脚本，移除冗余文件和代码。在`4.0.5`版本后，之前获取精确版本号的规则失效，目前已修复；未来如果继续出现无法获取精确版本号则会自动采用大版本+build的形式（如`v4.0.0+build.12345`）。

* 2024.10.1：通过转换dmg为img后解压，获取精确的微信版本号（例如：3.8.9.xx）；在此之前，后两位小版本号无法获取，所以通过添加更新日期后缀来区分大版本中的小版本，需在下载前自行判断。

项目使用 Github Action 每天自动检测微信**官网新版本更新**，计算 Hash/MD5 值并推送至仓库 Release。

项目仅抓取官网的Mac安装包，并不包含App Store中的版本。

各版本更新日志可参见官网 [changelog](https://weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_faq_list&head=true)

相关项目：
- [微信 Windows 64 位 3.0 版本存档](https://github.com/tom-snow/wechat-windows-versions)
- [微信 Windows 32 位 3.0 版本存档](https://github.com/tom-snow/wechat-windows-versions-x86)
- [微信 Mac 3.0 & 4.0 版本存档](https://github.com/zsbai/wechat-versions)


*如有问题/侵权，请直接提交 issue 告知。*
