# cf worker 保活 serv00 节点
  
按照serv的封禁趋势，禁止搭建代理是迟早的事，且serv本身正确的用途是建站而不是代理，因此我重置了自己所有的serv服务器，用来搭建各种服务和数据库

但是serv有登录要求，90天不登录可能会被封号，因此诞生了这个项目，参考了天诚的保活项目，也就是文件夹内的_worker.js

## 文件
文件夹内 `serv-account-alive.js`

## 特点
- 有前端可视化面板，可手动执行
- 前端面板会自动记录上一次执行的时间
- 支持自动化运行，需要设置corn触发器
- 支持tg消息推送

## 教程
### 步骤一
在cf新建一个worker，将代码复制到其中，部署

### 添加环境变量
- ACCOUNTS_URL = 存储你serv登录信息的直链（必填），直链内容模板:
```
{
  "accounts": [
    {
      "username": "用户名1",
      "password": "密码1",
      "panelnum": "3",
      "type": "serv00"
    },
    {
      "username": "用户名2",
      "password": "密码2",
      "panelnum": "8",
      "type": "serv00"
    },
    {
      "username": "用户名3",
      "password": "密码3",
      "panelnum": "",
      "type": "ct8"
    }
  ]
}
```
- PASSWORD = 前端网页访问密码（必填）
- TG_ID = 你的tg机器人的chat id（可选）
- TG_TOKEN = 你的tg机器人的token（可选）

### 绑定kv
- 新建一个kv存储空间，命名为 SERV_LOGIN
- 在worker中绑定这个kv，kv变量名SERV_LOGIN

### 设置corn触发器
建议设置为每月运行一次
