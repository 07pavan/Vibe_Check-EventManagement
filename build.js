const fs = require('fs');
const api = process.env.RENDER_API_URL || 'http://127.0.0.1:8001';
const env = api.includes('127.0.0.1') ? 'development' : 'production';
const content = [
  "window.GOATTEND_API = '" + api + "/api';",
  "window.GOATTEND_ENV = '" + env + "';",
  "window.GOATTEND_VERSION = '1.0.0';"
].join('\n');
fs.writeFileSync('frontend/config.js', content);
console.log('config.js generated for ' + env + ': ' + api);