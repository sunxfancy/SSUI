import { TauriProcessProvider, ProcessEnvironment } from './TauriProcessProvider';
import { IExecutorProvider } from './IExecutorProvider';

export class TauriExecutorProvider implements IExecutorProvider {
  private process: TauriProcessProvider;
  constructor(environment?: ProcessEnvironment) {
    this.process = new TauriProcessProvider('executor', '执行器', environment);
  }
  startExecutor() { return this.process.start(); }
  stopExecutor() { return this.process.stop(); }
  restartExecutor() { return this.process.restart(); }
  getExecutorStatus() { return this.process.status(); }
}
