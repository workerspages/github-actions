// 配置常量
const CONFIG = {
  RETRY_ATTEMPTS: 3,      // 重试次数
  RETRY_DELAY: { MIN: 1000, MAX: 9000 }, // 延迟时间（单位：毫秒）
  RATE_LIMIT: { MAX: 100, WINDOW: 3600000 }, // 限流：每小时最多100请求
  COOKIE_MAX_AGE: 86400   // Cookie 过期时间（24小时，单位：秒）
};

// 延迟函数
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 创建结果对象
function createResult(username, type, panelnum, success, message, retryCount = 0) {
  return {
    username,
    type,
    panelnum,
    cronResults: [{ success, message, ...(retryCount ? { retryCount } : {}) }],
    lastRun: new Date().toISOString()
  };
}

// 错误日志记录
async function logError(error, context, env) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${context}: ${error.message}`;
  console.error(logMessage);
  await sendTelegramMessage(`错误警告: ${logMessage}`, env);
}

// 生成随机 User-Agent
function generateRandomUserAgent() {
  const browsers = ['Chrome', 'Firefox', 'Safari', 'Edge', 'Opera'];
  const browser = browsers[Math.floor(Math.random() * browsers.length)];
  const version = Math.floor(Math.random() * 100) + 1;
  const os = ['Windows NT 10.0', 'Macintosh', 'X11'];
  const selectedOS = os[Math.floor(Math.random() * os.length)];
  const osVersion = selectedOS === 'X11' ? 'Linux x86_64' : 
                   selectedOS === 'Macintosh' ? 'Intel Mac OS X 10_15_7' : 
                   'Win64; x64';

  return `Mozilla/5.0 (${selectedOS}; ${osVersion}) AppleWebKit/537.36 (KHTML, like Gecko) ${browser}/${version}.0.0.0 Safari/537.36`;
}

// 请求频率限制
const rateLimit = {
  requests: new Map(),
  checkLimit: function(ip) {
    const now = Date.now();
    const userRequests = this.requests.get(ip) || [];
    const recentRequests = userRequests.filter(time => now - time < CONFIG.RATE_LIMIT.WINDOW);
    this.requests.set(ip, [...recentRequests, now]);
    return recentRequests.length >= CONFIG.RATE_LIMIT.MAX;
  }
};

// User-Agent 缓存
const userAgentCache = {
  cache: new Map(),
  get: function() {
    const now = Math.floor(Date.now() / 3600000);
    if (!this.cache.has(now)) {
      this.cache.clear();
      this.cache.set(now, generateRandomUserAgent());
    }
    return this.cache.get(now);
  }
};

export default {
  // 处理 HTTP 请求
  async fetch(request, env, ctx) {
    return handleRequest(request, env);
  },
  // 处理定时任务
  async scheduled(event, env, ctx) {
    return handleScheduled(event.scheduledTime, env);
  }
};

// 处理 HTTP 请求的主函数
async function handleRequest(request, env) {
  if (!env.PASSWORD || env.PASSWORD.trim() === "") {
    throw new Error("未设置有效的 PASSWORD 环境变量");
  }

  try {
    const url = new URL(request.url);
    const clientIP = request.headers.get('CF-Connecting-IP');

    if (rateLimit.checkLimit(clientIP)) {
      return new Response('请求过多', { status: 429 });
    }

    switch(url.pathname) {
      case '/login':
        return handleLogin(request, env);
      case '/run':
        return handleRun(request, env);
      case '/results':
        return handleResults(request, env);
      case '/check-auth':
        return handleCheckAuth(request, env);
      default:
        return new Response(getHtmlContent(), {
          headers: { 'Content-Type': 'text/html' },
        });
    }
  } catch (error) {
    await logError(error, `请求处理错误 (路径: ${request.url})`, env);
    return new Response('服务器内部错误', { status: 500 });
  }
}

// 添加这个函数
async function handleCheckAuth(request, env) {
  return new Response(JSON.stringify({
    authenticated: isAuthenticated(request, env)
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

// 处理登录请求
async function handleLogin(request, env) {
  if (request.method !== 'POST') {
    return new Response('不允许的方式', { status: 405 });
  }

  try {
    const formData = await request.formData();
    const password = formData.get('password');
    
    if (password === env.PASSWORD) {
      const response = new Response(JSON.stringify({ success: true }), {
        headers: { 'Content-Type': 'application/json' }
      });
      response.headers.set('Set-Cookie', 
        `auth=${env.PASSWORD}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=${CONFIG.COOKIE_MAX_AGE}`
      );
      return response;
    }
    
    return new Response(JSON.stringify({ success: false }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    await logError(error, 'Login Handler', env);
    return new Response('服务器内部错误', { status: 500 });
  }
}

// 处理运行脚本请求
async function handleRun(request, env) {
  if (!isAuthenticated(request, env)) {
    return new Response('未授权的访问', { status: 401 });
  }

  const encoder = new TextEncoder();
  const stream = new TransformStream();
  const writer = stream.writable.getWriter();

  // 创建异步执行函数
  const executeScript = async () => {
    try {
      const response = await fetch(env.ACCOUNTS_URL);
      const accountsData = await response.json();
      const accounts = accountsData.accounts;
      
      let results = [];
      let successCount = 0;
      let failureCount = 0;

      for (let i = 0; i < accounts.length; i++) {
        const account = accounts[i];
        // 发送开始处理某个账号的消息
        await writer.write(encoder.encode(JSON.stringify({
          type: 'processing',
          message: `正在登录服务器: ${account.type}-${account.panelnum} (用户名: ${account.username})...`,
          current: i + 1,
          total: accounts.length
        }) + '\n'));

        const result = await loginWithRetry(account, env);
        results.push(result);

        // 更新统计
        if (result.cronResults[0].success) {
          successCount++;
        } else {
          failureCount++;
        }

        // 发送进度更新
        await writer.write(encoder.encode(JSON.stringify({
          type: 'progress',
          completed: i + 1,
          total: accounts.length,
          result: result,
          stats: {
            success: successCount,
            failure: failureCount,
            total: accounts.length
          }
        }) + '\n'));

        await delay(
          Math.floor(Math.random() * 
          (CONFIG.RETRY_DELAY.MAX - CONFIG.RETRY_DELAY.MIN)) + 
          CONFIG.RETRY_DELAY.MIN
        );
      }

      // 发送完成消息
      const summary = `总共${accounts.length}个账号，成功${successCount}个，失败${failureCount}个`;
      await writer.write(encoder.encode(JSON.stringify({
        type: 'complete',
        message: summary,
        stats: {
          success: successCount,
          failure: failureCount,
          total: accounts.length
        }
      }) + '\n'));

      await env.SERV_LOGIN.put('lastResults', JSON.stringify(results));
      // 发送 TG 汇总消息
      await sendTelegramMessage(null, env, results);  // 传入 results 参数来生成完整报告
    } catch (error) {
      await writer.write(encoder.encode(JSON.stringify({
        type: 'error',
        message: error.message
      }) + '\n'));
    } finally {
      await writer.close();
    }
  };

  // 启动异步执行
  executeScript();

  return new Response(stream.readable, {
    headers: { 
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  });
}

// 处理结果请求
async function handleResults(request, env) {
  if (!isAuthenticated(request, env)) {
    return new Response(JSON.stringify({ authenticated: false }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const results = await env.SERV_LOGIN.get('lastResults', 'json');
    return new Response(JSON.stringify({ 
      authenticated: true, 
      results: results || [] 
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    await logError(error, 'Results Handler', env);
    return new Response('Internal Server Error', { status: 500 });
  }
}

// 定时任务处理函数
async function handleScheduled(scheduledTime, env) {
  try {
    console.log(`定时任务开始执行，计划时间：${new Date(scheduledTime).toISOString()}`);
    const response = await fetch(env.ACCOUNTS_URL);
    const accountsData = await response.json();
    const accounts = accountsData.accounts;
    
    let results = [];
    for (const account of accounts) {
      const result = await loginWithRetry(account, env);  // 添加 env 参数
      results.push(result);
      await delay(
        Math.floor(Math.random() * 
        (CONFIG.RETRY_DELAY.MAX - CONFIG.RETRY_DELAY.MIN)) + 
        CONFIG.RETRY_DELAY.MIN
      );
    }

    await env.SERV_LOGIN.put('lastResults', JSON.stringify(results));
    await sendTelegramMessage(`定时任务完成`, env, results);
  } catch (error) {
    await logError(error, `定时任务处理程序 (计划时间: ${new Date(scheduledTime).toISOString()})`, env);
  }
}

// 处理认证检查请求
function isAuthenticated(request, env) {
  const cookies = request.headers.get('Cookie');
  if (cookies) {
    const authCookie = cookies.split(';').find(c => c.trim().startsWith('auth='));
    if (authCookie) {
      const authValue = authCookie.split('=')[1];
      return authValue === env.PASSWORD;
    }
  }
  return false;
}

// 提取 CSRF Token
function extractCsrfToken(pageContent) {
  const csrfMatch = pageContent.match(/name="csrfmiddlewaretoken" value="([^"]*)"/)
  if (!csrfMatch) {
    throw new Error('未找到 CSRF token');
  }
  return csrfMatch[1];
}

// 处理登录响应
function handleLoginResponse(response, username, type, panelnum, env) {
  if (response.status === 302) {
    return createResult(username, type, panelnum, true, '登录成功');
  } else {
    const message = '登录失败，未知原因。请检查账号和密码是否正确。';
    console.error(message);
    return createResult(username, type, panelnum, false, message);
  }
}

// 账号登录检查函数
async function loginAccount(account, env) {
  const { username, password, panelnum, type } = account;
  const baseUrl = type === 'ct8' 
    ? 'https://panel.ct8.pl' 
    : `https://panel${panelnum}.serv00.com`;
  const loginUrl = `${baseUrl}/login/`;
  const userAgent = userAgentCache.get();

  try {
    const response = await fetch(loginUrl, {
      method: 'GET',
      headers: {
        'User-Agent': userAgent,
      },
    });

    const pageContent = await response.text();
    const csrfToken = extractCsrfToken(pageContent);
    const initialCookies = response.headers.get('set-cookie') || '';

    const loginResponse = await fetch(loginUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': loginUrl,
        'User-Agent': userAgent,
        'Cookie': initialCookies,
      },
      body: new URLSearchParams({
        'username': username,
        'password': password,
        'csrfmiddlewaretoken': csrfToken,
        'next': '/'
      }).toString(),
      redirect: 'manual'
    });

    return handleLoginResponse(loginResponse, username, type, panelnum, env);
  } catch (error) {
    await logError(error, `服务器: ${type}-${panelnum}, 用户名: ${username}`, env);
    return createResult(username, type, panelnum, false, error.message);
  }
}

// 带重试机制的登录函数
async function loginWithRetry(account, env, attempts = CONFIG.RETRY_ATTEMPTS) {
  for (let i = 0; i < attempts; i++) {
    try {
      const result = await loginAccount(account, env);
      if (result.cronResults[0].success) {
        return result;
      }
    } catch (error) {
      if (i === attempts - 1) {
        throw error;
      } 
    }
    await delay(CONFIG.RETRY_DELAY.MIN * (i + 1));
  }
  return createResult(
    account.username, 
    account.type, 
    account.panelnum,
    false,
    `登录失败，已重试 ${attempts} 次`,
    attempts
  );
}

// 发送 Telegram 通知
async function sendTelegramMessage(message, env, results = null) {
  if (!env.TG_ID || !env.TG_TOKEN) {
    console.warn("未设置 TG_ID 或 TG_TOKEN，跳过发送 Telegram 消息");
    return;
  }

  const url = `https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`;
  let messageText;

  if (!results) {
    messageText = message;
  } else {
    const now = new Date().toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).replace(/\//g, '-');

    const successCount = results.filter(r => r.cronResults[0].success).length;
    const failureCount = results.length - successCount;

    messageText = [
      `*🤖 Serv00 登录状态报告*`,
      `⏰ 时间: \`${now}\``,
      `📊 总计: \`${results.length}\` 个账户`,
      `✅ 成功: \`${successCount}\` | ❌ 失败: \`${failureCount}\``,
      '',
      ...results.map(result => {
        const success = result.cronResults[0].success;
        const serverinfo = result.type === 'ct8' 
          ? `${result.type}` 
          : `${result.type}-${result.panelnum}`;
        const lines = [
          `*服务器: ${serverinfo}* | 用户名: ${result.username}`,
          `状态: ${success ? '✅ 登录成功' : '❌ 登录失败'}`
        ];
        
        if (!success && result.cronResults[0].message) {
          lines.push(`失败原因：\`${result.cronResults[0].message}\``);
        }       
        return lines.join('\n');
      })
    ].join('\n');
  }

  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: env.TG_ID,
        text: messageText,
        parse_mode: 'Markdown'
      })
    });
  } catch (error) {
    console.error('发送TG消息时发生错误:', error);
  }
}

// 最后一个函数：HTML 内容生成
function getHtmlContent() {
  const siteIcon = 'https://pan.811520.xyz/icon/serv00.png';
  const bgimgURL = 'https://pan.811520.xyz/icon/back.webp';
  return `
  <!DOCTYPE html>
  <html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Serv00账户批量登录</title>
    <link rel="icon" href="${siteIcon}" type="image/png">
    <style>
      body {
        font-family: Arial, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        margin: 0;
        background-image: url('${bgimgURL}');
        background-size: cover;
      }
      .container {
        text-align: center;
        padding: 5px;
        background-color: rgba(255, 255, 255, 0.6);
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        max-width: 800px;
        width: 100%;
        margin: 0 0 20px 0;
      }
      footer {
        background-color: #4CAF50;
        color: white;
        text-align: center;
        font-size: 12px;
        width: 100%;
        padding: 10px;
        position: fixed;
        bottom: 0;
      }
      footer a {
        color: white;
        text-decoration: none;
        margin-left: 10px;
        transition: color 0.3s ease;
      }
      footer a:hover {
        color: #f1c40f;
      }
      table {
        width: 95%;
        border-collapse: collapse;
        margin: 20px auto;
      }
      th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
      }
      th {
        background-color: rgba(255, 255, 255, 0.7);
      }
      input, button {
        margin: 10px 0;
        padding: 10px;
        width: 200px;
        border-radius: 4px;
        border: 1px solid #ddd;
      }
      button {
        background-color: #4CAF50;
        border: none;
        color: white;
        cursor: pointer;
      }
      button:hover {
        background-color: #45a049;
      }
      button:disabled {
        background-color: #cccccc;
        cursor: not-allowed;
      }
      #status {
        margin-top: 10px;
        font-weight: bold;
      }
      #summary {
        margin: 10px 0;
        font-weight: bold;
        color: #333;
      }
      #loginForm {
        display: block;
      }
      #dashboard {
        display: none;
      }
      #dashboard button {
        margin: 0 0 5px 0;
        padding: 8px 12px;
        width: auto;
      }
      .error {
        color: #ff0000;
      }
      .success {
        color: #4CAF50;
      }
      .processing {
        color: #2196F3;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Serv00登录控制面板</h1>
      <div id="loginForm">
        <input type="password" id="password" placeholder="请输入密码">
        <button id="loginButton">登录</button>
      </div>
      <div id="dashboard">
        <button id="runButton">执行脚本</button>
        <div id="status"></div>
        <div id="summary"></div>
        <table id="resultsTable">
          <thead>
            <tr>
              <th>服务器</th>
              <th>用户名</th>
              <th>状态</th>
              <th>消息</th>
              <th>执行时间</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
    <footer>
      <div>
        Copyright © 2025 Yutian81&nbsp;&nbsp;&nbsp;| 
        <a href="https://github.com/yutian81/Keepalive/tree/main/cf-sb00-alive" target="_blank">GitHub Repository</a>&nbsp;&nbsp;&nbsp;| 
        <a href="https://blog.811520.xyz/" target="_blank">青云志博客</a>
      </div>
    </footer>
    <script>
      async function checkAuth() {
        try {
          const response = await fetch('/check-auth');
          const data = await response.json();
          if (data.authenticated) {
            showDashboard();
          } else {
            showLoginForm();
          }
        } catch (error) {
          console.error('身份验证检查失败: ', error);
          showLoginForm();
        }
      }

      function init() {
        const loginButton = document.getElementById('loginButton');
        const passwordInput = document.getElementById('password');
        const runButton = document.getElementById('runButton');
        
        if (loginButton) {
          loginButton.addEventListener('click', login);
        }
        
        if (passwordInput) {
          passwordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
              e.preventDefault();
              login();
            }
          });
        }
        
        if (runButton) {
          runButton.addEventListener('click', runScript);
        }
        
        checkAuth();
      }

      function showLoginForm() {
        const loginForm = document.getElementById('loginForm');
        const dashboard = document.getElementById('dashboard');
        if (loginForm) loginForm.style.display = 'block';
        if (dashboard) dashboard.style.display = 'none';
      }

      function showDashboard() {
        const loginForm = document.getElementById('loginForm');
        const dashboard = document.getElementById('dashboard');
        if (loginForm) loginForm.style.display = 'none';
        if (dashboard) dashboard.style.display = 'block';
        fetchResults();
      }

      async function login() {
        const passwordInput = document.getElementById('password');
        if (!passwordInput) return;
        
        const formData = new FormData();
        formData.append('password', passwordInput.value);
        
        try {
          const response = await fetch('/login', { 
            method: 'POST',
            body: formData,
            headers: {
              'Accept': 'application/json'
            }
          });
          
          if (!response.ok) {
            throw new Error('登录请求失败');
          }
          
          const result = await response.json();
          
          if (result.success) {
            await checkAuth();
          } else {
            alert('密码错误');
            passwordInput.value = '';
            passwordInput.focus();
          }
        } catch (error) {
          console.error('Login failed:', error);
          alert('登录失败，请重试');
          passwordInput.value = '';
          passwordInput.focus();
        }
      }

      async function runScript() {
        const statusDiv = document.getElementById('status');
        const summaryDiv = document.getElementById('summary');
        const runButton = document.getElementById('runButton');
        const tbody = document.querySelector('#resultsTable tbody');
        
        statusDiv.textContent = '正在执行脚本...';
        statusDiv.className = 'processing';
        runButton.disabled = true;
        summaryDiv.textContent = '';
        tbody.innerHTML = '';
        
        try {
          const response = await fetch('/run', { 
            method: 'POST',
            headers: {
              'Accept': 'application/json'
            }
          });

          if (!response.ok) {
            if (response.status === 401) {
              statusDiv.textContent = '未授权，请重新登录。';
              statusDiv.className = 'error';
              showLoginForm();
              return;
            }
            throw new Error('请求失败');
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\\n').filter(line => line.trim());

            for (const line of lines) {
              try {
                const data = JSON.parse(line);
                handleStreamData(data);
              } catch (e) {
                console.error('解析数据失败:', e);
              }
            }
          }
        } catch (error) {
          statusDiv.textContent = '执行出错: ' + error.message;
          statusDiv.className = 'error';
        } finally {
          runButton.disabled = false;
        }
      }

      function handleStreamData(data) {
        const statusDiv = document.getElementById('status');
        const summaryDiv = document.getElementById('summary');

        switch (data.type) {
          case 'processing':
            statusDiv.textContent = data.message;
            statusDiv.className = 'processing';
            break;
          case 'progress':
            addOrUpdateResultRow(data.result);
            if (data.stats) {
              summaryDiv.textContent = 
                \`总共\${data.stats.total}个账号，\` +
                \`成功\${data.stats.success}个，\` +
                \`失败\${data.stats.failure}个\`;
            }
            break;
          case 'complete':
            statusDiv.textContent = '执行完成！';
            statusDiv.className = 'success';
            summaryDiv.textContent = data.message;
            break;
          case 'error':
            statusDiv.textContent = '执行出错: ' + data.message;
            statusDiv.className = 'error';
            break;
        }
      }

      function addOrUpdateResultRow(result) {
        const serverinfo = result.type === 'ct8' ? result.type : result.type + "-" + result.panelnum;
        const success = result.cronResults[0]?.success ?? false;
        const message = success 
          ? '已登录' // 如果 success 为 true，设置消息为“已登录”
          : '失败原因: ' + (result.cronResults[0]?.message || '未知错误'); // 如果失败，显示失败原因或默认消息
        
        const tbody = document.querySelector('#resultsTable tbody');
        const existingRow = Array.from(tbody.rows).find(row => 
          row.cells[0].textContent === serverinfo && 
          row.cells[1].textContent === result.username
        );
        
        if (existingRow) {
          existingRow.cells[0].textContent = serverinfo;
          existingRow.cells[1].textContent = result.username;
          existingRow.cells[2].textContent = success ? '✅ 成功' : '❌ 失败';
          existingRow.cells[2].className = success ? 'success' : 'error';
          existingRow.cells[3].textContent = message;
          existingRow.cells[4].textContent = new Date(result.lastRun).toLocaleString('zh-CN');
        } else {
          const row = tbody.insertRow(0);
          row.insertCell(0).textContent = serverinfo;
          row.insertCell(1).textContent = result.username;
          const statusCell = row.insertCell(2);
          statusCell.textContent = success ? '✅ 成功' : '❌ 失败';
          statusCell.className = success ? 'success' : 'error';
          row.insertCell(3).textContent = message;
          row.insertCell(4).textContent = new Date(result.lastRun).toLocaleString('zh-CN');
        }
      }

      async function fetchResults() {
        try {
          const response = await fetch('/results');
          if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
              if (data.results) {
                data.results.forEach(result => addOrUpdateResultRow(result));
              }
            } else {
              showLoginForm();
            }
          } else {
            throw new Error('获取结果失败');
          }
        } catch (error) {
          console.error('获取结果时出错:', error);
          showLoginForm();
        }
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
      } else {
        init();
      }
    </script>
  </body>
  </html>
  `;
}
