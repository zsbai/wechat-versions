import lxml
import lxml.etree
import requests


url = "https://mac.weixin.qq.com/?t=mac&lang=zh_CN"
header = {
    'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',

}
r = requests.get(url,headers=header).text
tree = lxml.etree.HTML(r)
version = tree.xpath("/html/body/div/div[2]/div/div[1]/a[1]/div/p[2]/text()[1]")
print(version[0])

