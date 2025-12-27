## 用vps保活 serv00 & ct8
文件名：sb00_alive.sh

## 重要说明

- 脚本用途：用vps保活 serv00 & ct8，支持多个服务器批量操作，仅支持安装我修改过的四合一无交互脚本，不支持带交互的脚本

- 也可以支持安装老王原版的四合一无交互脚本，但是需要自己修改代码。因为我的代码里没有TUIC协议，而增加了socks5协议

- 本人修改的 [四合一无交互脚本地址](https://github.com/yutian81/Keepalive/blob/main/vps_sb5in1.sh)

- 必须将你所有的serv00服务器的ssh地址、用户名、密码以及四合一无交互脚本所需的外部变量（如端口等）存入到一个可直链下载的 json 文件，json 内容模板见下文

## 脚本原理

- 使用vps每5分钟检查一次serv00服务器（已安装好四合一）上vmess端口、argo隧道、哪吒探针，判断是否可连通

- 如果其中一项不可连通，则间隔 10 秒重新检查一次

- 连续5次均有某一项不可连通，则远程登录serv00的SSH，并读取 json 文件内的参数，重新安装四合一无交互脚本

-----

## 如何使用

### 一、将serv00的登录信息和无交互脚本的外部变量保存在json数组中

**注意:务必将 json 文件存入私库或其他支持直链的云盘，避免信息泄露。git私库文件可用CM的私库项目获取可访问的直链**

json 格式如下，注意最后一组`{}`后面没有`,`：

```
[
  { 
    "HOST": "panel3.serv00.com",
    "SSH_USER": "用户名",
    "SSH_PASS": "密码",
    "VMESS_PORT": "tcp端口1",
    "SOCKS_PORT": "tcp端口2",
    "HY2_PORT": "udp端口",
    "SOCKS_USER": "socks用户名",
    "SOCKS_PASS": "socks密码",
    "ARGO_DOMAIN": "argo域名",
    "ARGO_AUTH": "argo的token",
    "NEZHA_SERVER": "哪吒域名或ip",
    "NEZHA_PORT": "哪吒通信端口",
    "NEZHA_KEY": "哪吒密钥"
  },
  { 
    "HOST": "s4.serv00.com",
    "SSH_USER": "用户名",
    "SSH_PASS": "密码",
    "VMESS_PORT": "tcp端口1",
    "SOCKS_PORT": "tcp端口2",
    "HY2_PORT": "udp端口",
    "SOCKS_USER": "socks用户名",
    "SOCKS_PASS": "socks密码",
    "ARGO_DOMAIN": "argo域名",
    "ARGO_AUTH": "argo的token",
    "NEZHA_SERVER": "哪吒域名或ip",
    "NEZHA_PORT": "哪吒通信端口",
    "NEZHA_KEY": "哪吒密钥"
  },
  { 
    "HOST": "s5.serv00.com",
    "SSH_USER": "用户名",
    "SSH_PASS": "密码",
    "VMESS_PORT": "tcp端口1",
    "SOCKS_PORT": "tcp端口2",
    "HY2_PORT": "udp端口",
    "SOCKS_USER": "socks用户名",
    "SOCKS_PASS": "socks密码",
    "ARGO_DOMAIN": "argo域名",
    "ARGO_AUTH": "argo的token",
    "NEZHA_SERVER": "哪吒域名或ip",
    "NEZHA_PORT": "哪吒通信端口",
    "NEZHA_KEY": "哪吒密钥"
  }
]
```

**获取这个json文件的直链地址，例如：**
```
https://raw.githubusercontent.com/yutian81/serv00/main/alive/sb00ssh.json
```

### 二、修改脚本的全局变量
> [!IMPORTANT]  
> **必须将变量修改为你自己的信息，变量内容中的前后的`""`不要删除**
> 
> **以下变量必须修改，未列出的变量不要动**

| 变量 | 举例 | 说明 | 
| ---- | ---- | ---- | 
| VPS_JSON_URL | `https://raw.githubusercontent.com/yutian81/serv00/main/alive/sb00ssh.json` | 第一步中的json直链地址 |
| NEZHA_URL | `https://nezha.yutian.best` | 你的哪吒面板地址，必须带 `http(s)://` 前缀 |
| NEZHA_APITOKEN | xxxxxxroskZcpdxxxiBxkhxxxxxJevL1 | 你的哪吒面板的 `API TOKEN` |
| NEZHA_AGENT_ID | ("13" "14" "17" "23" "24" "26" "27") | 你的哪吒探针的`ID`号，只改数字，不要删除`()`和`""` |

### 三、在vps中运行本脚本

```
curl -s https://raw.githubusercontent.com/yutian81/serv00-ct8-ssh/main/vps_sb00_alive/sb00_alive.sh -o sb00_alive.sh && bash sb00_alive.sh
```
> 把其中的`https://raw.githubusercontent.com/yutian81/serv00-ct8-ssh/main/vps_sb00_alive/sb00_alive.sh`脚本地址改为你自己的`脚本直链地址`

**运行截图**

![运行截图](https://github.com/user-attachments/assets/94668e6c-30de-41e4-aae1-928bd585615c)
