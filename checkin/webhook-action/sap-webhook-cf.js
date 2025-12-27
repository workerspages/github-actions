// 环境变量配置(必填)
let email = "你的sap登录邮箱";       // SAP登录邮箱,直接填写或设置环境变量，变量名：EMAIL
let password = "你的sap登录密码";    // SAP登录密码,直接填写或设置环境变量，变量名：PASSWORD
let APP_URLS = "";                  // SAP应用URL，支持每行填写一个URL，变量名：APP_URLS
let MONITORED_APPS = [];            // 请勿修改

// 离线重启通知 Telegram配置(可选)
let CHAT_ID = "";    // Telegram聊天CHAT_ID,直接填写或设置环境变量，变量名：TG_CHAT_ID
let BOT_TOKEN = "";    // Telegram机器人TOKEN,直接填写或设置环境变量，变量名：TG_BOT_TOKEN

// 区域固定常量(无需更改)
const REGIONS = {
  US: {
    CF_API: "https://api.cf.us10-001.hana.ondemand.com",
    UAA_URL: "https://uaa.cf.us10-001.hana.ondemand.com",
    DOMAIN_PATTERN: /\.us10(-001)?\.hana\.ondemand\.com$/
  },
  AP: {
    CF_API: "https://api.cf.ap21.hana.ondemand.com",
    UAA_URL: "https://uaa.cf.ap21.hana.ondemand.com",
    DOMAIN_PATTERN: /\.ap21\.hana\.ondemand\.com$/
  }
};

// 工具函数
const sleep = ms => new Promise(r => setTimeout(r, ms));
const json = (o, c = 200) => new Response(JSON.stringify(o), {
  status: c,
  headers: { "content-type": "application/json" }
});

// 根据 URL 提取应用名称 (主机名的第一部分)
function extractAppNameFromUrl(url) {
  try {
    // 解析 URL 并获取 hostname
    const hostname = new URL(url).hostname;
    // 返回第一个点号之前的部分，即应用名称
    return hostname.split('.')[0];
  } catch (e) {
    console.error(`[config-error] 无法从 URL 提取应用名称: ${url}`);
    return null; 
  }
}

// 初始化应用列表
function initializeAppsList(appUrlsString) {
  if (!appUrlsString) {
    console.warn("[config-warning] APP_URLS 环境变量为空。请在 Worker 设置中配置应用 URL。");
    return [];
  }

  return appUrlsString
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('http'))
    .map(url => ({
      url: url,
      name: extractAppNameFromUrl(url)
    }))
    .filter(app => app.name !== null);
  }

// Telegram 消息发送
async function sendTelegramMessage(message) {
  // 如果没有配置 Telegram 参数，则忽略
  if (!CHAT_ID || !BOT_TOKEN || CHAT_ID === "your-chat-id" || BOT_TOKEN === "your-telegram-bot-token") {
    console.log("[telegram] Telegram 未配置，跳过发送消息");
    return;
  }

  try {
    const telegramUrl = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
    const response = await fetch(telegramUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        chat_id: CHAT_ID,
        text: message,
        parse_mode: "Markdown"
      })
    });

    const result = await response.json();
    if (!response.ok) {
      console.error(`[telegram-error] 发送消息失败: ${result.description}`);
    } else {
      console.log("[telegram] 消息发送成功");
    }
    return result;
  } catch (error) {
    console.error(`[telegram-error] 发送消息时出错: ${error.message}`);
  }
}

// 转换成上海时间
function formatShanghaiTime(date) {
  const utcTime = date.getTime() + (date.getTimezoneOffset() * 60000);
  const shanghaiTime = new Date(utcTime + (8 * 60 * 60 * 1000));
  
  return shanghaiTime.getFullYear() + '-' + 
           String(shanghaiTime.getMonth() + 1).padStart(2, '0') + '-' + 
           String(shanghaiTime.getDate()).padStart(2, '0') + ' ' +
           String(shanghaiTime.getHours()).padStart(2, '0') + ':' +
           String(shanghaiTime.getMinutes()).padStart(2, '0') + ':' +
           String(shanghaiTime.getSeconds()).padStart(2, '0');
}

// 根据URL识别区域
function detectRegionFromUrl(url) {
  for (const [regionCode, regionConfig] of Object.entries(REGIONS)) {
    if (regionConfig.DOMAIN_PATTERN.test(url)) {
      return regionCode;
    }
  }
  return null;
}

// 根据 URL 查找应用配置
function findAppConfigByUrl(url) {
  return MONITORED_APPS.find(app => app.url === url);
}

// CF API 交互函数
async function cfGET(url, token) {
  const response = await fetch(url, {
    headers: { authorization: `Bearer ${token}` }
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`CF GET ${response.status} ${url}: ${text.slice(0, 200)}`);
  }
  return text ? JSON.parse(text) : {};
}

async function cfPOST(url, token, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json"
    },
    body: payload ? JSON.stringify(payload) : null
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`CF POST ${response.status} ${url}: ${text.slice(0, 200)}`);
  }
  return text ? JSON.parse(text) : {};
}

// 认证函数
async function getUAAToken(email, password, uaaUrl) {
  try {
    console.log(`[auth] 尝试认证: ${email} @ ${uaaUrl}`);
    
    const authHeader = "Basic " + btoa("cf:");
    const body = new URLSearchParams();
    body.set("grant_type", "password");
    body.set("username", email);
    body.set("password", password);
    body.set("response_type", "token");

    const response = await fetch(`${uaaUrl}/oauth/token`, {
      method: "POST",
      headers: {
        authorization: authHeader,
        "content-type": "application/x-www-form-urlencoded"
      },
      body: body
    });

    const text = await response.text();
    console.log(`[auth] 响应状态: ${response.status}, 响应文本: ${text.substring(0, 200)}...`);
    
    if (!response.ok) {
      throw new Error(`UAA token error: ${response.status} ${text}`);
    }
    
    const result = JSON.parse(text);
    return result.access_token;
  } catch (error) {
    console.error(`[auth-error] 认证失败: ${error.message}`);
    throw error;
  }
}

// 应用信息获取函数 
async function getAppGuidByName(apiUrl, token, appName) {
  const result = await cfGET(`${apiUrl}/v3/apps?names=${encodeURIComponent(appName)}`, token);
  if (result.resources && result.resources.length > 0) {
    return result.resources[0].guid;
  }
  throw new Error(`未找到应用: ${appName}`);
}

// 应用元数据获取函数 (组织、空间、内存、硬盘)
async function getAppMetadata(apiUrl, token, appGuid) {
  try {
    // 获取进程详情 (用于提取内存和硬盘大小)
    const processResult = await cfGET(`${apiUrl}/v3/apps/${appGuid}/processes`, token);
    const webProcess = processResult.resources?.find(p => p.type === "web");
    const memory = webProcess?.memory_in_mb || 0;
    const disk = webProcess?.disk_in_mb || 0;

    // 获取应用详情 (用于提取 Space GUID)
    const appDetails = await cfGET(`${apiUrl}/v3/apps/${appGuid}`, token);
    const spaceGuid = appDetails.relationships?.space?.data?.guid;
    
    if (!spaceGuid) {
      return { memory: `${memory} MB`, disk: `${disk} MB`, org: "N/A", space: "N/A" };
    }

    // 获取 Space 详情 (用于提取 Space 名称和 Org GUID)
    const spaceDetails = await cfGET(`${apiUrl}/v3/spaces/${spaceGuid}`, token);
    const spaceName = spaceDetails.name;
    const orgGuid = spaceDetails.relationships?.organization?.data?.guid;

    // 获取 Org 详情 (用于提取 Org 名称)
    let orgName = "N/A";
    if (orgGuid) {
      const orgDetails = await cfGET(`${apiUrl}/v3/organizations/${orgGuid}`, token);
      orgName = orgDetails.name;
    }

    return { 
      memory: `${memory} MB`, 
      disk: `${disk} MB`, 
      org: orgName, 
      space: spaceName 
    };
  } catch (e) {
    console.error(`[metadata-error] 获取应用元数据失败: ${e.message}`);
    return { memory: "N/A", disk: "N/A", org: "N/A", space: "N/A" };
  }
}

// 应用状态函数
async function getAppState(apiUrl, token, appGuid) {
  const result = await cfGET(`${apiUrl}/v3/apps/${appGuid}`, token);
  return result?.state || "UNKNOWN";
}

async function getWebProcessGuid(apiUrl, token, appGuid) {
  const result = await cfGET(`${apiUrl}/v3/apps/${appGuid}/processes`, token);
  const webProcess = result?.resources?.find(p => p?.type === "web") || result?.resources?.[0];
  if (!webProcess) {
    throw new Error("在应用程序上找不到Web进程");
  }
  return webProcess.guid;
}

async function getProcessStats(apiUrl, token, processGuid) {
  return cfGET(`${apiUrl}/v3/processes/${processGuid}/stats`, token);
}

// 应用状态等待函数 
async function waitAppStarted(apiUrl, token, appGuid) {
  let delay = 2000;
  let state = "";
  
  for (let i = 0; i < 8; i++) {
    await sleep(delay);
    state = await getAppState(apiUrl, token, appGuid);
    console.log(`[app-state-check] attempt ${i + 1}: ${state}`);
    
    if (state === "STARTED") break;
    delay = Math.min(delay * 1.6, 15000);
  }
  
  if (state !== "STARTED") {
    throw new Error(`应用程序未及时启动，最终状态: ${state}`);
  }
}

async function waitProcessInstancesRunning(apiUrl, token, processGuid) {
  let delay = 2000;

  // 重试6次，避免 Worker 后台任务超时
  for (let i = 0; i < 6; i++) { 
    const stats = await getProcessStats(apiUrl, token, processGuid);
    const instances = stats?.resources || [];
    const states = instances.map(it => it?.state);
    console.log(`[proc-stats] attempt ${i + 1}: ${states.join(",") || "no-instances"}`);

    if (states.some(s => s === "RUNNING")) return;
      await sleep(delay);
      delay = Math.min(delay * 1.6, 10000); 
  }
  throw new Error("进程实例未及时运行");
}

// APP URL 检查函数 
async function checkAppUrl(appUrl) {
  try {
    const response = await fetch(appUrl, {
      method: "GET",
      signal: AbortSignal.timeout(30000)
    });
    console.log(`[app-check] ${appUrl} status: ${response.status}`);
    return response.status === 200;
  } catch (error) {
    console.log(`[app-check] ${appUrl} error: ${error.message}`);
    return false;
  }
}

// 首页
function generateStatusPage(apps) {
  // 获取当前时间并转换为上海时间（北京时间）
  const now = new Date();
  const formattedDate = formatShanghaiTime(now);

  const statusCards = apps.map(app => {
    const statusClass = app.healthy ? 'status-up' : 'status-down';
    const statusText = app.healthy ? '运行中' : '已停止';
    const regionName = app.region === 'US' ? '美国' : app.region === 'AP' ? '新加坡' : '未知';

    return `
      <div class="status-card ${statusClass}">
        <div class="card-header">
          <div class="app-info">
            <img src="https://www.sap.cn/favicon.ico" class="app-icon" alt="SAP">
            <h3>${app.app}</h3>
          </div>
          <span class="status-indicator ${statusClass}">${statusText}</span>
        </div>
        <div class="card-body">
          <div class="metadata-row">
            <p><i class="fas fa-globe-asia"></i> 区域：${regionName}</p>
            <p><i class="fas fa-memory"></i> 内存：${app.memory || 'N/A'}</p>
            <p><i class="fas fa-hdd"></i> 磁盘：${app.disk || 'N/A'}</p>
          </div>
          <div class="metadata-row">
            <p><i class="fas fa-sitemap"></i> 组织：${app.org || 'N/A'}</p>
            <p><i class="fas fa-cubes"></i> 空间：${app.space || 'N/A'}</p>
          </div>
        </div>
        <div class="card-footer">
          <button class="btn-restart" onclick="manualRestart('${app.app}', '${app.url}')">
            <i class="fas fa-redo-alt"></i> 手动重启
          </button>
          <a href="${app.url}" target="_blank" class="btn-visit">
            <i class="fas fa-external-link-alt"></i> 访问项目
          </a>
        </div>
      </div>
    `;
  }).join('');
  
  return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAP Cloud 应用状态监控</title>
  <link rel="icon" href="https://www.sap.cn/favicon.ico">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"> 
  <style>
    :root {
      --up-color: #4CAF50; /* 绿色 */
      --down-color: #F44336; /* 红色 */
      --text-color-light: #ffffff; /* 标题文字颜色 */
      --text-color-dark: #333333; /* 主体文字颜色 */
      --border-radius: 12px;
      --box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
      --glass-border: 1px solid rgba(255, 255, 255, 0.4); /* 更明显的玻璃边框 */
    }
    
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      margin: 0;
      padding: 0;
      color: var(--text-color-dark);
      /* 全局背景图设置 */
      background-image: url('https://pan.811520.xyz/icon/bg_light.webp');
      background-size: cover;
      background-attachment: fixed;
      background-repeat: no-repeat;
    }
    
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
      text-align: center;
    }
    
    header {
      padding: 30px 0 0 0;
      margin-bottom: 20px;
    }
    
    h1 {
      margin: 0;
      font-size: 2.8rem;
      font-weight: 700;
      color: var(--text-color-light);
      text-shadow: 2px 2px 4px rgba(0,0,0,0.4);
    }
    
    .subtitle {
      font-size: 1.3rem;
      opacity: 1;
      margin-top: 10px;
      color: var(--text-color-light);
      text-shadow: 1px 1px 3px rgba(0,0,0,0.4);
    }

    .controls {
      text-align: center;
      margin: 30px 0;
      gap: 15px;
    }
    
    .btn {
      background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
      color: white;
      border: none;
      padding: 12px 24px;
      font-size: 1rem;
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
    }
    
    .btn:hover {
      opacity: 0.9;
      transform: translateY(-2px);
    }

    /* 卡片网格布局 */
    .status-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
      gap: 30px;
      margin: 30px auto;
      max-width: 1200px;
      width: 100%;
    }
    
    /* 毛玻璃卡片效果 */
    .status-card {
      /* 半透明毛玻璃背景 */
      background: rgba(255, 255, 255, 0.3); 
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border-radius: var(--border-radius);
      box-shadow: var(--box-shadow);
      border: var(--glass-border);
      overflow: hidden;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      text-align: left;
      display: flex;
      flex-direction: column;
    }

    .status-up {
      border-left: 5px solid var(--up-color);
      color: #000000;
    }
    
    .status-down {
      border-left: 5px solid var(--down-color);
      color: #888888;
    }

    .status-card:hover {
      transform: translateY(-8px);
      box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.45);
    }
    
    .card-header {
      padding: 15px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.3);
    }

    .app-info {
      display: flex;
      align-items: center;
      flex-grow: 1;
      overflow: hidden;
    }

    .app-icon {
      width: 20px;
      height: 20px;
      margin-right: 10px;
      filter: drop-shadow(0 0 1px rgba(0,0,0,0.5));
    }

    .card-header h3 {
      margin: 0;
      font-size: 1.3rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .card-header a {
      color: inherit; /* 继承卡片状态色 (绿或红) */
      text-decoration: none;
      transition: color 0.3s;
      text-shadow: 0 0 5px rgba(0,0,0,0.3);
    }

    .card-header a:hover {
      opacity: 0.8;
    }

    .status-indicator {
      padding: 5px 15px;
      border-radius: 20px;
      font-weight: bold;
      font-size: 0.9rem;
      white-space: nowrap;
    }
    
    /* 状态指示器 */
    .status-up .status-indicator {
      background-color: var(--up-color);
      color: white;
    }
    
    .status-down .status-indicator {
      background-color: var(--down-color);
      color: white;
    }
    
    .card-body {
      padding: 15px 20px;
      font-size: 0.95rem;
      flex-grow: 1;
    }

    .metadata-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
      gap: 10px 20px;
      margin-bottom: 10px;
      align-items: center;
    }
    
    .card-body p {
      margin: 5px 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
    }

    /* 卡片内所有 fa 图标颜色与文字保持一致 (白色) */
    .card-body i {
      margin-right: 8px;
      color: inherit; /* 继承卡片状态色 (绿或红) */
    }
    
    .card-footer {
      padding: 15px 20px;
      border-top: 1px solid rgba(255, 255, 255, 0.3);
      text-align: center;
      display: flex;
      gap: 10px;
    }
    
    .card-footer button,
    .card-footer a.btn-visit {
      flex: 1;
      border: none;
      padding: 10px 15px;
      font-size: 0.95rem;
      border-radius: 8px;
      cursor: pointer;
      transition: opacity 0.3s ease, transform 0.2s;
      text-decoration: none;
      color: white;
      text-align: center;
    }

    /* 手动重启按钮 */
    .btn-restart {
      background: var(--up-color);
    }
    
    .btn-restart:hover {
      background: #388E3C;
      transform: translateY(-1px);
    }
    
    /* 访问项目按钮 */
    .btn-visit {
      background: #0288D1;
    }
    
    .btn-visit:hover {
      background: #039BE5;
      transform: translateY(-1px);
    }
    
    .card-footer i {
      margin-right: 8px;
      color: white; /* 按钮图标颜色 */
    }

    /* 页脚样式 */
    footer {
      text-align: center;
      padding: 20px;
      color: #333;
      font-size: 0.9rem;
      border-top: 1px solid #ccc;
      margin-top: 10px;
      background: none;
    }
    
    .footer-line-1 {
      margin-bottom: 10px;
      font-size: 0.9rem;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
    }

    .footer-line-1 a {
      color: #333;
      text-decoration: none;
      font-weight: normal;
      transition: color 0.3s;
    }

    .footer-line-1 a i {
      margin-right: 5px;
      color: #333;
      transition: color 0.3s;
    }
    
    /* 页脚所有链接悬停时变为蓝色 */
    .footer-line-1 a:hover,
    .footer-line-1 a:hover i,
    .footer-line-2 a:hover {
      color: #007bff;
    }

    .footer-line-2 {
      color: #666;
      font-size: 0.85rem;
      gap: 10px;
    }
    
    .footer-line-2 a {
      color: #666;
      text-decoration: none;
      transition: color 0.3s;
    }

    @media (max-width: 1250px) {
      .status-grid {
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      }
    }
    
    @media (max-width: 768px) {
      .status-grid {
        grid-template-columns: 1fr;
      }
      h1 {
        font-size: 2.2rem;
      }
      .footer-line-1,
      .footer-line-2 {
        flex-direction: column;
        gap: 8px;
      }
      .card-footer {
        flex-direction: column;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>SAP Cloud 应用监控</h1>
      <div class="subtitle">实时监控应用状态，确保服务持续可用</div>
    </header>
    
    <div class="controls">
      <button class="btn" onclick="refreshStatus()" style="margin-right: 15px;">
        <i class="fas fa-sync-alt"></i> 刷新状态
      </button>
      <a href="https://account.hanatrial.ondemand.com/" class="btn" target="_blank" style="text-decoration: none;">
        <i class="fas fa-external-link-alt"></i> 登录官网
      </a>
    </div>
    
    <div class="status-grid">
      ${statusCards}
    </div>

  </div> <footer>
    <div class="footer-line-1">
      <span>&copy; ${new Date().getFullYear()} Copyright by Yutian81</span>
      |
      <a href="https://github.com/yutian81/Keepalive/tree/main/webhook-action" target="_blank"><i class="fab fa-github"></i> Github</a>
      |
      <a href="https://blog.811520.xyz/post/2025/09/250916-uptime-action/" target="_blank"><i class="fas fa-blog"></i> QingYun Blog</a>
    </div>
    <div class="footer-line-2">
      原作者: <a href="https://github.com/eooce/Auto-deploy-sap-and-keepalive" target="_blank">eooce</a> | 状态更新: ${formattedDate}
    </div>
  </footer>

  <script>
    function refreshStatus() {
      location.reload();
    }
    
    function manualRestart(appName, appUrl) {
      if (confirm(\`确认要手动重启应用：\${appName} 吗？\n\n警告：这会向监控 Worker 发送重启请求。\`)) {
        // 1. 获取 Worker 自身的域名（从当前页面的 host 获取）
        const workerDomain = window.location.host;
        
        // 2. 构造完整的重启 Webhook URL
        const restartUrl = \`https://\${workerDomain}/webhook/restart?appUrl=\${encodeURIComponent(appUrl)}\`;
        
        console.log(\`Sending restart request to: \${restartUrl}\`);

        // 3. 发送重启请求
        fetch(restartUrl, { method: 'GET' }) 
          .then(response => response.json())
          .then(data => {
            if (data.ok) {
              alert(\`应用 \${appName} 重启请求已发送（代码 \${data.msg}）。请稍后刷新页面查看状态\`);
            } else {
              alert(\`重启请求发送失败: \${data.error || '未知错误'}\`);
            }
          })
          .catch(error => {
            console.error('重启请求出错:', error);
            alert('网络或服务请求错误，请检查控制台。');
          });
      }
    }
  </script>
</body>
</html>
  `;
}

// 核心启动逻辑
async function ensureAppRunning(appConfig, reason = "unknown") {
  const { url, name } = appConfig;
  const now = new Date();
  const formattedTime = formatShanghaiTime(now);
  
  console.log(`[trigger] ${reason} for app ${name} at ${new Date().toISOString()}`);
  
  // 检查应用URL状态
  const isAppHealthy = await checkAppUrl(url);
    if (isAppHealthy) {
        console.log(`[decision] ${url} 返回200, 应用正常运行, 无需重启`);
        const healthyMessage = `👍 *SAP应用状态良好*\n\n应用名称: ${name}\n应用URL: ${url}\n时间: ${formattedTime}\n\n应用运行正常, 无需重启`;
        await sendTelegramMessage(healthyMessage);
        return { app: name, status: "healthy", url: url, healthy: true };
      }
  
  // 发送离线提醒（使用上海时间）
  const offlineMessage = `⚠️ *SAP应用离线提醒*\n\n应用名称: ${name}\n应用URL: ${url}\n触发原因: ${reason}\n时间: ${formattedTime}\n\n正在尝试重启应用...`;
  await sendTelegramMessage(offlineMessage);
  
  console.log(`[decision] ${url} 状态异常，开始执行重启流程`);
  
  // 确定区域
  const detectedRegion = detectRegionFromUrl(url);
  if (!detectedRegion || !REGIONS[detectedRegion]) {
    throw new Error(`无法确定应用 ${name} 的区域，URL: ${url}`);
  }
  const regionConfig = REGIONS[detectedRegion];
  console.log(`[region] 应用 ${name} 的区域: ${detectedRegion}`);
  
  // 获取CF API访问令牌
  const token = await getUAAToken(email, password, regionConfig.UAA_URL);
  
  // 根据应用名称获取GUID
  const appGuid = await getAppGuidByName(regionConfig.CF_API, token, name);
  console.log(`[app-guid] ${appGuid}`);
  
  // 获取进程信息
  const processGuid = await getWebProcessGuid(regionConfig.CF_API, token, appGuid);
  
  // 强制执行重启操作（无论当前状态是否为 STARTED）
  try {
    console.log(`[action] 强制重启应用: ${name}`);
    await cfPOST(`${regionConfig.CF_API}/v3/apps/${appGuid}/actions/restart`, token);
    console.log("[action] 应用重启请求已发送");
  } catch (e) {
    // 如果重启失败（例如，应用可能确实是 STOPPED 状态），尝试启动
    console.warn(`[action-warning] 重启失败，尝试发送启动请求: ${e.message}`);
    await cfPOST(`${regionConfig.CF_API}/v3/apps/${appGuid}/actions/start`, token);
    console.log("[action] 应用启动请求已发送");
  }
  
  // 等待应用启动完成
  try {
    await waitAppStarted(regionConfig.CF_API, token, appGuid); 
    await waitProcessInstancesRunning(regionConfig.CF_API, token, processGuid);
  } catch (e) {
    console.error(`[wait-error] 应用未能在规定时间启动或运行: ${e.message}`);
    // 抛出错误，以便 Webhook 调用的 ctx.waitUntil 捕获
    throw e; 
  }
  
  // 再次检查应用URL确保启动成功
  console.log("[verification] 验证应用是否成功启动...");
  await sleep(5000);
  
  const isAppHealthyAfterStart = await checkAppUrl(url);
  if (isAppHealthyAfterStart) {
    console.log("[success] 应用启动成功, URL状态正常");
    // 发送重启成功提醒
    const successMessage = `✅ *SAP应用重启成功*\n\n应用名称: ${name}\n应用URL: ${url}\n时间: ${formatShanghaiTime(new Date())}`;
    await sendTelegramMessage(successMessage);
    return { app: name, status: "restarted_healthy", url: url, healthy: true };
  } else {
    console.log("[warning] 应用启动完成但URL状态仍异常，可能需要更多时间或存在其他问题");
    // 发送重启失败提醒
    const failedMessage = `❌ *SAP应用重启失败（URL仍异常）*\n\n应用名称: ${name}\n应用URL: ${url}\n时间: ${formatShanghaiTime(new Date())}`;
    await sendTelegramMessage(failedMessage);
    return { app: name, status: "restarted_but_unhealthy", url: url, healthy: false };
  }
}

// 监控所有应用 (用于 /status 和 /)
async function monitorAllApps(reason = "unknown") {
  console.log(`[monitor-start] 开始监控所有应用: ${reason}`);
  const results = [];
  
  // 使用对象存储令牌，避免重复认证
  const regionTokens = {};

  for (const app of MONITORED_APPS) {
    const detectedRegion = detectRegionFromUrl(app.url);
    const regionConfig = REGIONS[detectedRegion];

    let isHealthy = false;
    let metadata = { org: "N/A", space: "N/A", memory: "N/A", disk: "N/A" };

    try {
      // 快速 URL 健康检查
      isHealthy = await checkAppUrl(app.url);

      if (!regionConfig) {
        throw new Error(`无法确定区域: ${app.url}`);
      }
      
      // 获取令牌 (如果尚未获取)
      if (!regionTokens[detectedRegion]) {
        regionTokens[detectedRegion] = await getUAAToken(email, password, regionConfig.UAA_URL);
      }
      const token = regionTokens[detectedRegion];
      
      // 获取应用 GUID
      const appGuid = await getAppGuidByName(regionConfig.CF_API, token, app.name);

      // 获取详细元数据 (组织、空间、内存、硬盘)
      metadata = await getAppMetadata(regionConfig.CF_API, token, appGuid);

    } catch (error) {
      console.error(`[app-error] 检查应用 ${app.name} 时出错:`, error.message);
      // 如果出现错误，isHealthy 保持 false (或由 checkAppUrl 确定)，metadata 保持 N/A
    }
    
    results.push({
      app: app.name,
      url: app.url,
      healthy: isHealthy,
      region: detectedRegion,
      org: metadata.org,
      space: metadata.space,
      memory: metadata.memory,
      disk: metadata.disk
    });
  }
  
  console.log(`[monitor-complete] 所有应用状态检查完成`);
  return results;
}

export default {
  // HTTP 请求处理
  async fetch(request, env, ctx) {
    // 从环境变量获取配置
    email = env.EMAIL || email;
    password = env.PASSWORD || password;
    APP_URLS = env.APP_URLS;
    MONITORED_APPS = initializeAppsList(APP_URLS);
    CHAT_ID = env.TG_CHAT_ID || CHAT_ID;
    BOT_TOKEN = env.TG_BOT_TOKEN || BOT_TOKEN;

    if (MONITORED_APPS.length === 0 && !request.url.includes("/webhook/restart")) {
      // 如果应用列表为空，且不是重启请求，则返回配置错误页面
      return new Response(generateStatusPage([]), {
        headers: { "content-type": "text/html;charset=UTF-8" }
      });
    }    

    const url = new URL(request.url);
    
    try {
      // Webhook 触发端点，允许 GET 或 POST 请求，只要 URL 中包含 appUrl 参数即可
      if (url.pathname === "/webhook/restart" && (request.method === "GET" || request.method === "POST")) {
        const appUrl = url.searchParams.get('appUrl');
        
        if (!appUrl) {
          return json({ ok: false, error: "缺少 appUrl 查询参数" }, 400);
        }
        
        const appConfig = findAppConfigByUrl(appUrl);
        
        if (!appConfig) {
          return json({ ok: false, error: `未找到 URL: ${appUrl} 对应的应用配置` }, 404);
        }
        
        // 使用 ctx.waitUntil 允许长时间运行的重启任务在 Webhook 响应后继续执行
        ctx.waitUntil(
          ensureAppRunning(appConfig, "webhook-trigger")
            .then(result => {
              console.log(`Webhook 重启结果 (${appConfig.name}):`, result);
            })
            .catch(e => {
              console.error(`Webhook 重启失败 (${appConfig.name}):`, e.message);
              // 如果启动失败，发送 Telegram 消息
              sendTelegramMessage(`❌ *Webhook 重启最终失败*\n\n应用: ${appConfig.name}\n错误: ${e.message}`).catch(console.error);
            })
        );
        
        // 立即返回 202 Accepted 响应给 Uptime Kuma
        return json({ ok: true, msg: `已接收应用 ${appConfig.name} 的离线通知，后台正在尝试启动`, target_app: appConfig.name }, 202);
      }
      
      // 根路径 - 显示前端页面
      if (url.pathname === "/") {
        const statusResults = await monitorAllApps("status-page");
        const html = generateStatusPage(statusResults);
        return new Response(html, {
          headers: { "content-type": "text/html;charset=UTF-8" }
        });
      }
      
      // 手动启动端点 (保留，但建议用户使用 /webhook/restart)
      if (url.pathname === "/start") {
        return json({ ok: false, msg: "请使用 /webhook/restart?appUrl=... 触发单个应用重启" }, 400);
      }
      
      // 应用状态检查端点
      if (url.pathname === "/status") {
        const statusResults = await monitorAllApps("api-status-check");
        return json({
          ok: true,
          apps: statusResults,
          timestamp: new Date().toISOString()
        });
      }
      
      // 默认响应
      return new Response("SAP Cloud 自动保活 Worker 运行中");
      
    } catch (error) {
      console.error("[error]", error?.message || error);
      return json({ ok: false, error: String(error) }, 500);
    }
  }

  // 定时任务处理 (按要求，禁用自动重启逻辑，仅保留空壳)
    /*
    async scheduled(event, env, ctx) {
      // 从环境变量获取配置
      email = env.EMAIL || email;
      password = env.PASSWORD || password;
      CHAT_ID = env.CHAT_ID || CHAT_ID;
      BOT_TOKEN = env.BOT_TOKEN || BOT_TOKEN;
      APP_URLS = env.APP_URLS;
      MONITORED_APPS = initializeAppsList(APP_URLS);
  
      try {
        // 仅用于 /status 页面刷新，不触发重启
        console.log(`[cron-disabled] 定时任务触发: ${event.cron}，根据用户要求，此任务不会触发应用重启。`);
        // 如果需要保留周期性健康检查，可以取消注释下面这行，但它不会触发重启。
        // ctx.waitUntil(monitorAllApps("cron-check")); 
      } catch (error) {
        console.error("[cron-error]", error?.message || error);
      }
    }
    */

};
