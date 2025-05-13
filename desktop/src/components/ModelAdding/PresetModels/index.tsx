import React from 'react';
import { Button, Icon, Tooltip } from '@blueprintjs/core';
import styles from './style.module.css';
import { useTranslation } from 'react-i18next';
interface PresetModel {
    id: string;
    name: string;
    type: string;
    description: string[];
    imageUrl: string;
}

interface PresetModelsProps {
    onModelSelect?: (model: PresetModel) => void;
}

const presetModels: PresetModel[] = [
    {
        id: '001-flux-preset',
        name: 'Flux Model Preset',
        type: 'Flux',
        description: [
            'FLUX Schnell (Quantized)',
            'clip-vit-large-patch14',
            't5_bnb_int8_quantized_encoder',
            'Flux Vae'
        ],
        imageUrl: 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/f905bc28-9db6-4f83-85ae-93c94718881d/anim=false,width=450/NfX8MYg-_nTv_PpQBNJSr.jpeg'
    }
];

export const PresetModels: React.FC<PresetModelsProps> = ({ onModelSelect }) => {
    const { t } = useTranslation();
    return (
        <div className={styles.presetModel}>
            <div className={styles.cardList}>
                {presetModels.map(model => (
                    <div className={styles.card} key={model.id}>
                        <div className={styles.type}>{model.type}</div>
                        <div className={styles.image}>
                            <img src={model.imageUrl} alt={model.name} />
                        </div>
                        <div className={styles.info}>
                            <div className={styles.name}>{model.name}</div>
                            <div className={styles.actions}>
                                <Button
                                    text={t('dmg')}
                                    intent="primary"
                                    onClick={() => onModelSelect?.(model)}
                                />
                            </div>
                        </div>
                        <div className={styles.infoButton}>
                            <Tooltip
                                content={
                                    <div className={styles.tooltip}>
                                        {model.description.map((desc, index) => (
                                            <div key={index} className={styles.tooltipItem}>
                                                {desc}
                                            </div>
                                        ))}
                                    </div>
                                }
                                position="right"
                            >
                                <Icon icon="info-sign" />
                            </Tooltip>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default PresetModels;
