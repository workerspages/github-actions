// 环境变量优先，没有则使用代码里填写的
const DEFAULT_CONFIG = {
  ARGO_DOMAIN: 'databricks.argo.dmain.com',                          // (必填)填写自己的隧道域名
  DATABRICKS_HOST: 'https://abc-1223456789.cloud.databricks.com',    // (必填)直接在单引号内填写工作区host或添加环境变量,变量名：DATABRICKS_HOST
  DATABRICKS_TOKEN: 'dapi6dae4632d66931ecdeefexxxxxxxxxxxxx',        // (必填)直接在单引号内填写token或添加环境变量,变量名：DATABRICKS_TOKEN
  CHAT_ID: '',                                                       // 直接在单引号内填写Telegram聊天或添加环境变量CHAT_ID,须同时填写BOT_TOKEN(可选配置)
  BOT_TOKEN: ''                                                      // 直接在单引号内填写Telegram机器人或添加环境变量,须同时填写CHAT_ID
};

// 获取配置
function getConfig(env) {
  const host = env.DATABRICKS_HOST || DEFAULT_CONFIG.DATABRICKS_HOST;
  const token = env.DATABRICKS_TOKEN || DEFAULT_CONFIG.DATABRICKS_TOKEN;
  const chatId = env.TG_CHAT_ID || DEFAULT_CONFIG.CHAT_ID;
  const botToken = env.TG_BOT_TOKEN || DEFAULT_CONFIG.BOT_TOKEN;
  const argoDomain = env.ARGO_DOMAIN || DEFAULT_CONFIG.ARGO_DOMAIN;
  
  return {
    DATABRICKS_HOST: host,
    DATABRICKS_TOKEN: token,
    CHAT_ID: chatId,
    BOT_TOKEN: botToken,
    ARGO_DOMAIN: argoDomain,
    source: {
      host: env.DATABRICKS_HOST ? '环境变量' : '默认值',
      token: env.DATABRICKS_TOKEN ? '环境变量' : '默认值',
      chatId: env.CHAT_ID ? '环境变量' : '默认值',
      botToken: env.BOT_TOKEN ? '环境变量' : '默认值',
      argoDomain: env.ARGO_DOMAIN ? '环境变量' : '默认值'
    }
  };
}

// 存储上次 ARGO 状态
let lastArgoStatus = null;

// 检查 ARGO 域名状态
async function checkArgoDomain(argoDomain) {
  try {
    const response = await fetch(`https://${argoDomain}`, {
      method: 'GET',
      headers: {
        'User-Agent': 'Databricks-Monitor/1.0'
      }
    });
    
    const statusCode = response.status;
    console.log(`ARGO域名 ${argoDomain} 状态码: ${statusCode}`);
    
    return {
      online: statusCode === 404,
      statusCode: statusCode,
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    console.error(`检查 ARGO域名 ${argoDomain} 时出错:`, error);
    return {
      online: false,
      statusCode: null,
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

// 检查 ARGO 状态是否有变化
function hasArgoStatusChanged(newStatus) {
  if (!lastArgoStatus) return true;
  
  return lastArgoStatus.online !== newStatus.online || 
         lastArgoStatus.statusCode !== newStatus.statusCode;
}

// 发送 Telegram 通知
async function sendTelegramNotification(config, message) {
  const { CHAT_ID, BOT_TOKEN } = config;
  
  if (!CHAT_ID || !BOT_TOKEN) {
    console.log('Telegram 通知未配置，跳过发送');
    return false;
  }
  
  try {
    const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chat_id: CHAT_ID,
        text: message,
        parse_mode: 'HTML'
      }),
    });
    
    const result = await response.json();
    
    if (result.ok) {
      console.log('Telegram 通知发送成功');
      return true;
    } else {
      console.error('Telegram 通知发送失败:', result);
      return false;
    }
  } catch (error) {
    console.error('发送 Telegram 通知时出错:', error);
    return false;
  }
}

// 发送 ARGO 离线通知
async function sendArgoOfflineNotification(config, argoStatus) {
  const message = `🔴 <b>ARGO 隧道离线</b>\n\n` +
                 `🌐 域名: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `📊 状态码: <code>${argoStatus.statusCode || '连接失败'}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n\n` +
                 `🔍 正在检查 Databricks App 状态...`;
  
  return await sendTelegramNotification(config, message);
}

// 发送 ARGO 恢复通知
async function sendArgoRecoveryNotification(config) {
  const message = `✅ <b>ARGO 隧道恢复</b>\n\n` +
                 `🌐 域名: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `📊 状态: <code>404 (正常)</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n\n` +
                 `🎉 节点已恢复正常`;
  
  return await sendTelegramNotification(config, message);
}

// 发送离线通知
async function sendOfflineNotification(config, appName, appId) {
  const message = `🔴 <b>Databricks App 离线</b>\n\n` +
                 `📱 App: <code>${appName}</code>\n` +
                 `🆔 ID: <code>${appId}</code>\n` +
                 `🌐 ARGO: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n\n` +
                 `⚡ 系统正在尝试自动重启...`;

  return await sendTelegramNotification(config, message);
}

// 发送启动成功通知
async function sendStartSuccessNotification(config, appName, appId) {
  const message = `✅ <b>Databricks App 启动成功</b>\n\n` +
                 `📱 App: <code>${appName}</code>\n` +
                 `🆔 ID: <code>${appId}</code>\n` +
                 `🌐 ARGO: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n\n` +
                 `🎉 App 正在启动中,请等待argo恢复后再检查节点`;
  
  return await sendTelegramNotification(config, message);
}

// 发送启动失败通知
async function sendStartFailedNotification(config, appName, appId, error) {
  const message = `❌ <b>Databricks App 启动失败</b>\n\n` +
                 `📱 App: <code>${appName}</code>\n` +
                 `🆔 ID: <code>${appId}</code>\n` +
                 `🌐 ARGO: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n` +
                 `💥 错误: <code>${error}</code>\n\n` +
                 `🔧 请检查 App 配置或手动访问 域名/start 启动`;
  
  return await sendTelegramNotification(config, message);
}

// 发送手动操作通知
async function sendManualOperationNotification(config, operation, results) {
  const successCount = results.filter(r => r.status === 'started').length;
  const failedCount = results.filter(r => r.status === 'start_failed' || r.status === 'error').length;
  const stoppedCount = results.filter(r => r.computeState === 'STOPPED').length;
  
  const message = `📊 <b>Databricks Apps ${operation}</b>\n\n` +
                 `✅ 成功启动: ${successCount} 个\n` +
                 `❌ 启动失败: ${failedCount} 个\n` +
                 `⏸️ 停止状态: ${stoppedCount} 个\n` +
                 `🌐 ARGO域名: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}`;
  
  return await sendTelegramNotification(config, message);
}

// 获取 Apps 列表
async function getAppsList(config) {
  const { DATABRICKS_HOST, DATABRICKS_TOKEN } = config;
  
  let allApps = [];
  let pageToken = '';
  
  do {
    let url = `${DATABRICKS_HOST}/api/2.0/apps?page_size=50`;
    if (pageToken) {
      url += `&page_token=${encodeURIComponent(pageToken)}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${DATABRICKS_TOKEN}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API 请求失败: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    const apps = data.apps || [];
    
    allApps = allApps.concat(apps);
    pageToken = data.next_page_token || '';
  } while (pageToken);

  return allApps;
}

// 获取 Apps 状态
async function getAppsStatus(config) {
  try {
    const apps = await getAppsList(config);
    
    const results = apps.map(app => {
      const creationTimestampMs = app.creation_timestamp 
          ? app.creation_timestamp * 1000 
          : null;
      
      return {
          name: app.name,
          id: app.id,
          state: app.compute_status?.state || 'UNKNOWN',
          url: app.url,
          createdAt: creationTimestampMs, 
          lastUpdated: app.last_updated_timestamp 
              ? app.last_updated_timestamp * 1000 
              : null
      };
    });
    
    const summary = {
      total: results.length,
      active: results.filter(app => app.state === 'ACTIVE').length,
      stopped: results.filter(app => app.state === 'STOPPED').length,
      unknown: results.filter(app => app.state === 'UNKNOWN').length,
      other: results.filter(app => !['ACTIVE', 'STOPPED', 'UNKNOWN'].includes(app.state)).length
    };
    
    return {
      summary,
      apps: results
    };
  } catch (error) {
    throw error;
  }
}

// 智能检查：只在 ARGO 状态变化时调用 Databricks API
async function smartCheckAndStartApps(config) {
  console.log(`检查 ARGO 域名: ${config.ARGO_DOMAIN}`);
  const currentArgoStatus = await checkArgoDomain(config.ARGO_DOMAIN);
  
  // 检查 ARGO 状态是否有变化
  const statusChanged = hasArgoStatusChanged(currentArgoStatus);
  
  if (currentArgoStatus.online) {
    console.log(`✅ ARGO 域名 ${config.ARGO_DOMAIN} 状态正常 (404)`);
    
    // 如果状态从离线变为在线，发送恢复通知
    if (statusChanged && lastArgoStatus && !lastArgoStatus.online) {
      console.log('ARGO 状态从离线恢复为在线，发送恢复通知');
      await sendArgoRecoveryNotification(config);
    }
    
    // 更新上次状态
    lastArgoStatus = currentArgoStatus;
    
    return {
      argoStatus: 'online',
      statusChanged: statusChanged,
      message: 'ARGO 隧道运行正常',
      timestamp: new Date().toISOString()
    };
  }
  
  console.log(`🔴 ARGO 域名 ${config.ARGO_DOMAIN} 离线，状态码: ${currentArgoStatus.statusCode}`);
  
  // 如果 ARGO 状态变化为离线，发送通知并检查 Databricks
  if (statusChanged) {
    console.log('ARGO 状态变化为离线，发送通知并检查 Databricks Apps');
    await sendArgoOfflineNotification(config, currentArgoStatus);
  }
  
  // ARGO 离线，检查 Databricks Apps
  const apps = await getAppsList(config);
  const results = [];
  
  for (const app of apps) {
    const result = await processApp(app, config);
    results.push(result);
  }
  
  console.log(`ARGO 离线检查完成，共处理 ${results.length} 个 Apps`);
  
  // 更新上次状态
  lastArgoStatus = currentArgoStatus;
  
  return {
    argoStatus: 'offline',
    statusChanged: statusChanged,
    argoDetails: currentArgoStatus,
    results: results,
    timestamp: new Date().toISOString()
  };
}

// 启动停止的 Apps
async function startStoppedApps(config) {
  const apps = await getAppsList(config);
  const stoppedApps = apps.filter(app => (app.compute_status?.state || 'UNKNOWN') === 'STOPPED');
  const results = [];
  
  console.log(`找到 ${stoppedApps.length} 个停止的 Apps`);
  
  for (const app of stoppedApps) {
    const result = await startSingleApp(app, config);
    results.push(result);
  }
  
  if (stoppedApps.length > 0) {
    await sendManualOperationNotification(config, '手动启动', results);
  }
  
  return results;
}

// 处理单个 App
async function processApp(app, config) {
  const appName = app.name;
  const appId = app.id;
  const computeState = app.compute_status?.state || 'UNKNOWN';
  
  console.log(`检查 App: ${appName} (ID: ${appId}) | Compute状态: ${computeState}`);

  if (computeState === 'STOPPED') {
    console.log(`⚡ 启动停止的 App: ${appName}`);
    
    await sendOfflineNotification(config, appName, appId);

    return await startSingleApp(app, config);
  } else {
    console.log(`✅ App ${appName} 状态正常: ${computeState}`);
    return { 
      app: appName, 
      appId: appId, 
      status: 'healthy', 
      computeState,
      timestamp: new Date().toISOString()
    };
  }
}

// 启动单个 App
async function startSingleApp(app, config) {
  const { DATABRICKS_HOST, DATABRICKS_TOKEN } = config;
  const appName = app.name;
  const appId = app.id;
  
  try {
    const encodedAppName = encodeURIComponent(appName);
    const startUrl = `${DATABRICKS_HOST}/api/2.0/apps/${encodedAppName}/start`;
    
    console.log(`启动 URL: ${startUrl}`);
    
    const startResponse = await fetch(startUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${DATABRICKS_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });

    const responseText = await startResponse.text();
    console.log(`启动响应: ${responseText}`);

    if (startResponse.ok) {
      console.log(`✅ App ${appName} 启动成功`);
      
      await sendStartSuccessNotification(config, appName, appId);
      
      return { 
        app: appName, 
        appId: appId, 
        status: 'started', 
        success: true,
        timestamp: new Date().toISOString()
      };
    } else {
      console.error(`❌ App ${appName} 启动失败:`, responseText);
      
      let errorDetails;
      try {
        errorDetails = JSON.parse(responseText);
      } catch {
        errorDetails = { message: responseText };
      }
      
      const errorMessage = errorDetails.message || '未知错误';
      
      await sendStartFailedNotification(config, appName, appId, errorMessage);
      
      return { 
        app: appName, 
        appId: appId, 
        status: 'start_failed', 
        error: errorDetails,
        timestamp: new Date().toISOString()
      };
    }
  } catch (error) {
    console.error(`❌ App ${appName} 启动请求错误:`, error);
    
    await sendStartFailedNotification(config, appName, appId, error.message);
    
    return { 
      app: appName, 
      appId: appId, 
      status: 'error', 
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

// 前端 HTML
function getFrontendHTML() {
  return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="https://ui-assets.cloud.databricks.com/favicon.ico">
    <title>Databricks Apps 监控面板</title>
    <style>
        /* 保持之前的样式不变 */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: url('https://pan.811520.xyz/icon/bg_light.webp') no-repeat center/cover;
          padding: 20px;
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          background: rgba(255, 255, 255, 0.3);
          border-radius: 12px;
          box-shadow: 5px 10px 20px rgba(0, 0, 0, 0.2);
          overflow: hidden;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
        }
        .header {
          background: rgba(0, 0, 0, 0.6);
          color: white;
          padding: 30px;
          text-align: center;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .controls {
          padding: 25px;
          margin: 25px 25px 0 25px;
          background: rgba(255, 255, 255, 0.3);
          display: flex;
          gap: 15px;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          box-shadow: 5px 0 15px rgba(0, 0, 0, 0.15);
          border-radius: 8px;
        }
        .status-panel { padding: 25px; }
        .status-card {
          background: rgba(255, 255, 255, 0.3);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 20px;
          border-radius: 8px;
          box-shadow: 5px 10px 15px rgba(0, 0, 0, 0.15);
          border-left: 4px solid #007bff;
        }
        .status-card.argo-online { border-left-color: #28a745; }
        .status-card.argo-offline { border-left-color: #dc3545; }
        .status-title { font-size: 1.2em; font-weight: bold; margin-bottom: 15px; color: #2c3e50; }
        .status-content { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .status-item {
          padding: 10px;
          background: rgba(255, 255, 255, 0.35);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          border-radius: 8px;
        }
        .status-label { font-size: 0.9em; color: #6c757d; }
        .status-value { font-size: 1.1em; font-weight: bold; margin-top: 5px; }        
        .stats {
          width: 100%;
          display: flex;
          flex-direction: row;
          gap: 20px;
          flex-wrap: wrap;
          justify-content: flex-start;
          margin-top: 10px;
        }
        .stat-card {
          flex: 1; 
          min-width: 150px; 
          box-sizing: border-box; 
          background: rgba(255, 255, 255, 0.35);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          border-left: 4px solid #007bff;
          height: 120px; 
          display: flex;
          flex-direction: column;
          justify-content: center;
        }
        .stat-card.last-updated-card .stat-number {
          font-size: 1.2em;
          line-height: 1.3;
        }
        .stat-number { font-size: 2.5em; font-weight: bold; color: #2c3e50; }
        .stat-label { color: #6c757d; font-size: 0.9em; margin-top: 5px; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; }
        .btn-primary { background: #007bff; color: white; }
        .btn-secondary { background: #EC4A9D; color: white; text-align: center; }
        .btn-success { background: #28a745; color: white; }
        .btn-info { background: #17a2b8; color: white; }
        .btn-creat { background: #8a2be2; color: white; }
        .btn-warning { background: #ffc107; color: #212529; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .apps-list { padding: 25px 25px 0 25px; }
        .apps-table {
          width: 100%;
          border-collapse: collapse;
          background: rgba(255, 255, 255, 0.35);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 5px 10px 15px rgba(0, 0, 0, 0.15);
        }
        .apps-table th, .apps-table td { padding: 15px; text-align: left; }
        .apps-table th {
          background: rgba(255, 255, 255, 0.3);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          font-weight: 600;
          color: #2c3e50;
        }
        .state-badge { padding: 4px 12px; border-radius: 8px; font-size: 0.85em; font-weight: 600; }
        .state-active { background: #d4edda; color: #155724; }
        .state-stopped { background: #f8d7da; color: #721c24; }
        .state-unknown { background: #fff3cd; color: #856404; }
        .loading { text-align: center; padding: 40px; color: #6c757d; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; margin: 20px 25px; }
        .last-updated { text-align: center; padding: 15px; color: #6c757d; font-size: 0.9em; border-top: 1px solid #e9ecef; }
        .info-panel {
          background: rgba(255, 255, 255, 0.30);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 20px;
          border-radius: 8px;
          margin: 20px 0 0 0;
        }
        .routes-info {
          background: rgba(255, 255, 255, 0.30);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 20px;
          margin: 0 25px 25px 25px;
          border-radius: 8px;
          box-shadow: 5px 10px 15px rgba(0, 0, 0, 0.15);
        }
        .routes-info h3 { margin-bottom: 25px; color: #2c3e50; }
        .route-item {
          background: rgba(255, 255, 255, 0.35);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 15px;
          border-radius: 8px;
          border-left: 4px solid #007bff;
          flex: 1 1 calc(50% - 20px);
          box-sizing: border-box;
        }
        .routes-grid { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 10px; }
        .footer-links {
          display: flex;
          justify-content: center;
          gap: 20px;
          padding: 20px;
          background: rgba(0, 0, 0, 0.6);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
        }
        .footer-links a { color: white; text-decoration: none; font-weight: 500; transition: color 0.3s ease; display: flex; align-items: center; gap: 8px; }
        .footer-links a:hover { color: #4da8ff; }
        img.emoji { height: 1em; width: 1em; margin: 0 .05em 0 .1em; vertical-align: -0.1em; }
        @media (max-width: 768px) {
            .controls { flex-direction: column; align-items: stretch; }
            .btn { justify-content: center; }
            .apps-table { font-size: 0.9em; }
            .apps-table th, .apps-table td { padding: 10px 8px; }
            .route-item { flex: 1 1 100%; }
            .footer-links { flex-direction: column; align-items: center; gap: 15px; }
        }
        
        /* Modal styles 创建app的模态框样式*/
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
        }
        .modal-content {
            background: white;
            margin: 5% auto;
            padding: 0;
            border: none;
            border-radius: 8px;
            width: 80%;
            max-width: 800px;
            max-height: 80vh;
            overflow: hidden;
            box-shadow: 5px 10px 15px rgba(0, 0, 0, 0.15);
        }
        .modal-header {
            padding: 20px;
            background: rgba(0, 0, 0, 0.6);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e9ecef;
        }
        .modal-body {
            padding: 20px;
            max-height: 60vh;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.3);
        }
        .modal-footer {
            padding: 15px 20px;
            background: rgba(0, 0, 0, 0.6);
            display: flex;
            justify-content: flex-end;
            border-top: 1px solid #e9ecef;
        }
        .close {
            color: black;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: #ddd;
        }
        .log-entry {
            margin: 5px 0;
            padding: 5px;
            border-radius: 4px;
        }
        .log-info {
            color: #0066cc;
        }
        .log-success {
            color: #28a745;
        }
        .log-error {
            color: #dc3545;
        }
        .log-warning {
            color: #ffc107;
        }
        .spinner {
            border: 2px solid #f3f3f3;
            border-top: 2px solid #3498db;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
          <h1>👋 Databricks Apps 监控面板</h1>
          <p>智能监控 - ARGO 状态优先，减少 API 调用</p>
        </div>

        <div id="messageContainer"></div>

        <div class="controls">
          <button class="btn btn-primary" onclick="refreshStatus()">🔄 刷新状态</button>
          <button class="btn btn-success" onclick="startStoppedApps()">⚡ 启动 APP</button>
          <button class="btn btn-info" onclick="checkAndStart()">🔍 智能检查</button>
          <button class="btn btn-creat" onclick="createOrReplaceApp()">🛠️ 创建 APP</button>
          <button class="btn btn-warning" onclick="testNotification()">🔔 测试 TG 通知</button>
          <a href="#" id="projectHomepageLink" target="_blank" class="btn btn-secondary" style="text-decoration: none;">🔗 项目主页</a>
          <div class="stats" id="statsContainer">
            <div class="loading">⏳ 加载统计数据...</div>
          </div>
        </div>
        
        <div class="apps-list">
          <h3 style="margin-bottom: 20px; color: #2c3e50;">
              <img 
                  src="https://ui-assets.cloud.databricks.com/favicon.ico" 
                  alt="Databricks Icon" 
                  style="width: 24px; height: 24px; vertical-align: middle; margin-right: 10px;"
              >
              Databricks Apps 状态
          </h3>
          <div id="appsContainer">
              <div class="loading">⏳ 加载 Apps 列表...</div>
          </div>
        </div>

        <div class="status-panel">
            <div class="status-card" id="argoStatusCard">
                <div class="status-title">🚇 ARGO 隧道状态</div>
                <div class="status-content">
                    <div class="status-item">
                        <div class="status-label">🌐 域名</div>
                        <div class="status-value" id="argoDomain">-</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">📊 状态</div>
                        <div class="status-value" id="argoStatus">检查中...</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">⚡ 状态码</div>
                        <div class="status-value" id="argoStatusCode">-</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="routes-info">
          <h3>📚 API 路由说明</h3>
          <div class="routes-grid">
              <div class="route-item"><strong>GET /</strong> - 显示此管理界面</div>
              <div class="route-item"><strong>GET /status</strong> - 获取当前所有 Apps 的状态</div>
              <div class="route-item"><strong>GET /check</strong> - 智能检查（ARGO优先）</div>
              <div class="route-item"><strong>GET /check-argo</strong> - 检查 ARGO 域名状态</div>
              <div class="route-item"><strong>POST /start</strong> - 手动启动所有停止的 Apps</div>
              <div class="route-item"><strong>GET /config</strong> - 查看当前配置信息</div>
              <div class="route-item"><strong>POST /create-app</strong> - 创建/替换 APP（先删除再创建新APP）</div>
              <div class="route-item"><strong>POST /test-notification</strong> - 测试 Telegram 通知</div>
          </div>
        </div>
        
        <div class="footer-links">
            <a href="https://github.com/eooce/Databricks-depoly-and-keepalive" target="_blank">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                </svg>
                GitHub
            </a>
            <a href="https://github.com/yutian81/Keepalive/blob/main/databricks-alive" target="_blank">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                </svg>
                Yutian81修改
            </a>            
            <a href="https://www.youtube.com/@eooce" target="_blank">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8.051 1.999h.089c.822.003 4.987.033 6.11.335a2.01 2.01 0 011.415 1.42c.101.38.172.883.22 1.402l.01.104.022.26.008.104c.065.914.073 1.77.074 1.957v.075c-.001.194-.01 1.108-.082 2.06l-.008.105-.009.104c-.05.572-.124 1.14-.235 1.558a2.007 2.007 0 01-1.415 1.42c-1.16.312-5.569.334-6.18.335h-.142c-.309 0-1.587-.006-2.927-.052l-.17-.006-.087-.004-.171-.007-.171-.007c-1.11-.049-2.167-.128-2.654-.26a2.007 2.007 0 01-1.415-1.419c-.111-.417-.185-.986-.235-1.558L.09 9.82l-.008-.104A31.4 31.4 0 010 7.68v-.123c.002-.215.01-.958.064-1.778l.007-.103.003-.052.008-.104.022-.26.01-.104c.048-.519.119-1.023.22-1.402a2.007 2.007 0 011.415-1.42c.487-.13 1.544-.21 2.654-.26l.17-.007.172-.006.086-.003.171-.007A99.788 99.788 0 017.858 2h.193zM6.4 5.209v4.818l4.157-2.408L6.4 5.209z"/>
                </svg>
                YouTube
            </a>
            <a href="https://t.me/eooceu" target="_blank">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M16 8A8 8 0 110 8a8 8 0 0116 0zM8.287 5.906c-.778.324-2.334.994-4.666 2.01-.378.15-.577.298-.595.442-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294.26.006.549-.1.868-.32 2.179-1.471 3.304-2.214 3.374-2.23.05-.012.12-.026.166.016.047.041.042.12.037.141-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8.154 8.154 0 01-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629.093.06.183.125.27.187.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.426 1.426 0 00-.013-.315.337.337 0 00-.114-.217.526.526 0 00-.31-.093c-.3.005-.763.166-2.984 1.09z"/>
                </svg>
                Telegram Group
            </a>
        </div>
    </div>

    <!-- 创建APP日志模态框 -->
    <div id="logModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>🛠️ 创建APP日志</h2>
                <span class="close">&times;</span>
            </div>
            <div class="modal-body" id="logContent">
                <div class="log-entry log-info">等待开始创建APP...</div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary" onclick="closeLogModal()">🎯 关闭</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/@twemoji/api@latest/dist/twemoji.min.js" crossorigin="anonymous"></script>
    <script>
        let currentData = null;
        let logModal = document.getElementById("logModal");
        let logContent = document.getElementById("logContent");
        let span = document.getElementsByClassName("close")[0];
        
        // 页面加载时获取状态
        document.addEventListener('DOMContentLoaded', function() {
          twemoji.parse(document.body, { folder: 'svg', ext: '.svg' });
          Promise.all([
              refreshStatus(),
              updateProjectHomepage(),
              checkArgoStatus() 
          ]).catch(error => console.error("初始化加载失败:", error));
        });

        // 获取配置并更新链接
        async function updateProjectHomepage() {
            const linkElement = document.getElementById('projectHomepageLink');
            if (!linkElement) return;
        
            try {
                const response = await fetch('/config');
                const config = await response.json();
                const host = config.DATABRICKS_HOST;
                
                if (host && host !== '未设置') {
                    linkElement.href = host;
                    linkElement.title = '访问: ' + host; 
                    linkElement.classList.remove('btn-disabled');
                    linkElement.style.pointerEvents = 'auto';
                    console.log('项目主页链接已更新为:', host);
                } else {
                    console.warn('配置中缺少 DATABRICKS_HOST，无法设置主页链接。');
                    linkElement.classList.add('btn-danger');
                    linkElement.classList.add('disabled');
                    linkElement.style.pointerEvents = 'none';
                }
        
            } catch (error) {
                console.error('获取配置失败:', error);
                linkElement.textContent = '❌ 链接加载失败';
                linkElement.classList.add('btn-danger');
                linkElement.style.pointerEvents = 'none';
            }
        }

        // 关闭模态框的通用函数
        function closeLogModal() {
            const confirmed = confirm('确定要关闭窗口吗？这将会停止APP创建过程。');
            if (confirmed) {
                logModal.style.display = "none"; 
                if (window.appCreationSocket) {
                    window.appCreationSocket.close();
                    delete window.appCreationSocket;
                }
            }
        }
        // 关闭模态框 (点击关闭按钮)
        span.onclick = closeLogModal;
        // 点击模态框外部关闭
        window.onclick = function(event) {
            if (event.target === logModal) {
                closeLogModal();
            }
        }

        // 添加日志条目
        function addLogEntry(message, type = 'info') {
            const entry = document.createElement('div');
            entry.className = 'log-entry log-' + type;
            const timestamp = new Date().toLocaleTimeString();
            entry.innerHTML = '<span class="spinner" style="display: none;"></span>[' + timestamp + '] ' + message;
            logContent.appendChild(entry);
            logContent.scrollTop = logContent.scrollHeight;
            twemoji.parse(entry, { folder: 'svg', ext: '.svg' });
        }

        // 设置加载状态
        function setLogLoading(loading) {
            const entries = logContent.getElementsByClassName('log-entry');
            if (entries.length > 0) {
                const lastEntry = entries[entries.length - 1];
                const spinner = lastEntry.querySelector('.spinner'); 
                if (spinner) {
                    spinner.style.display = loading ? 'inline-block' : 'none';
                }
            }
        }

        // 创建或替换APP
        async function createOrReplaceApp() {
            if (!confirm('确定要创建新的APP吗？如果是免费用户且已有APP，将先删除现有APP再创建新APP。')) return;

            // 显示日志模态框
            logModal.style.display = "block";
            logContent.innerHTML = '';
            addLogEntry('⏳ 正在连接到服务器...', 'info');
            setLoading(true);
            setLogLoading(true);

            // 创建APP的函数，支持重启
            async function startAppCreation() {
                try {
                    // 建立WebSocket连接以获取实时日志
                    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = wsProtocol + '//' + window.location.host + '/create-app';
                    const socket = new WebSocket(wsUrl);

                    // 保存WebSocket连接引用，以便在关闭时使用
                    window.appCreationSocket = socket;
                    socket.onopen = function(event) {
                        setLogLoading(false);
                        addLogEntry('✅ 已连接到服务器，开始创建APP...', 'success');
                    };

                    socket.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'complete') {
                                setLogLoading(false);
                                if (data.success) {
                                    addLogEntry('✅ APP创建成功', 'success');
                                    showMessage('✅ APP创建成功', 'success');
                                } else {
                                    addLogEntry('❌ APP创建失败: ' + data.error, 'error');
                                    showMessage('❌ APP创建失败: ' + data.error, 'error');
                                }
                                socket.close();
                            } else if (data.type === 'restart') {
                                // 收到重启信号，关闭当前连接并重新开始
                                setLogLoading(false);
                                addLogEntry(data.message, 'info');
                                addLogEntry('⏳ 正在重新连接服务器...', 'info');
                                setLogLoading(true);
                                socket.close();
                                setTimeout(() => {
                                    startAppCreation();
                                }, 2000);
                            } else {
                                setLogLoading(false);
                                addLogEntry(data.message, data.type || 'info');
                                setLogLoading(true);
                            }
                        } catch (e) {
                            setLogLoading(false);
                            addLogEntry('⚠️ 收到未知消息: ' + event.data, 'info');
                        }
                    };

                    socket.onerror = function(error) {
                        setLogLoading(false);
                        addLogEntry('❌ WebSocket 连接错误: ' + error.message, 'error');
                        showMessage('❌ WebSocket 连接错误: ' + error.message, 'error');
                    };

                    socket.onclose = function(event) {
                        setLogLoading(false);
                        if (event.wasClean) {
                            addLogEntry('⚠️ 连接已关闭', 'info');
                        } else {
                            addLogEntry('❌ 连接意外中断', 'warning');
                        }
                        // 清理WebSocket连接引用
                        if (window.appCreationSocket === socket) {
                            delete window.appCreationSocket;
                        }
                        setLoading(false);
                    };

                } catch (error) {
                    setLogLoading(false);
                    addLogEntry('❌ 建立连接时出错: ' + error.message, 'error');
                    showMessage('❌ 请求失败: ' + error.message, 'error');
                    setLoading(false);
                }
            }

            // 开始创建APP
            startAppCreation();
        }

        // 检查 ARGO 状态
        async function checkArgoStatus() {
            try {
                const response = await fetch('/check-argo');
                const data = await response.json();
                
                document.getElementById('argoDomain').textContent = data.argoDomain || '-';
                document.getElementById('argoStatusCode').textContent = data.statusCode || '-';
                
                const statusCard = document.getElementById('argoStatusCard');
                const statusEl = document.getElementById('argoStatus');
                
                if (data.online) {
                    statusCard.className = 'status-card argo-online';
                    statusEl.innerHTML = '<span style="color: #28a745;">✅ 在线 </span>';
                } else {
                    statusCard.className = 'status-card argo-offline';
                    if (data.statusCode) {
                        statusEl.innerHTML = '<span style="color: #dc3545;">🔴 离线 - 状态码: ' + data.statusCode + '</span>';
                    } else {
                        statusEl.innerHTML = '<span style="color: #dc3545;">🔴 离线 - 连接失败</span>';
                    }
                }
                twemoji.parse(statusCard, { folder: 'svg', ext: '.svg' });
            } catch (error) {
                document.getElementById('argoStatus').innerHTML = '<span style="color: #dc3545;">❌ 检查失败</span>';
            }
        }
       
        // 测试 Telegram 通知
        async function testNotification() {
            setLoading(true);
            try {
                const response = await fetch('/test-notification', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    showMessage('✅ 测试通知发送成功，请检查 Telegram', 'success');
                } else {
                    showMessage('❌ 测试通知发送失败: ' + data.error, 'error');
                }
            } catch (error) {
                showMessage('❌ 请求失败: ' + error.message, 'error');
            } finally {
                setLoading(false);
            }
        }
             
        // 刷新 Databricks 状态
        async function refreshStatus() {
            setLoading(true);
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                if (data.success) {
                    currentData = data;
                    updateStats(data.results);
                    updateAppsList(data.results);
                    updateLastUpdated(); // 确保更新时间
                    showMessage('✅ Databricks 状态刷新成功', 'success');
                } else {
                    showMessage('❌ 刷新失败: ' + data.error, 'error');
                }
            } catch (error) {
                showMessage('❌ 请求失败: ' + error.message, 'error');
            } finally {
                await checkArgoStatus(); 
                setLoading(false);
            }
        }
        
        // 启动停止的 Apps
        async function startStoppedApps() {
            if (!confirm('⚠️ 确定要启动所有停止的 Apps 吗？')) return;
            
            setLoading(true);
            try {
                const response = await fetch('/start', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    showMessage('✅ 启动操作完成', 'success');
                    setTimeout(refreshStatus, 2000);
                } else {
                    showMessage('❌ 启动失败: ' + data.error, 'error');
                }
            } catch (error) {
                showMessage('❌ 请求失败: ' + error.message, 'error');
            } finally {
                await checkArgoStatus();
                setLoading(false);
            }
        }

        // 智能检查
        async function checkAndStart() {
            setLoading(true);
            try {
                const response = await fetch('/check');
                const data = await response.json();
                
                if (data.success) {
                    let message = '✅ 智能检查完成: ' + data.message;
                    if (data.argoStatus === 'offline' && data.results) {
                        message += ' (✅ 处理了 ' + data.results.length + ' 个 Apps)';
                    }
                    showMessage(message, 'success');
                    
                    // 刷新 ARGO 状态
                    checkArgoStatus();
                    
                    // 如果检查了 Databricks，刷新状态显示
                    if (data.results && data.results.length > 0) {
                        setTimeout(refreshStatus, 2000);
                    }
                } else {
                    showMessage('❌ 检查失败: ' + data.error, 'error');
                }
            } catch (error) {
                showMessage('❌ 请求失败: ' + error.message, 'error');
            } finally {
                await checkArgoStatus();
                setLoading(false);
            }
        }
        
        // 显示刷新状态的消息
        function showMessage(message, type) {
            const container = document.getElementById('messageContainer');
            const messageEl = document.createElement('div');
            messageEl.className = type === 'error' ? 'error' : 'success';
            messageEl.textContent = message;
            container.appendChild(messageEl);
            twemoji.parse(messageEl, { folder: 'svg', ext: '.svg' });
            setTimeout(function() { messageEl.remove(); }, 5000);
        }
        
        // 显示加载状态
        function setLoading(loading) {
            const buttons = document.querySelectorAll('.btn');
            if (loading) {
                buttons.forEach(function(btn) { btn.disabled = true; });
            } else {
                buttons.forEach(function(btn) { btn.disabled = false; });
            }
        }
        
        // 更新统计信息
        function updateStats(data) {
          const container = document.getElementById('statsContainer');
          const summary = data.summary;
      
          container.innerHTML = [
              '<div class="stat-card">',
                  '<div class="stat-number">' + summary.total + '</div>',
                  '<div class="stat-label">📦 Apps 数量</div>',
              '</div>',
              '<div class="stat-card">',
                  '<div class="stat-number" style="color: #28a745;">' + summary.active + '</div>',
                  '<div class="stat-label">🟢 运行中</div>',
              '</div>',
              '<div class="stat-card">',
                  '<div class="stat-number" style="color: #dc3545;">' + summary.stopped + '</div>',
                  '<div class="stat-label">🔴 已停止</div>',
              '</div>',
              '<div class="stat-card">',
                  '<div class="stat-number" style="color: #ffc107;">' + summary.unknown + '</div>',
                  '<div class="stat-label">⚠️ 状态未知</div>',
              '</div>',
              '<div class="stat-card last-updated-card">',
                  '<div class="stat-number" id="lastUpdatedCardTime">-</div>',
                  '<div class="stat-label">🕒 最后更新</div>',
              '</div>'
          ].join('');
          twemoji.parse(container, { folder: 'svg', ext: '.svg' });
          updateLastUpdated(true); // 创建卡片后调用更新时间函数
        }

        // 更新 Apps 列表
        function updateAppsList(data) {
            const container = document.getElementById('appsContainer');
            const apps = data.apps;

            if (apps.length === 0) {
              container.innerHTML = titleHtml + '<div class="loading">没有找到任何 Apps</div>';
              return;
            }
            
            let html = [
                '<table class="apps-table">',
                '<thead>',
                '<tr>',
                '<th>📦 App 名称</th>',
                '<th>📊 状态</th>',
                '<th>🆔 App ID</th>',
                '<th>🕒 创建时间</th>',
                '</tr>',
                '</thead>',
                '<tbody>'
            ].join('');
            
            apps.forEach(function(app) {
                const stateClass = 'state-' + app.state.toLowerCase();
                const createDate = app.createdAt ? new Date(app.createdAt).toLocaleString() : '未知';
                
                html += [
                    '<tr>',
                    '<td><strong>' + app.name + '</strong></td>',
                    '<td>',
                    '<span class="state-badge ' + stateClass + '">',
                    app.state,
                    '</span>',
                    '</td>',
                    '<td><code>' + app.id + '</code></td>',
                    '<td>' + createDate + '</td>',
                    '</tr>'
                ].join('');
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
            twemoji.parse(container, { folder: 'svg', ext: '.svg' });
        }
       
        // 最后更新时间
        function updateLastUpdated() {
            const now = new Date();
            const timeString = now.toLocaleDateString() + '<br>' + now.toLocaleTimeString(); 
            const lastUpdatedCardElement = document.getElementById('lastUpdatedCardTime'); 
            if (lastUpdatedCardElement) {
                lastUpdatedCardElement.innerHTML = timeString; // 使用 innerHTML 来识别 <br>
            }
        }
        
        // 每60分钟自动刷新一次
        setInterval(refreshStatus, 60 * 60 * 1000);
    </script>
</body>
</html>
  `;
}

// 创建或替换APP的后端处理函数
async function handleCreateOrReplaceApp(config, logStream) {
  const { DATABRICKS_HOST, DATABRICKS_TOKEN } = config;
  let creationAttempts = 0;
  const maxCreationAttempts = 200;

  // 心跳定时器
  let heartbeatInterval;

  // 发送日志消息的函数
  function sendLog(message, type = 'info') {
    if (logStream && !logStream.isClosed()) {
      try {
        logStream.send(JSON.stringify({ type, message }));
      } catch (e) {
        // 发送失败可能是因为连接已关闭
      }
    }
    console.log('[' + type + '] ' + message);
  }

  // 检查是否已取消的函数
  function isCancelled() {
    return logStream && logStream.isClosed();
  }

  // 启动心跳机制
  function startHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
    }

    heartbeatInterval = setInterval(() => {
      if (logStream && !logStream.isClosed()) {
        try {
          logStream.send(JSON.stringify({ type: 'heartbeat', message: '保持连接活跃' }));
        } catch (e) {
          // 发送心跳失败，可能是连接已关闭
          clearInterval(heartbeatInterval);
        }
      } else {
        clearInterval(heartbeatInterval);
      }
    }, 45000); // 每45秒发送一次心跳
  }

  // 停止心跳机制
  function stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  }

  try {
    // 启动心跳机制
    startHeartbeat();

    // 先获取现有的APP列表
    const apps = await getAppsList(config);

    // 检查是否已取消
    if (isCancelled()) {
      sendLog('操作已被用户取消', 'warning');
      throw new Error('操作已被用户取消');
    }

    // 如果没有APP，直接创建新APP
    if (apps.length === 0) {
      sendLog('没有发现现有APP，直接创建新APP', 'info');
    } 
    // 如果有APP，检查APP状态，只在状态为ERROR时删除并创建APP
    else {
      sendLog('检测到 ' + apps.length + ' 个现有APP，开始检查APP状态...', 'info');

      // 检查每个APP的状态
      let hasErrorApp = false;
      for (const app of apps) {
        // 检查是否已取消
        if (isCancelled()) {
          sendLog('操作已被用户取消', 'warning');
          throw new Error('操作已被用户取消');
        }

        const appName = app.name;
        sendLog('正在检查APP状态: ' + appName + '，当前状态: ' + app.state, 'info');
        
        // 只有当APP状态为ERROR时才标记为需要删除
        if (app.state === 'ERROR') {
          hasErrorApp = true;
          sendLog('发现处于ERROR状态的APP: ' + appName, 'warning');
        }
      }

      // 只有当存在ERROR状态的APP时才执行删除和创建操作
      if (hasErrorApp) {
        sendLog('发现处于ERROR状态的APP，开始删除...', 'info');

        // 删除所有处于ERROR状态的APP
        for (const app of apps) {
          // 只删除处于ERROR状态的APP
          if (app.state === 'ERROR') {
            // 检查是否已取消
            if (isCancelled()) {
              sendLog('操作已被用户取消', 'warning');
              throw new Error('操作已被用户取消');
            }

            const appName = app.name;
            const encodedAppName = encodeURIComponent(appName);
            const deleteUrl = DATABRICKS_HOST + '/api/2.0/apps/' + encodedAppName;

            sendLog('正在删除处于ERROR状态的APP: ' + appName, 'info');

            const deleteResponse = await fetch(deleteUrl, {
              method: 'DELETE',
              headers: {
                'Authorization': 'Bearer ' + DATABRICKS_TOKEN,
                'Content-Type': 'application/json',
              }
            });

            // 检查是否已取消
            if (isCancelled()) {
              sendLog('操作已被用户取消', 'warning');
              throw new Error('操作已被用户取消');
            }

            if (!deleteResponse.ok) {
              const errorText = await deleteResponse.text();
              sendLog('删除APP ' + appName + ' 失败: ' + errorText, 'error');
              throw new Error('删除APP ' + appName + ' 失败: ' + errorText);
            }

            sendLog('成功发送删除APP请求: ' + appName, 'success');
          }
        }

        // 循环检查APP是否已删除，每35秒检查一次，直到删除完毕
        sendLog('开始检查APP是否已删除...', 'info');
        let remainingApps;
        do {
          // 检查是否已取消
          if (isCancelled()) {
            sendLog('操作已被用户取消', 'warning');
            throw new Error('操作已被用户取消');
          }

          sendLog('等待35秒后检查APP删除状态...', 'info');
          // 等待35秒，但也要能响应取消
          for (let i = 0; i < 35; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            if (isCancelled()) {
              sendLog('操作已被用户取消', 'warning');
              throw new Error('操作已被用户取消');
            }
          }

          remainingApps = await getAppsList(config);
          // 只计算仍处于ERROR状态的APP
          const errorApps = remainingApps.filter(app => app.state === 'ERROR');
          if (errorApps.length > 0) {
            sendLog('仍有 ' + errorApps.length + ' 个处于ERROR状态的APP未删除，继续等待...', 'warning');
          } else {
            sendLog('所有处于ERROR状态的APP已成功删除', 'success');
          }
        } while (remainingApps.some(app => app.state === 'ERROR') && !isCancelled());
      } else {
        // 如果没有ERROR状态的APP，直接结束流程
        sendLog('没有发现处于ERROR状态的APP，跳过删除和创建步骤，流程结束', 'info');
        stopHeartbeat(); // 停止心跳
        return {
          success: true,
          message: '没有发现处于ERROR状态的APP，跳过删除和创建步骤',
          attempts: 0
        };
      }
    }

    // 检查是否已取消
    if (isCancelled()) {
      sendLog('操作已被用户取消', 'warning');
      throw new Error('操作已被用户取消');
    }

    // 创建新的APP
    const createUrl = DATABRICKS_HOST + '/api/2.0/apps';
    // 将APP名称改为小写"us"
    const newAppName = "us";

    // 这里使用一个简单的示例配置创建APP
    const appConfig = {
      name: newAppName,
      spec: {
        resources: {
          cpu: 0.5,
          memory: "1Gi"
        },
        serve: {
          endpoint: {
            name: "api",
            type: "HTTP",
            port: 8080,
            route: "/",
            timeout: "30s"
          }
        }
      }
    };

    sendLog('开始尝试创建新APP: ' + newAppName, 'info');

    // 循环尝试创建APP，最多尝试200次
    while (creationAttempts < maxCreationAttempts && !isCancelled()) {
      // 检查是否已取消
      if (isCancelled()) {
        sendLog('操作已被用户取消', 'warning');
        throw new Error('操作已被用户取消');
      }

      creationAttempts++;
      sendLog('第 ' + creationAttempts + ' 次尝试创建APP...', 'info');

      // 每10次尝试后断开连接并重新开始
      if (creationAttempts % 10 === 0) {
        sendLog('已尝试创建APP ' + creationAttempts + ' 次，为避免请求过多，将断开连接并重新开始...', 'info');
        // 发送重新开始信号
        if (logStream && !logStream.isClosed()) {
          try {
            logStream.send(JSON.stringify({
              type: 'restart',
              message: '为避免请求过多，断开连接并重新开始创建流程',
              restart: true
            }));
          } catch (e) {
            // 发送失败可能是因为连接已关闭
          }
        }
        // 停止心跳
        stopHeartbeat();
        // 返回重启信号
        return {
          restart: true,
          message: '为避免请求过多，断开连接并重新开始创建流程',
          attempts: creationAttempts
        };
      }

      const createResponse = await fetch(createUrl, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + DATABRICKS_TOKEN,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(appConfig)
      });

      // 检查是否已取消
      if (isCancelled()) {
        sendLog('操作已被用户取消', 'warning');
        throw new Error('操作已被用户取消');
      }

      const responseText = await createResponse.text();

      if (createResponse.ok) {
        sendLog('第 ' + creationAttempts + ' 次尝试创建APP成功', 'success');

        let createdApp;
        try {
          createdApp = JSON.parse(responseText);
        } catch (e) {
          sendLog("创建APP响应: " + responseText, 'info');
          throw new Error('无法解析创建APP的响应: ' + e.message);
        }

        sendLog('成功创建APP: ' + createdApp.name, 'success');

        // 检查APP状态，如果发现错误则删除并重新创建
        sendLog('检查新创建的APP状态...', 'info');
        let retries = 0;
        const maxRetries = 3;
        let appStatus = null;

        do {
          // 检查是否已取消
          if (isCancelled()) {
            sendLog('操作已被用户取消', 'warning');
            throw new Error('操作已被用户取消');
          }

          try {
            // 等待一段时间让APP初始化
            sendLog('等待30秒后检查APP状态...', 'info');
            // 等待30秒，但也要能响应取消
            for (let i = 0; i < 30; i++) {
              await new Promise(resolve => setTimeout(resolve, 1000));
              if (isCancelled()) {
                sendLog('操作已被用户取消', 'warning');
                throw new Error('操作已被用户取消');
              }
            }

            // 获取APP详细信息
            const appDetailsUrl = DATABRICKS_HOST + '/api/2.0/apps/' + newAppName;
            const appDetailsResponse = await fetch(appDetailsUrl, {
              method: 'GET',
              headers: {
                'Authorization': 'Bearer ' + DATABRICKS_TOKEN,
                'Content-Type': 'application/json',
              }
            });

            // 检查是否已取消
            if (isCancelled()) {
              sendLog('操作已被用户取消', 'warning');
              throw new Error('操作已被用户取消');
            }

            if (appDetailsResponse.ok) {
              const appDetails = await appDetailsResponse.json();
              appStatus = appDetails.compute_status?.state || 'UNKNOWN';
              sendLog('APP ' + newAppName + ' 当前状态: ' + appStatus, 'info');

              // 检查是否有错误状态
              if (appStatus === 'ERROR' || appStatus === 'FAILED') {
                sendLog('APP ' + newAppName + ' 处于错误状态，准备删除并重新创建...', 'warning');

                // 删除出错的APP
                const encodedAppName = encodeURIComponent(newAppName);
                const deleteUrl = DATABRICKS_HOST + '/api/2.0/apps/' + encodedAppName;

                const deleteResponse = await fetch(deleteUrl, {
                  method: 'DELETE',
                  headers: {
                    'Authorization': 'Bearer ' + DATABRICKS_TOKEN,
                    'Content-Type': 'application/json',
                  }
                });

                // 检查是否已取消
                if (isCancelled()) {
                  sendLog('操作已被用户取消', 'warning');
                  throw new Error('操作已被用户取消');
                }

                if (!deleteResponse.ok) {
                  const errorText = await deleteResponse.text();
                  sendLog('删除出错的APP ' + newAppName + ' 失败: ' + errorText, 'error');
                  throw new Error('删除出错的APP ' + newAppName + ' 失败: ' + errorText);
                }

                sendLog('已删除出错的APP: ' + newAppName, 'success');

                // 等待删除完成
                sendLog('等待35秒后重新创建APP...', 'info');
                // 等待35秒，但也要能响应取消
                for (let i = 0; i < 35; i++) {
                  await new Promise(resolve => setTimeout(resolve, 1000));
                  if (isCancelled()) {
                    sendLog('操作已被用户取消', 'warning');
                    throw new Error('操作已被用户取消');
                  }
                }

                // 重新开始创建循环
                break;
              } else if (appStatus === 'STARTING') {
                // 如果APP状态是STARTING，等待30秒后再次检查
                sendLog('APP ' + newAppName + ' 正在启动中，30秒后再次检查状态...', 'info');

                // 等待30秒，但也要能响应取消
                for (let i = 0; i < 30; i++) {
                  await new Promise(resolve => setTimeout(resolve, 1000));
                  if (isCancelled()) {
                    sendLog('操作已被用户取消', 'warning');
                    throw new Error('操作已被用户取消');
                  }
                }

                // 继续下一次循环检查状态
                continue;
              } else if (appStatus === 'ACTIVE' || appStatus === 'DEPLOYING') {
                // APP状态正常，跳出循环
                sendLog('APP创建完成且状态正常: ' + appStatus, 'success');
                stopHeartbeat(); // 停止心跳
                return {
                  success: true,
                  app: createdApp,
                  message: 'APP创建成功',
                  status: appStatus,
                  attempts: creationAttempts
                };
              }
            } else {
              const errorText = await appDetailsResponse.text();
              sendLog('获取APP详情失败，状态码: ' + appDetailsResponse.status + ' 错误信息: ' + errorText, 'error');
              // 如果是请求过多错误，则等待更长时间再重试
              if (appDetailsResponse.status === 429 || errorText.includes('Too many subrequests')) {
                sendLog('检测到请求过多，等待60秒后重试...', 'warning');
                for (let i = 0; i < 60; i++) {
                  await new Promise(resolve => setTimeout(resolve, 1000));
                  if (isCancelled()) {
                    sendLog('操作已被用户取消', 'warning');
                    throw new Error('操作已被用户取消');
                  }
                }

                // 如果重试后仍然有请求过多错误，我们跳出当前循环，让外层循环重新开始
                sendLog('请求过多错误持续存在，将重新开始创建流程...', 'warning');
                break;
              }
            }
          } catch (error) {
            // 检查是否已取消
            if (isCancelled()) {
              sendLog('操作已被用户取消', 'warning');
              throw new Error('操作已被用户取消');
            }

            sendLog('检查APP状态时出错: ' + error.message, 'error');

            // 如果是请求过多错误，则等待更长时间再重试
            if (error.message.includes('Too many subrequests')) {
              sendLog('检测到请求过多，等待60秒后重试...', 'warning');
              for (let i = 0; i < 60; i++) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                if (isCancelled()) {
                  sendLog('操作已被用户取消', 'warning');
                  throw new Error('操作已被用户取消');
                }
              }

              // 如果重试后仍然有请求过多错误，我们跳出当前循环，让外层循环重新开始
              sendLog('请求过多错误持续存在，将重新开始创建流程...', 'warning');
              break;
            }
          }

          retries++;
        } while (retries < maxRetries && !isCancelled());

        if (retries >= maxRetries) {
          sendLog('APP状态检查达到最大重试次数，可能存在异常', 'warning');
          // 如果达到最大重试次数，返回成功但带有警告
          stopHeartbeat(); // 停止心跳
          return {
            success: true,
            app: createdApp,
            message: 'APP创建成功，但状态检查达到最大重试次数',
            status: appStatus,
            attempts: creationAttempts
          };
        }
      } else if (responseText.includes("maximum number of apps")) {
        sendLog('第 ' + creationAttempts + ' 次尝试创建APP失败，仍检测到APP数量限制，继续重试...', 'warning');
        // 等待一段时间再重试，但也要能响应取消
        for (let i = 0; i < 35; i++) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          if (isCancelled()) {
            sendLog('操作已被用户取消', 'warning');
            throw new Error('操作已被用户取消');
          }
        }
      } else {
        sendLog('第 ' + creationAttempts + ' 次尝试创建APP失败: ' + responseText, 'error');
        throw new Error('创建APP失败: ' + responseText);
      }
    }

    // 检查是否已取消
    if (isCancelled()) {
      sendLog('操作已被用户取消', 'warning');
      throw new Error('操作已被用户取消');
    }

    // 如果达到最大尝试次数仍未成功
    if (creationAttempts >= maxCreationAttempts) {
      sendLog('创建APP失败，已达到最大尝试次数 ' + maxCreationAttempts, 'error');
      throw new Error('创建APP失败，已达到最大尝试次数 ' + maxCreationAttempts);
    }
  } catch (error) {
    sendLog('创建APP过程中出错: ' + error.message, 'error');
    stopHeartbeat(); // 停止心跳
    throw error;
  } finally {
    stopHeartbeat(); // 确保停止心跳
  }
}

// 处理创建APP的WebSocket连接
async function handleCreateAppWebSocket(request, env) {
  const webSocketPair = new WebSocketPair();
  const [client, server] = Object.values(webSocketPair);

  // 创建一个可取消的标记
  const abortController = new AbortController();

  // 创建一个包含send方法的对象来模拟流
  const logStream = {
    send: (message) => {
      try {
        if (server.readyState === WebSocket.READY_STATE_OPEN) {
          server.send(message);
        }
      } catch (e) {
        console.error('WebSocket发送消息失败:', e);
      }
    },
    isClosed: () => abortController.signal.aborted
  };

  // 监听连接关闭事件
  server.addEventListener('close', () => {
    console.log('WebSocket连接已关闭，触发取消信号');
    abortController.abort();
  });

  server.addEventListener('error', () => {
    console.log('WebSocket连接错误，触发取消信号');
    abortController.abort();
  });

  server.accept();

  // 启动APP创建过程
  const config = getConfig(env);

  // 在后台执行APP创建任务
  (async () => {
    try {
      const result = await handleCreateOrReplaceApp(config, logStream);
      if (!abortController.signal.aborted) {
        server.send(JSON.stringify({
          type: 'complete',
          success: true,
          message: 'APP创建完成',
          result: result
        }));
      }
    } catch (error) {
      // 只有在连接未关闭且不是取消操作的情况下才发送错误信息
      if (!abortController.signal.aborted && !error.message.includes('操作已被用户取消')) {
        try {
          server.send(JSON.stringify({
            type: 'complete',
            success: false,
            error: error.message
          }));
        } catch (e) {
          console.error('发送错误信息失败:', e);
        }
      }
    } finally {
      try {
        if (server.readyState === WebSocket.READY_STATE_OPEN) {
          server.close();
        }
      } catch (e) {
        console.error('关闭WebSocket连接时出错:', e);
      }
    }
  })();

  return new Response(null, {
    status: 101,
    webSocket: client,
  });
}

// 测试通知函数
async function testNotification(config) {
  const message = `🔔 <b>Databricks Apps 监控测试通知</b>\n\n` +
                 `✅ 这是一条测试消息\n` +
                 `🌐 ARGO域名: <code>${config.ARGO_DOMAIN}</code>\n` +
                 `⏰ 时间: ${new Date().toLocaleString('zh-CN')}\n\n` +
                 `🎉 如果你的 Telegram 配置正确，你应该能收到这条消息`;
  return await sendTelegramNotification(config, message);
}

// 检查 ARGO 状态
async function checkArgoStatusOnly(config) {
  const argoStatus = await checkArgoDomain(config.ARGO_DOMAIN);
  return {
    ...argoStatus,
    argoDomain: config.ARGO_DOMAIN
  };
}

// 主 Worker 处理器
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    
    if (path === '/' || path === '/index.html') {
      return new Response(getFrontendHTML(), {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }
    
    if (path === '/check') {
      try {
        const config = getConfig(env);
        const result = await smartCheckAndStartApps(config);
        
        return new Response(JSON.stringify({
          success: true,
          message: result.message || '检查完成',
          timestamp: new Date().toISOString(),
          argoStatus: result.argoStatus,
          statusChanged: result.statusChanged,
          results: result.results || []
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          success: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }
    
    if (path === '/check-argo') {
      try {
        const config = getConfig(env);
        const result = await checkArgoStatusOnly(config);
        return new Response(JSON.stringify(result), {
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          online: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }
    
    if (path === '/start') {
      try {
        const config = getConfig(env);
        const result = await startStoppedApps(config);
        return new Response(JSON.stringify({
          success: true,
          message: '启动操作完成',
          timestamp: new Date().toISOString(),
          results: result
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          success: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }
    
    if (path === '/status') {
      try {
        const config = getConfig(env);
        const result = await getAppsStatus(config);
        return new Response(JSON.stringify({
          success: true,
          message: '状态获取完成',
          timestamp: new Date().toISOString(),
          results: result
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          success: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }
    
    if (path === '/config') {
      const config = getConfig(env);
      const maskedToken = config.DATABRICKS_TOKEN ? 
        config.DATABRICKS_TOKEN.substring(0, 10) + '...' : '未设置';
      const maskedBotToken = config.BOT_TOKEN ? 
        config.BOT_TOKEN.substring(0, 10) + '...' : '未设置';
      
      return new Response(JSON.stringify({
        DATABRICKS_HOST: config.DATABRICKS_HOST,
        DATABRICKS_TOKEN: maskedToken,
        CHAT_ID: config.CHAT_ID || '未设置',
        BOT_TOKEN: maskedBotToken,
        ARGO_DOMAIN: config.ARGO_DOMAIN || '未设置',
        source: config.source
      }, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    if (path === '/test-notification') {
      try {
        const config = getConfig(env);
        const success = await testNotification(config);
        
        if (success) {
          return new Response(JSON.stringify({
            success: true,
            message: '测试通知发送成功'
          }), {
            headers: { 'Content-Type': 'application/json' }
          });
        } else {
          return new Response(JSON.stringify({
            success: false,
            error: '测试通知发送失败，请检查 Telegram 配置'
          }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
          });
        }
      } catch (error) {
        return new Response(JSON.stringify({
          success: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }

    // 处理创建/替换APP请求的路由
    if (path === '/create-app') {
      // 检查是否是WebSocket升级请求
      const upgradeHeader = request.headers.get('Upgrade');
      if (upgradeHeader === 'websocket') {
        return handleCreateAppWebSocket(request, env);
      }

      // 保持原有的POST请求处理
      try {
        const config = getConfig(env);
        const result = await handleCreateOrReplaceApp(config);

        return new Response(JSON.stringify({
          success: true,
          message: 'APP创建成功',
          app: result.app,
          timestamp: new Date().toISOString()
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          success: false,
          error: error.message
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }    
    
    return new Response(JSON.stringify({
      error: '路由不存在',
      available_routes: [
        { path: '/', method: 'GET', description: '前端管理界面' },
        { path: '/status', method: 'GET', description: '获取当前 Apps 状态' },
        { path: '/check', method: 'GET', description: '智能检查（ARGO优先）' },
        { path: '/check-argo', method: 'GET', description: '检查 ARGO 域名状态' },
        { path: '/start', method: 'POST', description: '手动启动所有停止的 Apps' },
        { path: '/config', method: 'GET', description: '查看当前配置信息' },
        { path: '/test-notification', method: 'POST', description: '测试 Telegram 通知' },
        { path: '/create-app', method: 'POST', description: '创建/替换 APP' }
      ]
    }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  },

  // 定时任务函数
  async scheduled(event, env, ctx) {
    console.log('开始定时智能检查...');
    
    try {
      const config = getConfig(env);
      const result = await smartCheckAndStartApps(config);
      
      console.log('定时检查完成:', result.message);
      if (result.statusChanged) {
        console.log('ARGO 状态发生变化，已处理');
      }
    } catch (error) {
      console.error('定时检查过程中出错:', error);
    }
  }
};
