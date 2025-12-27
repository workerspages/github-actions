// 这是一个 Cloudflare Worker 脚本，用于接收来自 Uptime Kuma 的 Webhook 请求，并将其转发到 GitHub Actions 进行处理。
// 请确保在 Cloudflare Worker 的环境变量(Secrets)中设置以下变量：
// GITHUB_TOKEN = <您的GitHub Personal Access Token>，该令牌需要有触发 GitHub Actions 的权限。
// SECRET_TOKEN = <设置的密码>，用于验证请求来源，以保护API端点的安全。
// 部署此脚本后，将 Uptime Kuma 的 Webhook URL 设置为：
// https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>

export default {
    async fetch(request, env, ctx) {
      // 只处理 POST 请求
      if (request.method !== 'POST') {
        return new Response(JSON.stringify({ message: '只允许 POST 请求' }), {
          status: 405, headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      }
  
      const url = new URL(request.url);
      const user = url.searchParams.get('user');
      const repo = url.searchParams.get('repo');
      const token = url.searchParams.get('token');
  
      // 身份验证
      const SECRET_TOKEN = env.SECRET_TOKEN;
      if (!SECRET_TOKEN) {
        console.error('安全风险：环境变量 SECRET_TOKEN 未设置！已拒绝所有请求。');
        return new Response(JSON.stringify({ message: '服务器端安全配置不完整。' }), {
          status: 500, headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      }
  
      if (token !== SECRET_TOKEN) {
        console.error(`验证失败：收到的Token "${token}" 与预设不匹配。`);
        return new Response(JSON.stringify({ message: '无效的身份验证令牌。' }), {
          status: 401, // Unauthorized
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      }
      
      // 验证 user 和 repo 参数是否存在
      if (!user || !repo) {
        const errorMessage = 'Webhook URL 中缺少 "user" 或 "repo" 查询参数。';
        console.error(errorMessage);
        return new Response(JSON.stringify({ message: errorMessage }), {
          status: 400, headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      }
      
      try {
        // 从环境变量(Secrets)中获取 GitHub PAT
        const GITHUB_TOKEN = env.GITHUB_TOKEN;
        if (!GITHUB_TOKEN) {
          const errorMessage = 'Cloudflare Worker 环境变量中未设置 GITHUB_TOKEN。';
          console.error(errorMessage);
          return new Response(JSON.stringify({ message: '服务器配置错误。' }), {
            status: 500, headers: { 'Content-Type': 'application/json; charset=utf-8' },
          });
        }
  
        // 解析来自 Uptime Kuma 的 JSON 请求体
        const uptimeKumaPayload = await request.json();
  
        // 检查是否是服务下线的通知 (status: 0 代表 Down)
        if (uptimeKumaPayload.heartbeat && uptimeKumaPayload.heartbeat.status === 0) {
          console.log(`服务 "${uptimeKumaPayload.monitor.name}" 已下线。正在转发到 GitHub 仓库: ${user}/${repo}`);
  
          const githubApiUrl = `https://api.github.com/repos/${user}/${repo}/dispatches`;
  
          // 向 GitHub 发送请求
          const githubResponse = await fetch(githubApiUrl, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${GITHUB_TOKEN}`,
              'Accept': 'application/vnd.github.v3+json',
              'Content-Type': 'application/json',
              'User-Agent': 'Cloudflare-Worker-Uptime-Kuma-Forwarder',
            },
            body: JSON.stringify({
              event_type: 'service-down-alert',
              client_payload: uptimeKumaPayload,
            }),
          });
          
          // 检查 GitHub API 的响应
          if (!githubResponse.ok) {
            const errorBody = await githubResponse.text();
            console.error(`触发 GitHub Action 失败: ${user}/${repo}。状态: ${githubResponse.status}。响应: ${errorBody}`);
            return new Response(JSON.stringify({ message: '转发到 GitHub 失败。' }), {
              status: githubResponse.status,
              headers: { 'Content-Type': 'application/json; charset=utf-8' },
            });
          }
          
          return new Response(JSON.stringify({ message: `Webhook 已成功转发到 ${user}/${repo}。` }), {
            status: 200,
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
          });
  
        } else {
          console.log('收到一个非“下线”事件或无效的请求体，已忽略。');
          return new Response(JSON.stringify({ message: '事件已忽略 (非“下线”状态)。' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
          });
        }
  
      } catch (error) {
        if (error instanceof SyntaxError) {
           return new Response(JSON.stringify({ message: '收到的 JSON 请求体无效。' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
          });
        }
        console.error(`处理 ${user}/${repo} 的 Webhook 时出错:`, error.message);
        return new Response(JSON.stringify({ message: '处理 Webhook 失败。' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      }
    },
};
