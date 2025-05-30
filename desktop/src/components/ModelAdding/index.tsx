import { useState } from 'react';
import { Tabs, Tab, Card, Elevation } from '@blueprintjs/core';
import CivitaiModels from './CivitaiModels';
import LocalModels from './LocalModels/index.tsx';
import HuggingfaceModels from './HuggingfaceModels';
import { HuggingfaceModel } from './HuggingfaceModels/index.tsx';
import { TauriModelsProvider } from '../../providers/TauriModelsProvider';
import { ModelsProvider } from '../../providers/IModelsProvider';
import styles from './style.module.css';
import PresetModels from './PresetModels/index.tsx';
import { useTranslation } from 'react-i18next';
import { Message } from 'ssui_components';
import GlobalStateManager from '../../services/GlobalState.ts';

interface ModelAddingPageProps {
    // 可以在这里添加需要的属性
}

const ModelAddingPage: React.FC<ModelAddingPageProps> = () => {
    const [selectedTabId, setSelectedTabId] = useState('preset');
    const { t } = useTranslation();
    const modelsProvider: ModelsProvider = new TauriModelsProvider();
    const rootState = GlobalStateManager.getInstance().getRootState();
    let message = new Message(rootState?.host || "localhost", rootState?.port || 7420);
    const handleTabChange = (newTabId: string) => {
        setSelectedTabId(newTabId);
    };

    const handleDownloadHuggingfaceModel = (model: HuggingfaceModel) => {
        console.log("downloading huggingface model: ", model.modelId);
        message.post('api/hf_download', {
            repo_id: model.modelId
        }, {
            'download_progress': (data: any) => {
                console.log(data);
            }
        });
    };

    const renderPresetModelsTab = () => {
        return (
            <Card elevation={Elevation.ZERO}>
                <PresetModels onModelSelect={(preset) => {
                    console.log('Selected model:', preset);
                }} />
            </Card>
        );
    };

    const renderCivitaiTab = () => {
        return (
            <Card elevation={Elevation.ZERO}>
                <CivitaiModels
                    onModelSelect={(model) => {
                        console.log('Selected model:', model);
                    }}
                />
            </Card>
        );
    };

    const renderHuggingfaceTab = () => {
        return (
            <Card elevation={Elevation.ZERO}>
                <HuggingfaceModels
                    onModelSelect={handleDownloadHuggingfaceModel}
                />
            </Card>
        );
    };

    const renderLocalModelsTab = () => {
        return (
            <Card elevation={Elevation.ZERO}>
                <LocalModels
                    modelsProvider={modelsProvider}
                    onModelAdd={(modelPath) => {
                        console.log('添加模型:', modelPath);
                    }}
                />
            </Card>
        );
    };

    return (
        <div className={styles.ModelAdding}>
            <Tabs
                id="ModelAddingTabs"
                selectedTabId={selectedTabId}
                onChange={handleTabChange}
                renderActiveTabPanelOnly={true}
            >
                <Tab
                    id="preset"
                    title={t('preset')}
                    panel={renderPresetModelsTab()}
                />
                <Tab
                    id="civitai"
                    title="Civitai"
                    panel={renderCivitaiTab()}
                />
                <Tab
                    id="huggingface"
                    title="Huggingface"
                    panel={renderHuggingfaceTab()}
                />
                <Tab
                    id="local"
                    title={t('local')}
                    panel={renderLocalModelsTab()}
                />
            </Tabs>
        </div>
    );
};

export default ModelAddingPage;
