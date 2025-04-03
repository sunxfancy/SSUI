import React from 'react';
import { Card, Elevation, Button, Icon } from '@blueprintjs/core';
import { Tooltip } from '@blueprintjs/core';
import { CivitaiModel } from '../types/civitai';
import './CivitaiModelCard.css';

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
      style={{
        width: '320px',
        height: '420px',
        position: 'relative',
        overflow: 'hidden',
        padding: 0,
        borderRadius: '18px'
      }}
    >
      {/* 模型类型标签 */}
      <div style={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        color: 'white',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '12px',
        textShadow: '0 1px 2px rgba(0,0,0,0.5)',
        zIndex: 1
      }}>
        {model.type}
      </div>

      {/* 模型预览图 */}
      <div style={{
        width: '100%',
        height: '420px',
        overflow: 'hidden'
      }}>
        {model.modelVersions[0]?.images[0] && (
          <img 
            src={model.modelVersions[0].images[0].url} 
            alt={model.name}
            className="model-card-img"
          />
        )}


      </div>

      {/* 模型标题和描述 */}
      <h3 style={{
        margin: '0',
        fontSize: '16px',
        fontWeight: 'bold',
        position: 'absolute',
        bottom: '50px',
        left: '10px',
        color: 'white',
        textShadow: '0 1px 2px rgba(0,0,0,0.5)',
        zIndex: 1
      }}>
        {model.name}
      </h3>
      
      <Icon icon="info-sign" style={{ position: 'absolute', top: '10px', right: '10px', color: 'white' }} />

      {/* 底部统计信息和操作按钮 */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '10px',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: 'white',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{
          display: 'flex',
          gap: '10px',
          fontSize: '12px',
          textShadow: '0 1px 2px rgba(0,0,0,0.5)'
        }}>
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