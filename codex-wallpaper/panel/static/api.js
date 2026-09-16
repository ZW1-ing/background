(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CodexWallpaperApi = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  async function requestJson(url, payload, fetchImpl = fetch) {
    const response = await fetchImpl(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const error = new Error(data.error || "操作失败");
      error.output = typeof data.output === "string" ? data.output : "";
      error.data = data;
      throw error;
    }
    return data;
  }

  function errorOutput(error, fallback = "操作失败") {
    const output = typeof error?.output === "string" ? error.output.trim() : "";
    if (output) {
      return output;
    }
    return error?.message || fallback;
  }

  return { requestJson, errorOutput };
});
