import { useState } from 'react';
import { Tabs, Tab, Card, Elevation } from '@blueprintjs/core';
import CivitaiModels from './CivitaiModels';
import LocalModels from './LocalModels/index.tsx';
import HuggingfaceModels from './HuggingfaceModels';
import { TauriModelsProvider } from '../../providers/TauriModelsProvider';
import { ModelsProvider } from '../../providers/IModelsProvider';
import type { IDownloaderProvider } from '../../providers/IDownloaderProvider';
import styles from './style.module.css';
import PresetModels from './PresetModels/index.tsx';
import { useTranslation } from 'react-i18next';

interface ModelAddingPageProps {
    initialTab?: 'preset' | 'civitai' | 'huggingface' | 'local';
    modelsProvider?: ModelsProvider;
    downloaderProvider?: IDownloaderProvider;
}

const ModelAddingPage: React.FC<ModelAddingPageProps> = ({ initialTab = 'preset', modelsProvider: suppliedModelsProvider, downloaderProvider }) => {
    const [selectedTabId, setSelectedTabId] = useState<string>(initialTab);
    const { t } = useTranslation();
    const [defaultModelsProvider] = useState(() => suppliedModelsProvider ?? new TauriModelsProvider());
    const modelsProvider = suppliedModelsProvider ?? defaultModelsProvider;
    const handleTabChange = (newTabId: string) => {
        setSelectedTabId(newTabId);
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
                    downloaderProvider={downloaderProvider}
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
                <HuggingfaceModels />
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
