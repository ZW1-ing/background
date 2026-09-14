const DEFAULTS = {
  background: {
    zoom: 1,
    position_x: 0.5,
    position_y: 0.5,
    dim: 0,
    blur: 0,
  },
  surfaces: {
    main: 0.35,
    sidebar: 0.45,
    composer: 0.45,
    dialog: 0.6,
  },
};

const preview = document.querySelector("#preview");
const imageInput = document.querySelector("#image-input");
const dropZone = document.querySelector("#drop-zone");
const imageName = document.querySelector("#image-name");
const appStatus = document.querySelector("#app-status");
const applyButton = document.querySelector("#apply-button");
const restoreButton = document.querySelector("#restore-button");
const resetButton = document.querySelector("#reset-button");
const clearOutputButton = document.querySelector("#clear-output-button");
const autoRestart = document.querySelector("#auto-restart");
const output = document.querySelector("#output");
const toast = document.querySelector("#toast");

let uploadedImageDataUri = null;
let uploadedObjectUrl = null;
let toastTimer = null;

function setPreviewImage(url) {
  preview.style.setProperty("--preview-image", `url("${url}")`);
}

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("is-error", isError);
  toast.classList.add("is-visible");
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 4200);
}

function setOutput(text) {
  output.textContent = text || "等待操作...";
}

function configFromControls() {
  return {
    background: {
      zoom: Number(document.querySelector("#background-zoom").value) / 100,
      position_x: Number(document.querySelector("#background-x").value) / 100,
      position_y: Number(document.querySelector("#background-y").value) / 100,
      blur: Number(document.querySelector("#background-blur").value),
      dim: Number(document.querySelector("#background-dim").value) / 100,
    },
    surfaces: {
      main: Number(document.querySelector("#surface-main").value) / 100,
      sidebar: Number(document.querySelector("#surface-sidebar").value) / 100,
      composer: Number(document.querySelector("#surface-composer").value) / 100,
      dialog: Number(document.querySelector("#surface-dialog").value) / 100,
    },
  };
}

function applyConfigToControls(config) {
  const normalized = {
    background: { ...DEFAULTS.background, ...(config?.background || {}) },
    surfaces: { ...DEFAULTS.surfaces, ...(config?.surfaces || {}) },
  };
  document.querySelector("#background-zoom").value = Math.round(
    normalized.background.zoom * 100
  );
  document.querySelector("#background-x").value = Math.round(
    normalized.background.position_x * 100
  );
  document.querySelector("#background-y").value = Math.round(
    normalized.background.position_y * 100
  );
  document.querySelector("#background-blur").value = Math.round(
    normalized.background.blur
  );
  document.querySelector("#background-dim").value = Math.round(
    normalized.background.dim * 100
  );
  document.querySelector("#surface-main").value = Math.round(
    normalized.surfaces.main * 100
  );
  document.querySelector("#surface-sidebar").value = Math.round(
    normalized.surfaces.sidebar * 100
  );
  document.querySelector("#surface-composer").value = Math.round(
    normalized.surfaces.composer * 100
  );
  document.querySelector("#surface-dialog").value = Math.round(
    normalized.surfaces.dialog * 100
  );
  renderPreview();
}

function renderPreview() {
  const config = configFromControls();
  preview.style.setProperty("--preview-zoom", config.background.zoom);
  preview.style.setProperty(
    "--preview-x",
    `${config.background.position_x * 100}%`
  );
  preview.style.setProperty(
    "--preview-y",
    `${config.background.position_y * 100}%`
  );
  preview.style.setProperty("--preview-blur", `${config.background.blur}px`);
  preview.style.setProperty("--preview-dim", config.background.dim);
  preview.style.setProperty("--preview-main-opacity", config.surfaces.main);
  preview.style.setProperty(
    "--preview-sidebar-opacity",
    config.surfaces.sidebar
  );
  preview.style.setProperty(
    "--preview-composer-opacity",
    config.surfaces.composer
  );
  preview.style.setProperty(
    "--preview-dialog-opacity",
    config.surfaces.dialog
  );

  document.querySelectorAll(".slider-row").forEach((row) => {
    const input = row.querySelector("input");
    const value = row.querySelector("output");
    if (row.dataset.control === "background-blur") {
      value.textContent = `${input.value} px`;
    } else {
      value.textContent = `${input.value}%`;
    }
  });
}

function setBusy(isBusy) {
  applyButton.disabled = isBusy;
  restoreButton.disabled = isBusy;
  applyButton.textContent = isBusy ? "正在应用..." : "应用背景";
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "操作失败");
  }
  return data;
}

function describeStatus(state) {
  const status = state?.status || "";
  const match = status.match(/^App:\s+(.+)$/m);
  if (match) {
    const appName = match[1].split("/").pop();
    appStatus.textContent = `已连接 ${appName}`;
    return;
  }
  appStatus.textContent = "未检测到 Codex 或 ChatGPT 应用";
}

async function loadState() {
  try {
    const response = await fetch("/api/state");
    const state = await response.json();
    applyConfigToControls(state.config);
    describeStatus(state);
    if (state.hasImage) {
      setPreviewImage(`/api/current-image?t=${Date.now()}`);
      imageName.textContent = state.imageName || "已保存的自定义背景";
    } else {
      setPreviewImage(state.defaultImageUrl);
      imageName.textContent = "当前使用内置背景";
    }
    setOutput(state.status || "等待操作...");
  } catch (error) {
    appStatus.textContent = "无法读取应用状态";
    setOutput(String(error));
  }
}

function readFileAsDataUri(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("无法读取图片"));
    reader.readAsDataURL(file);
  });
}

async function handleImage(file) {
  const supported = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp",
  ];
  if (!supported.includes(file.type)) {
    showToast("请选择 PNG、JPEG、WebP、GIF 或 BMP 图片", true);
    return;
  }
  if (file.size > 30 * 1024 * 1024) {
    showToast("图片不能超过 30 MB", true);
    return;
  }
  uploadedImageDataUri = await readFileAsDataUri(file);
  if (uploadedObjectUrl) {
    URL.revokeObjectURL(uploadedObjectUrl);
  }
  uploadedObjectUrl = URL.createObjectURL(file);
  setPreviewImage(uploadedObjectUrl);
  imageName.textContent = file.name;
  showToast("图片已加入预览，点击“应用背景”后生效");
}

document.querySelectorAll('input[type="range"]').forEach((input) => {
  input.addEventListener("input", renderPreview);
});

imageInput.addEventListener("change", () => {
  const file = imageInput.files?.[0];
  if (file) {
    handleImage(file).catch((error) => showToast(error.message, true));
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    handleImage(file).catch((error) => showToast(error.message, true));
  }
});

applyButton.addEventListener("click", async () => {
  setBusy(true);
  setOutput("正在重建 app.asar 并重新签名，可能需要几十秒...");
  try {
    const data = await requestJson("/api/apply", {
      imageData: uploadedImageDataUri,
      imageName: imageName.textContent,
      config: configFromControls(),
    });
    setOutput(data.output);
    if (autoRestart.checked) {
      setOutput(`${data.output}\n\n正在重启 ChatGPT...`);
      try {
        const restartData = await requestJson("/api/restart", {});
        setOutput(`${data.output}\n\n${restartData.output}`);
        showToast("背景已应用，ChatGPT 已重新打开");
      } catch (restartError) {
        setOutput(`${data.output}\n\n${restartError.message}`);
        showToast("背景已应用，但自动重启失败，请手动重启 ChatGPT", true);
      }
    } else {
      showToast("背景已应用；请完全退出并重新打开 ChatGPT 后查看");
    }
  } catch (error) {
    setOutput(error.message);
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
});

restoreButton.addEventListener("click", async () => {
  if (!window.confirm("恢复为官方外观？背景图片和参数文件会保留。")) {
    return;
  }
  setBusy(true);
  setOutput("正在从干净备份恢复...");
  try {
    const data = await requestJson("/api/restore", {});
    setOutput(data.output);
    showToast("已恢复官方外观，请重新打开 ChatGPT");
  } catch (error) {
    setOutput(error.message);
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
});

resetButton.addEventListener("click", () => {
  applyConfigToControls(DEFAULTS);
  showToast("参数已重置为默认值");
});

clearOutputButton.addEventListener("click", () => setOutput(""));

loadState();
