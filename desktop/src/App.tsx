import {useRef, useState} from 'react';
import {WorkSpace} from './components/WorkSpace'
import TabWindowManager from './components/TabWindowManager/index.tsx';
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { ModelManager } from './components/ModelManager';
import ModelAddingPage from './components/ModelAdding';
import Queue from './components/Queue';
import { open } from '@tauri-apps/plugin-dialog';
import NewWorkflow from './components/NewWorkflow.tsx';
import { Extensions } from './components/Extensions';
import { ModelManagerProvider } from './providers/ModelManagerProvider';
import GlobalStateManager from './services/GlobalState.ts';
import {Navbar} from "./components/Navbar";
import { TabPanel } from '@blueprintjs/core'
import FileOpenerProvider from './providers/FileOpenerProvider.ts';
import { ExtensionsProvider } from './providers/ExtensionsProvider.ts';

const App = () => {
    const [ currentWorkspace, setCurrentWorkspace ] = useState('')
    const [ isNewWorkflowDialogOpen, setIsNewWorkflowDialogOpen ] = useState(false)
    const [ navIndex, setNavIndex ] = useState(0)
    const tabWindowManagerRef = useRef<TabWindowManager>(null)
    const modelManagerProvider = useRef<ModelManagerProvider>(new ModelManagerProvider())
    const extensionsProviderRef = useRef<ExtensionsProvider>(new ExtensionsProvider())


    const onOpenWorkspace = () => {
        open({
            directory: true,
            multiple: false
        }).then(async (result: string | null) => {
            if (result) {
                setCurrentWorkspace(result)
            }
        });
    }

    const onSelectWorkflow = () => {
        setIsNewWorkflowDialogOpen(true)
    }

    const onFileOpen = async (filePath: string) => {
        const rootState = GlobalStateManager.getInstance().getRootState();
        const defaultUrl = await FileOpenerProvider.constructDefaultUrl(filePath);
        const host = rootState?.host || 'localhost';
        const port = rootState?.port || 7422;
        tabWindowManagerRef.current?.openFile(filePath, `http://${host}:${port}${defaultUrl}`);
    }

    const addModel = () => {
        tabWindowManagerRef.current?.openReactComponent(<ModelAddingPage />, "添加模型");
    }

    const openSettings = () => {
        const rootState = GlobalStateManager.getInstance().getRootState();
        const host = rootState?.host || 'localhost';
        const port = rootState?.port || 7422;
        const path = encodeURIComponent(`${rootState?.path}/resources/desktop_settings.json`);
        const filePath = `/functional_ui/?view=project_settings&path=${path}`;
        tabWindowManagerRef.current?.openFile("应用设置", `http://${host}:${port}${filePath}`);
    }

    const openExtensionStore = () => {
        tabWindowManagerRef.current?.openFile("#internal-extension-store", "https://sunxfancy.github.io/test_page/", "扩展商城");
    }

    const handleWorkflowSelect = (workflowIds: string[], targetPath: string) => {
        // TODO：将workflowIds转换为文件然后写入到目标文件夹中
        console.log(workflowIds);
        setIsNewWorkflowDialogOpen(false)
        setCurrentWorkspace(targetPath)
    }

    return (
        <div style={{ height: '100%' }}>
            <Allotment>
                <Allotment.Pane preferredSize={360} minSize={360} maxSize={500}>
                    <div style={{ display: 'flex', height: '100%' }}>
                        <Navbar navIndex={navIndex} updateNavIndex={setNavIndex} openSettings={openSettings} />
                        {/*<GenerateNavContent></GenerateNavContent>*/}
                        <div style={{ width: '100%', overflow: 'hidden' }}>
                            <TabPanel
                                id={0}
                                selectedTabId={navIndex}
                                parentId="navbar-tabs"
                                panel={<WorkSpace currentWorkspace={currentWorkspace} onOpenWorkspace={onOpenWorkspace} onSelectWorkflow={onSelectWorkflow} onFileOpen={onFileOpen} />}
                            />
                            <TabPanel
                                id={1}
                                selectedTabId={navIndex}
                                parentId="navbar-tabs"
                                panel={<ModelManager provider={modelManagerProvider.current} addModel={addModel} />}
                            />
                            <TabPanel
                                id={2}
                                selectedTabId={navIndex}
                                parentId="navbar-tabs"
                                panel={<Queue />}
                            />
                            <TabPanel
                                id={3}
                                selectedTabId={navIndex}
                                parentId="navbar-tabs"
                                panel={<Extensions provider={extensionsProviderRef.current} onOpenExtensionStore={openExtensionStore} />}
                            />
                        </div>

                    </div>
                </Allotment.Pane>
                <Allotment.Pane>
                    <TabWindowManager ref={tabWindowManagerRef} />
                </Allotment.Pane>
            </Allotment>
            <NewWorkflow isOpen={isNewWorkflowDialogOpen} onClose={() => setIsNewWorkflowDialogOpen(false)} onWorkflowSelect={handleWorkflowSelect} />
        </div>
    )
}

export default App
