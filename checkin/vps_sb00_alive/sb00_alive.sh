#!/bin/bash

#老王原始vps保活脚本：https://github.com/eooce/Sing-box/blob/main/keep_00.sh
#yutian81修改vps保活脚本：https://github.com/yutian81/serv00-ct8-ssh/blob/main/vps_sb00_alive/sb00_alive.sh
#老王原始serv00四合一无交互脚本：https://github.com/eooce/Sing-box/blob/main/sb_00.sh
#yutian81修改serv00四合一无交互脚本：https://github.com/yutian81/serv00-ct8-ssh/blob/main/vps_sb00_alive/sb00-sk5.sh
#yutian81修改serv00四合一有交互脚本：https://github.com/yutian81/serv00-ct8-ssh/blob/main/sb_serv00_socks.sh
#yutian81无交互脚本执行命令的变量为 SCRIPT_URL；直接重启服务器原有进程的变量为 REBOOT_URL
#yutian81-vps保活serv00项目说明：https://github.com/yutian81/serv00-ct8-ssh/blob/main/vps_sb00_alive/README.md
#修改说明：yutian81的版本在老王原始四合一脚本基础上，去掉了 TUIC 协议，增加了 SOCKS5 协议

# 定义颜色
red() { echo -e "\e[1;91m$1\033[0m"; }
green() { echo -e "\e[1;32m$1\033[0m"; }
yellow() { echo -e "\e[1;33m$1\033[0m"; }

# 定义全局变量
SCRIPT_PATH="/root/sb00_alive.sh"  # 本脚本路径，不要改变文件名
#SCRIPT_URL="https://raw.githubusercontent.com/yutian81/serv00-ct8-ssh/main/vps_sb00_alive/sb00-sk5.sh"  # 四合一无交互yutian版，含socks5，无tuic
#SCRIPT_URL="https://raw.githubusercontent.com/eooce/Sing-box/refs/heads/main/sb_00.sh"  # 四合一无交互老王版，无socks5，含tuic
VPS_JSON_URL=""  # 储存vps登录信息及无交互脚本外部变量的json文件
REBOOT_URL="https://raw.githubusercontent.com/yutian81/serv00-ct8-ssh/main/reboot.sh"   # 仅支持重启yutian81修改serv00四合一有交互脚本
NEZHA_URL=""  # 哪吒面板地址，需要 http(s):// 前缀
NEZHA_APITOKEN=""  # 哪吒面板的 API TOKEN
NEZHA_API="$NEZHA_URL/api/v1/server/list"  # 获取哪吒探针列表的api接口，请勿修改
NEZHA_AGENT_ID=("2" "3" "4" "8" "9" "10" "11" "12")  # 从哪吒管理后台获取探针ID填入到此

# 外部传入参数
export TERM=xterm
export DEBIAN_FRONTEND=noninteractive

# 根据对应系统安装依赖
install_packages() {
    if [ -f /etc/debian_version ]; then
        package_manager="apt-get install -y"
        packages="sshpass curl netcat-openbsd cron jq"
    elif [ -f /etc/redhat-release ]; then
        package_manager="yum install -y"
        packages="sshpass curl netcat-openbsd cron jq"
    elif [ -f /etc/fedora-release ]; then
        package_manager="dnf install -y"
        packages="sshpass curl netcat-openbsd cron jq"
    elif [ -f /etc/alpine-release ]; then
        package_manager="apk add"
        packages="openssh curl netcat-openbsd cronie jq"
    else
        red "不支持的系统架构！"
        exit 1
    fi
    $package_manager $packages > /dev/null
}
install_packages

# 判断系统架构，添加对应的定时任务
add_cron_job() {
    local new_cron="*/5 * * * * /bin/bash $SCRIPT_PATH >> /root/00_keep.log 2>&1"
    local current_cron
    if crontab -l | grep -q "$SCRIPT_PATH" > /dev/null 2>&1; then
        red "定时任务已存在，跳过添加计划任务"
    else
        if [ -f /etc/debian_version ] || [ -f /etc/redhat-release ] || [ -f /etc/fedora-release ]; then
            (crontab -l; echo "$new_cron") | crontab -
        elif [ -f /etc/alpine-release ]; then
            if [ -f /var/spool/cron/crontabs/root ]; then
                current_cron=$(cat /var/spool/cron/crontabs/root)
            fi
            echo -e "$current_cron\n$new_cron" > /var/spool/cron/crontabs/root
            rc-service crond restart
        fi
        green "已添加定时任务，每5分钟执行一次"
    fi
}
add_cron_job

# 下载存储有服务器登录及无交互脚本外部变量信息的 JSON 文件
download_json() {
    if ! curl -s "$VPS_JSON_URL" -o sb00ssh.json; then
        red "Serv00 配置文件下载失败，尝试使用 wget 下载！"
        if ! wget -q "$VPS_JSON_URL" -O sb00ssh.json; then
            red "Serv00 配置文件下载失败，请检查下载地址是否正确！"
            exit 1
        else
            green "Serv00 配置文件通过 wget 下载成功！"
        fi
    else
        green "Serv00 配置文件通过 curl 下载成功！"
    fi
    # 检查文件是否存在和非空
    if [[ ! -s "sb00ssh.json" ]]; then
        red "配置文件 sb00ssh.json 不存在或为空"
        exit 1
    fi    
}
download_json

# 检测 TCP 端口
check_tcp_port() {
    local HOST=$1
    local VMESS_PORT=$2
    # 使用 nc 命令检测端口状态，返回0表示可用
    if nc -zv "$HOST" "$VMESS_PORT" &>/dev/null; then
        port_status=0  # 端口可用
    else
        port_status=1  # 端口不可用
    fi
}

# 检查 Argo 隧道状态
check_argo_status() {
    local ARGO_DOMAIN=$1
    argo_status=$(curl -o /dev/null -s -w "%{http_code}\n" "https://$ARGO_DOMAIN")
    echo "$argo_status"
}

# 获取哪吒探针列表
check_nezha_list() {
    agent_list=$(curl -s -H "Authorization: $NEZHA_APITOKEN" "$NEZHA_API")
    if [ $? -ne 0 ] || [[ -z "$agent_list" || "$agent_list" == "null" ]]; then
        red "获取哪吒探针列表失败，请检查 NEZHA_APITOKEN 和 NEZHA_URL 设置"
        exit 1
    fi
}

# 连接并执行远程命令的函数
run_remote_command() {
    local HOST=$1 SSH_USER=$2 SSH_PASS=$3 VMESS_PORT=$4 HY2_PORT=$5 SOCKS_PORT=$6 SOCKS_USER=$7 SOCKS_PASS=$8 ARGO_DOMAIN=$9 ARGO_AUTH=${10} NEZHA_SERVER=${11} NEZHA_PORT=${12} NEZHA_KEY=${13}
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no "$SSH_USER@$HOST" \
    "ps aux | grep \"$(whoami)\" | grep -v 'sshd\|bash\|grep' | awk '{print \$2}' | xargs -r kill -9 > /dev/null 2>&1 && \
    VMESS_PORT=$VMESS_PORT HY2_PORT=$HY2_PORT SOCKS_PORT=$SOCKS_PORT \
    SOCKS_USER=\"$SOCKS_USER\" SOCKS_PASS=\"$SOCKS_PASS\" \
    ARGO_DOMAIN=$ARGO_DOMAIN ARGO_AUTH=\"$ARGO_AUTH\" \
    NEZHA_SERVER=$NEZHA_SERVER NEZHA_PORT=$NEZHA_PORT NEZHA_KEY=$NEZHA_KEY \
    bash <(curl -Ls ${REBOOT_URL})" #使用此脚本无需重装节点，它将直接启动原本存储在服务器中进程和配置文件，实现节点重启，仅适用于yutian81修改serv00四合一有交互脚本
    # bash <(curl -Ls ${SCRIPT_URL}) #使用此脚本即自动安装无交互节点脚本
}

# 处理服务器列表并遍历，TCP端口、Argo、哪吒探针三项检测有一项不通即连接 SSH 执行命令
process_servers() { 
    jq -c '.[]' "sb00ssh.json" | while IFS= read -r servers; do
        HOST=$(echo "$servers" | jq -r '.HOST')
        SSH_USER=$(echo "$servers" | jq -r '.SSH_USER')
        SSH_PASS=$(echo "$servers" | jq -r '.SSH_PASS')
        VMESS_PORT=$(echo "$servers" | jq -r '.VMESS_PORT')
        SOCKS_PORT=$(echo "$servers" | jq -r '.SOCKS_PORT')
        HY2_PORT=$(echo "$servers" | jq -r '.HY2_PORT')
        SOCKS_USER=$(echo "$servers" | jq -r '.SOCKS_USER')
        SOCKS_PASS=$(echo "$servers" | jq -r '.SOCKS_PASS')
        ARGO_DOMAIN=$(echo "$servers" | jq -r '.ARGO_DOMAIN')
        ARGO_AUTH=$(echo "$servers" | jq -r '.ARGO_AUTH')
        NEZHA_SERVER=$(echo "$servers" | jq -r '.NEZHA_SERVER')
        NEZHA_PORT=$(echo "$servers" | jq -r '.NEZHA_PORT')
        NEZHA_KEY=$(echo "$servers" | jq -r '.NEZHA_KEY')
        yellow "正在检查服务器 $HOST 的 [Vmess端口]、[Argo隧道]、[哪吒探针] 是否可访问"

        local attempt=0
        local max_attempts=5  # 最大尝试检测次数
        local time=$(TZ="Asia/Hong_Kong" date +"%Y-%m-%d %H:%M")
        while [ $attempt -lt $max_attempts ]; do
            all_checks=true            

            # 检查 TCP 端口是否通畅，不通则 10 秒后重试
            check_tcp_port "$HOST" "$VMESS_PORT"
            if [ "$port_status" -ne 0 ]; then
                red "TCP 端口 $(yellow "$VMESS_PORT") 不可用！休眠 10 秒后重试"
                all_checks=false
                sleep 10
                attempt=$((attempt + 1))
                continue
            fi
            
            # 检查 Argo 连接是否通畅，不通则 10 秒后重试
            argo_status=$(check_argo_status "$ARGO_DOMAIN")
            if [ "$argo_status" == "530" ]; then
                red "Argo $(yellow "$ARGO_DOMAIN") 不可用！状态码：$(yellow "$argo_status")，休眠 10 秒后重试"
                all_checks=false
                sleep 10
                attempt=$((attempt + 1))
                continue
            fi
            
            # 检查 nezha 探针是否在线，不在线则 10 秒后重试
            check_nezha_list
            current_time=$(date +%s)
            echo "$agent_list" | jq -c '.result[]' | while IFS= read -r server; do
                server_name=$(echo "$server" | jq -r '.name')
                last_active=$(echo "$server" | jq -r '.last_active')
                valid_ip=$(echo "$server" | jq -r '.valid_ip')
                server_id=$(echo "$server" | jq -r '.id')
                # 筛选 ID 相符的探针
                if [[ " ${NEZHA_AGENT_ID[@]} " =~ " $server_id " ]]; then
                    if [ $((current_time - last_active)) -gt 30 ]; then
                        nezha_status="offline"
                        red 服务器 "$server_name 的哪吒探针已离线，探针 ID 为 $server_id"
                        all_checks=false
                        sleep 10
                        attempt=$((attempt + 1))
                        continue
                    else
                        nezha_status="online" 
                        break
                    fi
                fi
            done
            
            # 如果所有检查都通过，则打印通畅信息并退出循环
            if [ "$all_checks" == true ]; then
                green "TCP 端口 $(yellow "$VMESS_PORT") $(green "通畅"); $(green "Argo") $(yellow "$ARGO_DOMAIN") $(green "正常") ; $(yellow "哪吒探针") $(green "正常")"
                green "服务器 $(yellow "$HOST") $(green "一切正常！账户：") $(yellow "$SSH_USER")  [$time]"
                break
            fi
        done
        
        # 三项循环检测达到 5 次，远程连接 SSH 执行安装命令
        if [ $attempt -ge $max_attempts ]; then
            red "多次检测失败，开始连接服务器  $(yellow "$HOST") 重装脚本  [$time]"
            if sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no "$SSH_USER@$HOST" -q exit; then
                green "服务器  $(yellow "$HOST")  连接成功，账户：$(yellow "$SSH_USER")  [$time]"
                run_remote_command "$HOST" "$SSH_USER" "$SSH_PASS" "$VMESS_PORT" "$HY2_PORT" "$SOCKS_PORT" "$SOCKS_USER" "$SOCKS_PASS" "$ARGO_DOMAIN" "$ARGO_AUTH" "$NEZHA_SERVER" "$NEZHA_PORT" "$NEZHA_KEY"
                cmd_status=$?
                sleep 3
                if [ $cmd_status -eq 0 ]; then
                    if [ $port_status -eq 0 ] && [ $argo_status != "530" ] && [ $nezha_status == "online" ]; then
                        green "远程命令执行成功，结果如下："
                        green "服务器 $(yellow "$HOST") 端口 $(yellow "$VMESS_PORT") 恢复正常; Argo $(yellow "$ARGO_DOMAIN") 恢复正常; 哪吒 $(yellow "$server_name") 恢复正常"
                    else
                        red "Vmess端口、Argo或哪吒状态异常，请检查服务器参数 $VPS_JSON_URL"
                    fi
                else
                    red "远程命令执行失败，请检查服务器 $(yellow "$HOST") 参数设置是否正确"
                fi
            else
                red "服务器: $(yellow "$HOST") 连接失败，请检查账户 $(yellow "$SSH_USER") 和 $(yellow "密码")  [$time]"
            fi
        fi
    done
}
process_servers
