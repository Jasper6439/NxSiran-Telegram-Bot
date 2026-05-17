/**
 * AI Router Pool - LoveSupremacy Universe
 * 免费优先的多平台模型路由池
 * 
 * 端口: 8081
 * 路由:
 *   POST /v1/chat/completions    -> 对话路由
 *   POST /v1/images/generations  -> 生图路由
 * 
 * 策略: 免费优先，禁止收费模型
 * 新增: PAI EAS SD WebUI (LoRA 自定义角色生图)
 */

const http = require('http');
const https = require('https');
const url = require('url');

// ============ 配置 ============
const PORT = 8081;
const TIMEOUT = 30000; // 30s

// 从环境变量读取 API Keys（由 systemd 注入）
const ENV = process.env;

// 对话路由池（优先级从高到低，免费优先）
const CHAT_POOL = [
  {
    name: 'OpenRouter-Free',
    base: 'https://openrouter.ai/api/v1',
    key: ENV.OPENROUTER_API_KEY,
    model: ENV.OPENROUTER_MODEL || 'openrouter/auto',
    type: 'chat',
    priority: 1
  },
  {
    name: 'SenseNova-Flash',
    base: 'https://api.sensenova.cn/v1',
    key: ENV.SENSENOVA_API_KEY,
    model: ENV.SENSENOVA_MODEL || 'sensenova-6.7-flash-lite',
    type: 'chat',
    priority: 2
  },
  {
    name: 'Gemini-Free',
    base: 'https://generativelanguage.googleapis.com/v1beta',
    key: ENV.GEMINI_API_KEY,
    model: 'gemini-2.0-flash-lite',
    type: 'chat',
    priority: 3
  },
  {
    name: 'SiliconFlow-Backup',
    base: 'https://api.siliconflow.cn/v1',
    key: ENV.SILICONFLOW_API_KEY,
    model: ENV.SILICONFLOW_MODEL || 'deepseek-ai/DeepSeek-V4-Flash',
    type: 'chat',
    priority: 99 // 兜底
  }
];

// 生图路由池（免费优先，禁止收费）
// 优先级: PAI-EAS-SDWebUI(LoRA) > SenseNova-U1 > SiliconFlow-ZImage
const IMAGE_POOL = [
  {
    name: 'PAI-EAS-SDWebUI',
    base: 'https://sd-lsu-1243031680433943.cn-shanghai.pai-eas.aliyuncs.com',
    key: ENV.EAS_SD_TOKEN || 'ec1b31af2f021d4cae4132905f5ebbcabb4c85bb',
    type: 'image',
    priority: 1,
    lora: {
      // LoRA 触发词配置，可切换
      trigger: ENV.EAS_SD_LORA_TRIGGER || '<lora:adam:0.8>, ',
      defaultPrompt: 'masterpiece, best quality,',
      defaultNegative: 'lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, bad feet, mutation, deformed, extra limbs, extra arms, extra legs, malformed limbs, fused fingers, too many fingers, long neck, cross-eyed, mutated hands, polar lowres, bad face'
    }
  },
  {
    name: 'SenseNova-U1',
    base: 'https://token.sensenova.cn/v1',
    key: ENV.SENSENOVA_API_KEY,
    model: ENV.SENSENOVA_IMAGE_MODEL || 'sensenova-u1-fast',
    type: 'image',
    priority: 2
  },
  {
    name: 'SiliconFlow-ZImage',
    base: 'https://api.siliconflow.cn/v1',
    key: ENV.SILICONFLOW_API_KEY,
    model: ENV.SILICONFLOW_IMAGE_MODEL || 'Tongyi-MAI/Z-Image-Turbo',
    type: 'image',
    priority: 3
  }
];

// ============ 日志 ============
function log(level, msg, extra) {
  extra = extra || '';
  const ts = new Date().toISOString();
  console.log('[' + ts + '] [' + level + '] ' + msg + ' ' + extra);
}

// ============ HTTP 请求工具 ============
function request(targetUrl, options, body) {
  options = options || {};
  body = body || null;
  return new Promise(function(resolve, reject) {
    const parsed = url.parse(targetUrl);
    const client = parsed.protocol === 'https:' ? https : http;
    const req = client.request({
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.path,
      method: options.method || 'GET',
      headers: options.headers || {},
      timeout: TIMEOUT
    }, function(res) {
      let data = '';
      res.on('data', function(chunk) { data += chunk; });
      res.on('end', function() {
        resolve({ status: res.statusCode, headers: res.headers, body: data });
      });
    });
    req.on('error', reject);
    req.on('timeout', function() { req.destroy(); reject(new Error('timeout')); });
    if (body) req.write(body);
    req.end();
  });
}

// ============ 对话路由 ============
async function routeChat(body) {
  for (const provider of CHAT_POOL) {
    if (!provider.key) {
      log('SKIP', provider.name + ': no API key');
      continue;
    }

    try {
      log('TRY', provider.name, provider.model);

      // 构建请求体
      const reqBody = JSON.parse(JSON.stringify(body));
      reqBody.model = provider.model;

      // Gemini 特殊处理
      if (provider.name === 'Gemini-Free') {
        const geminiBody = {
          contents: (reqBody.messages || []).map(function(m) {
            return {
              role: m.role === 'assistant' ? 'model' : m.role,
              parts: [{ text: m.content }]
            };
          })
        };
        const geminiUrl = provider.base + '/models/' + provider.model + ':generateContent?key=' + provider.key;
        const res = await request(geminiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        }, JSON.stringify(geminiBody));

        if (res.status === 200) {
          const data = JSON.parse(res.body);
          const text = (data.candidates && data.candidates[0] && data.candidates[0].content && data.candidates[0].content.parts && data.candidates[0].content.parts[0] && data.candidates[0].content.parts[0].text) || '';
          return {
            status: 200,
            body: JSON.stringify({
              choices: [{ message: { role: 'assistant', content: text } }],
              model: provider.model,
              provider: provider.name
            })
          };
        }
        throw new Error('Gemini ' + res.status + ': ' + res.body);
      }

      // 标准 OpenAI 格式
      const apiUrl = provider.base + '/chat/completions';
      const res = await request(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + provider.key
        }
      }, JSON.stringify(reqBody));

      if (res.status >= 200 && res.status < 300) {
        // 注入 provider 信息
        const data = JSON.parse(res.body);
        data.provider = provider.name;
        return { status: res.status, body: JSON.stringify(data) };
      }

      log('FAIL', provider.name, res.status + ': ' + res.body.slice(0, 200));
    } catch (err) {
      log('ERR', provider.name, err.message);
    }
  }

  return {
    status: 503,
    body: JSON.stringify({ error: 'All providers failed or no API keys configured' })
  };
}

// ============ SD WebUI 原生 API 生图路由 ============
async function routeSDWebUI(body, provider) {
  try {
    log('TRY', provider.name, 'SD WebUI txt2img');

    const lora = provider.lora || {};
    const userPrompt = body.prompt || '';
    const fullPrompt = (lora.trigger || '') + (lora.defaultPrompt || '') + ' ' + userPrompt;
    const negativePrompt = body.negative_prompt || lora.defaultNegative || '';

    // 解析 size (默认 512x768)
    let width = 512, height = 768;
    if (body.size) {
      const parts = body.size.split('x');
      const w = Number(parts[0]), h = Number(parts[1]);
      if (w && h) { width = w; height = h; }
    }

    // 构建 SD WebUI 原生请求体
    const sdBody = {
      prompt: fullPrompt,
      negative_prompt: negativePrompt,
      steps: body.steps || 28,
      cfg_scale: body.cfg_scale || 7,
      width: width,
      height: height,
      sampler_index: body.sampler || 'DPM++ 2M Karras',
      seed: body.seed || -1,
      n_iter: body.n || 1,
      batch_size: 1,
      restore_faces: false,
      tiling: false,
      send_images: true,
      save_images: false
    };

    const sdUrl = provider.base + '/sdapi/v1/txt2img';
    const headers = { 'Content-Type': 'application/json' };
    if (provider.key) {
      headers['Authorization'] = provider.key;  // EAS Token 直接放 Authorization
    }

    const res = await request(sdUrl, {
      method: 'POST',
      headers: headers
    }, JSON.stringify(sdBody));

    if (res.status >= 200 && res.status < 300) {
      const sdData = JSON.parse(res.body);
      const images = sdData.images || [];
      if (images.length === 0) {
        throw new Error('SD WebUI returned no images');
      }

      // 转换为 OpenAI images/generations 格式
      const openaiData = images.map(function(imgBase64) {
        return { url: 'data:image/png;base64,' + imgBase64 };
      });

      return {
        status: 200,
        body: JSON.stringify({
          created: Math.floor(Date.now() / 1000),
          data: openaiData,
          provider: provider.name,
          // 额外信息供调试
          _sd_params: {
            prompt: fullPrompt,
            negative_prompt: negativePrompt,
            steps: sdBody.steps,
            width: sdBody.width,
            height: sdBody.height
          }
        })
      };
    }

    log('FAIL', provider.name, res.status + ': ' + res.body.slice(0, 300));
    throw new Error('SD WebUI ' + res.status + ': ' + res.body.slice(0, 200));
  } catch (err) {
    log('ERR', provider.name, err.message);
    throw err;
  }
}

// ============ 生图路由 ============
async function routeImage(body) {
  for (const provider of IMAGE_POOL) {
    if (!provider.key && provider.name !== 'PAI-EAS-SDWebUI') {
      log('SKIP', provider.name + ': no API key');
      continue;
    }

    try {
      // PAI EAS SD WebUI 原生 API 路由
      if (provider.name === 'PAI-EAS-SDWebUI') {
        return await routeSDWebUI(body, provider);
      }

      log('TRY', provider.name, provider.model);

      // SenseNova U1 Fast 独立接口
      if (provider.name === 'SenseNova-U1') {
        const reqBody = {
          model: provider.model,
          prompt: body.prompt || '',
          n: body.n || 1,
          size: body.size || '1024x1024'
        };
        const res = await request(provider.base + '/images/generations', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + provider.key
          }
        }, JSON.stringify(reqBody));

        if (res.status >= 200 && res.status < 300) {
          const data = JSON.parse(res.body);
          data.provider = provider.name;
          return { status: res.status, body: JSON.stringify(data) };
        }
        log('FAIL', provider.name, res.status + ': ' + res.body.slice(0, 200));
        continue;
      }

      // SiliconFlow 标准 images/generations
      const reqBody = {
        model: provider.model,
        prompt: body.prompt || '',
        n: body.n || 1,
        size: body.size || '1024x1024'
      };
      const res = await request(provider.base + '/images/generations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + provider.key
        }
      }, JSON.stringify(reqBody));

      if (res.status >= 200 && res.status < 300) {
        const data = JSON.parse(res.body);
        data.provider = provider.name;
        return { status: res.status, body: JSON.stringify(data) };
      }
      log('FAIL', provider.name, res.status + ': ' + res.body.slice(0, 200));
    } catch (err) {
      log('ERR', provider.name, err.message);
    }
  }

  return {
    status: 503,
    body: JSON.stringify({ error: 'All image providers failed or no API keys configured' })
  };
}

// ============ HTTP Server ============
const server = http.createServer(async function(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // 健康检查
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      chat_providers: CHAT_POOL.filter(function(p) { return p.key; }).map(function(p) { return p.name; }),
      image_providers: IMAGE_POOL.filter(function(p) { return p.key; }).map(function(p) { return p.name; })
    }));
    return;
  }

  if (req.method !== 'POST') {
    res.writeHead(405);
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }

  // 读取 body
  let body = '';
  req.on('data', function(chunk) { body += chunk; });
  await new Promise(function(resolve) { req.on('end', resolve); });

  let jsonBody = {};
  try { jsonBody = JSON.parse(body); } catch(e) {}

  let result;
  if (req.url === '/v1/chat/completions') {
    log('REQ', 'chat', jsonBody.model || 'default');
    result = await routeChat(jsonBody);
  } else if (req.url === '/v1/images/generations') {
    log('REQ', 'image', (jsonBody.prompt && jsonBody.prompt.slice(0, 30)) || 'empty');
    result = await routeImage(jsonBody);
  } else {
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  res.writeHead(result.status, { 'Content-Type': 'application/json' });
  res.end(result.body);
});

server.listen(PORT, '0.0.0.0', function() {
  log('START', 'AI Router Pool running on http://0.0.0.0:' + PORT);
  log('INFO', 'Chat providers: ' + (CHAT_POOL.filter(function(p) { return p.key; }).map(function(p) { return p.name; }).join(', ') || 'NONE'));
  log('INFO', 'Image providers: ' + (IMAGE_POOL.filter(function(p) { return p.key; }).map(function(p) { return p.name; }).join(', ') || 'NONE'));
});
