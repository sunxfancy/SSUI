
import './App.css';
import '../../ssui_components/src/components/InternalComponents';
import { getUIProvider } from './ui/UIProvider';
import { ExtensionLoader } from './extension/loader';


let loader = new ExtensionLoader();
loader.loadExtensions();

function App() {
  function getView() {
    const params = new URLSearchParams(window.location.search);
    console.log("getView", params);
    var path = '';
    if (params.has('path')) {
      path = params.get('path') ?? '';
      console.log('Path:', path);
    }

    var provider = null;
    if (params.has('view')) {
      const view = params.get('view') ?? '';
      provider = getUIProvider(view);
    }
    if (!provider) {
      provider = getUIProvider('functional');
    }

    if (provider) {
      return provider.getUI(path);
    }
  }

  return (
    <main>
      {getView()}
    </main>
  );
}

export default App;
