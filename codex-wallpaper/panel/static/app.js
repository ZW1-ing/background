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

const { requestJson, errorOutput } = globalThis.CodexWallpaperApi;
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
const appSection = document.querySelector("#app-section");
const appTargetStatus = document.querySelector("#app-target-status");
const appSelect = document.querySelector("#app-select");
const chooseAppButton = document.querySelector("#choose-app-button");
const refreshAppsButton = document.querySelector("#refresh-apps-button");
const appHelp = document.querySelector("#app-help");

let uploadedImageDataUri = null;
let uploadedObjectUrl = null;
let toastTimer = null;
let canApplyCurrentTarget = true;

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
  applyButton.disabled = isBusy || !canApplyCurrentTarget;
  restoreButton.disabled = isBusy;
  chooseAppButton.disabled = isBusy;
  refreshAppsButton.disabled = isBusy;
  appSelect.disabled = isBusy;
  applyButton.textContent = isBusy ? "正在应用..." : "应用背景";
}

function describeStatus(state) {
  if (state?.selectedApp) {
    appStatus.textContent = `已连接 ${state.selectedApp.name}`;
    return;
  }
  const status = state?.status || "";
  const match = status.match(/^App:\s+(.+)$/m);
  if (match) {
    const appName = match[1].split("/").pop();
    appStatus.textContent = `已连接 ${appName}`;
    return;
  }
  appStatus.textContent = "未检测到 Codex 或 ChatGPT 应用";
}

function selectedAppName() {
  return appSelect.selectedOptions?.[0]?.textContent?.split(" · ")[0] || "目标应用";
}

function renderApplicationControls(state) {
  if (!state?.canChooseApp) {
    appSection.hidden = true;
    return;
  }

  appSection.hidden = false;
  const selected = state.selectedApp;
  const targetCanApply = Boolean(
    selected && (selected.canApply !== false || selected.copyable)
  );
  const usesWritableCopy = Boolean(
    selected && selected.canApply === false && selected.copyable
  );
  canApplyCurrentTarget = targetCanApply;
  appHelp.classList.toggle(
    "is-error",
    Boolean(selected && selected.canApply === false && !selected.copyable)
  );
  if (selected && selected.canApply === false) {
    appHelp.textContent = selected.copyable
      ? "检测到 Microsoft Store 版。点击应用时会自动创建可修改副本，原应用不会被修改。"
      : selected.patchabilityError || "当前安装受系统保护，无法修改应用资源。";
  } else {
    appHelp.textContent =
      state.platform === "Windows"
        ? "Windows 需要管理员权限，才能修改应用资源。"
        : "如果没有自动检测到应用，可以在这里手动选择。";
  }
  const applications = state.applications || [];
  appSelect.replaceChildren();
  if (!applications.length) {
    const option = new Option("未检测到 ChatGPT 或 Codex", "");
    option.disabled = true;
    option.selected = true;
    appSelect.add(option);
    appTargetStatus.textContent =
      state.platform === "Windows"
        ? "请选择已安装的 ChatGPT.exe 或 Codex.exe"
        : "请选择已安装的 ChatGPT.app 或 Codex.app";
    applyButton.disabled = !canApplyCurrentTarget;
    return;
  }

  for (const application of applications) {
    const unsupported =
      application.canApply === false
        ? application.copyable
          ? "（自动副本）"
          : "（不支持）"
        : "";
    const option = new Option(
      `${application.name}${unsupported} · ${application.executable}`,
      application.executable
    );
    option.title = application.executable;
    option.selected =
      application.executable === state.selectedApp?.executable;
    appSelect.add(option);
  }
  appTargetStatus.textContent = state.selectedApp
    ? targetCanApply
      ? usesWritableCopy
        ? `当前使用 ${state.selectedApp.name} Store 版，应用时自动复制`
        : `当前使用 ${state.selectedApp.name}`
      : "当前目标不支持修改"
    : "请选择要修改的应用";
  applyButton.disabled = !canApplyCurrentTarget;
}

function applyState(state) {
  applyConfigToControls(state.config);
  describeStatus(state);
  renderApplicationControls(state);
  if (state.hasImage) {
    setPreviewImage(`/api/current-image?t=${Date.now()}`);
    imageName.textContent = state.imageName || "已保存的自定义背景";
  } else {
    setPreviewImage(state.defaultImageUrl);
    imageName.textContent = "当前使用内置背景";
  }
  setOutput(state.status || "等待操作...");
}

async function loadState() {
  try {
    const response = await fetch("/api/state");
    const state = await response.json();
    applyState(state);
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

async function prepareImageData(file) {
  const limit = 1100 * 1024;
  const original = await readFileAsDataUri(file);
  if (file.size <= limit) {
    return original;
  }

  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = objectUrl;
    await image.decode();
    const longest = Math.max(image.naturalWidth, image.naturalHeight);
    const steps = [
      [2560, 0.82],
      [1920, 0.72],
      [1600, 0.64],
      [1280, 0.58],
    ];
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("浏览器不支持图片压缩");
    }
    for (const [maxDimension, quality] of steps) {
      const scale = Math.min(1, maxDimension / longest);
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const compressed = canvas.toDataURL("image/jpeg", quality);
      const payloadBytes = Math.ceil(
        ((compressed.length - compressed.indexOf(",") - 1) * 3) / 4
      );
      if (payloadBytes <= limit) {
        return compressed;
      }
    }
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
  throw new Error("图片压缩后仍然过大，请选择较小的图片");
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
  uploadedImageDataUri = await prepareImageData(file);
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
    applyState(data.state);
    setOutput(data.output);
    if (autoRestart.checked) {
      const appName = data.state?.selectedApp?.name || selectedAppName();
      setOutput(`${data.output}\n\n正在重启 ${appName}...`);
      try {
        const restartData = await requestJson("/api/restart", {});
        setOutput(`${data.output}\n\n${restartData.output}`);
        showToast(`背景已应用，${appName} 已重新打开`);
      } catch (restartError) {
        setOutput(`${data.output}\n\n${errorOutput(restartError)}`);
        showToast(`背景已应用，但自动重启失败，请手动重启 ${appName}`, true);
      }
    } else {
      showToast("背景已应用；请完全退出并重新打开目标应用后查看");
    }
  } catch (error) {
    setOutput(errorOutput(error));
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
});

async function refreshApplications(showMessage = false) {
  const response = await fetch("/api/apps");
  const state = await response.json();
  if (!response.ok || !state.ok) {
    throw new Error(state.error || "无法检测应用");
  }
  renderApplicationControls(state);
  describeStatus(state);
  if (showMessage) {
    showToast("应用列表已刷新");
  }
}

appSelect.addEventListener("change", async () => {
  if (!appSelect.value) {
    return;
  }
  setBusy(true);
  try {
    const data = await requestJson("/api/select-app", {
      path: appSelect.value,
    });
    applyState(data.state);
    showToast(`已选择 ${data.app.name}`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
});

chooseAppButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const data = await requestJson("/api/select-app", {});
    applyState(data.state);
    showToast(`已选择 ${data.app.name}`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
});

refreshAppsButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    await refreshApplications(true);
  } catch (error) {
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
    setOutput(errorOutput(error));
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
