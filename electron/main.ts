import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, ChildProcess } from 'node:child_process'
import net from 'node:net'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
process.env.APP_ROOT = path.join(__dirname, '..')

export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST

let win: BrowserWindow | null = null
let pyProcess: ChildProcess | null = null
let pyPort: number = 38391
let currentWorkspace: string | null = null

// 配置存储路径
const CONFIG_FILE = path.join(app.getPath('userData'), 'app_config.json')

function loadAppConfig() {
  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'))
      currentWorkspace = config.lastWorkspace || null
    } catch (e) {
      console.error('Failed to load config', e)
    }
  }
}

function saveAppConfig() {
  const config = { lastWorkspace: currentWorkspace }
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config), 'utf-8')
}

// 检查端口是否可用
function isPortAvailable(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer()
      .once('error', () => resolve(false))
      .once('listening', () => {
        server.close()
        resolve(true)
      })
      .listen(port, '127.0.0.1')
  })
}

async function getAvailablePort(startPort: number): Promise<number> {
  let port = startPort
  while (!(await isPortAvailable(port))) {
    port++
  }
  return port
}

function killPythonBackend() {
  if (pyProcess) {
    console.log('Terminating Python backend...')
    pyProcess.kill('SIGTERM') // Send termination signal
    pyProcess = null
  }
}

async function startPythonBackend(workspace: string) {
  // 如果已有进程在运行，先杀掉（切换工作区场景）
  killPythonBackend()

  pyPort = await getAvailablePort(38391)
  console.log(`Starting Python backend on port ${pyPort} with workspace ${workspace}...`)

  const pythonExe = path.join(process.env.APP_ROOT, 'python_embed', 'python.exe')
  const scriptPath = path.join(process.env.APP_ROOT, 'backend', 'server.py')

  pyProcess = spawn(pythonExe, [scriptPath, pyPort.toString(), workspace], {
    cwd: process.env.APP_ROOT,
    stdio: 'pipe'
  })

  pyProcess.stdout?.on('data', (data) => console.log(`[Py]: ${data}`))
  pyProcess.stderr?.on('data', (data) => console.error(`[PyError]: ${data}`))

  pyProcess.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`Python backend exited unexpectedly with code ${code}`)
    }
  })
}

function createWindow() {
  win = new BrowserWindow({
    icon: path.join(process.env.VITE_PUBLIC, 'electron-vite.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
    width: 1200,
    height: 800,
    show: false, // 先隐藏
    backgroundColor: '#f8fafc' // 使用 slate-50 颜色
  })

  win.once('ready-to-show', () => {
    win?.show() // 准备好了再显示
  })

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL)
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html'))
  }
}

// IPC Handlers
ipcMain.handle('get-python-port', () => pyPort)
ipcMain.handle('get-workspace', () => currentWorkspace)

ipcMain.handle('select-workspace', async () => {
  const result = await dialog.showOpenDialog(win!, {
    properties: ['openDirectory']
  })
  if (!result.canceled && result.filePaths.length > 0) {
    currentWorkspace = result.filePaths[0]
    saveAppConfig()
    // 切换工作区后重启后端
    await startPythonBackend(currentWorkspace)
    // 通知前端刷新
    win?.webContents.send('workspace-changed', currentWorkspace)
    return currentWorkspace
  }
  return null
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    killPythonBackend()
    app.quit()
  }
})

app.on('before-quit', () => {
  killPythonBackend()
})

app.whenReady().then(async () => {
  loadAppConfig()
  
  // 如果没有选择过工作区，先启动一个默认的，或者由前端引导选择
  const defaultWorkspace = currentWorkspace || path.join(app.getPath('documents'), 'AcademicClarity')
  currentWorkspace = defaultWorkspace
  
  await startPythonBackend(defaultWorkspace)
  createWindow()
})
