import React, { useState, useEffect } from 'react';
import { 
  Button, 
  FormGroup, 
  InputGroup,
  Spinner,
  Tabs,
  Tab,
  NonIdealState
} from '@blueprintjs/core';
import axios from 'axios';
import HuggingfaceModelCard from './HuggingfaceModelCard';

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
  siblings?: Array<{
    rfilename: string;
    size?: number;
    lfs?: {
      sha256?: string;
    }
  }>;
}

interface HuggingfaceModelsProps {
  onModelSelect?: (model: HuggingfaceModel) => void;
}

const HuggingfaceModels: React.FC<HuggingfaceModelsProps> = ({ onModelSelect }) => {
  const [models, setModels] = useState<HuggingfaceModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [hasSearched, setHasSearched] = useState(false);

  const searchModels = async () => {
    if (!inputValue.trim()) return;

    try {
      setLoading(true);
      setError(null);
      setHasSearched(true);
      
      const response = await axios.get('https://huggingface.co/api/models', {
        params: {
          search: inputValue,
          limit: 50,
          sort: 'downloads',
          direction: -1
        }
      });
      
      setModels(response.data);
    } catch (err) {
      setError('搜索模型失败');
      console.error('搜索模型时出错:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddRepo = async () => {
    if (!inputValue.trim()) return;
    
    try {
      setLoading(true);
      setError(null);
      setHasSearched(true);
      
      // 获取单个仓库信息
      const response = await axios.get(`https://huggingface.co/api/models/${inputValue}`);
      
      // 如果成功获取，添加到模型列表的开头
      if (response.data) {
        setModels(prevModels => [response.data, ...prevModels]);
        setInputValue(''); // 清空输入
      }
    } catch (err) {
      setError('添加仓库失败，请确认仓库ID格式正确');
      console.error('添加仓库时出错:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    searchModels();
  };

  // 根据pipeline_tag过滤模型
  const filteredModels = selectedType === 'all' 
    ? models 
    : models.filter(model => model.pipeline_tag === selectedType);

  // 获取所有可用的模型类型
  const modelTypes = ['all', ...new Set(models.map(model => model.pipeline_tag).filter(Boolean))];

  return (
    <div style={{ paddingLeft: '20px', paddingRight: '20px' }}>
      {/* 合并的搜索/添加仓库区域 */}
      <form onSubmit={handleSearchSubmit}>
        <FormGroup
          helperText="搜索模型或输入仓库ID (例如: 'runwayml/stable-diffusion-v1-5')"
        >
          <div style={{ display: 'flex', gap: '5px' }}>
            <div style={{ flex: 1 }}>
            <InputGroup
              placeholder="搜索模型或输入仓库ID..."
              value={inputValue}
              onChange={handleInputChange}
            />
            </div>
            <Button 
              type="submit" 
              intent="primary"
              disabled={!inputValue.trim() || loading}
            >
              搜索
            </Button>
            <Button 
              intent="success" 
              onClick={handleAddRepo}
              disabled={!inputValue.trim() || loading}
            >
              添加仓库
            </Button>
          </div>
        </FormGroup>
      </form>

      {/* 模型类型标签页 - 只在有模型时显示 */}
      {models.length > 0 && (
        <Tabs
          selectedTabId={selectedType}
          onChange={(newTabId) => setSelectedType(newTabId as string)}
        >
          {modelTypes.map(type => (
            <Tab 
              key={type} 
              id={type} 
              title={type === 'all' ? '全部' : type} 
            />
          ))}
        </Tabs>
      )}

      {/* 模型列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spinner />
        </div>
      ) : error ? (
        <NonIdealState
          icon="error"
          title="加载失败"
          description={error}
        />
      ) : !hasSearched ? (
        <NonIdealState
          icon="search"
          title="搜索Huggingface模型"
          description="输入关键词搜索模型或直接添加仓库ID"
        />
      ) : filteredModels.length === 0 ? (
        <NonIdealState
          icon="search"
          title="未找到模型"
          description="请尝试其他搜索关键词或直接添加仓库ID"
        />
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '20px',
          padding: '20px',
          maxHeight: 'calc(100vh - 220px)',
          overflow: 'auto'
        }}>
          {filteredModels.map(model => (
            <HuggingfaceModelCard 
              key={model.id}
              model={model}
              onModelSelect={onModelSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default HuggingfaceModels; 