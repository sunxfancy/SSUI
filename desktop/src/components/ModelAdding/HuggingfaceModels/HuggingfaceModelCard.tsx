import React from 'react';
import { Card, Elevation, Button, Tag, Icon } from '@blueprintjs/core';

interface HuggingfaceModel {
  id: string;
  modelId: string;
  private: boolean;
  author: string;
  downloads: number;
  likes: number;
  tags: string[];
  pipeline_tag: string;
  lastModified: string;
}

interface HuggingfaceModelCardProps {
  model: HuggingfaceModel;
  onModelSelect?: (model: HuggingfaceModel) => void;
}

const HuggingfaceModelCard: React.FC<HuggingfaceModelCardProps> = ({ model, onModelSelect }) => {
  const handleCardClick = () => {
    if (onModelSelect) {
      onModelSelect(model);
    }
  };

  // 从ID中提取名称
  const modelName = model.id.includes('/') ? model.id.split('/')[1] : model.id;
  // 默认图片URL（Huggingface默认头像）
  const imageUrl = `https://huggingface.co/${model.id}/resolve/main/model-card.png`;
  // 格式化下载数
  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  return (
    <Card
      elevation={Elevation.TWO}
      interactive={true}
      onClick={handleCardClick}
      style={{
        width: '320px',
        height: '380px',
        position: 'relative',
        overflow: 'hidden',
        padding: '10px',
        borderRadius: '8px',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* 模型类型标签 */}
      {model.pipeline_tag && (
        <Tag
          minimal
          style={{
            position: 'absolute',
            top: '15px',
            left: '15px',
            zIndex: 1
          }}
        >
          {model.pipeline_tag}
        </Tag>
      )}

      {/* 模型预览图 */}
      <div style={{
        height: '160px',
        borderRadius: '4px',
        overflow: 'hidden',
        backgroundColor: '#f5f8fa',
        marginBottom: '15px',
        position: 'relative'
      }}>
        <img
          src={imageUrl}
          alt={modelName}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover'
          }}
          onError={(e) => {
            // 如果模型卡片图片加载失败，显示默认背景
            e.currentTarget.style.display = 'none';
          }}
        />
        <div style={{
          position: 'absolute',
          bottom: '10px',
          right: '10px',
          backgroundColor: 'rgba(0,0,0,0.5)',
          color: 'white',
          padding: '3px 6px',
          borderRadius: '3px',
          fontSize: '12px'
        }}>
          {model.author}
        </div>
      </div>

      {/* 模型标题和描述 */}
      <h3 style={{
        margin: '0 0 10px 0',
        fontSize: '16px',
        fontWeight: 'bold',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }}>
        {modelName}
      </h3>

      {/* 模型ID */}
      <div style={{
        fontSize: '13px',
        color: '#666',
        marginBottom: '15px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }}>
        {model.id}
      </div>

      {/* 标签 */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '5px',
        marginBottom: '15px',
        maxHeight: '50px',
        overflow: 'hidden'
      }}>
        {(model.tags || []).slice(0, 3).map((tag, index) => (
          <Tag key={index} minimal>{tag}</Tag>
        ))}
        {(model.tags || []).length > 3 && <Tag minimal>...</Tag>}
      </div>

      <div style={{ flex: 1 }}></div>

      {/* 底部统计信息和操作按钮 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: '10px'
      }}>
        <div style={{
          display: 'flex',
          gap: '15px',
          fontSize: '12px',
          color: '#666'
        }}>
          <span title="下载次数">
            <Icon icon="download" style={{ marginRight: '3px' }} />
            {formatNumber(model.downloads || 0)}
          </span>
          <span title="点赞数">
            <Icon icon="heart" style={{ marginRight: '3px' }} />
            {formatNumber(model.likes || 0)}
          </span>
        </div>
        <Button
          text="下载"
          intent="primary"
          small
          onClick={(e) => {
            e.stopPropagation();
            // 这里可以添加下载逻辑
            if (onModelSelect) {
              onModelSelect(model);
            }
          }}
        />
      </div>
    </Card>
  );
};

export default HuggingfaceModelCard; 