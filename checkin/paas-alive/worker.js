import moment from 'https://cdn.jsdelivr.net/npm/moment-timezone@0.5.34/builds/moment-timezone-with-data.min.js';

// 从环境变量加载 URLs，每行一个地址
async function handleRequest(event, env) {
  // 获取环境变量
  const urls = (env['24_URLS'] || '').split('\n').map(url => url.trim()).filter(url => url);  // 24小时不间断访问的地址
  const websites = (env['NO24_URLS'] || '').split('\n').map(url => url.trim()).filter(url => url);  // 01:00至05:00暂停访问的地址

  // 访问网站的函数
  async function visitWebsites(websites) {
    const currentMoment = moment().tz('Asia/Hong_Kong');
    const formattedTime = currentMoment.format('YYYY-MM-DD HH:mm:ss');
    for (let url of websites) {
      try {
        const response = await fetch(url);
        console.log(`${formattedTime} 访问网站成功: ${url} - Status code: ${response.status}`);
      } catch (error) {
        console.error(`${formattedTime} 访问网站失败 ${url}: ${error.message}`);
      }
    }
  }

  // 访问24小时不间断的URL数组
  async function scrapeAndLog(url) {
    try {
      const response = await fetch(url);
      console.log(`${moment().tz('Asia/Hong_Kong').format('YYYY-MM-DD HH:mm:ss')} 访问网站成功: ${url} - Status code: ${response.status}`);
    } catch (error) {
      console.error(`${moment().tz('Asia/Hong_Kong').format('YYYY-MM-DD HH:mm:ss')} 访问网站失败: ${url}: ${error.message}`);
    }
  }

  // 定时器函数，控制在01:00到05:00之间暂停访问指定的网站
  async function checkAndSetTimer() {
    const currentMoment = moment().tz('Asia/Hong_Kong');
    const formattedTime = currentMoment.format('YYYY-MM-DD HH:mm:ss');
    
    // 判断是否在 1:00 到 5:00 之间
    if (currentMoment.hours() >= 1 && currentMoment.hours() < 5) {
      console.log(`停止访问：1:00 到 5:00 --- ${formattedTime}`);
      // 在1:00到5:00之间，不访问NO24_URLS中的网站
      return;
    } else {
      console.log(`执行访问任务：${formattedTime}`);
      // 在其他时间，执行访问NO24_URLS中的网站
      await visitWebsites(websites);
    }
  }

  console.log(`Worker 激活时间：${moment().tz('Asia/Hong_Kong').format('YYYY-MM-DD HH:mm:ss')}`);

  // 每次请求访问24小时不间断的URLs
  for (let url of urls) {
    await scrapeAndLog(url);
  }

  // 处理在01:00至05:00暂停访问的URLs
  await checkAndSetTimer();
  return new Response('Request processed by Cloudflare Worker!', {
    status: 200,
    headers: { 'Content-Type': 'text/plain' },
  });
}

// 在此添加 Cron Trigger 事件监听器
addEventListener('scheduled', event => {
  const env = event.env; // 确保从事件中获取环境变量
  event.waitUntil(handleRequest(event, env));
});
