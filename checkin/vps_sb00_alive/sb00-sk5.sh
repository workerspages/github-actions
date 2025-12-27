#!/bin/bash
# 此为四协议无交互一键安装脚本，去掉tuic协议，增加sk5协议
# 原作者为老王：https://github.com/eooce/Sing-box

re="\033[0m"
red="\033[1;91m"
green="\e[1;32m"
yellow="\e[1;33m"
purple="\e[1;35m"
red() { echo -e "\e[1;91m$1\033[0m"; }
green() { echo -e "\e[1;32m$1\033[0m"; }
yellow() { echo -e "\e[1;33m$1\033[0m"; }
purple() { echo -e "\e[1;35m$1\033[0m"; }
reading() { read -p "$(red "$1")" "$2"; }

USERNAME=$(whoami)
HOSTNAME=$(hostname)

export LC_ALL=C
export UUID=${UUID:-'bc97f674-c578-4940-9234-0a1da46041b9'}
export VMESS_PORT=${VMESS_PORT:-'40000'}
export SOCKS_PORT=${SOCKS_PORT:-'50000'}
export HY2_PORT=${HY2_PORT:-'60000'}
export SOCKS_USER=${SOCKS_USER:-'abc123'}
export SOCKS_PASS=${SOCKS_PASS:-'abc456'}
export ARGO_DOMAIN=${ARGO_DOMAIN:-''}   
export ARGO_AUTH=${ARGO_AUTH:-''}
export NEZHA_SERVER=${NEZHA_SERVER:-''} 
export NEZHA_PORT=${NEZHA_PORT:-'5555'}     
export NEZHA_KEY=${NEZHA_KEY:-''} 
export CFIP=${CFIP:-'www.visa.com.tw'} 
export CFPORT=${CFPORT:-'443'} 

[[ "$HOSTNAME" == "s1.ct8.pl" ]] && WORKDIR="domains/${USERNAME}.ct8.pl/logs" || WORKDIR="domains/${USERNAME}.serv00.net/logs"
[ -d "$WORKDIR" ] || (mkdir -p "$WORKDIR" && chmod 777 "$WORKDIR")
ps aux | grep $(whoami) | grep -v "sshd\|bash\|grep" | awk '{print $2}' | xargs -r kill -9 > /dev/null 2>&1

argo_configure() {
clear
purple "正在安装中,请稍等..."
  if [[ -z $ARGO_AUTH || -z $ARGO_DOMAIN ]]; then
    green "ARGO_DOMAIN or ARGO_AUTH is empty,use quick tunnel"
    return
  fi

  if [[ $ARGO_AUTH =~ TunnelSecret ]]; then
    echo $ARGO_AUTH > tunnel.json
    cat > tunnel.yml << EOF
tunnel: $(cut -d\" -f12 <<< "$ARGO_AUTH")
credentials-file: tunnel.json
protocol: http2

ingress:
  - hostname: $ARGO_DOMAIN
    service: http://localhost:$VMESS_PORT
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
  else
    green "ARGO_AUTH mismatch TunnelSecret,use token connect to tunnel"
  fi
}

generate_config() {

    openssl ecparam -genkey -name prime256v1 -out "private.key"
    openssl req -new -x509 -days 3650 -key "private.key" -out "cert.pem" -subj "/CN=$USERNAME.serv00.net"

  cat > config.json << EOF
{
  "log": {
    "disabled": true,
    "level": "info",
    "timestamp": true
  },
  "dns": {
    "servers": [
      {
        "tag": "google",
        "address": "tls://8.8.8.8",
        "strategy": "ipv4_only",
        "detour": "direct"
      }
    ],
    "rules": [
      {
        "rule_set": [
          "geosite-openai"
        ],
        "server": "wireguard"
      },
      {
        "rule_set": [
          "geosite-netflix"
        ],
        "server": "wireguard"
      },
      {
        "rule_set": [
          "geosite-category-ads-all"
        ],
        "server": "block"
      }
    ],
    "final": "google",
    "strategy": "",
    "disable_cache": false,
    "disable_expire": false
  },
    "inbounds": [
    {
       "tag": "hysteria-in",
       "type": "hysteria2",
       "listen": "::",
       "listen_port": $HY2_PORT,
       "users": [
         {
             "password": "$UUID"
         }
     ],
     "masquerade": "https://bing.com",
     "tls": {
         "enabled": true,
         "alpn": [
             "h3"
         ],
         "certificate_path": "cert.pem",
         "key_path": "private.key"
        }
    },
    {
      "tag": "vmess-ws-in",
      "type": "vmess",
      "listen": "::",
      "listen_port": $VMESS_PORT,
      "users": [
      {
        "uuid": "$UUID"
      }
    ],
    "transport": {
      "type": "ws",
      "path": "/vmess",
      "early_data_header_name": "Sec-WebSocket-Protocol"
      }
    },
    {
      "tag": "socks-in",
      "type": "socks",
      "listen": "::",
      "listen_port": $SOCKS_PORT,
      "users": [
        {
          "username": "$SOCKS_USER",
          "password": "$SOCKS_PASS"
        }
      ]
    }

 ],
    "outbounds": [
    {
      "type": "direct",
      "tag": "direct"
    },
    {
      "type": "block",
      "tag": "block"
    },
    {
      "type": "dns",
      "tag": "dns-out"
    },
    {
      "type": "wireguard",
      "tag": "wireguard-out",
      "server": "162.159.195.100",
      "server_port": 4500,
      "local_address": [
        "172.16.0.2/32",
        "2606:4700:110:83c7:b31f:5858:b3a8:c6b1/128"
      ],
      "private_key": "mPZo+V9qlrMGCZ7+E6z2NI6NOV34PD++TpAR09PtCWI=",
      "peer_public_key": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
      "reserved": [
        26,
        21,
        228
      ]
    }
  ],
  "route": {
    "rules": [
      {
        "protocol": "dns",
        "outbound": "dns-out"
      },
      {
        "ip_is_private": true,
        "outbound": "direct"
      },
      {
        "rule_set": [
          "geosite-openai"
        ],
        "outbound": "wireguard-out"
      },
      {
        "rule_set": [
          "geosite-netflix"
        ],
        "outbound": "wireguard-out"
      },
      {
        "rule_set": [
          "geosite-category-ads-all"
        ],
        "outbound": "block"
      }
    ],
    "rule_set": [
      {
        "tag": "geosite-netflix",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-netflix.srs",
        "download_detour": "direct"
      },
      {
        "tag": "geosite-openai",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/sing/geo/geosite/openai.srs",
        "download_detour": "direct"
      },      
      {
        "tag": "geosite-category-ads-all",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-category-ads-all.srs",
        "download_detour": "direct"
      }
    ],
    "final": "direct"
   },
   "experimental": {
      "cache_file": {
      "path": "cache.db",
      "cache_id": "mycacheid",
      "store_fakeip": true
    }
  }
}
EOF
}

download_singbox() {
  ARCH=$(uname -m) && DOWNLOAD_DIR="." && mkdir -p "$DOWNLOAD_DIR" && FILE_INFO=()
  if [ "$ARCH" == "arm" ] || [ "$ARCH" == "arm64" ] || [ "$ARCH" == "aarch64" ]; then
      FILE_INFO=(
          "https://github.com/eooce/test/releases/download/arm64/sb web"
          "https://github.com/eooce/test/releases/download/arm64/bot13 bot"
          "https://github.com/eooce/test/releases/download/ARM/swith npm"
      )
  elif [ "$ARCH" == "amd64" ] || [ "$ARCH" == "x86_64" ] || [ "$ARCH" == "x86" ]; then
      FILE_INFO=(
          "https://github.com/eooce/test/releases/download/freebsd/sb web"
          "https://github.com/eooce/test/releases/download/freebsd/server bot"
          "https://github.com/eooce/test/releases/download/freebsd/npm npm"
      )
  else
      echo "不支持该系统架构: $ARCH"
      exit 1
  fi

download_with_fallback() {
    local URL=$1
    local FILENAME_DIR=$2
    local FILENAME=$3
    curl -L -sS --max-time 2 -o "$FILENAME" "$URL" &
    CURL_PID=$!
    CURL_START_SIZE=$(stat -c%s "$FILENAME" 2>/dev/null || echo 0)    
    sleep 1
    CURL_CURRENT_SIZE=$(stat -c%s "$FILENAME" 2>/dev/null || echo 0)
    
    if [ "$CURL_CURRENT_SIZE" -le "$CURL_START_SIZE" ]; then
        kill $CURL_PID 2>/dev/null
        wait $CURL_PID 2>/dev/null
        wget -q -O "$FILENAME" "$URL"
        echo -e "\e[1;32m正在使用 wget 下载 $FILENAME\e[0m"
    else
        wait $CURL_PID
        echo -e "\e[1;32m正在使用 curl 下载 $FILENAME\e[0m"
    fi
    chmod +x "$FILENAME"
}

for entry in "${FILE_INFO[@]}"; do
    URL=$(echo "$entry" | cut -d ' ' -f 1)
    FILENAME=$(echo "$entry" | cut -d ' ' -f 2)
    FILENAME_DIR=$DOWNLOAD_DIR/$FILENAME
    if [ -e "$FILENAME_DIR" ]; then
        echo -e "\e[1;32m$FILENAME_DIR 已经存在，跳过下载\e[0m"
    else
        download_with_fallback "$URL" "$FILENAME_DIR" "$FILENAME"
    fi
done
wait

if [ -e "$DOWNLOAD_DIR/npm" ]; then
    tlsPorts=("443" "8443" "2096" "2087" "2083" "2053")
    if [[ "${tlsPorts[*]}" =~ "${NEZHA_PORT}" ]]; then
      NEZHA_TLS="--tls"
    else
      NEZHA_TLS=""
    fi
    if [ -n "$NEZHA_SERVER" ] && [ -n "$NEZHA_PORT" ] && [ -n "$NEZHA_KEY" ]; then
        export TMPDIR=$(pwd)
        nohup ./"$DOWNLOAD_DIR/npm" -s ${NEZHA_SERVER}:${NEZHA_PORT} -p ${NEZHA_KEY} ${NEZHA_TLS} >/dev/null 2>&1 & 
        sleep 2
        pgrep -f "npm" > /dev/null && green "$DOWNLOAD_DIR/npm 正在运行" || { 
            red "$DOWNLOAD_DIR/npm 未运行，正在重启……"
            pkill -f "npm" && nohup ./"$DOWNLOAD_DIR/npm" -s "${NEZHA_SERVER}:${NEZHA_PORT}" -p "${NEZHA_KEY}" ${NEZHA_TLS} >/dev/null 2>&1 & 
            sleep 2
            purple "$DOWNLOAD_DIR/npm 已重启"
        }
    else
        purple "哪吒参数为空，跳过运行"
    fi
fi

if [ -e "$DOWNLOAD_DIR/web" ]; then
    nohup ./"$DOWNLOAD_DIR/web" run -c config.json >/dev/null 2>&1 &
    sleep 2
    pgrep -f "web" > /dev/null && green "$DOWNLOAD_DIR/web 正在运行" || { 
        red "$DOWNLOAD_DIR/web 未运行，正在重启……"
        pkill -f "web" && nohup ./"$DOWNLOAD_DIR/web" run -c config.json >/dev/null 2>&1 &
        sleep 2
        purple "$DOWNLOAD_DIR/web 已重启"
    }
fi

if [ -e "$DOWNLOAD_DIR/bot" ]; then
    if [[ $ARGO_AUTH =~ ^[A-Z0-9a-z=]{120,250}$ ]]; then
      args="tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token \"${ARGO_AUTH}\""
    elif [[ $ARGO_AUTH =~ TunnelSecret ]]; then
      args="tunnel --edge-ip-version auto --config tunnel.yml run"
    else
      args="tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile boot.log --loglevel info --url http://localhost:$VMESS_PORT"
    fi
    nohup ./"$DOWNLOAD_DIR/bot" $args >/dev/null 2>&1 &
    sleep 2
    pgrep -f "bot" > /dev/null && green "$DOWNLOAD_DIR/bot 正在运行" || { 
        red "$DOWNLOAD_DIR/bot 未运行，正在重启……"
        pkill -f "bot" && nohup ./"$DOWNLOAD_DIR/bot" "${args}" >/dev/null 2>&1 &
        sleep 2
        purple "$DOWNLOAD_DIR/bot 已重启"
    }
fi
sleep 5
# rm -f "$(basename ${FILE_MAP[npm]})" "$(basename ${FILE_MAP[web]})" "$(basename ${FILE_MAP[bot]})"
}

get_argodomain() {
  if [[ -n $ARGO_AUTH ]]; then
    echo "$ARGO_DOMAIN"
  else
    grep -oE 'https://[[:alnum:]+\.-]+\.trycloudflare\.com' boot.log | sed 's@https://@@'
  fi
}

get_ip() {
  ip=$(curl -s --max-time 2 ipv4.ip.sb)
  if [ -z "$ip" ]; then
    ip=$( [[ "$HOSTNAME" =~ s[0-9]\.serv00\.com ]] && echo "${HOSTNAME/s/web}" || echo "$HOSTNAME" )
  else
    url="https://www.toolsdaquan.com/toolapi/public/ipchecking/$ip/443"
    response=$(curl -s --location --max-time 3.5 --request GET "$url" --header 'Referer: https://www.toolsdaquan.com/ipcheck')
    if [ -z "$response" ] || ! echo "$response" | grep -q '"icmp":"success"'; then
        accessible=false
    else
        accessible=true
    fi
    if [ "$accessible" = false ]; then
        ip=$( [[ "$HOSTNAME" =~ s[0-9]\.serv00\.com ]] && echo "${HOSTNAME/s/web}" || echo "$ip" )
    fi
  fi
  echo "$ip"
}

get_links(){
argodomain=$(get_argodomain)
echo -e "\e[1;32mArgoDomain:\e[1;35m${argodomain}\e[0m\n"
sleep 1
IP=$(get_ip)
ISP=$(curl -s https://speed.cloudflare.com/meta | awk -F\" '{print $26"-"$18}' | sed -e 's/ /_/g') 
sleep 1
yellow "注意：v2ray或其他软件的跳过证书验证需设置为true,否则hy2或tuic节点可能不通\n"
cat > list.txt <<EOF
vmess://$(echo "{ \"v\": \"2\", \"ps\": \"$ISP\", \"add\": \"$IP\", \"port\": \"$VMESS_PORT\", \"id\": \"$UUID\", \"aid\": \"0\", \"scy\": \"none\", \"net\": \"ws\", \"type\": \"none\", \"host\": \"\", \"path\": \"/vmess?ed=2048\", \"tls\": \"\", \"sni\": \"\", \"alpn\": \"\", \"fp\": \"\"}" | base64 -w0)

vmess://$(echo "{ \"v\": \"2\", \"ps\": \"$ISP\", \"add\": \"$CFIP\", \"port\": \"$CFPORT\", \"id\": \"$UUID\", \"aid\": \"0\", \"scy\": \"none\", \"net\": \"ws\", \"type\": \"none\", \"host\": \"$argodomain\", \"path\": \"/vmess?ed=2048\", \"tls\": \"tls\", \"sni\": \"$argodomain\", \"alpn\": \"\", \"fp\": \"\"}" | base64 -w0)

hysteria2://$UUID@$IP:$HY2_PORT/?sni=www.bing.com&alpn=h3&insecure=1#$ISP

socks5://$SOCKS_USER:$SOCKS_PASS@$IP:$SOCKS_PORT
EOF
cat list.txt
purple "\n$WORKDIR/list.txt saved successfully"
purple "Running done!"
yellow "Serv00|ct8老王sing-box一键四协议安装脚本(vmess-ws|vmess-ws-tls(argo)|hysteria2|tuic)\n"
echo -e "${green}issues反馈：${re}${yellow}https://github.com/eooce/Sing-box/issues${re}\n"
echo -e "${green}反馈论坛：${re}${yellow}https://bbs.vps8.me${re}\n"
echo -e "${green}TG反馈群组：${re}${yellow}https://t.me/vps888${re}\n"
purple "转载请著名出处，请勿滥用\n"
sleep 3 
rm -rf boot.log config.json sb.log core tunnel.yml tunnel.json fake_useragent_0.2.0.json
}

install_singbox() {
    clear
    cd $WORKDIR
    argo_configure
    generate_config
    download_singbox
    get_links
}
install_singbox
