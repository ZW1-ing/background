const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");

const api = require(path.resolve(__dirname, "../panel/static/api.js"));

test("failed apply keeps the patcher output for the panel", async () => {
  const fetchImpl = async () => ({
    ok: false,
    json: async () => ({
      ok: false,
      error: "应用失败，请查看下方输出",
      output: [
        "App:   C:\\Program Files\\WindowsApps\\OpenAI.ChatGPT\\ChatGPT.exe",
        "Microsoft Store / WindowsApps 安装受系统保护，当前版本不支持修改。",
      ].join("\n"),
    }),
  });

  let error;
  try {
    await api.requestJson("/api/apply", {}, fetchImpl);
  } catch (caught) {
    error = caught;
  }

  assert.equal(error.message, "应用失败，请查看下方输出");
  assert.match(api.errorOutput(error), /Microsoft Store \/ WindowsApps/);
});
