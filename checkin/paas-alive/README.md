# paas-alive

此脚本用于部署到 cf worker，通过设置 worker 的 corn 触发器定时访问指定的地址，包括间断访问和不间断访问两种模式一起运行，以保证容器活跃。

# 使用说明 

1. 部署到 cf worker 

2. 设置环境变量： 

   **变量1：**`24_URLS` = 需要24小时不间断访问的地址，`每行填写1个`，如：
   ```
   https://www.baidu.com
   https://www.yahoo.com
   https://github.com
   ```
   **变量2：**`NO24_URLS` = 凌晨1点至5点暂停访问，其他时间段不间断访问的地址，`每行填写1个`，格式同上

4. 设置 corn 触发器，建议设置为每 2 分钟执行一次

# 适用平台
* 包括但不限于Glitch，Rendenr，Back4app，clever cloud，Zeabur，codesanbox，replit。。。等等，不支持物理停机的容器。
* 老王部署在 huggingface 上的[保活项目](https://huggingface.co/spaces/rides/keep-alive)  可直接复制他的 space，修改 index.js 中的地址即可。

# 原作者
[老王](https://github.com/eooce/Auto-keep-online/tree/main)
