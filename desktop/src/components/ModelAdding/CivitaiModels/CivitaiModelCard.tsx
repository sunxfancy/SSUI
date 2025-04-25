import React from 'react';
import { Card, Elevation, Button, Icon } from '@blueprintjs/core';
import { CivitaiModel } from '../../../types/civitai.ts';
import styles from './style.module.css'

interface CivitaiModelCardProps {
  model: CivitaiModel;
  onModelSelect?: (model: CivitaiModel) => void;
}

const CivitaiModelCard: React.FC<CivitaiModelCardProps> = ({ model, onModelSelect }) => {
  const handleCardClick = () => {
    if (onModelSelect) {
      onModelSelect(model);
    }
  };

  return (
      <Card
          elevation={Elevation.TWO}
          interactive={true}
          onClick={handleCardClick}
          className={styles.civitaiModelCard}
      >
        {/* 模型类型标签 */}
        <div className={styles.cardType}>
          {model.type}
        </div>

        {/* 模型预览图 */}
        <div className={styles.previewImage}>
          {model.modelVersions[0]?.images[0] && (
              <img
                  src={model.modelVersions[0].images[0].url}
                  alt={model.name}
              />
          )}
        </div>

        {/* 模型标题和描述 */}
        <h3 className={styles.name}>
          {model.name}
        </h3>

        <Icon icon="info-sign" className={styles.signIcon} />

        {/* 底部统计信息和操作按钮 */}
        <div className={styles.operateBar}>
          <div className={styles.text}>
            <span>下载: {model.stats.downloadCount}</span>
            <span>点赞: {model.stats.thumbsUpCount}</span>
            <span>评论: {model.stats.commentCount}</span>
          </div>
          <Button
              text="下载"
              intent="primary"
              small
              onClick={(e) => {
                e.stopPropagation();
                // 这里可以添加下载逻辑
                console.log('下载模型:', model.name);
              }}
          />
        </div>
      </Card>
  );
};

export default CivitaiModelCard;
