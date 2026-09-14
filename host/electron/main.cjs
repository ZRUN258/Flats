"use strict";

const { app, BrowserWindow, dialog, net, protocol } = require("electron");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const APP_SCHEME = "flats";
const APP_ORIGIN = `${APP_SCHEME}://app`;
const HOST_ROOT = path.resolve(__dirname, "..");

protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: { standard: true, secure: true, supportFetchAPI: true }
  }
]);

let mainWindow = null;

function isTrustedOrigin(origin) {
  try {
    const url = new URL(origin);
    return url.protocol === `${APP_SCHEME}:` && url.hostname === "app";
  } catch {
    return false;
  }
}

function resolveAppFile(requestUrl) {
  const url = new URL(requestUrl);
  const relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
  const filePath = path.resolve(HOST_ROOT, relativePath);
  const insideHost = filePath === HOST_ROOT || filePath.startsWith(`${HOST_ROOT}${path.sep}`);
  return insideHost ? filePath : null;
}

function describePort(port) {
  const name = port.displayName || port.portName || "串口设备";
  const details = [];
  if (port.vendorId) details.push(`VID ${port.vendorId}`);
  if (port.productId) details.push(`PID ${port.productId}`);
  if (port.serialNumber) details.push(`SN ${port.serialNumber}`);
  return details.length ? `${name}（${details.join(" · ")}）` : name;
}

function configureSerialAccess(window) {
  const session = window.webContents.session;

  session.setPermissionCheckHandler((_webContents, permission, requestingOrigin) => {
    return permission === "serial" && isTrustedOrigin(requestingOrigin);
  });

  session.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(permission === "serial" && isTrustedOrigin(webContents.getURL()));
  });

  session.setDevicePermissionHandler((details) => {
    return details.deviceType === "serial" && isTrustedOrigin(details.origin);
  });

  const selectSerialPort = async (event, portList, _webContents, callback) => {
    event.preventDefault();

    if (!portList.length) {
      callback("");
      await dialog.showMessageBox(window, {
        type: "warning",
        title: "未发现串口设备",
        message: "未发现可用的串口设备",
        detail: "请连接设备并确认驱动安装正常，然后重新点击连接。"
      });
      return;
    }

    const cancelId = portList.length;
    const result = await dialog.showMessageBox(window, {
      type: "question",
      title: "选择串口设备",
      message: "请选择要连接的串口",
      detail: "运动控制器和 SlaveADC 需要分别选择各自对应的串口。",
      buttons: [...portList.map(describePort), "取消"],
      cancelId,
      defaultId: 0,
      noLink: true
    });

    callback(result.response === cancelId ? "" : portList[result.response].portId);
  };

  session.on("select-serial-port", selectSerialPort);
  return () => session.removeListener("select-serial-port", selectSerialPort);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    backgroundColor: "#07111f",
    autoHideMenuBar: true,
    title: "Flats 上位机",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  const removeSerialListener = configureSerialAccess(mainWindow);

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(`${APP_ORIGIN}/`)) event.preventDefault();
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => {
    removeSerialListener();
    mainWindow = null;
  });
  mainWindow.loadURL(`${APP_ORIGIN}/index.html`);
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(() => {
    protocol.handle(APP_SCHEME, (request) => {
      const filePath = resolveAppFile(request.url);
      if (!filePath) return new Response("Not found", { status: 404 });
      return net.fetch(pathToFileURL(filePath).toString());
    });

    createWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
