import { TauriProcessProvider, ProcessEnvironment } from './TauriProcessProvider';
import { IServerProvider } from './IServerProvider';

export class TauriServerProvider implements IServerProvider {
  private process: TauriProcessProvider;
  constructor(environment?: ProcessEnvironment) {
    this.process = new TauriProcessProvider('server', '服务器', environment);
  }
  startServer() { return this.process.start(); }
  stopServer() { return this.process.stop(); }
  restartServer() { return this.process.restart(); }
  getServerStatus() { return this.process.status(); }
}
