import { ipcRenderer, contextBridge } from 'electron'

// --------- Expose specific API to the Renderer process ---------
contextBridge.exposeInMainWorld('api', {
  onWorkspaceChanged: (callback: (newPath: string) => void) => {
    const subscription = (_event: any, newPath: string) => callback(newPath)
    ipcRenderer.on('workspace-changed', subscription)
    return () => ipcRenderer.removeListener('workspace-changed', subscription)
  },
  getPythonPort: () => ipcRenderer.invoke('get-python-port'),
  getWorkspace: () => ipcRenderer.invoke('get-workspace'),
  selectWorkspace: () => ipcRenderer.invoke('select-workspace'),
})
