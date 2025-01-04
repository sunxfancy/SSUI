
import { Button } from "@blueprintjs/core";
import { load } from '@tauri-apps/plugin-store';


function App() {
  async function onClick() {
    const store = await load('settings.json', { autoSave: false });
    await store.set('root', undefined);
    await store.save();
  }

  return (
    <main className="container">
      <Button intent="primary" text="Run" onClick={onClick} />
    </main>
  );
}

export default App;
