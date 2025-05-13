import { useState } from 'react';
import { Tabs, Tab, Card, Elevation } from '@blueprintjs/core';
import CivitaiModels from './CivitaiModels';
import LocalModels from './LocalModels/index.tsx';
import HuggingfaceModels from './HuggingfaceModels';
import { TauriModelsProvider } from '../../providers/TauriModelsProvider';
import { ModelsProvider } from '../../providers/IModelsProvider';
import styles from './style.module.css';
import PresetModels from './PresetModels/index.tsx';
import { useTranslation } from 'react-i18next';

interface ModelAddingPageProps {
    // 可以在这里添加需要的属性
}

const ModelAddingPage: React.FC<ModelAddingPageProps> = () => {
    const [selectedTabId, setSelectedTabId] = useState('preset');
    const { t } = useTranslation();
    const modelsProvider = new TauriModelsProvider();

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
                    onModelSelect={(model) => {
                        console.log('选择的Huggingface模型:', model);
                    }}
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
