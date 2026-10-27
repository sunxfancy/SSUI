import './App.css';
import { UIStateProvider } from 'ssui_components';
import { getUIProvider } from './ui/UIProvider';


function App() {
  function getView() {
    const params = new URLSearchParams(window.location.search);
    var path = '';
    if (params.has('path')) {
      path = params.get('path') ?? '';
      console.log('Path:', path);
    }

    var provider = null;
    if (params.has('view')) {
      const view = params.get('view') ?? '';
      provider = getUIProvider(view);
      console.log('View:', view, provider);
    } else {
      console.log('No view provided, using functional');
    }
    if (!provider) {
      provider = getUIProvider('functional');
    }

    if (provider) {
      const view = provider.getName();
      if (!path || view === 'project_settings') return provider.getUI(path);
      return <UIStateProvider key={path + ':' + view} path={path} view={view}>{provider.getUI(path)}</UIStateProvider>;
    }
  }

  return (
    <main>
      {getView()}
    </main>
  );
}

export default App;
