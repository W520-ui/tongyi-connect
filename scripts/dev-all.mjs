import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendRoot = path.join(projectRoot, 'backend')
const pythonExecutable = process.platform === 'win32'
  ? path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
  : path.join(backendRoot, '.venv', 'bin', 'python')

if (!existsSync(pythonExecutable)) {
  console.error(`[dev] Backend virtual environment was not found at:\n      ${pythonExecutable}`)
  console.error('[dev] Create it first with:')
  console.error('      cd backend')
  console.error('      python -m venv .venv')
  console.error('      .venv/Scripts/python -m pip install -e .  # Windows')
  console.error('      .venv/bin/python -m pip install -e .      # macOS/Linux')
  process.exit(1)
}

const children = []
let shuttingDown = false

function startProcess(label, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, FORCE_COLOR: '1' },
    stdio: 'inherit',
    windowsHide: false,
  })

  children.push({ child, label })

  child.on('error', (error) => {
    if (!shuttingDown) {
      console.error(`[dev] Failed to start ${label}: ${error.message}`)
      void shutdown(1)
    }
  })

  child.on('exit', (code, signal) => {
    if (shuttingDown) return

    if (signal) {
      console.error(`[dev] ${label} stopped after signal ${signal}.`)
    } else if (code !== 0) {
      console.error(`[dev] ${label} exited with code ${code ?? 1}.`)
    } else {
      console.log(`[dev] ${label} stopped.`)
    }

    void shutdown(code ?? 1)
  })

  return child
}

function stopProcess({ child }) {
  if (process.platform !== 'win32') {
    if (!child.killed && child.exitCode === null && child.signalCode === null) {
      child.kill('SIGTERM')
    }
    return Promise.resolve()
  }

  // uvicorn --reload starts a second Python process. Always ask taskkill to
  // terminate the whole tree, even when the launcher has already exited.
  // Otherwise the reloader can keep port 8000 occupied after Ctrl+C.
  return new Promise((resolve) => {
    const taskkill = spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true,
    })
    taskkill.once('exit', resolve)
    taskkill.once('error', resolve)
  })
}

async function shutdown(code = 0) {
  if (shuttingDown) return
  shuttingDown = true
  await Promise.all(children.map(stopProcess))
  process.exit(code)
}

process.once('SIGINT', () => void shutdown(0))
process.once('SIGTERM', () => void shutdown(0))

console.log('[dev] Starting FastAPI backend and Vite frontend...')
startProcess(
  'backend',
  pythonExecutable,
  ['-m', 'uvicorn', 'app.main:app', '--reload'],
  backendRoot,
)

const viteCli = path.join(projectRoot, 'node_modules', 'vite', 'bin', 'vite.js')
if (!existsSync(viteCli)) {
  console.error(`[dev] Frontend dependencies were not found at:\n      ${viteCli}`)
  console.error('[dev] Install them first with: npm install')
  void shutdown(1)
} else {
  // Calling the Vite CLI through the current Node executable avoids spawning
  // npm.cmd directly, which Windows cannot launch without a shell.
  startProcess('frontend', process.execPath, [viteCli], projectRoot)
}

