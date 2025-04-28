import React, {useRef, useState} from 'react';
import { load } from '@tauri-apps/plugin-store';
import {WorkSpace} from './components/WorkSpace'
import TabWindowManager from './components/TabWindowManager';
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { ModelManager } from './components/ModelManager';
import ModelAddingPage from './components/ModelAdding';
import Queue from './components/Queue';
import { open } from '@tauri-apps/plugin-dialog';
import NewWorkflow from './components/NewWorkflow.tsx';
import { Extensions } from './components/Extensions/index.tsx';
import { ModelManagerProvider } from './providers/ModelManagerProvider';
import GlobalStateManager from './services/GlobalState.ts';
import {Navbar} from "./components/Navbar";
import { TabPanel } from '@blueprintjs/core'

const App = () => {
    const [ currentWorkspace, setCurrentWorkspace ] = useState('')
    const [ isNewWorkflowDialogOpen, setIsNewWorkflowDialogOpen ] = useState(false)
    const [ navIndex, setNavIndex ] = useState(0)
    const tabWindowManagerRef = useRef<TabWindowManager>()
    const modelManagerProvider = useRef(new ModelManagerProvider())

    const onClick = async () => {
        const store = await load('settings.json', { autoSave: false });
        await store.set('root', undefined);
        await store.save();
    }

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

    const onFileOpen = (filePath: string) => {
        const rootState = GlobalStateManager.getInstance().getRootState();
        const host = rootState?.host || 'localhost';
        const port = rootState?.port || 7422;
        tabWindowManagerRef.current?.openFile(filePath, `http://${host}:${port}/functional_ui/?path=${filePath}`);
    }

    const addModel = () => {
        tabWindowManagerRef.current?.openReactComponent(<ModelAddingPage />, "添加模型");
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
                <Allotment.Pane preferredSize={360} minSize={100} maxSize={500}>
                    <div style={{ display: 'flex', height: '100%' }}>
                        <Navbar navIndex={navIndex} updateNavIndex={setNavIndex} />
                        {/*<GenerateNavContent></GenerateNavContent>*/}
                        <div style={{ width: '100%' }}>
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
                                panel={<ModelManager provider={modelManagerProvider} addModel={addModel} />}
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
                                panel={<Extensions onOpenExtensionStore={openExtensionStore} />}
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
